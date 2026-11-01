"""Offline regression tests for bot handlers, persistence, Mini App auth, and economy.
Run with: python -m unittest test_runtime_regressions.py
These tests mock Telegram and Neon; they do not modify real user data.
"""
from __future__ import annotations

import ast
import copy
import gc
import html
from contextlib import nullcontext
import hashlib
import hmac
import json
import os
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
from urllib.parse import urlencode

import config

# The application pins psycopg2-binary in requirements.txt, but keep the
# offline suite runnable in minimal environments that intentionally omit DB
# drivers. Database tests below force DATABASE_URL empty and never connect.
try:
    import psycopg2  # noqa: F401
except ModuleNotFoundError:
    _psycopg2_stub = types.ModuleType('psycopg2')
    _psycopg2_stub.connect = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        RuntimeError('PostgreSQL driver stub must never connect in offline tests')
    )
    _psycopg2_extras_stub = types.ModuleType('psycopg2.extras')
    _psycopg2_extras_stub.Json = lambda value: value
    _psycopg2_stub.extras = _psycopg2_extras_stub
    sys.modules.setdefault('psycopg2', _psycopg2_stub)
    sys.modules.setdefault('psycopg2.extras', _psycopg2_extras_stub)

from core import database, locks
from handlers import businesses, callbacks, moderation, shop
from handlers import economy as economy_handlers
from services import economy, saving, stars
from data.jobs import JOBS, validate_jobs


class FakeBot:
    def __init__(self):
        self.replies = []
        self.answers = []
        self.invoices = []

    def reply_to(self, message, text, **kwargs):
        self.replies.append((text, kwargs))
        return SimpleNamespace(message_id=len(self.replies))

    def answer_callback_query(self, *args, **kwargs):
        self.answers.append((args, kwargs))
        return True

    def send_invoice(self, **kwargs):
        self.invoices = getattr(self, 'invoices', [])
        self.invoices.append(kwargs)
        return SimpleNamespace(message_id=len(self.invoices))


class BusinessDisplayTests(unittest.TestCase):
    """Exercise the actual catalog/card renderers without importing live DB startup."""
    class Keyboard:
        def __init__(self, *args, **kwargs):
            self.buttons = []
        def add(self, *buttons):
            self.buttons.extend(buttons)

    class Button:
        def __init__(self, text, callback_data):
            self.text = text
            self.callback_data = callback_data

    class DisplayBot:
        def __init__(self):
            self.sent = []
        def send_message(self, *args, **kwargs):
            self.sent.append((args, kwargs))
        def edit_message_text(self, *args, **kwargs):
            self.sent.append((args, kwargs))

    def setUp(self):
        source_path = Path(__file__).with_name('newfile.py')
        tree = ast.parse(source_path.read_text(encoding='utf-8'), filename=str(source_path))
        wanted = {'_render_business_catalog', 'render_business_detail'}
        nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in wanted]
        self.assertEqual({node.name for node in nodes}, wanted)
        self.bot = self.DisplayBot()
        self.econ = {
            'balance': 123456,
            'businesses': {'shop': 1234.0},
            'donor_businesses': {'vipbiz': 1234.0},
            'biz_levels': {'shop': 3, 'vipbiz': 2},
            'biz_purchase_price': {'shop': 1000},
        }
        self.ctx = {
            'get_user_econ': lambda *_args, **_kwargs: self.econ,
            '_migrate_legacy_businesses': lambda _econ: False,
            '_business_catalog': lambda: [
                (1, 'shop', {'name': 'Test Shop', 'price': 1000, 'upgrade_cost': 500}, False),
                (2, 'vipbiz', {'name': 'VIP Business', 'price': 0, 'upgrade_cost': 0}, True),
                (3, 'future', {'name': 'Future', 'price': 9999, 'upgrade_cost': 1000}, False),
            ],
            '_business_user_owns': lambda econ, b_id, donor=False: b_id in (
                econ.get('donor_businesses', {}) if donor else econ.get('businesses', {})
            ),
            '_business_stars_price': lambda _b_id: 20,
            '_business_level': lambda econ, b_id: int(econ.get('biz_levels', {}).get(b_id, 1)),
            '_business_hourly_income': lambda b_id, level: {'shop': 100, 'vipbiz': 200, 'future': 500}[b_id] * level,
            '_business_pending_amount': lambda _econ, _b_id, _now: 42,
            '_business_purchase_price': lambda _econ, _b_id: 1000,
            '_business_by_number': lambda _number: (1, 'shop', {'name': 'Test Shop', 'price': 1000, 'upgrade_cost': 500}, False),
            'BUSINESS_SELL_RATE': 0.8,
            'BUSINESS_TAX_RATE': 0.2,
            'BUSINESSES': {'shop': {'upgrade_cost': 500}},
            'DONOR_BUSINESSES': {'vipbiz': {}},
            'InlineKeyboardMarkup': self.Keyboard,
            'InlineKeyboardButton': self.Button,
            'html': html,
            'time': time,
            'bot': self.bot,
        }
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source_path), 'exec'), self.ctx)

    def test_catalog_shows_owned_business_income_and_combined_after_tax_estimate(self):
        self.ctx['_render_business_catalog'](1, 2, 'Player')
        text = self.bot.sent[-1][0][1]
        self.assertIn('Общий базовый доход: <b>700 🪙/ч</b>', text)
        self.assertIn('После налога 20%: <b>≈560 🪙/ч</b>', text)
        self.assertIn('Test Shop', text)
        self.assertIn('VIP Business', text)
        self.assertIn('Куплено: <b>2/3</b>', text)

    def test_owned_business_card_and_button_show_next_upgrade_price(self):
        self.ctx['render_business_detail'](1, 2, 'Player', 1)
        text = self.bot.sent[-1][0][1]
        keyboard = self.bot.sent[-1][1]['reply_markup']
        self.assertIn('Улучшение до уровня 4: <b>1,500 🪙</b>', text)
        self.assertTrue(any('1,500 🪙' in button.text for button in keyboard.buttons))

    def test_business_catalog_paginates_and_buttons_open_details(self):
        catalog = [
            (i, f'biz{i}', {'name': f'Business {i}', 'short': f'Biz {i}', 'price': i * 100}, False)
            for i in range(1, 11)
        ]
        self.ctx['_business_catalog'] = lambda: catalog
        self.ctx['_business_hourly_income'] = lambda _b_id, _level: 100
        self.ctx['_render_business_catalog'](1, 2, 'Player', page=1)
        text = self.bot.sent[-1][0][1]
        keyboard = self.bot.sent[-1][1]['reply_markup']
        self.assertIn('Страница <b>2/2</b>', text)
        self.assertIn('9. Business 9', text)
        self.assertNotIn('1. Business 1 —', text)
        self.assertTrue(any(button.callback_data == 'biz_catalog_page:0:2' for button in keyboard.buttons))
        self.assertTrue(any(button.callback_data == 'biz_detail_open:9:2' for button in keyboard.buttons))


class BusinessCollectionTests(unittest.TestCase):
    def setUp(self):
        self.bot = FakeBot()
        injected_names = (
            'bot', 'can_process_user_message', 'get_user_econ',
            'collect_business_base_profit', '_business_collection_period_text',
            '_apply_business_payout_modifiers', '_adjust_balance',
            'mark_dirty', 'critical_save', 'time',
        )
        self._missing = object()
        self.old_globals = {name: businesses.__dict__.get(name, self._missing) for name in injected_names}
        self.econ = {
            'balance': 100,
            'businesses': {'smoothie_bar': 1_000.0},
            'biz_last_collect': {'smoothie_bar': 1_000.0},
            'biz_income_carry': {'smoothie_bar': 0.0},
        }
        self.initial_econ = copy.deepcopy(self.econ)
        self.save_result = True

        def collect(econ, now):
            # Simulate the real settlement mutation which must roll back on a failed save.
            econ.setdefault('biz_last_collect', {})['smoothie_bar'] = now
            econ.setdefault('biz_income_carry', {})['smoothie_bar'] = 0.25
            return 100

        businesses._inject({
            'bot': self.bot,
            'can_process_user_message': lambda _message: True,
            'get_user_econ': lambda *_args, **_kwargs: self.econ,
            'collect_business_base_profit': collect,
            '_business_collection_period_text': lambda _econ, _now: '2 ч 15 мин',
            '_apply_business_payout_modifiers': lambda *_args: (
                80, '\n📈 Прибыль до налога: <b>+100 🪙</b>\n📉 Налог бизнеса (20%): <b>-20 🪙</b>'
            ),
            '_adjust_balance': lambda econ, amount, reason=None: econ.__setitem__(
                'balance', int(econ.get('balance', 0) or 0) + int(amount)
            ),
            'mark_dirty': lambda: None,
            'critical_save': lambda *_args, **_kwargs: self.save_result,
            'time': SimpleNamespace(time=lambda: 5_000.0),
        })

    def tearDown(self):
        for name, value in self.old_globals.items():
            if value is self._missing:
                businesses.__dict__.pop(name, None)
            else:
                businesses.__dict__[name] = value

    @staticmethod
    def message():
        user = SimpleNamespace(id=123, first_name='Nya', last_name='', username='nya')
        return SimpleNamespace(text='/collect', from_user=user, chat=SimpleNamespace(id=123))

    def test_collection_receipt_shows_period_tax_net_and_balance_once(self):
        businesses.cmd_collect(self.message())
        text = self.bot.replies[-1][0]
        self.assertIn('Период накопления: 2 ч 15 мин', text)
        self.assertIn('Прибыль до налога', text)
        self.assertIn('Налог бизнеса (20%)', text)
        self.assertIn('Начислено: +80 🪙', text)
        self.assertIn('Баланс: <b>180 🪙</b>', text)
        self.assertNotIn('К получению', text)

    def test_failed_save_rolls_back_balance_and_collection_clocks(self):
        self.save_result = False
        businesses.cmd_collect(self.message())
        self.assertEqual(self.econ, self.initial_econ)
        self.assertIn('Начисление отменено', self.bot.replies[-1][0])


class CustomTitleTests(unittest.TestCase):
    def setUp(self):
        self.bot = FakeBot()
        self.econ = {
            'has_custom_title_cert': True,
            'custom_title': None,
            'custom_title_text': None,
            'active_title': None,
        }
        shop.bot = self.bot
        shop.can_process_user_message = lambda _message: True
        shop.get_user_econ = lambda *_args, **_kwargs: self.econ
        shop.mark_dirty = lambda: None
        shop.critical_save = lambda *_args, **_kwargs: True
        shop.html = html
        shop.TITLES = {}
        shop.LabeledPrice = lambda label, amount: SimpleNamespace(label=label, amount=amount)

    def message(self, text):
        user = SimpleNamespace(id=123, first_name='Nya', last_name='', username='nya')
        return SimpleNamespace(text=text, from_user=user, chat=SimpleNamespace(id=123))

    def test_create_off_on_delete_roundtrip(self):
        shop.cmd_custom_title(self.message('/create_tittle Queen of Cats 😺'))
        self.assertEqual(self.econ['custom_title_text'], 'Queen of Cats 😺')
        self.assertEqual(self.econ['custom_title'], 'Queen of Cats 😺')

        shop.cmd_custom_title(self.message('/create_tittle off'))
        self.assertIsNone(self.econ['custom_title'])
        self.assertEqual(self.econ['custom_title_text'], 'Queen of Cats 😺')

        shop.cmd_custom_title(self.message('/create_tittle on'))
        self.assertEqual(self.econ['custom_title'], 'Queen of Cats 😺')
        self.assertEqual(self.econ['custom_title_text'], 'Queen of Cats 😺')

        shop.cmd_custom_title(self.message('/create_tittle delete'))
        self.assertIsNone(self.econ['custom_title'])
        self.assertIsNone(self.econ['custom_title_text'])

    def test_legacy_title_is_migrated_and_html_is_escaped(self):
        self.econ['custom_title'] = '<Admin>'
        shop.cmd_custom_title(self.message('/create_tittle off'))
        self.assertEqual(self.econ['custom_title_text'], '<Admin>')
        self.assertIsNone(self.econ['custom_title'])

        shop.cmd_custom_title(self.message('/create_tittle <b>Tester</b>'))
        self.assertEqual(self.econ['custom_title'], None)
        self.assertEqual(len(self.bot.invoices), 1)
        self.assertEqual(self.bot.invoices[0]['prices'][0].amount, 4)
        self.assertIn('<b>Tester</b>', self.bot.invoices[0]['description'])

    def test_reserved_word_can_be_used_as_title(self):
        shop.cmd_custom_title(self.message('/create_tittle set off'))
        self.assertEqual(self.econ['custom_title_text'], 'off')
        self.assertEqual(self.econ['custom_title'], 'off')

    def test_each_new_title_requires_a_four_star_invoice(self):
        self.econ['has_custom_title_cert'] = False
        shop.cmd_custom_title(self.message('/create_tittle No entitlement'))
        self.assertIsNone(self.econ['custom_title'])
        self.assertEqual(len(self.bot.invoices), 1)
        self.assertEqual(self.bot.invoices[0]['currency'], 'XTR')
        self.assertEqual(self.bot.invoices[0]['prices'][0].amount, 4)
        self.assertIn('pending_custom_title_orders', self.econ)

    def test_failed_persistence_rolls_back(self):
        shop.critical_save = lambda *_args, **_kwargs: False
        shop.cmd_custom_title(self.message('/create_tittle Unsaved'))
        self.assertIsNone(self.econ['custom_title'])
        self.assertIsNone(self.econ['custom_title_text'])
        self.assertNotIn('Unsaved', str(self.econ.get('pending_custom_title_orders', {})))
        self.assertIn('отменено', self.bot.replies[-1][0])


class CustomTitleStarsValidationTests(unittest.TestCase):
    def setUp(self):
        self.old_config = {
            'db': stars._db,
            'db_lock': stars._db_lock,
            'mark_dirty': stars._mark_dirty,
            'save_now': stars._save_now,
            'get_user': stars._get_user,
            'titles': stars._titles,
            'themes': stars._themes,
            'pets_data': stars._pets_data,
        }
        self.now = time.time()
        self.econ = {'pending_custom_title_orders': {
            'order123': {'text': 'Moon Knight', 'created_at': self.now, 'amount': 4},
        }}
        stars.configure(db={}, get_user=lambda **_kwargs: self.econ)

    def tearDown(self):
        stars.configure(**self.old_config)

    def test_valid_four_star_order_is_accepted(self):
        self.assertEqual(stars.validate_stars_payload('ctitle:123:order123', 4, 123, 'XTR'), (True, ''))

    def test_custom_title_rejects_wrong_buyer_amount_currency_and_expired_order(self):
        self.assertFalse(stars.validate_stars_payload('ctitle:123:order123', 4, 456, 'XTR')[0])
        self.assertFalse(stars.validate_stars_payload('ctitle:123:order123', 3, 123, 'XTR')[0])
        self.assertFalse(stars.validate_stars_payload('ctitle:123:order123', 4, 123, 'USD')[0])
        self.econ['pending_custom_title_orders']['order123']['created_at'] = self.now - 172801
        self.assertFalse(stars.validate_stars_payload('ctitle:123:order123', 4, 123, 'XTR')[0])


class StickerPackTests(unittest.TestCase):
    def setUp(self):
        moderation._WAIFU_STICKER_CACHE.clear()
        moderation._WAIFU_STICKER_CACHE_AT.clear()
        self.clock = [100.0]
        self.calls = []

        class StickerBot:
            def get_sticker_set(inner_self, pack_name):
                self.calls.append(pack_name)
                if len(self.calls) == 1:
                    raise RuntimeError('temporary Telegram error')
                return SimpleNamespace(stickers=[SimpleNamespace(file_id='file-id-123')])

        moderation.bot = StickerBot()
        moderation.time = SimpleNamespace(time=lambda: self.clock[0])

    def test_temporary_pack_error_is_retried_after_negative_cache_ttl(self):
        pack = 'NekoWaifu'
        self.assertEqual(moderation._get_waifu_pack_file_ids(pack), ())
        self.assertEqual(moderation._get_waifu_pack_file_ids(pack), ())
        self.assertEqual(len(self.calls), 1, 'negative cache should avoid repeated API calls during cooldown')

        self.clock[0] += 61
        self.assertEqual(moderation._get_waifu_pack_file_ids(pack), ('file-id-123',))
        self.assertEqual(len(self.calls), 2, 'expired negative cache should allow retry')


class CallbackAckTests(unittest.TestCase):
    def test_noop_callback_is_acknowledged_once(self):
        bot = FakeBot()
        callbacks._inject({
            'bot': bot,
            'db': {'bot_active': True},
            '_bot_output_language': lambda _chat_id, _uid: 'ru',
            '_CALLBACK_LANG_LOCK': threading.Lock(),
            '_CALLBACK_LANG_BY_ID': {},
            '_LOCALE_CONTEXT': SimpleNamespace(user_id=None, chat_id=None),
            'time': time,
            'is_chat_banned': lambda _chat_id: False,
            'user_flood_history': {},
        })
        call = SimpleNamespace(
            id='test-callback-1', data='noop',
            from_user=SimpleNamespace(id=456, username='tester', first_name='Test', last_name=''),
            message=SimpleNamespace(chat=SimpleNamespace(id=456), message_id=1),
        )
        callbacks.callback_inline(call)
        self.assertEqual(len(bot.answers), 1)
        self.assertEqual(bot.answers[0][0][0], 'test-callback-1')


class BattlePassRewardTests(unittest.TestCase):
    def setUp(self):
        source_path = Path(__file__).with_name('handlers') / 'callbacks.py'
        tree = ast.parse(source_path.read_text(encoding='utf-8'), filename=str(source_path))
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_apply_halloween_bp_rewards')
        self.account = {'balance': 1000, 'bp_exp': 2000, 'bp_premium': False, 'paid_stars_items': ['bp_premium']}
        self.activated = []

        def level(exp):
            exp = max(0, int(exp or 0))
            return (min(30, exp // 100 + 1), 0, 100, '')

        def adjust(econ, amount, reason=''):
            econ['balance'] = int(econ.get('balance', 0)) + int(amount)
            econ.setdefault('economy_transactions', []).append({'delta': int(amount), 'reason': reason})

        def activate(econ, pet_id):
            self.activated.append(pet_id)
            econ['pet'] = {'id': pet_id}

        self.ctx = {
            'get_user_bp_level': level,
            'HALLOWEEN_BP_MAX_LEVEL': 30,
            'activate_pet': activate,
            '_adjust_balance': adjust,
        }
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(source_path), 'exec'), self.ctx)

    def test_legacy_paid_stars_entitlement_unlocks_premium_rewards(self):
        receipt = self.ctx['_apply_halloween_bp_rewards'](self.account)
        self.assertTrue(receipt['premium'])
        self.assertEqual(receipt['level'], 21)
        self.assertGreater(receipt['premium_coins'], 0)
        self.assertEqual(self.activated, ['pumpkin_cat'])
        self.assertNotIn('profile_theme', self.account)
        self.assertIn('🎃 Премиум-тыква', self.account['inventory'])

    def test_claiming_twice_does_not_duplicate_coins_or_items(self):
        apply = self.ctx['_apply_halloween_bp_rewards']
        first = apply(self.account)
        after_first = self.account['balance']
        second = apply(self.account)
        self.assertGreater(first['granted'], 0)
        self.assertEqual(second['granted'], 0)
        self.assertEqual(second['total_coins'], 0)
        self.assertEqual(self.account['balance'], after_first)
        self.assertEqual(self.activated, ['pumpkin_cat'])

    def test_shop_purchase_callbacks_reject_non_positive_coin_prices(self):
        source_path = Path(__file__).with_name('handlers') / 'callbacks.py'
        text = source_path.read_text(encoding='utf-8')
        tree = ast.parse(text, filename=str(source_path))
        callback = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'callback_inline')
        targets = {
            'buy_med_', 'buy_buff_', 'buy_house_', 'buy_furn_', 'buy_seed_',
            'buy_studio_', 'buy_biz_', 'buy_veh_', 'buy_rod_', 'buy_bow_',
            'buy_ring_', 'buy_badge_', 'buy_theme_', 'buy_title_', 'buy_pet_',
        }
        branches = {}
        for node in ast.walk(callback):
            if isinstance(node, ast.If):
                test_src = ast.get_source_segment(text, node.test) or ''
                for target in targets:
                    if target in test_src:
                        branches[target] = ast.get_source_segment(text, node) or ''
        for target in sorted(targets):
            with self.subTest(target=target):
                self.assertIn(target, branches)
                self.assertIn('<= 0', branches[target])

    def test_claim_branch_requires_durable_save_and_rolls_back_on_failure(self):
        source_path = Path(__file__).with_name('handlers') / 'callbacks.py'
        text = source_path.read_text(encoding='utf-8')
        tree = ast.parse(text, filename=str(source_path))
        callback = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'callback_inline')
        branch_src = ''
        for node in ast.walk(callback):
            if isinstance(node, ast.If) and 'claim_bp_rewards' in (ast.get_source_segment(text, node.test) or ''):
                branch_src = ast.get_source_segment(text, node) or ''
                break
        self.assertIn('_durable_profile_transaction(', branch_src)
        self.assertIn("'battle pass reward claim'", branch_src)
        self.assertIn('Не удалось сохранить награды в Neon', branch_src)
        self.assertIn("'pet_inventory'", branch_src)


class ConfigurationValidationTests(unittest.TestCase):
    def test_non_finite_environment_floats_fall_back_to_safe_default(self):
        original_problems = list(config._CONFIG_PROBLEMS)
        try:
            config._CONFIG_PROBLEMS.clear()
            for invalid in ('nan', 'NaN', 'inf', '-inf', 'Infinity'):
                with self.subTest(invalid=invalid), mock.patch.dict(
                    os.environ, {'NYABOT_TEST_FLOAT': invalid}
                ):
                    self.assertEqual(
                        config._env_float('NYABOT_TEST_FLOAT', 2.5, minimum=0.1),
                        2.5,
                    )
            with mock.patch.dict(os.environ, {'NYABOT_TEST_FLOAT': '3.75'}):
                self.assertEqual(
                    config._env_float('NYABOT_TEST_FLOAT', 2.5, minimum=0.1),
                    3.75,
                )
            self.assertEqual(len(config._CONFIG_PROBLEMS), 5)
        finally:
            config._CONFIG_PROBLEMS[:] = original_problems


class PersistenceConsistencyTests(unittest.TestCase):
    def test_snapshot_version_is_read_with_the_locked_snapshot(self):
        observed = {}
        lock = threading.RLock()

        def fake_save_snapshot(**kwargs):
            observed.update(kwargs)
            return True

        with mock.patch.object(saving, 'save_snapshot', side_effect=fake_save_snapshot):
            self.assertTrue(saving.save_data(
                {'economy': {}},
                db_lock=lock,
                db_version=1,  # deliberately stale value from caller
                db_version_getter=lambda: 9,
                db_dirty_setter=lambda _value: None,
                db_dirty_clear_if_version=lambda _expected: None,
            ))

        self.assertEqual(observed['snapshot_version'], 9)

    def test_concurrent_mutation_cannot_have_its_dirty_flag_cleared(self):
        lock = threading.RLock()
        version = {'value': 7}
        dirty = {'value': True}

        def compare_and_clear(expected_version):
            # Represent a handler mutation that occurs after the save snapshot
            # has been written but before its compare-and-clear lock is acquired.
            with lock:
                version['value'] += 1
                if version['value'] != expected_version:
                    return False
                dirty['value'] = False
                return True

        with tempfile.TemporaryDirectory() as tmp:
            output_path = str(Path(tmp) / 'state.json')
            with mock.patch.object(database, 'DATA_FILE', output_path), \
                 mock.patch.object(database, 'DATABASE_URL', ''):
                result = database.save_snapshot(
                    snapshot={'economy': {'id_1': {'balance': 10}}},
                    snapshot_version=7,
                    db_version_getter=lambda: version['value'],
                    db_dirty_setter=lambda value: dirty.__setitem__('value', value),
                    db_dirty_clear_if_version=compare_and_clear,
                )

            self.assertTrue(result)
            self.assertTrue(Path(output_path).exists())
            self.assertTrue(dirty['value'])
            self.assertEqual(version['value'], 8)

    def test_dirty_flag_is_cleared_when_saved_version_is_still_current(self):
        lock = threading.RLock()
        version = {'value': 3}
        dirty = {'value': True}

        def compare_and_clear(expected_version):
            with lock:
                if version['value'] != expected_version:
                    return False
                dirty['value'] = False
                return True

        with tempfile.TemporaryDirectory() as tmp:
            output_path = str(Path(tmp) / 'state.json')
            with mock.patch.object(database, 'DATA_FILE', output_path), \
                 mock.patch.object(database, 'DATABASE_URL', ''):
                result = database.save_snapshot(
                    snapshot={'economy': {}},
                    snapshot_version=3,
                    db_version_getter=lambda: version['value'],
                    db_dirty_setter=lambda value: dirty.__setitem__('value', value),
                    db_dirty_clear_if_version=compare_and_clear,
                )
        self.assertTrue(result)
        self.assertFalse(dirty['value'])



class NeonCanonicalSaveTests(unittest.TestCase):
    """A local backup failure must not undo a successful canonical Neon commit."""

    def test_successful_neon_commit_is_success_even_if_local_backup_fails(self):
        cleared = []
        with tempfile.TemporaryDirectory() as tmp:
            output_path = str(Path(tmp) / 'state.json')
            with mock.patch.object(database, 'DATA_FILE', output_path), \
                 mock.patch.object(database, 'DATABASE_URL', 'postgresql://offline-test'), \
                 mock.patch.object(database, '_pg_save', return_value=True), \
                 mock.patch('builtins.open', side_effect=OSError('disk is read-only')):
                result = database.save_snapshot(
                    snapshot={'economy': {'id_7': {'balance': 900}}},
                    snapshot_version=17,
                    db_version_getter=lambda: 17,
                    db_dirty_setter=lambda _value: None,
                    db_dirty_clear_if_version=lambda version: cleared.append(version),
                )

        self.assertTrue(result)
        self.assertEqual(cleared, [17])


    def test_neon_failure_does_not_claim_success_from_local_pending_snapshot(self):
        cleared = []
        with tempfile.TemporaryDirectory() as tmp:
            output_path = str(Path(tmp) / 'state.json')
            with mock.patch.object(database, 'DATA_FILE', output_path), \
                 mock.patch.object(database, 'DATABASE_URL', 'postgresql://offline-test'), \
                 mock.patch.object(database, '_pg_save', return_value=False):
                result = database.save_snapshot(
                    snapshot={'economy': {'id_7': {'balance': 900}}},
                    snapshot_version=18,
                    db_version_getter=lambda: 18,
                    db_dirty_setter=lambda _value: None,
                    db_dirty_clear_if_version=lambda version: cleared.append(version),
                )
            self.assertTrue(Path(output_path).exists())
            snapshot = __import__('json').loads(Path(output_path).read_text(encoding='utf-8'))

        self.assertFalse(result)
        self.assertTrue(snapshot['_meta']['pending_neon_sync'])
        self.assertEqual(cleared, [])

    def test_json_only_mode_reports_local_write_failure(self):
        with mock.patch.object(database, 'DATA_FILE', '/this/path/should/not/exist/state.json'), \
             mock.patch.object(database, 'DATABASE_URL', ''), \
             mock.patch('builtins.open', side_effect=OSError('disk is read-only')):
            result = database.save_snapshot(
                snapshot={'economy': {}},
                snapshot_version=1,
                db_version_getter=lambda: 1,
                db_dirty_setter=lambda _value: None,
                db_dirty_clear_if_version=lambda _version: self.fail('must not clear dirty state'),
            )
        self.assertFalse(result)


class UserActionLockLifecycleTests(unittest.TestCase):
    def test_unused_user_locks_are_not_retained_forever(self):
        user_id = 987_654_321_012_345
        with locks.USER_ACTION_LOCKS_GUARD:
            locks.USER_ACTION_LOCKS.pop(user_id, None)

        first = locks._get_user_action_lock(user_id)
        second = locks._get_user_action_lock(user_id)
        self.assertIs(first, second)
        self.assertIn(user_id, locks.USER_ACTION_LOCKS)

        del first, second
        gc.collect()
        self.assertNotIn(user_id, locks.USER_ACTION_LOCKS)

    def test_active_reference_keeps_same_user_lock_stable(self):
        user_id = 987_654_321_012_346
        first = locks._get_user_action_lock(user_id)
        gc.collect()
        second = locks._get_user_action_lock(user_id)
        self.assertIs(first, second)


class MultiUserCallbackDeadlockTests(unittest.TestCase):
    """Catch lock-upgrade cycles between CALLBACK_STATE_LOCK and user locks."""

    def test_callback_multi_user_upgrade_does_not_drop_global_lock_mid_upgrade(self):
        target_user_lock_acquired = threading.Event()
        allow_target_acquire_to_continue = threading.Event()
        second_callback_acquired_global = threading.Event()
        second_callback_finished = threading.Event()
        first_callback_finished = threading.Event()
        gate_used = threading.Event()

        class TestRLock:
            def __init__(self, on_acquire=None):
                self._lock = threading.RLock()
                self._on_acquire = on_acquire

            def acquire(self, *args, **kwargs):
                acquired = self._lock.acquire(*args, **kwargs)
                if acquired and self._on_acquire:
                    self._on_acquire()
                return acquired

            def release(self):
                return self._lock.release()

            def __enter__(self):
                self.acquire()
                return self

            def __exit__(self, *_args):
                self.release()

        def target_acquired():
            if threading.current_thread().name == 'lock-upgrade-a' and not gate_used.is_set():
                gate_used.set()
                target_user_lock_acquired.set()
                allow_target_acquire_to_continue.wait(timeout=2)

        def callback_global_acquired():
            if threading.current_thread().name == 'lock-upgrade-b':
                second_callback_acquired_global.set()

        user_locks = {
            1: TestRLock(),
            2: TestRLock(on_acquire=target_acquired),
        }
        callback_global_lock = TestRLock(on_acquire=callback_global_acquired)

        def handler(update):
            uid = int(update.from_user.id)
            if uid == 1:
                with locks.serialized_multi_user_action(1, 2):
                    first_callback_finished.set()
            else:
                second_callback_finished.set()

        wrapped = locks.serialize_user_action(handler)
        update_a = SimpleNamespace(
            from_user=SimpleNamespace(id=1), message=SimpleNamespace(), data='test-a'
        )
        update_b = SimpleNamespace(
            from_user=SimpleNamespace(id=2), message=SimpleNamespace(), data='test-b'
        )

        with mock.patch.object(locks, '_get_user_action_lock', side_effect=lambda uid: user_locks[int(uid)]), \
             mock.patch.object(locks, 'CALLBACK_STATE_LOCK', callback_global_lock):
            thread_a = threading.Thread(target=wrapped, args=(update_a,), name='lock-upgrade-a', daemon=True)
            thread_b = threading.Thread(target=wrapped, args=(update_b,), name='lock-upgrade-b', daemon=True)
            thread_a.start()
            self.assertTrue(target_user_lock_acquired.wait(timeout=1), 'first callback did not reach multi-user lock acquisition')
            thread_b.start()

            # If callback A releases CALLBACK_STATE_LOCK while holding both user
            # locks, callback B can grab the global lock and wait on user 2 while
            # callback A waits to reacquire the global lock: a classic deadlock.
            b_grabbed_global_while_a_upgraded = second_callback_acquired_global.wait(timeout=0.15)
            allow_target_acquire_to_continue.set()
            thread_a.join(timeout=1.5)
            thread_b.join(timeout=1.5)

        self.assertFalse(
            b_grabbed_global_while_a_upgraded,
            'another callback acquired CALLBACK_STATE_LOCK during multi-user lock upgrade',
        )
        self.assertFalse(thread_a.is_alive(), 'first callback deadlocked during multi-user action')
        self.assertFalse(thread_b.is_alive(), 'second callback deadlocked waiting for a participant lock')
        self.assertTrue(first_callback_finished.is_set())
        self.assertTrue(second_callback_finished.is_set())

    def test_nested_current_user_lock_depth_is_restored(self):
        user_locks = {1: threading.RLock(), 2: threading.RLock()}
        nested_done = threading.Event()

        def handler(update):
            uid = int(update.from_user.id)
            with locks._get_user_action_lock(uid):
                with locks.serialized_multi_user_action(uid, 2):
                    nested_done.set()

        wrapped = locks.serialize_user_action(handler)
        update = SimpleNamespace(
            from_user=SimpleNamespace(id=1), message=SimpleNamespace(), data='nested'
        )
        with mock.patch.object(locks, '_get_user_action_lock', side_effect=lambda uid: user_locks[int(uid)]):
            worker = threading.Thread(target=wrapped, args=(update,), daemon=True)
            worker.start()
            worker.join(timeout=1)
            self.assertFalse(worker.is_alive(), 'nested lock depth was not restored')
            self.assertTrue(nested_done.is_set())

            acquired = threading.Event()
            def acquire_from_other_thread():
                with user_locks[1]:
                    acquired.set()
            probe = threading.Thread(target=acquire_from_other_thread, daemon=True)
            probe.start()
            probe.join(timeout=1)
            self.assertFalse(probe.is_alive(), 'user lock was leaked after nested action')
            self.assertTrue(acquired.is_set())


class WorkCatalogDisplayTests(unittest.TestCase):
    """Exercise the actual job catalogue/card renderers without Telegram I/O."""

    class Keyboard:
        def __init__(self, *args, **kwargs):
            self.buttons = []
        def add(self, *buttons):
            self.buttons.extend(buttons)
            return self

    class Button:
        def __init__(self, text, callback_data):
            self.text = text
            self.callback_data = callback_data

    class DisplayBot:
        def __init__(self):
            self.sent = []
        def send_message(self, *args, **kwargs):
            self.sent.append((args, kwargs))
        def edit_message_text(self, *args, **kwargs):
            self.sent.append((args, kwargs))

    def setUp(self):
        source_path = Path(__file__).with_name('handlers') / 'economy.py'
        tree = ast.parse(source_path.read_text(encoding='utf-8'), filename=str(source_path))
        wanted = {
            '_job_catalog_entries', '_job_number_for_id', '_parse_work_number',
            'render_job_catalog', 'render_job_detail', 'cmd_work',
        }
        nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in wanted]
        self.assertEqual({n.name for n in nodes}, wanted)
        self.bot = self.DisplayBot()
        self.econ = {'work_exp': 0, 'last_work_time': 0, 'balance': 1000}
        self.cooldown = ''
        self.ctx = {
            'JOBS': JOBS,
            'InlineKeyboardMarkup': self.Keyboard,
            'InlineKeyboardButton': self.Button,
            'get_user_econ': lambda *_a, **_kw: self.econ,
            'cooldown_text': lambda *_a, **_kw: self.cooldown,
            'html': html,
            'bot': self.bot,
            'can_process_user_message': lambda _message: True,
        }
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source_path), 'exec'), self.ctx)

    def test_catalog_is_paginated_and_has_stable_numbered_detail_buttons(self):
        self.ctx['render_job_catalog'](-100, 123, 'Игрок')
        text = self.bot.sent[-1][0][1]
        keyboard = self.bot.sent[-1][1]['reply_markup']
        callbacks = [button.callback_data for button in keyboard.buttons]
        self.assertIn('Страница <b>1/3</b>', text)
        self.assertIn('1. 👨‍🌾 Фермер', text)
        self.assertIn('job_detail:1:123', callbacks)
        self.assertIn('job_page:1:123', callbacks)

        self.ctx['render_job_catalog'](-100, 123, 'Игрок', page=1)
        second_text = self.bot.sent[-1][0][1]
        self.assertIn('Страница <b>2/3</b>', second_text)
        self.assertIn('8. 🔧 Автомеханик', second_text)

    def test_ineligible_job_card_hides_work_button_and_shows_exp_shortfall(self):
        self.econ['work_exp'] = 0
        self.ctx['render_job_detail'](-100, 123, 'Игрок', 3)
        text = self.bot.sent[-1][0][1]
        callbacks = [b.callback_data for b in self.bot.sent[-1][1]['reply_markup'].buttons]
        self.assertIn('Пока недоступна', text)
        self.assertIn('50 EXP', text)
        self.assertIn('🔒', text)
        self.assertTrue(any(x.startswith('train_job_exp:3:') for x in callbacks))
        self.assertFalse(any(x.startswith('do_job_') for x in callbacks))

    def test_eligible_job_card_shows_estimate_and_work_button(self):
        self.econ['work_exp'] = 0
        self.ctx['render_job_detail'](-100, 123, 'Игрок', 1)
        text = self.bot.sent[-1][0][1]
        callbacks = [b.callback_data for b in self.bot.sent[-1][1]['reply_markup'].buttons]
        self.assertIn('≈38 🪙 за смену', text)
        self.assertIn('do_job_fermer:123', callbacks)
        self.assertIn('можете выйти на смену сейчас', text)

    def test_cooldown_hides_work_button(self):
        self.econ['work_exp'] = 0
        self.cooldown = '17 минут'
        self.ctx['render_job_detail'](-100, 123, 'Игрок', 1)
        text = self.bot.sent[-1][0][1]
        callbacks = [b.callback_data for b in self.bot.sent[-1][1]['reply_markup'].buttons]
        self.assertIn('17 минут', text)
        self.assertFalse(any(x.startswith('do_job_') for x in callbacks))

    def test_numeric_text_parser_accepts_russian_aliases_and_slash_command(self):
        parse = self.ctx['_parse_work_number']
        for text, expected in (
            ('работа 1', 1), ('/work 2', 2), ('робота №3', 3),
            ('работа #4', 4), ('/work 16', 16),
        ):
            with self.subTest(text=text):
                self.assertEqual(parse(text), expected)
        self.assertIsNone(parse('работа'))
        self.assertIsNone(parse('работа ноль'))
        self.assertIsNone(parse('работа 0'))
        self.assertIsNone(parse('работа 1 лишнее'))

    def test_job_ids_map_back_to_the_same_display_number(self):
        number = self.ctx['_job_number_for_id']('mechanic')
        self.assertEqual(number, 8)
        self.assertIsNone(self.ctx['_job_number_for_id']('missing-job'))

    def test_cmd_work_routes_numbered_text_to_detail_and_plain_text_to_catalog(self):
        calls = []
        self.ctx['render_job_detail'] = lambda *args, **kwargs: calls.append(('detail', args, kwargs))
        self.ctx['render_job_catalog'] = lambda *args, **kwargs: calls.append(('catalog', args, kwargs))
        message = SimpleNamespace(
            text='робота 1',
            chat=SimpleNamespace(id=-100),
            from_user=SimpleNamespace(id=123, first_name='Игрок', last_name='', username='player'),
        )
        self.ctx['cmd_work'](message)
        self.assertEqual(calls[-1][0], 'detail')
        self.assertEqual(calls[-1][1], (-100, 123, 'Игрок', 1))
        message.text = 'работа'
        self.ctx['cmd_work'](message)
        self.assertEqual(calls[-1][0], 'catalog')
        self.assertEqual(calls[-1][1], (-100, 123, 'Игрок'))


class WorkShiftLockOrderTests(unittest.TestCase):
    """Exercise the real work-shift function with lock-order enforcing locks."""

    def test_work_shift_takes_balance_lock_before_db_lock(self):
        source_path = Path(__file__).with_name('handlers') / 'economy.py'
        tree = ast.parse(source_path.read_text(encoding='utf-8'), filename=str(source_path))
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_perform_job_shift')
        local = threading.local()

        class LockOrderRLock:
            def __init__(self, name):
                self.name = name
                self._lock = threading.RLock()

            def __enter__(self):
                counts = getattr(local, 'counts', {})
                if self.name == 'balance' and counts.get('db', 0) and not counts.get('balance', 0):
                    raise AssertionError('lock inversion: BALANCE_TX_LOCK acquired while db_lock is held')
                self._lock.acquire()
                counts = getattr(local, 'counts', {})
                counts[self.name] = counts.get(self.name, 0) + 1
                local.counts = counts
                return self

            def __exit__(self, *_args):
                counts = getattr(local, 'counts', {})
                counts[self.name] = max(0, counts.get(self.name, 0) - 1)
                local.counts = counts
                self._lock.release()

        balance_lock = LockOrderRLock('balance')
        database_lock = LockOrderRLock('db')
        account = {'balance': 100, 'work_exp': 0, 'last_work_time': 0}
        exp_calls = []
        dirty_calls = []
        achievements = []

        def adjust(econ, amount, reason=''):
            with balance_lock:
                with database_lock:
                    econ['balance'] = int(econ.get('balance', 0) or 0) + int(amount)
                    return econ['balance']

        def add_account_exp(*args, **kwargs):
            counts = getattr(local, 'counts', {})
            self.assertGreater(counts.get('balance', 0), 0)
            self.assertGreater(counts.get('db', 0), 0)
            exp_calls.append((args, kwargs))

        ctx = {
            'JOBS': {'clerk': {'name': 'Работник', 'req_exp': 0, 'chance': 100, 'min_pay': 25, 'max_pay': 25, 'exp_gain': 5}},
            'BALANCE_TX_LOCK': balance_lock,
            'db_lock': database_lock,
            'get_user_econ': lambda *_a, **_kw: account,
            'cooldown_text': lambda *_a, **_kw: None,
            'time': time,
            'random': SimpleNamespace(randint=lambda lo, hi: lo),
            'pet_bonus': lambda *_a: 0.0,
            'get_vehicle_work_bonus': lambda *_a: 0.0,
            'get_title_work_bonus': lambda *_a: 0.0,
            'get_vip_work_bonus': lambda *_a: 0.0,
            '_adjust_balance': adjust,
            'add_account_exp': add_account_exp,
            'mark_dirty': lambda: dirty_calls.append(True),
            'check_achievements': lambda *args, **kwargs: achievements.append((args, kwargs)),
        }
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(source_path), 'exec'), ctx)

        result = ctx['_perform_job_shift'](1001, 'Игрок', 'player', 'clerk', -100)
        self.assertTrue(result[0])
        self.assertEqual(account['balance'], 125)
        self.assertEqual(account['work_exp'], 5)
        self.assertEqual(len(exp_calls), 1)
        self.assertEqual(len(dirty_calls), 1)
        self.assertEqual(len(achievements), 1)


class EconomyLevelPerformanceTests(unittest.TestCase):
    def test_level_boundaries_match_existing_progression_curve(self):
        for level in (1, 2, 3, 4, 10, 100, 1_000, 100_000):
            with self.subTest(level=level):
                threshold = economy.account_exp_for_level(level)
                actual_level, actual_exp, next_exp, bar = economy.get_account_level(threshold)
                self.assertEqual(actual_level, level)
                self.assertEqual(actual_exp, threshold)
                self.assertEqual(next_exp, economy.account_exp_for_level(level + 1))
                self.assertEqual(len(bar), 8)
                if level > 1:
                    self.assertEqual(economy.get_account_level(threshold - 1)[0], level - 1)

    def test_level_100_threshold_is_exact_and_still_supported(self):
        self.assertEqual(economy.account_exp_for_level(100), 98_503)
        self.assertEqual(economy.get_account_level(98_502)[0], 99)
        self.assertEqual(economy.get_account_level(98_503)[0], 100)

    def test_very_large_xp_is_handled_without_linear_level_scan(self):
        exp = 10 ** 24
        level, actual_exp, next_exp, bar = economy.get_account_level(exp)
        self.assertGreater(level, 1_000_000)
        self.assertEqual(actual_exp, exp)
        self.assertLessEqual(economy.account_exp_for_level(level), exp)
        self.assertGreater(next_exp, exp)
        self.assertEqual(len(bar), 8)

    def test_non_finite_xp_values_fall_back_safely(self):
        for value in (float('inf'), float('-inf'), float('nan'), 'not-a-number'):
            with self.subTest(value=value):
                self.assertEqual(economy.get_account_level(value)[0], 1)

class AccountExpAuditTests(unittest.TestCase):
    def setUp(self):
        names = ('_db', '_db_lock', '_mark_dirty', '_balance_adjuster', '_get_user_econ',
                 '_titles', '_vehicles', '_donor_vehicles', '_season_rollover')
        self.previous = {name: getattr(economy, name, None) for name in names}
        self.econ = {'account_exp': 0, 'season_points': 0}
        self.dirty = []
        economy.configure(
            db={}, db_lock=threading.RLock(), mark_dirty=lambda: self.dirty.append(True),
            get_user_econ=lambda *_args, **_kwargs: self.econ, titles={}, vehicles={},
            donor_vehicles={}, season_rollover=None,
        )

    def tearDown(self):
        for name, value in self.previous.items():
            setattr(economy, name, value)

    def test_award_returns_actual_amount_and_records_source_and_level_transition(self):
        gained = economy.add_account_exp(100, 'Player', 150, source='safe_win')
        self.assertEqual(gained, 150)
        self.assertEqual(self.econ['account_exp'], 150)
        self.assertEqual(self.econ['account_exp_history'][-1]['source'], 'safe_win')
        self.assertEqual(self.econ['account_exp_history'][-1]['before'], 0)
        self.assertEqual(self.econ['account_exp_history'][-1]['after'], 150)
        self.assertEqual(self.econ['account_exp_history'][-1]['level_before'], 1)
        self.assertEqual(self.econ['account_exp_history'][-1]['level_after'], 2)
        self.assertTrue(self.dirty)

    def test_invalid_or_unusually_large_single_awards_are_rejected_without_mutation(self):
        for amount in (0, -5, 5001, 'bad', float('inf')):
            with self.subTest(amount=amount):
                self.assertEqual(economy.add_account_exp(100, 'Player', amount), 0)
        self.assertEqual(self.econ['account_exp'], 0)
        self.assertNotIn('account_exp_history', self.econ)
        self.assertEqual(self.econ['season_points'], 0)

    def test_message_activity_xp_has_a_daily_cap(self):
        awarded = sum(economy.add_account_exp(100, 'Player', 2, source='message_activity') for _ in range(600))
        self.assertEqual(awarded, 1000)
        self.assertEqual(self.econ['account_exp'], 1000)
        self.assertEqual(self.econ['account_exp_daily_limits']['message_activity'], 1000)
        self.assertEqual(economy.add_account_exp(100, 'Player', 2, source='message_activity'), 0)

    def test_admin_exp_adjustments_are_written_to_provenance_history(self):
        self.econ['account_exp'] = 100
        delta = economy.record_account_exp_adjustment(self.econ, 100, 98_503, source='admin_set_level:42')
        self.assertEqual(delta, 98_403)
        entry = self.econ['account_exp_history'][-1]
        self.assertEqual(entry['source'], 'admin_set_level:42')
        self.assertEqual(entry['before'], 100)
        self.assertEqual(entry['after'], 98_503)
        self.assertEqual(entry['level_before'], 2)
        self.assertEqual(entry['level_after'], 100)

    def test_xp_history_is_bounded(self):
        for _ in range(65):
            economy.add_account_exp(100, 'Player', 1, source='test')
        self.assertEqual(len(self.econ['account_exp_history']), 50)
        self.assertEqual(self.econ['account_exp'], 65)

    def test_public_jobs_catalog_is_valid_and_contains_advanced_roles(self):
        self.assertEqual(validate_jobs(JOBS), [])
        self.assertGreaterEqual(len(JOBS), 16)
        for role in ('mechanic', 'medic', 'designer', 'analyst', 'engineer', 'lawyer', 'architect', 'astronaut', 'researcher'):
            self.assertIn(role, JOBS)

    def test_runtime_wrapper_returns_service_exp_for_compensation(self):
        tree = ast.parse(Path(__file__).with_name('newfile.py').read_text(encoding='utf-8'))
        matches = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'add_account_exp']
        self.assertGreaterEqual(len(matches), 2)  # legacy implementation plus the active service wrapper
        wrapper = matches[-1]
        returns = [node for node in ast.walk(wrapper) if isinstance(node, ast.Return)]
        self.assertTrue(any(isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute)
                            and node.value.func.attr == 'add_account_exp' for node in returns))


class XPAdminAuditCommandTests(unittest.TestCase):
    def _load_handler(self, owner_allowed, econ, replies, lookups):
        source_path = Path(__file__).with_name('handlers') / 'admin.py'
        tree = ast.parse(source_path.read_text(encoding='utf-8'), filename=str(source_path))
        nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in ('_audit_int', 'cmd_xp_audit')]
        self.assertEqual({node.name for node in nodes}, {'_audit_int', 'cmd_xp_audit'})

        class FakeBot:
            @staticmethod
            def reply_to(message, text, **kwargs):
                replies.append((text, kwargs))

        def get_user_econ(*, user_id, user_tag):
            lookups.append((user_id, user_tag))
            return econ

        ctx = {
            '_is_owner_admin': lambda _message: owner_allowed,
            'resolve_user_from_string': lambda _chat_id, _raw: (456, 'target'),
            'get_user_econ': get_user_econ,
            'get_account_level': economy.get_account_level,
            'account_exp_for_level': economy.account_exp_for_level,
            'bot': FakeBot(), 'html': html, 'time': time,
        }
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source_path), 'exec'), ctx)
        return ctx['cmd_xp_audit']

    def test_owner_audit_shows_level_activity_and_signed_admin_adjustment(self):
        replies, lookups = [], []
        econ = {
            'account_exp': 98_503, 'msg_stats': {'total_count': 12},
            'mini_games_played': 8, 'mini_games_wins': 4,
            'achievements': ['first'], 'work_exp': 250,
            'season_points': 30, 'stars_donated': 0,
            'account_exp_history': [{'time': time.time(), 'source': 'admin_set_level:42',
                                     'gained': 98_403, 'before': 100, 'after': 98_503}],
        }
        handler = self._load_handler(True, econ, replies, lookups)
        message = SimpleNamespace(text='/xpaudit @target', reply_to_message=None, chat=SimpleNamespace(id=-100))
        handler(message)
        self.assertEqual(len(lookups), 1)
        text_out = replies[0][0]
        for expected in ('98,503', 'Сообщений:', 'Мини-игр:', 'Достижений:', 'admin_set_level:42', '+98,403</b> EXP'):
            self.assertIn(expected, text_out)

    def test_non_owner_cannot_use_xp_audit_or_read_target_profile(self):
        replies, lookups = [], []
        handler = self._load_handler(False, {'account_exp': 98_503}, replies, lookups)
        message = SimpleNamespace(text='/xpaudit @target', reply_to_message=None, chat=SimpleNamespace(id=-100))
        handler(message)
        self.assertEqual(replies, [])
        self.assertEqual(lookups, [])


class MiniAppInitDataTests(unittest.TestCase):
    def setUp(self):
        source_path = Path(__file__).with_name('newfile.py')
        tree = ast.parse(source_path.read_text(encoding='utf-8'), filename=str(source_path))
        node = next(
            n for n in tree.body
            if isinstance(n, ast.FunctionDef) and n.name == '_miniapp_user'
        )
        self.now = 1_800_000_000
        self.token = 'test-token-do-not-use-in-production'
        self.ctx = {
            'TOKEN': self.token,
            'parse_qsl': __import__('urllib.parse', fromlist=['parse_qsl']).parse_qsl,
            're': __import__('re'),
            'hmac': hmac,
            'hashlib': hashlib,
            'json': json,
            'time': SimpleNamespace(time=lambda: self.now),
        }
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(source_path), 'exec'), self.ctx)

    def signed_payload(self, *, extra_pairs=None, user=None, auth_date=None):
        values = {
            'auth_date': str(self.now if auth_date is None else auth_date),
            'user': json.dumps(user or {'id': 12345, 'first_name': 'Nya'}, separators=(',', ':')),
        }
        values.update(extra_pairs or {})
        check = '\n'.join(f'{key}={values[key]}' for key in sorted(values))
        secret_key = hmac.new(b'WebAppData', self.token.encode(), hashlib.sha256).digest()
        values['hash'] = hmac.new(secret_key, check.encode(), hashlib.sha256).hexdigest()
        return urlencode(list(values.items()))

    def test_valid_signed_user_is_returned_with_normalized_integer_id(self):
        user = self.ctx['_miniapp_user'](self.signed_payload())
        self.assertEqual(user['id'], 12345)
        self.assertEqual(user['first_name'], 'Nya')

    def test_duplicate_auth_fields_are_rejected(self):
        payload = self.signed_payload()
        self.assertIsNone(self.ctx['_miniapp_user'](payload + '&auth_date=' + str(self.now)))

    def test_invalid_hash_expired_data_and_non_positive_id_are_rejected(self):
        payload = self.signed_payload()[:-1] + ('A' if self.signed_payload()[-1] != 'A' else 'B')
        self.assertIsNone(self.ctx['_miniapp_user'](payload))
        self.assertIsNone(self.ctx['_miniapp_user'](self.signed_payload(auth_date=self.now - 86401)))
        self.assertIsNone(self.ctx['_miniapp_user'](self.signed_payload(user={'id': 0})))


class EconomyJournalTests(unittest.TestCase):
    def setUp(self):
        source_path = Path(__file__).with_name('newfile.py')
        tree = ast.parse(source_path.read_text(encoding='utf-8'), filename=str(source_path))
        names = {'_record_economy_transaction', '_adjust_balance', '_set_balance'}
        nodes = [
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name in names
        ]
        self.assertEqual({node.name for node in nodes}, names)
        self.ctx = {
            'BALANCE_TX_LOCK': threading.RLock(),
            'db_lock': threading.RLock(),
            'time': time,
            'mark_dirty': lambda: None,
        }
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source_path), 'exec'), self.ctx)

    def test_adjust_and_set_balance_both_record_actual_delta(self):
        econ = {'balance': 100}
        self.assertEqual(self.ctx['_adjust_balance'](econ, -25, 'Покупка теста'), 75)
        self.assertEqual(self.ctx['_set_balance'](econ, 140, reason='Админская выдача'), 140)
        self.assertEqual(
            [(row['delta'], row['before'], row['after'], row['reason'])
             for row in econ['economy_transactions']],
            [(-25, 100, 75, 'Покупка теста'), (65, 75, 140, 'Админская выдача')],
        )

    def test_journal_is_bounded_and_zero_delta_is_not_logged(self):
        econ = {'balance': 0}
        for index in range(110):
            self.ctx['_adjust_balance'](econ, 1, f'Тест {index}')
        self.ctx['_adjust_balance'](econ, 0, 'Нулевое изменение')
        journal = econ['economy_transactions']
        self.assertEqual(len(journal), 100)
        self.assertEqual(journal[0]['reason'], 'Тест 10')
        self.assertEqual(journal[-1]['reason'], 'Тест 109')

    def test_unlabelled_changes_get_directional_reason(self):
        econ = {'balance': 20}
        self.ctx['_adjust_balance'](econ, 10)
        self.ctx['_adjust_balance'](econ, -5)
        self.ctx['_set_balance'](econ, 40)
        self.ctx['_set_balance'](econ, 3)
        self.assertEqual(
            [row['reason'] for row in econ['economy_transactions']],
            ['Начисление коинов', 'Списание коинов', 'Начисление коинов', 'Списание коинов'],
        )

    def test_clamped_delta_records_only_the_actual_balance_change(self):
        econ = {'balance': 10}
        self.assertEqual(self.ctx['_adjust_balance'](econ, -30, reason='Clamped debit', minimum=0), 0)
        self.assertEqual(len(econ['economy_transactions']), 1)
        transaction = econ['economy_transactions'][0]
        self.assertEqual((transaction['delta'], transaction['before'], transaction['after'], transaction['reason']),
                         (-10, 10, 0, 'Clamped debit'))


class EconomyServiceAddCoinsTests(unittest.TestCase):
    def test_add_coins_uses_injected_atomic_balance_adapter(self):
        account = {'balance': 40}
        calls = []
        def adapter(econ, delta, reason):
            calls.append((delta, reason))
            econ['balance'] += delta
            return econ['balance']
        with mock.patch.object(economy, '_resolve_econ', return_value=account), mock.patch.object(
            economy, '_balance_adjuster', adapter
        ):
            result = economy.add_coins(123, 'Player', 25)
        self.assertEqual(result, 65)
        self.assertEqual(calls, [(25, 'Начисление коинов')])

    def test_standalone_add_coins_fallback_clamps_and_journals_actual_delta(self):
        account = {'balance': 20}
        dirty = []
        with mock.patch.object(economy, '_resolve_econ', return_value=account), mock.patch.object(
            economy, '_balance_adjuster', None
        ), mock.patch.object(economy, '_db_lock', threading.RLock()), mock.patch.object(
            economy, '_mark_dirty', lambda: dirty.append(True)
        ):
            result = economy.add_coins(123, 'Player', -50)
        self.assertEqual(result, 0)
        self.assertEqual(account['economy_transactions'][0]['delta'], -20)
        self.assertEqual(account['economy_transactions'][0]['reason'], 'Списание коинов')
        self.assertEqual(dirty, [True])


class MoneyHistoryCommandTests(unittest.TestCase):
    """Exercise the actual balance-history command in an isolated handler context."""
    def setUp(self):
        source_path = Path(__file__).with_name('handlers') / 'bank.py'
        tree = ast.parse(source_path.read_text(encoding='utf-8'), filename=str(source_path))
        node = next(
            n for n in tree.body
            if isinstance(n, ast.FunctionDef) and n.name == 'cmd_money_history'
        )
        self.bot = FakeBot()
        self.econ = {'balance': 12_345, 'economy_transactions': []}
        self.ctx = {
            'can_process_user_message': lambda _message: True,
            'get_user_econ': lambda *_args, **_kwargs: self.econ,
            'bot': self.bot,
            'html': html,
            'datetime': datetime,
            'MSK_TZ': timezone.utc,
        }
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(source_path), 'exec'), self.ctx)

    @staticmethod
    def message():
        user = SimpleNamespace(id=123, first_name='Test', last_name='', username='tester')
        return SimpleNamespace(from_user=user, chat=SimpleNamespace(id=123))

    def test_history_shows_latest_ten_and_escapes_reasons(self):
        self.econ['economy_transactions'] = [
            {'time': 1_800_000_000 + idx, 'delta': idx + 1, 'before': idx, 'after': idx + 1,
             'reason': '<admin>' if idx == 10 else f'Операция {idx}'}
            for idx in range(12)
        ]
        self.ctx['cmd_money_history'](self.message())
        text = self.bot.replies[-1][0]
        self.assertIn('12,345 🪙', text)
        self.assertIn('Операция 11', text)
        self.assertIn('Операция 2', text)
        self.assertNotIn('Операция 1</b>', text)
        self.assertIn('&lt;admin&gt;', text)
        self.assertNotIn('<admin>', text)

    def test_empty_history_has_clear_message(self):
        self.ctx['cmd_money_history'](self.message())
        text = self.bot.replies[-1][0]
        self.assertIn('История баланса', text)
        self.assertIn('Записей пока нет', text)



class AdminFunctionRecoveryTests(unittest.TestCase):
    """An admin-function kill switch must not lock the group creator out."""
    def setUp(self):
        source_path = Path(__file__).with_name('newfile.py')
        tree = ast.parse(source_path.read_text(encoding='utf-8'), filename=str(source_path))
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'can_admin_action')
        self.settings = {'admin_functions_enabled': False}
        self.levels = {1: 4, 2: 2, 3: 1}
        self.ctx = {
            'get_chat_settings': lambda _chat_id: self.settings,
            'is_chat_owner': lambda _chat_id, user_id: int(user_id) == 1,
            'get_admin_level': lambda _chat_id, user_id: self.levels.get(int(user_id), 0),
            'get_admin_permission_level': lambda _chat_id, action: 2 if action == 'settings' else 3,
        }
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(source_path), 'exec'), self.ctx)

    def test_creator_can_open_settings_after_admin_functions_are_disabled(self):
        self.assertTrue(self.ctx['can_admin_action'](-100, 1, 'settings'))

    def test_kill_switch_still_blocks_moderation_even_for_creator(self):
        self.assertFalse(self.ctx['can_admin_action'](-100, 1, 'ban'))
        self.assertFalse(self.ctx['can_admin_action'](-100, 2, 'settings'))

    def test_enabled_mode_still_uses_configured_permission_levels(self):
        self.settings['admin_functions_enabled'] = True
        self.assertTrue(self.ctx['can_admin_action'](-100, 2, 'settings'))
        self.assertFalse(self.ctx['can_admin_action'](-100, 3, 'settings'))

    def test_admin_function_text_command_requires_chat_creator(self):
        moderation = Path(__file__).with_name('handlers').joinpath('moderation.py').read_text(encoding='utf-8')
        command_block = moderation[moderation.find("if action in ('функции','функция','админфункции'):"):moderation.find("if action in ('функции','функция','админфункции'):", moderation.find("if action in ('функции','функция','админфункции'):") + 1)]
        self.assertIn('is_chat_owner(message.chat.id, message.from_user.id)', command_block)

    def test_settings_callbacks_share_the_same_permission_gate(self):
        callbacks = Path(__file__).with_name('handlers').joinpath('callbacks.py').read_text(encoding='utf-8')
        warn_limit_block = callbacks[callbacks.find("elif action_data == 'set_warn_limit':"):callbacks.find('# GIF ДЛЯ ПРОФИЛЯ', callbacks.find("elif action_data == 'set_warn_limit':"))]
        self.assertIn("can_admin_action(chat_id, user_id, 'settings')", warn_limit_block)
        self.assertNotIn('if not is_admin(chat_id,user_id)', warn_limit_block)
        settings_block = callbacks[callbacks.find('# НАСТРОЙКИ'):callbacks.find("elif action_data.startswith('set_user_lang_')")]
        self.assertIn("can_admin_action(chat_id, user_id, 'settings')", settings_block)
        self.assertNotIn('if not is_admin(chat_id, user_id): return', settings_block)


class TamagotchiStateTests(unittest.TestCase):
    """Test the actual pure state helpers used by the Mini App endpoint."""
    def setUp(self):
        source_path = Path(__file__).with_name('newfile.py')
        tree = ast.parse(source_path.read_text(encoding='utf-8'), filename=str(source_path))
        names = {
            '_MINI_TAMAGOTCHI_STAT_DECAY_PER_HOUR', '_MINI_TAMAGOTCHI_COOLDOWNS',
            '_mini_finite_float', '_mini_tamagotchi_default', '_mini_tamagotchi_tick',
            '_mini_tamagotchi_action', '_mini_tamagotchi_public',
        }
        nodes = [
            node for node in tree.body
            if (isinstance(node, ast.FunctionDef) and node.name in names)
            or (isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in names for t in node.targets))
        ]
        self.ctx = {'time': time, 're': __import__('re'), 'math': __import__('math')}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source_path), 'exec'), self.ctx)

    def test_pet_needs_decay_after_time_away(self):
        pet = self.ctx['_mini_tamagotchi_default'](1000)
        self.assertTrue(self.ctx['_mini_tamagotchi_tick'](pet, 1000 + 7200))
        self.assertEqual(pet['hunger'], 64.0)
        self.assertEqual(pet['happiness'], 74.0)
        self.assertEqual(pet['energy'], 76.0)
        self.assertEqual(pet['cleanliness'], 84.0)

    def test_short_refresh_does_not_mutate_persistent_state(self):
        pet = self.ctx['_mini_tamagotchi_default'](1000)
        before = copy.deepcopy(pet)
        self.assertFalse(self.ctx['_mini_tamagotchi_tick'](pet, 1059))
        self.assertEqual(pet, before)

    def test_care_actions_are_bounded_and_rate_limited(self):
        pet = self.ctx['_mini_tamagotchi_default'](1000)
        pet['hunger'] = 97
        self.assertTrue(self.ctx['_mini_tamagotchi_action'](pet, 'feed', 1000)['ok'])
        self.assertEqual(pet['hunger'], 100)
        self.assertEqual(self.ctx['_mini_tamagotchi_action'](pet, 'feed', 1001)['error'], 'action_cooldown')
        self.assertEqual(pet['care_count'], 1)

    def test_invalid_action_and_blank_name_are_rejected(self):
        pet = self.ctx['_mini_tamagotchi_default'](1000)
        self.assertEqual(self.ctx['_mini_tamagotchi_action'](pet, 'give_coins', 1000)['error'], 'invalid_action')
        self.assertEqual(self.ctx['_mini_tamagotchi_action'](pet, 'rename', 1000, name=' \n ')['error'], 'invalid_name')

    def test_public_state_handles_corrupt_cooldown_values(self):
        pet = self.ctx['_mini_tamagotchi_default'](1000)
        pet['last_actions'] = {'feed': 'bad value'}
        pet['care_count'] = 'not a number'
        view = self.ctx['_mini_tamagotchi_public'](pet, 1000)
        self.assertEqual(view['name'], 'Ня')
        self.assertEqual(view['care_count'], 0)
        self.assertEqual(view['next_actions']['feed'], 0)
        self.assertEqual(view['mood'], 'happy')



class TamagotchiApiTests(unittest.TestCase):
    """Exercise the authenticated endpoint against fake state and persistence."""
    def setUp(self):
        source_path = Path(__file__).with_name('newfile.py')
        tree = ast.parse(source_path.read_text(encoding='utf-8'), filename=str(source_path))
        names = {
            '_MINI_TAMAGOTCHI_STAT_DECAY_PER_HOUR', '_MINI_TAMAGOTCHI_COOLDOWNS',
            '_mini_finite_float', '_mini_tamagotchi_default', '_mini_tamagotchi_tick',
            '_mini_tamagotchi_action', '_mini_tamagotchi_public', 'mini_tamagotchi_api',
        }
        nodes = [
            node for node in tree.body
            if (isinstance(node, ast.FunctionDef) and node.name in names)
            or (isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in names for t in node.targets))
        ]
        self.payload = {}
        self.econ = {'user_id': 12345, 'balance': 500}
        self.save_result = True
        self.save_calls = []
        self.dirty_calls = []
        from contextlib import nullcontext
        class FakeApp:
            @staticmethod
            def route(*_args, **_kwargs):
                return lambda func: func
        def critical_save(**kwargs):
            self.save_calls.append(kwargs)
            return self.save_result
        self.ctx = {
            'app': FakeApp(),
            'request': SimpleNamespace(get_json=lambda silent=True: self.payload),
            'jsonify': lambda value: value,
            '_miniapp_auth': lambda payload: {'id': 12345, 'first_name': 'Nya'} if payload.get('initData') == 'signed' else None,
            '_get_user_action_lock': lambda _uid: nullcontext(),
            'MINIAPP_LOCK': threading.RLock(),
            'get_user_econ': lambda *_args, **_kwargs: self.econ,
            'critical_save': critical_save,
            'mark_dirty': lambda: self.dirty_calls.append(True),
            'copy': copy,
            'time': time,
            're': __import__('re'),
            'math': __import__('math'),
        }
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source_path), 'exec'), self.ctx)

    def call(self, payload):
        self.payload = {'initData': 'signed', **payload}
        result = self.ctx['mini_tamagotchi_api']()
        return result if isinstance(result, tuple) else (result, 200)

    def test_initial_state_is_saved_to_the_player_record(self):
        body, status = self.call({})
        self.assertEqual(status, 200)
        self.assertTrue(body['ok'])
        self.assertEqual(body['pet']['name'], 'Ня')
        self.assertIn('mini_tamagotchi', self.econ)
        self.assertEqual(len(self.save_calls), 1)
        self.assertEqual(self.econ['balance'], 500)

    def test_care_action_persists_without_changing_economy_balance(self):
        body, status = self.call({'action': 'feed'})
        self.assertEqual(status, 200)
        self.assertTrue(body['ok'])
        self.assertGreaterEqual(body['pet']['hunger'], 78)
        self.assertEqual(self.econ['balance'], 500)
        self.assertEqual(self.econ['mini_tamagotchi']['care_count'], 1)

    def test_failed_persistence_rolls_back_pet_creation(self):
        self.save_result = False
        body, status = self.call({})
        self.assertEqual(status, 503)
        self.assertEqual(body['error'], 'save_failed')
        self.assertNotIn('mini_tamagotchi', self.econ)
        self.assertEqual(self.econ['balance'], 500)

    def test_unsigned_request_is_rejected_before_mutation(self):
        self.payload = {'initData': 'invalid'}
        body, status = self.ctx['mini_tamagotchi_api']()
        self.assertEqual(status, 403)
        self.assertNotIn('mini_tamagotchi', self.econ)


class MiniAppCriticalSaveTests(unittest.TestCase):
    """Exercise Mini App money endpoints with a forced Neon save failure."""

    def setUp(self):
        source_path = Path(__file__).with_name('newfile.py')
        tree = ast.parse(source_path.read_text(encoding='utf-8'), filename=str(source_path))
        names = {
            '_mini_add_notification', '_mini_snapshot_fields', '_mini_restore_fields',
            '_mini_rollback_reward', 'mini_bonus_api', 'mini_task_claim_api',
            'mini_game_finish_api',
        }
        nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
        self.assertEqual({node.name for node in nodes}, names)

        from contextlib import nullcontext
        from datetime import datetime, timezone

        class FakeApp:
            @staticmethod
            def route(*_args, **_kwargs):
                return lambda func: func

        self.payload = {'initData': 'signed'}
        self.econ = {'user_id': 12345, 'balance': 1000}
        self.save_result = False
        self.save_calls = []
        self.dirty_calls = []
        self.econ['daily_progress'] = {'messages': 1}
        self.econ['weekly_progress'] = {'messages': 1}
        self.game_started = time.time() - 10
        self.games = {
            'game-owned-by-me': {
                'user_id': 12345, 'game': 'mines', 'difficulty': 'easy', 'started': self.game_started,
            },
            'game-owned-by-other': {
                'user_id': 54321, 'game': 'snake', 'difficulty': 'easy', 'started': self.game_started,
            },
        }
        def save_data(**kwargs):
            self.save_calls.append(kwargs)
            return False
        def adjust_balance(econ, amount, reason='Изменение баланса'):
            delta = int(amount or 0)
            before = int(econ.get('balance', 0) or 0)
            after = before + delta
            econ['balance'] = after
            journal = econ.setdefault('economy_transactions', [])
            journal.append({'delta': delta, 'before': before, 'after': after, 'reason': reason})
            return after
        def add_account_exp(uid, name, amount, username=None, *, source='activity'):
            self.econ['account_exp'] = int(self.econ.get('account_exp', 0) or 0) + int(amount)
            self.econ['season_points'] = int(self.econ.get('season_points', 0) or 0) + max(1, int(amount) // 5)
            history = self.econ.setdefault('account_exp_history', [])
            history.append({'source': source, 'gained': int(amount)})
            return int(amount)

        self.ctx = {
            'app': FakeApp(),
            'request': SimpleNamespace(get_json=lambda silent=True: self.payload),
            'jsonify': lambda value: value,
            '_miniapp_auth': lambda payload: (
                {'id': 12345, 'first_name': 'Nya', 'username': 'nya'}
                if payload.get('initData') == 'signed' else None
            ),
            '_get_user_action_lock': lambda _uid: nullcontext(),
            'MINIAPP_LOCK': threading.RLock(),
            'MINIAPP_GAMES': self.games,
            'MINIAPP_GAME_TTL': 300,
            'MINIAPP_DAILY_REWARD_CAP': 500,
            'get_user_econ': lambda *_args, **_kwargs: self.econ,
            'get_daily_tasks': lambda *_args, **_kwargs: (
                [('messages', 'Напиши сообщение', 1, 100)], self.econ
            ),
            'get_weekly_tasks': lambda *_args, **_kwargs: (
                [('messages', 'Напиши сообщение', 1, 250)], self.econ
            ),
            'add_account_exp': add_account_exp,
            '_adjust_balance': adjust_balance,
            'critical_save': lambda **kwargs: (self.save_calls.append(kwargs) or self.save_result),
            'save_data': save_data,
            'mark_dirty': lambda: self.dirty_calls.append(True),
            'db_lock': threading.RLock(),
            'copy': copy,
            'time': time,
            're': __import__('re'),
            'now_msk': lambda: datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc),
            'MINIAPP_LOCK': threading.RLock(),
        }
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source_path), 'exec'), self.ctx)

    def call(self, name, payload):
        self.payload = {'initData': 'signed', **payload}
        result = self.ctx[name]()
        return result if isinstance(result, tuple) else (result, 200)

    def test_daily_bonus_failure_reverts_balance_and_daily_claim_marker(self):
        body, status = self.call('mini_bonus_api', {})
        self.assertEqual(status, 503)
        self.assertEqual(body['error'], 'save_failed')
        self.assertEqual(self.econ['balance'], 1000)
        self.assertNotIn('mini_daily_claimed', self.econ)
        self.assertNotIn('mini_transactions', self.econ)
        # The ledger records both the attempted grant and compensating reversal.
        self.assertEqual([x['delta'] for x in self.econ['economy_transactions']], [600, -600])
        self.assertTrue(self.save_calls)

    def test_task_claim_failure_reverts_reward_claim_and_exp(self):
        self.econ.update({'balance': 100, 'account_exp': 90, 'season_points': 12})
        body, status = self.call('mini_task_claim_api', {'task_id': 'messages', 'kind': 'daily'})
        self.assertEqual(status, 503)
        self.assertEqual(body['error'], 'save_failed')
        self.assertEqual(self.econ['balance'], 100)
        self.assertEqual(self.econ['account_exp'], 90)
        self.assertEqual(self.econ['season_points'], 12)
        self.assertNotIn('account_exp_history', self.econ)
        self.assertNotIn('daily_claimed', self.econ)
        self.assertNotIn('mini_transactions', self.econ)
        self.assertEqual([x['delta'] for x in self.econ['economy_transactions']], [100, -100])

    def test_game_finish_failure_reverts_reward_record_and_counters(self):
        self.econ.update({'balance': 50, 'mini_games_played': 2, 'mini_reported_records': {'mines': 7}})
        body, status = self.call('mini_game_finish_api', {'game_id': 'game-owned-by-me', 'score': 999})
        self.assertEqual(status, 503)
        self.assertEqual(body['error'], 'save_failed')
        self.assertEqual(self.econ['balance'], 50)
        self.assertEqual(self.econ['mini_games_played'], 2)
        self.assertEqual(self.econ['mini_reported_records'], {'mines': 7})
        self.assertNotIn('mini_game_reward_date', self.econ)
        self.assertNotIn('mini_transactions', self.econ)
        self.assertEqual([x['delta'] for x in self.econ['economy_transactions']], [25, -25])

    def test_wrong_player_cannot_consume_another_players_game_session(self):
        self.payload = {'initData': 'signed', 'game_id': 'game-owned-by-other', 'score': 1}
        body, status = self.call('mini_game_finish_api', {'game_id': 'game-owned-by-other', 'score': 1})
        self.assertEqual(status, 400)
        self.assertEqual(body['error'], 'invalid_game')
        self.assertIn('game-owned-by-other', self.games)
        self.assertEqual(self.econ['balance'], 1000)



class MiniAppSettingsPersistenceTests(unittest.TestCase):
    """Changing the Mini App language is serialized and durable before success."""

    def setUp(self):
        source_path = Path(__file__).with_name('newfile.py')
        tree = ast.parse(source_path.read_text(encoding='utf-8'), filename=str(source_path))
        node = next(
            n for n in tree.body
            if isinstance(n, ast.FunctionDef) and n.name == 'mini_settings_api'
        )

        class FakeApp:
            @staticmethod
            def route(*_args, **_kwargs):
                return lambda func: func

        self.payload = {'initData': 'signed', 'language': 'uk'}
        self.econ = {'user_id': 12345, 'language': 'ru'}
        self.save_result = True
        self.save_calls = []
        self.dirty_calls = []
        self.lock_active = False

        from contextlib import contextmanager
        @contextmanager
        def user_lock(_uid):
            self.assertFalse(self.lock_active)
            self.lock_active = True
            try:
                yield
            finally:
                self.lock_active = False

        def critical_save(**kwargs):
            self.assertTrue(self.lock_active, 'user action must remain serialized through persistence')
            self.save_calls.append(kwargs)
            return self.save_result

        self.ctx = {
            'app': FakeApp(),
            'request': SimpleNamespace(get_json=lambda silent=True: self.payload),
            'jsonify': lambda value: value,
            '_miniapp_auth': lambda payload: (
                {'id': 12345, 'first_name': 'Nya', 'username': 'nya'}
                if payload.get('initData') == 'signed' else None
            ),
            '_get_user_action_lock': user_lock,
            'db_lock': threading.RLock(),
            'get_user_econ': lambda *_args, **_kwargs: self.econ,
            'mark_dirty': lambda: self.dirty_calls.append(True),
            'critical_save': critical_save,
            'json': json,
        }
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(source_path), 'exec'), self.ctx)

    def call(self):
        result = self.ctx['mini_settings_api']()
        return result if isinstance(result, tuple) else (result, 200)

    def test_language_is_saved_before_success_is_returned(self):
        body, status = self.call()
        self.assertEqual(status, 200)
        self.assertEqual(body, {'ok': True, 'language': 'uk'})
        self.assertEqual(self.econ['language'], 'uk')
        self.assertEqual(len(self.save_calls), 1)
        self.assertEqual(self.save_calls[0]['reason'], 'Mini App language setting')
        self.assertFalse(self.lock_active)

    def test_failed_neon_save_rolls_back_language_and_returns_error(self):
        self.save_result = False
        body, status = self.call()
        self.assertEqual(status, 503)
        self.assertEqual(body['error'], 'save_failed')
        self.assertEqual(self.econ['language'], 'ru')
        self.assertEqual(len(self.dirty_calls), 2)
        self.assertFalse(self.lock_active)

class MiniAppEmpireTests(unittest.TestCase):
    """Confirm the API total is exactly the sum of visible owned-business rows."""

    def test_empire_hourly_total_equals_rows_without_duplicate_counting(self):
        source_path = Path(__file__).with_name('newfile.py')
        tree = ast.parse(source_path.read_text(encoding='utf-8'), filename=str(source_path))
        node = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'mini_empire_api')
        class FakeApp:
            @staticmethod
            def route(*_args, **_kwargs):
                return lambda func: func
        econ = {
            'businesses': {'shop': 1000},
            'donor_businesses': {'vipbiz': 1},
            'biz_levels': {'shop': 2, 'vipbiz': 3},
        }
        ctx = {
            'app': FakeApp(),
            'request': SimpleNamespace(get_json=lambda silent=True: {'initData': 'signed'}),
            'jsonify': lambda value: value,
            '_miniapp_auth': lambda _payload: {'id': 12345, 'first_name': 'Nya'},
            'get_user_econ': lambda *_args, **_kwargs: econ,
            '_get_user_action_lock': lambda _uid: nullcontext(),
            'LEGACY_BUSINESS_REPLACEMENTS': {},
            'copy': copy,
            'critical_save': lambda **_kwargs: True,
            'mark_dirty': lambda: None,
            'save_data': lambda **_kwargs: True,
            '_migrate_legacy_businesses': lambda _econ: False,
            '_business_catalog': lambda: [
                (1, 'shop', {'name': 'Shop', 'short': 'Shop', 'world': 'earth', 'price': 1000}, False),
                (2, 'vipbiz', {'name': 'VIP', 'short': 'VIP', 'world': 'moon', 'price': 0}, True),
            ],
            '_business_level': lambda record, b_id: record.get('biz_levels', {}).get(b_id, 1),
            '_business_hourly_income': lambda b_id, level: {'shop': 100, 'vipbiz': 200}[b_id] * level,
            '_business_purchase_price': lambda _record, _b_id: 1000,
            'BUSINESS_TAX_RATE': 0.2,
            'BUSINESS_SELL_RATE': 0.8,
            'BOT_VERSION': '0.7',
        }
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(source_path), 'exec'), ctx)
        response = ctx['mini_empire_api']()
        self.assertEqual(response['gross_hourly'], sum(row['hourly_gross'] for row in response['rows']))
        self.assertEqual(response['gross_hourly'], 800)
        self.assertEqual(response['net_hourly_estimate'], 640)
        self.assertEqual(response['business_count'], 2)


class LegacyBusinessMigrationTests(unittest.TestCase):
    """Verify legacy conversion is lazy, idempotent, and preserves profile assets."""

    @staticmethod
    def load_migration(replacements, legacy_info, econ, adjust_balance=None):
        source_path = Path(__file__).with_name('newfile.py')
        tree = ast.parse(source_path.read_text(encoding='utf-8'), filename=str(source_path))
        node = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == '_migrate_legacy_businesses')
        dirty_calls = []
        ctx = {
            'LEGACY_BUSINESS_REPLACEMENTS': replacements,
            'LEGACY_BUSINESS_INFO': legacy_info,
            'BUSINESS_SELL_RATE': 0.8,
            'time': time,
            '_adjust_balance': adjust_balance or (lambda *_args, **_kwargs: None),
            'mark_dirty': lambda: dirty_calls.append(True),
        }
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(source_path), 'exec'), ctx)
        return ctx['_migrate_legacy_businesses'], dirty_calls

    def test_no_legacy_assets_means_no_profile_mutation(self):
        econ = {'businesses': {'smoothie_bar': 123.0}, 'balance': 500, 'biz_levels': {'smoothie_bar': 2}}
        before = copy.deepcopy(econ)
        migrate, dirty_calls = self.load_migration({'bottles': 'smoothie_bar'}, {'bottles': {'price': 200}}, econ)
        self.assertFalse(migrate(econ))
        self.assertEqual(econ, before)
        self.assertEqual(dirty_calls, [])

    def test_legacy_asset_is_moved_with_level_price_and_income_clock(self):
        econ = {
            'businesses': {'bottles': 123.0},
            'balance': 500,
            'biz_levels': {'bottles': 2},
            'biz_purchase_price': {'bottles': 250},
            'biz_last_collect': {'bottles': 111.0},
            'biz_income_carry': {'bottles': 0.25},
        }
        migrate, dirty_calls = self.load_migration({'bottles': 'smoothie_bar'}, {'bottles': {'price': 200}}, econ)
        self.assertTrue(migrate(econ))
        self.assertNotIn('bottles', econ['businesses'])
        self.assertEqual(econ['businesses']['smoothie_bar'], 123.0)
        self.assertEqual(econ['biz_levels']['smoothie_bar'], 2)
        self.assertEqual(econ['biz_purchase_price']['smoothie_bar'], 250)
        self.assertEqual(econ['biz_last_collect']['smoothie_bar'], 111.0)
        self.assertEqual(econ['biz_income_carry']['smoothie_bar'], 0.25)
        self.assertEqual(econ['legacy_assets'][0]['from'], 'bottles')
        self.assertTrue(dirty_calls)


class BankTransactionAtomicityTests(unittest.TestCase):
    """Test the actual bank helpers with tracked locks and isolated state."""

    class TrackingLock:
        def __init__(self, name, held):
            self.name = name
            self.held = held
            self.depth = 0
        def __enter__(self):
            self.depth += 1
            self.held[self.name] = self.held.get(self.name, 0) + 1
            return self
        def __exit__(self, exc_type, exc, tb):
            self.held[self.name] -= 1
            if self.held[self.name] <= 0:
                self.held.pop(self.name, None)
            self.depth -= 1
            return False

    def setUp(self):
        source_path = Path(__file__).with_name('newfile.py')
        tree = ast.parse(source_path.read_text(encoding='utf-8'), filename=str(source_path))
        wanted = {'_bank_deposit', '_bank_withdraw', '_debit_balance_up_to'}
        nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in wanted]
        self.assertEqual({node.name for node in nodes}, wanted)
        self.held = {}
        self.dirty = []
        self.wallet_lock = self.TrackingLock('user', self.held)
        self.balance_lock = self.TrackingLock('balance', self.held)
        self.db_lock = self.TrackingLock('db', self.held)
        def adjust(econ, amount, reason=''):
            self.assertGreater(self.held.get('balance', 0), 0)
            self.assertGreater(self.held.get('db', 0), 0)
            before = int(econ.get('balance', 0) or 0)
            econ['balance'] = before + int(amount)
            econ.setdefault('economy_transactions', []).append({
                'delta': int(amount), 'before': before, 'after': econ['balance'], 'reason': reason,
            })
            self.dirty.append(True)
            return econ['balance']
        self.ctx = {
            'BALANCE_TX_LOCK': self.balance_lock,
            'db_lock': self.db_lock,
            '_get_user_action_lock': lambda _uid: self.wallet_lock,
            '_adjust_balance': adjust,
            'mark_dirty': lambda: self.dirty.append(True),
            'time': time,
            'contextlib': __import__('contextlib'),
        }
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source_path), 'exec'), self.ctx)

    def test_deposit_moves_wallet_and_bank_under_all_locks(self):
        econ = {'balance': 100, 'bank_deposit': 10}
        result = self.ctx['_bank_deposit'](econ, 40, user_id=123)
        self.assertEqual(result, (True, 40, 60, 50))
        self.assertEqual((econ['balance'], econ['bank_deposit']), (60, 50))
        self.assertEqual(econ['economy_transactions'][-1]['reason'], 'Перевод наличных в банковский вклад')
        self.assertEqual(self.held, {})

    def test_deposit_all_uses_current_wallet_balance(self):
        econ = {'balance': 81, 'bank_deposit': 9}
        result = self.ctx['_bank_deposit'](econ, user_id=123)
        self.assertEqual(result, (True, 81, 0, 90))

    def test_insufficient_wallet_does_not_partially_mutate_deposit(self):
        econ = {'balance': 30, 'bank_deposit': 70}
        before = copy.deepcopy(econ)
        result = self.ctx['_bank_deposit'](econ, 31, user_id=123)
        self.assertEqual(result, (False, 0, 30, 70))
        self.assertEqual(econ, before)
        self.assertEqual(self.dirty, [])

    def test_withdraw_moves_bank_and_wallet_under_all_locks(self):
        econ = {'balance': 11, 'bank_deposit': 80, 'last_bank_calc': 123.0}
        result = self.ctx['_bank_withdraw'](econ, 25, user_id=123)
        self.assertEqual(result, (True, 25, 36, 55))
        self.assertEqual((econ['balance'], econ['bank_deposit']), (36, 55))
        self.assertEqual(econ['economy_transactions'][-1]['reason'], 'Снятие с банковского вклада')
        self.assertEqual(self.held, {})

    def test_withdraw_all_zeros_deposit_and_resets_interest_clock(self):
        econ = {'balance': 11, 'bank_deposit': 80, 'last_bank_calc': 123.0}
        result = self.ctx['_bank_withdraw'](econ, user_id=123)
        self.assertEqual(result, (True, 80, 91, 0))
        self.assertGreater(econ['last_bank_calc'], 123.0)

    def test_insufficient_deposit_does_not_partially_mutate_wallet(self):
        econ = {'balance': 11, 'bank_deposit': 20, 'last_bank_calc': 123.0}
        before = copy.deepcopy(econ)
        result = self.ctx['_bank_withdraw'](econ, 21, user_id=123)
        self.assertEqual(result, (False, 0, 11, 20))
        self.assertEqual(econ, before)
        self.assertEqual(self.dirty, [])

    def test_non_positive_amount_is_rejected_without_mutation(self):
        econ = {'balance': 100, 'bank_deposit': 200}
        before = copy.deepcopy(econ)
        self.assertFalse(self.ctx['_bank_deposit'](econ, 0, user_id=123)[0])
        self.assertFalse(self.ctx['_bank_withdraw'](econ, -1, user_id=123)[0])
        self.assertEqual(econ, before)

    def test_admin_clamped_debit_reads_live_balance_inside_locks(self):
        econ = {'balance': 35}
        removed, balance_after = self.ctx['_debit_balance_up_to'](econ, 100, reason='Admin take')
        self.assertEqual((removed, balance_after), (35, 0))
        self.assertEqual(econ['economy_transactions'][-1]['reason'], 'Admin take')
        self.assertEqual(self.held, {})

    def test_admin_clamped_debit_does_not_make_balance_negative(self):
        econ = {'balance': 0}
        before = copy.deepcopy(econ)
        removed, balance_after = self.ctx['_debit_balance_up_to'](econ, 100, reason='Admin take')
        self.assertEqual((removed, balance_after), (0, 0))
        self.assertEqual(econ, before)

    def test_interest_accrual_mutates_balance_and_clock_under_database_lock(self):
        class LockedDict(dict):
            def __setitem__(inner_self, key, value):
                self.assertGreater(self.held.get('db', 0), 0, f'{key} updated outside db_lock')
                return super(LockedDict, inner_self).__setitem__(key, value)
        econ_record = LockedDict({'bank_deposit': 1000, 'last_bank_calc': 1000.0})
        dirty_calls = []
        with mock.patch.object(economy, '_db_lock', self.db_lock), mock.patch.object(
            economy, '_mark_dirty', lambda: (self.assertGreater(self.held.get('db', 0), 0), dirty_calls.append(True))
        ):
            earned = economy.update_bank_interest(econ_record, now=1000 + 6 * 3600 + 1)
        self.assertEqual(earned, 2)
        self.assertEqual(econ_record['bank_deposit'], 1002)
        self.assertEqual(econ_record['last_bank_calc'], 1000.0 + 6 * 3600)
        self.assertEqual(dirty_calls, [True])
        self.assertEqual(self.held, {})

    def test_pet_needs_decay_is_mutated_under_database_lock(self):
        class LockedDict(dict):
            def __setitem__(inner_self, key, value):
                self.assertGreater(self.held.get('db', 0), 0, f'{key} updated outside db_lock')
                return super(LockedDict, inner_self).__setitem__(key, value)
        pet = LockedDict({'hunger': 100, 'cleanliness': 100, 'last_update': 1000.0})
        dirty_calls = []
        with mock.patch.object(economy, '_db_lock', self.db_lock), mock.patch.object(
            economy, '_mark_dirty', lambda: (self.assertGreater(self.held.get('db', 0), 0), dirty_calls.append(True))
        ):
            economy.update_pet_stats(pet, now=1000 + 3600)
        self.assertEqual(pet['hunger'], 96)
        self.assertEqual(pet['cleanliness'], 97)
        self.assertEqual(pet['last_update'], 4600.0)
        self.assertEqual(dirty_calls, [True])
        self.assertEqual(self.held, {})

    def test_bank_handler_paths_call_atomic_helpers_instead_of_split_writes(self):
        root = Path(__file__).parent
        callbacks_text = (root / 'handlers' / 'callbacks.py').read_text(encoding='utf-8')
        moderation_text = (root / 'handlers' / 'moderation.py').read_text(encoding='utf-8')
        callback_bank = callbacks_text[callbacks_text.index("elif action_data == 'bank_dep_100':"):callbacks_text.index('# ЛОТЕРЕЯ')]
        self.assertEqual(callback_bank.count('_bank_deposit('), 2)
        self.assertEqual(callback_bank.count('_bank_withdraw('), 2)
        self.assertNotIn("econ['bank_deposit'] =", callback_bank)
        self.assertNotIn("econ['bank_deposit'] -=", callback_bank)
        first_bank = moderation_text[moderation_text.index("if text_lower.startswith(('банк положить', 'депозит')):"):moderation_text.index('# РП-КОМАНДЫ')]
        second_bank = moderation_text[moderation_text.index('# БАНК: пополнение/снятие прямо текстом'):moderation_text.index('# Удобные русские названия существующих разделов')]
        self.assertIn('_bank_deposit(', first_bank)
        self.assertIn('_bank_withdraw(', first_bank)
        self.assertIn('_bank_deposit(', second_bank)
        self.assertIn('_bank_withdraw(', second_bank)
        for block in (first_bank, second_bank):
            self.assertNotIn("econ['bank_deposit'] =", block)
            self.assertNotIn("econ['bank_deposit'] +=", block)
            self.assertNotIn("econ['bank_deposit'] -=", block)



class DurableSaleTransactionTests(unittest.TestCase):
    """Exercise /sell against Neon failures and malformed legacy inventory keys."""

    def setUp(self):
        self.econ = {
            'user_id': 701,
            'balance': 100,
            'account_exp': 4,
            'fish_inventory': {'Salmon': 2, 'legacy_unknown_fish': 7},
            'hunt_inventory': {'Rabbit': 1, 'legacy_unknown_trophy': 3},
        }
        self.bot = FakeBot()
        self.dirty = []
        self.save_calls = []
        self.save_results = [True]
        self.originals = {}

        def save(reason='test', **kwargs):
            self.save_calls.append(reason)
            if len(self.save_calls) == 1 and self.save_results and self.save_results[0] is False:
                # Simulate an unrelated field update while Neon I/O is in flight.
                self.econ['account_exp'] = 77
            return self.save_results.pop(0) if self.save_results else True

        def adjust(econ, amount, reason='Изменение баланса'):
            before = int(econ.get('balance', 0) or 0)
            delta = int(amount or 0)
            econ['balance'] = before + delta
            econ.setdefault('economy_transactions', []).append({
                'delta': delta, 'before': before, 'after': before + delta, 'reason': reason,
            })
            return econ['balance']

        self.message = SimpleNamespace(
            from_user=SimpleNamespace(id=701, first_name='Test', last_name='', username='tester'),
            chat=SimpleNamespace(id=701), text='/sell',
        )
        values = {
            'can_process_user_message': lambda _message: True,
            'get_user_econ': lambda *_args, **_kwargs: self.econ,
            'gold_rush_event': {'active': False},
            'get_economic_event': lambda: None,
            'FISH_TYPES': [('Salmon', 'A fish', '10')],
            'HUNT_TYPES': [('Rabbit', 'A trophy', '20')],
            'BALANCE_TX_LOCK': threading.RLock(),
            'db_lock': threading.RLock(),
            '_adjust_balance': adjust,
            'mark_dirty': lambda: self.dirty.append(True),
            'critical_save': save,
            'bot': self.bot,
        }
        for key, value in values.items():
            self.originals[key] = (key in economy_handlers.__dict__, economy_handlers.__dict__.get(key))
            setattr(economy_handlers, key, value)

    def tearDown(self):
        for key, (existed, value) in self.originals.items():
            if existed:
                setattr(economy_handlers, key, value)
            else:
                economy_handlers.__dict__.pop(key, None)

    def test_sale_is_durable_and_preserves_unknown_legacy_items(self):
        economy_handlers.cmd_sell(self.message)
        self.assertEqual(self.econ['balance'], 140)
        self.assertEqual(self.econ['fish_inventory'], {'legacy_unknown_fish': 7})
        self.assertEqual(self.econ['hunt_inventory'], {'legacy_unknown_trophy': 3})
        self.assertEqual(len(self.save_calls), 1)
        self.assertIn('+40', self.bot.replies[-1][0])

    def test_failed_sale_reverses_only_its_fields_and_preserves_concurrent_profile_update(self):
        self.save_results = [False, True]
        economy_handlers.cmd_sell(self.message)
        self.assertEqual(self.econ['balance'], 100)
        self.assertEqual(self.econ['fish_inventory'], {'Salmon': 2, 'legacy_unknown_fish': 7})
        self.assertEqual(self.econ['hunt_inventory'], {'Rabbit': 1, 'legacy_unknown_trophy': 3})
        self.assertEqual(self.econ['account_exp'], 77)
        self.assertEqual([op['delta'] for op in self.econ['economy_transactions']], [40, -40])
        self.assertIn('не удалось сохранить', self.bot.replies[-1][0].lower())
        self.assertEqual(len(self.save_calls), 2)


class DurableCoinVehiclePurchaseTests(unittest.TestCase):
    def setUp(self):
        self.econ = {'user_id': 702, 'balance': 500, 'account_exp': 8, 'vehicle_inventory': []}
        self.dirty = []
        self.save_calls = []
        self.save_results = [True]
        self.originals = {}

        def save(reason='test', **kwargs):
            self.save_calls.append(reason)
            if len(self.save_calls) == 1 and self.save_results and self.save_results[0] is False:
                self.econ['account_exp'] = 99
            return self.save_results.pop(0) if self.save_results else True

        def adjust(econ, amount, reason='Изменение баланса'):
            before = int(econ.get('balance', 0) or 0)
            delta = int(amount or 0)
            econ['balance'] = before + delta
            econ.setdefault('economy_transactions', []).append({'delta': delta, 'before': before, 'after': before + delta, 'reason': reason})
            return econ['balance']

        values = {
            'VEHICLES': {'test_car': {'name': 'Test car', 'price': 125}},
            'BALANCE_TX_LOCK': threading.RLock(),
            'db_lock': threading.RLock(),
            '_adjust_balance': adjust,
            'mark_dirty': lambda: self.dirty.append(True),
            'critical_save': save,
        }
        for key, value in values.items():
            self.originals[key] = (key in callbacks.__dict__, callbacks.__dict__.get(key))
            setattr(callbacks, key, value)

    def tearDown(self):
        for key, (existed, value) in self.originals.items():
            if existed:
                setattr(callbacks, key, value)
            else:
                callbacks.__dict__.pop(key, None)

    def test_purchase_success_debits_once_and_equips_new_vehicle(self):
        ok, message = callbacks._purchase_coin_vehicle(self.econ, 'test_car')
        self.assertTrue(ok)
        self.assertIn('Test car', message)
        self.assertEqual(self.econ['balance'], 375)
        self.assertEqual(self.econ['vehicle_inventory'], ['test_car'])
        self.assertEqual(self.econ['equipped_vehicle'], 'test_car')
        self.assertEqual(len(self.save_calls), 1)

    def test_failed_save_reverses_vehicle_and_price_without_clobbering_other_fields(self):
        self.save_results = [False, True]
        ok, message = callbacks._purchase_coin_vehicle(self.econ, 'test_car')
        self.assertFalse(ok)
        self.assertEqual(self.econ['balance'], 500)
        self.assertEqual(self.econ['vehicle_inventory'], [])
        self.assertNotIn('equipped_vehicle', self.econ)
        self.assertNotIn('vehicle', self.econ)
        self.assertEqual(self.econ['account_exp'], 99)
        self.assertEqual([op['delta'] for op in self.econ['economy_transactions']], [-125, 125])
        self.assertIn('восстановлены', message)
        self.assertEqual(len(self.save_calls), 2)

    def test_duplicate_or_zero_price_vehicle_is_rejected(self):
        self.econ['vehicle_inventory'] = ['test_car']
        ok, _ = callbacks._purchase_coin_vehicle(self.econ, 'test_car')
        self.assertFalse(ok)
        callbacks.VEHICLES['free_car'] = {'name': 'Free car', 'price': 0}
        try:
            ok, _ = callbacks._purchase_coin_vehicle(self.econ, 'free_car')
            self.assertFalse(ok)
        finally:
            callbacks.VEHICLES.pop('free_car', None)
        self.assertEqual(self.econ['balance'], 500)


class DurablePlayerMarketTests(unittest.TestCase):
    def setUp(self):
        self.buyer = {'user_id': 811, 'balance': 500, 'account_exp': 10, 'fish_inventory': {'Salmon': 3}}
        self.seller = {'user_id': 812, 'balance': 100, 'season_points': 2, 'fish_inventory': {}}
        self.econs = {811: self.buyer, 812: self.seller}
        self.db = {'player_market': {
            '123456': {
                'seller_id': 812, 'seller_name': 'Seller', 'kind': 'fish',
                'item_name': 'Salmon', 'name': 'Salmon', 'qty': 2,
                'price': 150, 'created_at': time.time() - 5,
            }
        }}
        self.dirty = []
        self.save_calls = []
        self.save_results = [True]
        self.originals = {}

        def save(reason='test', **kwargs):
            self.save_calls.append(reason)
            if len(self.save_calls) == 1 and self.save_results and self.save_results[0] is False:
                self.buyer['account_exp'] = 91
                self.seller['season_points'] = 99
            return self.save_results.pop(0) if self.save_results else True

        def get_user_econ(user_id=None, *args, **kwargs):
            if user_id is None:
                user_id = args[0] if args else kwargs.get('user_id')
            return self.econs[int(user_id)]

        def adjust(econ, amount, reason='Изменение баланса'):
            before = int(econ.get('balance', 0) or 0)
            delta = int(amount or 0)
            econ['balance'] = before + delta
            econ.setdefault('economy_transactions', []).append({'delta': delta, 'before': before, 'after': before + delta, 'reason': reason})
            return econ['balance']

        values = {
            'db': self.db,
            'PLAYER_MARKET_LOCK': threading.RLock(),
            'BALANCE_TX_LOCK': threading.RLock(),
            'db_lock': threading.RLock(),
            'serialized_multi_user_action': lambda *_args, **_kwargs: nullcontext(),
            'FISH_TYPES': [('Salmon', 'Fish', '10')],
            'HUNT_TYPES': [('Rabbit', 'Trophy', '20')],
            'get_user_econ': get_user_econ,
            '_adjust_balance': adjust,
            'mark_dirty': lambda: self.dirty.append(True),
            'critical_save': save,
        }
        for key, value in values.items():
            self.originals[key] = (key in callbacks.__dict__, callbacks.__dict__.get(key))
            setattr(callbacks, key, value)

    def tearDown(self):
        for key, (existed, value) in self.originals.items():
            if existed:
                setattr(callbacks, key, value)
            else:
                callbacks.__dict__.pop(key, None)

    def test_market_purchase_success_moves_coins_and_inventory_once(self):
        status, message = callbacks._purchase_player_market_listing(811, 'Buyer', 'buyer', '123456')
        self.assertEqual(status, 'success')
        self.assertIn('сохранена', message)
        self.assertEqual(self.buyer['balance'], 350)
        self.assertEqual(self.seller['balance'], 250)
        self.assertEqual(self.buyer['fish_inventory']['Salmon'], 5)
        self.assertNotIn('123456', self.db['player_market'])
        self.assertEqual(len(self.save_calls), 1)

    def test_market_purchase_save_failure_compensates_only_transaction_fields(self):
        self.save_results = [False, True]
        status, message = callbacks._purchase_player_market_listing(811, 'Buyer', 'buyer', '123456')
        self.assertEqual(status, 'failed')
        self.assertIn('восстановлены', message)
        self.assertEqual(self.buyer['balance'], 500)
        self.assertEqual(self.seller['balance'], 100)
        self.assertEqual(self.buyer['fish_inventory']['Salmon'], 3)
        self.assertIn('123456', self.db['player_market'])
        self.assertEqual(self.buyer['account_exp'], 91)
        self.assertEqual(self.seller['season_points'], 99)
        self.assertEqual([x['delta'] for x in self.buyer['economy_transactions']], [-150, 150])
        self.assertEqual([x['delta'] for x in self.seller['economy_transactions']], [150, -150])
        self.assertEqual(len(self.save_calls), 2)

    def test_same_listing_cannot_be_purchased_twice_or_by_its_seller(self):
        status, _ = callbacks._purchase_player_market_listing(812, 'Seller', 'seller', '123456')
        self.assertEqual(status, 'failed')
        status, _ = callbacks._purchase_player_market_listing(811, 'Buyer', 'buyer', '123456')
        self.assertEqual(status, 'success')
        balance = self.buyer['balance']
        status, _ = callbacks._purchase_player_market_listing(811, 'Buyer', 'buyer', '123456')
        self.assertEqual(status, 'failed')
        self.assertEqual(self.buyer['balance'], balance)


class PlayerMarketPostingTests(unittest.TestCase):
    def setUp(self):
        self.econ = {'user_id': 813, 'balance': 200, 'account_exp': 3, 'fish_inventory': {'Salmon': 2}}
        self.db = {'player_market': {}}
        self.bot = FakeBot()
        self.save_calls = []
        self.save_results = [True]
        self.dirty = []
        self.originals = {}
        source_path = Path(__file__).with_name('newfile.py')
        tree = ast.parse(source_path.read_text(encoding='utf-8'), filename=str(source_path))
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'cmd_player_market')

        def save(reason='test', **kwargs):
            self.save_calls.append(reason)
            if len(self.save_calls) == 1 and self.save_results and self.save_results[0] is False:
                self.econ['account_exp'] = 55
            return self.save_results.pop(0) if self.save_results else True

        ctx = {
            'can_process_user_message': lambda _message: True,
            'get_user_econ': lambda *_args, **_kwargs: self.econ,
            'db': self.db,
            'PLAYER_MARKET_LOCK': threading.RLock(),
            'BALANCE_TX_LOCK': threading.RLock(),
            'db_lock': threading.RLock(),
            'FISH_TYPES': [('Salmon', 'Fish', '10')],
            'HUNT_TYPES': [('Rabbit', 'Trophy', '20')],
            'copy': copy,
            'random': __import__('random'),
            'time': time,
            'html': html,
            'mark_dirty': lambda: self.dirty.append(True),
            'critical_save': save,
            'bot': self.bot,
        }
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(source_path), 'exec'), ctx)
        self.cmd = ctx['cmd_player_market']
        self.ctx = ctx

    def test_post_listing_success_removes_exactly_one_resource(self):
        msg = SimpleNamespace(
            from_user=SimpleNamespace(id=813, first_name='Seller', last_name='', username='seller'),
            chat=SimpleNamespace(id=813), text='/pmarket sell fish 1 500',
        )
        self.cmd(msg)
        self.assertEqual(self.econ['fish_inventory'], {'Salmon': 1})
        self.assertEqual(len(self.db['player_market']), 1)
        listing = next(iter(self.db['player_market'].values()))
        self.assertEqual((listing['item_name'], listing['price'], listing['qty']), ('Salmon', 500, 1))
        self.assertEqual(len(self.save_calls), 1)

    def test_failed_posting_restores_resource_without_clobbering_other_fields(self):
        self.save_results = [False, True]
        msg = SimpleNamespace(
            from_user=SimpleNamespace(id=813, first_name='Seller', last_name='', username='seller'),
            chat=SimpleNamespace(id=813), text='/pmarket sell fish 1 500',
        )
        self.cmd(msg)
        self.assertEqual(self.econ['fish_inventory'], {'Salmon': 2})
        self.assertEqual(self.econ['account_exp'], 55)
        self.assertEqual(self.db['player_market'], {})
        self.assertEqual(len(self.save_calls), 2)


class PlayerMarketExpiryTests(unittest.TestCase):
    def setUp(self):
        self.seller = {'user_id': 814, 'balance': 10, 'season_points': 1, 'fish_inventory': {'Salmon': 1}}
        self.db = {'player_market': {
            'expired': {'seller_id': 814, 'seller_name': 'Seller', 'kind': 'fish', 'item_name': 'Salmon', 'name': 'Salmon', 'qty': 2, 'price': 100, 'created_at': 1}
        }}
        self.save_calls = []
        self.save_results = [True]
        self.dirty = []
        source_path = Path(__file__).with_name('newfile.py')
        tree = ast.parse(source_path.read_text(encoding='utf-8'), filename=str(source_path))
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_expire_player_market_listings')

        def save(reason='test', **kwargs):
            self.save_calls.append(reason)
            if len(self.save_calls) == 1 and self.save_results and self.save_results[0] is False:
                self.seller['season_points'] = 88
            return self.save_results.pop(0) if self.save_results else True

        def get_user_econ(*args, **kwargs):
            uid = kwargs.get('user_id', args[0] if args else 0)
            return self.seller if int(uid) == 814 else {'user_id': int(uid)}

        self.ctx = {
            'db': self.db,
            'PLAYER_MARKET_LOCK': threading.RLock(),
            'BALANCE_TX_LOCK': threading.RLock(),
            'db_lock': threading.RLock(),
            'serialized_multi_user_action': lambda *_args, **_kwargs: nullcontext(),
            'FISH_TYPES': [('Salmon', 'Fish', '10')],
            'HUNT_TYPES': [('Rabbit', 'Trophy', '20')],
            'get_user_econ': get_user_econ,
            'copy': copy,
            'time': time,
            'mark_dirty': lambda: self.dirty.append(True),
            'critical_save': save,
        }
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(source_path), 'exec'), self.ctx)

    def test_expired_listing_returns_item_only_after_durable_save(self):
        self.assertTrue(self.ctx['_expire_player_market_listings'](900, now=100000))
        self.assertEqual(self.seller['fish_inventory']['Salmon'], 3)
        self.assertNotIn('expired', self.db['player_market'])
        self.assertEqual(len(self.save_calls), 1)

    def test_expiry_save_failure_reverses_item_and_restores_listing_only(self):
        self.save_results = [False, True]
        self.assertFalse(self.ctx['_expire_player_market_listings'](900, now=100000))
        self.assertEqual(self.seller['fish_inventory']['Salmon'], 1)
        self.assertEqual(self.seller['season_points'], 88)
        self.assertIn('expired', self.db['player_market'])
        self.assertEqual(len(self.save_calls), 2)


class StarsJournalDurabilityTests(unittest.TestCase):
    def test_final_journal_save_failure_restores_previous_status_and_processed_marker(self):
        state = {
            'stars_payment_log': {'charge-701': {'status': 'processing', 'grant_status': 'pending', 'payload': 'coins:100'}},
            'processed_stars_charges': [],
        }
        dirty = []
        with mock.patch.object(stars, '_db', state, create=True), \
             mock.patch.object(stars, '_db_lock', threading.RLock(), create=True), \
             mock.patch.object(stars, '_mark_dirty', lambda: dirty.append(True), create=True), \
             mock.patch.object(stars, '_save_now', return_value=False, create=True):
            result = stars._finish_stars_payment_journal('charge-701', 'completed')
        self.assertFalse(result)
        self.assertEqual(state['stars_payment_log']['charge-701']['status'], 'processing')
        self.assertEqual(state['stars_payment_log']['charge-701']['grant_status'], 'pending')
        self.assertEqual(state['processed_stars_charges'], [])
        self.assertEqual(len(dirty), 2)

    def test_final_journal_commit_marks_charge_only_after_successful_save(self):
        state = {'stars_payment_log': {'charge-702': {'status': 'processing'}}, 'processed_stars_charges': []}
        with mock.patch.object(stars, '_db', state, create=True), \
             mock.patch.object(stars, '_db_lock', threading.RLock(), create=True), \
             mock.patch.object(stars, '_mark_dirty', lambda: None, create=True), \
             mock.patch.object(stars, '_save_now', return_value=True, create=True):
            result = stars._finish_stars_payment_journal('charge-702', 'completed')
        self.assertTrue(result)
        self.assertEqual(state['stars_payment_log']['charge-702']['status'], 'completed')
        self.assertIn('charge-702', state['processed_stars_charges'])

    def test_external_telegram_gift_delivery_is_not_inside_refund_catch(self):
        source_path = Path(__file__).with_name('handlers') / 'callbacks.py'
        text = source_path.read_text(encoding='utf-8')
        tree = ast.parse(text, filename=str(source_path))
        impl = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_process_stars_successful_payment_impl')
        gift_if = next(n for n in ast.walk(impl) if isinstance(n, ast.If) and "payload.startswith('tgift:')" in (ast.get_source_segment(text, n.test) or ''))
        # The `send_gift` try/except is allowed to refund send failures, but
        # finalization must be a sibling statement so journal failures cannot
        # refund a gift Telegram already delivered.
        tries = [n for n in ast.walk(gift_if) if isinstance(n, ast.Try) and any(isinstance(x, ast.Expr) and isinstance(x.value, ast.Call) and getattr(x.value.func, 'id', '') == '_refund_and_mark_stars_payment' for h in n.handlers for x in ast.walk(h))]
        self.assertTrue(tries)
        for try_node in tries:
            calls = [n for n in ast.walk(try_node) if isinstance(n, ast.Call) and getattr(n.func, 'id', '') == '_finalize_stars_success']
            self.assertEqual(calls, [])



if __name__ == '__main__':
    unittest.main()


class DurableShopTransactionTests(unittest.TestCase):
    """Exercise the shared durable shop transaction primitive used by callbacks."""
    @classmethod
    def setUpClass(cls):
        source_path = Path(__file__).with_name('handlers') / 'callbacks.py'
        cls.source = source_path.read_text(encoding='utf-8')
        tree = ast.parse(cls.source, filename=str(source_path))
        wanted = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == '_durable_profile_transaction'
        )
        cls.function = wanted

    def setUp(self):
        self.econ = {'balance': 1_000, 'inventory': [], 'season_points': 3}
        self.calls = []
        self.dirty = []
        self.save_results = [True]
        self.save_hook = None
        self.ctx = {
            'copy': copy,
            'BALANCE_TX_LOCK': threading.RLock(),
            'db_lock': threading.RLock(),
            '_adjust_balance': self.adjust,
            'mark_dirty': lambda: self.dirty.append(True),
            'critical_save': self.save,
        }
        exec(
            compile(ast.Module(body=[self.function], type_ignores=[]), '<durable-shop-helper>', 'exec'),
            self.ctx,
        )

    def adjust(self, profile, amount, reason=None):
        self.calls.append((amount, reason))
        profile['balance'] = int(profile.get('balance', 0) or 0) + int(amount)

    def save(self, reason, retries=3):
        if self.save_hook:
            self.save_hook(reason, retries)
        result = self.save_results.pop(0) if self.save_results else True
        return result

    def test_success_debits_and_applies_mutation_before_success(self):
        def mutation():
            self.econ['inventory'].append('ring')
            return 'ring'

        ok, result = self.ctx['_durable_profile_transaction'](
            self.econ, 'test ring', ['inventory'], mutation, cost=250,
        )
        self.assertTrue(ok)
        self.assertEqual(result, 'ring')
        self.assertEqual(self.econ['balance'], 750)
        self.assertEqual(self.econ['inventory'], ['ring'])
        self.assertEqual(self.calls[0][0], -250)
        self.assertEqual(len(self.calls), 1)

    def test_failed_neon_save_rolls_back_purchase_and_preserves_orthogonal_change(self):
        self.save_results = [False, True]
        def concurrent_change(reason, retries):
            if len(self.calls) == 1:
                self.econ['season_points'] = 88
        self.save_hook = concurrent_change

        ok, reason = self.ctx['_durable_profile_transaction'](
            self.econ, 'test ring', ['inventory'],
            lambda: self.econ['inventory'].append('ring'), cost=250,
        )
        self.assertFalse(ok)
        self.assertEqual(reason, 'save_failed')
        self.assertEqual(self.econ['balance'], 1_000)
        self.assertEqual(self.econ['inventory'], [])
        self.assertEqual(self.econ['season_points'], 88)
        self.assertEqual([delta for delta, _ in self.calls], [-250, 250])

    def test_validation_prevents_duplicate_charge_and_save(self):
        self.save_results = []
        ok, reason = self.ctx['_durable_profile_transaction'](
            self.econ, 'duplicate purchase', ['inventory'],
            lambda: self.econ['inventory'].append('ring'), cost=250,
            validate=lambda: 'already_owned',
        )
        self.assertFalse(ok)
        self.assertEqual(reason, 'already_owned')
        self.assertEqual(self.econ['balance'], 1_000)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.dirty, [])

    def test_insufficient_balance_does_not_mutate_or_save(self):
        self.econ['balance'] = 10
        self.save_results = []
        ok, reason = self.ctx['_durable_profile_transaction'](
            self.econ, 'expensive item', ['inventory'],
            lambda: self.econ['inventory'].append('item'), cost=25,
        )
        self.assertFalse(ok)
        self.assertEqual(reason, 'insufficient')
        self.assertEqual(self.econ['balance'], 10)
        self.assertEqual(self.econ['inventory'], [])
        self.assertEqual(self.calls, [])

    def test_mutation_exception_compensates_coin_debit(self):
        def broken_mutation():
            self.econ['inventory'].append('partial')
            raise RuntimeError('mutation failure')

        ok, reason = self.ctx['_durable_profile_transaction'](
            self.econ, 'broken item', ['inventory'], broken_mutation, cost=250,
        )
        self.assertFalse(ok)
        self.assertEqual(reason, 'mutation_error:RuntimeError')
        self.assertEqual(self.econ['balance'], 1_000)
        self.assertEqual(self.econ['inventory'], [])
        self.assertEqual([delta for delta, _ in self.calls], [-250, 250])
        self.assertEqual(self.save_results, [])

    def test_failed_save_reverses_coin_credit_created_inside_mutation(self):
        self.save_results = [False, True]
        def mutation_with_credit():
            self.econ['inventory'].append('business-upgrade')
            self.ctx['_adjust_balance'](self.econ, 500, reason='settled business profit')
            return 'upgraded'

        ok, reason = self.ctx['_durable_profile_transaction'](
            self.econ, 'business upgrade', ['inventory'], mutation_with_credit, cost=250,
        )
        self.assertFalse(ok)
        self.assertEqual(reason, 'save_failed')
        self.assertEqual(self.econ['balance'], 1_000)
        self.assertEqual(self.econ['inventory'], [])
        self.assertEqual([delta for delta, _ in self.calls], [-250, 500, -500, 250])

    def test_profile_shop_callbacks_use_durable_helper_and_no_direct_debit(self):
        targets = [
            "buy_studio_", "buy_seed_", "buy_buff_", "buy_theme_", "buy_rod_",
            "buy_bow_", "buy_ring_", "buy_title_", "buy_badge_", "buy_pet_",
        ]
        for target in targets:
            with self.subTest(target=target):
                needle = f"elif action_data.startswith('{target}')"
                start = self.source.index(needle)
                next_branch = self.source.find('\n        elif action_data', start + len(needle))
                block = self.source[start:next_branch if next_branch != -1 else len(self.source)]
                self.assertIn('_durable_profile_transaction(', block)
                self.assertNotIn('_adjust_balance(', block)

    def test_one_time_items_have_duplicate_validation(self):
        for target in ("buy_ring_", "buy_theme_", "buy_title_", "buy_badge_", "buy_pet_"):
            with self.subTest(target=target):
                needle = f"elif action_data.startswith('{target}')"
                start = self.source.index(needle)
                next_branch = self.source.find('\n        elif action_data', start + len(needle))
                block = self.source[start:next_branch if next_branch != -1 else len(self.source)]
                self.assertIn('validate=', block)
                self.assertTrue(any(token in block for token in ('already_owned', 'inventory')))


class DurableBusinessTransactionTests(unittest.TestCase):
    """Exercise callback business purchases, upgrades, and sales without Telegram/Neon."""
    @classmethod
    def setUpClass(cls):
        source_path = Path(__file__).with_name('handlers') / 'callbacks.py'
        cls.source = source_path.read_text(encoding='utf-8')
        tree = ast.parse(cls.source, filename=str(source_path))
        wanted = {
            '_durable_profile_transaction', '_purchase_ordinary_business',
            '_upgrade_business_durably', '_sell_ordinary_business_durably',
        }
        cls.nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in wanted]
        cls.found = {node.name for node in cls.nodes}
        if cls.found != wanted:
            raise AssertionError(f'Business transaction helper set mismatch: {cls.found}')

    def setUp(self):
        self.econ = {
            'balance': 5_000,
            'businesses': {},
            'biz_levels': {},
            'biz_purchase_price': {},
            'biz_last_collect': {},
            'biz_income_carry': {},
            'business_transactions': [],
            'business_tax_paid': 0,
            'stats': {},
            'season_points': 7,
        }
        self.balance_ops = []
        self.save_results = [True]
        self.save_hook = None
        self.settled_levels = []
        self.dirty = []
        self.ctx = {
            'copy': copy,
            'BALANCE_TX_LOCK': threading.RLock(),
            'db_lock': threading.RLock(),
            'BUSINESSES': {'studio': {'name': 'Studio', 'price': 500, 'upgrade_cost': 200}},
            'DONOR_BUSINESSES': {'vip_studio': {'name': 'VIP Studio', 'upgrade_cost': 500}},
            'BUSINESS_SELL_RATE': 0.6,
            'time': SimpleNamespace(time=lambda: 10_000.0),
            '_adjust_balance': self.adjust,
            '_record_business_tx': self.record_business_tx,
            '_settle_business_net_profit': self.settle_business,
            'mark_dirty': lambda: self.dirty.append(True),
            'critical_save': self.save,
        }
        exec(compile(ast.Module(body=self.nodes, type_ignores=[]), '<durable-business-helpers>', 'exec'), self.ctx)

    def adjust(self, profile, amount, reason=None):
        amount = int(amount)
        self.balance_ops.append((amount, reason))
        profile['balance'] = int(profile.get('balance', 0) or 0) + amount

    @staticmethod
    def record_business_tx(profile, row):
        tx = profile.setdefault('business_transactions', [])
        tx.append(row)
        del tx[:-200]

    def settle_business(self, profile, business_id, now=None):
        self.settled_levels.append(profile.get('biz_levels', {}).get(business_id, 1))
        self.adjust(profile, 100, reason=f'profit {business_id}')
        profile['business_tax_paid'] = int(profile.get('business_tax_paid', 0) or 0) + 20
        profile.setdefault('biz_last_collect', {})[business_id] = now or 10_000.0
        profile.setdefault('biz_income_carry', {})[business_id] = 0.25
        return 100, 20

    def save(self, reason, retries=3):
        if self.save_hook:
            self.save_hook(reason, retries)
        return self.save_results.pop(0) if self.save_results else True

    def test_business_purchase_is_durable_and_initializes_all_income_fields(self):
        ok, result = self.ctx['_purchase_ordinary_business'](self.econ, 'studio')
        self.assertTrue(ok)
        self.assertEqual(self.econ['balance'], 4_500)
        self.assertIn('studio', self.econ['businesses'])
        self.assertEqual(self.econ['biz_levels']['studio'], 1)
        self.assertEqual(self.econ['biz_purchase_price']['studio'], 500)
        self.assertEqual(self.econ['biz_last_collect']['studio'], 10_000.0)
        self.assertEqual(self.econ['biz_income_carry']['studio'], 0.0)
        self.assertEqual(self.econ['stats']['biz_owned_total'], 1)
        self.assertEqual(self.econ['business_transactions'][-1]['type'], 'buy')
        self.assertEqual(result['price'], 500)

    def test_duplicate_stale_business_purchase_does_not_charge_twice(self):
        self.econ['businesses']['studio'] = 1.0
        self.save_results = []
        ok, reason = self.ctx['_purchase_ordinary_business'](self.econ, 'studio')
        self.assertFalse(ok)
        self.assertEqual(reason, 'already_owned')
        self.assertEqual(self.econ['balance'], 5_000)
        self.assertEqual(self.balance_ops, [])

    def test_failed_business_purchase_save_rolls_back_only_business_fields(self):
        self.save_results = [False, True]
        self.save_hook = lambda _reason, _retries: self.econ.__setitem__('season_points', 99)
        ok, reason = self.ctx['_purchase_ordinary_business'](self.econ, 'studio')
        self.assertFalse(ok)
        self.assertEqual(reason, 'save_failed')
        self.assertEqual(self.econ['balance'], 5_000)
        self.assertNotIn('studio', self.econ['businesses'])
        self.assertEqual(self.econ['season_points'], 99)
        self.assertEqual([delta for delta, _ in self.balance_ops], [-500, 500])

    def test_business_upgrade_settles_old_level_and_rolls_back_income_on_save_failure(self):
        self.econ['businesses'] = {'studio': 1.0}
        self.econ['biz_levels'] = {'studio': 2}
        self.econ['biz_purchase_price'] = {'studio': 500}
        self.econ['biz_last_collect'] = {'studio': 10.0}
        self.econ['biz_income_carry'] = {'studio': 0.1}
        self.save_results = [False, True]
        self.save_hook = lambda _reason, _retries: self.econ.__setitem__('season_points', 123)
        ok, reason = self.ctx['_upgrade_business_durably'](self.econ, 'studio')
        self.assertFalse(ok)
        self.assertEqual(reason, 'save_failed')
        self.assertEqual(self.settled_levels, [2])
        self.assertEqual(self.econ['balance'], 5_000)
        self.assertEqual(self.econ['biz_levels']['studio'], 2)
        self.assertEqual(self.econ['biz_last_collect']['studio'], 10.0)
        self.assertEqual(self.econ['biz_income_carry']['studio'], 0.1)
        self.assertEqual(self.econ['business_tax_paid'], 0)
        self.assertEqual(self.econ['season_points'], 123)
        self.assertEqual([delta for delta, _ in self.balance_ops], [-400, 100, -100, 400])

    def test_unowned_business_cannot_be_upgraded_through_stale_callback(self):
        self.save_results = []
        ok, reason = self.ctx['_upgrade_business_durably'](self.econ, 'studio')
        self.assertFalse(ok)
        self.assertEqual(reason, 'not_owned')
        self.assertEqual(self.econ['balance'], 5_000)
        self.assertEqual(self.balance_ops, [])

    def test_business_sale_credits_refund_and_income_atomically(self):
        self.econ['balance'] = 5_000
        self.econ['businesses'] = {'studio': 1.0}
        self.econ['biz_levels'] = {'studio': 2}
        self.econ['biz_purchase_price'] = {'studio': 500}
        self.econ['biz_last_collect'] = {'studio': 1.0}
        self.econ['biz_income_carry'] = {'studio': 0.1}
        ok, result = self.ctx['_sell_ordinary_business_durably'](self.econ, 'studio')
        self.assertTrue(ok)
        self.assertEqual(result['value'], 300)
        self.assertEqual(result['pending_net'], 100)
        self.assertEqual(self.econ['balance'], 5_400)
        self.assertNotIn('studio', self.econ['businesses'])
        self.assertNotIn('studio', self.econ['biz_levels'])
        self.assertEqual(self.econ['stats']['biz_owned_total'], 0)
        self.assertEqual(self.econ['business_transactions'][-1]['type'], 'sell')

    def test_failed_business_sale_rolls_back_refund_profit_and_fields_without_stale_profile_restore(self):
        self.econ['businesses'] = {'studio': 1.0}
        self.econ['biz_levels'] = {'studio': 2}
        self.econ['biz_purchase_price'] = {'studio': 500}
        self.econ['biz_last_collect'] = {'studio': 1.0}
        self.econ['biz_income_carry'] = {'studio': 0.1}
        self.save_results = [False, True]
        self.save_hook = lambda _reason, _retries: self.econ.__setitem__('season_points', 42)
        ok, reason = self.ctx['_sell_ordinary_business_durably'](self.econ, 'studio')
        self.assertFalse(ok)
        self.assertEqual(reason, 'save_failed')
        self.assertEqual(self.econ['balance'], 5_000)
        self.assertIn('studio', self.econ['businesses'])
        self.assertEqual(self.econ['biz_levels']['studio'], 2)
        self.assertEqual(self.econ['biz_last_collect']['studio'], 1.0)
        self.assertEqual(self.econ['season_points'], 42)
        self.assertEqual([delta for delta, _ in self.balance_ops], [100, 300, -400])


class HardLimitedStarsGrantRollbackTests(unittest.TestCase):
    def test_failed_limited_pet_grant_restores_inventory_and_entitlement_fields(self):
        profile = {'paid_stars_items': [], 'pet_inventory': ['cat'], 'season_points': 12}
        before = copy.deepcopy(profile)
        fake_pet = {'name': 'Moon Fox', 'luck_bonus': 200}
        with mock.patch.object(stars, '_pets_data', {'moon_fox': fake_pet}), \
             mock.patch.object(stars, '_mark_dirty', side_effect=RuntimeError('save callback failed')):
            with self.assertRaises(RuntimeError):
                stars.grant_hard_limited_stars_item(profile, 'pet_moon_fox')
        self.assertEqual(profile, before)

    def test_limited_pet_grant_tracks_pet_inventory_in_rollback_snapshot(self):
        source = Path(__file__).with_name('services') / 'stars.py'
        tree = ast.parse(source.read_text(encoding='utf-8'), filename=str(source))
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'grant_hard_limited_stars_item')
        segment = ast.get_source_segment(source.read_text(encoding='utf-8'), function) or ''
        self.assertIn("'pet_inventory'", segment)
        self.assertIn('for key, (existed, value) in snapshot.items()', segment)


class FullCodeAuditHardeningTests(unittest.TestCase):
    """Regression coverage for defensive fixes found during the full source audit."""
    @classmethod
    def setUpClass(cls):
        cls.source_path = Path(__file__).with_name('newfile.py')
        cls.source = cls.source_path.read_text(encoding='utf-8')
        cls.tree = ast.parse(cls.source, filename=str(cls.source_path))
        cls.functions = {
            node.name: node for node in cls.tree.body
            if isinstance(node, ast.FunctionDef)
        }

    def _exec_function(self, name, context):
        node = self.functions[name]
        stripped = copy.deepcopy(node)
        stripped.decorator_list = []
        module = ast.Module(body=[stripped], type_ignores=[])
        exec(compile(ast.fix_missing_locations(module), str(self.source_path), 'exec'), context)
        return context[name]

    def test_json_api_preflight_rejects_arrays_and_accepts_objects(self):
        request_obj = SimpleNamespace(path='/api/mini/profile', method='POST', payload=[1, 2])
        request_obj.get_json = lambda silent=True: request_obj.payload
        ctx = {'request': request_obj, 'jsonify': lambda value: value}
        fn = self._exec_function('_validate_miniapp_json_object', ctx)
        result = fn()
        self.assertIsInstance(result, tuple)
        self.assertEqual(result[1], 400)
        self.assertEqual(result[0]['error'], 'invalid_payload')
        request_obj.payload = {'initData': 'x'}
        self.assertIsNone(fn())
        request_obj.path, request_obj.method = '/health', 'GET'
        self.assertIsNone(fn())

    def test_chat_settings_repairs_bad_rows_and_marks_migrations_dirty(self):
        ctx = {
            'db': {'settings': {'123': ['corrupt']}},
            'db_lock': threading.RLock(),
            'copy': copy,
            'mark_dirty': lambda: ctx['dirty'].append(True),
            'dirty': [],
        }
        fn = self._exec_function('get_chat_settings', ctx)
        result = fn(123)
        self.assertIsInstance(result, dict)
        self.assertEqual(result['language'], 'ru')
        self.assertTrue(ctx['dirty'])
        self.assertEqual(ctx['db']['settings']['123'], result)

    def test_profile_merge_ignores_corrupt_shapes_without_losing_valid_assets(self):
        ctx = {
            'copy': copy,
            'math': __import__('math'),
            'VEHICLES': {'car_a': {'tier': 1}},
            'DONOR_VEHICLES': {'car_d': {'tier': 2}},
            'DONOR_BUSINESSES': {'vipbiz': {}},
            'PETS_DATA': {'cat': {}},
        }
        fn = self._exec_function('merge_user_econ_data', ctx)
        dest = {
            'balance': '10', 'inventory': ['🪙'], 'titles': ['old'],
            'fish_inventory': 'damaged', 'backpack': None, 'businesses': ['bad'],
            'vehicle_inventory': 'bad', 'business_transactions': None,
        }
        src = {
            'balance': '25', 'inventory': [['legacy-unhashable'], '🪙'],
            'titles': ['new'], 'fish_inventory': {'Salmon': '2'},
            'backpack': {'energy_drink': '3'}, 'businesses': {'shop': 1},
            'vehicle_inventory': ['car_a'], 'equipped_vehicle': 'car_a',
            'pet_inventory': ['cat'], 'business_transactions': [{'type': 'sale'}],
        }
        result = fn(dest, src)
        self.assertIs(result, dest)
        self.assertEqual(result['balance'], 35)
        self.assertIn(['legacy-unhashable'], result['inventory'])
        self.assertEqual(result['fish_inventory']['Salmon'], 2)
        self.assertEqual(result['backpack']['energy_drink'], 3)
        self.assertEqual(result['businesses']['shop'], 1)
        self.assertEqual(result['equipped_vehicle'], 'car_a')
        self.assertIn('cat', result['pet_inventory'])

    def test_bank_interest_repairs_corrupt_fields_and_caps_extreme_elapsed_time(self):
        dirty = []
        with mock.patch.object(economy, '_db_lock', threading.RLock()), mock.patch.object(
            economy, '_mark_dirty', lambda: dirty.append(True)
        ):
            malformed = {'bank_deposit': 'not-a-number', 'last_bank_calc': 'bad'}
            self.assertEqual(economy.update_bank_interest(malformed, now=100000.0), 0)
            self.assertEqual(malformed['bank_deposit'], 0)
            self.assertEqual(malformed['last_bank_calc'], 100000.0)

            extreme = {'bank_deposit': 1000, 'last_bank_calc': 1.0}
            earned = economy.update_bank_interest(extreme, now=2_000_000_000.0)
            self.assertGreaterEqual(earned, 0)
            self.assertLessEqual(extreme['last_bank_calc'], 2_000_000_000.0)
            self.assertEqual(extreme['last_bank_calc'], 2_000_000_000.0)
        self.assertGreaterEqual(len(dirty), 2)

    def test_pet_decay_recovers_from_corrupt_stats_and_future_timestamp(self):
        dirty = []
        with mock.patch.object(economy, '_db_lock', threading.RLock()), mock.patch.object(
            economy, '_mark_dirty', lambda: dirty.append(True)
        ):
            pet = {'hunger': 'oops', 'cleanliness': float('nan'), 'last_update': 9999999999.0}
            economy.update_pet_stats(pet, now=1000.0)
        self.assertEqual(pet['hunger'], 100)
        self.assertEqual(pet['cleanliness'], 100)
        self.assertEqual(pet['last_update'], 1000.0)
        self.assertTrue(dirty)

    def test_telegram_chat_ids_are_not_synthetically_rewritten(self):
        self.assertEqual(config.normalize_tg_id('-1234567890'), -1234567890)
        self.assertEqual(config.normalize_tg_id('-1001234567890'), -1001234567890)
        self.assertEqual(config.normalize_tg_id('123456'), 123456)
        self.assertEqual(config.normalize_tg_id('not-an-id'), 0)
        self.assertEqual(config.normalize_tg_id(None), 0)

    def test_tamagotchi_public_state_tolerates_nan_and_infinite_fields(self):
        names = {'_mini_finite_float', '_mini_tamagotchi_default', '_mini_tamagotchi_public'}
        nodes = [copy.deepcopy(n) for n in self.tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
        self.assertEqual({n.name for n in nodes}, names)
        for node in nodes:
            node.decorator_list = []
        ctx = {'math': __import__('math'), 'time': time, 're': __import__('re'), '_MINI_TAMAGOTCHI_STAT_DECAY_PER_HOUR': {'hunger': 7.0, 'happiness': 4.0, 'energy': 5.0, 'cleanliness': 3.0}, '_MINI_TAMAGOTCHI_COOLDOWNS': {'feed': 5, 'play': 8, 'sleep': 10, 'clean': 5, 'rename': 30}}
        exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), str(self.source_path), 'exec'), ctx)
        public = ctx['_mini_tamagotchi_public']({
            'created_at': float('nan'), 'last_update': float('inf'),
            'hunger': float('nan'), 'happiness': float('inf'),
            'energy': 'broken', 'cleanliness': -float('inf'),
            'last_actions': {'feed': float('nan'), 'play': float('inf')},
        }, now=1000.0)
        self.assertEqual(public['age_days'], 0)
        for field in ('hunger', 'happiness', 'energy', 'cleanliness'):
            self.assertGreaterEqual(public[field], 0)
            self.assertLessEqual(public[field], 100)
        self.assertTrue(all(isinstance(value, int) and value >= 0 for value in public['next_actions'].values()))

    def test_world_and_global_message_stats_skip_corrupt_legacy_profiles(self):
        from_block = self.source[self.source.index('def _global_message_stats():'):self.source.index('def setup_bot_commands():')]
        globals_ctx = {
            'db_lock': threading.RLock(),
            'db': {'economy': {
                'bad': {'balance': 'oops', 'bank_deposit': None, 'msg_stats': ['wrong']},
                'good': {'balance': 15, 'bank_deposit': 20, 'msg_stats': {'total_count': 4}},
            }, 'bot_news': []},
            'BUSINESSES': {}, 'DONOR_BUSINESSES': {},
            'time': time, 'math': __import__('math'), 'copy': copy,
        }
        tree = ast.parse(from_block)
        target = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_global_message_stats')
        exec(compile(ast.fix_missing_locations(ast.Module(body=[target], type_ignores=[])), str(self.source_path), 'exec'), globals_ctx)
        self.assertEqual(globals_ctx['_global_message_stats'](), (4, 1))

    def test_stars_journal_recovery_repairs_corrupt_processed_list_and_fields(self):
        dirty = []
        db = {
            'stars_payment_log': {
                'charge-corrupt': {
                    'status': 'processing', 'grant_status': 'granted',
                    'payload': 'vippass_monthly', 'buyer_id': 'not-a-user-id',
                    'entitlement_until': 'not-a-timestamp',
                },
                'charge-completed': {
                    'status': 'completed', 'payload': 'vippass_monthly',
                    'buyer_id': 77, 'entitlement_until': 'damaged',
                },
            },
            'processed_stars_charges': 'corrupt-string',
        }
        profile = {'paid_stars_items': None, 'vip_until': 'NaN'}
        ctx = {
            'db': db, 'time': time, 'math': __import__('math'),
            'STARS_VIP_PASS': {'monthly': {'days': 30}},
            'get_user_econ': lambda user_id: profile if user_id == 77 else None,
            'mark_dirty': lambda: dirty.append(True),
        }
        fn = self._exec_function('recover_stars_entitlements_from_journal', ctx)
        self.assertTrue(fn())
        self.assertEqual(db['stars_payment_log']['charge-corrupt']['status'], 'completed')
        self.assertEqual(db['processed_stars_charges'], ['charge-corrupt'])
        self.assertEqual(profile['paid_stars_items'], [])
        self.assertEqual(profile.get('vip_until', 0), 0)
        self.assertTrue(dirty)

        corrupt_root_db = {'stars_payment_log': ['bad-log-row']}
        root_dirty = []
        root_ctx = {
            'db': corrupt_root_db, 'time': time, 'math': __import__('math'),
            'STARS_VIP_PASS': {}, 'get_user_econ': lambda **_kwargs: None,
            'mark_dirty': lambda: root_dirty.append(True),
        }
        self._exec_function('recover_stars_entitlements_from_journal', root_ctx)
        self.assertTrue(root_ctx['recover_stars_entitlements_from_journal']())
        self.assertEqual(corrupt_root_db['stars_payment_log'], {})
        self.assertTrue(root_dirty)

    def test_world_snapshot_ignores_corrupt_root_and_legacy_amounts(self):
        ctx = {
            'db_lock': threading.RLock(),
            'db': {'economy': {'bad': {'user_id': float('inf'), 'balance': 'oops', 'bank_deposit': None}}, 'bot_news': 42},
            'BUSINESSES': {}, 'DONOR_BUSINESSES': {},
        }
        self._exec_function('_mini_world_snapshot', ctx)
        result = ctx['_mini_world_snapshot']()
        self.assertEqual(result['players'], 0)
        self.assertEqual(result['coins'], 0)
        self.assertEqual(result['bank'], 0)
        self.assertEqual(result['news'], [])
