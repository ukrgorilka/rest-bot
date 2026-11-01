import os
import json
import copy
import time
import threading

import psycopg2
from psycopg2.extras import Json


DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
DATA_FILE = "rests_data.json"

db_lock = threading.RLock()
DB_SAVE_LOCK = threading.RLock()

db_dirty = False
db_version = 0
last_db_change_at = 0.0


_PG_SCHEMA_LOCK = threading.Lock()
_PG_SCHEMA_READY = False
_PG_SINGLE_INSTANCE_CONN = None
_PG_SINGLE_INSTANCE_LOCK_KEY = 741923811
_PG_SAVE_SERIAL_LOCK_KEY = 741923812



def _pg_connect():
    if not DATABASE_URL:
        return None
    return psycopg2.connect(
        DATABASE_URL,
        connect_timeout=10
    )


def _pg_prepare_connection(conn):
    global _PG_SCHEMA_READY

    if _PG_SCHEMA_READY:
        return True

    with _PG_SCHEMA_LOCK:
        if _PG_SCHEMA_READY:
            return True

        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS bot_state (
                        id SMALLINT PRIMARY KEY,
                        data JSONB NOT NULL,
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                """)

        _PG_SCHEMA_READY = True

    return True


def _pg_init():
    conn = _pg_connect()

    if conn is None:
        return False

    try:
        return _pg_prepare_connection(conn)
    finally:
        conn.close()


def _pg_load():
    conn = _pg_connect()

    if conn is None:
        return None

    try:
        _pg_prepare_connection(conn)

        with conn.cursor() as cur:
            cur.execute(
                "SELECT data FROM bot_state WHERE id = 1"
            )

            row = cur.fetchone()

            return row[0] if row else None

    finally:
        conn.close()


def acquire_single_instance_lock():
    """Keep only one live bot process connected to the shared Neon database."""
    global _PG_SINGLE_INSTANCE_CONN
    if not DATABASE_URL:
        return True
    if _PG_SINGLE_INSTANCE_CONN is not None:
        return True
    conn = _pg_connect()
    if conn is None:
        return False
    try:
        _pg_prepare_connection(conn)
        with conn.cursor() as cur:
            cur.execute("SELECT pg_try_advisory_lock(%s)", (_PG_SINGLE_INSTANCE_LOCK_KEY,))
            row = cur.fetchone()
            locked = bool(row and row[0])
        if not locked:
            conn.close()
            print("[DB] Другой экземпляр бота уже использует Neon. Новый экземпляр остановлен.")
            return False
        _PG_SINGLE_INSTANCE_CONN = conn
        print("[DB] Эксклюзивная блокировка экземпляра Neon получена.")
        return True
    except Exception as exc:
        try:
            conn.close()
        except Exception:
            pass
        print(f"[DB] Не удалось получить блокировку экземпляра: {exc}")
        return False


def release_single_instance_lock():
    global _PG_SINGLE_INSTANCE_CONN
    conn = _PG_SINGLE_INSTANCE_CONN
    _PG_SINGLE_INSTANCE_CONN = None
    if conn is None:
        return
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_unlock(%s)", (_PG_SINGLE_INSTANCE_LOCK_KEY,))
    except Exception:
        pass
    try:
        conn.close()
    except Exception:
        pass


def _pg_save(snapshot):
    conn = _pg_connect()

    if conn is None:
        return False

    try:
        _pg_prepare_connection(conn)

        with conn:
            with conn.cursor() as cur:
                # Serialize writers even if a deployment accidentally starts
                # more than one process before the singleton guard is noticed.
                cur.execute("SELECT pg_advisory_xact_lock(%s)", (_PG_SAVE_SERIAL_LOCK_KEY,))
                cur.execute("""
                    INSERT INTO bot_state (id, data, updated_at)
                    VALUES (1, %s, NOW())
                    ON CONFLICT (id) DO UPDATE SET
                        data = EXCLUDED.data,
                        updated_at = NOW()
                """, (Json(snapshot),))

        return True

    finally:
        conn.close()


def _load_local_json():
    if not os.path.exists(DATA_FILE):
        return None

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    except Exception as e:
        print(f"[DB] Ошибка чтения локального JSON: {e}")
        return None

def mark_dirty():
    global db_dirty, db_version, last_db_change_at

    with db_lock:
        db_dirty = True
        db_version += 1
        last_db_change_at = time.time()

def _load_data_from_sources(default_data, normalize_loaded_data):
    if DATABASE_URL:
        try:
            pg_data = _pg_load()
            local_data = _load_local_json()

            if pg_data is not None:
                pg_ts = float(
                    (pg_data.get("_meta") or {}).get("saved_at", 0) or 0
                ) if isinstance(pg_data, dict) else 0.0

                local_ts = float(
                    (local_data.get("_meta") or {}).get("saved_at", 0) or 0
                ) if isinstance(local_data, dict) else 0.0

                local_meta = (local_data.get("_meta") or {}) if isinstance(local_data, dict) else {}
                local_pending = bool(local_meta.get("pending_neon_sync", False))

                # A local file is allowed to override Neon only when it explicitly
                # records that the Neon write was pending. This prevents an old
                # stale rests_data.json from silently overwriting a newer Neon DB.
                if local_pending and local_data is not None and local_ts > pg_ts + 0.5:
                    print("[DB] Локальный snapshot помечен как ожидающий синхронизации; восстанавливается в Neon.")
                    local_normalized = normalize_loaded_data(local_data)
                    local_normalized.setdefault("_meta", {})["pending_neon_sync"] = False
                    try:
                        if _pg_save(local_normalized):
                            print("[DB] Ожидающий локальный snapshot успешно синхронизирован с Neon.")
                            return local_normalized
                    except Exception as sync_error:
                        print(f"[DB] Не удалось синхронизировать pending snapshot: {sync_error}")
                    # Neon remains authoritative when recovery cannot be completed.

                print("[DB] Загружена база из Neon PostgreSQL.")
                return normalize_loaded_data(pg_data)

            if local_data is not None:
                migrated = normalize_loaded_data(local_data)

                if _pg_save(migrated):
                    print(
                        "[DB] Выполнена первичная миграция "
                        "rests_data.json -> Neon PostgreSQL."
                    )

                return migrated

            print(
                "[DB] Neon пустая, локальная JSON-база не найдена. "
                "Создаётся новая база."
            )

            base = normalize_loaded_data(default_data)
            _pg_save(base)
            return base

        except Exception as e:
            print(f"[DB ERROR] Не удалось загрузить Neon: {e}")
            # When DATABASE_URL is configured, silently booting from an old
            # local snapshot is unsafe: the next autosave can overwrite a
            # newer Neon state with stale JSON. Production therefore fails
            # closed by default. Local fallback is an explicit emergency
            # override for operators who understand the risk.
            allow_local_fallback = os.environ.get("ALLOW_LOCAL_DB_FALLBACK", "").strip().lower() in {
                "1", "true", "yes", "on"
            }
            if DATABASE_URL and not allow_local_fallback:
                raise RuntimeError(
                    "Neon database could not be loaded and local fallback is disabled."
                ) from e
            print("[DB] Переключение на локальный JSON как аварийный fallback.")

    local_data = _load_local_json()

    if local_data is not None:
        return normalize_loaded_data(local_data)

    return normalize_loaded_data(default_data)

def load_data(default_data_factory, normalize_loaded_data):
    default_data = default_data_factory()
    return _load_data_from_sources(
        default_data,
        normalize_loaded_data
    )

def save_snapshot(
    snapshot,
    snapshot_version,
    db_version_getter,
    db_dirty_setter,
    send_backup=False,
    db_channel_id=0,
    bot_instance=None
):
    saved_to_pg = False

    try:
        meta = snapshot.setdefault("_meta", {})
        if not isinstance(meta, dict):
            meta = {}
            snapshot["_meta"] = meta
        meta["saved_at"] = time.time()
        # The local file must explicitly remember whether Neon accepted this snapshot.
        # Neon itself should store the canonical snapshot with pending_neon_sync=False.
        meta["pending_neon_sync"] = bool(DATABASE_URL)

        if DATABASE_URL:
            try:
                pg_snapshot = copy.deepcopy(snapshot)
                pg_snapshot.setdefault("_meta", {})["pending_neon_sync"] = False
                saved_to_pg = _pg_save(pg_snapshot)
                if saved_to_pg:
                    snapshot["_meta"]["pending_neon_sync"] = False
                else:
                    raise RuntimeError("PostgreSQL недоступен")

            except Exception as e:
                print(f"[DB ERROR] Ошибка сохранения в Neon: {e}")

        temp_file = f"{DATA_FILE}.tmp"

        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(
                snapshot,
                f,
                ensure_ascii=False,
                indent=4
            )
            f.flush()
            os.fsync(f.fileno())

        os.replace(temp_file, DATA_FILE)

        current_version = db_version_getter()

        if current_version == snapshot_version:
            if saved_to_pg or not DATABASE_URL:
                db_dirty_setter(False)

        if send_backup and db_channel_id and bot_instance:
            # Telegram backup delivery is best-effort. A backup API error must
            # never make an already persisted Neon/local snapshot look failed.
            try:
                with open(DATA_FILE, "rb") as f:
                    msg = bot_instance.send_document(
                        db_channel_id,
                        f,
                        caption="💾 Экстренный бекап базы данных"
                    )

                    try:
                        bot_instance.pin_chat_message(
                            db_channel_id,
                            msg.message_id,
                            disable_notification=True
                        )
                    except Exception as e:
                        print(f"[BACKUP PIN ERROR] {e}")
            except Exception as e:
                print(f"[BACKUP ERROR] {e}")

        return (saved_to_pg or not DATABASE_URL)

    except Exception as e:
        print(f"Ошибка при сохранении базы данных: {e}")
        return False
