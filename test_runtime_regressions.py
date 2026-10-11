"""Offline regression tests for safe callback acknowledgement and custom titles.
Run with: python -m unittest test_runtime_regressions.py
These tests mock Telegram and Neon; they do not modify real user data.
"""
from __future__ import annotations

import html
import threading
import time
import unittest
from types import SimpleNamespace

from handlers import callbacks, moderation, shop


class FakeBot:
    def __init__(self):
        self.replies = []
        self.answers = []

    def reply_to(self, message, text, **kwargs):
        self.replies.append((text, kwargs))
        return SimpleNamespace(message_id=len(self.replies))

    def answer_callback_query(self, *args, **kwargs):
        self.answers.append((args, kwargs))
        return True


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
        self.assertEqual(self.econ['custom_title'], '<b>Tester</b>')
        self.assertIn('&lt;b&gt;Tester&lt;/b&gt;', self.bot.replies[-1][0])

    def test_reserved_word_can_be_used_as_title(self):
        shop.cmd_custom_title(self.message('/create_tittle set off'))
        self.assertEqual(self.econ['custom_title_text'], 'off')
        self.assertEqual(self.econ['custom_title'], 'off')

    def test_unowned_title_is_rejected(self):
        self.econ['has_custom_title_cert'] = False
        shop.cmd_custom_title(self.message('/create_tittle No entitlement'))
        self.assertIsNone(self.econ['custom_title'])
        self.assertIn('/stars', self.bot.replies[-1][0])

    def test_failed_persistence_rolls_back(self):
        shop.critical_save = lambda *_args, **_kwargs: False
        shop.cmd_custom_title(self.message('/create_tittle Unsaved'))
        self.assertIsNone(self.econ['custom_title'])
        self.assertIsNone(self.econ['custom_title_text'])
        self.assertIn('отменено', self.bot.replies[-1][0])


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


if __name__ == '__main__':
    unittest.main()
