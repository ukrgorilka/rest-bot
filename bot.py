"""NyaBot production launcher.

This file is the only process entry point used by Railway.
It deliberately acquires the Neon singleton lock before importing the large
application module, then supervises the polling loop so transient Telegram
/network errors do not leave the service dead.
"""

from __future__ import annotations

import logging
import os
import signal
import threading
import time

import config
from core.database import (
    acquire_single_instance_lock,
    release_single_instance_lock,
    single_instance_lock_is_alive,
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




def _is_telegram_conflict(exc: BaseException) -> bool:
    """Detect Telegram's 409 polling conflict across API error representations."""
    code = getattr(exc, "error_code", None)
    if code == 409:
        return True
    result_json = getattr(exc, "result_json", None)
    if isinstance(result_json, dict) and result_json.get("error_code") == 409:
        return True
    message = str(exc or "").lower()
    return "409" in message and (
        "getupdates" in message or "conflict" in message or "terminated by other" in message
    )

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

    if not config.DATABASE_URL and not config.ALLOW_JSON_BOOTSTRAP:
        LOG.error(
            "[STARTUP] DATABASE_URL is missing and ALLOW_JSON_BOOTSTRAP is disabled; "
            "refusing to start without the canonical Neon database."
        )
        raise SystemExit(1)

    if not _wait_for_single_instance():
        raise SystemExit(1)

    stop_event = threading.Event()

    def _request_shutdown(signum, _frame):
        LOG.info("Shutdown signal %s received; stopping NyaBot cleanly.", signum)
        stop_event.set()

    for _sig_name in ("SIGTERM", "SIGINT"):
        _sig = getattr(signal, _sig_name, None)
        if _sig is not None:
            signal.signal(_sig, _request_shutdown)

    try:
        import newfile

        _prepare_polling(newfile)

        LOG.info("Starting NyaBot polling with a single supervised getUpdates loop.")
        try:
            newfile.run_bot(
                stop_event=stop_event,
                lock_health_check=single_instance_lock_is_alive,
            )
        except KeyboardInterrupt:
            LOG.info("Shutdown requested.")
        except SystemExit:
            raise
        except Exception as exc:
            if _is_telegram_conflict(exc):
                # Do not create another polling thread. A 409 means Telegram is
                # already serving getUpdates to another process. Give an older
                # Railway deployment time to terminate, then let Railway restart
                # this process and retry the Neon singleton acquisition.
                LOG.error(
                    "Telegram returned 409 Conflict. Another instance is consuming "
                    "getUpdates; stopping this process instead of retrying in parallel."
                )
                stop_event.set()
                time.sleep(30.0)
                raise SystemExit(2)
            LOG.exception("NyaBot polling stopped because of an unexpected error.")
            raise
    finally:
        stop_event.set()
        release_single_instance_lock()
        LOG.info("Neon singleton lock released; process shutdown complete.")


if __name__ == "__main__":
    main()
