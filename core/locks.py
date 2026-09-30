"""Concurrency/anti-double-action locks for NyaBot.

This module contains the locks that were previously kept inside newfile.py.
The objects are intentionally module-level singletons so every imported part
of the bot shares the same lock instances.
"""

import functools
import threading


# Per-user serialization prevents double-click/double-spend races.
USER_ACTION_LOCKS = {}
USER_ACTION_LOCKS_GUARD = threading.Lock()

# Shared state / payment locks.
CALLBACK_STATE_LOCK = threading.RLock()
STARS_PAYMENT_LOCK = threading.RLock()
DB_SAVE_LOCK = threading.Lock()
QUIZ_LOCK = threading.RLock()
TRANSFER_LOCK = threading.RLock()
CASINO_LOCK = threading.RLock()
GUILD_LOCK = threading.RLock()
SAFE_LOCK = threading.RLock()
PLAYER_MARKET_LOCK = threading.RLock()
LOTTERY_LOCK = threading.RLock()
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

        is_callback = (
            hasattr(update, "data")
            and hasattr(update, "message")
            and hasattr(update, "from_user")
        )

        if is_callback:
            with CALLBACK_STATE_LOCK:
                with user_lock:
                    return func(update, *args, **kwargs)

        with user_lock:
            return func(update, *args, **kwargs)

    return wrapped


def serialize_stars_payment(func):
    """Process successful Telegram Stars payments one at a time."""
    @functools.wraps(func)
    def wrapped(update, *args, **kwargs):
        with STARS_PAYMENT_LOCK:
            return func(update, *args, **kwargs)

    return wrapped
