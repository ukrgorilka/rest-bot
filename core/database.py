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
