"""Concurrency/anti-double-action locks for NyaBot.

This module contains the locks that were previously kept inside newfile.py.
The objects are intentionally module-level singletons so every imported part
of the bot shares the same lock instances.
"""

import functools
import threading
import weakref
from contextlib import contextmanager


# Per-user serialization prevents double-click/double-spend races.
# Weak values prevent the registry retaining one RLock forever for every user
# who ever interacted with the bot. Active handlers keep strong references to
# their locks, so concurrent actions for the same user still share one lock.
USER_ACTION_LOCKS = weakref.WeakValueDictionary()
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
def ordered_user_action_locks(*user_ids, retain_user_id=None):
    """Acquire per-user locks in deterministic order.

    ``retain_user_id`` keeps that user's lock acquired when the context exits.
    This is used when upgrading a handler's existing single-user lock to a
    multi-user transaction: the outer handler must remain serialized until it
    returns, but the other participants' locks must be released normally.
    """
    normalized = []
    for uid in user_ids:
        try:
            value = int(uid)
        except (TypeError, ValueError, OverflowError):
            continue
        if value and value not in normalized:
            normalized.append(value)
    normalized.sort()
    try:
        retained_uid = int(retain_user_id) if retain_user_id is not None else None
    except (TypeError, ValueError, OverflowError):
        retained_uid = None
    locks = [(uid, _get_user_action_lock(uid)) for uid in normalized]
    acquired = []
    try:
        for uid, lock in locks:
            lock.acquire()
            acquired.append((uid, lock))
        yield
    finally:
        for uid, lock in reversed(acquired):
            if retained_uid is not None and uid == retained_uid:
                continue
            lock.release()


@contextmanager
def serialized_multi_user_action(current_user_id, *other_user_ids):
    """Upgrade the current handler lock to an ordered multi-user transaction.

    Callback handlers acquire CALLBACK_STATE_LOCK before their user lock. Keep
    that global lock held while upgrading: dropping it and reacquiring it after
    the participant locks are held creates a cycle (callback A holds users 1+2
    and waits for CALLBACK_STATE_LOCK while callback B holds that lock and waits
    for user 2). Other callbacks therefore cannot enter the lock-upgrade window.
    """
    try:
        uid = int(current_user_id)
    except (TypeError, ValueError, OverflowError):
        uid = 0
    current_lock = _get_user_action_lock(uid)
    released_depth = 0
    current_retained = False
    try:
        # Fully release any recursion depth owned by this handler before taking
        # the sorted set. Usually this is one acquisition, but draining the RLock
        # also makes nested wrappers safe.
        if uid > 0:
            while True:
                try:
                    current_lock.release()
                    released_depth += 1
                except RuntimeError:
                    break

        with ordered_user_action_locks(
            uid, *other_user_ids,
            retain_user_id=uid if released_depth else None,
        ):
            try:
                yield
            finally:
                # The ordered context keeps one current-user lock for the outer
                # handler; restore any additional recursion depth below.
                current_retained = bool(released_depth)
    finally:
        # If acquiring the ordered set failed before entering its body, restore
        # every release. Otherwise one acquisition remains retained, so restore
        # only the extra recursion depth. This preserves the outer with-blocks.
        restore_count = max(0, released_depth - (1 if current_retained else 0))
        for _ in range(restore_count):
            current_lock.acquire()


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
