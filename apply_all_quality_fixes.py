from __future__ import annotations

import argparse
import ast
from pathlib import Path
import shutil
import sys
import time

ROOT = Path.cwd()
FIX_DIR = Path(__file__).resolve().parent


def fail(msg: str) -> None:
    raise RuntimeError(msg)


def replace_once(path: str, old: str, new: str, label: str, *, dry_run: bool) -> None:
    p = ROOT / path
    if not p.exists():
        fail(f"[{label}] file not found: {path}")
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        fail(f"[{label}] expected exactly 1 match in {path}, found {count}")
    if not dry_run:
        p.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"OK {label}: {path}")


def write_exact(path: str, content: str, required_marker: str, label: str, *, dry_run: bool) -> None:
    p = ROOT / path
    current = p.read_text(encoding="utf-8") if p.exists() else ""
    if required_marker not in current:
        fail(f"[{label}] expected marker not found in {path}; refusing full-file replacement")
    if dry_run:
        print(f"OK {label}: {path} (replacement validated)")
        return
    p.write_text(content, encoding="utf-8")
    print(f"OK {label}: {path}")


BOT_PY = '''"""NyaBot process launcher.

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
'''

SAVING_PY = '''"""Persistence service for NyaBot.

Neon/local snapshot implementation lives in core.database. This module is the
application-level bridge used by the bot workers and admin save command.
"""
import copy
import os
import time
import threading

from core.database import (
    load_data as database_load_data,
    save_snapshot,
    acquire_single_instance_lock as database_acquire_single_instance_lock,
    release_single_instance_lock as database_release_single_instance_lock,
)

_save_lock = threading.RLock()


def load_data(default_data_factory, normalize_loaded_data):
    return database_load_data(default_data_factory, normalize_loaded_data)


def save_data(db, *, db_lock, db_version, db_version_getter, db_dirty_setter,
              data_file="rests_data.json", send_backup=False,
              db_channel_id=0, bot_instance=None):
    with _save_lock:
        with db_lock:
            snapshot = copy.deepcopy(db)
            snapshot["_meta"] = {"saved_at": time.time()}
            snapshot_version = db_version
        return save_snapshot(
            snapshot=snapshot,
            snapshot_version=snapshot_version,
            db_version_getter=db_version_getter,
            db_dirty_setter=db_dirty_setter,
            send_backup=send_backup,
            db_channel_id=db_channel_id,
            bot_instance=bot_instance,
        )


def acquire_single_instance_lock():
    """Compatibility wrapper used by newfile.py runtime startup."""
    return database_acquire_single_instance_lock()


def release_single_instance_lock():
    """Release the process-wide Neon advisory lock, if this process owns it."""
    return database_release_single_instance_lock()


def start_autosave_worker(*, is_dirty, last_change_at, save_callback,
                          debounce=25.0, interval=5.0, stop_event=None,
                          on_tick=None):
    stop_event = stop_event or threading.Event()

    def worker():
        while not stop_event.is_set():
            stop_event.wait(interval)
            if stop_event.is_set():
                break
            try:
                if on_tick:
                    on_tick()
            except Exception as exc:
                print(f"[AUTOSAVE] tick failed: {exc}")
            try:
                if is_dirty() and time.time() - last_change_at() >= debounce:
                    save_callback(False)
            except Exception as exc:
                print(f"[AUTOSAVE] save failed: {exc}")

    thread = threading.Thread(target=worker, daemon=True, name="autosave")
    thread.start()
    return thread


def start_periodic_backup_worker(*, data_file="rests_data.json",
                                  db_channel_id=0, bot_instance=None,
                                  interval=7200, stop_event=None,
                                  now_label=None):
    stop_event = stop_event or threading.Event()

    def worker():
        while not stop_event.is_set():
            stop_event.wait(interval)
            if stop_event.is_set():
                break
            try:
                if not db_channel_id or not bot_instance or not os.path.exists(data_file):
                    continue
                with open(data_file, "rb") as f:
                    caption = "💾 Плановый авто-бекап базы данных"
                    if now_label:
                        caption += f" [{now_label()}]"
                    msg = bot_instance.send_document(db_channel_id, f, caption=caption)
                    try:
                        bot_instance.pin_chat_message(
                            db_channel_id, msg.message_id, disable_notification=True
                        )
                    except Exception as exc:
                        print(f"[BACKUP PIN ERROR] {exc}")
            except Exception as exc:
                print(f"[BACKUP ERROR] {exc}")

    thread = threading.Thread(target=worker, daemon=True, name="periodic-backup")
    thread.start()
    return thread


__all__ = [
    "load_data", "save_data", "acquire_single_instance_lock",
    "release_single_instance_lock", "start_autosave_worker",
    "start_periodic_backup_worker",
]
'''


def apply(dry_run: bool = False) -> None:
    # Full-file replacements first.
    write_exact("bot.py", BOT_PY, 'import config', "bot.py singleton launcher", dry_run=dry_run)
    write_exact("services/saving.py", SAVING_PY, 'from core.database import load_data as database_load_data', "saving singleton wrappers", dry_run=dry_run)

    replace_once(
        "core/database.py",
        '''        except Exception as e:\n            print(f"[DB ERROR] Не удалось загрузить Neon: {e}")\n            print("[DB] Переключение на локальный JSON как аварийный fallback.")''',
        '''        except Exception as e:\n            print(f"[DB ERROR] Не удалось загрузить Neon: {e}")\n            # When DATABASE_URL is configured, silently booting from an old\n            # local snapshot is unsafe: the next autosave can overwrite a\n            # newer Neon state with stale JSON. Production therefore fails\n            # closed by default. Local fallback is an explicit emergency\n            # override for operators who understand the risk.\n            allow_local_fallback = os.environ.get("ALLOW_LOCAL_DB_FALLBACK", "").strip().lower() in {\n                "1", "true", "yes", "on"\n            }\n            if DATABASE_URL and not allow_local_fallback:\n                raise RuntimeError(\n                    "Neon database could not be loaded and local fallback is disabled."\n                ) from e\n            print("[DB] Переключение на локальный JSON как аварийный fallback.")''',
        "Neon fallback is fail-closed",
        dry_run=dry_run,
    )

    # Moderation safety + startup lifecycle.
    replace_once(
        "newfile.py",
        '''def _mod_can_act(message, target_id, action):\n    if not _mod_is_group(message):\n        return False, 'Эти команды работают только в группах.'\n    if not can_admin_action(message.chat.id, message.from_user.id, action):\n        return False, 'Недостаточно прав для этой команды или функции админов отключены.'\n    if not target_id:\n        return False, 'Не удалось определить пользователя. Ответь на его сообщение или укажи @username/ID.'\n    if int(target_id) == int(message.from_user.id):\n        return False, 'Нельзя применить модерацию к себе.'\n    try:\n        target_member = bot.get_chat_member(message.chat.id, int(target_id))\n        if target_member.status in ('creator', 'administrator'):\n            return False, 'Нельзя модерировать владельца или администратора с такими правами.'\n    except Exception:\n        pass\n    return True, ''\n''',
        '''def _mod_can_act(message, target_id, action):\n    if not _mod_is_group(message):\n        return False, 'Эти команды работают только в группах.'\n    if not can_admin_action(message.chat.id, message.from_user.id, action):\n        return False, 'Недостаточно прав для этой команды или функции админов отключены.'\n    if not target_id:\n        return False, 'Не удалось определить пользователя. Ответь на его сообщение или укажи @username/ID.'\n\n    actor_id = int(message.from_user.id)\n    target_id = int(target_id)\n    actor_level = get_admin_level(message.chat.id, actor_id)\n    target_level = get_admin_level(message.chat.id, target_id)\n    if target_level > 0 and target_level >= actor_level:\n        return False, 'Нельзя модерировать администратора равного или более высокого уровня.'\n    if target_id == actor_id:\n        return False, 'Нельзя применить модерацию к себе.'\n\n    try:\n        target_member = bot.get_chat_member(message.chat.id, target_id)\n        if target_member.status in ('creator', 'administrator'):\n            return False, 'Нельзя модерировать владельца или администратора с такими правами.'\n    except Exception:\n        # High-impact moderation must fail closed. If Telegram cannot confirm\n        # the target role, do not risk banning/muting an administrator.\n        return False, 'Не удалось проверить права пользователя в Telegram. Повторите действие позже.'\n    return True, ''\n''',
        "moderation fail-closed + hierarchy",
        dry_run=dry_run,
    )

    replace_once(
        "newfile.py",
        '''                    if rec.get('mute_until') and rec['mute_until'] <= now:\n                        try: _mod_unmute(cid, user_id)\n                        except Exception: pass\n                        rec['mute_until'] = None; rec['mute_active'] = False; changed = True\n                    if rec.get('ban_until') and rec['ban_until'] <= now:\n                        try: _mod_unban(cid, user_id)\n                        except Exception: pass\n                        rec['ban_until'] = None; rec['ban_active'] = False; changed = True\n''',
        '''                    if rec.get('mute_until') and rec['mute_until'] <= now:\n                        try:\n                            _mod_unmute(cid, user_id)\n                        except Exception as exc:\n                            print(f'[MOD WORKER] unmute failed chat={cid} user={user_id}: {exc}')\n                        else:\n                            rec['mute_until'] = None\n                            rec['mute_active'] = False\n                            changed = True\n                    if rec.get('ban_until') and rec['ban_until'] <= now:\n                        try:\n                            _mod_unban(cid, user_id)\n                        except Exception as exc:\n                            print(f'[MOD WORKER] unban failed chat={cid} user={user_id}: {exc}')\n                        else:\n                            rec['ban_until'] = None\n                            rec['ban_active'] = False\n                            changed = True\n''',
        "moderation expiry state only after Telegram success",
        dry_run=dry_run,
    )

    replace_once(
        "newfile.py",
        '''def _start_moderation_worker():\n    t = threading.Thread(target=_moderation_worker, daemon=True, name='moderation-expiry')\n    t.start()\n\n_start_moderation_worker()\n''',
        '''def start_moderation_worker():\n    t = threading.Thread(target=_moderation_worker, daemon=True, name='moderation-expiry')\n    t.start()\n''',
        "moderation worker no longer starts on import",
        dry_run=dry_run,
    )

    replace_once(
        "newfile.py",
        '''    leave_banned_chats()\n    threading.Thread(target=vd_facts_worker, daemon=True).start()''',
        '''    leave_banned_chats()\n    # Start moderation expiry only after the singleton guard has been acquired.\n    start_moderation_worker()\n    threading.Thread(target=vd_facts_worker, daemon=True).start()''',
        "moderation worker starts after runtime guard",
        dry_run=dry_run,
    )

    # Safer user resolution: an ambiguous display name must not select the first match.
    replace_once(
        "newfile.py",
        '''    if 'economy' in db:\n        for k, v in list(db['economy'].items()):\n            disp = v.get('display_name', '').lower()\n            if disp == clean_q or clean_tag(disp).lower() == clean_q:\n                return v.get('user_id'), v.get('display_name')\n''',
        '''    if 'economy' in db:\n        display_matches = []\n        for k, v in list(db['economy'].items()):\n            if not isinstance(v, dict):\n                continue\n            disp = str(v.get('display_name', '') or '').lower()\n            if disp == clean_q or clean_tag(disp).lower() == clean_q:\n                display_matches.append((v.get('user_id'), v.get('display_name')))\n        if len(display_matches) == 1:\n            return display_matches[0]\n        if len(display_matches) > 1:\n            # Ambiguous display names are unsafe for destructive/admin actions.\n            return None, query.replace('@', '').strip()\n''',
        "ambiguous display names no longer auto-target first match",
        dry_run=dry_run,
    )

    # The owner sleep-mode gate belongs to the actual extracted message handler.
    replace_once(
        "handlers/moderation.py",
        '''    # Полностью останавливаем обработку пользовательских сообщений. Владелец\n    # остаётся единственным, кто может включить бота обратно.\n    if not db.get('bot_active', True) and not is_super_admin:\n        return\n\n    # bot_active больше не блокирует обычных пользователей.\n    # Старое значение False в Neon не должно переводить бота в режим "только владелец".\n    if not db.get('bot_active', True) and is_super_admin and text_lower in ['/start_bot', '/resume', 'включить бота', 'запустить бота']:\n        db['bot_active'] = True\n        mark_dirty()\n        critical_save('start bot')\n        log_event('ВКЛЮЧЕНИЕ', f'Бот возобновил работу по команде ID:{user_id}')\n        bot.reply_to(message, "🟢 <b>Бот успешно включен и возобновил работу!</b> 😻", parse_mode='HTML')\n        return\n''',
        '''    # In sleep mode ONLY the owner may use explicit resume commands. Every\n    # other message, including owner commands unrelated to resume, is blocked.\n    if not db.get('bot_active', True):\n        if is_super_admin and text_lower in ['/start_bot', '/resume', 'включить бота', 'запустить бота']:\n            db['bot_active'] = True\n            mark_dirty()\n            critical_save('start bot')\n            log_event('ВКЛЮЧЕНИЕ', f'Бот возобновил работу по команде ID:{user_id}')\n            bot.reply_to(message, "🟢 <b>Бот успешно включен и возобновил работу!</b> 😻", parse_mode='HTML')\n        return\n''',
        "bot inactive mode blocks all non-resume traffic",
        dry_run=dry_run,
    )

    # Chat-local daily heroes message count.
    replace_once(
        "handlers/games.py",
        '''    for k, info in econ_items.items():\n        m_day = info.get('msg_stats', {}).get('day_count', 0)\n        if m_day > top_msg_cnt: top_msg_cnt, top_msg_user = m_day, info\n''',
        '''    for k, info in econ_items.items():\n        if not isinstance(info, dict):\n            continue\n        if int(chat_id) < 0:\n            chat_stats = (info.get('msg_stats_chats') or {}).get(str(int(chat_id)), {})\n            m_day = chat_stats.get('day_count', 0) if isinstance(chat_stats, dict) else 0\n        else:\n            m_day = info.get('msg_stats', {}).get('day_count', 0)\n        if m_day > top_msg_cnt: top_msg_cnt, top_msg_user = m_day, info\n''',
        "daily heroes uses chat-local message stats",
        dry_run=dry_run,
    )

    # Stars accounting stays in the canonical finalizer only.
    replace_once(
        "handlers/callbacks.py",
        '''        # Только после успешной проверки товара учитываем Stars в статистике поддержки.\n        econ['stars_donated'] = econ.get('stars_donated', 0) + stars_amount\n\n        # 0. Проверка на подарок другому человеку\n''',
        '''        # 0. Проверка на подарок другому человеку\n''',
        "remove premature Stars statistics increment",
        dry_run=dry_run,
    )

    # Fix stale-econ use in the delayed Telegram dice resolver.
    replace_once(
        "newfile.py",
        '''        with _get_user_action_lock(user_id):\n            try:\n                has_clover = (econ.get('luck_clover_until', 0) > time.time())\n''',
        '''        with _get_user_action_lock(user_id):\n            try:\n                # Refresh the live account after the 3.5s Telegram delay. The\n                # original closure could overwrite newer balance changes made\n                # while the dice message was in flight.\n                econ = get_user_econ(user_id, user_name, username=user_username)\n                has_clover = (econ.get('luck_clover_until', 0) > time.time())\n''',
        "sports dice resolver re-reads live account",
        dry_run=dry_run,
    )

    # Blackjack: refund the stake if the result message itself cannot be sent.
    replace_once(
        "newfile.py",
        '''    bot.send_message(\n        chat_id,\n        f"🃏 <b>БЛЭКДЖЕК (21 ОЧКО)</b> 😺\\n━━━━━━━━━━━━━━━━━━━━\\n"\n        f"👤 Игрок: {make_link(chat_id, user_name, user_id, ping=True)}\\n💰 Ставка: <b>{bet} 🪙</b>\\n\\n"\n        f"🎴 Ваши карты: {p_cards} (Сумма: <b>{p_score}</b>)\\n🤖 Дилер: [{d_cards[0]}, ❓]\\n━━━━━━━━━━━━━━━━━━━━",\n        reply_markup=markup, parse_mode='HTML'\n    )\n''',
        '''    try:\n        bot.send_message(\n            chat_id,\n            f"🃏 <b>БЛЭКДЖЕК (21 ОЧКО)</b> 😺\\n━━━━━━━━━━━━━━━━━━━━\\n"\n            f"👤 Игрок: {make_link(chat_id, user_name, user_id, ping=True)}\\n💰 Ставка: <b>{bet} 🪙</b>\\n\\n"\n            f"🎴 Ваши карты: {p_cards} (Сумма: <b>{p_score}</b>)\\n🤖 Дилер: [{d_cards[0]}, ❓]\\n━━━━━━━━━━━━━━━━━━━━",\n            reply_markup=markup, parse_mode='HTML'\n        )\n    except Exception as exc:\n        active_bj_games.pop(game_id, None)\n        _adjust_balance(econ, bet)\n        reverse_casino_bet(bet, chat_id)\n        print(f"[BJ START SEND ERROR] {exc}")\n        try:\n            bot.reply_to(message, '❌ Не удалось запустить Блэкджек. Ставка возвращена. 😿', parse_mode='HTML')\n        except Exception:\n            pass\n''',
        "blackjack send failure refunds stake",
        dry_run=dry_run,
    )

    # Meme payout must use an atomic delta, not a stale pre-computed balance.
    replace_once(
        "newfile.py",
        '''                econ = get_user_econ(user_id=winner['author_id'])\n                _set_balance(econ, econ.get('balance', 0) + 1500)\n''',
        '''                econ = get_user_econ(user_id=winner['author_id'])\n                _adjust_balance(econ, 1500)\n''',
        "meme reward uses atomic balance delta",
        dry_run=dry_run,
    )

    if dry_run:
        print("DRY RUN complete: no files changed")
        return

    # Compile all Python code outside non/ after modification.
    errors = []
    for p in ROOT.rglob("*.py"):
        if "non" in p.parts or ".git" in p.parts:
            continue
        try:
            ast.parse(p.read_text(encoding="utf-8"), filename=str(p))
        except SyntaxError as exc:
            errors.append(f"{p}: {exc}")
    if errors:
        raise RuntimeError("Syntax verification failed:\n" + "\n".join(errors))
    print("PYTHON AST verification: PASS")


def main() -> int:
    ap = argparse.ArgumentParser(description="Apply NyaBot quality fixes with strict anchor checks")
    ap.add_argument("--check", action="store_true", help="validate every expected change without writing")
    ap.add_argument("--apply", action="store_true", help="apply changes")
    args = ap.parse_args()
    if args.check == args.apply:
        ap.error("choose exactly one of --check or --apply")
    if args.apply:
        # One backup directory per run. Never backs up non/.
        stamp = time.strftime("%Y%m%d-%H%M%S")
        backup_root = ROOT / ".quality_fix_backups" / stamp
        for rel in [
            "bot.py", "services/saving.py", "core/database.py", "newfile.py",
            "handlers/moderation.py", "handlers/games.py", "handlers/callbacks.py",
        ]:
            src = ROOT / rel
            if src.exists():
                dst = backup_root / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
        print(f"Backup created: {backup_root}")
    apply(dry_run=args.check)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
