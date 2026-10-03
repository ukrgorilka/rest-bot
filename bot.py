"""NyaBot production launcher.

This file is the only process entry point used by Railway.
It deliberately acquires the Neon singleton lock before importing the large
application module, then supervises the polling loop so transient Telegram
/network errors do not leave the service dead.
"""

from __future__ import annotations

import logging
import os
import sys
import time

import config
from core.database import (
    acquire_single_instance_lock,
    release_single_instance_lock,
)


LOG = logging.getLogger("nyabot.startup")


def _configure_logging() -> None:
    level_name = os.environ.get("LOG_LEVEL", "INFO").upper().strip()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        force=True,
    )


def _wait_for_single_instance(max_attempts: int = 60, delay: float = 5.0) -> bool:
    """Wait for another deployment to release the Neon singleton lock.

    Railway can briefly run the old and new deployment at the same time.
    Exiting immediately in that situation can leave the replacement service
    stopped. Waiting makes deployment races self-healing.
    """
    if not config.DATABASE_URL:
        return True

    for attempt in range(1, max_attempts + 1):
        try:
            if acquire_single_instance_lock():
                LOG.info("Neon singleton lock acquired.")
                return True
        except Exception:
            LOG.exception("Unexpected error while acquiring Neon singleton lock.")

        if attempt < max_attempts:
            LOG.warning(
                "Another NyaBot instance appears to be active; "
                "waiting %ss before retry (%s/%s).",
                delay,
                attempt,
                max_attempts,
            )
            time.sleep(delay)

    LOG.error("Could not acquire the Neon singleton lock after %s attempts.", max_attempts)
    return False


def _prepare_polling(newfile) -> None:
    """Make the polling process deterministic after a deployment/restart."""
    bot = getattr(newfile, "bot", None)
    if bot is None:
        return

    try:
        # This bot uses long polling, not a Telegram webhook. Removing a stale
        # webhook prevents getUpdates from being blocked by an old webhook.
        bot.remove_webhook()
        LOG.info("Telegram webhook cleared; long polling is ready.")
    except Exception:
        # Do not prevent startup if Telegram temporarily rejects the request.
        LOG.exception("Could not clear Telegram webhook; continuing to polling.")


def main() -> None:
    _configure_logging()

    problems = config.validate()
    for problem in problems:
        LOG.warning("[CONFIG] %s", problem)

    if not config.BOT_TOKEN:
        LOG.error("[STARTUP] BOT_TOKEN is missing; bot startup aborted.")
        raise SystemExit(1)

    if not _wait_for_single_instance():
        raise SystemExit(1)

    try:
        # Import only after the singleton lock is acquired. newfile.py loads
        # the database and registers the entire handler tree during import.
        import newfile

        _prepare_polling(newfile)

        # run_bot() owns the actual Telegram polling. The supervisor below
        # restarts it after an unexpected exception without re-importing the
        # 450K+ legacy module or registering handlers a second time.
        restart_delay = 3.0

        while True:
            try:
                LOG.info("Starting NyaBot polling.")
                newfile.run_bot()

                # A normal return is unexpected for a long-polling process.
                LOG.warning("NyaBot polling returned unexpectedly; restarting.")
                restart_delay = 3.0

            except KeyboardInterrupt:
                LOG.info("Shutdown requested.")
                break

            except SystemExit:
                raise

            except Exception:
                LOG.exception(
                    "NyaBot polling crashed. Restarting in %.1f seconds.",
                    restart_delay,
                )

            _prepare_polling(newfile)
            time.sleep(restart_delay)
            restart_delay = min(restart_delay * 2.0, 60.0)

    finally:
        release_single_instance_lock()
        LOG.info("Neon singleton lock released.")


if __name__ == "__main__":
    main()
