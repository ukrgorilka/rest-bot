"""Standalone couples/relationships feature for NyaBot.

This module deliberately does not read or write the legacy ``marriage`` field.
Relationship state lives in ``db['relationships']`` and is shared by the pair.
Commands are plain text, e.g. ``отн чмок`` (no dot and no slash required).
"""

from __future__ import annotations

import copy
import html
import json
import math
import os
import random
import re
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from urllib.parse import urlsplit

from core.locks import serialize_user_action


RELATIONSHIPS_LOCK = threading.RLock()
RELATIONSHIP_OUTBOX = threading.local()
RELATIONSHIP_GIF_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "relationships", "data", "gifs.json")
MAX_GIFT_HISTORY = 100
MAX_RELATIONSHIP_HISTORY = 100
MAX_CHILDREN_PER_PAIR = 3
PREGNANCY_DURATION_SECONDS = 40 * 60 * 60  # 1 игровая неделя = 1 реальный час
FAMILY_PLAN_TTL_SECONDS = 24 * 60 * 60
PROTECTION_DURATION_SECONDS = 48 * 60 * 60
PROTECTION_COST = 40
PROPOSAL_TTL_SECONDS = 24 * 60 * 60
BREAKUP_CONFIRM_TTL_SECONDS = 2 * 60

LEVEL_THRESHOLDS = [0, 100, 250, 450, 700, 1000, 1500]

# ``reward`` is paid to the shared pair wallet. ``lifetime`` drives levels and
# never decreases when the pair spends its petals.
ACTIONS = {
    "чмок": {"key": "kiss", "caption": "💋 {actor} чмокнул(а) {partner}!", "level": 1, "reward": 0, "cooldown": 5},
    "обнять": {"key": "hug", "caption": "🫂 {actor} крепко обнял(а) {partner}!", "level": 1, "reward": 0, "cooldown": 5},
    "поцеловать": {"key": "kiss", "caption": "💗 {actor} нежно поцеловал(а) {partner}!", "level": 1, "reward": 0, "cooldown": 10},
    "укусить": {"key": "bite", "caption": "😼 {actor} игриво укусил(а) {partner}!", "level": 1, "reward": 0, "cooldown": 10},
    "погладить": {"key": "pat", "caption": "🐾 {actor} нежно погладил(а) {partner}!", "level": 1, "reward": 0, "cooldown": 5},
    "прижать": {"key": "cuddle", "caption": "💕 {actor} прижал(а) к себе {partner}!", "level": 1, "reward": 0, "cooldown": 10},
    "комплимент": {"key": "compliment", "cooldown_key": "compliment", "caption": "🌷 {actor} сделал(а) {partner} комплимент! Пара получает +{reward} лепестков.", "level": 1, "reward": 15, "cooldown": 3600},
    "сделать комплимент": {"key": "compliment", "cooldown_key": "compliment", "caption": "🌷 {actor} сделал(а) {partner} комплимент! Пара получает +{reward} лепестков.", "level": 1, "reward": 15, "cooldown": 3600},
    "помочь": {"key": "help", "caption": "🤝 {actor} помог(ла) {partner}! Пара получает +{reward} лепестков.", "level": 1, "reward": 20, "cooldown": 7200},
    "подарить цветы": {"key": "flowers", "caption": "💐 {actor} подарил(а) {partner} цветы! Пара получает +{reward} лепестков.", "level": 2, "reward": 30, "cooldown": 28800},
    "свидание": {"key": "date", "caption": "🕯 {actor} пригласил(а) {partner} на свидание! Пара получает +{reward} лепестков.", "level": 2, "reward": 35, "cooldown": 43200},
    "приготовить ужин": {"key": "dinner", "caption": "🍝 {actor} приготовил(а) ужин для {partner}! Пара получает +{reward} лепестков.", "level": 3, "reward": 45, "cooldown": 43200},
    "написать письмо": {"key": "letter", "caption": "💌 {actor} написал(а) {partner} письмо! Пара получает +{reward} лепестков.", "level": 3, "reward": 50, "cooldown": 43200},
    "сюрприз": {"key": "surprise", "caption": "🎁 {actor} устроил(а) {partner} сюрприз! Пара получает +{reward} лепестков.", "level": 4, "reward": 75, "cooldown": 86400},
    "пикник": {"key": "picnic", "caption": "🧺 {actor} устроил(а) для {partner} романтический пикник! Пара получает +{reward} лепестков.", "level": 5, "reward": 90, "cooldown": 86400},
    "путешествие": {"key": "travel", "caption": "✈️ {actor} отправился(ась) с {partner} в путешествие! Пара получает +{reward} лепестков.", "level": 6, "reward": 120, "cooldown": 129600},
    "отпраздновать годовщину": {"key": "anniversary", "caption": "🎉 {actor} отпраздновал(а) годовщину с {partner}! Пара получает +{reward} лепестков.", "level": 7, "reward": 180, "cooldown": 172800},
}

HOUSES = {
    "комната": {"name": "🪴 Уютная комната", "price": 150, "income": 1},
    "домик": {"name": "🏡 Загородный домик", "price": 500, "income": 3},
    "вилла": {"name": "🌴 Вилла у моря", "price": 1200, "income": 7},
    "особняк": {"name": "🏰 Большой особняк", "price": 2500, "income": 15},
}

GIF_DATA = None


def _inject(ctx):
    for name, value in ctx.items():
        if name not in {"__name__", "__package__", "__loader__", "__spec__", "__cached__", "__builtins__"}:
            globals()[name] = value


@contextmanager
def _relationship_transaction():
    """Serialize pair mutations without performing Telegram I/O under DB locks."""
    depth = getattr(RELATIONSHIP_OUTBOX, "depth", 0)
    outermost = depth == 0
    if outermost:
        RELATIONSHIP_OUTBOX.messages = []
    RELATIONSHIP_OUTBOX.depth = depth + 1
    try:
        with RELATIONSHIPS_LOCK:
            state_lock = globals().get("db_lock")
            if state_lock is None:
                yield
            else:
                with state_lock:
                    yield
    finally:
        RELATIONSHIP_OUTBOX.depth = depth
        if outermost:
            messages = list(getattr(RELATIONSHIP_OUTBOX, "messages", []))
            RELATIONSHIP_OUTBOX.messages = []
            for message, text in messages:
                try:
                    bot.reply_to(message, text, parse_mode="HTML", disable_web_page_preview=False)
                except Exception as exc:
                    print(f"[RELATIONSHIP REPLY ERROR] {exc}")


def _safe_int(value, default=0, minimum=None, maximum=None):
    try:
        if isinstance(value, bool):
            result = int(value)
        else:
            numeric = float(value)
            if not math.isfinite(numeric):
                return default
            result = int(numeric)
    except (TypeError, ValueError, OverflowError):
        return default
    if minimum is not None:
        result = max(int(minimum), result)
    if maximum is not None:
        result = min(int(maximum), result)
    return result


def _safe_timestamp(value, default=0.0):
    try:
        result = float(value)
        return min(result, 253402300799.0) if math.isfinite(result) and result >= 0 else float(default)
    except (TypeError, ValueError, OverflowError):
        return float(default)


def _store():
    """Return a shape-safe relationship store while preserving valid records."""
    changed = False
    root = db.get("relationships") if isinstance(db, dict) else None
    if not isinstance(root, dict):
        root = {}
        db["relationships"] = root
        changed = True
    for key, expected in (("pairs", dict), ("users", dict), ("pending", dict), ("history", list), ("family_invites", dict), ("family_members", dict)):
        if not isinstance(root.get(key), expected):
            root[key] = expected()
            changed = True

    # Expire malformed and stale offers opportunistically so the pending index
    # cannot grow forever when users stop replying to old proposals.
    now = time.time()
    for target_key, proposal in list(root["pending"].items()):
        if not isinstance(proposal, dict):
            root["pending"].pop(target_key, None)
            changed = True
            continue
        from_id = _safe_int(proposal.get("from_id"), 0, minimum=1)
        to_id = _safe_int(proposal.get("to_id"), 0, minimum=1)
        created_at = _safe_timestamp(proposal.get("created_at"), 0)
        age = now - created_at
        if (not from_id or not to_id or from_id == to_id or str(to_id) != str(target_key)
                or age < 0 or age >= PROPOSAL_TTL_SECONDS):
            root["pending"].pop(target_key, None)
            changed = True
    for target_key, invite in list(root["family_invites"].items()):
        if not isinstance(invite, dict):
            root["family_invites"].pop(target_key, None)
            changed = True
            continue
        target_id = _safe_int(invite.get("to_id"), 0, minimum=1)
        pair_id = str(invite.get("pair_id") or "")
        created_at = _safe_timestamp(invite.get("created_at"), 0)
        age = now - created_at
        if (not target_id or str(target_id) != str(target_key) or not pair_id
                or age < 0 or age >= FAMILY_PLAN_TTL_SECONDS):
            root["family_invites"].pop(target_key, None)
            changed = True

    if changed:
        mark_dirty()
    return root


def _today():
    return datetime.now(timezone.utc).date().isoformat()


def _level(total_earned):
    total_earned = _safe_int(total_earned, 0, minimum=0)
    level = 1
    for index, threshold in enumerate(LEVEL_THRESHOLDS, start=1):
        if total_earned >= threshold:
            level = index
    return level


def _normalize_pair(pair_id, pair):
    """Repair malformed optional fields without discarding a valid couple."""
    changed = False

    def set_value(key, value):
        nonlocal changed
        if pair.get(key) != value:
            pair[key] = value
            changed = True

    set_value("id", str(pair_id))

    names = pair.get("names")
    if not isinstance(names, dict):
        names = {}
        set_value("names", names)

    users = pair.get("users")
    if isinstance(users, (list, tuple)):
        clean_users = []
        for raw in users:
            uid = _safe_int(raw, 0, minimum=1)
            if uid and uid not in clean_users:
                clean_users.append(uid)
    else:
        clean_users = []
    if len(clean_users) == 2:
        clean_users.sort()
        set_value("users", clean_users)

    for uid in clean_users:
        key = str(uid)
        name = names.get(key)
        if not isinstance(name, str) or not name.strip():
            names[key] = f"ID:{uid}"
            changed = True
        elif len(name) > 80:
            names[key] = name[:80]
            changed = True

    now = time.time()
    started = _safe_timestamp(pair.get("started_at"), now)
    set_value("started_at", started or now)
    set_value("petals", _safe_int(pair.get("petals"), 0, minimum=0))
    set_value("earned_total", _safe_int(pair.get("earned_total"), 0, minimum=0))
    set_value("level", _level(pair.get("earned_total", 0)))

    gif_mode = pair.get("gif_mode")
    set_value("gif_mode", gif_mode if gif_mode in {"preview", "media"} else "preview")

    protection_until = _safe_timestamp(pair.get("protection_until"), 0)
    set_value("protection_until", protection_until)

    family_plan = pair.get("family_plan")
    if isinstance(family_plan, dict):
        status = family_plan.get("status")
        if status == "pending":
            created_at = _safe_timestamp(family_plan.get("created_at"), 0)
            expires_at = _safe_timestamp(family_plan.get("expires_at"), 0)
            by = _safe_int(family_plan.get("by"), 0, minimum=1)
            if not created_at or not expires_at or not by or time.time() >= expires_at:
                set_value("family_plan", None)
            else:
                set_value("family_plan", {"status": "pending", "by": by, "created_at": created_at, "expires_at": expires_at})
        elif status == "active":
            started_at = _safe_timestamp(family_plan.get("started_at"), 0)
            due_at = _safe_timestamp(family_plan.get("due_at"), 0)
            child_name = re.sub(r"[<>\x00-\x1f\x7f]", "", str(family_plan.get("child_name") or "")).strip()[:32]
            if not started_at or not due_at or due_at <= started_at:
                set_value("family_plan", None)
            else:
                set_value("family_plan", {"status": "active", "started_at": started_at, "due_at": due_at, "child_name": child_name})
        else:
            set_value("family_plan", None)
    elif family_plan is not None:
        set_value("family_plan", None)

    cooldowns = pair.get("cooldowns")
    if not isinstance(cooldowns, dict):
        cooldowns = {}
        set_value("cooldowns", cooldowns)
    else:
        clean_cooldowns = {}
        for key, value in cooldowns.items():
            timestamp = _safe_timestamp(value, 0)
            if timestamp > 0:
                clean_cooldowns[str(key)[:64]] = timestamp
        set_value("cooldowns", clean_cooldowns)

    children = pair.get("children")
    if not isinstance(children, list):
        children = []
        set_value("children", children)
    else:
        clean_children = []
        for index, child in enumerate(children[:MAX_CHILDREN_PER_PAIR], start=1):
            if not isinstance(child, dict):
                changed = True
                continue
            normalized_child = {
                "id": index,
                "name": str(child.get("name") or "Ребёнок")[:32],
                "born_at": _safe_timestamp(child.get("born_at"), now) or now,
                "happiness": _safe_int(child.get("happiness"), 50, minimum=0, maximum=100),
                "last_care_at": _safe_timestamp(child.get("last_care_at"), 0),
            }
            member_id = _safe_int(child.get("member_id"), 0, minimum=1)
            if member_id:
                normalized_child["member_id"] = member_id
                normalized_child["kind"] = "consenting_member"
            elif child.get("kind") == "virtual":
                normalized_child["kind"] = "virtual"
            clean_children.append(normalized_child)
            if clean_children[-1] != child:
                changed = True
        if clean_children != children:
            set_value("children", clean_children)

    house = pair.get("house")
    if not isinstance(house, str) or house not in HOUSES:
        set_value("house", None)
    set_value("last_house_income_at", _safe_timestamp(pair.get("last_house_income_at"), now) or now)

    gifts = pair.get("gifts")
    if not isinstance(gifts, list):
        gifts = []
        set_value("gifts", gifts)
    else:
        clean_gifts = [item for item in gifts[-MAX_GIFT_HISTORY:] if isinstance(item, dict)]
        set_value("gifts", clean_gifts)

    task = pair.get("daily_task")
    valid_kinds = {"earn", "actions", "care"}
    if not isinstance(task, dict) or task.get("kind") not in valid_kinds:
        set_value("daily_task", None)
    else:
        normalized_task = {
            "kind": task["kind"],
            "title": str(task.get("title") or "Ежедневное задание")[:120],
            "target": _safe_int(task.get("target"), 1, minimum=1, maximum=10000),
            "reward": _safe_int(task.get("reward"), 0, minimum=0, maximum=100000),
            "date": str(task.get("date") or "")[:10],
            "progress": _safe_int(task.get("progress"), 0, minimum=0),
            "claimed": bool(task.get("claimed", False)),
        }
        normalized_task["progress"] = min(normalized_task["target"], normalized_task["progress"])
        set_value("daily_task", normalized_task)

    breakup = pair.get("breakup_confirmation")
    if isinstance(breakup, dict):
        normalized_breakup = {
            "by": _safe_int(breakup.get("by"), 0, minimum=1),
            "at": _safe_timestamp(breakup.get("at"), 0),
        }
        if not normalized_breakup["by"] or not normalized_breakup["at"]:
            set_value("breakup_confirmation", None)
        else:
            set_value("breakup_confirmation", normalized_breakup)
    elif breakup is not None:
        set_value("breakup_confirmation", None)

    if changed:
        mark_dirty()
    return pair


def _pair_for(user_id):
    uid = _safe_int(user_id, 0, minimum=1)
    if not uid:
        return None
    root = _store()
    user_key = str(uid)
    pair_id = root["users"].get(user_key)
    pair = root["pairs"].get(str(pair_id)) if pair_id else None
    if not isinstance(pair, dict):
        if pair_id is not None:
            root["users"].pop(user_key, None)
            mark_dirty()
        return None
    raw_users = pair.get("users")
    if not isinstance(raw_users, (list, tuple)):
        return None
    users = []
    for raw in raw_users:
        clean_uid = _safe_int(raw, 0, minimum=1)
        if clean_uid and clean_uid not in users:
            users.append(clean_uid)
    if len(users) != 2 or uid not in users:
        root["users"].pop(user_key, None)
        mark_dirty()
        return None

    # Repair a missing reverse index, but never overwrite a partner who already
    # belongs to a different active pair in a damaged database snapshot.
    changed = False
    for partner_uid in users:
        partner_key = str(partner_uid)
        mapped_pair = root["users"].get(partner_key)
        if mapped_pair is None:
            root["users"][partner_key] = str(pair_id)
            changed = True
        elif str(mapped_pair) != str(pair_id):
            if str(mapped_pair) not in root["pairs"]:
                root["users"].pop(partner_key, None)
                root["users"][partner_key] = str(pair_id)
                changed = True
            else:
                root["users"].pop(user_key, None)
                mark_dirty()
                return None
    if changed:
        mark_dirty()
    return _normalize_pair(str(pair_id), pair)


def _user_name(user_id, fallback=None):
    econ = get_user_econ(user_id=int(user_id))
    return str(econ.get("display_name") or econ.get("name") or fallback or f"ID:{user_id}")


def _resolve_target(message, raw=""):
    reply = getattr(message, "reply_to_message", None)
    if reply and getattr(reply, "from_user", None):
        user = reply.from_user
        name = (f"{user.first_name or ''} {user.last_name or ''}").strip() or user.username or f"ID:{user.id}"
        return int(user.id), name, bool(getattr(user, "is_bot", False))
    raw = (raw or "").strip()
    if not raw:
        return None, None, False
    uid, name = resolve_user_from_string(message.chat.id, raw)
    return (int(uid), name or raw.lstrip("@"), False) if uid else (None, None, False)


def _pair_names(pair):
    names = pair.get("names", {}) if isinstance(pair.get("names"), dict) else {}
    ids = [int(x) for x in pair.get("users", [])]
    return ids, {uid: str(names.get(str(uid)) or _user_name(uid)) for uid in ids}


def _partner_id(pair, user_id):
    for uid in pair.get("users", []):
        if int(uid) != int(user_id):
            return int(uid)
    return None


def _gender(user_id):
    try:
        value = get_user_econ(user_id=int(user_id)).get("relationship_gender")
    except (TypeError, ValueError, OverflowError, AttributeError):
        return None
    # Corrupt economy rows can contain lists/dicts here; only exact strings are valid.
    return value if isinstance(value, str) and value in {"male", "female"} else None


def _pair_type(pair):
    ids = [int(x) for x in pair.get("users", [])]
    genders = [_gender(uid) for uid in ids]
    if None in genders:
        return "generic"
    if genders[0] != genders[1]:
        return "male_female"
    return "male_male" if genders[0] == "male" else "female_female"


def _load_gifs():
    global GIF_DATA
    if GIF_DATA is not None:
        return GIF_DATA
    try:
        with open(RELATIONSHIP_GIF_FILE, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        GIF_DATA = payload if isinstance(payload, dict) else {}
    except (OSError, ValueError, TypeError):
        GIF_DATA = {}
    return GIF_DATA


def _get_gif(action_key, pair):
    data = _load_gifs()
    pair_type = _pair_type(pair)
    assets = data.get(pair_type, {}) if isinstance(data.get(pair_type), dict) else {}
    generic_assets = data.get("generic", {})
    if not isinstance(generic_assets, dict):
        generic_assets = {}
    candidates = assets.get(action_key) or generic_assets.get(action_key) or []
    if isinstance(candidates, (str, dict)):
        candidates = [candidates]
    if not isinstance(candidates, list):
        return None
    valid = []
    for item in candidates:
        if isinstance(item, str) and item.strip():
            valid.append(item.strip())
        elif isinstance(item, dict) and (item.get("url") or item.get("preview_url") or item.get("media_url") or item.get("file_id")):
            valid.append(item)
    if not valid:
        return None
    selected = random.choice(valid)
    if isinstance(selected, dict):
        selected = dict(selected)
        if pair.get("gif_mode", "preview") == "media":
            media_url = selected.get("media_url")
            if media_url:
                return {"url": media_url, "mode": "media"}
            if selected.get("file_id"):
                return selected
        preview_url = selected.get("preview_url") or selected.get("url")
        if preview_url:
            return {
                "url": preview_url,
                "mode": "preview",
                "fallback_media_url": selected.get("media_url"),
            }
    return selected


def _progress_task(pair, kind, amount=1):
    task = pair.get("daily_task")
    if not isinstance(task, dict) or task.get("date") != _today() or task.get("claimed"):
        return
    if task.get("kind") == kind:
        task["progress"] = min(int(task.get("target", 1)), int(task.get("progress", 0)) + int(amount))


def _ensure_daily_task(pair):
    task = pair.get("daily_task")
    if isinstance(task, dict) and task.get("date") == _today():
        return task
    tasks = [
        {"kind": "earn", "title": "Заработайте вместе 30 лепестков", "target": 30, "reward": 12},
        {"kind": "actions", "title": "Совершите 2 совместных действия", "target": 2, "reward": 10},
    ]
    if pair.get("children"):
        tasks.append({"kind": "care", "title": "Позаботьтесь о ребёнке", "target": 1, "reward": 15})
    chosen = random.choice(tasks)
    task = {**chosen, "date": _today(), "progress": 0, "claimed": False}
    pair["daily_task"] = task
    mark_dirty()
    return task


def _credit(pair, amount):
    amount = max(0, int(amount))
    if amount <= 0:
        return 0, _level(pair.get("earned_total", 0))
    old_level = _level(pair.get("earned_total", 0))
    pair["petals"] = int(pair.get("petals", 0) or 0) + amount
    pair["earned_total"] = int(pair.get("earned_total", 0) or 0) + amount
    pair["level"] = _level(pair["earned_total"])
    _progress_task(pair, "earn", amount)
    return amount, old_level


def _calculate_house_income(pair):
    house_data = HOUSES.get(pair.get("house"))
    if not house_data:
        return 0
    now = time.time()
    last = _safe_timestamp(pair.get("last_house_income_at"), now) or now
    # Cap offline accrual so a dormant pair cannot collect unlimited income.
    hours = max(0.0, min(72.0, (now - last) / 3600.0))
    rate = _safe_int(house_data.get("income"), 0, minimum=0)
    if rate <= 0:
        return 0
    earned = max(0, int(hours * rate))
    # Preserve fractional progress to the next whole hourly payout.
    fractional_hours = max(0.0, hours - (earned / rate))
    new_last = now - (fractional_hours * 3600.0)
    pair["last_house_income_at"] = new_last
    if earned:
        _credit(pair, earned)
        # House income can be triggered by a read-only profile command. Persist it
        # here rather than depending on a later purchase/action to mark state dirty.
        mark_dirty()
    return earned


def _pair_profile_text(pair, user_id, chat_id):
    ids, names = _pair_names(pair)
    partner_id = _partner_id(pair, user_id)
    gender_labels = {"male": "мужской", "female": "женский", None: "не указан"}
    my_gender = gender_labels.get(_gender(user_id), "не указан")
    partner_gender = gender_labels.get(_gender(partner_id), "не указан")
    started = datetime.fromtimestamp(float(pair.get("started_at", time.time())), timezone.utc).strftime("%d.%m.%Y")
    days = max(1, int((time.time() - float(pair.get("started_at", time.time()))) / 86400) + 1)
    earned = int(pair.get("earned_total", 0) or 0)
    level = _level(earned)
    house = HOUSES.get(pair.get("house"), {}).get("name", "пока нет")
    children = pair.get("children", []) if isinstance(pair.get("children"), list) else []
    return (
        "💞 <b>ПРОФИЛЬ ОТНОШЕНИЙ</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Вы: {html.escape(str(names.get(int(user_id)) or _user_name(user_id)))} · {my_gender}\n"
        f"💗 Партнёр: {make_link(chat_id, names.get(partner_id) or _user_name(partner_id), partner_id, ping=False)} · {partner_gender}\n"
        f"📅 Вместе с: <b>{started}</b> · <b>{days} дн.</b>\n"
        f"⭐ Уровень пары: <b>{level}</b>\n"
        f"🌸 Баланс: <b>{int(pair.get('petals', 0) or 0)} лепестков</b>\n"
        f"🌺 Всего заработано: <b>{earned} лепестков</b>\n"
        f"🏡 Дом: <b>{house}</b>\n"
        f"👶 Детей: <b>{len(children)}</b>\n"
        f"🖼 GIF: <b>{'превью-ссылка' if pair.get('gif_mode', 'preview') == 'preview' else 'медиа'}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Команды: <code>отн действия</code>, <code>отн задания</code>, "
        "<code>отн дети</code>, <code>отн планирование</code>, <code>отн дом</code>, <code>отн магазин</code>"
    )


def _help_text():
    return (
        "💞 <b>СИСТЕМА ОТНОШЕНИЙ</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💌 <code>отн предложить @username</code> — предложить отношения\n"
        "💗 <code>отн принять</code> / <code>отн отказать</code> — ответить на предложение\n"
        "✉️ <code>отн отменить</code> — отменить своё исходящее предложение\n"
        "👤 <code>отн профиль</code> — профиль вашей пары\n"
        "⚧ <code>отн пол мужчина</code> или <code>отн пол женщина</code> — указать пол для подбора GIF\n"
        "🎭 <code>отн действия</code> — список доступных RP-действий\n"
        "🖼 <code>отн гиф превью</code> / <code>отн гиф медиа</code> — карточка со ссылкой или вложенная GIF-анимация\n"
        "🌷 <code>отн сделать комплимент</code> — +15 лепестков раз в час\n"
        "🌸 <code>отн задания</code> / <code>отн забрать награду</code> — ежедневное задание\n"
        "👶 <code>отн планировать ребёнка</code> — предложить совместное семейное планирование\n"
        "🤝 <code>отн планирование принять</code> / <code>отн планирование отказать</code> — ответить на предложение\n"
        "🕒 <code>отн беременность</code> / <code>отн родить</code> — статус и завершение игрового семейного таймера (40 часов)\n"
        "🧸 <code>отн дети</code> / <code>отн ребёнок имя Мира</code> / <code>отн ребёнок забота</code> — воспитывать детей\n"
        "🛡 <code>отн защита купить</code> / <code>отн контрацептив купить</code> — игровой предмет защиты на 48 часов\n"
        "👨‍👩‍👧 <code>отн в семью @username</code> или ответом на сообщение — приглашение в семью; <code>отн родить @username</code> — тот же запрос\n"
        "✅ <code>отн принять в семью</code> / <code>отн отказаться от семьи</code> / <code>отн выйти из семьи</code> — управление участием\n"
        "🏡 <code>отн дом</code> / <code>отн дом купить домик</code> — общий дом\n"
        "🎁 <code>отн магазин</code> / <code>отн подарок розы</code> — подарки\n"
        "📜 <code>отн подарки</code> — история подарков пары\n"
        "📖 <code>отн история</code> — архив завершённых отношений\n"
        "💔 <code>отн расстаться</code> — запросить завершение отношений\n"
        "⚠️ <code>отн расстаться подтвердить</code> — подтвердить завершение\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Уровень растёт от общего количества заработанных лепестков. Потраченные лепестки не отнимают уровень."
    )


def _reply(message, text):
    # Many commands reply from inside a shared-state transaction. Queue those
    # messages so a slow Telegram API call never holds db_lock/RELATIONSHIPS_LOCK.
    if getattr(RELATIONSHIP_OUTBOX, "depth", 0) > 0:
        RELATIONSHIP_OUTBOX.messages.append((message, text))
        return
    bot.reply_to(message, text, parse_mode="HTML", disable_web_page_preview=False)


def _handle_proposal(message, args, user_id, user_name):
    target_id, target_name, is_bot = _resolve_target(message, args)
    if not target_id:
        _reply(message, "Укажи пользователя через @username или ответь на его сообщение: <code>отн предложить @username</code>.")
        return
    if target_id == user_id or is_bot:
        _reply(message, "❌ Нельзя начать отношения с собой или ботом.")
        return
    with _relationship_transaction():
        if _pair_for(user_id):
            _reply(message, "❌ У тебя уже есть отношения. Сначала заверши их командой <code>отн расстаться</code>.")
            return
        if _pair_for(target_id):
            _reply(message, f"❌ {html.escape(target_name)} уже состоит в отношениях.")
            return
        root = _store()
        now = time.time()
        pending = root["pending"].get(str(target_id))
        if isinstance(pending, dict):
            created_at = _safe_timestamp(pending.get("created_at"), 0)
            age = now - created_at
            if 0 <= age < PROPOSAL_TTL_SECONDS:
                _reply(message, "У этого пользователя уже есть неотвеченное предложение.")
                return
            root["pending"].pop(str(target_id), None)

        # One outstanding proposal per sender avoids accidental spam and
        # guarantees a predictable accept/cancel flow.
        for target_key, proposal in list(root["pending"].items()):
            if not isinstance(proposal, dict):
                root["pending"].pop(target_key, None)
                continue
            if _safe_int(proposal.get("from_id"), 0) != int(user_id):
                continue
            proposal_age = now - _safe_timestamp(proposal.get("created_at"), 0)
            if 0 <= proposal_age < PROPOSAL_TTL_SECONDS:
                _reply(message, "У тебя уже есть исходящее предложение. Напиши <code>отн отменить</code> или дождись ответа.")
                return
            root["pending"].pop(target_key, None)
        root["pending"][str(target_id)] = {
            "from_id": int(user_id), "from_name": user_name,
            "to_id": int(target_id), "to_name": target_name,
            "chat_id": int(message.chat.id), "created_at": time.time(),
        }
        mark_dirty()
    _reply(message, f"💌 {make_link(message.chat.id, user_name, user_id, ping=True)} предложил(а) отношения {make_link(message.chat.id, target_name, target_id, ping=True)}!\n\nЧтобы принять предложение, напиши <code>отн принять</code>. Для отказа — <code>отн отказать</code>. Предложение действует 24 часа.")


def _accept_proposal(message, user_id, user_name):
    with _relationship_transaction():
        root = _store()
        pending = root["pending"].get(str(user_id))
        created_at = _safe_timestamp(pending.get("created_at"), 0) if isinstance(pending, dict) else 0
        age = time.time() - created_at
        if not isinstance(pending, dict) or age < 0 or age >= PROPOSAL_TTL_SECONDS:
            root["pending"].pop(str(user_id), None)
            mark_dirty()
            _reply(message, "💌 У тебя нет действующего предложения отношений.")
            return
        if _safe_int(pending.get("to_id"), 0) != int(user_id):
            root["pending"].pop(str(user_id), None)
            mark_dirty()
            _reply(message, "❌ Предложение повреждено или больше не действительно.")
            return
        from_id = _safe_int(pending.get("from_id"), 0, minimum=1)
        if not from_id or from_id == int(user_id) or _pair_for(user_id) or _pair_for(from_id):
            root["pending"].pop(str(user_id), None)
            mark_dirty()
            _reply(message, "❌ Предложение уже нельзя принять: один из пользователей состоит в отношениях.")
            return
        ids = sorted([from_id, int(user_id)])
        pair_id = f"{ids[0]}:{ids[1]}"
        pair = {
            "id": pair_id, "users": ids,
            "names": {str(from_id): str(pending.get("from_name") or _user_name(from_id)), str(user_id): user_name},
            "started_at": time.time(), "petals": 0, "earned_total": 0, "level": 1,
            "cooldowns": {}, "children": [], "house": None, "last_house_income_at": time.time(),
            "gifts": [], "daily_task": None, "gif_mode": "preview", "protection_until": 0,
            "family_plan": None,
        }
        root["pairs"][pair_id] = pair
        root["users"][str(from_id)] = pair_id
        root["users"][str(user_id)] = pair_id
        # Starting a pair invalidates every pending proposal involving either member.
        for target_key, proposal in list(root["pending"].items()):
            if not isinstance(proposal, dict):
                root["pending"].pop(target_key, None)
                continue
            proposal_from = _safe_int(proposal.get("from_id"), 0)
            proposal_to = _safe_int(proposal.get("to_id"), 0)
            if proposal_from in ids or proposal_to in ids:
                root["pending"].pop(target_key, None)
        mark_dirty()
    _reply(message, f"💞 <b>Отношения начались!</b>\n{make_link(message.chat.id, pending.get('from_name') or 'Пользователь', from_id, ping=True)} и {make_link(message.chat.id, user_name, user_id, ping=True)} теперь пара.\n\nПервый уровень открыт. Используйте <code>отн профиль</code> и <code>отн действия</code>.")


def _end_relationship(message, user_id, confirm=False):
    """End a relationship only after an explicit second confirmation.

    Finished pairs are archived so their history, children and achievements do
    not disappear from persistent storage when someone mistypes the command.
    """
    user_id = int(user_id)
    with _relationship_transaction():
        root = _store()
        pair = _pair_for(user_id)
        if not pair:
            _reply(message, "У тебя сейчас нет отношений.")
            return

        pending = pair.get("breakup_confirmation")
        now = time.time()
        if not confirm:
            pair["breakup_confirmation"] = {"by": user_id, "at": now}
            mark_dirty()
            _reply(
                message,
                "⚠️ <b>Подтверди расставание</b>\n"
                "Это завершит активные отношения. Дом, дети, баланс и подарки будут сохранены в истории пары, "
                "но использовать их дальше будет нельзя.\n\n"
                "Для подтверждения в течение 2 минут напиши: <code>отн расстаться подтвердить</code>.",
            )
            return

        confirmed_by = _safe_int(pending.get("by"), 0, minimum=1) if isinstance(pending, dict) else 0
        confirmed_at = _safe_timestamp(pending.get("at"), 0) if isinstance(pending, dict) else 0
        if confirmed_by != user_id or not confirmed_at or now - confirmed_at < 0 or now - confirmed_at > BREAKUP_CONFIRM_TTL_SECONDS:
            pair["breakup_confirmation"] = None
            mark_dirty()
            _reply(message, "Подтверждение не найдено или истекло. Для начала напиши <code>отн расстаться</code>.")
            return

        _calculate_house_income(pair)
        ids = [int(x) for x in pair.get("users", [])]
        pair_id = str(pair.get("id"))
        archived = copy.deepcopy(pair)
        archived["ended_at"] = now
        archived["ended_by"] = user_id
        archived["breakup_confirmation"] = None
        root["history"].append(archived)
        if len(root["history"]) > MAX_RELATIONSHIP_HISTORY:
            del root["history"][:-MAX_RELATIONSHIP_HISTORY]
        for uid in ids:
            root["users"].pop(str(uid), None)
        for child in archived.get("children", []):
            if isinstance(child, dict) and child.get("member_id"):
                member_key = str(_safe_int(child.get("member_id"), 0, minimum=1))
                if member_key != "0" and root.get("family_members", {}).get(member_key) == pair_id:
                    root["family_members"].pop(member_key, None)
        root["pairs"].pop(pair_id, None)
        # Remove pending family invitations so former partners cannot invite
        # someone into a relationship that has already been archived.
        for target_key, invite in list(root["family_invites"].items()):
            if isinstance(invite, dict) and str(invite.get("pair_id")) == pair_id:
                root["family_invites"].pop(target_key, None)
        # Discard outstanding proposals involving either former partner.
        for target_key, proposal in list(root["pending"].items()):
            if not isinstance(proposal, dict):
                root["pending"].pop(target_key, None)
                continue
            from_id = _safe_int(proposal.get("from_id"), 0)
            to_id = _safe_int(proposal.get("to_id"), 0)
            if from_id in ids or to_id in ids:
                root["pending"].pop(target_key, None)
        mark_dirty()

    _reply(message, "💔 Отношения завершены. История пары, дом, дети, подарки и достижения сохранены в архиве.")


def _relationship_history(message, user_id):
    with _relationship_transaction():
        rows = []
        for pair in _store()["history"]:
            if not isinstance(pair, dict):
                continue
            users = pair.get("users")
            if isinstance(users, (list, tuple)) and user_id in [_safe_int(x, 0) for x in users]:
                rows.append(pair)
        rows = rows[-5:]
        if not rows:
            _reply(message, "📖 У тебя пока нет завершённых отношений.")
            return
        lines = ["📖 <b>ИСТОРИЯ ОТНОШЕНИЙ</b>", "━━━━━━━━━━━━━━━━━━━━"]
        for pair in reversed(rows):
            users = [_safe_int(x, 0) for x in pair.get("users", [])]
            names = pair.get("names", {}) if isinstance(pair.get("names"), dict) else {}
            partner_id = next((uid for uid in users if uid != user_id), 0)
            partner_name = str(names.get(str(partner_id)) or f"ID:{partner_id}")
            started = datetime.fromtimestamp(_safe_timestamp(pair.get("started_at"), time.time()), timezone.utc).strftime("%d.%m.%Y")
            ended = datetime.fromtimestamp(_safe_timestamp(pair.get("ended_at"), time.time()), timezone.utc).strftime("%d.%m.%Y")
            earned = _safe_int(pair.get("earned_total"), 0, minimum=0)
            children = len(pair.get("children", [])) if isinstance(pair.get("children"), list) else 0
            lines.append(
                f"• {html.escape(partner_name)} · {started} — {ended} · "
                f"заработано {earned} лепестков · детей: {children}"
            )
        _reply(message, "\n".join(lines))


def _valid_media_url(value):
    if not isinstance(value, str) or len(value) > 2048:
        return False
    if any(ch.isspace() or ord(ch) < 32 or ord(ch) == 127 for ch in value):
        return False
    try:
        parsed = urlsplit(value)
        # Accessing .port also validates malformed ports (urlsplit can defer this error).
        _ = parsed.port
        return (
            parsed.scheme.lower() in {"http", "https"}
            and bool(parsed.hostname)
            and not parsed.username
            and not parsed.password
        )
    except ValueError:
        return False


def _send_action_media(message, asset, caption):
    """Send an animation file_id/direct media URL or a clickable page preview."""
    if isinstance(asset, dict):
        asset_data = dict(asset)
        file_id = asset.get("file_id")
        url = asset.get("url") or asset.get("preview_url")
        mode = str(asset.get("mode") or "").lower()
        if (isinstance(file_id, str) and file_id.strip() and len(file_id) <= 512
                and not any(ch.isspace() or ord(ch) < 32 for ch in file_id)):
            bot.send_animation(
                message.chat.id, file_id.strip(), caption=caption, parse_mode="HTML",
                reply_to_message_id=message.message_id,
            )
            return
        if not _valid_media_url(url):
            raise ValueError("GIF catalog entry must contain a valid http(s) url or Telegram file_id")
        asset = url.strip()
        if mode == "preview":
            try:
                bot.send_message(
                    message.chat.id, f"{caption}\n{html.escape(asset)}",
                    parse_mode="HTML", disable_web_page_preview=False,
                    reply_to_message_id=message.message_id,
                )
                return
            except Exception:
                # If Telegram rejects the page preview, try its direct media URL
                # before falling back to a text-only action in the caller.
                fallback_media = asset_data.get("fallback_media_url") if isinstance(asset_data, dict) else None
                if not _valid_media_url(fallback_media) or not urlsplit(fallback_media).path.lower().endswith((".gif", ".mp4", ".m4v")):
                    raise
                bot.send_animation(
                    message.chat.id, fallback_media, caption=caption, parse_mode="HTML",
                    reply_to_message_id=message.message_id,
                )
                return
    if not isinstance(asset, str) or not asset.strip():
        raise ValueError("Empty relationship GIF asset")
    asset = asset.strip()
    if asset.lower().startswith(("https://", "http://")):
        if not _valid_media_url(asset):
            raise ValueError("Invalid relationship media URL")
        path = urlsplit(asset).path.lower()
        if not path.endswith((".gif", ".mp4", ".m4v")):
            bot.send_message(
                message.chat.id, f"{caption}\n{html.escape(asset)}",
                parse_mode="HTML", disable_web_page_preview=False,
                reply_to_message_id=message.message_id,
            )
            return
    elif len(asset) > 512 or any(ch.isspace() or ord(ch) < 32 for ch in asset) or "://" in asset:
        raise ValueError("Invalid Telegram animation file_id")
    bot.send_animation(
        message.chat.id, asset, caption=caption, parse_mode="HTML",
        reply_to_message_id=message.message_id,
    )


def _do_action(message, action_name, user_id, user_name):
    action = ACTIONS[action_name]
    with _relationship_transaction():
        pair = _pair_for(user_id)
        if not pair:
            _reply(message, "Для RP-действий сначала нужны отношения. Напиши <code>отн предложить @username</code>.")
            return
        _calculate_house_income(pair)
        level = _level(pair.get("earned_total", 0))
        if level < int(action["level"]):
            _reply(message, f"🔒 Команда откроется на {action['level']}-м уровне пары. Сейчас уровень: {level}.")
            return
        now = time.time()
        cooldown_key = action.get("cooldown_key") or action_name
        cooldown_until = float(pair.setdefault("cooldowns", {}).get(cooldown_key, 0) or 0)
        if cooldown_until > now:
            remaining = int(cooldown_until - now)
            hours, rem = divmod(remaining, 3600)
            minutes = rem // 60
            seconds = rem % 60
            wait = f"{hours} ч. {minutes} мин." if hours else (f"{minutes} мин. {seconds} сек." if minutes else f"{seconds} сек.")
            _reply(message, f"⏳ Это действие пока на перезарядке. Осталось: <b>{wait}</b>.")
            return
        pair["cooldowns"][cooldown_key] = now + int(action["cooldown"])
        reward = int(action["reward"])
        old_level = _level(pair.get("earned_total", 0))
        if reward:
            _credit(pair, reward)
        _progress_task(pair, "actions", 1)
        partner_id = _partner_id(pair, user_id)
        partner_name = _user_name(partner_id)
        mark_dirty()
        new_level = _level(pair.get("earned_total", 0))
        new_balance = _safe_int(pair.get("petals"), 0, minimum=0)
        caption = action["caption"].format(actor=html.escape(user_name), partner=html.escape(partner_name), reward=reward)
        asset = _get_gif(action["key"], pair)
    if asset:
        try:
            _send_action_media(message, asset, caption)
        except Exception as exc:
            print(f"[RELATIONSHIP GIF] Could not send configured asset {action['key']}: {exc}")
            _reply(message, caption)
    else:
        _reply(message, caption)
    if reward:
        _reply(message, f"🌸 +<b>{reward} лепестков</b> на общий счёт пары. Баланс: <b>{new_balance}</b>.")
    if new_level > old_level:
        _reply(message, f"🎉 <b>Новый уровень пары: {new_level}!</b> Открылись новые действия. Напишите <code>отн действия</code>.")


def _actions_list(pair, user_id):
    level = _level(pair.get("earned_total", 0))
    lines = ["🎭 <b>ДЕЙСТВИЯ ОТНОШЕНИЙ</b>", "━━━━━━━━━━━━━━━━━━━━"]
    descriptions = {
        "чмок": "ур. 1 · без награды", "обнять": "ур. 1 · без награды", "поцеловать": "ур. 1 · без награды",
        "укусить": "ур. 1 · без награды", "погладить": "ур. 1 · без награды", "прижать": "ур. 1 · без награды",
        "сделать комплимент": "ур. 1 · +15 лепестков · раз в час", "помочь": "ур. 1 · +20 лепестков · раз в 2 ч.",
        "подарить цветы": "ур. 2 · +30 лепестков · раз в 8 ч.", "свидание": "ур. 2 · +35 лепестков · раз в 12 ч.",
        "приготовить ужин": "ур. 3 · +45 лепестков · раз в 12 ч.", "написать письмо": "ур. 3 · +50 лепестков · раз в 12 ч.",
        "сюрприз": "ур. 4 · +75 лепестков · раз в сутки",
        "пикник": "ур. 5 · +90 лепестков · раз в сутки",
        "путешествие": "ур. 6 · +120 лепестков · раз в 36 ч.",
        "отпраздновать годовщину": "ур. 7 · +180 лепестков · раз в 48 ч.",
    }
    for name, description in descriptions.items():
        required = int(ACTIONS[name]["level"])
        marker = "✅" if level >= required else "🔒"
        lines.append(f"{marker} <code>отн {name}</code> — {description}")
    if level >= len(LEVEL_THRESHOLDS):
        lines.append(f"\nТекущий уровень: <b>{level}</b> · достигнут максимальный уровень.")
    else:
        remaining = max(0, LEVEL_THRESHOLDS[level] - int(pair.get("earned_total", 0) or 0))
        lines.append(f"\nТекущий уровень: <b>{level}</b>. До следующего уровня: <b>{remaining}</b> лепестков.")
    return "\n".join(lines)


def _daily_task(message, pair, command):
    task = _ensure_daily_task(pair)
    if command == "забрать награду":
        if task.get("claimed"):
            _reply(message, "Награда за сегодняшнее задание уже получена.")
            return
        if int(task.get("progress", 0)) < int(task.get("target", 1)):
            _reply(message, f"Задание ещё не выполнено: {task.get('progress', 0)}/{task.get('target', 1)}.")
            return
        reward = int(task.get("reward", 0))
        task["claimed"] = True
        old_level = _level(pair.get("earned_total", 0))
        _credit(pair, reward)
        mark_dirty()
        new_level = _level(pair.get("earned_total", 0))
        _reply(message, f"🎉 Задание выполнено! Пара получает +<b>{reward} лепестков</b>.")
        if new_level > old_level:
            _reply(message, f"⭐ Поздравляем! Теперь у пары {new_level}-й уровень.")
        return
    status = "получено" if task.get("claimed") else f"{int(task.get('progress', 0))}/{int(task.get('target', 1))}"
    _reply(message, f"🌸 <b>ЕЖЕДНЕВНОЕ ЗАДАНИЕ</b>\n{html.escape(str(task.get('title', 'Задание')))}\nПрогресс: <b>{status}</b>\nНаграда: <b>{int(task.get('reward', 0))} лепестков</b>\n\nПосле выполнения: <code>отн забрать награду</code>")


def _children_command(message, pair, user_id, command):
    """Show and care for children; births are gated by a mutual 40-hour plan."""
    children = pair.setdefault("children", [])
    normalized = str(command or "").strip()
    lower = normalized.lower()

    if lower.startswith("завести"):
        _reply(
            message,
            "👶 Теперь ребёнок появляется после совместного семейного планирования. "
            "Начните с <code>отн планировать ребёнка</code>, дождитесь подтверждения партнёра, "
            "а имя задайте командой <code>отн ребёнок имя Мира</code>.",
        )
        return

    if lower.startswith("имя"):
        family_plan = pair.get("family_plan")
        name = normalized[len("имя"):].strip()
        if not isinstance(family_plan, dict) or family_plan.get("status") != "active":
            _reply(message, "Сначала начните и подтвердите семейное планирование: <code>отн планировать ребёнка</code>.")
            return
        clean_name = re.sub(r"[<>\x00-\x1f\x7f]", "", name)[:32].strip()
        if not clean_name:
            _reply(message, "Укажи имя: <code>отн ребёнок имя Мира</code>.")
            return
        family_plan["child_name"] = clean_name
        mark_dirty()
        _reply(message, f"✅ Имя будущего ребёнка сохранено: <b>{html.escape(clean_name)}</b>.")
        return

    if lower == "родить":
        family_plan = pair.get("family_plan")
        if not isinstance(family_plan, dict) or family_plan.get("status") != "active":
            _reply(message, "Пока нет активного семейного планирования. Команда: <code>отн планировать ребёнка</code>.")
            return
        if len(children) >= MAX_CHILDREN_PER_PAIR:
            _reply(message, "У пары уже максимум — 3 ребёнка.")
            return
        now = time.time()
        due_at = _safe_timestamp(family_plan.get("due_at"), 0)
        remaining = due_at - now
        if remaining > 0:
            hours = max(1, math.ceil(remaining / 3600))
            weeks = min(40, int(max(0, now - _safe_timestamp(family_plan.get("started_at"), now)) // 3600))
            _reply(message, f"🕒 Ещё рано. Игровой срок: {weeks}/40 недель. Осталось примерно {hours} ч.")
            return
        cost = 80
        if _safe_int(pair.get("petals"), 0, minimum=0) < cost:
            _reply(message, f"Срок завершён, но на семейные расходы нужно {cost} лепестков. Пополните общий счёт и повторите <code>отн родить</code>.")
            return
        pair["petals"] = _safe_int(pair.get("petals"), 0, minimum=0) - cost
        child_name = str(family_plan.get("child_name") or "Малыш").strip()[:32] or "Малыш"
        child_id = len(children) + 1
        children.append({
            "id": child_id,
            "name": child_name,
            "born_at": now,
            "happiness": 50,
            "last_care_at": 0,
            "kind": "virtual",
        })
        pair["family_plan"] = None
        _progress_task(pair, "care", 1)
        mark_dirty()
        _reply(message, f"🎉 В семье пополнение! Добро пожаловать, <b>{html.escape(child_name)}</b>. Потрачено 80 лепестков на семейные расходы. Используйте <code>отн дети</code> и <code>отн ребёнок забота</code>.")
        return

    if lower.startswith("забота"):
        if not children:
            _reply(message, "У пары пока нет детей. Начните с <code>отн планировать ребёнка</code>.")
            return
        try:
            index = int(lower[len("забота"):].strip() or "1") - 1
        except ValueError:
            index = 0
        if index < 0 or index >= len(children):
            _reply(message, "Такого ребёнка нет. Посмотри список: <code>отн дети</code>.")
            return
        child = children[index]
        now = time.time()
        remaining = float(child.get("last_care_at", 0) or 0) + 43200 - now
        if remaining > 0:
            _reply(message, f"🧸 Ребёнку пока хватает заботы. Попробуйте через {max(1, int(remaining // 3600))} ч.")
            return
        child["happiness"] = min(100, int(child.get("happiness", 50)) + 15)
        child["last_care_at"] = now
        _progress_task(pair, "care", 1)
        mark_dirty()
        _reply(message, f"🧸 Вы позаботились о <b>{html.escape(str(child.get('name', 'ребёнок')))}</b>! Счастье: {child['happiness']}/100.")
        return

    lines = ["👶 <b>ДЕТИ ВАШЕЙ ПАРЫ</b>", "━━━━━━━━━━━━━━━━━━━━"]
    if not children:
        lines.append("Пока детей нет. Команда: <code>отн планировать ребёнка</code>.")
    for child in children:
        if not isinstance(child, dict):
            continue
        if child.get("member_id"):
            stage = "участник семьи"
            age_days = None
        else:
            age_days = max(0, int((time.time() - _safe_timestamp(child.get("born_at"), time.time())) / 86400))
            if age_days < 7:
                stage = "младенец"
            elif age_days < 30:
                stage = "малыш"
            elif age_days < 90:
                stage = "ребёнок"
            elif age_days < 180:
                stage = "подросток"
            else:
                stage = "взрослый"
        age_text = "" if age_days is None else f" · возраст {age_days} дн."
        lines.append(
            f"• <b>{html.escape(str(child.get('name', 'Ребёнок')))}</b> · {stage}{age_text} · "
            f"счастье {_safe_int(child.get('happiness'), 50, minimum=0, maximum=100)}/100"
        )

    family_plan = pair.get("family_plan")
    if isinstance(family_plan, dict) and family_plan.get("status") == "active":
        now = time.time()
        started = _safe_timestamp(family_plan.get("started_at"), now)
        due = _safe_timestamp(family_plan.get("due_at"), now)
        weeks = min(40, max(0, int((now - started) // 3600)))
        lines.append(f"\n🍼 Семейный таймер: <b>{weeks}/40 недель</b>. Команды: <code>отн беременность</code>, <code>отн родить</code>.")
    _reply(message, "\n".join(lines))


def _family_plan_status(pair):
    plan = pair.get("family_plan")
    if not isinstance(plan, dict):
        return "Сейчас у пары нет активного семейного планирования."
    now = time.time()
    if plan.get("status") == "pending":
        remaining = max(0, int(_safe_timestamp(plan.get("expires_at"), now) - now))
        initiator = _safe_int(plan.get("by"), 0)
        return (
            f"💌 Есть предложение от <b>{html.escape(_user_name(initiator))}</b>. "
            f"Партнёр может ответить <code>отн планирование принять</code> или "
            f"<code>отн планирование отказать</code>. Предложение действует ещё {max(1, math.ceil(remaining / 3600))} ч."
        )
    if plan.get("status") == "active":
        started = _safe_timestamp(plan.get("started_at"), now)
        due = _safe_timestamp(plan.get("due_at"), now)
        elapsed = max(0.0, now - started)
        weeks = min(40, int(elapsed // 3600))
        remaining = max(0, int(due - now))
        if remaining > 0:
            hours, seconds = divmod(remaining, 3600)
            minutes = seconds // 60
            return (f"🍼 <b>Семейный таймер активен</b>\n"
                    f"Срок: <b>{weeks}/40 недель</b>\n"
                    f"Осталось: <b>{hours} ч. {minutes} мин.</b>\n"
                    f"Имя: <b>{html.escape(str(plan.get('child_name') or 'не выбрано'))}</b>\n"
                    "После завершения используйте <code>отн родить</code>.")
        return f"🎉 Игровой срок завершён: <b>40/40 недель</b>. Можно завершить событие командой <code>отн родить</code>. Имя: <b>{html.escape(str(plan.get('child_name') or 'Малыш'))}</b>."
    return "Сейчас у пары нет активного семейного планирования."


def _family_plan_command(message, pair, user_id, command):
    lower = command.strip().lower()
    now = time.time()
    plan = pair.get("family_plan")
    if lower in {"планирование", "беременность"}:
        protection = _safe_timestamp(pair.get("protection_until"), 0)
        status = _family_plan_status(pair)
        if protection > now:
            status += f"\n🛡 Игровая защита действует ещё {max(1, math.ceil((protection - now) / 3600))} ч."
        _reply(message, status)
        return

    if lower in {"планировать ребёнка", "планировать ребенка"}:
        if len(pair.get("children", [])) >= MAX_CHILDREN_PER_PAIR:
            _reply(message, "У пары уже максимум — 3 ребёнка.")
            return
        protection = _safe_timestamp(pair.get("protection_until"), 0)
        if protection > now:
            _reply(message, f"🛡 Игровая защита активна ещё {max(1, math.ceil((protection - now) / 3600))} ч. Сначала дождитесь её завершения или отключите её командой <code>отн защита снять</code>.")
            return
        if isinstance(plan, dict) and plan.get("status") in {"pending", "active"}:
            _reply(message, _family_plan_status(pair))
            return
        pair["family_plan"] = {
            "status": "pending", "by": int(user_id), "created_at": now,
            "expires_at": now + FAMILY_PLAN_TTL_SECONDS,
        }
        mark_dirty()
        _reply(message, "💌 Предложение семейного планирования отправлено партнёру. Оно начнётся только после его явного согласия: <code>отн планирование принять</code>. Отказ: <code>отн планирование отказать</code>.")
        return

    if lower == "планирование принять":
        if not isinstance(plan, dict) or plan.get("status") != "pending":
            _reply(message, "Нет ожидающего предложения семейного планирования.")
            return
        if _safe_int(plan.get("by"), 0) == int(user_id):
            _reply(message, "Подтвердить предложение должен второй партнёр.")
            return
        protection = _safe_timestamp(pair.get("protection_until"), 0)
        if protection > now:
            _reply(message, "Сейчас включена игровая защита. Сначала отключите её: <code>отн защита снять</code>.")
            return
        if len(pair.get("children", [])) >= MAX_CHILDREN_PER_PAIR:
            _reply(message, "У пары уже максимум — 3 ребёнка.")
            return
        pair["family_plan"] = {
            "status": "active", "started_at": now,
            "due_at": now + PREGNANCY_DURATION_SECONDS,
            "child_name": "",
        }
        mark_dirty()
        _reply(message, "✅ Оба партнёра согласились. Запущен игровой семейный таймер: 1 час = 1 игровая неделя, всего 40 часов. В любой момент можно посмотреть <code>отн беременность</code> и выбрать имя через <code>отн ребёнок имя Мира</code>.")
        return

    if lower == "планирование отказать":
        if not isinstance(plan, dict) or plan.get("status") != "pending":
            _reply(message, "Нет ожидающего предложения семейного планирования.")
            return
        if _safe_int(plan.get("by"), 0) == int(user_id):
            _reply(message, "Отклонить предложение может второй партнёр. Чтобы отменить своё, напишите <code>отн планирование отменить</code>.")
            return
        pair["family_plan"] = None
        mark_dirty()
        _reply(message, "Предложение семейного планирования отклонено. Ничего не запущено.")
        return

    if lower == "планирование отменить":
        if not isinstance(plan, dict) or plan.get("status") != "pending":
            _reply(message, "Нет исходящего предложения, которое можно отменить.")
            return
        if _safe_int(plan.get("by"), 0) != int(user_id):
            _reply(message, "Отменить предложение может только тот, кто его отправил.")
            return
        pair["family_plan"] = None
        mark_dirty()
        _reply(message, "Исходящее предложение семейного планирования отменено.")
        return

    _reply(message, "Команды семейного планирования: <code>отн планировать ребёнка</code>, <code>отн планирование принять</code>, <code>отн беременность</code>.")


def _protection_command(message, pair, command):
    now = time.time()
    lower = command.strip().lower()
    until = _safe_timestamp(pair.get("protection_until"), 0)
    if lower == "защита купить":
        if isinstance(pair.get("family_plan"), dict) and pair["family_plan"].get("status") == "active":
            _reply(message, "Во время активного семейного таймера игровую защиту купить нельзя.")
            return
        if until > now:
            _reply(message, f"🛡 Игровая защита уже активна ещё {max(1, math.ceil((until - now) / 3600))} ч.")
            return
        if _safe_int(pair.get("petals"), 0, minimum=0) < PROTECTION_COST:
            _reply(message, f"На общем счёте нужно {PROTECTION_COST} лепестков.")
            return
        pair["petals"] = _safe_int(pair.get("petals"), 0, minimum=0) - PROTECTION_COST
        pair["protection_until"] = now + PROTECTION_DURATION_SECONDS
        mark_dirty()
        _reply(message, f"🛡 Игровая защита активирована на 48 часов. Стоимость: {PROTECTION_COST} лепестков. Пока она действует, новое семейное планирование недоступно.")
        return
    if lower in {"защита снять", "защита отключить"}:
        if until <= now:
            _reply(message, "Игровая защита сейчас не активна.")
            return
        pair["protection_until"] = 0
        mark_dirty()
        _reply(message, "Игровая защита отключена.")
        return
    if until > now:
        _reply(message, f"🛡 Защита активна ещё {max(1, math.ceil((until - now) / 3600))} ч. Купить: <code>отн защита купить</code>; снять: <code>отн защита снять</code>.")
    else:
        _reply(message, f"Защита не активна. Купить игровую защиту на 48 часов можно за {PROTECTION_COST} лепестков: <code>отн защита купить</code>.")


def _leave_family(message, user_id):
    root = _store()
    key = str(int(user_id))
    pair_id = root["family_members"].get(key)
    pair = root["pairs"].get(str(pair_id)) if pair_id else None
    if not isinstance(pair, dict):
        root["family_members"].pop(key, None)
        mark_dirty()
        _reply(message, "Ты сейчас не состоишь в игровой семье как приглашённый участник.")
        return
    children = pair.get("children", []) if isinstance(pair.get("children"), list) else []
    updated = [child for child in children if not (isinstance(child, dict) and _safe_int(child.get("member_id"), 0) == int(user_id))]
    if len(updated) == len(children):
        root["family_members"].pop(key, None)
        mark_dirty()
        _reply(message, "Участие в игровой семье завершено.")
        return
    pair["children"] = updated
    for index, child in enumerate(updated, start=1):
        if isinstance(child, dict):
            child["id"] = index
    root["family_members"].pop(key, None)
    mark_dirty()
    _reply(message, "Ты вышел(ла) из игровой семьи. Запись об участии удалена из активного профиля пары.")


def _invite_family_member(message, pair, user_id, raw_target):
    target_id, target_name, is_bot = _resolve_target(message, raw_target)
    if not target_id:
        _reply(message, "Укажи участника группы через @username или ответь на его сообщение: <code>отн в семью @username</code>.")
        return
    if target_id == int(user_id) or is_bot or target_id in [int(x) for x in pair.get("users", [])]:
        _reply(message, "Нельзя пригласить себя, бота или одного из родителей.")
        return
    root = _store()
    key = str(target_id)
    pair_id = str(pair.get("id"))
    if key in root["users"]:
        _reply(message, "Этот пользователь уже состоит в отношениях. Сначала он должен освободиться от своей пары.")
        return
    if key in root["family_members"]:
        _reply(message, "Этот пользователь уже состоит в другой игровой семье.")
        return
    if len(pair.get("children", [])) >= MAX_CHILDREN_PER_PAIR:
        _reply(message, "У пары уже максимум — 3 ребёнка/участника семьи.")
        return
    existing = root["family_invites"].get(key)
    if isinstance(existing, dict):
        if str(existing.get("pair_id")) == pair_id:
            _reply(message, "Приглашение уже отправлено. Пользователь может ответить <code>отн принять в семью</code>.")
        else:
            _reply(message, "У пользователя уже есть ожидающее приглашение в другую игровую семью.")
        return
    root["family_invites"][key] = {
        "pair_id": pair_id, "from_id": int(user_id), "to_id": int(target_id),
        "name": str(target_name or _user_name(target_id))[:80], "created_at": time.time(),
    }
    mark_dirty()
    _reply(message, f"👨‍👩‍👧 Приглашение отправлено <b>{html.escape(str(target_name or _user_name(target_id)))}</b>. Он/она станет участником игровой семьи только после собственного подтверждения командой <code>отн принять в семью</code>. Отказ: <code>отн отказаться от семьи</code>.")


def _respond_family_invite(message, user_id, accept):
    root = _store()
    key = str(int(user_id))
    invite = root["family_invites"].get(key)
    if not isinstance(invite, dict):
        _reply(message, "У тебя нет активных приглашений в игровую семью.")
        return
    created_at = _safe_timestamp(invite.get("created_at"), 0)
    now = time.time()
    if not created_at or now - created_at < 0 or now - created_at >= FAMILY_PLAN_TTL_SECONDS:
        root["family_invites"].pop(key, None)
        mark_dirty()
        _reply(message, "Приглашение уже истекло.")
        return
    if not accept:
        root["family_invites"].pop(key, None)
        mark_dirty()
        _reply(message, "Приглашение в игровую семью отклонено.")
        return
    pair_id = str(invite.get("pair_id") or "")
    pair = root["pairs"].get(pair_id)
    if not isinstance(pair, dict):
        root["family_invites"].pop(key, None)
        mark_dirty()
        _reply(message, "Эта игровая семья уже не существует.")
        return
    pair = _normalize_pair(pair_id, pair)
    if key in root["users"] or key in root["family_members"]:
        root["family_invites"].pop(key, None)
        mark_dirty()
        _reply(message, "Ты уже состоишь в паре или в другой игровой семье.")
        return
    children = pair.setdefault("children", [])
    if len(children) >= MAX_CHILDREN_PER_PAIR:
        root["family_invites"].pop(key, None)
        mark_dirty()
        _reply(message, "В этой игровой семье уже максимум — 3 ребёнка/участника.")
        return
    name = str(getattr(getattr(message, "from_user", None), "first_name", "") or _user_name(user_id))[:32]
    children.append({
        "id": len(children) + 1, "name": name, "born_at": now,
        "happiness": 50, "last_care_at": 0, "member_id": int(user_id),
        "kind": "consenting_member",
    })
    root["family_members"][key] = pair_id
    root["family_invites"].pop(key, None)
    mark_dirty()
    _reply(message, "✅ Ты добровольно присоединился(ась) к игровой семье. Чтобы выйти позже, напиши <code>отн выйти из семьи</code>.")


def _house_command(message, pair, command):
    _calculate_house_income(pair)
    if command.startswith("купить"):
        key = command[len("купить"):].strip().lower()
        if key not in HOUSES:
            _reply(message, "Выбери дом: " + ", ".join(f"<code>{k}</code> ({v['price']} лепестков)" for k, v in HOUSES.items()))
            return
        if pair.get("house"):
            _reply(message, "У пары уже есть дом. Второй дом пока нельзя купить.")
            return
        house = HOUSES[key]
        if int(pair.get("petals", 0) or 0) < int(house["price"]):
            _reply(message, f"Для покупки нужно {house['price']} лепестков.")
            return
        pair["petals"] = int(pair.get("petals", 0)) - int(house["price"])
        pair["house"] = key
        pair["last_house_income_at"] = time.time()
        mark_dirty()
        _reply(message, f"🏡 Пара купила: <b>{house['name']}</b>! Доход: {house['income']} лепестков в час (начисляется при командах отношений, максимум за 72 часа).")
        return
    house_id = pair.get("house")
    if house_id in HOUSES:
        house = HOUSES[house_id]
        _reply(message, f"🏡 <b>Дом пары</b>\n{house['name']}\nДоход: {house['income']} лепестков/час\nБаланс: {int(pair.get('petals', 0))} лепестков.")
    else:
        lines = ["🏡 <b>ДОМА ДЛЯ ПАРЫ</b>"]
        for key, house in HOUSES.items():
            lines.append(f"• <code>отн дом купить {key}</code> — {house['name']} · {house['price']} лепестков · {house['income']}/ч")
        _reply(message, "\n".join(lines))


def _shop_command(message, pair, command):
    if command in {"подарки", "история подарков"}:
        history = pair.get("gifts", []) if isinstance(pair.get("gifts"), list) else []
        if not history:
            _reply(message, "🎁 У пары пока нет подарков в истории.")
            return
        lines = ["🎁 <b>ИСТОРИЯ ПОДАРКОВ ПАРЫ</b>", "━━━━━━━━━━━━━━━━━━━━"]
        for item in history[-10:][::-1]:
            if not isinstance(item, dict):
                continue
            sender_id = _safe_int(item.get("by"), 0)
            sender = _user_name(sender_id) if sender_id else "Пользователь"
            stamp = datetime.fromtimestamp(_safe_timestamp(item.get("at"), time.time()), timezone.utc).strftime("%d.%m.%Y")
            lines.append(f"• {html.escape(str(item.get('name') or 'Подарок'))} — {html.escape(sender)} · {stamp}")
        _reply(message, "\n".join(lines))
        return
    gifts = {
        "розы": {"name": "🌹 Букет роз", "price": 20},
        "шоколад": {"name": "🍫 Коробка шоколада", "price": 15},
        "мишку": {"name": "🧸 Плюшевый мишка", "price": 45},
        "украшение": {"name": "💎 Украшение", "price": 90},
    }
    if command.startswith("подарок"):
        gift_key = command[len("подарок"):].strip().lower()
        if gift_key not in gifts:
            _reply(message, "Укажи подарок: <code>отн подарок розы</code>, <code>шоколад</code>, <code>мишку</code> или <code>украшение</code>.")
            return
        gift = gifts[gift_key]
        if int(pair.get("petals", 0) or 0) < gift["price"]:
            _reply(message, f"Не хватает лепестков. Нужно {gift['price']}.")
            return
        pair["petals"] = int(pair.get("petals", 0)) - int(gift["price"])
        gift_history = pair.setdefault("gifts", [])
        gift_history.append({"name": gift["name"], "by": int(message.from_user.id), "at": time.time()})
        del gift_history[:-MAX_GIFT_HISTORY]
        mark_dirty()
        _reply(message, f"🎁 Вы подарили паре: <b>{gift['name']}</b>! Подарок сохранён в истории пары.")
        return
    lines = ["🎁 <b>МАГАЗИН ОТНОШЕНИЙ</b>", "━━━━━━━━━━━━━━━━━━━━"]
    for key, gift in gifts.items():
        lines.append(f"• <code>отн подарок {key}</code> — {gift['name']} · {gift['price']} лепестков")
    _reply(message, "\n".join(lines))


def handle_relationship_commands(message):
    if not message or not getattr(message, "from_user", None) or not can_process_user_message(message):
        return
    raw = str(getattr(message, "text", "") or "").strip()
    match = re.match(r"^отн(?:\s+(.*))?$", raw, flags=re.IGNORECASE)
    if not match:
        return
    args = (match.group(1) or "").strip()
    user_id = _safe_int(getattr(message.from_user, "id", 0), 0, minimum=1)
    if not user_id:
        return
    user_name = (
        f"{getattr(message.from_user, 'first_name', '') or ''} "
        f"{getattr(message.from_user, 'last_name', '') or ''}"
    ).strip() or getattr(message.from_user, "username", None) or f"ID:{user_id}"
    user_name = str(user_name)[:80]
    command = args.lower().strip()

    if not command or command in {"помощь", "help", "команды"}:
        _reply(message, _help_text())
        return
    if command == "предложить" or command.startswith("предложить "):
        target = args[len("предложить"):].strip()
        _handle_proposal(message, target, user_id, user_name)
        return
    if command == "принять":
        _accept_proposal(message, user_id, user_name)
        return
    if command == "отказать":
        with _relationship_transaction():
            _store()["pending"].pop(str(user_id), None)
            mark_dirty()
        _reply(message, "Предложение отклонено.")
        return
    if command == "принять в семью" or command == "отказаться от семьи":
        with _relationship_transaction():
            _respond_family_invite(message, user_id, accept=(command == "принять в семью"))
        return
    if command == "выйти из семьи":
        with _relationship_transaction():
            _leave_family(message, user_id)
        return
    if command == "отменить":
        removed = 0
        with _relationship_transaction():
            pending = _store()["pending"]
            for target_key, proposal in list(pending.items()):
                if isinstance(proposal, dict) and _safe_int(proposal.get("from_id"), 0) == user_id:
                    pending.pop(target_key, None)
                    removed += 1
            if removed:
                mark_dirty()
        _reply(message, "✅ Исходящее предложение отменено." if removed else "У тебя нет исходящих предложений.")
        return
    if command in {"расстаться", "расстаться подтвердить"}:
        _end_relationship(message, user_id, confirm=(command == "расстаться подтвердить"))
        return
    if command == "история":
        _relationship_history(message, user_id)
        return
    if command == "пол" or command.startswith("пол "):
        value = command[len("пол"):].strip()
        if value in {"мужчина", "мужской", "парень", "м"}:
            gender = "male"
            label = "мужской"
        elif value in {"женщина", "женский", "девушка", "ж"}:
            gender = "female"
            label = "женский"
        else:
            _reply(message, "Укажи: <code>отн пол мужчина</code> или <code>отн пол женщина</code>.")
            return
        with _relationship_transaction():
            econ = get_user_econ(user_id=user_id, username=getattr(message.from_user, "username", None))
            econ["relationship_gender"] = gender
            mark_dirty()
        _reply(message, f"✅ Пол сохранён как {label}. Для пары будут подбираться соответствующие GIF, когда они добавлены в каталог.")
        return

    if command in {"гиф превью", "гиф медиа"}:
        with _relationship_transaction():
            pair = _pair_for(user_id)
            if not pair:
                _reply(message, "Для настройки GIF сначала нужны отношения.")
                return
            pair["gif_mode"] = "preview" if command.endswith("превью") else "media"
            mark_dirty()
            _reply(message, "✅ GIF будут отправляться как превью-ссылки (как карточка Telegram)." if pair["gif_mode"] == "preview" else "✅ GIF будут отправляться как отдельное анимированное медиа Telegram.")
        return

    if command in {"планирование", "беременность", "планировать ребёнка", "планировать ребенка", "планирование принять", "планирование отказать", "планирование отменить"}:
        with _relationship_transaction():
            pair = _pair_for(user_id)
            if not pair:
                _reply(message, "Для семейного планирования сначала нужны отношения.")
                return
            _family_plan_command(message, pair, user_id, command)
        return

    if command == "защита" or command.startswith("защита ") or command == "контрацептив" or command.startswith("контрацептив "):
        protection_command = command.replace("контрацептив", "защита", 1)
        with _relationship_transaction():
            pair = _pair_for(user_id)
            if not pair:
                _reply(message, "Для игровой защиты сначала нужны отношения.")
                return
            _protection_command(message, pair, protection_command)
        return

    if command == "в семью" or command.startswith("в семью ") or command.startswith("родить @"):
        raw_target = command[len("в семью"):].strip() if command.startswith("в семью") else args[len("родить"):].strip()
        with _relationship_transaction():
            pair = _pair_for(user_id)
            if not pair:
                _reply(message, "Пригласить участника в семью могут только участники пары.")
                return
            _invite_family_member(message, pair, user_id, raw_target)
        return

    if command in {"профиль", "пара"}:
        with _relationship_transaction():
            pair = _pair_for(user_id)
            if pair:
                _calculate_house_income(pair)
                _ensure_daily_task(pair)
                pair_snapshot = copy.deepcopy(pair)
            else:
                pair_snapshot = None
        if not pair_snapshot:
            _reply(message, "💔 У тебя пока нет отношений. Начать можно командой <code>отн предложить @username</code>.")
            return
        _reply(message, _pair_profile_text(pair_snapshot, user_id, message.chat.id))
        return

    if command in {"действия", "список"}:
        with _relationship_transaction():
            pair = _pair_for(user_id)
            if pair:
                _calculate_house_income(pair)
                pair_snapshot = copy.deepcopy(pair)
            else:
                pair_snapshot = None
        if not pair_snapshot:
            _reply(message, "Сначала создай пару: <code>отн предложить @username</code>.")
            return
        _reply(message, _actions_list(pair_snapshot, user_id))
        return

    if command in {"задания", "задание", "забрать награду"}:
        with _relationship_transaction():
            pair = _pair_for(user_id)
            if not pair:
                _reply(message, "Для заданий сначала нужны отношения.")
                return
            _calculate_house_income(pair)
            _ensure_daily_task(pair)
            _daily_task(message, pair, "забрать награду" if command == "забрать награду" else "show")
        return

    if command in {"родить", "дети", "ребёнок", "ребенок"} or command.startswith(("родить ", "ребёнок ", "ребенок ")):
        child_command = ""
        if command.startswith(("ребёнок ", "ребенок ")):
            child_command = args.split(" ", 1)[1] if " " in args else ""
        elif command.startswith("родить "):
            # `отн родить @user` is a consent-based family invitation; no user is assigned a role without acceptance.
            raw_target = args[len("родить"):].strip()
            with _relationship_transaction():
                pair = _pair_for(user_id)
                if not pair:
                    _reply(message, "Пригласить участника в семью могут только участники пары.")
                    return
                _invite_family_member(message, pair, user_id, raw_target)
            return
        elif command == "родить":
            child_command = "родить"
        with _relationship_transaction():
            pair = _pair_for(user_id)
            if not pair:
                _reply(message, "Для воспитания детей сначала нужны отношения.")
                return
            _calculate_house_income(pair)
            _children_command(message, pair, user_id, child_command)
        return

    if command in {"дом", "дом купить"} or command.startswith("дом купить "):
        with _relationship_transaction():
            pair = _pair_for(user_id)
            if not pair:
                _reply(message, "Для общего дома сначала нужны отношения.")
                return
            _house_command(message, pair, command[len("дом"):].strip())
        return

    if command in {"магазин", "подарки", "история подарков"} or command.startswith("подарок"):
        with _relationship_transaction():
            pair = _pair_for(user_id)
            if not pair:
                _reply(message, "Для магазина отношений сначала нужны отношения.")
                return
            _calculate_house_income(pair)
            _shop_command(message, pair, command)
        return

    # Longest phrase first so multi-word actions are not swallowed by shorter ones.
    action_name = next((name for name in sorted(ACTIONS, key=len, reverse=True) if command == name), None)
    if action_name:
        _do_action(message, action_name, user_id, user_name)
        return

    _reply(message, "Не понял команду. Посмотри список: <code>отн</code>.")

def register(ctx, only=None):
    _inject(ctx)
    bot = ctx["bot"]
    wanted = set(only) if only is not None else {"handle_relationship_commands"}
    registered = []
    if "handle_relationship_commands" in wanted:
        handler = serialize_user_action(handle_relationship_commands)
        bot.message_handler(
            func=lambda message: bool(getattr(message, "text", None))
            and re.match(r"^\s*отн(?:\s|$)", message.text, flags=re.IGNORECASE) is not None,
            content_types=["text"],
        )(handler)
        ctx["handle_relationship_commands"] = handler
        globals()["handle_relationship_commands"] = handler
        registered.append("handle_relationship_commands")
    return registered
