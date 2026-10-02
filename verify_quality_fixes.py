from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path.cwd()
CHECKS = []


def check(label: str, condition: bool):
    CHECKS.append((label, bool(condition)))


def text(rel: str) -> str:
    p = ROOT / rel
    if not p.exists():
        return ''
    return p.read_text(encoding='utf-8')

bot = text('bot.py')
saving = text('services/saving.py')
db = text('core/database.py')
new = text('newfile.py')
mod = text('handlers/moderation.py')
games = text('handlers/games.py')
callbacks = text('handlers/callbacks.py')

check('bot.py imports singleton lock', 'acquire_single_instance_lock' in bot and 'release_single_instance_lock' in bot)
check('bot.py acquires before importing newfile', bot.find('acquire_single_instance_lock()') < bot.find('import newfile'))
check('saving.py exposes singleton wrappers', 'def acquire_single_instance_lock():' in saving and 'def release_single_instance_lock():' in saving)
check('Neon fallback is fail-closed', 'local fallback is disabled' in db and 'ALLOW_LOCAL_DB_FALLBACK' in db)
check('moderation worker does not start at import', '_start_moderation_worker()' not in new)
check('moderation worker has runtime entry point', 'def start_moderation_worker():' in new)
check('moderation expiry clears state only on success', "else:\n                            rec['mute_until'] = None" in new and "else:\n                            rec['ban_until'] = None" in new)
check('moderation action is fail-closed on Telegram lookup errors', 'Не удалось проверить права пользователя в Telegram' in new)
check('moderation action checks internal hierarchy', 'target_level >= actor_level' in new)
check('sleep mode blocks non-resume traffic', 'if not db.get(\'bot_active\', True):' in mod and "'/start_bot'" in mod)
check('daily heroes uses per-chat counters', 'msg_stats_chats' in games and 'chat_stats' in games)
check('premature Stars increment removed', "econ['stars_donated'] = econ.get('stars_donated', 0) + stars_amount" not in callbacks)
check('delayed dice resolver refreshes live econ', "econ = get_user_econ(user_id, user_name, username=user_username)" in new[new.find('def process_sport_dice_game'):])
check('ambiguous display names no longer auto-select first match', 'display_matches' in new and 'len(display_matches) > 1' in new)
check('blackjack send failure refund exists', '[BJ START SEND ERROR]' in new and 'reverse_casino_bet(bet, chat_id)' in new)
check('meme reward uses atomic delta', "_adjust_balance(econ, 1500)" in new)
check('brick send failure refund exists', '[BRICK START SEND ERROR]' in games)
check('crash send failure refund exists', '[CRASH START SEND ERROR]' in games)
check('mines send failure refund exists', '[MINES START SEND ERROR]' in games)
check('rps send failure refunds both players', '[RPS START SEND ERROR]' in games and 'live_target' in games)

# Do not touch the protected non/ subtree.
check('no quality artifact targets non/', not any('non' in p.parts for p in (ROOT / 'non').glob('*')) if (ROOT / 'non').exists() else True)

syntax_errors = []
for p in ROOT.rglob('*.py'):
    if 'non' in p.parts or '.git' in p.parts:
        continue
    try:
        ast.parse(p.read_text(encoding='utf-8'), filename=str(p))
    except SyntaxError as exc:
        syntax_errors.append(f'{p}: {exc}')

ok = all(v for _, v in CHECKS) and not syntax_errors
for label, value in CHECKS:
    print(('PASS' if value else 'FAIL') + ' — ' + label)
if syntax_errors:
    print('FAIL — syntax errors:')
    for err in syntax_errors:
        print('  ' + err)
print(f'\nResult: {"PASS" if ok else "FAIL"} ({sum(v for _,v in CHECKS)}/{len(CHECKS)} static checks)')
raise SystemExit(0 if ok else 1)
