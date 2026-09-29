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


def _pg_save(snapshot):
    conn = _pg_connect()

    if conn is None:
        return False

    try:
        _pg_prepare_connection(conn)

        with conn:
            with conn.cursor() as cur:
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

                if local_data is not None and local_ts > pg_ts + 1.0:
                    print("[DB] Локальный snapshot новее Neon; восстанавливается в Neon.")

                    local_normalized = normalize_loaded_data(local_data)

                    try:
                        if _pg_save(local_normalized):
                            print("[DB] Локальный snapshot успешно синхронизирован с Neon.")
                    except Exception as sync_error:
                        print(
                            f"[DB] Не удалось синхронизировать локальный snapshot "
                            f"с Neon: {sync_error}"
                        )

                    return local_normalized

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
