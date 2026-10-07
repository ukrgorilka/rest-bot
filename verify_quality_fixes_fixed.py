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
businesses_handler = text('handlers/businesses.py')
config = text('config.py')
requirements = text('requirements.txt')
test_runtime = text('test_runtime_regressions.py')
loc = text('core/localization.py')

check('bot.py imports singleton lock', 'acquire_single_instance_lock' in bot and 'release_single_instance_lock' in bot)
check('bot.py acquires before importing newfile', bot.find('acquire_single_instance_lock()') < bot.find('import newfile'))
check('saving.py exposes singleton wrappers', 'def acquire_single_instance_lock():' in saving and 'def release_single_instance_lock():' in saving)
check('Neon fallback is fail-closed', 'local fallback is disabled' in db and 'ALLOW_LOCAL_DB_FALLBACK' in db)
check('moderation worker does not start at import', '_start_moderation_worker()' not in new)
check('moderation worker has runtime entry point', 'def start_moderation_worker():' in new)
check('moderation expiry clears state only on success', "else:\n                            rec['mute_until'] = None" in new and "else:\n                            rec['ban_until'] = None" in new)
check('moderation action is fail-closed on Telegram lookup errors', 'Не удалось проверить права пользователя в Telegram' in new)
check('moderation action checks internal hierarchy', 'target_level >= actor_level' in new)
check('sleep mode blocks non-resume traffic', "if not db.get('bot_active', True):" in mod and "'/start_bot'" in mod)
check('daily heroes uses per-chat counters', 'msg_stats_chats' in games and 'chat_stats' in games)
check('premature Stars increment removed', "econ['stars_donated'] = econ.get('stars_donated', 0) + stars_amount" not in callbacks)
check('message-not-modified helper exists', 'def _is_message_not_modified_error(exc):' in loc and "'message is not modified'" in loc)
check('edit text suppresses harmless no-op', 'if _is_message_not_modified_error(exc):' in loc and 'bot.edit_message_text = edit_message_text' in loc)
check('edit reply markup is protected', 'def edit_message_reply_markup(' in loc and 'bot.edit_message_reply_markup = edit_message_reply_markup' in loc)
check('delayed dice resolver refreshes live econ', "econ = get_user_econ(user_id, user_name, username=user_username)" in new[new.find('def process_sport_dice_game'):])
check('ambiguous display names no longer auto-select first match', 'display_matches' in new and 'len(display_matches) > 1' in new)
check('blackjack send failure refund exists', '[BJ START SEND ERROR]' in new and 'reverse_casino_bet(bet, chat_id)' in new)
check('meme reward uses atomic delta', "_adjust_balance(econ, 1500)" in new)
check('brick send failure refund exists', '[BRICK START SEND ERROR]' in games)
check('crash send failure refund exists', '[CRASH START SEND ERROR]' in games)
check('mines send failure refund exists', '[MINES START SEND ERROR]' in games)
check('rps send failure refunds both players', '[RPS START SEND ERROR]' in games and 'live_target' in games)

# New callback/business/persistence checks.
check('callback parser has a single safe acknowledgement helper', 'def _answer_callback_query(' in callbacks and 'contextvars' in callbacks and '_CALLBACK_ANSWERED' in callbacks)
check('callback handler auto-acknowledges forgotten return paths', "if call and getattr(call, 'id', None) and not _CALLBACK_ANSWERED.get():" in callbacks)
check('v0.3 business callbacks parse owner suffix only once', "_,b_id=action_data.split(':',1)" in callbacks and "_,b_id,owner=action_data.split(':',2)" not in callbacks)
check('v0.3 business purchase has durable-save rollback boundary', "if not critical_save('business purchase', retries=3):" in callbacks and 'econ.clear(); econ.update(state_before); mark_dirty()' in callbacks)
check('legacy business mutations rollback on failed Neon save', callbacks.count('state_before') >= 7 and callbacks.count('econ.clear(); econ.update(state_before)') >= 7)
check('business catalog shows price and ownership', "status = '✅ Куплен' if owned else '❌ Не куплен'" in new and 'price_text = f"{int(info.get(\'price\', 0) or 0):,} 🪙"' in new)
check('donor business catalog shows Stars price and ownership', 'price_text = f"{_business_stars_price(b_id)} ⭐"' in new and 'if is_donor:' in new)
check('business command persistence rolls back on save failure', 'state_before = copy.deepcopy(econ)' in businesses_handler and 'Начисление отменено' in businesses_handler)
check('Neon empty-state writes must succeed', 'the initial default state could not be persisted' in db and 'explicit JSON bootstrap was requested' in db)
check('reachable Neon is never overwritten by pending local snapshot', 'локальный snapshot НЕ загружается поверх Neon' in db)
check('missing Neon does not silently use old JSON', 'rests_data.json не используется без явного ALLOW_JSON_BOOTSTRAP=1' in db)
check('invalid numeric ENV is reported instead of crashing at import', 'def _env_int(' in config and 'def _env_float(' in config and '_CONFIG_PROBLEMS' in config)
check('production startup refuses missing canonical Neon', 'DATABASE_URL is missing and ALLOW_JSON_BOOTSTRAP is disabled' in bot)
check('runtime regressions exercise real callback handler', (ROOT / 'test_runtime_regressions.py').exists() and 'callbacks.callback_inline(call)' in test_runtime)
check('key runtime dependencies are pinned', 'Flask==' in requirements and 'pyTelegramBotAPI==' in requirements and 'psycopg2-binary==' in requirements)
check('broadcast marks blocked private users inactive', 'broadcast_status' in new and 'bot was blocked by the user' in new and 'def _mark_broadcast_inactive' in new)
check('broadcast excludes inactive recipients before sending', "econ.get('broadcast_status', 'active') != 'active'" in new and 'skipped_inactive' in new)
check('production web server no longer uses Flask app.run', 'waitress_serve(app' in new and 'app.run(host=' not in new)
check('waitress production dependency is pinned', 'waitress==' in requirements)

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
print(f'\nResult: {"PASS" if ok else "FAIL"} ({sum(v for _, v in CHECKS)}/{len(CHECKS)} static checks)')
raise SystemExit(0 if ok else 1)
