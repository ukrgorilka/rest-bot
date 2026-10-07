"""Runtime-level regression checks for Telegram callback and business flows.

These tests deliberately avoid the real Telegram/Neon services. They execute the
actual callback handler with lightweight fakes so static string checks cannot mask
broken callback parsing, missing acknowledgements, or money-state rollbacks.
"""
from __future__ import annotations

import ast
import copy
import importlib
from pathlib import Path
import threading
import time
from types import SimpleNamespace


callbacks = importlib.import_module("handlers.callbacks")


class FakeBot:
    def __init__(self):
        self.answers = []
        self.edits = []
        self.sent = []
        self.deleted = []

    def answer_callback_query(self, call_id, text=None, **kwargs):
        self.answers.append((str(call_id), text, kwargs))
        return True

    def edit_message_text(self, text, **kwargs):
        self.edits.append((text, kwargs))
        return True

    def send_message(self, chat_id, text, **kwargs):
        self.sent.append((chat_id, text, kwargs))
        return SimpleNamespace(message_id=999)

    def delete_message(self, chat_id, message_id):
        self.deleted.append((chat_id, message_id))
        return True


class FakeMarkup:
    def __init__(self, *args, **kwargs):
        self.items = []

    def add(self, *buttons):
        self.items.extend(buttons)


class FakeButton:
    def __init__(self, text, callback_data=None, **kwargs):
        self.text = text
        self.callback_data = callback_data



def fake_call(data, user_id=123):
    return SimpleNamespace(
        id=f"cb-{time.time_ns()}",
        data=data,
        from_user=SimpleNamespace(id=user_id, username="tester", first_name="Test", last_name=""),
        message=SimpleNamespace(chat=SimpleNamespace(id=456), message_id=789),
    )


def configure_common(bot, econ, *, active_c_mines=None, active_bj_games=None):
    callbacks._inject({
        "bot": bot,
        "db": {"bot_active": True},
        "time": time,
        "_bot_output_language": lambda chat_id, user_id: "ru",
        "_CALLBACK_LANG_LOCK": threading.RLock(),
        "_CALLBACK_LANG_BY_ID": {},
        "_LOCALE_CONTEXT": SimpleNamespace(user_id=None, chat_id=None),
        "is_chat_banned": lambda chat_id: False,
        "user_flood_history": {},
        "is_chat_owner": lambda chat_id, user_id: False,
        "is_admin": lambda chat_id, user_id: False,
        "get_user_econ": lambda user_id, user_name, username=None: econ,
        "username": "tester",
        "_migrate_legacy_businesses": lambda econ: False,
        "mark_dirty": lambda: None,
        "critical_save": lambda *args, **kwargs: True,
        "_adjust_balance": lambda econ, amount: econ.__setitem__("balance", int(econ.get("balance", 0)) + int(amount)),
        "check_achievements": lambda *args, **kwargs: None,
        "_record_business_tx": lambda econ, entry: econ.setdefault("business_transactions", []).append(entry),
        "_delete_message_quietly": lambda chat_id, message_id: bot.delete_message(chat_id, message_id),
        "BUSINESSES": {
            "smoothie_bar": {"name": "🍓 Смуси-бар", "short": "Смуси-бар", "price": 900, "base_income": 10, "upgrade_cost": 650},
            "crypto_farm": {"name": "💻 Крипто-Ферма", "short": "Крипто-Ферма", "price": 18_000, "base_income": 150, "upgrade_cost": 13_000},
        },
        "DONOR_BUSINESSES": {},
        "STARS_COSMETICS": {},
        "InlineKeyboardMarkup": FakeMarkup,
        "InlineKeyboardButton": FakeButton,
        "html": importlib.import_module("html"),
        "_business_catalog": lambda: [(1, "smoothie_bar", {"name": "🍓 Смуси-бар", "short": "Смуси-бар", "price": 900, "base_income": 10, "upgrade_cost": 650}, False), (2, "crypto_farm", {"name": "💻 Крипто-Ферма", "short": "Крипто-Ферма", "price": 18_000, "base_income": 150, "upgrade_cost": 13_000}, False)],
        "_business_by_number": lambda number: (int(number), "smoothie_bar", {}, False),
        "_business_level": lambda econ, b_id: int((econ.get("biz_levels") or {}).get(b_id, 1)),
        "_business_hourly_income": lambda b_id, lvl: 10,
        "_business_pending_amount": lambda econ, b_id, now: 0,
        "_business_purchase_price": lambda econ, b_id: int((econ.get("biz_purchase_price") or {}).get(b_id, 900)),
        "_settle_business_net_profit": lambda econ, b_id, now: (0, 0),
        "render_business_detail": lambda *args, **kwargs: None,
        "render_business_view": lambda *args, **kwargs: None,
        "publish_bot_news": lambda *args, **kwargs: None,
        "CSAPER_DIFFICULTIES": {},
        "active_c_mines": active_c_mines if active_c_mines is not None else {},
        "render_classic_mines_board": lambda game_id: ("board", FakeMarkup()),
        "active_bj_games": active_bj_games if active_bj_games is not None else {},
        "calculate_bj_score": lambda cards: sum(cards),
    })


def assert_callback_answered(bot, call):
    assert any(row[0] == str(call.id) for row in bot.answers), f"callback {call.id} was not acknowledged"


# 1) v0.3 owner suffix is parsed by the generic callback parser exactly once.

econ = {"balance": 2000, "businesses": {}, "biz_levels": {}, "biz_purchase_price": {}}
bot = FakeBot()
configure_common(bot, econ)
call = fake_call("biz_detail_buy:smoothie_bar:123")
callbacks.callback_inline(call)
assert econ["balance"] == 1100, econ
assert "smoothie_bar" in econ["businesses"], econ
assert_callback_answered(bot, call)

# 2) Every early-return callback branch must leave Telegram's loading spinner.
bot = FakeBot()
econ = {"balance": 0}
mines = {}
configure_common(bot, econ, active_c_mines=mines)
call = fake_call("cmmode_missing-game:123")
callbacks.callback_inline(call)
assert_callback_answered(bot, call)

# 3) A classic Mines revealed-cell early return is also acknowledged.
bot = FakeBot()
mines = {"cm_1_1": {"user_id": 123, "finished": False, "mode": "flag", "revealed": {0}, "flags": set(), "cols": 1, "rows": 1}}
configure_common(bot, {"balance": 0}, active_c_mines=mines)
call = fake_call("cmo_cm_1_1_0:123")
callbacks.callback_inline(call)
assert_callback_answered(bot, call)

# 4) Blackjack bust cleanup acknowledges the callback after deleting the game.
bot = FakeBot()
bj = {"game": {"user_id": 123, "finished": False, "deck": [5], "p_cards": [10, 10], "d_cards": [10, 7], "bet": 100}}
configure_common(bot, {"balance": 0}, active_bj_games=bj)
call = fake_call("bj_hit_game:123")
callbacks.callback_inline(call)
assert "game" not in bj
assert_callback_answered(bot, call)

# 5) A failed legacy purchase must restore every money/business field.
econ = {"balance": 20_000, "businesses": {}, "biz_levels": {}, "biz_purchase_price": {}, "biz_last_collect": {}, "biz_income_carry": {}}
bot = FakeBot()
configure_common(bot, econ)
callbacks.critical_save = lambda *args, **kwargs: False
call = fake_call("buy_biz_crypto_farm:123")
callbacks.callback_inline(call)
assert econ["balance"] == 20_000, econ
assert "crypto_farm" not in econ.get("businesses", {}), econ
assert_callback_answered(bot, call)

# 6) Failed legacy upgrade also rolls back the level and money.
econ = {"balance": 50_000, "businesses": {"crypto_farm": time.time()}, "biz_levels": {"crypto_farm": 1}, "biz_purchase_price": {"crypto_farm": 18_000}, "biz_last_collect": {"crypto_farm": time.time() - 10}, "biz_income_carry": {}}
bot = FakeBot()
configure_common(bot, econ)
callbacks.critical_save = lambda *args, **kwargs: False
call = fake_call("upg_biz_crypto_farm:123")
before = copy.deepcopy(econ)
callbacks.callback_inline(call)
assert econ == before, (econ, before)
assert_callback_answered(bot, call)


# 7) Execute the actual business catalog renderer in isolation and verify the
#    user-facing list contains both price and ownership status.
newfile_source = Path("newfile.py").read_text(encoding="utf-8")
newfile_tree = ast.parse(newfile_source)
needed_names = {"BUSINESSES", "DONOR_BUSINESSES", "STARS_COSMETICS"}
helper_names = {"_business_catalog", "_business_user_owns", "_business_stars_price", "_render_business_catalog"}
selected = []
for node in newfile_tree.body:
    if isinstance(node, ast.Assign):
        names = {t.id for t in node.targets if isinstance(t, ast.Name)}
        if names & needed_names:
            selected.append(node)
    elif isinstance(node, ast.FunctionDef) and node.name in helper_names:
        selected.append(node)
ns = {"html": importlib.import_module("html")}
exec(compile(ast.Module(body=selected, type_ignores=[]), "newfile_business_catalog.py", "exec"), ns)

class CatalogBot:
    def __init__(self):
        self.sent = []

    def send_message(self, chat_id, text, **kwargs):
        self.sent.append(text)
        return SimpleNamespace(message_id=1000)

catalog_bot = CatalogBot()
catalog_econ = {"balance": 12345, "businesses": {}}
ns["bot"] = catalog_bot
ns["get_user_econ"] = lambda user_id, user_name: catalog_econ
ns["_migrate_legacy_businesses"] = lambda econ: False
ns["mark_dirty"] = lambda: None
ns["_business_info"] = lambda b_id: ns["BUSINESSES"].get(b_id) or ns["DONOR_BUSINESSES"].get(b_id)
ns["_render_business_catalog"](456, 123, "Test")
rendered = catalog_bot.sent[-1]
assert "900 🪙" in rendered and "❌ Не куплен" in rendered, rendered
catalog_econ["businesses"]["smoothie_bar"] = 1
catalog_bot.sent.clear()
ns["_render_business_catalog"](456, 123, "Test")
rendered = catalog_bot.sent[-1]
assert "900 🪙" in rendered and "✅ Куплен" in rendered, rendered

print("business catalog runtime UX: PASS (price + ownership status)")

print("runtime regressions: PASS (callbacks, business parsing, acknowledgements, rollback)")
