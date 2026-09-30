"""NyaBot launcher.

Temporary architecture stage:
- config.py owns environment-backed configuration;
- newfile.py remains the working monolith;
- handlers/services can be migrated later without changing the current bot
  behaviour.

This file deliberately does not duplicate Telegram handlers or business logic.
"""

import os


def load_config():
    """Load and validate the central configuration."""
    import config

    problems = config.validate()
    if problems:
        for problem in problems:
            print(f"[CONFIG] {problem}")

    return config


def main():
    config = load_config()

    # Keep the current working newfile.py untouched for this migration stage.
    #
    # newfile.py currently starts its own Flask/Telegram workers and ends with
    # bot.infinity_polling(), so importing it is intentionally the final step.
    print("[BOT] Loading legacy newfile.py...")
    import newfile  # noqa: F401

    # If a future refactor removes auto-start from newfile.py, the launcher
    # can take over the actual polling here without changing config.py.
    return config


if __name__ == "__main__":
    main()
