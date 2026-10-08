"""Concurrency/anti-double-action locks for NyaBot.

This module contains the locks that were previously kept inside newfile.py.
The objects are intentionally module-level singletons so every imported part
of the bot shares the same lock instances.
"""

import functools
import threading
from contextlib import contextmanager


# Per-user serialization prevents double-click/double-spend races.
USER_ACTION_LOCKS = {}
USER_ACTION_LOCKS_GUARD = threading.Lock()

# Shared state / payment locks.
CALLBACK_STATE_LOCK = threading.RLock()
STARS_PAYMENT_LOCK = threading.RLock()
DB_SAVE_LOCK = threading.Lock()
QUIZ_LOCK = threading.RLock()
TRANSFER_LOCK = threading.RLock()
# Canonical lock for all monetary mutations and persistence snapshots.
BALANCE_TX_LOCK = TRANSFER_LOCK
CASINO_LOCK = threading.RLock()
GUILD_LOCK = threading.RLock()
SAFE_LOCK = threading.RLock()
PLAYER_MARKET_LOCK = threading.RLock()
LOTTERY_LOCK = threading.RLock()
SEASON_LOCK = threading.RLock()
MEME_LOCK = threading.RLock()
MARKET_LOCK = threading.RLock()

# Legacy compatibility name present in the old monolith.
stars_payment_lock = STARS_PAYMENT_LOCK


def _get_user_action_lock(user_id):
    key = int(user_id or 0)
    with USER_ACTION_LOCKS_GUARD:
        lock = USER_ACTION_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            USER_ACTION_LOCKS[key] = lock
        return lock

@contextmanager
def ordered_user_action_locks(*user_ids):
    """Acquire all per-user locks in deterministic order to prevent deadlocks."""
    normalized = []
    for uid in user_ids:
        try:
            value = int(uid)
        except (TypeError, ValueError):
            continue
        if value and value not in normalized:
            normalized.append(value)
    normalized.sort()
    locks = [_get_user_action_lock(uid) for uid in normalized]
    for lock in locks:
        lock.acquire()
    try:
        yield
    finally:
        for lock in reversed(locks):
            lock.release()


@contextmanager
def serialized_multi_user_action(current_user_id, *other_user_ids):
    """Serialize a multi-user mutation using deterministic per-user lock order.

    The previous implementation tried to release/reacquire the global callback
    lock here because callbacks were wrapped in that global lock. That made a
    slow Telegram/Neon operation able to block every callback in the bot. The
    callback wrapper is now per-user, so this helper only needs the ordered user
    locks and remains safely re-entrant for the current user's lock.
    """
    with ordered_user_action_locks(current_user_id, *other_user_ids):
        yield


def _extract_update_user_id(update):
    user = getattr(update, "from_user", None)
    if user is not None and getattr(user, "id", None):
        return int(user.id)

    msg = getattr(update, "message", None)
    user = getattr(msg, "from_user", None)
    if user is not None and getattr(user, "id", None):
        return int(user.id)

    return None


def serialize_user_action(func):
    """Serialize registered Telegram handlers per user."""
    @functools.wraps(func)
    def wrapped(update, *args, **kwargs):
        user_id = _extract_update_user_id(update)

        if user_id is None:
            return func(update, *args, **kwargs)

        user_lock = _get_user_action_lock(user_id)

        # Serialize only this user's actions. Do NOT hold the global callback
        # state lock while the handler performs Telegram/Neon I/O: one slow
        # callback must never freeze callbacks (and therefore ordinary messages)
        # for every other user. Shared in-memory state that truly needs global
        # serialization is protected at the narrow mutation sites instead.
        with user_lock:
            return func(update, *args, **kwargs)

    return wrapped


def serialize_stars_payment(func):
    """Keep Stars handling serialized per payer without a global bottleneck.

    A successful-payment handler is already wrapped by serialize_user_action in
    production registration. Keeping this decorator as a per-user lock as well
    is re-entrant for that case and prevents one user's slow payment from
    blocking payments from all other users.
    """
    @functools.wraps(func)
    def wrapped(update, *args, **kwargs):
        user_id = _extract_update_user_id(update)
        if user_id is None:
            return func(update, *args, **kwargs)
        with _get_user_action_lock(user_id):
            return func(update, *args, **kwargs)

    return wrapped
