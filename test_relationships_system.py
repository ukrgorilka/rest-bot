import ast
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from handlers import relationships, moderation


class RelationshipLevelTests(unittest.TestCase):
    def test_second_level_starts_at_100_lifetime_petals(self):
        self.assertEqual(relationships._level(0), 1)
        self.assertEqual(relationships._level(99), 1)
        self.assertEqual(relationships._level(100), 2)
        self.assertEqual(relationships._level(250), 3)
        self.assertEqual(relationships._level(1500), 7)

    def test_spendable_balance_does_not_drive_level_thresholds(self):
        # The helper uses lifetime earnings only; a purchase changes only `petals`.
        pair = {"petals": 5, "earned_total": 120, "level": 2}
        self.assertEqual(relationships._level(pair["earned_total"]), 2)

    def test_compliment_and_flowers_rewards_and_unlocks(self):
        self.assertEqual(relationships.ACTIONS["комплимент"]["reward"], 15)
        self.assertEqual(relationships.ACTIONS["подарить цветы"]["level"], 2)
        self.assertEqual(relationships.ACTIONS["подарить цветы"]["reward"], 30)
        self.assertGreater(
            relationships.ACTIONS["подарить цветы"]["cooldown"],
            relationships.ACTIONS["комплимент"]["cooldown"],
        )


class RelationshipGifRoutingTests(unittest.TestCase):
    def test_pair_categories_follow_both_partners_genders(self):
        gender_map = {1: "male", 2: "female"}
        with patch.object(
            relationships, "get_user_econ", create=True,
            side_effect=lambda user_id=None, **kwargs: {
                "relationship_gender": gender_map.get(int(user_id))
            },
        ):
            self.assertEqual(relationships._pair_type({"users": [1, 2]}), "male_female")
            gender_map[2] = "male"
            self.assertEqual(relationships._pair_type({"users": [1, 2]}), "male_male")
            gender_map[1] = "female"
            gender_map[2] = "female"
            self.assertEqual(relationships._pair_type({"users": [1, 2]}), "female_female")
            gender_map[2] = None
            self.assertEqual(relationships._pair_type({"users": [1, 2]}), "generic")

    def test_old_marriage_store_is_not_used(self):
        source = Path("handlers/relationships.py").read_text(encoding="utf-8")
        self.assertIn('db.get("relationships")', source)
        self.assertNotIn("get('marriage')", source)


class RelationshipMediaTests(unittest.TestCase):
    def test_page_url_is_sent_as_clickable_preview(self):
        class Chat:
            id = -100123
        class Message:
            chat = Chat()
            message_id = 77
        fake_bot = unittest.mock.Mock()
        with patch.object(relationships, "bot", fake_bot, create=True):
            relationships._send_action_media(
                Message(),
                {"url": "https://tenor.com/view/example", "mode": "preview"},
                "💐 Подарок",
            )
        fake_bot.send_message.assert_called_once()
        self.assertFalse(fake_bot.send_message.call_args.kwargs["disable_web_page_preview"])
        self.assertIn("https://tenor.com/view/example", fake_bot.send_message.call_args.args[1])
        fake_bot.send_animation.assert_not_called()

    def test_preview_send_failure_uses_the_valid_direct_gif_fallback(self):
        class Chat:
            id = -100123
        class Message:
            chat = Chat()
            message_id = 77
        fake_bot = unittest.mock.Mock()
        fake_bot.send_message.side_effect = RuntimeError("preview endpoint unavailable")
        with patch.object(relationships, "bot", fake_bot, create=True):
            relationships._send_action_media(
                Message(),
                {"url": "https://tenor.com/view/example", "mode": "preview",
                 "fallback_media_url": "https://media1.tenor.com/m/demo/demo.gif"},
                "🫂 Объятие",
            )
        fake_bot.send_animation.assert_called_once_with(
            -100123,
            "https://media1.tenor.com/m/demo/demo.gif",
            caption="🫂 Объятие",
            parse_mode="HTML",
            reply_to_message_id=77,
        )

    def test_direct_gif_url_is_sent_as_animation(self):
        class Chat:
            id = -100123
        class Message:
            chat = Chat()
            message_id = 77
        fake_bot = unittest.mock.Mock()
        with patch.object(relationships, "bot", fake_bot, create=True):
            relationships._send_action_media(Message(), "https://cdn.example/gif.mp4", "🫂 Объятие")
        fake_bot.send_animation.assert_called_once_with(
            -100123,
            "https://cdn.example/gif.mp4",
            caption="🫂 Объятие",
            parse_mode="HTML",
            reply_to_message_id=77,
        )
        fake_bot.send_message.assert_not_called()


class RelationshipPersistenceHardeningTests(unittest.TestCase):
    def test_store_repairs_corrupt_root_shapes_and_marks_database_dirty(self):
        dirty = []
        state = {"relationships": {"pairs": [], "users": None, "pending": {}, "history": {}}}
        with patch.object(relationships, "db", state, create=True), patch.object(
            relationships, "mark_dirty", lambda: dirty.append(True), create=True
        ):
            root = relationships._store()
        self.assertIsInstance(root["pairs"], dict)
        self.assertIsInstance(root["users"], dict)
        self.assertIsInstance(root["pending"], dict)
        self.assertIsInstance(root["history"], list)
        self.assertTrue(dirty)

    def test_pair_normalization_repairs_bad_optional_values(self):
        pair = {
            "users": [1, 2], "petals": "broken", "earned_total": float("nan"),
            "cooldowns": "bad", "children": [{"name": "Kid", "happiness": 500}],
            "house": [], "gifts": "bad", "daily_task": {"kind": "unknown"},
        }
        dirty = []
        with patch.object(relationships, "mark_dirty", lambda: dirty.append(True), create=True):
            relationships._normalize_pair("1:2", pair)
        self.assertEqual(pair["petals"], 0)
        self.assertEqual(pair["earned_total"], 0)
        self.assertEqual(pair["level"], 1)
        self.assertEqual(pair["cooldowns"], {})
        self.assertEqual(pair["children"][0]["happiness"], 100)
        self.assertIsNone(pair["house"])
        self.assertEqual(pair["gifts"], [])
        self.assertIsNone(pair["daily_task"])
        self.assertTrue(dirty)

    def test_house_income_marks_dirty_even_when_triggered_by_profile_read(self):
        now = 2_000_000.0
        pair = {"house": "комната", "last_house_income_at": now - 7200, "petals": 0, "earned_total": 0}
        dirty = []
        def credit(target, amount):
            target["petals"] = target.get("petals", 0) + amount
            target["earned_total"] = target.get("earned_total", 0) + amount
        with patch.object(relationships.time, "time", return_value=now), patch.object(
            relationships, "_credit", side_effect=credit
        ), patch.object(relationships, "mark_dirty", lambda: dirty.append(True), create=True):
            earned = relationships._calculate_house_income(pair)
        self.assertEqual(earned, 2)
        self.assertEqual(pair["petals"], 2)
        self.assertTrue(dirty)

    def test_breakup_requires_confirmation_and_archives_shared_assets(self):
        pair_id = "101:202"
        pair = {
            "id": pair_id, "users": [101, 202], "names": {"101": "One", "202": "Two"},
            "started_at": 1_900_000_000, "petals": 250, "earned_total": 500, "level": 3,
            "cooldowns": {}, "children": [{"id": 1, "name": "Mira", "born_at": 1_900_000_000, "happiness": 80, "last_care_at": 0}],
            "house": "домик", "last_house_income_at": 1_900_000_000, "gifts": [{"name": "Розы", "by": 101, "at": 1_900_000_000}],
        }
        state = {"relationships": {"pairs": {pair_id: pair}, "users": {"101": pair_id, "202": pair_id}, "pending": {}, "history": []}}
        message = SimpleNamespace()
        replies = []
        with patch.object(relationships, "db", state, create=True), patch.object(
            relationships, "mark_dirty", lambda: None, create=True
        ), patch.object(relationships, "_reply", lambda _message, text: replies.append(text)):
            relationships._end_relationship(message, 101, confirm=False)
            self.assertIn(pair_id, state["relationships"]["pairs"])
            self.assertIn("подтверди", replies[-1].lower())
            relationships._end_relationship(message, 101, confirm=True)
        root = state["relationships"]
        self.assertNotIn(pair_id, root["pairs"])
        self.assertNotIn("101", root["users"])
        self.assertNotIn("202", root["users"])
        self.assertEqual(len(root["history"]), 1)
        archived = root["history"][0]
        self.assertEqual(archived["petals"], 250)
        self.assertEqual(archived["children"][0]["name"], "Mira")
        self.assertEqual(archived["house"], "домик")

    def test_future_dated_or_expired_proposals_are_not_accepted(self):
        now = 2_100_000.0
        state = {"relationships": {"pairs": {}, "users": {}, "pending": {
            "202": {"from_id": 101, "to_id": 202, "created_at": now + 600}
        }, "history": []}}
        message = SimpleNamespace(chat=SimpleNamespace(id=-100))
        replies = []
        with patch.object(relationships, "db", state, create=True), patch.object(
            relationships.time, "time", return_value=now
        ), patch.object(relationships, "mark_dirty", lambda: None, create=True), patch.object(
            relationships, "_reply", lambda _message, text: replies.append(text)
        ):
            relationships._accept_proposal(message, 202, "User")
        self.assertFalse(state["relationships"]["pending"])
        self.assertFalse(state["relationships"]["pairs"])
        self.assertIn("нет действующего", replies[-1].lower())


class RelationshipMediaValidationTests(unittest.TestCase):
    def test_non_http_links_are_rejected_as_media(self):
        class Chat:
            id = -100123
        class Message:
            chat = Chat()
            message_id = 77
        fake_bot = unittest.mock.Mock()
        with patch.object(relationships, "bot", fake_bot, create=True):
            with self.assertRaises(ValueError):
                relationships._send_action_media(Message(), {"url": "javascript:alert(1)", "mode": "preview"}, "test")
        fake_bot.send_message.assert_not_called()
        fake_bot.send_animation.assert_not_called()

    def test_action_list_displays_exact_multiword_compliment_command(self):
        text = relationships._actions_list({"earned_total": 0}, 101)
        self.assertIn("отн сделать комплимент", text)
        self.assertNotIn("отн комплимент</code>", text)


class RoutingAndModerationGuardTests(unittest.TestCase):
    def test_commands_for_other_bots_are_detected(self):
        source = Path("newfile.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_is_command_addressed_to_other_bot")
        ctx = {"re": __import__("re"), "get_cached_bot_username": lambda: "my_own_bot"}
        exec(compile(ast.Module(body=[node], type_ignores=[]), "newfile.py", "exec"), ctx)
        predicate = ctx["_is_command_addressed_to_other_bot"]
        msg = lambda text: SimpleNamespace(text=text)
        self.assertTrue(predicate(msg("/menu@garemanine")))
        self.assertFalse(predicate(msg("/menu@my_own_bot")))
        self.assertFalse(predicate(msg("/menu")))

    @staticmethod
    def _moderation_gate(settings, bot_can_restrict):
        source = Path("newfile.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_moderation_system_available")
        ctx = {
            "get_chat_settings": lambda _chat_id: settings,
            "_bot_can_restrict": lambda _chat_id: bot_can_restrict,
        }
        exec(compile(ast.Module(body=[node], type_ignores=[]), "newfile.py", "exec"), ctx)
        return ctx["_moderation_system_available"](-100123)

    def test_moderation_gate_is_silent_when_admin_actions_are_disabled(self):
        self.assertFalse(self._moderation_gate({"admin_functions_enabled": False}, True))

    def test_moderation_gate_is_silent_when_bot_lacks_telegram_rights(self):
        self.assertFalse(self._moderation_gate({"admin_functions_enabled": True}, False))

class RelationshipCommandFlowTests(unittest.TestCase):
    class Bot:
        def __init__(self):
            self.replies = []
        def reply_to(self, message, text, **kwargs):
            self.replies.append((text, kwargs))

    def test_plain_text_compliment_command_rewards_shared_pair_and_obeys_pair_cooldown(self):
        pair_id = "101:202"
        pair = {
            "id": pair_id, "users": [101, 202], "names": {"101": "One", "202": "Two"},
            "started_at": 1_900_000_000, "petals": 0, "earned_total": 0, "level": 1,
            "cooldowns": {}, "children": [], "house": None, "last_house_income_at": 1_900_000_000,
            "gifts": [], "daily_task": None,
        }
        state = {"relationships": {"pairs": {pair_id: pair}, "users": {"101": pair_id, "202": pair_id}, "pending": {}, "history": []}}
        fake_bot = self.Bot()
        dirty = []
        message = SimpleNamespace(
            text="отн сделать комплимент", message_id=5,
            from_user=SimpleNamespace(id=101, first_name="One", last_name="", username="one"),
            chat=SimpleNamespace(id=-100123),
        )
        user_names = {101: "One", 202: "Two"}
        with patch.object(relationships, "db", state, create=True), patch.object(
            relationships, "bot", fake_bot, create=True
        ), patch.object(relationships, "mark_dirty", lambda: dirty.append(True), create=True), patch.object(
            relationships, "can_process_user_message", return_value=True, create=True
        ), patch.object(
            relationships, "get_user_econ", side_effect=lambda user_id=None, **_kw: {"display_name": user_names.get(int(user_id), "User")}, create=True
        ), patch.object(relationships, "_get_gif", return_value=None):
            relationships.handle_relationship_commands(message)
            message.text = "отн комплимент"
            relationships.handle_relationship_commands(message)
        self.assertEqual(pair["petals"], 15)
        self.assertEqual(pair["earned_total"], 15)
        self.assertIn("15 лепестков", fake_bot.replies[0][0])
        self.assertIn("перезарядке", fake_bot.replies[-1][0])
        self.assertTrue(dirty)

    def test_accepting_pending_offer_is_rejected_if_sender_already_has_partner(self):
        existing_id = "101:303"
        existing = {
            "id": existing_id, "users": [101, 303], "names": {"101": "One", "303": "Three"},
            "started_at": 1_900_000_000, "petals": 0, "earned_total": 0, "level": 1,
            "cooldowns": {}, "children": [], "house": None, "last_house_income_at": 1_900_000_000,
            "gifts": [], "daily_task": None,
        }
        state = {"relationships": {
            "pairs": {existing_id: existing}, "users": {"101": existing_id, "303": existing_id},
            "pending": {"202": {"from_id": 101, "to_id": 202, "from_name": "One", "created_at": 2_000_000_000}},
            "history": [],
        }}
        replies = []
        with patch.object(relationships, "db", state, create=True), patch.object(
            relationships.time, "time", return_value=2_000_000_010
        ), patch.object(relationships, "mark_dirty", lambda: None, create=True), patch.object(
            relationships, "_reply", lambda _message, text: replies.append(text)
        ):
            relationships._accept_proposal(SimpleNamespace(), 202, "Two")
        self.assertEqual(set(state["relationships"]["pairs"]), {existing_id})
        self.assertNotIn("202", state["relationships"]["users"])
        self.assertIn("состоит в отношениях", replies[-1].lower())


class RelationshipConcurrencyAndProposalTests(unittest.TestCase):
    def test_replies_are_flushed_after_relationship_locks_are_released(self):
        fake_bot = unittest.mock.Mock()
        message = SimpleNamespace()
        with patch.object(relationships, "bot", fake_bot, create=True), patch.object(
            relationships, "db_lock", __import__("threading").RLock(), create=True
        ):
            with relationships._relationship_transaction():
                relationships._reply(message, "queued")
                fake_bot.reply_to.assert_not_called()
            fake_bot.reply_to.assert_called_once_with(
                message, "queued", parse_mode="HTML", disable_web_page_preview=False
            )

    def test_pair_lookup_repairs_a_missing_partner_reverse_index(self):
        pair_id = "101:202"
        pair = {
            "id": pair_id, "users": [101, 202], "names": {"101": "One", "202": "Two"},
            "started_at": 1_900_000_000, "petals": 0, "earned_total": 0,
            "cooldowns": {}, "children": [], "house": None,
        }
        state = {"relationships": {
            "pairs": {pair_id: pair}, "users": {"101": pair_id}, "pending": {}, "history": []
        }}
        with patch.object(relationships, "db", state, create=True), patch.object(
            relationships, "mark_dirty", lambda: None, create=True
        ):
            self.assertIsNotNone(relationships._pair_for(101))
        self.assertEqual(state["relationships"]["users"]["202"], pair_id)

    def test_outgoing_proposal_is_limited_to_one_and_can_be_cancelled(self):
        state = {"relationships": {
            "pairs": {}, "users": {},
            "pending": {"202": {"from_id": 101, "to_id": 202, "created_at": 2_000_000_000}},
            "history": [],
        }}
        replies = []
        message = SimpleNamespace(chat=SimpleNamespace(id=-100))
        with patch.object(relationships, "db", state, create=True), patch.object(
            relationships.time, "time", return_value=2_000_000_010
        ), patch.object(relationships, "mark_dirty", lambda: None, create=True), patch.object(
            relationships, "_resolve_target", return_value=(303, "Three", False)
        ), patch.object(relationships, "_reply", lambda _message, text: replies.append(text)):
            relationships._handle_proposal(message, "@three", 101, "One")
        self.assertNotIn("303", state["relationships"]["pending"])
        self.assertIn("отн отменить", replies[-1].lower())

    def test_malformed_gender_value_falls_back_to_generic(self):
        with patch.object(relationships, "get_user_econ", return_value={"relationship_gender": ["male"]}, create=True):
            self.assertIsNone(relationships._gender(101))
            self.assertEqual(relationships._pair_type({"users": [101, 202]}), "generic")

    def test_media_urls_with_spaces_or_invalid_ports_are_rejected(self):
        self.assertFalse(relationships._valid_media_url("https://tenor.com/view/a b"))
        self.assertFalse(relationships._valid_media_url("https://tenor.com:bad/view/a"))


class BotUsernameRetryTests(unittest.TestCase):
    def test_transient_get_me_failure_does_not_cache_empty_username_forever(self):
        source = Path("newfile.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "get_cached_bot_username")

        class FakeBot:
            def __init__(self):
                self.calls = 0
            def get_me(self):
                self.calls += 1
                if self.calls == 1:
                    raise RuntimeError("temporary Telegram outage")
                return SimpleNamespace(username="My_Bot")

        fake_bot = FakeBot()
        ctx = {"BOT_USERNAME_CACHE": None, "bot": fake_bot}
        exec(compile(ast.Module(body=[node], type_ignores=[]), "newfile.py", "exec"), ctx)
        self.assertIsNone(ctx["get_cached_bot_username"]())
        self.assertEqual(ctx["get_cached_bot_username"](), "my_bot")
        self.assertEqual(fake_bot.calls, 2)


class RelationshipLifecycleTests(unittest.TestCase):
    def test_store_purges_expired_and_malformed_proposals(self):
        now = 2_200_000.0
        state = {"relationships": {
            "pairs": {}, "users": {}, "history": [],
            "pending": {
                "202": {"from_id": 101, "to_id": 202, "created_at": now - relationships.PROPOSAL_TTL_SECONDS - 1},
                "303": {"from_id": 101, "to_id": 999, "created_at": now},
                "404": None,
            },
        }}
        with patch.object(relationships, "db", state, create=True), patch.object(
            relationships.time, "time", return_value=now
        ), patch.object(relationships, "mark_dirty", lambda: None, create=True):
            relationships._store()
        self.assertEqual(state["relationships"]["pending"], {})

    def test_children_profile_shows_age_stage(self):
        now = 1_700_000_000.0
        pair = {"users": [101, 202], "names": {"101": "One", "202": "Two"},
                "started_at": now - 10 * 86400, "petals": 0, "earned_total": 0,
                "house": None, "children": [{"name": "Mira", "born_at": now - 40 * 86400, "happiness": 75}]}
        replies = []
        with patch.object(relationships, "_reply", lambda _message, text: replies.append(text)), patch.object(
            relationships.time, "time", return_value=now
        ):
            relationships._children_command(SimpleNamespace(), pair, 101, "")
        self.assertIn("ребёнок", replies[-1].lower())
        self.assertIn("возраст 40 дн.", replies[-1])



class RelationshipProgressionTests(unittest.TestCase):
    def test_late_levels_each_unlock_a_rewarding_action(self):
        for action_name, expected_level in (
            ("пикник", 5), ("путешествие", 6), ("отпраздновать годовщину", 7)
        ):
            with self.subTest(action=action_name):
                self.assertEqual(relationships.ACTIONS[action_name]["level"], expected_level)
                self.assertGreater(relationships.ACTIONS[action_name]["reward"], 0)

    def test_generic_catalog_has_a_preview_and_media_asset_for_every_action(self):
        import json
        catalog = json.loads(Path("relationships/data/gifs.json").read_text(encoding="utf-8"))
        expected_keys = {value["key"] for value in relationships.ACTIONS.values()}
        self.assertTrue(expected_keys.issubset(set(catalog["generic"])))
        for key in expected_keys:
            with self.subTest(action=key):
                assets = catalog["generic"][key]
                self.assertTrue(assets)
                for asset in assets:
                    self.assertIsInstance(asset, dict)
                    self.assertTrue(asset["preview_url"].startswith("https://tenor.com/view/"))
                    self.assertTrue(asset["media_url"].startswith("https://media1.tenor.com/m/"))
                    self.assertTrue(asset["media_url"].lower().endswith(".gif"))

    def test_pair_specific_collections_match_three_couple_types(self):
        import json
        catalog = json.loads(Path("relationships/data/gifs.json").read_text(encoding="utf-8"))
        expected = {"male_female", "female_female", "male_male"}
        self.assertTrue(expected.issubset(catalog))
        for category in expected:
            with self.subTest(category=category):
                for action in ("kiss", "hug", "cuddle"):
                    self.assertTrue(catalog[category][action])

    def test_catalog_has_at_least_forty_distinct_curated_gifs(self):
        import json
        catalog = json.loads(Path("relationships/data/gifs.json").read_text(encoding="utf-8"))
        media_urls = {
            item["media_url"]
            for category in ("generic", "male_female", "female_female", "male_male")
            for items in catalog[category].values()
            for item in items
        }
        self.assertGreaterEqual(len(media_urls), 40)

    def test_pair_specific_kiss_and_hug_gifs_are_configured(self):
        import json
        catalog = json.loads(Path("relationships/data/gifs.json").read_text(encoding="utf-8"))
        for category in ("male_female", "female_female", "male_male"):
            with self.subTest(category=category):
                for action in ("kiss", "hug", "cuddle"):
                    self.assertTrue(catalog[category][action])


class RelationshipGifModeTests(unittest.TestCase):
    def test_preview_is_default_and_uses_tenor_page(self):
        asset = {
            "preview_url": "https://tenor.com/view/demo-gif-123",
            "media_url": "https://media1.tenor.com/m/demo/demo.gif",
        }
        catalog = {"male_female": {"hug": [asset]}, "generic": {}}
        with patch.object(relationships, "_load_gifs", return_value=catalog), patch.object(
            relationships, "_pair_type", return_value="male_female"
        ), patch.object(relationships.random, "choice", side_effect=lambda items: items[0]):
            result = relationships._get_gif("hug", {"users": [1, 2]})
        self.assertEqual(result, {
            "url": asset["preview_url"], "mode": "preview",
            "fallback_media_url": asset["media_url"],
        })

    def test_media_mode_uses_the_direct_gif_file(self):
        asset = {
            "preview_url": "https://tenor.com/view/demo-gif-123",
            "media_url": "https://media1.tenor.com/m/demo/demo.gif",
        }
        catalog = {"male_female": {"hug": [asset]}, "generic": {}}
        with patch.object(relationships, "_load_gifs", return_value=catalog), patch.object(
            relationships, "_pair_type", return_value="male_female"
        ), patch.object(relationships.random, "choice", side_effect=lambda items: items[0]):
            result = relationships._get_gif("hug", {"users": [1, 2], "gif_mode": "media"})
        self.assertEqual(result, {"url": asset["media_url"], "mode": "media"})


class RelationshipFamilyPlanningTests(unittest.TestCase):
    def test_family_plan_requires_both_partners_and_runs_exactly_forty_hours(self):
        now = 1_700_000_000.0
        pair = {"users": [101, 202], "children": [], "petals": 100, "family_plan": None}
        replies = []
        message = SimpleNamespace()
        with patch.object(relationships.time, "time", return_value=now), patch.object(
            relationships, "mark_dirty", lambda: None, create=True
        ), patch.object(relationships, "_reply", lambda _message, text: replies.append(text)):
            relationships._family_plan_command(message, pair, 101, "планировать ребёнка")
            self.assertEqual(pair["family_plan"]["status"], "pending")
            relationships._family_plan_command(message, pair, 101, "планирование принять")
            self.assertEqual(pair["family_plan"]["status"], "pending")
            relationships._family_plan_command(message, pair, 202, "планирование принять")
        plan = pair["family_plan"]
        self.assertEqual(plan["status"], "active")
        self.assertEqual(plan["due_at"] - plan["started_at"], 40 * 60 * 60)
        self.assertIn("второй партнёр", replies[1].lower())

    def test_family_invitation_needs_target_acceptance_and_can_be_left(self):
        now = 1_700_000_000.0
        pair_id = "101:202"
        pair = {"id": pair_id, "users": [101, 202], "names": {"101": "One", "202": "Two"},
                "started_at": now, "petals": 0, "earned_total": 0, "children": [],
                "house": None, "last_house_income_at": now, "gifts": [], "cooldowns": {}}
        state = {"relationships": {
            "pairs": {pair_id: pair}, "users": {"101": pair_id, "202": pair_id},
            "pending": {}, "history": [], "family_invites": {}, "family_members": {},
        }}
        replies = []
        message = SimpleNamespace(from_user=SimpleNamespace(first_name="NewMember"))
        with patch.object(relationships, "db", state, create=True), patch.object(
            relationships, "time", relationships.time, create=True
        ), patch.object(relationships.time, "time", return_value=now), patch.object(
            relationships, "mark_dirty", lambda: None, create=True
        ), patch.object(relationships, "_resolve_target", return_value=(303, "NewMember", False)), patch.object(
            relationships, "_reply", lambda _message, text: replies.append(text)
        ):
            relationships._invite_family_member(message, pair, 101, "@newmember")
            self.assertEqual(pair["children"], [])
            self.assertIn("303", state["relationships"]["family_invites"])
            relationships._respond_family_invite(message, 303, accept=True)
            self.assertEqual(len(pair["children"]), 1)
            self.assertEqual(state["relationships"]["family_members"]["303"], pair_id)
            relationships._leave_family(message, 303)
        self.assertEqual(pair["children"], [])
        self.assertNotIn("303", state["relationships"]["family_members"])
        self.assertIn("добровольно", replies[1].lower())

    def test_game_protection_blocks_new_family_plan(self):
        now = 1_700_000_000.0
        pair = {"users": [101, 202], "children": [], "petals": 80, "family_plan": None, "protection_until": 0}
        replies = []
        with patch.object(relationships.time, "time", return_value=now), patch.object(
            relationships, "mark_dirty", lambda: None, create=True
        ), patch.object(relationships, "_reply", lambda _message, text: replies.append(text)):
            relationships._protection_command(SimpleNamespace(), pair, "защита купить")
            relationships._family_plan_command(SimpleNamespace(), pair, 101, "планировать ребёнка")
        self.assertEqual(pair["petals"], 40)
        self.assertGreater(pair["protection_until"], now)
        self.assertIsNone(pair["family_plan"])
        self.assertIn("защита активна", replies[-1].lower())

    def test_birth_can_be_completed_only_after_timer_is_due(self):
        now = 1_700_000_000.0
        pair = {
            "users": [101, 202], "children": [], "petals": 100,
            "family_plan": {"status": "active", "started_at": now - 40 * 3600,
                            "due_at": now, "child_name": "Мира"},
        }
        replies = []
        with patch.object(relationships.time, "time", return_value=now), patch.object(
            relationships, "mark_dirty", lambda: None, create=True
        ), patch.object(relationships, "_reply", lambda _message, text: replies.append(text)):
            relationships._children_command(SimpleNamespace(), pair, 101, "родить")
        self.assertEqual(len(pair["children"]), 1)
        self.assertEqual(pair["children"][0]["name"], "Мира")
        self.assertEqual(pair["petals"], 20)
        self.assertIsNone(pair["family_plan"])


if __name__ == "__main__":
    unittest.main()
