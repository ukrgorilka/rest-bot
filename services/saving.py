"""Persistence service for NyaBot.

Neon/local snapshot implementation lives in core.database. This module is the
application-level bridge used by the bot workers and admin save command.
"""
import copy
import os
import time
import threading

from core.database import (
    load_data as database_load_data,
    save_snapshot,
    acquire_single_instance_lock as database_acquire_single_instance_lock,
    release_single_instance_lock as database_release_single_instance_lock,
    single_instance_lock_is_alive as database_single_instance_lock_is_alive,
)

_save_lock = threading.RLock()


def acquire_single_instance_lock():
    """Compatibility wrapper used by newfile.py runtime startup."""
    return database_acquire_single_instance_lock()


def release_single_instance_lock():
    """Release the process-wide Neon advisory lock, if this process owns it."""
    return database_release_single_instance_lock()


def single_instance_lock_is_alive():
    """Return whether the process still owns a healthy Neon lock session."""
    return database_single_instance_lock_is_alive()


def load_data(default_data_factory, normalize_loaded_data):
    return database_load_data(default_data_factory, normalize_loaded_data)


def save_data(db, *, db_lock, db_version, db_version_getter, db_dirty_setter,
              data_file="rests_data.json", send_backup=False,
              db_channel_id=0, bot_instance=None):
    with _save_lock:
        with db_lock:
            snapshot = copy.deepcopy(db)
            snapshot["_meta"] = {"saved_at": time.time()}
            snapshot_version = db_version
        return save_snapshot(
            snapshot=snapshot,
            snapshot_version=snapshot_version,
            db_version_getter=db_version_getter,
            db_dirty_setter=db_dirty_setter,
            send_backup=send_backup,
            db_channel_id=db_channel_id,
            bot_instance=bot_instance,
        )


def start_autosave_worker(*, is_dirty, last_change_at, save_callback,
                          debounce=25.0, interval=5.0, stop_event=None,
                          on_tick=None):
    stop_event = stop_event or threading.Event()

    def worker():
        while not stop_event.is_set():
            stop_event.wait(interval)
            if stop_event.is_set():
                break
            try:
                if on_tick:
                    on_tick()
            except Exception as exc:
                print(f"[AUTOSAVE] tick failed: {exc}")
            try:
                if is_dirty() and time.time() - last_change_at() >= debounce:
                    save_callback(False)
            except Exception as exc:
                print(f"[AUTOSAVE] save failed: {exc}")

    thread = threading.Thread(target=worker, daemon=True, name="autosave")
    thread.start()
    return thread


def start_periodic_backup_worker(*, data_file="rests_data.json",
                                  db_channel_id=0, bot_instance=None,
                                  interval=7200, stop_event=None,
                                  now_label=None):
    stop_event = stop_event or threading.Event()

    def worker():
        while not stop_event.is_set():
            stop_event.wait(interval)
            if stop_event.is_set():
                break
            try:
                if not db_channel_id or not bot_instance or not os.path.exists(data_file):
                    continue
                with open(data_file, "rb") as f:
                    caption = "💾 Плановый авто-бекап базы данных"
                    if now_label:
                        caption += f" [{now_label()}]"
                    msg = bot_instance.send_document(db_channel_id, f, caption=caption)
                    try:
                        bot_instance.pin_chat_message(
                            db_channel_id, msg.message_id, disable_notification=True
                        )
                    except Exception as exc:
                        print(f"[BACKUP PIN ERROR] {exc}")
            except Exception as exc:
                print(f"[BACKUP ERROR] {exc}")

    thread = threading.Thread(target=worker, daemon=True, name="periodic-backup")
    thread.start()
    return thread


__all__ = [
    "load_data", "save_data", "start_autosave_worker",
    "start_periodic_backup_worker", "acquire_single_instance_lock",
    "release_single_instance_lock", "single_instance_lock_is_alive",
]
