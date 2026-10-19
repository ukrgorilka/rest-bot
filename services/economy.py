"""Economy service for NyaBot.

Pure/shared economy operations. Telegram handlers stay outside this module.
Call configure(...) once during bot startup.
"""
import time
import threading
import math
from decimal import Decimal, localcontext
from math import isqrt

_db = None
_db_lock = threading.RLock()
_mark_dirty = lambda: None
_balance_adjuster = None
_titles = {}
_vehicles = {}
_donor_vehicles = {}
_season_rollover = None

def configure(*, db, db_lock=None, mark_dirty=None, get_user_econ=None, titles=None, vehicles=None,
              donor_vehicles=None, season_rollover=None, balance_adjuster=None):
    global _db, _db_lock, _mark_dirty, _balance_adjuster, _get_user_econ, _titles, _vehicles, _donor_vehicles, _season_rollover
    _db = db
    _db_lock = db_lock or threading.RLock()
    _mark_dirty = mark_dirty or (lambda: None)
    _balance_adjuster = balance_adjuster
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

def _xp_threshold(level):
    """Exact integer XP threshold for the existing 100 * level**1.5 curve."""
    level = max(1, int(level))
    # floor(100 * n**1.5) == floor(sqrt(10_000 * n**3)). Using integer
    # arithmetic avoids float rounding at high levels and handles big XP values.
    n = level - 1
    return isqrt(10_000 * n * n * n)


def get_account_level(exp):
    """Return level progress in logarithmic time, even for corrupt/high XP values."""
    try:
        exp = max(0, int(exp or 0))
    except (TypeError, ValueError, OverflowError):
        exp = 0

    # Find the highest level whose starting threshold is no greater than XP.
    # A binary search avoids millions of iterations for high but valid XP values.
    low, high = 1, 2
    while _xp_threshold(high) <= exp:
        low = high
        high *= 2

    while low + 1 < high:
        mid = (low + high) // 2
        if _xp_threshold(mid) <= exp:
            low = mid
        else:
            high = mid

    lvl = low
    current_tier_base = _xp_threshold(lvl)
    next_tier_exp = _xp_threshold(lvl + 1)
    in_tier_exp = exp - current_tier_base
    needed_in_tier = max(1, next_tier_exp - current_tier_base)
    percent = min(1.0, in_tier_exp / needed_in_tier)
    filled = int(percent * 8)
    bar = "█" * filled + "░" * (8 - filled)
    return lvl, exp, next_tier_exp, bar


def account_exp_for_level(level):
    try:
        level = max(1, int(level))
    except (TypeError, ValueError, OverflowError):
        return 0
    return _xp_threshold(level)

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
    """Apply a clamped balance delta through the canonical transaction adapter."""
    try:
        delta = int(amount or 0)
    except (TypeError, ValueError, OverflowError):
        return 0
    econ = _resolve_econ(user_id, user_tag, username)
    reason = 'Начисление коинов' if delta >= 0 else 'Списание коинов'
    if _balance_adjuster is not None:
        return _balance_adjuster(econ, delta, reason)

    # Safe fallback for isolated service use before the main application injects
    # its canonical BALANCE_TX_LOCK-aware adapter. Preserve a bounded audit log.
    with _db_lock:
        current = int(econ.get('balance', 0) or 0)
        new_balance = max(0, current + delta)
        actual_delta = new_balance - current
        econ['balance'] = new_balance
        if actual_delta:
            journal = econ.setdefault('economy_transactions', [])
            if not isinstance(journal, list):
                journal = []
                econ['economy_transactions'] = journal
            journal.append({
                'time': time.time(), 'delta': actual_delta, 'before': current,
                'after': new_balance, 'reason': reason,
            })
            del journal[:-100]
        _mark_dirty()
        return new_balance

MAX_ACCOUNT_EXP_AWARD = 5000
MAX_MESSAGE_ACTIVITY_EXP_PER_UTC_DAY = 1000
ACCOUNT_EXP_HISTORY_LIMIT = 50


def add_account_exp(user_id, user_tag, exp_amount=1, username=None, *, source='activity'):
    """Award bounded positive profile XP and keep a compact diagnostic ledger.

    High levels are intentionally not capped. The bound applies to a single
    award, not lifetime XP, and is above every currently configured award.
    """
    try:
        base_exp = int(exp_amount)
    except (TypeError, ValueError, OverflowError):
        return 0
    if base_exp <= 0 or base_exp > MAX_ACCOUNT_EXP_AWARD:
        return 0

    # Run season rollover before acquiring db_lock to preserve canonical lock order.
    if _season_rollover:
        _season_rollover()

    source_text = str(source or 'activity').strip()[:64] or 'activity'
    with _db_lock:
        econ = _resolve_econ(user_id, user_tag, username)
        try:
            old_exp = max(0, int(econ.get('account_exp', 0) or 0))
        except (TypeError, ValueError, OverflowError):
            old_exp = 0
        old_level = get_account_level(old_exp)[0]

        active_t = econ.get('active_title')
        bonus = 1.0
        if active_t and active_t in _titles and _titles[active_t].get('buff') == 'exp_bonus':
            try:
                bonus += float(_titles[active_t].get('val', 0) or 0) / 100.0
            except (TypeError, ValueError, OverflowError):
                pass
        if is_vip_active(econ):
            bonus += 0.25
        if not (bonus == bonus):  # NaN guard
            bonus = 1.0
        bonus = max(1.0, min(3.0, bonus))

        gained_exp = int(base_exp * bonus)
        if source_text == 'message_activity':
            # Passive chat XP was previously claimable every 5 seconds forever,
            # which made a single noisy account capable of reaching level 100
            # within a few continuously active days. Keep a per-UTC-day budget;
            # other active gameplay rewards retain their existing progression.
            today_utc = time.strftime('%Y-%m-%d', time.gmtime())
            daily = econ.get('account_exp_daily_limits')
            if not isinstance(daily, dict) or daily.get('date') != today_utc:
                daily = {'date': today_utc, 'message_activity': 0}
                econ['account_exp_daily_limits'] = daily
            try:
                used_today = max(0, int(daily.get('message_activity', 0) or 0))
            except (TypeError, ValueError, OverflowError):
                used_today = 0
            used_today = min(MAX_MESSAGE_ACTIVITY_EXP_PER_UTC_DAY, used_today)
            gained_exp = min(gained_exp, MAX_MESSAGE_ACTIVITY_EXP_PER_UTC_DAY - used_today)
            if gained_exp <= 0:
                return 0
            daily['message_activity'] = used_today + gained_exp

        new_exp = old_exp + gained_exp
        econ['account_exp'] = new_exp
        econ['season_points'] = int(econ.get('season_points', 0) or 0) + max(1, gained_exp // 5)

        history = econ.setdefault('account_exp_history', [])
        if not isinstance(history, list):
            history = []
            econ['account_exp_history'] = history
        history.append({
            'time': time.time(), 'source': source_text, 'base': base_exp,
            'gained': gained_exp, 'before': old_exp, 'after': new_exp,
            'level_before': old_level, 'level_after': get_account_level(new_exp)[0],
        })
        del history[:-ACCOUNT_EXP_HISTORY_LIMIT]
        _mark_dirty()
        return gained_exp


def record_account_exp_adjustment(econ, old_exp, new_exp, *, source='admin_adjustment'):
    """Record a direct administrative correction/grant without altering XP again."""
    if not isinstance(econ, dict):
        return 0
    try:
        before = max(0, int(old_exp or 0))
        after = max(0, int(new_exp or 0))
    except (TypeError, ValueError, OverflowError):
        return 0
    delta = after - before
    if delta == 0:
        return 0
    source_text = str(source or 'admin_adjustment').strip()[:64] or 'admin_adjustment'
    with _db_lock:
        history = econ.setdefault('account_exp_history', [])
        if not isinstance(history, list):
            history = []
            econ['account_exp_history'] = history
        history.append({
            'time': time.time(), 'source': source_text, 'base': abs(delta),
            'gained': delta, 'before': before, 'after': after,
            'level_before': get_account_level(before)[0],
            'level_after': get_account_level(after)[0],
        })
        del history[:-ACCOUNT_EXP_HISTORY_LIMIT]
        _mark_dirty()
    return delta

def change_karma(user_id, user_tag, amount, username=None):
    with _db_lock:
        econ = _resolve_econ(user_id, user_tag, username)
        econ['karma'] = max(-100, min(100, int(econ.get('karma', 0) or 0) + int(amount or 0)))
        value = econ['karma']
        _mark_dirty()
        return value

def update_bank_interest(econ, now=None):
    """Accrue bank interest atomically, bounded against corrupt timestamps/amounts."""
    try:
        now = time.time() if now is None else float(now)
        if not math.isfinite(now):
            now = time.time()
    except (TypeError, ValueError, OverflowError):
        now = time.time()

    with _db_lock:
        changed = False
        try:
            bank = int(econ.get("bank_deposit", 0) or 0)
        except (TypeError, ValueError, OverflowError):
            bank = 0
        if bank < 0:
            bank = 0
        if econ.get("bank_deposit") != bank:
            econ["bank_deposit"] = bank
            changed = True

        try:
            last = float(econ.get("last_bank_calc", now) or now)
        except (TypeError, ValueError, OverflowError):
            last = now
        if not math.isfinite(last) or last <= 0 or last > now + 60:
            last = now
            changed = True

        if bank <= 0:
            if econ.get("last_bank_calc") != now:
                econ["last_bank_calc"] = now
                changed = True
            if changed:
                _mark_dirty()
            return 0

        periods = int(max(0.0, now - last) // (6 * 3600))
        if periods <= 0:
            # Persist corrections to invalid stored timestamps even if no interest is due.
            if changed:
                econ["last_bank_calc"] = last
                _mark_dirty()
            return 0

        # Bound work and accrual for absurd legacy/corrupt timestamps. Move the
        # clock forward to the bounded window, so repeated profile reads cannot
        # repeatedly grant another 13.7 years from the same stale timestamp.
        if periods > 20000:
            last = now - 20000 * 6 * 3600
            periods = 20000
        try:
            with localcontext() as ctx:
                ctx.prec = min(5000, max(50, len(str(bank)) + 32))
                new_value = int(Decimal(bank) * (Decimal("1.0025") ** periods))
        except (ArithmeticError, ValueError, OverflowError):
            new_value = bank
        new_value = max(bank, new_value)
        earned = new_value - bank
        econ["bank_deposit"] = new_value
        econ["last_bank_calc"] = last + periods * 6 * 3600
        _mark_dirty()
        return earned

def update_pet_stats(pet, now=None):
    """Decay pet needs safely even when an old snapshot has malformed values."""
    if not isinstance(pet, dict):
        return
    try:
        now = time.time() if now is None else float(now)
        if not math.isfinite(now):
            now = time.time()
    except (TypeError, ValueError, OverflowError):
        now = time.time()

    with _db_lock:
        changed = False
        try:
            last = float(pet.get("last_update", now) or now)
        except (TypeError, ValueError, OverflowError):
            last = now
        if not math.isfinite(last) or last <= 0 or last > now + 60:
            last = now
            changed = True
        elapsed = max(0.0, min(now - last, 365 * 86400.0))

        values = {}
        for key, default in (("hunger", 100), ("cleanliness", 100)):
            try:
                value = int(float(pet.get(key, default) or 0))
            except (TypeError, ValueError, OverflowError):
                value = default
            value = max(0, min(100, value))
            values[key] = max(0, value - int(elapsed / 3600.0 * (4 if key == "hunger" else 3)))
            if pet.get(key) != values[key]:
                changed = True

        if elapsed > 0.1:
            changed = True
        if changed:
            pet["hunger"] = values["hunger"]
            pet["cleanliness"] = values["cleanliness"]
            # Decay was applied for the full bounded interval; anchor the clock
            # to now so stale timestamps cannot replay the same decay repeatedly.
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
