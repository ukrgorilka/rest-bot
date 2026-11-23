"""Comprehensive unit tests for NyaBot v1.0 features, UI helpers, and changelog."""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from core import ui
from data import changelog
from handlers import features_v1, relationships


class FakeMarkup:
    def __init__(self):
        self.rows = []

    def row(self, *buttons):
        self.rows.append(list(buttons))

    def add(self, *buttons):
        self.rows.append(list(buttons))


class FakeButton:
    def __init__(self, text, callback_data=None, url=None):
        self.text = text
        self.callback_data = callback_data
        self.url = url


class CoreUIAndChangelogTests(unittest.TestCase):
    def test_progress_bar_and_sparkline_and_card(self):
        self.assertEqual(ui.progress_bar(50, 100, width=10), "▰▰▰▰▰▱▱▱▱▱ 50%")
        self.assertEqual(ui.progress_bar(0, 100, width=4), "▱▱▱▱ 0%")
        self.assertEqual(len(ui.sparkline([10, 20, 15, 30])), 4)
        rendered = ui.card("<b>Title</b>", body=["A", "B"], expandable=["C", "D"], footer="Foot")
        self.assertIn("<blockquote>A\nB</blockquote>", rendered)
        self.assertIn("<blockquote expandable>C\nD</blockquote>", rendered)
        self.assertIn("Foot", rendered)

    def test_changelog_starts_at_v1_0_and_supports_pagination(self):
        self.assertEqual(changelog.CHANGELOG[0]["version"], "1.0")
        text, idx, prev_ver, next_ver = changelog.render_changelog_message(None)
        self.assertIn("v1.1", text)
        self.assertEqual(prev_ver, "1.0")
        self.assertEqual(idx, len(changelog.CHANGELOG) - 1)
        self.assertIsNone(next_ver)

        # Simulate multi-version changelog (1.0 -> 1.4 -> 1.5) to verify button navigation
        fake_log = [
            {"version": "1.0", "date": "01.01", "title": "Start", "added": ["A"], "fixed": []},
            {"version": "1.4", "date": "02.01", "title": "Mid", "added": ["B"], "fixed": ["F1"]},
            {"version": "1.5", "date": "03.01", "title": "Latest", "added": ["C"], "fixed": ["F2"]},
        ]
        with patch.object(changelog, "CHANGELOG", fake_log), patch.object(
            features_v1, "InlineKeyboardMarkup", FakeMarkup, create=True
        ), patch.object(features_v1, "InlineKeyboardButton", FakeButton, create=True):
            t_latest, m_latest = features_v1._build_update_view(None)
            self.assertIn("v1.5", t_latest)
            self.assertEqual(m_latest.rows[0][0].text, "⬅️ Прошлое «1.4»")
            self.assertEqual(m_latest.rows[0][0].callback_data, "v1:upd:1")

            t_mid, m_mid = features_v1._build_update_view(1)
            self.assertIn("v1.4", t_mid)
            self.assertEqual(len(m_mid.rows[0]), 2)
            self.assertEqual(m_mid.rows[0][0].text, "⬅️ Прошлое «1.0»")
            self.assertEqual(m_mid.rows[0][1].text, "Новее «1.5» ➡️")


class FeaturesV1RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.bot = MagicMock()
        self.state = {
            "economy": {},
            "relationships": {"pairs": {}, "users": {}, "pending": {}, "history": [], "family_invites": {}, "family_members": {}},
            "guilds": {},
            "chat_daily_stats": {},
            "settings": {},
        }
        self.econs = {}

    def _get_econ(self, uid, name="", username=None):
        uid = int(uid)
        if uid not in self.econs:
            self.econs[uid] = {
                "balance": 10_000,
                "bank_deposit": 2_000,
                "bonus_streak": 2,
                "achievements": ["first_step"],
                "businesses": [],
                "miners": [],
                "reputation": 0,
            }
        self.state["economy"][str(uid)] = self.econs[uid]
        return self.econs[uid]

    def _adjust(self, econ, delta):
        econ["balance"] = int(econ.get("balance", 0)) + int(delta)

    def _patch_ctx(self):
        import threading
        return patch.multiple(
            features_v1,
            bot=self.bot,
            db=self.state,
            db_lock=threading.RLock(),
            mark_dirty=lambda: None,
            can_process_user_message=lambda _m: True,
            get_user_econ=self._get_econ,
            _adjust_balance=self._adjust,
            make_link=lambda _c, name, _u, ping=False: f"<b>{name}</b>",
            InlineKeyboardMarkup=FakeMarkup,
            InlineKeyboardButton=FakeButton,
            ACHIEVEMENTS={"first_step": {"title": "🌟 Первый шаг", "desc": "Начать путь", "reward": 100}},
            get_chat_settings=lambda cid: self.state["settings"].setdefault(str(cid), {}),
            can_admin_action=lambda _c, _u, _a: True,
            add_account_exp=lambda uid, name, amt, username=None, source="": self.econs[int(uid)].__setitem__("exp", self.econs[int(uid)].get("exp", 0) + amt),
            create=True,
        )

    def test_help_tabs_render_and_switch(self):
        with self._patch_ctx():
            text, markup = features_v1._build_help_view("rel")
            self.assertIn("Отношения", text)
            self.assertGreaterEqual(len(markup.rows), 2)

    def test_reputation_and_anti_abuse_cooldown(self):
        features_v1._REP_COOLDOWNS.clear()
        msg = SimpleNamespace(
            chat=SimpleNamespace(id=-100, type="supergroup"),
            from_user=SimpleNamespace(id=101, first_name="Alice", last_name="", username="alice"),
            reply_to_message=SimpleNamespace(from_user=SimpleNamespace(id=202, first_name="Bob", last_name="", username="bob", is_bot=False)),
        )
        with self._patch_ctx():
            features_v1.cmd_rep(msg)
            self.assertEqual(self.econs[202]["reputation"], 1)
            # Second rep immediately should be blocked by 6h cooldown
            features_v1.cmd_rep(msg)
            self.assertEqual(self.econs[202]["reputation"], 1)
            self.assertIn("уже благодарил", self.bot.reply_to.call_args.args[1].lower())

    def test_pvp_duel_accept_transfers_bet_and_logs_receipt(self):
        features_v1._ACTIVE_DUELS.clear()
        msg = SimpleNamespace(
            chat=SimpleNamespace(id=-100, type="supergroup"),
            from_user=SimpleNamespace(id=101, first_name="Alice", last_name="", username="alice"),
            reply_to_message=SimpleNamespace(from_user=SimpleNamespace(id=202, first_name="Bob", last_name="", username="bob", is_bot=False)),
        )
        with self._patch_ctx():
            features_v1.cmd_duel(msg, "500")
            self.assertEqual(len(features_v1._ACTIVE_DUELS), 1)
            duel_id = next(iter(features_v1._ACTIVE_DUELS))
            call = SimpleNamespace(
                id="cb1",
                data=f"v1:duel:acc:{duel_id}",
                from_user=SimpleNamespace(id=202, first_name="Bob", last_name="", username="bob"),
                message=SimpleNamespace(chat=SimpleNamespace(id=-100), message_id=10),
            )
            features_v1.handle_v1_callbacks(call)
            total_after = self.econs[101]["balance"] + self.econs[202]["balance"]
            self.assertEqual(total_after, 20_000)
            self.assertNotEqual(self.econs[101]["balance"], 10_000)
            receipt = features_v1._build_receipt_text(101, "Alice")
            self.assertIn("Финансовый чек", receipt)

    def test_heist_join_and_resolve_success_and_jail(self):
        features_v1._ACTIVE_HEISTS.clear()
        features_v1._HEIST_COOLDOWNS.clear()
        msg = SimpleNamespace(
            chat=SimpleNamespace(id=-100, type="supergroup"),
            from_user=SimpleNamespace(id=101, first_name="Alice", last_name="", username="alice"),
        )
        with self._patch_ctx():
            features_v1.cmd_heist(msg)
            heist_id = next(iter(features_v1._ACTIVE_HEISTS))
            join_call = SimpleNamespace(
                id="cb_j",
                data=f"v1:heist:join:{heist_id}",
                from_user=SimpleNamespace(id=202, first_name="Bob", last_name="", username="bob"),
                message=SimpleNamespace(chat=SimpleNamespace(id=-100), message_id=11),
            )
            features_v1.handle_v1_callbacks(join_call)
            self.assertEqual(len(features_v1._ACTIVE_HEISTS[heist_id]["members"]), 2)

            go_call = SimpleNamespace(
                id="cb_g",
                data=f"v1:heist:go:{heist_id}",
                from_user=SimpleNamespace(id=101, first_name="Alice", last_name="", username="alice"),
                message=SimpleNamespace(chat=SimpleNamespace(id=-100), message_id=11),
            )
            with patch.object(features_v1.random, "randint", return_value=99):  # force failure -> jail
                features_v1.handle_v1_callbacks(go_call)
            self.assertGreater(self.econs[101].get("jail_until", 0), 0)
            self.assertGreater(self.econs[202].get("jail_until", 0), 0)

    def test_badge_selection_and_notifications_and_merchant(self):
        with self._patch_ctx():
            call_set = SimpleNamespace(
                id="cb_b",
                data="v1:badge:set:101:first_step",
                from_user=SimpleNamespace(id=101, first_name="Alice", last_name="", username="alice"),
                message=SimpleNamespace(chat=SimpleNamespace(id=-100), message_id=12),
            )
            features_v1.handle_v1_callbacks(call_set)
            self.assertEqual(self.econs[101]["active_badge"], "first_step")
            self.assertEqual(ui.badge_prefix(self.econs[101], {"first_step": {"title": "🌟 Первый шаг"}}), "🌟 ")

            msg = SimpleNamespace(
                chat=SimpleNamespace(id=-100, type="supergroup"),
                from_user=SimpleNamespace(id=101, first_name="Alice", last_name="", username="alice"),
            )
            features_v1.cmd_notifications(msg, "вкл")
            self.assertTrue(self.econs[101]["dm_notifications"])

            buy_call = SimpleNamespace(
                id="cb_m",
                data="v1:merch:buy:101:0",
                from_user=SimpleNamespace(id=101, first_name="Alice", last_name="", username="alice"),
                message=SimpleNamespace(chat=SimpleNamespace(id=-100), message_id=13),
            )
            features_v1.handle_v1_callbacks(buy_call)
            self.assertEqual(self.econs[101]["balance"], 6500)
            self.assertEqual(self.econs[101]["exp"], 250)

    def test_relationship_pair_streak_milestone(self):
        pair = {"users": [101, 202], "petals": 0, "earned_total": 0, "streak": 2, "last_streak_date": "2026-11-22"}
        with patch.object(relationships, "_today", return_value="2026-11-23"), patch.object(
            relationships, "datetime"
        ) as fake_dt, patch.object(relationships, "mark_dirty", lambda: None, create=True):
            from datetime import date
            fake_dt.now.return_value.date.return_value = date(2026, 11, 23)
            streak, bonus = relationships._update_pair_streak(pair)
        self.assertEqual(streak, 3)
        self.assertEqual(bonus, 10)
        self.assertEqual(pair["petals"], 10)



    def test_dot_otn_condom_toggle_and_sex_chance(self):
        now = 1_900_000_000.0
        pair_id = "101:202"
        pair = {
            "id": pair_id, "users": [101, 202], "names": {"101": "Alice", "202": "Bob"},
            "started_at": now, "petals": 0, "earned_total": 0, "level": 1,
            "cooldowns": {}, "children": [], "house": None, "last_house_income_at": now,
            "gifts": [], "condom_enabled": False, "family_plan": None,
        }
        state = {"relationships": {"pairs": {pair_id: pair}, "users": {"101": pair_id, "202": pair_id}, "pending": {}, "history": [], "family_invites": {}, "family_members": {}}}
        replies = []
        msg_condom = SimpleNamespace(
            text=".отн презик", message_id=1,
            from_user=SimpleNamespace(id=101, first_name="Alice", last_name="", username="alice"),
            chat=SimpleNamespace(id=-100),
        )
        with patch.object(relationships, "db", state, create=True), patch.object(
            relationships.time, "time", return_value=now
        ), patch.object(relationships, "mark_dirty", lambda: None, create=True), patch.object(
            relationships, "can_process_user_message", return_value=True, create=True
        ), patch.object(relationships, "_reply", lambda _m, text, **kw: replies.append(text)):
            # Dot-prefix .отн must be ignored (no conflict with Celestiana)
            relationships.handle_relationship_commands(msg_condom)
            self.assertFalse(pair["condom_enabled"])
            # Plain отн презик toggles ON and OFF
            msg_condom.text = "отн презик"
            relationships.handle_relationship_commands(msg_condom)
            self.assertTrue(pair["condom_enabled"])
            relationships.handle_relationship_commands(msg_condom)
            self.assertFalse(pair["condom_enabled"])
            # Resolve sex with condom OFF and forced 40% trigger (<0.40)
            with patch.object(relationships.random, "random", return_value=0.10):
                res = relationships._resolve_sex_action(msg_condom, pair, 202)
            self.assertIn("таймер", res.lower())
            self.assertIsNotNone(pair["family_plan"])
            self.assertEqual(pair["family_plan"]["status"], "active")
            self.assertEqual(pair["petals"], 15)

    def test_boobs_biometry_and_cooldown(self):
        msg = SimpleNamespace(
            chat=SimpleNamespace(id=-100, type="supergroup"),
            from_user=SimpleNamespace(id=101, first_name="Alice", last_name="", username="alice"),
        )
        with self._patch_ctx():
            features_v1.cmd_boobs(msg)
            self.assertIn("boobs_size", self.econs[101])
            first_size = self.econs[101]["boobs_size"]
            # Immediate second call hits 20-minute cooldown
            features_v1.cmd_boobs(msg)
            self.assertEqual(self.econs[101]["boobs_size"], first_size)
            self.assertIn("раз в 20 минут", self.bot.reply_to.call_args.args[1].lower())


if __name__ == "__main__":
    unittest.main()
