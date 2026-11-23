"""NyaBot v1.0 feature suite: changelog (/update), tabbed /help, daily hub,
collect-all, PvP duels, co-op bank heists, random chat events, chat-of-the-day,
achievement badges, +rep reputation, night merchant, guild weekly goals,
24h financial receipt, opt-in DM notifications, and admin chat toggles.
"""

from __future__ import annotations

import hashlib
import html
import math
import random
import re
import threading
import time
import uuid
from datetime import datetime, timezone

from core.locks import serialize_user_action, serialized_multi_user_action
from core.ui import badge_prefix, card, format_duration, progress_bar, sparkline
from data.changelog import render_changelog_message


HANDLER_NAMES = [
    "cmd_update",
    "cmd_help_menu",
    "cmd_daily_hub",
    "cmd_boobs",
    "handle_v1_callbacks",
]

_V1_LOCK = threading.RLock()
_ACTIVE_DUELS = {}       # duel_id -> dict
_ACTIVE_HEISTS = {}      # heist_id -> dict
_ACTIVE_DROPS = {}       # drop_id -> dict
_ACTIVE_MATH = {}        # chat_id -> dict
_CHAT_MSG_COUNTER = {}   # chat_id -> int
_HEIST_COOLDOWNS = {}    # chat_id -> float
_REP_COOLDOWNS = {}      # (sender_id, target_id) -> float

_HELP_TABS = {
    "econ": (
        "💰 <b>Экономика и работа</b>",
        [
            "• <code>баланс</code> / <code>профиль</code> / <code>чек</code> — кошелёк, банк и сводка за 24ч",
            "• <code>дейли</code> / <code>собрать всё</code> — статус кулдаунов и сбор всего дохода",
            "• <code>работа</code> / <code>учиться</code> / <code>бизнес</code> / <code>майнер</code>",
            "• <code>банк положить 5000</code> / <code>банк снять 5000</code> / <code>кредит</code>",
            "• <code>передать @user 1000</code> — перевод игроку (комиссия 3%)",
            "• <code>биржа</code> / <code>портфель</code> / <code>торговец</code> — акции и ночная лавка",
        ],
    ),
    "games": (
        "🎮 <b>Игры и PvP</b>",
        [
            "• <code>дуэль @user 500</code> — PvP-дуэль на Ня-коины по кнопке",
            "• <code>ограбление</code> — командное ограбление банка (2–4 игрока)",
            "• <code>/games</code> / <code>колесо</code> / <code>мины</code> / <code>краш</code> / <code>блекджек</code>",
            "• <code>сад</code> / <code>кейс</code> / <code>сейф</code> / <code>лотерея</code>",
            "• <code>шар</code> / <code>шанс</code> / <code>детектор</code> / <code>герои дня</code>",
        ],
    ),
    "pets": (
        "🐾 <b>Питомцы и профиль</b>",
        [
            "• <code>питомец</code> / <code>гулять</code> / <code>одежда питомца</code> / <code>бой питомцев</code>",
            "• <code>ачивки</code> / <code>бейдж</code> — достижения и выбор значка в профиль",
            "• <code>инвентарь</code> / <code>магазин</code> / <code>аптека</code> / <code>гараж</code>",
            "• <code>уведомления вкл</code> / <code>выкл</code> — тихие напоминания в ЛС",
        ],
    ),
    "rel": (
        "💞 <b>Отношения (отн)</b>",
        [
            "• <code>отн предложить @user</code> — начать отношения (с кнопками)",
            "• <code>отн профиль</code> / <code>отн топ</code> / <code>отн действия</code>",
            "• <code>отн сделать комплимент</code> / <code>отн задания</code> / <code>отн забрать награду</code>",
            "• <code>отн дом</code> / <code>отн дом улучшить вилла</code> / <code>отн магазин</code>",
            "• <code>отн планировать ребёнка</code> / <code>отн дети</code> / <code>отн гиф</code>",
        ],
    ),
    "clan": (
        "🏛 <b>Гильдии и закон</b>",
        [
            "• <code>/guild</code> / <code>гильдия цель</code> — гильдия и недельная цель с наградой",
            "• <code>шериф</code> / <code>тюрьма</code> / <code>побег</code> / <code>залог</code>",
            "• <code>+реп</code> (ответом) / <code>топ реп</code> — репутация полезных участников",
        ],
    ),
    "chat": (
        "🛡 <b>Чат и администрирование</b>",
        [
            "• <code>чат дня</code> — итоги активности и топ-3 за сегодня",
            "• <code>/update</code> (<code>обнова</code>) — история обновлений бота с v1.0",
            "• <code>автоответы вкл/выкл</code> — реакции бота на слова (для админов)",
            "• <code>ивенты вкл/выкл</code> — случайные сундуки и задачки (для админов)",
            "• <code>автоудаление приветствий вкл/выкл</code> — автоочистка приветствий",
        ],
    ),
}

_MARKET_NEWS = [
    ("🌿 Дефицит кошачьей мяты подстегнул спрос среди инвесторов!", +12),
    ("🚀 Крупный кит скупил полрынка Ня-коинов за один вечер!", +15),
    ("📉 Биржа слегка остывает после вчерашнего ралли — время присмотреться к скидкам.", -7),
    ("⚡ Аналитики ждут волатильный день: удача улыбается смелым трейдерам.", +5),
    ("🐟 В порту задержали партию лосося — пищевые активы штормит.", -5),
    ("✨ Сезонный бум в экономике чата: объёмы торгов растут!", +9),
]


def _inject(ctx):
    for name, value in ctx.items():
        if name not in {"__name__", "__package__", "__loader__", "__spec__", "__cached__", "__builtins__"}:
            globals()[name] = value


def _today_utc():
    return datetime.now(timezone.utc).date().isoformat()


def _iso_week_key():
    iso = datetime.now(timezone.utc).isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _display_name(user):
    if not user:
        return "Пользователь"
    full = f"{getattr(user, 'first_name', '') or ''} {getattr(user, 'last_name', '') or ''}".strip()
    return (full or getattr(user, "username", None) or f"ID:{getattr(user, 'id', 0)}")[:80]


def _mk_markup(rows):
    markup_cls = globals().get("InlineKeyboardMarkup")
    btn_cls = globals().get("InlineKeyboardButton")
    if markup_cls is None or btn_cls is None:
        return None
    markup = markup_cls()
    for row in rows:
        btns = [btn_cls(label, callback_data=cb) for label, cb in row]
        if btns:
            markup.row(*btns)
    return markup


def _safe_edit(call, text, reply_markup=None):
    msg = getattr(call, "message", None)
    if not msg:
        return
    kwargs = {"parse_mode": "HTML", "disable_web_page_preview": True}
    if reply_markup is not None:
        kwargs["reply_markup"] = reply_markup
    try:
        bot.edit_message_text(text, chat_id=msg.chat.id, message_id=msg.message_id, **kwargs)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 1. /update — Changelog viewer starting from v1.0
# ---------------------------------------------------------------------------
def _build_update_view(index=None):
    text, clamped_idx, prev_ver, next_ver = render_changelog_message(index)
    nav_row = []
    if prev_ver is not None:
        nav_row.append((f"⬅️ Прошлое «{prev_ver}»", f"v1:upd:{clamped_idx - 1}"))
    if next_ver is not None:
        nav_row.append((f"Новее «{next_ver}» ➡️", f"v1:upd:{clamped_idx + 1}"))
    markup = _mk_markup([nav_row]) if nav_row else None
    return text, markup


def cmd_update(message):
    if not can_process_user_message(message):
        return
    text, markup = _build_update_view(None)
    kwargs = {"parse_mode": "HTML", "disable_web_page_preview": True}
    if markup is not None:
        kwargs["reply_markup"] = markup
    bot.reply_to(message, text, **kwargs)


# ---------------------------------------------------------------------------
# 2. /help — Tabbed interactive help menu
# ---------------------------------------------------------------------------
def _build_help_view(tab="econ"):
    if tab not in _HELP_TABS:
        tab = "econ"
    title, lines = _HELP_TABS[tab]
    text = card(
        f"📖 <b>Меню команд NyaBot</b> · {title}",
        body=lines,
        footer="Переключай разделы кнопками ниже · История релизов: <code>/update</code>",
    )
    markup = _mk_markup([
        [("💰 Экономика", "v1:help:econ"), ("🎮 Игры", "v1:help:games"), ("🐾 Питомцы", "v1:help:pets")],
        [("💞 Отношения", "v1:help:rel"), ("🏛 Гильдия", "v1:help:clan"), ("🛡 Чат", "v1:help:chat")],
        [("🚀 Обновление v1.0", "v1:upd:latest")],
    ])
    return text, markup


def cmd_help_menu(message):
    if not can_process_user_message(message):
        return
    text, markup = _build_help_view("econ")
    kwargs = {"parse_mode": "HTML", "disable_web_page_preview": True}
    if markup is not None:
        kwargs["reply_markup"] = markup
    bot.reply_to(message, text, **kwargs)


# ---------------------------------------------------------------------------
# 3. Daily Hub (дейли / /daily) & Collect All (собрать всё)
# ---------------------------------------------------------------------------
def _build_daily_hub_text(user_id, user_name, username=None):
    now = time.time()
    econ = get_user_econ(user_id, user_name, username=username)
    lines = []

    # Daily chest/bonus (24h — canonical key: last_streak_time, command: /chest)
    last_bonus = float(econ.get("last_streak_time", 0) or 0)
    rem_bonus = last_bonus + 86400 - now
    lines.append(
        f"{'✅' if rem_bonus <= 0 else '⏳'} <b>Ежедневный сундук</b> — "
        + ("готов! (<code>/chest</code>)" if rem_bonus <= 0 else f"через {format_duration(rem_bonus)}")
    )

    # Work cooldown (canonical key: last_work_time)
    last_work = float(econ.get("last_work_time", 0) or 0)
    rem_work = last_work + 1800 - now
    lines.append(
        f"{'✅' if rem_work <= 0 else '⏳'} <b>Работа</b> — "
        + ("можно на смену (<code>работа</code>)" if rem_work <= 0 else f"через {format_duration(rem_work)}")
    )

    # Businesses & donor businesses (canonical dict structures)
    biz_map = econ.get("businesses") if isinstance(econ.get("businesses"), dict) else {}
    donor_biz = econ.get("donor_businesses") if isinstance(econ.get("donor_businesses"), dict) else {}
    biz_count = len(biz_map) + len(donor_biz)
    if biz_count:
        lines.append(f"🏢 <b>Пассивный доход</b> — предприятий: <b>{biz_count}</b> (<code>собрать всё</code>)")
    else:
        lines.append("🏢 <b>Бизнесы</b> — пока нет (<code>бизнес</code>)")

    # Pet walk (canonical key: econ['last_pet_walk'])
    pet = econ.get("pet")
    if isinstance(pet, dict) and (pet.get("name") or pet.get("id")):
        last_walk = float(econ.get("last_pet_walk", 0) or 0)
        rem_walk = last_walk + 3600 - now
        lines.append(
            f"{'✅' if rem_walk <= 0 else '⏳'} <b>Прогулка с питомцем</b> — "
            + ("готов гулять (<code>гулять</code>)" if rem_walk <= 0 else f"через {format_duration(rem_walk)}")
        )

    # Wheel of fortune (canonical key: last_wheel_time)
    last_wheel = float(econ.get("last_wheel_time", 0) or 0)
    rem_wheel = last_wheel + 86400 - now
    lines.append(
        f"{'✅' if rem_wheel <= 0 else '⏳'} <b>Колесо фортуны</b> — "
        + ("готово (<code>колесо</code>)" if rem_wheel <= 0 else f"через {format_duration(rem_wheel)}")
    )

    # Relationship compliment & daily task
    rel_root = db.get("relationships", {}) if isinstance(db, dict) else {}
    pair_id = rel_root.get("users", {}).get(str(user_id)) if isinstance(rel_root, dict) else None
    pair = rel_root.get("pairs", {}).get(str(pair_id)) if pair_id and isinstance(rel_root.get("pairs"), dict) else None
    if isinstance(pair, dict):
        cd_comp = float(pair.get("cooldowns", {}).get("compliment", 0) or 0) - now
        lines.append(
            f"{'✅' if cd_comp <= 0 else '⏳'} <b>Комплимент паре</b> — "
            + ("готов (<code>отн сделать комплимент</code>)" if cd_comp <= 0 else f"через {format_duration(cd_comp)}")
        )

    badge = badge_prefix(econ, globals().get("ACHIEVEMENTS"))
    text = card(
        f"📋 <b>{badge}Сводка дня</b>",
        body=lines,
        footer="💡 Нажми кнопку ниже, чтобы собрать весь пассивный доход сразу.",
    )
    markup = _mk_markup([
        [("💰 Собрать всё", f"v1:collect:all:{user_id}"), ("🔄 Обновить", f"v1:daily:open:{user_id}")],
    ])
    return text, markup


def cmd_daily_hub(message):
    if not can_process_user_message(message):
        return
    uid = int(message.from_user.id)
    uname = _display_name(message.from_user)
    text, markup = _build_daily_hub_text(uid, uname, username=getattr(message.from_user, "username", None))
    kwargs = {"parse_mode": "HTML"}
    if markup is not None:
        kwargs["reply_markup"] = markup
    bot.reply_to(message, text, **kwargs)


def _perform_collect_all(user_id, user_name, username=None):
    now = time.time()
    biz_income = 0
    miner_income = 0
    house_petals = 0
    changed = False

    with db_lock:
        econ = get_user_econ(user_id, user_name, username=username)

        # Canonical business & crypto_farm collection via collect_business_base_profit
        collector_fn = globals().get("collect_business_base_profit")
        if callable(collector_fn) and (econ.get("businesses") or econ.get("donor_businesses")):
            base_profit = int(collector_fn(econ, now) or 0)
            if base_profit > 0:
                biz_income += base_profit
                changed = True

        total_coins = biz_income + miner_income
        if total_coins > 0:
            _record_money_event(econ, total_coins, "Сбор дохода")

        # Relationship house petals
        rel_root = db.get("relationships", {}) if isinstance(db, dict) else {}
        pair_id = rel_root.get("users", {}).get(str(user_id)) if isinstance(rel_root, dict) else None
        pair = rel_root.get("pairs", {}).get(str(pair_id)) if pair_id and isinstance(rel_root.get("pairs"), dict) else None
        if isinstance(pair, dict) and pair.get("house"):
            try:
                from handlers import relationships as rel_mod
                house_petals = rel_mod._calculate_house_income(pair)
                if house_petals > 0:
                    changed = True
            except Exception:
                pass

        if changed:
            mark_dirty()

    if total_coins > 0:
        _adjust_balance(econ, total_coins)
        mark_dirty()

    lines = []
    if biz_income:
        lines.append(f"🏢 Бизнесы: <b>+{biz_income:,} 🪙</b>")
    if miner_income:
        lines.append(f"⛏ Майнеры: <b>+{miner_income:,} 🪙</b>")
    if house_petals:
        lines.append(f"🏡 Дом пары: <b>+{house_petals:,} лепестков</b>")
    if not lines:
        return card("💰 <b>Сбор дохода</b>", body="Пока нечего собирать — приходи чуть позже!", footer="Статус кулдаунов: <code>дейли</code>")
    return card(
        "💰 <b>Сбор пассивного дохода</b>",
        body=lines + [f"\n💵 Итого монет: <b>+{biz_income + miner_income:,} 🪙</b>"],
        footer="✨ Всё зачислено на баланс!",
    )


def cmd_collect_all(message):
    if not can_process_user_message(message):
        return
    uid = int(message.from_user.id)
    uname = _display_name(message.from_user)
    text = _perform_collect_all(uid, uname, username=getattr(message.from_user, "username", None))
    bot.reply_to(message, text, parse_mode="HTML")


# ---------------------------------------------------------------------------
# 4. PvP Duels (дуэль @user <ставка>)
# ---------------------------------------------------------------------------
def cmd_duel(message, args_text=""):
    if not can_process_user_message(message):
        return
    uid = int(message.from_user.id)
    uname = _display_name(message.from_user)
    chat_id = message.chat.id

    target_id = None
    target_name = None
    bet = 0
    tokens = args_text.strip().split()
    reply = getattr(message, "reply_to_message", None)
    if reply and getattr(reply, "from_user", None):
        target_u = reply.from_user
        if getattr(target_u, "is_bot", False):
            bot.reply_to(message, "❌ Нельзя вызвать бота на дуэль.")
            return
        target_id = int(target_u.id)
        target_name = _display_name(target_u)
        if tokens and tokens[0].isdigit():
            bet = int(tokens[0])
    elif len(tokens) >= 2:
        raw_target, raw_bet = tokens[0], tokens[1]
        if raw_bet.isdigit():
            bet = int(raw_bet)
        target_id, target_name = resolve_user_from_string(chat_id, raw_target)

    if not target_id or bet < 50 or bet > 500_000:
        bot.reply_to(
            message,
            card(
                "⚔️ <b>PvP-дуэль на Ня-коины</b>",
                body="Формат: <code>дуэль @username 500</code> или ответом на сообщение: <code>дуэль 500</code>.\nСтавка: от <b>50</b> до <b>500,000 🪙</b>.",
            ),
            parse_mode="HTML",
        )
        return
    if target_id == uid:
        bot.reply_to(message, "❌ Нельзя вызвать на дуэль самого себя.")
        return

    econ = get_user_econ(uid, uname, username=getattr(message.from_user, "username", None))
    if float(econ.get("jail_until", 0) or 0) > time.time():
        rem_j = float(econ.get("jail_until", 0)) - time.time()
        bot.reply_to(message, f"🚓 Ты сейчас в тюрьме! До освобождения: <b>{format_duration(rem_j)}</b>.", parse_mode="HTML")
        return
    if int(econ.get("balance", 0)) < bet:
        bot.reply_to(message, f"❌ Недостаточно Ня-коинов для ставки {bet:,} 🪙.")
        return

    duel_id = uuid.uuid4().hex[:8]
    now = time.time()
    with _V1_LOCK:
        # Prune expired duels
        for k in [k for k, v in _ACTIVE_DUELS.items() if now - v["created_at"] > 120]:
            _ACTIVE_DUELS.pop(k, None)
        _ACTIVE_DUELS[duel_id] = {
            "id": duel_id,
            "chat_id": chat_id,
            "from_id": uid,
            "from_name": uname,
            "to_id": int(target_id),
            "to_name": str(target_name or f"ID:{target_id}"),
            "bet": bet,
            "created_at": now,
        }

    markup = _mk_markup([
        [("⚔️ Принять вызов", f"v1:duel:acc:{duel_id}"), ("🏳️ Отказаться", f"v1:duel:dec:{duel_id}")],
    ])
    text = card(
        "⚔️ <b>Вызов на дуэль!</b>",
        body=[
            f"👤 {make_link(chat_id, uname, uid, ping=False)} бросает вызов {make_link(chat_id, target_name, target_id, ping=True)}!",
            f"💰 Ставка: <b>{bet:,} 🪙</b> (победитель забирает банк!)",
        ],
        footer="⏳ Вызов действует 2 минуты.",
    )
    bot.reply_to(message, text, parse_mode="HTML", reply_markup=markup)


# ---------------------------------------------------------------------------
# 5. Co-op Bank Heist (ограбление) — links with jail & sheriff
# ---------------------------------------------------------------------------
def cmd_heist(message):
    if not can_process_user_message(message):
        return
    chat_id = message.chat.id
    uid = int(message.from_user.id)
    uname = _display_name(message.from_user)
    now = time.time()

    leader_econ = get_user_econ(uid, uname, username=getattr(message.from_user, "username", None))
    if float(leader_econ.get("jail_until", 0) or 0) > now:
        bot.reply_to(message, f"🚓 Из тюрьмы банк не ограбишь! Осталось: <b>{format_duration(float(leader_econ['jail_until']) - now)}</b>.", parse_mode="HTML")
        return
    with _V1_LOCK:
        cd_until = _HEIST_COOLDOWNS.get(chat_id, 0.0)
        if cd_until > now:
            bot.reply_to(message, f"🚓 Полиция ещё патрулирует район! Следующее ограбление через <b>{format_duration(cd_until - now)}</b>.", parse_mode="HTML")
            return
        for k in [k for k, v in _ACTIVE_HEISTS.items() if now - v["created_at"] > 120]:
            _ACTIVE_HEISTS.pop(k, None)
        heist_id = uuid.uuid4().hex[:8]
        _ACTIVE_HEISTS[heist_id] = {
            "id": heist_id,
            "chat_id": chat_id,
            "leader_id": uid,
            "members": {uid: uname},
            "created_at": now,
            "started": False,
        }

    text = _render_heist_lobby(_ACTIVE_HEISTS[heist_id])
    markup = _mk_markup([
        [("🎭 Вступить в банду", f"v1:heist:join:{heist_id}"), ("🚀 Начать дело", f"v1:heist:go:{heist_id}")],
    ])
    bot.reply_to(message, text, parse_mode="HTML", reply_markup=markup)


def _render_heist_lobby(heist):
    members_text = "\n".join(f"• {html.escape(name)}" for name in heist["members"].values())
    return card(
        "🏦 <b>Сбор банды на ограбление банка!</b>",
        body=[
            f"👥 Участники ({len(heist['members'])}/4):",
            members_text,
            "\n⚠️ При провале вся банда отправится в тюрьму на 5 минут (работают <code>побег</code> и <code>залог</code>).",
        ],
        footer="Нужно от 2 до 4 участников. Лидер может нажать «Начать дело».",
    )


# ---------------------------------------------------------------------------
# 6. Random Chat Events (chest drop / quick math) & Chat of the Day
# ---------------------------------------------------------------------------
def record_chat_activity_and_events(message):
    """Track daily chat messages and periodically trigger random chat events."""
    chat = getattr(message, "chat", None)
    user = getattr(message, "from_user", None)
    if not chat or not user or getattr(chat, "type", "") == "private":
        return
    chat_id = int(chat.id)
    uid = int(user.id)
    uname = _display_name(user)
    today = _today_utc()

    # 1. Check if message solves an active quick-math event
    text_raw = str(getattr(message, "text", "") or "").strip()
    if text_raw and re.fullmatch(r"-?\d+", text_raw):
        solved = None
        with _V1_LOCK:
            ev = _ACTIVE_MATH.get(chat_id)
            if ev and time.time() <= ev["expires_at"] and int(text_raw) == ev["answer"]:
                solved = _ACTIVE_MATH.pop(chat_id, None)
        if solved:
            reward = solved["reward"]
            econ = get_user_econ(uid, uname, username=getattr(user, "username", None))
            _adjust_balance(econ, reward)
            _record_money_event(econ, reward, "Чат-ивент (пример)")
            mark_dirty()
            try:
                bot.reply_to(
                    message,
                    card(
                        "⚡ <b>Верный ответ!</b>",
                        body=f"🏆 {make_link(chat_id, uname, uid, ping=False)} первым решил(а) <code>{solved['expr']} = {solved['answer']}</code> и забрал(а) <b>+{reward:,} 🪙</b>!",
                    ),
                    parse_mode="HTML",
                )
            except Exception:
                pass

    # 2. Record daily chat stats
    with db_lock:
        stats = db.setdefault("chat_daily_stats", {})
        if not isinstance(stats, dict):
            stats = {}
            db["chat_daily_stats"] = stats
        chat_days = stats.setdefault(str(chat_id), {})
        if not isinstance(chat_days, dict):
            chat_days = {}
            stats[str(chat_id)] = chat_days
        # Keep only last 3 UTC days per chat
        if len(chat_days) > 3:
            for old_day in sorted(chat_days.keys())[:-3]:
                chat_days.pop(old_day, None)
        day_rec = chat_days.setdefault(today, {"total": 0, "users": {}, "names": {}})
        day_rec["total"] = int(day_rec.get("total", 0)) + 1
        day_rec["users"][str(uid)] = int(day_rec["users"].get(str(uid), 0)) + 1
        day_rec["names"][str(uid)] = uname

    # 3. Random chat event every 35 messages (when enabled)
    settings = get_chat_settings(chat_id)
    if not settings.get("chat_events_enabled", True):
        return
    trigger = False
    with _V1_LOCK:
        cnt = _CHAT_MSG_COUNTER.get(chat_id, 0) + 1
        if cnt >= 35:
            _CHAT_MSG_COUNTER[chat_id] = 0
            trigger = True
        else:
            _CHAT_MSG_COUNTER[chat_id] = cnt
    if not trigger:
        return

    if random.random() < 0.55:
        drop_id = uuid.uuid4().hex[:8]
        reward = random.randint(350, 900)
        with _V1_LOCK:
            _ACTIVE_DROPS[drop_id] = {"chat_id": chat_id, "reward": reward, "created_at": time.time()}
        markup = _mk_markup([[("🎁 Забрать сундук", f"v1:drop:claim:{drop_id}")]])
        try:
            bot.send_message(
                chat_id,
                card("🎁 <b>В чате упал сундук!</b>", body=f"Внутри <b>{reward:,} 🪙</b> — кто первый нажмёт кнопку, тот и забирает!"),
                parse_mode="HTML",
                reply_markup=markup,
            )
        except Exception:
            pass
    else:
        a = random.randint(7, 24)
        b = random.randint(3, 9)
        c = random.randint(1, 25)
        ans = a * b - c
        expr = f"{a} × {b} − {c}"
        reward = random.randint(400, 800)
        with _V1_LOCK:
            _ACTIVE_MATH[chat_id] = {"expr": expr, "answer": ans, "reward": reward, "expires_at": time.time() + 45}
        try:
            bot.send_message(
                chat_id,
                card("⚡ <b>Быстрый челлендж!</b>", body=f"Реши первым за 45 секунд: <code>{expr} = ?</code>\nНаграда: <b>{reward:,} 🪙</b>"),
                parse_mode="HTML",
            )
        except Exception:
            pass


def cmd_chat_day(message):
    if not can_process_user_message(message):
        return
    chat_id = str(message.chat.id)
    today = _today_utc()
    day_rec = (db.get("chat_daily_stats", {}) or {}).get(chat_id, {}).get(today)
    if not isinstance(day_rec, dict) or not day_rec.get("total"):
        bot.reply_to(message, card("📊 <b>Чат дня</b>", body="Сегодня сообщений пока почти нет — пора оживить беседу!"), parse_mode="HTML")
        return
    users = day_rec.get("users", {})
    names = day_rec.get("names", {})
    ranked = sorted(users.items(), key=lambda kv: -int(kv[1]))[:5]
    medals = ["🥇", "🥈", "🥉", "4.", "5."]
    lines = [f"💬 Всего сообщений сегодня: <b>{int(day_rec.get('total', 0)):,}</b>", ""]
    for idx, (uid_str, count) in enumerate(ranked):
        nm = html.escape(str(names.get(uid_str) or f"ID:{uid_str}"))
        lines.append(f"{medals[idx]} <b>{nm}</b> — {int(count)} сообщ.")
    if ranked:
        hero = html.escape(str(names.get(ranked[0][0]) or f"ID:{ranked[0][0]}"))
        lines.append(f"\n👑 Герой дня: <b>{hero}</b>")
    bot.reply_to(message, card(f"📊 <b>Итоги дня · {today}</b>", body=lines), parse_mode="HTML")


# ---------------------------------------------------------------------------
# 7. Achievement Badges (бейдж / бейджи)
# ---------------------------------------------------------------------------
def _build_badge_menu(user_id, user_name, username=None):
    econ = get_user_econ(user_id, user_name, username=username)
    unlocked = econ.get("achievements", []) if isinstance(econ.get("achievements"), list) else []
    catalog = globals().get("ACHIEVEMENTS") or {}
    current = badge_prefix(econ, catalog) or "не выбран"

    if not unlocked:
        return card(
            "🏅 <b>Выбор бейджа профиля</b>",
            body="У тебя пока нет открытых достижений. Открой хотя бы одну ачивку (<code>ачивки</code>), чтобы надеть её значок!",
        ), None

    rows = []
    lines = [f"Текущий бейдж: <b>{current}</b>", "", "Нажми на открытое достижение ниже, чтобы выбрать его значок:"]
    buf = []
    for ach_id in unlocked[:12]:
        ach = catalog.get(ach_id)
        if not isinstance(ach, dict):
            continue
        title = str(ach.get("title") or ach_id)[:24]
        buf.append((title, f"v1:badge:set:{user_id}:{ach_id}"))
        if len(buf) == 2:
            rows.append(buf)
            buf = []
    if buf:
        rows.append(buf)
    rows.append([("❌ Снять бейдж", f"v1:badge:clear:{user_id}")])
    return card("🏅 <b>Выбор бейджа профиля</b>", body=lines), _mk_markup(rows)


def cmd_badges(message):
    if not can_process_user_message(message):
        return
    uid = int(message.from_user.id)
    uname = _display_name(message.from_user)
    text, markup = _build_badge_menu(uid, uname, username=getattr(message.from_user, "username", None))
    kwargs = {"parse_mode": "HTML"}
    if markup is not None:
        kwargs["reply_markup"] = markup
    bot.reply_to(message, text, **kwargs)


# ---------------------------------------------------------------------------
# 8. Reputation (+реп / спасибо / топ реп)
# ---------------------------------------------------------------------------
def cmd_rep(message):
    if not can_process_user_message(message):
        return
    reply = getattr(message, "reply_to_message", None)
    if not reply or not getattr(reply, "from_user", None):
        bot.reply_to(message, "⭐ Ответь командой <code>+реп</code> на сообщение человека, чтобы повысить его репутацию.", parse_mode="HTML")
        return
    sender_id = int(message.from_user.id)
    target_u = reply.from_user
    target_id = int(target_u.id)
    if target_id == sender_id or getattr(target_u, "is_bot", False):
        bot.reply_to(message, "❌ Нельзя выдать репутацию самому себе или боту.")
        return
    now = time.time()
    cd_key = (sender_id, target_id)
    with _V1_LOCK:
        last_ts = _REP_COOLDOWNS.get(cd_key, 0.0)
        rem = last_ts + 6 * 3600 - now
        if rem > 0:
            bot.reply_to(message, f"⏳ Ты уже благодарил(а) этого участника. Снова можно через <b>{format_duration(rem)}</b>.", parse_mode="HTML")
            return
        _REP_COOLDOWNS[cd_key] = now
    target_name = _display_name(target_u)
    with db_lock:
        t_econ = get_user_econ(target_id, target_name, username=getattr(target_u, "username", None))
        t_econ["reputation"] = int(t_econ.get("reputation", 0) or 0) + 1
        new_rep = t_econ["reputation"]
        mark_dirty()
    link = make_link(message.chat.id, target_name, target_id, ping=False)
    bot.reply_to(
        message,
        card("⭐ <b>Репутация повышена!</b>", body=f"{link} получил(а) <b>+1 реп</b> · Всего: <b>{new_rep}</b>"),
        parse_mode="HTML",
    )


def cmd_top_rep(message):
    if not can_process_user_message(message):
        return
    econ_map = db.get("economy", {}) if isinstance(db, dict) else {}
    rows = []
    for key, rec in econ_map.items():
        if not isinstance(rec, dict):
            continue
        rep = int(rec.get("reputation", 0) or 0)
        if rep > 0:
            name = str(rec.get("display_name") or rec.get("name") or key)
            rows.append((rep, name))
    rows.sort(key=lambda x: -x[0])
    if not rows:
        bot.reply_to(message, card("⭐ <b>Топ репутации</b>", body="Пока никто не получил репутацию. Ответь на полезное сообщение командой <code>+реп</code>!"), parse_mode="HTML")
        return
    medals = ["🥇", "🥈", "🥉"]
    lines = [
        f"{medals[i] if i < 3 else f'{i+1}.'} <b>{html.escape(name)}</b> — ⭐ {rep}"
        for i, (rep, name) in enumerate(rows[:10])
    ]
    bot.reply_to(message, card("⭐ <b>Самые полезные участники (Топ реп)</b>", body=lines), parse_mode="HTML")


# ---------------------------------------------------------------------------
# 9. Night Merchant (торговец / ночной торговец)
# ---------------------------------------------------------------------------
def _merchant_rotation_key():
    now_dt = datetime.now(timezone.utc)
    return f"{now_dt.date().isoformat()}-S{now_dt.hour // 4}"


def _merchant_offers():
    return [
        {"id": "xp_boost", "name": "⚡ Бустер опыта (+250 EXP)", "price": 3500},
        {"id": "work_reset", "name": "⏳ Сброс кулдауна работы", "price": 2000},
        {"id": "lucky_box", "name": "🎁 Таинственный свёрток (1,000–6,000 🪙)", "price": 3000},
    ]


def cmd_night_merchant(message):
    if not can_process_user_message(message):
        return
    uid = int(message.from_user.id)
    uname = _display_name(message.from_user)
    econ = get_user_econ(uid, uname, username=getattr(message.from_user, "username", None))
    rot = _merchant_rotation_key()
    bought = econ.get("merchant_bought", {}).get(rot, []) if isinstance(econ.get("merchant_bought"), dict) else []
    offers = _merchant_offers()
    lines = [f"💳 Твой баланс: <b>{int(econ.get('balance', 0)):,} 🪙</b>", ""]
    rows = []
    for idx, item in enumerate(offers):
        mark = "✅ куплено" if item["id"] in bought else f"<b>{item['price']:,} 🪙</b>"
        lines.append(f"{idx + 1}. {item['name']} — {mark}")
        if item["id"] not in bought:
            rows.append([(f"Купить #{idx + 1} ({item['price']:,} 🪙)", f"v1:merch:buy:{uid}:{idx}")])
    text = card(
        "🌙 <b>Ночной торговец</b>",
        body=lines,
        footer="🔄 Ассортимент обновляется каждые 4 часа (1 покупка каждого лота за смену).",
    )
    markup = _mk_markup(rows) if rows else None
    kwargs = {"parse_mode": "HTML"}
    if markup is not None:
        kwargs["reply_markup"] = markup
    bot.reply_to(message, text, **kwargs)


# ---------------------------------------------------------------------------
# 10. Guild Weekly Goal (гильдия цель)
# ---------------------------------------------------------------------------
def _find_user_guild(user_id):
    guilds = db.get("guilds", {}) if isinstance(db, dict) else {}
    uid_str = str(user_id)
    for gid, g in guilds.items():
        if not isinstance(g, dict):
            continue
        members = g.get("members", [])
        if user_id in members or uid_str in [str(m) for m in members]:
            return gid, g
    return None, None


def cmd_guild_goal(message):
    if not can_process_user_message(message):
        return
    uid = int(message.from_user.id)
    with db_lock:
        gid, guild = _find_user_guild(uid)
        if not guild:
            bot.reply_to(message, card("🏛 <b>Недельная цель гильдии</b>", body="Ты пока не состоишь в гильдии. Вступи или создай её через <code>/guild</code>."), parse_mode="HTML")
            return
        week = _iso_week_key()
        goal = guild.get("weekly_goal")
        if not isinstance(goal, dict) or goal.get("week") != week:
            goal = {
                "week": week,
                "title": "Пополните казну или внесите вклад в цель гильдии на 50,000 🪙",
                "target": 50000,
                "progress": 0,
                "contributors": {},
                "claimed_by": [],
                "reward": 3000,
            }
            guild["weekly_goal"] = goal
            mark_dirty()
        g_name = html.escape(str(guild.get("name") or gid))
        prog = int(goal.get("progress", 0))
        targ = max(1, int(goal.get("target", 50000)))
        bar = progress_bar(prog, targ, width=10)
        claimed = uid in [int(x) for x in goal.get("claimed_by", [])]
    lines = [
        f"🎯 {html.escape(str(goal.get('title')))}",
        f"📊 {bar} ({prog:,} / {targ:,} 🪙)",
        f"🎁 Награда каждому участнику: <b>{int(goal.get('reward', 3000)):,} 🪙</b>",
    ]
    rows = []
    if prog < targ:
        rows.append([("💸 Внести 5,000 🪙 в цель", f"v1:guild:donate:{uid}:5000")])
    elif not claimed:
        rows.append([("🎁 Забрать награду недели", f"v1:guild:claim:{uid}")])
    else:
        lines.append("✅ Ты уже забрал(а) награду за эту неделю!")
    markup = _mk_markup(rows) if rows else None
    kwargs = {"parse_mode": "HTML"}
    if markup is not None:
        kwargs["reply_markup"] = markup
    bot.reply_to(message, card(f"🏛 <b>Цель гильдии «{g_name}»</b>", body=lines), **kwargs)


# ---------------------------------------------------------------------------
# 11. 24h Money Receipt (чек / сводка денег)
# ---------------------------------------------------------------------------
def _record_money_event(econ, delta, label):
    if not isinstance(econ, dict):
        return
    hist = econ.setdefault("v1_money_log", [])
    if not isinstance(hist, list):
        hist = []
        econ["v1_money_log"] = hist
    hist.append({"at": time.time(), "delta": int(delta), "label": str(label)[:40]})
    if len(hist) > 60:
        del hist[:-60]


def _build_receipt_text(user_id, user_name, username=None):
    econ = get_user_econ(user_id, user_name, username=username)
    now = time.time()
    cutoff = now - 86400
    raw_native = econ.get("money_history", []) if isinstance(econ.get("money_history"), list) else []
    raw_v1 = econ.get("v1_money_log", []) if isinstance(econ.get("v1_money_log"), list) else []
    recent = []
    for x in raw_native:
        if isinstance(x, dict):
            ts = float(x.get("ts") or x.get("at") or x.get("time") or 0)
            if ts >= cutoff:
                recent.append({"at": ts, "delta": int(x.get("delta", 0) or 0), "label": str(x.get("reason") or x.get("label") or "Операция")})
    if not recent:
        for x in raw_v1:
            if isinstance(x, dict) and float(x.get("at", 0) or 0) >= cutoff:
                recent.append(x)
    income = sum(int(x["delta"]) for x in recent if int(x.get("delta", 0)) > 0)
    expense = sum(-int(x["delta"]) for x in recent if int(x.get("delta", 0)) < 0)
    net = income - expense
    lines = [
        f"💵 Кошелёк: <b>{int(econ.get('balance', 0)):,} 🪙</b> · 🏦 Банк: <b>{int(econ.get('bank_deposit', 0)):,} 🪙</b>",
        f"📈 Доходы за 24ч: <b>+{income:,} 🪙</b>",
        f"📉 Расходы за 24ч: <b>-{expense:,} 🪙</b>",
        f"⚖️ Итог за 24ч: <b>{'+' if net >= 0 else ''}{net:,} 🪙</b>",
    ]
    if recent:
        lines.append("")
        lines.append("<b>Последние операции:</b>")
        for item in recent[-5:][::-1]:
            d = int(item.get("delta", 0))
            sign = "+" if d >= 0 else ""
            lines.append(f"• {html.escape(str(item.get('label', 'Операция')))}: <b>{sign}{d:,} 🪙</b>")
    return card("🧾 <b>Финансовый чек (24 часа)</b>", body=lines)


def cmd_money_receipt(message):
    if not can_process_user_message(message):
        return
    uid = int(message.from_user.id)
    uname = _display_name(message.from_user)
    bot.reply_to(message, _build_receipt_text(uid, uname, username=getattr(message.from_user, "username", None)), parse_mode="HTML")


# ---------------------------------------------------------------------------
# 12. Opt-in DM Notifications (уведомления вкл/выкл)
# ---------------------------------------------------------------------------
def cmd_notifications(message, mode=""):
    if not can_process_user_message(message):
        return
    uid = int(message.from_user.id)
    uname = _display_name(message.from_user)
    with db_lock:
        econ = get_user_econ(uid, uname, username=getattr(message.from_user, "username", None))
        if mode in {"вкл", "on", "да"}:
            econ["dm_notifications"] = True
            mark_dirty()
        elif mode in {"выкл", "off", "нет"}:
            econ["dm_notifications"] = False
            mark_dirty()
        enabled = bool(econ.get("dm_notifications", False))
    status = "✅ включены" if enabled else "🔕 выключены"
    bot.reply_to(
        message,
        card(
            "🔔 <b>Тихие уведомления в ЛС</b>",
            body=[
                f"Статус: <b>{status}</b>",
                "Когда включено, бот может напоминать в личку про готовый сад, завершённый таймер в <code>отн</code> и выход из тюрьмы.",
            ],
            footer="Управление: <code>уведомления вкл</code> / <code>уведомления выкл</code>",
        ),
        parse_mode="HTML",
    )


def check_and_send_dm_notifications():
    """Send one-shot DM reminders to opted-in users when timers complete."""
    now = time.time()
    econ_map = db.get("economy", {}) if isinstance(globals().get("db"), dict) else {}
    rel_root = db.get("relationships", {}) if isinstance(globals().get("db"), dict) else {}
    pairs = rel_root.get("pairs", {}) if isinstance(rel_root, dict) else {}
    users_map = rel_root.get("users", {}) if isinstance(rel_root, dict) else {}
    sent = 0
    for uid_str, econ in list(econ_map.items()):
        if not isinstance(econ, dict) or not econ.get("dm_notifications"):
            continue
        try:
            uid = int(str(uid_str).split("_")[-1])
        except (TypeError, ValueError):
            continue
        # 1. Jail release notification
        jail_until = float(econ.get("jail_until", 0) or 0)
        if 0 < jail_until <= now and not econ.get("_notified_jail_done"):
            econ["_notified_jail_done"] = True
            try:
                bot.send_message(uid, "🔓 <b>Ты вышел(а) из тюрьмы!</b> Можно снова играть и участвовать в делах.", parse_mode="HTML")
                sent += 1
            except Exception:
                pass
        elif jail_until > now and econ.get("_notified_jail_done"):
            econ["_notified_jail_done"] = False
        # 2. 40-hour relationship timer ready
        pair_id = users_map.get(str(uid))
        pair = pairs.get(str(pair_id)) if pair_id else None
        if isinstance(pair, dict):
            fp = pair.get("family_plan")
            if isinstance(fp, dict) and fp.get("status") == "active":
                due_at = float(fp.get("due_at", 0) or 0)
                if 0 < due_at <= now and not fp.get(f"_notified_{uid}"):
                    fp[f"_notified_{uid}"] = True
                    try:
                        bot.send_message(uid, "🍼 <b>Игровой таймер 40 недель завершён!</b> Напиши в чате <code>отн родить</code>.", parse_mode="HTML")
                        sent += 1
                    except Exception:
                        pass
    return sent


# ---------------------------------------------------------------------------
# 13. Live Market Helper (sparkline + daily news)
# ---------------------------------------------------------------------------
def get_daily_market_news():
    digest = hashlib.sha256(_today_utc().encode("utf-8")).digest()
    idx = digest[0] % len(_MARKET_NEWS)
    return _MARKET_NEWS[idx]


def format_market_sparkline(info):
    hist = info.get("history")
    if isinstance(hist, list) and len(hist) >= 2:
        return sparkline(hist[-8:])
    old_p = float(info.get("old_price", info.get("price", 1.0)) or 1.0)
    cur_p = float(info.get("price", 1.0) or 1.0)
    mid = (old_p + cur_p) / 2.0
    return sparkline([old_p, old_p * 0.99, mid, cur_p])


# ---------------------------------------------------------------------------
# 14. Admin Chat Toggles (автоответы / ивенты / автоудаление приветствий)
# ---------------------------------------------------------------------------
def cmd_chat_toggle(message, setting_key, title, enable):
    if not can_process_user_message(message):
        return
    if getattr(message.chat, "type", "") == "private":
        bot.reply_to(message, "Эта настройка работает в групповых чатах.")
        return
    if not can_admin_action(message.chat.id, message.from_user.id, "settings"):
        bot.reply_to(message, "❌ Менять настройки чата могут только администраторы.")
        return
    with db_lock:
        settings = get_chat_settings(message.chat.id)
        settings[setting_key] = bool(enable)
        mark_dirty()
    state_str = "✅ включены" if enable else "🔕 отключены"
    bot.reply_to(message, card(f"⚙️ <b>Настройка чата</b>", body=f"{title}: <b>{state_str}</b>."), parse_mode="HTML")


# ---------------------------------------------------------------------------
# 15. Text Command Dispatcher (called from handlers/moderation.py)
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# 14b. Boobs Biometry (сиськи / /boobs / топ сисек)
# ---------------------------------------------------------------------------
def cmd_boobs(message):
    if not can_process_user_message(message):
        return
    uid = int(message.from_user.id)
    uname = _display_name(message.from_user)
    chat_id = message.chat.id
    econ = get_user_econ(uid, uname, username=getattr(message.from_user, "username", None))

    now = time.time()
    last_time = float(econ.get("last_boobs_time", 0) or 0)
    cooldown = 1200  # 20 минут, как у замера писюна
    rem = last_time + cooldown - now
    if rem > 0:
        bot.reply_to(
            message,
            f"⏳ Замер сисек доступен раз в 20 минут! 😿\nПодождите: <b>{format_duration(rem)}</b>.",
            parse_mode="HTML",
        )
        return

    change_pool = [-2, -1, -1, 0, 1, 1, 2]
    change = random.choice([-3, 3]) if random.random() < 0.08 else random.choice(change_pool)
    cur_size = int(econ.get("boobs_size", 2) if econ.get("boobs_size") is not None else 2)
    new_size = max(0, min(15, cur_size + change))

    econ["boobs_size"] = new_size
    econ["last_boobs_time"] = now
    mark_dirty()

    sign = "+" if change >= 0 else ""
    u_link = make_link(chat_id, uname, uid, ping=True)
    if new_size >= 10:
        comment = "🌌 Легендарные габариты аниме-богини! Физика чата официально сдалась! 🙀"
    elif new_size >= 7:
        comment = "👑 Максимальная гравитация — весь чат обернулся! 😻"
    elif new_size >= 5:
        comment = "🔥 Внушительный и роскошный размер! 😸"
    elif new_size >= 3:
        comment = "👌 Классический гармоничный размер! 😺"
    elif new_size >= 1:
        comment = "🌸 Аккуратненько и миленько — плоскость тоже в моде! 😽"
    else:
        comment = "📏 Абсолютная аэродинамика! Зато спина не болит 😹"

    bot.reply_to(
        message,
        card(
            "🍒 <b>Замер сисек</b>",
            body=[
                f"👤 {u_link}",
                f"📏 Размер: <b>{new_size} размер</b> ({sign}{change})",
                f"💬 <i>{comment}</i>",
            ],
            footer="Топ чата: <code>топ сисек</code> · Вся статистика: <code>/biometry</code>",
        ),
        parse_mode="HTML",
    )


def cmd_top_boobs(message):
    if not can_process_user_message(message):
        return
    econ_map = db.get("economy", {}) if isinstance(db, dict) else {}
    rows = []
    for key, rec in econ_map.items():
        if not isinstance(rec, dict) or rec.get("boobs_size") is None:
            continue
        size = int(rec.get("boobs_size", 0) or 0)
        name = str(rec.get("display_name") or rec.get("name") or key)
        rows.append((size, name))
    rows.sort(key=lambda x: -x[0])
    if not rows:
        bot.reply_to(message, card("🍒 <b>Топ по размеру сисек</b>", body="Пока никто не делал замер! Напиши <code>сиськи</code>."), parse_mode="HTML")
        return
    medals = ["🥇", "🥈", "🥉"]
    lines = [
        f"{medals[i] if i < 3 else f'{i+1}.'} <b>{html.escape(name)}</b> — 🍒 {size} размер"
        for i, (size, name) in enumerate(rows[:10])
    ]
    bot.reply_to(message, card("🍒 <b>Топ по размеру сисек</b>", body=lines), parse_mode="HTML")


def try_handle_v1_text(message, text_lower):
    """Handle plain-text Russian aliases for v1.0 features. Returns True if handled."""
    if text_lower in {"сиськи", "грудь", "размер груди", ".сиськи"}:
        cmd_boobs(message)
        return True
    if text_lower in {"топ сисек", "топ сиськи", "топ груди"}:
        cmd_top_boobs(message)
        return True
    if text_lower in {"обнова", "обновления", "апдейт", "changelog"}:
        cmd_update(message)
        return True
    if text_lower in {"команды", "меню помощи", "справка"}:
        cmd_help_menu(message)
        return True
    if text_lower in {"дейли", "сводка дня"}:
        cmd_daily_hub(message)
        return True
    if text_lower in {"собрать всё", "собрать все"}:
        cmd_collect_all(message)
        return True
    if text_lower == "дуэль" or text_lower.startswith("дуэль "):
        cmd_duel(message, text_lower[len("дуэль"):].strip())
        return True
    if text_lower in {"ограбление", "ограбить банк"}:
        cmd_heist(message)
        return True
    if text_lower in {"чат дня", "итоги дня"}:
        cmd_chat_day(message)
        return True
    if text_lower in {"бейдж", "бейджи", "значок"}:
        cmd_badges(message)
        return True
    if text_lower in {"+реп", "+rep", "спасибо"} and getattr(message, "reply_to_message", None):
        cmd_rep(message)
        return True
    if text_lower in {"топ реп", "топ репутации"}:
        cmd_top_rep(message)
        return True
    if text_lower in {"торговец", "ночной торговец", "лавка"}:
        cmd_night_merchant(message)
        return True
    if text_lower in {"гильдия цель", "клан цель", "цель гильдии"}:
        cmd_guild_goal(message)
        return True
    if text_lower in {"чек", "сводка денег"}:
        cmd_money_receipt(message)
        return True
    if text_lower == "уведомления" or text_lower.startswith("уведомления "):
        cmd_notifications(message, text_lower[len("уведомления"):].strip())
        return True
    if text_lower in {"автоответы вкл", "автоответы выкл"}:
        cmd_chat_toggle(message, "auto_replies_enabled", "Автоответы на слова", text_lower.endswith("вкл"))
        return True
    if text_lower in {"ивенты вкл", "ивенты выкл"}:
        cmd_chat_toggle(message, "chat_events_enabled", "Случайные чат-ивенты", text_lower.endswith("вкл"))
        return True
    if text_lower in {"автоудаление приветствий вкл", "автоудаление приветствий выкл"}:
        cmd_chat_toggle(message, "auto_delete_welcome", "Автоудаление приветствий", text_lower.endswith("вкл"))
        return True
    return False


# ---------------------------------------------------------------------------
# 16. Unified Callback Handler (v1: prefix)
# ---------------------------------------------------------------------------
def handle_v1_callbacks(call):
    data = str(getattr(call, "data", "") or "")
    if not data.startswith("v1:"):
        return
    user = getattr(call, "from_user", None)
    msg = getattr(call, "message", None)
    if not user or not msg:
        return
    uid = int(user.id)
    uname = _display_name(user)
    parts = data.split(":")

    try:
        # /update pagination
        if len(parts) == 3 and parts[1] == "upd":
            idx = None if parts[2] == "latest" else int(parts[2])
            text, markup = _build_update_view(idx)
            _safe_edit(call, text, reply_markup=markup)
            bot.answer_callback_query(call.id)
            return

        # /help tabs
        if len(parts) == 3 and parts[1] == "help":
            text, markup = _build_help_view(parts[2])
            _safe_edit(call, text, reply_markup=markup)
            bot.answer_callback_query(call.id)
            return

        # Daily hub refresh / open
        if len(parts) == 4 and parts[1] == "daily" and parts[2] == "open":
            if int(parts[3]) != uid:
                bot.answer_callback_query(call.id, "Открой свою сводку командой «дейли».", show_alert=True)
                return
            text, markup = _build_daily_hub_text(uid, uname, username=getattr(user, "username", None))
            _safe_edit(call, text, reply_markup=markup)
            bot.answer_callback_query(call.id, "Обновлено!")
            return

        # Collect all button
        if len(parts) == 4 and parts[1] == "collect" and parts[2] == "all":
            if int(parts[3]) != uid:
                bot.answer_callback_query(call.id, "Эта кнопка для другого игрока.", show_alert=True)
                return
            text = _perform_collect_all(uid, uname, username=getattr(user, "username", None))
            _safe_edit(call, text)
            bot.answer_callback_query(call.id, "💰 Готово!")
            return

        # Balance card quick buttons
        if len(parts) == 4 and parts[1] == "bal":
            if int(parts[3]) != uid:
                bot.answer_callback_query(call.id, "Открой свой баланс командой «баланс».", show_alert=True)
                return
            if parts[2] == "dep":
                bot.answer_callback_query(call.id, "Напиши: банк положить <сумма>", show_alert=True)
            else:
                bot.answer_callback_query(call.id, "Напиши: банк снять <сумма>", show_alert=True)
            return

        # Receipt button
        if len(parts) == 4 and parts[1] == "check" and parts[2] == "open":
            if int(parts[3]) != uid:
                bot.answer_callback_query(call.id, "Открой свой чек командой «чек».", show_alert=True)
                return
            _safe_edit(call, _build_receipt_text(uid, uname, username=getattr(user, "username", None)))
            bot.answer_callback_query(call.id)
            return

        # Badge picker
        if parts[1] == "badge":
            action = parts[2]
            owner_id = int(parts[3])
            if owner_id != uid:
                bot.answer_callback_query(call.id, "Открой выбор бейджа командой «бейдж».", show_alert=True)
                return
            if action == "menu":
                text, markup = _build_badge_menu(uid, uname, username=getattr(user, "username", None))
                _safe_edit(call, text, reply_markup=markup)
                bot.answer_callback_query(call.id)
                return
            if action == "clear":
                with db_lock:
                    econ = get_user_econ(uid, uname, username=getattr(user, "username", None))
                    econ["active_badge"] = None
                    mark_dirty()
                text, markup = _build_badge_menu(uid, uname, username=getattr(user, "username", None))
                _safe_edit(call, text, reply_markup=markup)
                bot.answer_callback_query(call.id, "Бейдж снят")
                return
            if action == "set" and len(parts) >= 5:
                ach_id = ":".join(parts[4:])
                with db_lock:
                    econ = get_user_econ(uid, uname, username=getattr(user, "username", None))
                    if ach_id not in (econ.get("achievements") or []):
                        bot.answer_callback_query(call.id, "Это достижение ещё не открыто.", show_alert=True)
                        return
                    econ["active_badge"] = ach_id
                    mark_dirty()
                text, markup = _build_badge_menu(uid, uname, username=getattr(user, "username", None))
                _safe_edit(call, text, reply_markup=markup)
                bot.answer_callback_query(call.id, "🏅 Бейдж установлен!")
                return

        # PvP Duel
        if len(parts) == 4 and parts[1] == "duel":
            action, duel_id = parts[2], parts[3]
            with _V1_LOCK:
                duel = _ACTIVE_DUELS.get(duel_id)
                if not duel or time.time() - duel["created_at"] > 120:
                    _ACTIVE_DUELS.pop(duel_id, None)
                    bot.answer_callback_query(call.id, "Вызов на дуэль истёк.", show_alert=True)
                    return
                if uid != duel["to_id"]:
                    bot.answer_callback_query(call.id, "Ответить может только вызванный игрок.", show_alert=True)
                    return
                _ACTIVE_DUELS.pop(duel_id, None)
            if action == "dec":
                _safe_edit(call, card("🏳️ <b>Дуэль отменена</b>", body=f"{html.escape(duel['to_name'])} отказался(ась) от вызова."))
                bot.answer_callback_query(call.id, "Отказ принят")
                return
            bet = duel["bet"]
            with serialized_multi_user_action(duel["from_id"], duel["to_id"]):
                e1 = get_user_econ(duel["from_id"], duel["from_name"])
                e2 = get_user_econ(duel["to_id"], duel["to_name"])
                if int(e1.get("balance", 0)) < bet or int(e2.get("balance", 0)) < bet:
                    _safe_edit(call, card("❌ <b>Дуэль не состоялась</b>", body="У одного из игроков уже не хватает Ня-коинов."))
                    bot.answer_callback_query(call.id, "Недостаточно средств", show_alert=True)
                    return
                r1, r2 = random.randint(1, 100), random.randint(1, 100)
                while r1 == r2:
                    r2 = random.randint(1, 100)
                if r1 > r2:
                    winner_name, loser_name = duel["from_name"], duel["to_name"]
                    _adjust_balance(e1, bet)
                    _adjust_balance(e2, -bet)
                    _record_money_event(e1, bet, "Победа в дуэли")
                    _record_money_event(e2, -bet, "Проигрыш в дуэли")
                else:
                    winner_name, loser_name = duel["to_name"], duel["from_name"]
                    _adjust_balance(e2, bet)
                    _adjust_balance(e1, -bet)
                    _record_money_event(e2, bet, "Победа в дуэли")
                    _record_money_event(e1, -bet, "Проигрыш в дуэли")
                mark_dirty()
            _safe_edit(
                call,
                card(
                    "⚔️ <b>Итог дуэли!</b>",
                    body=[
                        f"🎲 {html.escape(duel['from_name'])}: <b>{r1}</b> vs {html.escape(duel['to_name'])}: <b>{r2}</b>",
                        f"🏆 Победитель: <b>{html.escape(winner_name)}</b> (+<b>{bet:,} 🪙</b>)",
                        f"💨 Проигравший: {html.escape(loser_name)} (-{bet:,} 🪙)",
                    ],
                ),
            )
            bot.answer_callback_query(call.id, "⚔️ Дуэль завершена!")
            return

        # Co-op Heist
        if len(parts) == 4 and parts[1] == "heist":
            action, heist_id = parts[2], parts[3]
            with _V1_LOCK:
                heist = _ACTIVE_HEISTS.get(heist_id)
                if not heist or heist["started"]:
                    bot.answer_callback_query(call.id, "Ограбление уже завершилось или истекло.", show_alert=True)
                    return
                if action == "join":
                    if uid in heist["members"]:
                        bot.answer_callback_query(call.id, "Ты уже в банде!")
                        return
                    if len(heist["members"]) >= 4:
                        bot.answer_callback_query(call.id, "Банда уже полная (4/4)!", show_alert=True)
                        return
                    heist["members"][uid] = uname
                    lobby_text = _render_heist_lobby(heist)
                    markup = _mk_markup([
                        [("🎭 Вступить в банду", f"v1:heist:join:{heist_id}"), ("🚀 Начать дело", f"v1:heist:go:{heist_id}")],
                    ])
                    _safe_edit(call, lobby_text, reply_markup=markup)
                    bot.answer_callback_query(call.id, "🎭 Ты в банде!")
                    return
                if action == "go":
                    if uid != heist["leader_id"]:
                        bot.answer_callback_query(call.id, "Начать дело может только лидер банды.", show_alert=True)
                        return
                    if len(heist["members"]) < 2:
                        bot.answer_callback_query(call.id, "Нужно минимум 2 участника!", show_alert=True)
                        return
                    heist["started"] = True
                    _ACTIVE_HEISTS.pop(heist_id, None)
                    _HEIST_COOLDOWNS[heist["chat_id"]] = time.time() + 600
            # Resolve heist
            crew = list(heist["members"].items())
            chance = min(80, 50 + len(crew) * 6)
            success = random.randint(1, 100) <= chance
            now = time.time()
            if success:
                total_loot = random.randint(900, 1800) * len(crew)
                share = total_loot // len(crew)
                for mid, mname in crew:
                    me = get_user_econ(mid, mname)
                    _adjust_balance(me, share)
                    _record_money_event(me, share, "Ограбление банка")
                mark_dirty()
                res_text = card(
                    "💰 <b>Ограбление прошло успешно!</b>",
                    body=[
                        f"🏦 Общий куш: <b>{total_loot:,} 🪙</b>",
                        f"💵 Доля каждого ({len(crew)} чел.): <b>+{share:,} 🪙</b>",
                    ],
                )
            else:
                with db_lock:
                    for mid, mname in crew:
                        me = get_user_econ(mid, mname)
                        me["jail_until"] = max(float(me.get("jail_until", 0) or 0), now + 300)
                    mark_dirty()
                res_text = card(
                    "🚓 <b>Облава! Банду повязали!</b>",
                    body=[
                        f"Все участники ({len(crew)} чел.) отправлены в тюрьму на <b>5 минут</b>.",
                        "Используйте <code>побег</code> или <code>залог</code>, чтобы выбраться раньше!",
                    ],
                )
            _safe_edit(call, res_text)
            bot.answer_callback_query(call.id, "💰 Успех!" if success else "🚓 В тюрьму!")
            return

        # Random chest drop
        if len(parts) == 4 and parts[1] == "drop" and parts[2] == "claim":
            drop_id = parts[3]
            with _V1_LOCK:
                drop = _ACTIVE_DROPS.pop(drop_id, None)
            if not drop:
                bot.answer_callback_query(call.id, "Сундук уже забрали!", show_alert=True)
                return
            reward = drop["reward"]
            econ = get_user_econ(uid, uname, username=getattr(user, "username", None))
            _adjust_balance(econ, reward)
            _record_money_event(econ, reward, "Сундук в чате")
            mark_dirty()
            _safe_edit(call, card("🎁 <b>Сундук открыт!</b>", body=f"🏆 {make_link(msg.chat.id, uname, uid, ping=False)} оказался(ась) быстрее всех и забрал(а) <b>+{reward:,} 🪙</b>!"))
            bot.answer_callback_query(call.id, f"+{reward:,} 🪙!")
            return

        # Night merchant purchase
        if len(parts) == 5 and parts[1] == "merch" and parts[2] == "buy":
            owner_id, slot = int(parts[3]), int(parts[4])
            if owner_id != uid:
                bot.answer_callback_query(call.id, "Открой лавку командой «торговец».", show_alert=True)
                return
            offers = _merchant_offers()
            if slot < 0 or slot >= len(offers):
                bot.answer_callback_query(call.id, "Лот не найден.", show_alert=True)
                return
            item = offers[slot]
            rot = _merchant_rotation_key()
            econ = get_user_econ(uid, uname, username=getattr(user, "username", None))
            bought_map = econ.setdefault("merchant_bought", {})
            if not isinstance(bought_map, dict):
                bought_map = {}
                econ["merchant_bought"] = bought_map
            bought_list = bought_map.setdefault(rot, [])
            if item["id"] in bought_list:
                bot.answer_callback_query(call.id, "Ты уже купил(а) этот лот в этой смене.", show_alert=True)
                return
            if int(econ.get("balance", 0)) < item["price"]:
                bot.answer_callback_query(call.id, f"Не хватает Ня-коинов (нужно {item['price']:,}).", show_alert=True)
                return
            _adjust_balance(econ, -item["price"])
            _record_money_event(econ, -item["price"], f"Торговец: {item['id']}")
            bought_list.append(item["id"])
            outcome = ""
            if item["id"] == "xp_boost":
                add_account_exp(uid, uname, 250, username=getattr(user, "username", None), source="night_merchant_boost")
                outcome = "⚡ Начислено +250 EXP!"
            elif item["id"] == "work_reset":
                econ["last_work_time"] = 0
                outcome = "⏳ Кулдаун работы полностью сброшен!"
            elif item["id"] == "lucky_box":
                prize = random.randint(1000, 6000)
                _adjust_balance(econ, prize)
                _record_money_event(econ, prize, "Таинственный свёрток")
                outcome = f"🎁 В свёртке оказалось <b>+{prize:,} 🪙</b>!"
            mark_dirty()
            _safe_edit(call, card("🌙 <b>Покупка у Ночного торговца</b>", body=[f"Куплено: <b>{item['name']}</b>", outcome]))
            bot.answer_callback_query(call.id, "✅ Куплено!")
            return

        # Guild goal donate / claim
        if parts[1] == "guild":
            action = parts[2]
            owner_id = int(parts[3])
            if owner_id != uid:
                bot.answer_callback_query(call.id, "Открой цель командой «гильдия цель».", show_alert=True)
                return
            gid, guild = _find_user_guild(uid)
            if not guild or not isinstance(guild.get("weekly_goal"), dict):
                bot.answer_callback_query(call.id, "Цель гильдии не найдена.", show_alert=True)
                return
            goal = guild["weekly_goal"]
            if action == "donate" and len(parts) == 5:
                amount = int(parts[4])
                econ = get_user_econ(uid, uname, username=getattr(user, "username", None))
                if int(econ.get("balance", 0)) < amount:
                    bot.answer_callback_query(call.id, f"Недостаточно Ня-коинов ({amount:,} 🪙).", show_alert=True)
                    return
                _adjust_balance(econ, -amount)
                _record_money_event(econ, -amount, "Вклад в цель гильдии")
                with _V1_LOCK:
                    goal["progress"] = min(int(goal["target"]), int(goal.get("progress", 0)) + amount)
                    contrib = goal.setdefault("contributors", {})
                    contrib[str(uid)] = int(contrib.get(str(uid), 0)) + amount
                mark_dirty()
                bot.answer_callback_query(call.id, f"✅ Внесено {amount:,} 🪙!")
                _safe_edit(
                    call,
                    card(
                        "🏛 <b>Вклад в цель гильдии принят!</b>",
                        body=f"Прогресс: {progress_bar(goal['progress'], goal['target'], width=10)} ({goal['progress']:,}/{goal['target']:,} 🪙)",
                    ),
                )
                return
            if action == "claim":
                with _V1_LOCK:
                    if int(goal.get("progress", 0)) < int(goal.get("target", 1)):
                        bot.answer_callback_query(call.id, "Цель ещё не выполнена!", show_alert=True)
                        return
                    if uid in [int(x) for x in goal.get("claimed_by", [])]:
                        bot.answer_callback_query(call.id, "Награда уже получена!", show_alert=True)
                        return
                    goal.setdefault("claimed_by", []).append(uid)
                reward = int(goal.get("reward", 3000))
                econ = get_user_econ(uid, uname, username=getattr(user, "username", None))
                _adjust_balance(econ, reward)
                _record_money_event(econ, reward, "Награда цели гильдии")
                mark_dirty()
                bot.answer_callback_query(call.id, f"🎁 +{reward:,} 🪙!")
                _safe_edit(call, card("🎉 <b>Награда гильдии получена!</b>", body=f"На баланс зачислено <b>+{reward:,} 🪙</b>."))
                return
    except Exception as exc:
        print(f"[V1 CALLBACK ERROR] {exc}")
        try:
            bot.answer_callback_query(call.id, "Ошибка обработки кнопки.")
        except Exception:
            pass


def register(ctx, only=None):
    _inject(ctx)
    bot = ctx["bot"]
    wanted = set(only) if only is not None else set(HANDLER_NAMES)
    registered = []
    if "cmd_update" in wanted:
        h = serialize_user_action(cmd_update)
        bot.message_handler(commands=["update", "changelog"])(h)
        ctx["cmd_update"] = h
        globals()["cmd_update"] = h
        registered.append("cmd_update")
    if "cmd_help_menu" in wanted:
        h = serialize_user_action(cmd_help_menu)
        bot.message_handler(commands=["help"])(h)
        ctx["cmd_help_menu"] = h
        globals()["cmd_help_menu"] = h
        registered.append("cmd_help_menu")
    if "cmd_daily_hub" in wanted:
        h = serialize_user_action(cmd_daily_hub)
        bot.message_handler(commands=["daily"])(h)
        ctx["cmd_daily_hub"] = h
        globals()["cmd_daily_hub"] = h
        registered.append("cmd_daily_hub")
    if "cmd_boobs" in wanted:
        h = serialize_user_action(cmd_boobs)
        bot.message_handler(commands=["boobs", "сиськи"])(h)
        ctx["cmd_boobs"] = h
        globals()["cmd_boobs"] = h
        registered.append("cmd_boobs")
    if "handle_v1_callbacks" in wanted:
        cb = serialize_user_action(handle_v1_callbacks)
        bot.callback_query_handler(
            func=lambda call: str(getattr(call, "data", "") or "").startswith("v1:")
        )(cb)
        ctx["handle_v1_callbacks"] = cb
        globals()["handle_v1_callbacks"] = cb
        registered.append("handle_v1_callbacks")
    return registered
