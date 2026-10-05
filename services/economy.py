"""Economy service for NyaBot.

Pure/shared economy operations. Telegram handlers stay outside this module.
Call configure(...) once during bot startup.
"""
import time
import threading

_db = None
_db_lock = threading.RLock()
_mark_dirty = lambda: None
_titles = {}
_vehicles = {}
_donor_vehicles = {}
_season_rollover = None

def configure(*, db, db_lock=None, mark_dirty=None, get_user_econ=None, titles=None, vehicles=None,
              donor_vehicles=None, season_rollover=None):
    global _db, _db_lock, _mark_dirty, _get_user_econ, _titles, _vehicles, _donor_vehicles, _season_rollover
    _db = db
    _db_lock = db_lock or threading.RLock()
    _mark_dirty = mark_dirty or (lambda: None)
    _get_user_econ = get_user_econ
    _titles = titles or {}
    _vehicles = vehicles or {}
    _donor_vehicles = donor_vehicles or {}
    _season_rollover = season_rollover

def _require_configured():
    if _db is None:
        raise RuntimeError("services.economy.configure() must be called before use")

def get_global_user_key(user_id=None, user_tag=None, clean_tag=None):
    if user_id:
        return f"id_{user_id}"
    if user_tag:
        tag = clean_tag(user_tag) if clean_tag else str(user_tag).strip().lstrip("@")
        return f"tag_{tag.lower()}"
    return "unknown_user"

def get_account_level(exp):
    try:
        exp = max(0, int(exp or 0))
    except (TypeError, ValueError):
        exp = 0
    lvl = 1
    current_tier_base = 0
    next_tier_exp = 100
    while exp >= next_tier_exp:
        current_tier_base = next_tier_exp
        lvl += 1
        next_tier_exp = int(100 * (lvl ** 1.5))
    in_tier_exp = exp - current_tier_base
    needed_in_tier = max(1, next_tier_exp - current_tier_base)
    percent = min(1.0, in_tier_exp / needed_in_tier)
    filled = int(percent * 8)
    bar = "█" * filled + "░" * (8 - filled)
    return lvl, exp, next_tier_exp, bar

def account_exp_for_level(level):
    try:
        level = max(1, int(level))
    except (TypeError, ValueError):
        return 0
    return 0 if level <= 1 else int(100 * ((level - 1) ** 1.5))

def is_vip_active(econ):
    return bool(econ and (econ.get("vip_forever") or econ.get("vip_until", 0) > time.time()))

def get_donor_title_buffs(econ):
    if not isinstance(econ, dict):
        return {}
    active = econ.get("active_title")
    info = _titles.get(active, {}) if active else {}
    return info.get("donor_buffs", {}) or {}

def get_title_work_bonus(econ):
    return float(get_donor_title_buffs(econ).get("work_bonus", 0.0))

def get_title_bonus_multiplier(econ):
    return float(get_donor_title_buffs(econ).get("bonus_mult", 0.0))

def get_title_business_bonus(econ):
    return float(get_donor_title_buffs(econ).get("business_bonus", 0.0))

def get_vip_work_bonus(econ):
    return 0.10 if is_vip_active(econ) else 0.0

def get_vehicle_work_bonus(econ):
    """Small secondary vehicle bonus; cooldown reduction remains the primary car stat."""
    if not isinstance(econ, dict):
        return 0.0
    vehicle = econ.get("equipped_vehicle") or econ.get("vehicle")
    info = _vehicles.get(vehicle) or _donor_vehicles.get(vehicle)
    if not info:
        return 0.0
    try:
        return max(0.0, min(0.20, float(info.get("work_bonus", 0.0) or 0.0)))
    except (TypeError, ValueError):
        return 0.0

def get_vip_business_bonus(econ):
    return 0.10 if is_vip_active(econ) else 0.0

def get_user_cd_reduction(econ):
    if not isinstance(econ, dict):
        return 0.0
    reduction = 0.0
    vehicle = econ.get("equipped_vehicle") or econ.get("vehicle")
    info = _vehicles.get(vehicle) or _donor_vehicles.get(vehicle)
    if info:
        reduction += float(info.get("cd_cut", 0.0) or 0.0)
    active = econ.get("active_title")
    if active in _titles:
        title = _titles[active]
        if title.get("buff") == "cd_reduction":
            reduction += float(title.get("val", 0) or 0) / 100.0
    if is_vip_active(econ):
        reduction += 0.35
    return min(0.75, max(0.0, reduction))

def cooldown_text(last_time, cooldown, user_econ=None):
    if not last_time:
        return None
    now_ts = time.time()
    reduction = get_user_cd_reduction(user_econ) if user_econ else 0.0
    effective_cooldown = max(1.0, float(cooldown) * (1.0 - reduction))
    elapsed = now_ts - float(last_time)
    left = int(effective_cooldown - elapsed)
    if left <= 0:
        return None
    hours = left // 3600
    minutes = (left % 3600) // 60
    seconds = left % 60
    parts = []
    if hours > 0:
        parts.append(f"{hours} ч")
    if minutes > 0:
        parts.append(f"{minutes} мин")
    if seconds > 0 or not parts:
        parts.append(f"{seconds} сек")
    return " ".join(parts)

def _resolve_econ(user_id=None, user_tag=None, username=None):
    if _get_user_econ is None:
        raise RuntimeError("services.economy.configure() requires get_user_econ")
    return _get_user_econ(user_id, user_tag, username)

def add_coins(user_id, user_tag, amount, username=None):
    with _db_lock:
        econ = _resolve_econ(user_id, user_tag, username)
        econ['balance'] = max(0, int(econ.get('balance', 0) or 0) + int(amount or 0))
        _mark_dirty()
        return econ['balance']

def add_account_exp(user_id, user_tag, exp_amount=1, username=None):
    with _db_lock:
        econ = _resolve_econ(user_id, user_tag, username)
        active_t = econ.get('active_title')
        bonus = 1.0
        if active_t and active_t in _titles and _titles[active_t].get('buff') == 'exp_bonus':
            bonus += float(_titles[active_t].get('val', 0) or 0) / 100.0
        if is_vip_active(econ):
            bonus += 0.25
        gained_exp = int(exp_amount * bonus)
        econ['account_exp'] = int(econ.get('account_exp', 0) or 0) + gained_exp
        if _season_rollover:
            _season_rollover()
        econ['season_points'] = int(econ.get('season_points', 0) or 0) + max(1, gained_exp // 5)
        _mark_dirty()
        return gained_exp

def change_karma(user_id, user_tag, amount, username=None):
    with _db_lock:
        econ = _resolve_econ(user_id, user_tag, username)
        econ['karma'] = max(-100, min(100, int(econ.get('karma', 0) or 0) + int(amount or 0)))
        value = econ['karma']
        _mark_dirty()
        return value

def update_bank_interest(econ, now=None):
    bank = int(econ.get("bank_deposit", 0) or 0)
    now = time.time() if now is None else float(now)
    if bank <= 0:
        econ["last_bank_calc"] = now
        return 0
    last = float(econ.get("last_bank_calc", now) or now)
    periods = int(max(0.0, now - last) // (6 * 3600))
    if periods <= 0:
        return 0
    new_value = int(bank * (1.0025 ** periods))
    earned = new_value - bank
    econ["bank_deposit"] = new_value
    econ["last_bank_calc"] = last + periods * 6 * 3600
    if earned > 0:
        _mark_dirty()
    return earned

def update_pet_stats(pet, now=None):
    if not pet:
        return
    now = time.time() if now is None else float(now)
    last = float(pet.get("last_update", now) or now)
    hours = (now - last) / 3600.0
    if hours > 0.1:
        pet["hunger"] = max(0, int(pet.get("hunger", 100) or 0) - int(hours * 4))
        pet["cleanliness"] = max(0, int(pet.get("cleanliness", 100) or 0) - int(hours * 3))
        pet["last_update"] = now
        _mark_dirty()

def merge_numeric(dest, src, fields):
    for field in fields:
        dest[field] = int(dest.get(field, 0) or 0) + int(src.get(field, 0) or 0)

__all__ = [
    "configure", "get_global_user_key", "get_account_level", "account_exp_for_level",
    "is_vip_active", "get_donor_title_buffs", "get_title_work_bonus",
    "get_title_bonus_multiplier", "get_title_business_bonus", "get_vip_work_bonus",
    "get_vip_business_bonus", "get_user_cd_reduction", "cooldown_text",
    "add_coins", "add_account_exp", "change_karma", "update_bank_interest",
    "update_pet_stats", "merge_numeric",
]
