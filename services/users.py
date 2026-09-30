"""User/account service for NyaBot.

This is the boundary for user records. Complex legacy migrations can be moved here
incrementally; handlers should not need to know how the database key is formed.
"""
import threading
import time

_db = None
_db_lock = threading.RLock()
_mark_dirty = lambda: None
_clean_tag = lambda value: str(value or "").strip().lstrip("@")
_default_user_factory = None

def configure(*, db, db_lock=None, mark_dirty=None, clean_tag=None, default_user_factory=None):
    global _db, _db_lock, _mark_dirty, _clean_tag, _default_user_factory
    _db = db
    _db_lock = db_lock or threading.RLock()
    _mark_dirty = mark_dirty or (lambda: None)
    _clean_tag = clean_tag or _clean_tag
    _default_user_factory = default_user_factory

def _require_db():
    if _db is None:
        raise RuntimeError("services.users.configure() must be called before use")

def global_user_key(user_id=None, user_tag=None):
    if user_id:
        return f"id_{int(user_id)}"
    if user_tag:
        return f"tag_{_clean_tag(user_tag).lower()}"
    return "unknown_user"

def _find_by_username(username):
    if not username:
        return None
    wanted = _clean_tag(username).lower()
    for record in _db.setdefault("economy", {}).values():
        if isinstance(record, dict) and str(record.get("username", "")).lower() == wanted and record.get("user_id"):
            return record
    return None

def get_user(user_id=None, user_tag=None, username=None):
    _require_db()
    with _db_lock:
        economy = _db.setdefault("economy", {})
        clean_username = _clean_tag(username).lower() if username else None
        clean_tag = _clean_tag(user_tag) if user_tag else None
        if not user_id and clean_username:
            found = _find_by_username(clean_username)
            if found:
                user_id = found.get("user_id")
        key = global_user_key(user_id, user_tag or username)
        user = economy.get(key)
        if user is None and user_id:
            for old_key, candidate in list(economy.items()):
                if not isinstance(candidate, dict):
                    continue
                if candidate.get("user_id") == int(user_id):
                    user = candidate
                    break
        if user is None:
            user = _default_user_factory() if _default_user_factory else {
                "user_id": int(user_id) if user_id else None,
                "display_name": clean_tag or clean_username or "Пользователь",
                "username": clean_username,
                "balance": 0,
                "inventory": {},
            }
            economy[key] = user
            _mark_dirty()
        else:
            economy[key] = user
        if clean_tag:
            user["display_name"] = clean_tag
        if clean_username:
            user["username"] = clean_username
        if user_id:
            user["user_id"] = int(user_id)
        return user

def get_balance(user):
    return int(user.get("balance", 0) or 0)

def set_balance(user, amount):
    with _db_lock:
        user["balance"] = max(0, int(amount or 0))
        _mark_dirty()
        return user["balance"]

def add_balance(user, amount):
    with _db_lock:
        user["balance"] = max(0, get_balance(user) + int(amount or 0))
        _mark_dirty()
        return user["balance"]

def update_fields(user, **fields):
    with _db_lock:
        user.update(fields)
        _mark_dirty()
        return user

__all__ = [
    "configure", "global_user_key", "get_user", "get_balance",
    "set_balance", "add_balance", "update_fields",
]
