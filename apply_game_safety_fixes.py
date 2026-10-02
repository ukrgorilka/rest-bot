from __future__ import annotations

import argparse
import ast
from pathlib import Path
import shutil
import sys
import time

ROOT = Path.cwd()

def replace_once(path: str, old: str, new: str, label: str, dry_run: bool):
    p = ROOT / path
    if not p.exists():
        raise RuntimeError(f"[{label}] missing file: {path}")
    text = p.read_text(encoding='utf-8')
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"[{label}] expected 1 exact match in {path}, found {count}")
    if not dry_run:
        p.write_text(text.replace(old, new, 1), encoding='utf-8')
    print(f"OK {label}")


def apply(dry_run=False):
    replace_once(
        'handlers/games.py',
        '''    bot.send_message(\n        message.chat.id,\n        f"🧱 <b>ИГРА КИРПИЧ (СТРОЙКА)</b> 😺\\n"\n        f"━━━━━━━━━━━━━━━━━━━━\\n"\n        f"👤 Строитель: {make_link(message.chat.id, user_name, user_id, ping=False)}\\n"\n        f"💰 Ставка: <b>{bet} 🪙</b>\\n"\n        f"📈 Текущий множитель: <b>1.00x</b>\\n"\n        f"━━━━━━━━━━━━━━━━━━━━\\n"\n        f"<i>Делайте шаги, чтобы увеличить множитель, но осторожно: кирпич может сорваться в любой момент!</i> 😸",\n        reply_markup=markup,\n        parse_mode='HTML'\n                             )\n''',
        '''    try:\n        bot.send_message(\n            message.chat.id,\n            f"🧱 <b>ИГРА КИРПИЧ (СТРОЙКА)</b> 😺\\n"\n            f"━━━━━━━━━━━━━━━━━━━━\\n"\n            f"👤 Строитель: {make_link(message.chat.id, user_name, user_id, ping=False)}\\n"\n            f"💰 Ставка: <b>{bet} 🪙</b>\\n"\n            f"📈 Текущий множитель: <b>1.00x</b>\\n"\n            f"━━━━━━━━━━━━━━━━━━━━\\n"\n            f"<i>Делайте шаги, чтобы увеличить множитель, но осторожно: кирпич может сорваться в любой момент!</i> 😸",\n            reply_markup=markup,\n            parse_mode='HTML'\n        )\n    except Exception as exc:\n        active_brick.pop(game_id, None)\n        _adjust_balance(econ, bet)\n        reverse_casino_bet(bet, chat_id)\n        print(f"[BRICK START SEND ERROR] {exc}")\n        try:\n            bot.reply_to(message, '❌ Не удалось запустить игру. Ставка возвращена. 😿', parse_mode='HTML')\n        except Exception:\n            pass\n''',
        'brick start UI failure refunds stake', dry_run)

    replace_once(
        'handlers/games.py',
        '''    sent_msg = bot.send_message(\n        message.chat.id,\n        f"🚀 <b>ИГРА КРАШ (CRASH ROCKET)</b> 😺\\n"\n        f"━━━━━━━━━━━━━━━━━━━━\\n"\n        f"👤 Пилот: {make_link(message.chat.id, user_name, user_id, ping=False)}\\n"\n        f"💰 Ставка: <b>{bet} 🪙</b>\\n"\n        f"📈 Запуск двигателей... [🚀☁️☁️☁️☁️☁️☁️]\\n"\n        f"━━━━━━━━━━━━━━━━━━━━\\n"\n        f"<i>Приготовьтесь забрать куш!</i> 😸",\n        reply_markup=markup,\n        parse_mode='HTML'\n    )\n''',
        '''    try:\n        sent_msg = bot.send_message(\n            message.chat.id,\n            f"🚀 <b>ИГРА КРАШ (CRASH ROCKET)</b> 😺\\n"\n            f"━━━━━━━━━━━━━━━━━━━━\\n"\n            f"👤 Пилот: {make_link(message.chat.id, user_name, user_id, ping=False)}\\n"\n            f"💰 Ставка: <b>{bet} 🪙</b>\\n"\n            f"📈 Запуск двигателей... [🚀☁️☁️☁️☁️☁️☁️]\\n"\n            f"━━━━━━━━━━━━━━━━━━━━\\n"\n            f"<i>Приготовьтесь забрать куш!</i> 😸",\n            reply_markup=markup,\n            parse_mode='HTML'\n        )\n    except Exception as exc:\n        active_crash.pop(game_id, None)\n        _adjust_balance(econ, bet)\n        reverse_casino_bet(bet, chat_id)\n        print(f"[CRASH START SEND ERROR] {exc}")\n        try:\n            bot.reply_to(message, '❌ Не удалось запустить Краш. Ставка возвращена. 😿', parse_mode='HTML')\n        except Exception:\n            pass\n        return\n''',
        'crash start UI failure refunds stake', dry_run)

    replace_once(
        'handlers/games.py',
        '''    bot.reply_to(\n        message,\n        f"💣 <b>НАСТРОЙКА ИГРЫ «САПЁР»</b> 😺\\n"\n        f"━━━━━━━━━━━━━━━━━━━━\\n"\n        f"💰 Ставка: <b>{bet} 🪙</b>\\n\\n"\n        f"Шаг 1: <b>Выберите размер игрового поля:</b> 😸",\n        reply_markup=markup,\n        parse_mode='HTML'\n    )\n''',
        '''    try:\n        bot.reply_to(\n            message,\n            f"💣 <b>НАСТРОЙКА ИГРЫ «САПЁР»</b> 😺\\n"\n            f"━━━━━━━━━━━━━━━━━━━━\\n"\n            f"💰 Ставка: <b>{bet} 🪙</b>\\n\\n"\n            f"Шаг 1: <b>Выберите размер игрового поля:</b> 😸",\n            reply_markup=markup,\n            parse_mode='HTML'\n        )\n    except Exception as exc:\n        active_mines.pop(game_id, None)\n        _adjust_balance(econ, bet)\n        reverse_casino_bet(bet, chat_id)\n        print(f"[MINES START SEND ERROR] {exc}")\n        try:\n            bot.reply_to(message, '❌ Не удалось запустить Сапёра. Ставка возвращена. 😿', parse_mode='HTML')\n        except Exception:\n            pass\n''',
        'mines start UI failure refunds stake', dry_run)

    replace_once(
        'handlers/games.py',
        '''    bot.send_message(\n        chat_id,\n        f"✌️ <b>ДУЭЛЬ: КАМЕНЬ-НОЖНИЦЫ-БУМАГА!</b> 😺\\n━━━━━━━━━━━━━━━━━━━━\\n"\n        f"⚔️ {make_link(chat_id, user_name, user_id, ping=True)} VS {make_link(chat_id, target_user, target_user_id, ping=True)}\\n"\n        f"💰 Ставка: <b>{bet} 🪙</b> с каждого (Общий банк: <b>{bet * 2} 🪙</b>)!\\n"\n        f"━━━━━━━━━━━━━━━━━━━━\\n"\n        f"<i>Оба дуэлянта, сделайте свой выбор на кнопках ниже:</i> 😸",\n        reply_markup=markup, parse_mode='HTML'\n    )\n''',
        '''    try:\n        bot.send_message(\n            chat_id,\n            f"✌️ <b>ДУЭЛЬ: КАМЕНЬ-НОЖНИЦЫ-БУМАГА!</b> 😺\\n━━━━━━━━━━━━━━━━━━━━\\n"\n            f"⚔️ {make_link(chat_id, user_name, user_id, ping=True)} VS {make_link(chat_id, target_user, target_user_id, ping=True)}\\n"\n            f"💰 Ставка: <b>{bet} 🪙</b> с каждого (Общий банк: <b>{bet * 2} 🪙</b>)!\\n"\n            f"━━━━━━━━━━━━━━━━━━━━\\n"\n            f"<i>Оба дуэлянта, сделайте свой выбор на кнопках ниже:</i> 😸",\n            reply_markup=markup, parse_mode='HTML'\n        )\n    except Exception as exc:\n        active_rps_games.pop(game_id, None)\n        # The action handler is already serialized for the initiating user;\n        # use the ordered helper for the two-account refund.\n        with serialized_multi_user_action(user_id, target_user_id):\n            live_econ = get_user_econ(user_id, user_name, username=message.from_user.username)\n            live_target = get_user_econ(target_user_id, target_user)\n            _adjust_balance(live_econ, bet)\n            _adjust_balance(live_target, bet)\n            mark_dirty()\n        print(f"[RPS START SEND ERROR] {exc}")\n        try:\n            bot.reply_to(message, '❌ Не удалось создать дуэль. Обе ставки возвращены. 😿', parse_mode='HTML')\n        except Exception:\n            pass\n''',
        'rps start UI failure refunds both stakes', dry_run)

    if not dry_run:
        for p in ROOT.rglob('*.py'):
            if 'non' in p.parts or '.git' in p.parts:
                continue
            ast.parse(p.read_text(encoding='utf-8'), filename=str(p))
        print('PYTHON AST verification: PASS')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()
    if args.check == args.apply:
        ap.error('choose exactly one of --check or --apply')
    if args.apply:
        stamp = time.strftime('%Y%m%d-%H%M%S')
        backup = ROOT / '.quality_fix_backups' / ('game-' + stamp)
        for rel in ['handlers/games.py']:
            src=ROOT/rel
            if src.exists():
                dst=backup/rel; dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dst)
        print(f'Backup created: {backup}')
    apply(dry_run=args.check)

if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('ERROR:', exc, file=sys.stderr)
        raise SystemExit(2)
