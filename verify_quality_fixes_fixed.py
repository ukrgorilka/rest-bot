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
shop = text('handlers/shop.py')
stars = text('services/stars.py')
loc = text('core/localization.py')

check('bot.py imports singleton lock', 'acquire_single_instance_lock' in bot and 'release_single_instance_lock' in bot)
check('bot.py acquires before importing newfile', bot.find('acquire_single_instance_lock()') < bot.find('import newfile'))
check('saving.py exposes singleton wrappers', 'def acquire_single_instance_lock():' in saving and 'def release_single_instance_lock():' in saving)
check('Neon fallback is fail-closed', 'refusing to boot from local JSON' in db and 'ALLOW_JSON_BOOTSTRAP' in db)
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
check('ordinary business purchases use durable field-scoped transactions', 'def _purchase_ordinary_business(' in callbacks and '_purchase_ordinary_business(econ, b_id)' in callbacks and '_durable_profile_transaction(' in callbacks)
check('business buy/upgrade/sell operations share durable transaction wrappers', all(x in callbacks for x in ('_purchase_ordinary_business(econ, b_id)', '_upgrade_business_durably(econ, b_id, donor=False)', '_upgrade_business_durably(econ, b_id, donor=True)', '_sell_ordinary_business_durably(econ, b_id)')) and '_durable_profile_transaction(' in callbacks)
check('business catalog shows price and ownership', "'✅ Куплен' if x['owned'] else '❌ Не куплен'" in new and 'price_text = f"{int(info.get(\'price\', 0) or 0):,} 🪙"' in new)
check('donor business catalog shows Stars price and ownership', 'price_text = f"{_business_stars_price(b_id)} ⭐"' in new and 'if is_donor:' in new)
check('business command persistence rolls back on save failure', 'state_before = copy.deepcopy(econ)' in businesses_handler and 'Начисление отменено' in businesses_handler)
check('Neon empty-state writes must succeed', 'the initial default state could not be persisted' in db and 'explicit JSON bootstrap was requested' in db)
check('reachable Neon is never overwritten by pending local snapshot', 'Neon is the canonical source of live progress' in db and 'локальный JSON не накатывается поверх неё' in db)
check('missing Neon does not silently use old JSON', 'rests_data.json не используется без явного ALLOW_JSON_BOOTSTRAP=1' in db)
check('invalid numeric ENV is reported instead of crashing at import', 'def _env_int(' in config and 'def _env_float(' in config and '_CONFIG_PROBLEMS' in config)
check('production startup refuses missing canonical Neon', 'DATABASE_URL is missing and ALLOW_JSON_BOOTSTRAP is disabled' in bot)
check('runtime regressions exercise real callback handler', (ROOT / 'test_runtime_regressions.py').exists() and 'callbacks.callback_inline(call)' in test_runtime)
check('custom title creation charges 4 Telegram Stars per title', "invoice_payload=f'ctitle:{user_id}:{token}'" in shop and "currency='XTR'" in shop and "amount=4" in shop and "raw_payload.startswith('ctitle:')" in stars)
check('custom title command has spelling aliases and saved-state actions', "commands=['create_tittle', 'create_title', 'custom_title', 'кастомный_титул']" in shop and all(token in shop for token in ('custom_title_text', 'custom title unequip', 'custom title equip', 'custom title delete')))
check('custom title field is initialized and old titles are migrated', "('custom_title_text', None)" in new and "u_data['custom_titles']" in new and "econ['custom_title_text'] = str(legacy_text)" in shop)
check('paid custom-title entitlement is recorded in payment handler', "if c_type == 'title_cert':" in callbacks and "econ['has_custom_title_cert'] = True" in callbacks and "econ['paid_stars_items']" in callbacks and '/create_tittle' in callbacks)
check('custom-title runtime tests cover four-Star invoices and persistence rollback', all(name in test_runtime for name in ('test_create_off_on_delete_roundtrip', 'test_failed_persistence_rolls_back', 'test_reserved_word_can_be_used_as_title', 'test_each_new_title_requires_a_four_star_invoice', 'test_temporary_pack_error_is_retried_after_negative_cache_ttl')))
check('inventory has separate item and badge categories', "inv_cat_items:{user_id}" in new and "category == 'items'" in new and "'items', 'themes'" in callbacks)
check('key runtime dependencies are pinned', 'Flask==' in requirements and 'pyTelegramBotAPI==' in requirements and 'psycopg2-binary==' in requirements)

check('slot two-of-a-kind pays only 0.7x', 'multiplier = 0.7' in mod and 'Возвращается 70% ставки (x0.7)' in mod)
check('actual casino payout multipliers are shown after pool caps', 'Фактический множитель' in callbacks and 'фактически x{effective_mult:.2f}' in mod)
check('Mini App client scores do not award score-based progression', 'mini_reported_records' in new and 'mini_verified_records' in new and 'score_used_for_economy' in new)
check('Mini App completion reward is fixed and daily capped', 'safe_daily_cap = min(int(MINIAPP_DAILY_REWARD_CAP), 500)' in new and 'reward = min(25, remaining)' in new)
check('custom title payments are restored and verified before grant', 'pending_custom_title_orders' in callbacks and 'grant paid custom title' in callbacks and 'ctitle:' in stars)
check('admin runtime diagnostics command is registered', 'commands=["nyadiag", "диагностика"]' in new and 'def _nyabot_diagnostics_handler' in new)
check('economy balance changes are journaled', "'economy_transactions'" in new and 'def _adjust_balance(econ, amount, reason=' in new)
# Business incomes are checked against the actual 45%-per-level formula at level 5 (factor 2.8).
check('high-cost business max-level income is balanced to targets',
      "'base_income': 220000" in new
      and "'base_income': 70000" in new
      and "'base_income': 77000" in new
      and "'base_income': 107000" in new
      and '1 + (level - 1) * 0.45' in new
      and int(70000 * 2.8) < 220000
      and int(77000 * 2.8) < 220000
      and int(107000 * 2.8) <= 300000)

# Data-driven laws/work checks.
jobs_data = text('data/jobs.py')
laws_data = text('data/laws.ru')
rules_service = text('services/rules.py')
rules_handler = text('handlers/rules.py')
check('job data moved out of newfile', 'from data.jobs import JOBS' in new and 'JOBS = {' not in new)
check('job definitions validate', 'def validate_jobs' in jobs_data and "REQUIRED_FIELDS = ('name', 'req_exp', 'chance', 'min_pay', 'max_pay', 'exp_gain')" in jobs_data)
check('law data file exists with both countries', laws_data.count('[law]') >= 20 and 'country=UA' in laws_data and 'country=RU' in laws_data)
check('law parser is data-only and random', 'def load_laws' in rules_service and 'def random_law' in rules_service)
check('law trigger phrases are registered before catch-all messages', 'cmd_law_joke' in rules_handler and "REGISTRATION_ORDER = ['cmd_law_joke'" in text('handlers/__init__.py'))
check('law country callback exists', "action_data.startswith('law_country:')" in callbacks and "callback_data=f'law_country:UA:{user_id}'" in rules_handler)
check('work callback validates job data and isolates errors', '_perform_job_shift' in text('handlers/economy.py') and '[WORK CALLBACK ERROR]' in callbacks)
check('production WSGI remains enabled', "serve(app, host='0.0.0.0', port=port, threads=4)" in new and 'waitress==' in requirements)

# Do not touch the protected non/ subtree.
check('no quality artifact targets non/', not any('non' in p.parts for p in (ROOT / 'non').glob('*')) if (ROOT / 'non').exists() else True)


# v0.5 reliability hardening contracts.
check('float environment settings reject NaN and Infinity', 'math.isfinite(value)' in text('config.py'))
check('save snapshot version is read under the state lock', 'snapshot_version = db_version_getter() if db_version_getter else db_version' in text('services/saving.py'))
check('dirty flag uses an atomic compare-and-clear callback', 'db_dirty_clear_if_version' in text('newfile.py') and 'db_dirty = False' in text('newfile.py')[text('newfile.py').find('def _clear_dirty_if_version'):text('newfile.py').find('return saving_service.save_data')])
check('snapshot saver never clears dirty state through a non-atomic fallback', 'db_dirty_clear_if_version(snapshot_version)' in text('core/database.py') and 'bookkeeping error after a successful durable save' in text('core/database.py'))
check('successful Neon commit survives a local backup write failure', 'If PostgreSQL has already committed this snapshot' in text('core/database.py') and 'if not saved_to_pg:\n                return False' in text('core/database.py'))
check('per-user action lock registry releases inactive locks', 'weakref.WeakValueDictionary()' in text('core/locks.py') and 'Active handlers keep strong references' in text('core/locks.py'))
check('account level lookup uses logarithmic search and integer thresholds', 'while low + 1 < high:' in text('services/economy.py') and 'isqrt(10_000 * n * n * n)' in text('services/economy.py'))
check('Mini App input size is bounded', 'app.config["MAX_CONTENT_LENGTH"] = 64 * 1024' in text('newfile.py'))
check('Mini App initData rejects duplicate and oversized field sets', 'max_num_fields=32' in text('newfile.py') and 'len({key for key, _value in parsed}) != len(parsed)' in text('newfile.py'))
check('absolute balance changes use the economy journal', "delta = new_balance - current" in text('newfile.py') and "_record_economy_transaction(econ, delta, current, new_balance, reason)" in text('newfile.py'))
check('transfer helper records both account sides in the journal', "f'Перевод игроку {receiver_id}'" in text('newfile.py') and "f'Перевод от игрока {sender_id}'" in text('newfile.py'))
check('runtime regressions cover persistence races, signed Mini App auth, and economy journal', all(token in text('test_runtime_regressions.py') for token in ('test_concurrent_mutation_cannot_have_its_dirty_flag_cleared', 'test_duplicate_auth_fields_are_rejected', 'test_adjust_and_set_balance_both_record_actual_delta')))
check('money history command is registered without replacing rest history', 'moneyhistory' in text('handlers/bank.py') and 'cmd_money_history' in text('handlers/__init__.py') and "commands=['history'," in text('handlers/bank.py'))
check('money history displays only recent operations and escapes reasons', '[-10:]' in text('handlers/bank.py') and 'html.escape' in text('handlers/bank.py') and 'test_history_shows_latest_ten_and_escapes_reasons' in test_runtime)
check('unlabelled balance changes receive directional journal labels', "reason = 'Начисление коинов' if delta > 0 else 'Списание коинов'" in new and 'test_unlabelled_changes_get_directional_reason' in test_runtime)


# v0.6 owner recovery, business pages, and Mini App Tamagotchi contracts.
check('chat creator can access settings while admin functions are disabled', "if action == 'settings' and is_chat_owner(chat_id, user_id):" in new and "if not get_chat_settings(chat_id).get('admin_functions_enabled', True):" in new)
settings_callback_block = callbacks[callbacks.find('# НАСТРОЙКИ'):callbacks.find("elif action_data.startswith('set_user_lang_')")]
check('settings callbacks use the shared permission check', "can_admin_action(chat_id, user_id, 'settings')" in settings_callback_block and 'if not is_admin(chat_id, user_id): return' not in settings_callback_block)
check('warn limit callback respects admin-function kill switch', "elif action_data == 'set_warn_limit':\n            if not can_admin_action(chat_id, user_id, 'settings')" in callbacks)
check('admin-function command is restricted to actual chat creator', "if not is_chat_owner(message.chat.id, message.from_user.id):" in text('handlers/moderation.py'))
check('Tamagotchi does not display a fabricated game record', "x[0]==='tamagotchi'?'':`<span class=\"game-record\"" in text('miniapp/app.js'))
check('Telegram business catalog is paginated and links each card', "page_size = 8" in new and "biz_catalog_page:{page + 1}:{user_id}" in new and "biz_detail_open:{x['number']}:{user_id}" in new)
check('business catalog total income is calculated across full catalog', 'for idx, b_id, info, is_donor in catalog:' in new and 'total_hourly_income += hourly_income' in new and 'total_hourly_income * (1 - tax_rate)' in new)
check('business page callbacks are routed to the actual catalog renderer', "action_data.startswith('biz_catalog_page:')" in callbacks and "page=int(raw_page)" in callbacks)
check('Mini App business cards use filters and pagination', "function empireFilter(filter)" in text('miniapp/app.js') and 'pageSize=4' in text('miniapp/app.js') and "state.businessFilter==='donor'" in text('miniapp/app.js'))
check('Tamagotchi state is separated from existing Telegram pets', "econ['mini_tamagotchi']" in new and "econ['pet']" not in new[new.find('def mini_tamagotchi_api'):new.find('def _mini_world_snapshot')])
check('Tamagotchi actions are allow-listed and grant no currency', "action not in {'feed', 'play', 'sleep', 'clean', 'rename'}" in new and "_set_balance" not in new[new.find('def mini_tamagotchi_api'):new.find('def _mini_world_snapshot')])
check('Tamagotchi is authenticated and persistence failure rolls back state', "user = _miniapp_auth(payload)" in new[new.find('def mini_tamagotchi_api'):new.find('def _mini_world_snapshot')] and "if not critical_save(reason='Mini App Tamagotchi state')" in new)
check('Tamagotchi endpoint and state helpers have runtime regression coverage', all(name in test_runtime for name in ('TamagotchiStateTests', 'TamagotchiApiTests', 'test_failed_persistence_rolls_back_pet_creation', 'test_care_actions_are_bounded_and_rate_limited')))
check('admin recovery logic has regression coverage', all(name in test_runtime for name in ('AdminFunctionRecoveryTests', 'test_creator_can_open_settings_after_admin_functions_are_disabled', 'test_kill_switch_still_blocks_moderation_even_for_creator')))
check('Mini App release version and cache keys are bumped together', 'BOT_VERSION = "0.14"' in config and 'v0.14 · Work Catalog' in text('miniapp/index.html') and '<title>NyaBot · v0.14</title>' in text('miniapp/index.html') and '20261019-v014' in text('miniapp/index.html') and 'NYABOT · v0.14' in text('miniapp/app.js'))
check('Mini App daily/task/game rewards require durable save and rollback', all(token in new for token in ("critical_save(reason='Mini App daily bonus')", "critical_save(reason='Mini App task reward')", "critical_save(reason=f'Mini App game completion: {game_name}')", '_mini_rollback_reward(econ, reward, ')))
check('Mini App game session ownership is checked before session consumption', "game = MINIAPP_GAMES.get(gid)" in new and "if not game or game.get('user_id') != uid:" in new and 'MINIAPP_GAMES.pop(gid, None)' in new)
check('Mini App Neon failure rollback has runtime tests for bonus, task, and game rewards', all(token in test_runtime for token in ('test_daily_bonus_failure_reverts_balance_and_daily_claim_marker', 'test_task_claim_failure_reverts_reward_claim_and_exp', 'test_game_finish_failure_reverts_reward_record_and_counters')))
check('Mini App empire hourly total is checked against business rows', 'class MiniAppEmpireTests' in test_runtime and 'test_empire_hourly_total_equals_rows_without_duplicate_counting' in test_runtime)

check('Legacy business migration is a no-op without legacy IDs', "not isinstance(businesses, dict) or not any(" in new[new.find('def _migrate_legacy_businesses'):new.find('def _business_catalog')] and 'test_no_legacy_assets_means_no_profile_mutation' in test_runtime)
empire = new[new.find('def mini_empire_api'):new.find('# MINI APP: TAMAGOTCHI COMPANION')]
check('Mini App empire serializes profile migration and persists it before responding', "with _get_user_action_lock(uid):" in empire and "critical_save(reason='Mini App legacy business migration', retries=3)" in empire and "return jsonify({'ok': False, 'error': 'save_failed'}), 503" in empire)
tasks_api = new[new.find('def mini_tasks_api'):new.find('@app.route(\'/api/mini/tasks/claim\'')]
check('Mini App task list synchronizes daily/weekly reset with player actions', 'with _get_user_action_lock(uid):' in tasks_api and 'get_daily_tasks(uid, name, username=username)' in tasks_api and 'get_weekly_tasks(uid, name, username=username)' in tasks_api)
check('Legacy business migration preserves ownership, upgrade level, price, and collection timers', 'test_legacy_asset_is_moved_with_level_price_and_income_clock' in test_runtime)
check('Mini App surfaces save rollback errors and frees consumed game UI state', 'saveFailed:' in text('miniapp/app.js') and "r.error==='save_failed'?`❌ ${L().saveFailed}`" in text('miniapp/app.js') and 'cleanupGame();await load()' in text('miniapp/app.js'))

check('Mini App language setting is locked and durably saved', "critical_save(reason='Mini App language setting', retries=2)" in new and 'MiniAppSettingsPersistenceTests' in test_runtime)
_test_classes = [n.name for n in ast.parse(test_runtime).body if isinstance(n, ast.ClassDef)]
check('offline runtime test class names are unique', len(_test_classes) == len(set(_test_classes)))
check('Neon save-failure semantics are covered in both modes', all(name in test_runtime for name in ('test_successful_neon_commit_is_success_even_if_local_backup_fails', 'test_neon_failure_does_not_claim_success_from_local_pending_snapshot', 'test_json_only_mode_reports_local_write_failure')))


# v0.9 atomic bank transactions and shared-state locking.
check('bank deposits and withdrawals update wallet/deposit under canonical locks', 'def _bank_deposit(econ, amount=None, user_id=None):' in new and 'def _bank_withdraw(econ, amount=None, user_id=None):' in new and 'with BALANCE_TX_LOCK:\n            with db_lock:' in new[new.find('def _bank_deposit'):new.find('def debit_coins')])
callback_bank_block = callbacks[callbacks.find("elif action_data == 'bank_dep_100':"):callbacks.find('# ЛОТЕРЕЯ')]
check('all bank callback actions use atomic transaction helpers', callback_bank_block.count('_bank_deposit(') == 2 and callback_bank_block.count('_bank_withdraw(') == 2 and "econ['bank_deposit'] =" not in callback_bank_block and "econ['bank_deposit'] -=" not in callback_bank_block)
moderation_bank_block_1 = text('handlers/moderation.py')[text('handlers/moderation.py').find("if text_lower.startswith(('банк положить', 'депозит')):"):text('handlers/moderation.py').find('# РП-КОМАНДЫ')]
moderation_bank_block_2 = text('handlers/moderation.py')[text('handlers/moderation.py').find('# БАНК: пополнение/снятие прямо текстом'):text('handlers/moderation.py').find('# Удобные русские названия существующих разделов')]
check('text bank commands no longer split wallet and deposit updates', all('_bank_deposit(' in block and '_bank_withdraw(' in block and "econ['bank_deposit'] +=" not in block and "econ['bank_deposit'] -=" not in block for block in (moderation_bank_block_1, moderation_bank_block_2)))
check('bank interest and pet decay update coupled state under shared db lock', 'def update_bank_interest(econ, now=None):' in text('services/economy.py') and 'if periods > 20000:' in text('services/economy.py') and 'def update_pet_stats(pet, now=None):' in text('services/economy.py') and 'not math.isfinite(last)' in text('services/economy.py'))
check('bank atomicity and locked service mutations have regression tests', all(name in test_runtime for name in ('BankTransactionAtomicityTests', 'test_insufficient_wallet_does_not_partially_mutate_deposit', 'test_insufficient_deposit_does_not_partially_mutate_wallet', 'test_interest_accrual_mutates_balance_and_clock_under_database_lock', 'test_pet_needs_decay_is_mutated_under_database_lock')))
check('release version and Mini App cache keys are bumped together', 'BOT_VERSION = "0.14"' in config and 'v0.14 · Work Catalog' in text('miniapp/index.html') and '20261019-v014' in text('miniapp/index.html') and 'NYABOT · v0.14' in text('miniapp/app.js'))
check('admin clamped debit and gift use atomic balance deltas', 'def _debit_balance_up_to(econ, amount, reason=' in new and '_debit_balance_up_to(t_econ, t_amt' in text('handlers/moderation.py') and "_adjust_balance(t_econ, t_amt, reason='Админская выдача коинов')" in text('handlers/moderation.py'))
check('stream, business income, and stake refund avoid stale absolute balance writes', all(token in new for token in ("_adjust_balance(live_econ, max(0, int(donates or 0)), reason='Доход от стрима')", "_adjust_balance(live_econ, bet, reason=f'Возврат ставки: ошибка запуска {game_type}')", "_adjust_balance(econ, amount, reason=f'Прибыль бизнеса: {b_id}')")))
check('clamped admin debit behavior has direct regression tests', all(name in test_runtime for name in ('test_admin_clamped_debit_reads_live_balance_inside_locks', 'test_admin_clamped_debit_does_not_make_balance_negative')))
check('shared economy service coin updates route through the journaled balance adapter', 'balance_adjuster=None' in text('services/economy.py') and 'if _balance_adjuster is not None:' in text('services/economy.py') and 'balance_adjuster=lambda econ, amount, reason=' in new and 'test_add_coins_uses_injected_atomic_balance_adapter' in test_runtime)

check('multi-user callback lock upgrade avoids global/user lock cycle', 'retain_user_id=uid if released_depth else None' in text('core/locks.py') and 'CALLBACK_STATE_LOCK before their user lock' in text('core/locks.py') and 'test_callback_multi_user_upgrade_does_not_drop_global_lock_mid_upgrade' in test_runtime)
check('work shift follows balance-lock-before-db-lock order', 'with BALANCE_TX_LOCK:\n        with db_lock:' in text('handlers/economy.py') and 'test_work_shift_takes_balance_lock_before_db_lock' in test_runtime)

# Catch future deadlocks where a helper acquires BALANCE_TX_LOCK while its caller
# already owns db_lock, unless the balance lock is also held in the scope.
_LOCK_ORDER_CRITICAL_CALLS = {
    '_adjust_balance', '_set_balance', '_debit_balance_up_to', '_bank_deposit',
    '_bank_withdraw', 'debit_coins', 'transfer_coins', 'add_coins',
    'add_account_exp', 'season_rollover', 'check_achievements',
}
_LOCK_ORDER_VIOLATIONS = []
for _path in ROOT.rglob('*.py'):
    if _path.name.startswith('test_') or _path.name.startswith('verify_') or '.git' in _path.parts:
        continue
    try:
        _tree = ast.parse(_path.read_text(encoding='utf-8'), filename=str(_path))
    except SyntaxError:
        continue
    def _scan_lock_order(_node, _with_ancestors=()):
        if isinstance(_node, ast.Call):
            try:
                _fn_name = ast.unparse(_node.func).split('.')[-1]
            except Exception:
                _fn_name = ''
            if _fn_name in _LOCK_ORDER_CRITICAL_CALLS:
                _has_db_lock = any(
                    any('db_lock' in ast.unparse(_item.context_expr) for _item in _scope.items)
                    for _scope in _with_ancestors
                )
                _has_balance_lock = any(
                    any(('BALANCE_TX_LOCK' in ast.unparse(_item.context_expr) or 'TRANSFER_LOCK' in ast.unparse(_item.context_expr)) for _item in _scope.items)
                    for _scope in _with_ancestors
                )
                if _has_db_lock and not _has_balance_lock:
                    _LOCK_ORDER_VIOLATIONS.append(f'{_path}:{_node.lineno}:{_fn_name}')
        _next = _with_ancestors + ((_node,) if isinstance(_node, ast.With) else ())
        for _child in ast.iter_child_nodes(_node):
            _scan_lock_order(_child, _next)
    _scan_lock_order(_tree)
check('no monetary helper acquires BALANCE_TX_LOCK under db_lock', not _LOCK_ORDER_VIOLATIONS)
if _LOCK_ORDER_VIOLATIONS:
    print('  Lock-order violations: ' + ', '.join(_LOCK_ORDER_VIOLATIONS))



# v0.10 audit: store price validation and durable battle-pass claims.
_cb_text = text('handlers/callbacks.py')
check('Battle Pass claim recognizes legacy paid Stars entitlement', "'bp_premium' in paid_items" in _cb_text and "bool(econ.get('bp_premium')" in _cb_text)
check('Battle Pass rewards use durable field-scoped save and rollback', '_durable_profile_transaction(' in _cb_text and "'battle pass reward claim'" in _cb_text and "'pet_inventory'" in _cb_text and 'Не удалось сохранить награды в Neon' in _cb_text)
check('Battle Pass helper prevents duplicate reward grants', 'def _apply_halloween_bp_rewards(econ):' in _cb_text and "claimed_free" in _cb_text and "claimed_prem" in _cb_text)
_store_targets = ['buy_med_', 'buy_buff_', 'buy_house_', 'buy_furn_', 'buy_seed_', 'buy_studio_', 'buy_biz_', 'buy_veh_', 'buy_rod_', 'buy_bow_', 'buy_ring_', 'buy_badge_', 'buy_theme_', 'buy_title_', 'buy_pet_']
_store_branches_ok = True
_cb_tree = ast.parse(_cb_text)
_cb_fn = next(n for n in _cb_tree.body if isinstance(n, ast.FunctionDef) and n.name == 'callback_inline')
_cb_branches = {}
for _node in ast.walk(_cb_fn):
    if isinstance(_node, ast.If):
        _test_src = ast.get_source_segment(_cb_text, _node.test) or ''
        for _target in _store_targets:
            if _target in _test_src:
                _cb_branches[_target] = ast.get_source_segment(_cb_text, _node) or ''
for _target in _store_targets:
    _store_branches_ok = _store_branches_ok and _target in _cb_branches and '<=' in _cb_branches.get(_target, '') and '0' in _cb_branches.get(_target, '')
check('coin shop rejects zero/non-positive price across item categories', _store_branches_ok)
check('release version is v0.14 and Mini App cache keys are refreshed', 'BOT_VERSION = "0.14"' in text('config.py') and 'v0.14 · Work Catalog' in text('miniapp/index.html') and '20261019-v014' in text('miniapp/index.html') and 'NYABOT · v0.14' in text('miniapp/app.js'))
check('Mini App rejects malformed JSON and JSON non-objects before endpoint handlers', 'def _validate_miniapp_json_object():' in new and "request.path.startswith('/api/mini/')" in new and "'error': 'invalid_payload'" in new)
check('chat settings repair corrupt per-chat records and mark default migrations dirty', 'def get_chat_settings(chat_id):' in new and "settings = db.get('settings')" in new and 'if changed:\n            mark_dirty()' in new)
check('legacy profile merge tolerates unhashable lists and malformed optional maps', 'Equality-based de-duplication also handles historical unhashable values.' in new and 'def as_dict(parent, key):' in new and 'def as_int(value, default=0):' in new)
check('profile defaults, collection-shape repair, and equipped-item migrations mark database dirty', 'if field not in u_data:\n            u_data[field] = default\n            defaults_changed = True' in new and 'if defaults_changed:\n        mark_dirty()' in new and "u_data[_num_field] = normalized_value" in new and '_collections_changed' in new)
check('bank interest has bounded exponentiation and malformed timestamp recovery', 'if periods > 20000:' in text('services/economy.py') and 'Decimal("1.0025") ** periods' in text('services/economy.py'))
check('Mini App validation, corrupt-state merge and bank recovery have runtime tests', all(name in test_runtime for name in ('FullCodeAuditHardeningTests', 'test_json_api_preflight_rejects_arrays_and_accepts_objects', 'test_profile_merge_ignores_corrupt_shapes_without_losing_valid_assets', 'test_bank_interest_repairs_corrupt_fields_and_caps_extreme_elapsed_time')))
check('Telegram chat IDs are parsed without unsafe -100 prefix rewriting', 'return int(raw)' in config and 'Prefixing -100 to an arbitrary negative ID' in config and 'test_telegram_chat_ids_are_not_synthetically_rewritten' in test_runtime)
check('Mini App Tamagotchi public serialization guards NaN/Infinity and invalid shape', 'def _mini_finite_float(value, default=0.0):' in new and "_mini_finite_float(pet.get('created_at', now) or now, now)" in new and 'test_tamagotchi_public_state_tolerates_nan_and_infinite_fields' in test_runtime)
check('world and aggregate stats skip corrupt legacy profile shapes', 'def _global_message_stats():' in new and "if not isinstance(stats, dict):" in new and 'test_world_and_global_message_stats_skip_corrupt_legacy_profiles' in test_runtime and 'test_world_snapshot_ignores_corrupt_root_and_legacy_amounts' in test_runtime)
check('Stars entitlement journal repairs malformed processed rows and expiry fields', 'def recover_stars_entitlements_from_journal():' in new and "if not isinstance(processed, list):" in new and 'raw_current_vip_until' in new and 'test_stars_journal_recovery_repairs_corrupt_processed_list_and_fields' in test_runtime)


# v0.12 workforce, XP provenance, and staging adapter checks.
_exp_text = text('services/economy.py')
_admin_text = text('handlers/admin.py')
check('single XP awards are positive and bounded with a rolling provenance ledger', 'MAX_ACCOUNT_EXP_AWARD = 5000' in _exp_text and 'ACCOUNT_EXP_HISTORY_LIMIT = 50' in _exp_text and "'account_exp_history'" in _exp_text and "'level_after'" in _exp_text)
check('passive message XP has a UTC-day ceiling to prevent fast level farming', 'MAX_MESSAGE_ACTIVITY_EXP_PER_UTC_DAY = 1000' in _exp_text and "source_text == 'message_activity'" in _exp_text and "'account_exp_daily_limits'" in _exp_text)
check('direct admin level/XP changes are tagged in the XP provenance ledger', 'record_account_exp_adjustment' in _exp_text and all(source in new for source in ('admin_set_level:', 'admin_add_exp:', 'admin_set_exp:')))
check('XP audit shows supporting activity context and signed adjustments', all(term in _admin_text for term in ('Сообщений:', 'Мини-игр:', 'Достижений:', 'Stars в статистике', "signed = f'{gained:+,}'")))
check('runtime XP wrapper returns actual value for rollback compensation', 'return economy_service.add_account_exp(' in new and "source='activity'" in new[new.find('def add_account_exp(user_id', new.find('def add_account_exp(user_id') + 1):])
_xp_call_sites = []
for _runtime_path in [*ROOT.glob('handlers/*.py'), ROOT / 'newfile.py']:
    if not _runtime_path.exists():
        continue
    try:
        _runtime_tree = ast.parse(_runtime_path.read_text(encoding='utf-8'))
    except SyntaxError:
        continue
    for _call in ast.walk(_runtime_tree):
        if isinstance(_call, ast.Call) and ((isinstance(_call.func, ast.Name) and _call.func.id == 'add_account_exp') or (isinstance(_call.func, ast.Attribute) and _call.func.attr == 'add_account_exp')):
            if _runtime_path.name == 'newfile.py' and isinstance(_call.func, ast.Attribute):
                _xp_call_sites.append(any(k.arg == 'source' for k in _call.keywords))
            else:
                _xp_call_sites.append(any(k.arg == 'source' for k in _call.keywords))
check('every active XP award call site provides a diagnostic source label', bool(_xp_call_sites) and all(_xp_call_sites))
check('owner-only XP audit command is registered', 'def cmd_xp_audit(message):' in _admin_text and 'if not _is_owner_admin(message):' in _admin_text[:_admin_text.find('def cmd_xp_audit')] + _admin_text[_admin_text.find('def cmd_xp_audit'): _admin_text.find('def cmd_global_stats')] and "commands=['xpaudit', 'xp_audit', 'опытаудит']" in _admin_text and "'cmd_xp_audit': 'admin'" in text('handlers/__init__.py'))
check('new job catalog adds nine advanced work roles and validates', all(role in text('data/jobs.py') for role in ('mechanic', 'medic', 'designer', 'analyst', 'engineer', 'lawyer', 'architect', 'astronaut', 'researcher')) and 'def validate_jobs' in text('data/jobs.py'))
check('Mini App task rollback snapshots XP history and season points', "'account_exp', 'season_points', 'account_exp_history'" in new and 'gained_exp or 0' not in new[new.find('def mini_task_claim_api'):new.find('def mini_achievements_api')])
_stage_text = text('scripts/neon_staging_smoke.py')
check('Neon staging smoke uses the real snapshot adapter and preflight guards', 'NYABOT_TEST_DATABASE_URL' in _stage_text and 'NYABOT_STAGING_CONFIRM' in _stage_text and 'database._pg_save(marker)' in _stage_text and 'database._pg_load()' in _stage_text and 'active bot runtime lease exists' in _stage_text)


# v0.14 paginated job catalogue and per-job cards.
_work_ui = text('handlers/economy.py')
_work_callbacks = text('handlers/callbacks.py')
_work_router = text('handlers/moderation.py')
check('job catalogue is paginated and assigns stable one-based job numbers', 'page_size = 6' in _work_ui and 'def _job_catalog_entries()' in _work_ui and "callback_data=f'job_detail:{number}:{user_id}'" in _work_ui and "callback_data=f'job_page:{page + 1}:{user_id}'" in _work_ui)
check('job cards show requirements, success chance and probability-weighted earnings', all(token in _work_ui for token in ('Требуемый опыт', 'Шанс успешной смены', 'Приблизительно в среднем', 'expected_pay = int(round(((min_pay + max_pay) / 2) * chance / 100))')))
check('work button is only shown when EXP requirement and cooldown both allow a shift', 'if available_now:' in _work_ui and "callback_data=f'do_job_{job_id}:{user_id}'" in _work_ui and 'eligible = work_exp >= req_exp' in _work_ui and 'available_now = eligible and not left' in _work_ui)
check('numbered work text aliases and slash command route to the selected detail card', 'def _parse_work_number(text):' in _work_ui and "(?:работа|работы|робота|work|job)\\s+[#№]?\\d+" in _work_router and 'number = _parse_work_number' in _work_ui)
check('work callbacks handle pagination, details, training and refresh after an accepted shift', all(term in _work_callbacks for term in ('job_catalog', 'job_page:', 'job_detail:', 'train_job_catalog:', 'train_job_exp:', '_job_number_for_id(job_id)')))
check('work display regression tests cover pagination, estimates, eligibility and cooldown', 'class WorkCatalogDisplayTests(unittest.TestCase):' in test_runtime and all(term in test_runtime for term in ('test_catalog_is_paginated_and_has_stable_numbered_detail_buttons', 'test_ineligible_job_card_hides_work_button_and_shows_exp_shortfall', 'test_eligible_job_card_shows_estimate_and_work_button', 'test_cooldown_hides_work_button', 'test_numeric_text_parser_accepts_russian_aliases_and_slash_command', 'test_cmd_work_routes_numbered_text_to_detail_and_plain_text_to_catalog')))
check('release version and all Mini App labels/cache keys identify v0.14', 'BOT_VERSION = "0.14"' in text('config.py') and 'v0.14 · Work Catalog' in text('miniapp/index.html') and '20261019-v014' in text('miniapp/index.html') and 'NYABOT · v0.14' in text('miniapp/app.js'))


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
