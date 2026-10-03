"""NyaBot process launcher.

The bot implementation lives in newfile.py during the migration period.
This launcher owns the process entry point and keeps configuration centralized.
"""

import config
from core.database import (
    acquire_single_instance_lock,
    release_single_instance_lock,
)


def main():
    problems = config.validate()
    for problem in problems:
        print(f"[CONFIG] {problem}")

    if not config.BOT_TOKEN:
        print("[STARTUP] BOT_TOKEN is missing; bot startup aborted.")
        return

    # Acquire the Neon singleton BEFORE importing newfile.py. Importing the
    # application initializes shared state and registers workers/handlers, so
    # the guard must happen before that work.
    if config.DATABASE_URL and not acquire_single_instance_lock():
        print("[STARTUP] Another bot instance owns the Neon singleton lock.")
        return

    try:
        import newfile
        newfile.run_bot()
    finally:
        release_single_instance_lock()


if __name__ == "__main__":
    main()
