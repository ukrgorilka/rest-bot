"""NyaBot process launcher.

The bot implementation lives in newfile.py during the migration period.
This launcher owns the process entry point and keeps configuration centralized.
"""

import config


def main():
    problems = config.validate()
    for problem in problems:
        print(f"[CONFIG] {problem}")

    import newfile

    newfile.run_bot()


if __name__ == "__main__":
    main()
