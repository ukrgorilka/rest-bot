"""Regression checks for the Railway production lifecycle and broadcast safety."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
bot = (ROOT / "bot.py").read_text(encoding="utf-8")
newfile = (ROOT / "newfile.py").read_text(encoding="utf-8")
db = (ROOT / "core/database.py").read_text(encoding="utf-8")
req = (ROOT / "requirements.txt").read_text(encoding="utf-8")

checks = {
    "manual getUpdates loop replaces infinity_polling": "bot.get_updates(" in newfile and "bot.process_new_updates(updates)" in newfile and "bot.infinity_polling()" not in newfile,
    "Telegram 409 becomes explicit polling conflict": "class TelegramPollingConflict" in newfile and "error_code == 409" in newfile,
    "lock health is checked during polling": "lock_health_check" in newfile and "single_instance_lock_is_alive" in db,
    "lock is released on process shutdown": "release_single_instance_lock()" in bot and "finally:" in bot,
    "SIGTERM is handled": "SIGTERM" in bot and "stop_event.set()" in bot,
    "production WSGI server is configured": "from waitress import serve" in newfile and "serve(app" in newfile,
    "waitress dependency is pinned": "waitress==3.0.2" in req,
    "blocked broadcast IDs are remembered": "broadcast_inactive_ids" in newfile,
    "broadcast skips inactive IDs": "cid not in inactive_ids" in newfile and "normalized not in inactive_ids" in newfile,
    "broadcast does not delete game state": "status'] = 'inactive'" in newfile and "broadcast_failed_at" in newfile,
}
failed = [name for name, ok in checks.items() if not ok]
for name, ok in checks.items():
    print(("PASS" if ok else "FAIL") + " — " + name)
if failed:
    raise SystemExit("Failed: " + ", ".join(failed))
print(f"production runtime contract: PASS ({len(checks)}/{len(checks)})")
