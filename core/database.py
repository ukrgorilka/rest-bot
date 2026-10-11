import os
import json
import copy
import time
import threading
import uuid

import psycopg2
from psycopg2.extras import Json


DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
DATA_FILE = os.environ.get("DATA_FILE", "rests_data.json").strip() or "rests_data.json"
ALLOW_JSON_BOOTSTRAP = os.environ.get("ALLOW_JSON_BOOTSTRAP", "").strip().lower() in {"1", "true", "yes", "on"}

db_lock = threading.RLock()
DB_SAVE_LOCK = threading.RLock()

db_dirty = False
db_version = 0
last_db_change_at = 0.0


_PG_SCHEMA_LOCK = threading.Lock()
_PG_SCHEMA_READY = False
_PG_SINGLE_INSTANCE_OWNER = None
_PG_SINGLE_INSTANCE_GUARD = threading.RLock()
_PG_SINGLE_INSTANCE_LEASE_SECONDS = 90
_PG_SINGLE_INSTANCE_RENEW_INTERVAL = 15.0
_PG_SINGLE_INSTANCE_LAST_RENEWED_AT = 0.0
_PG_LEGACY_SINGLE_INSTANCE_LOCK_KEY = 741923811
_PG_SAVE_SERIAL_LOCK_KEY = 741923812



def _pg_connect():
    if not DATABASE_URL:
        return None
    return psycopg2.connect(
        DATABASE_URL,
        connect_timeout=10,
        application_name='nyabot',
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10,
        keepalives_count=3,
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
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS bot_runtime_lock (
                        lock_name TEXT PRIMARY KEY,
                        owner_token TEXT NOT NULL,
                        expires_at TIMESTAMPTZ NOT NULL,
                        heartbeat_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
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


def _claim_or_renew_singleton_lease(owner_token):
    """Atomically claim/renew a DB row lease (safe with Neon pooler URLs)."""
    conn = _pg_connect()
    if conn is None:
        return False
    try:
        _pg_prepare_connection(conn)
        with conn:
            with conn.cursor() as cur:
                # Compatibility gate for a rolling Railway deploy: older builds
                # use this session-level advisory key. The xact-scoped probe is
                # safe with Neon transaction poolers and conflicts with that old
                # lock, so the new version waits for the old poller to exit.
                cur.execute(
                    "SELECT pg_try_advisory_xact_lock(%s)",
                    (_PG_LEGACY_SINGLE_INSTANCE_LOCK_KEY,),
                )
                legacy_gate = cur.fetchone()
                if not legacy_gate or not legacy_gate[0]:
                    return False

                # Keep the compatibility gate and lease write in the same DB
                # transaction. This also serializes races between new instances.
                cur.execute(
                    """
                    INSERT INTO bot_runtime_lock (lock_name, owner_token, expires_at, heartbeat_at)
                    VALUES ('nyabot', %s, NOW() + (%s::int * INTERVAL '1 second'), NOW())
                    ON CONFLICT (lock_name) DO UPDATE SET
                        owner_token = EXCLUDED.owner_token,
                        expires_at = EXCLUDED.expires_at,
                        heartbeat_at = NOW()
                    WHERE bot_runtime_lock.expires_at <= NOW()
                       OR bot_runtime_lock.owner_token = EXCLUDED.owner_token
                    RETURNING owner_token
                    """,
                    (owner_token, _PG_SINGLE_INSTANCE_LEASE_SECONDS),
                )
                row = cur.fetchone()
                return bool(row and row[0] == owner_token)
    finally:
        conn.close()


def _get_singleton_owner_token():
    global _PG_SINGLE_INSTANCE_OWNER
    if _PG_SINGLE_INSTANCE_OWNER is None:
        _PG_SINGLE_INSTANCE_OWNER = uuid.uuid4().hex
    return _PG_SINGLE_INSTANCE_OWNER


def acquire_single_instance_lock():
    """Acquire NyaBot's distributed Neon lease before Telegram polling."""
    global _PG_SINGLE_INSTANCE_LAST_RENEWED_AT
    if not DATABASE_URL:
        return True

    with _PG_SINGLE_INSTANCE_GUARD:
        owner_token = _get_singleton_owner_token()
        try:
            acquired = _claim_or_renew_singleton_lease(owner_token)
        except Exception as exc:
            print(f"[DB] Не удалось получить Neon singleton lease: {exc}")
            return False
        if not acquired:
            print("[DB] Другой экземпляр бота владеет Neon singleton lease. Новый экземпляр остановлен.")
            return False
        _PG_SINGLE_INSTANCE_LAST_RENEWED_AT = time.monotonic()
        print("[DB] Эксклюзивная аренда экземпляра Neon получена/продлена.")
        return True


def release_single_instance_lock():
    """Release only the lease owned by this process; never delete another owner's lease."""
    global _PG_SINGLE_INSTANCE_OWNER, _PG_SINGLE_INSTANCE_LAST_RENEWED_AT
    if not DATABASE_URL:
        return
    with _PG_SINGLE_INSTANCE_GUARD:
        owner_token = _PG_SINGLE_INSTANCE_OWNER
        _PG_SINGLE_INSTANCE_OWNER = None
        _PG_SINGLE_INSTANCE_LAST_RENEWED_AT = 0.0
        if not owner_token:
            return
        try:
            conn = _pg_connect()
        except Exception as exc:
            print(f"[DB] Не удалось подключиться к Neon для освобождения singleton lease; она истечёт автоматически: {exc}")
            return
        if conn is None:
            return  # The lease will expire naturally if Neon is temporarily unavailable.
        try:
            _pg_prepare_connection(conn)
            with conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM bot_runtime_lock WHERE lock_name = 'nyabot' AND owner_token = %s",
                        (owner_token,),
                    )
        except Exception as exc:
            print(f"[DB] Не удалось освободить Neon singleton lease; она истечёт автоматически: {exc}")
        finally:
            conn.close()


def single_instance_lock_is_alive():
    """Renew the singleton lease periodically and fail closed if ownership is lost."""
    global _PG_SINGLE_INSTANCE_LAST_RENEWED_AT
    if not DATABASE_URL:
        return True

    with _PG_SINGLE_INSTANCE_GUARD:
        owner_token = _get_singleton_owner_token()
        now = time.monotonic()
        # A 90-second DB lease with 15-second renewals tolerates long-poll waits
        # and avoids an extra SQL write for every individual Telegram update.
        if _PG_SINGLE_INSTANCE_LAST_RENEWED_AT and now - _PG_SINGLE_INSTANCE_LAST_RENEWED_AT < _PG_SINGLE_INSTANCE_RENEW_INTERVAL:
            return True
        try:
            alive = _claim_or_renew_singleton_lease(owner_token)
        except Exception as exc:
            print(f"[DB] Neon singleton lease heartbeat failed: {exc}")
            return False
        if not alive:
            print("[DB] Neon singleton lease is owned by another process or has been removed; polling must stop.")
            return False
        _PG_SINGLE_INSTANCE_LAST_RENEWED_AT = now
        return True


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

            if pg_data is not None:
                # Neon is the canonical source of live progress. Local JSON is
                # only a backup and must never be copied on top of existing Neon
                # state, even when a local snapshot claims to be newer.
                print("[DB] Загружена каноническая база из Neon PostgreSQL; локальный JSON не накатывается поверх неё.")
                return normalize_loaded_data(pg_data)

            local_data = _load_local_json()
            if local_data is not None and ALLOW_JSON_BOOTSTRAP:
                migrated = normalize_loaded_data(local_data)
                if not _pg_save(migrated):
                    raise RuntimeError(
                        "Neon is empty and explicit JSON bootstrap was requested, but the bootstrap snapshot could not be saved to Neon."
                    )
                print(
                    "[DB] Выполнена ЯВНАЯ первичная миграция "
                    "rests_data.json -> Neon PostgreSQL (ALLOW_JSON_BOOTSTRAP=1)."
                )
                return migrated

            if local_data is not None and not ALLOW_JSON_BOOTSTRAP:
                print("[DB] Neon не содержит bot_state. Старый rests_data.json НЕ используется без ALLOW_JSON_BOOTSTRAP=1.")

            print("[DB] Neon пустая; создаётся новая база из встроенных дефолтов.")
            base = normalize_loaded_data(default_data)
            if not _pg_save(base):
                raise RuntimeError("Neon is empty and the initial default state could not be persisted.")
            return base

        except RuntimeError:
            # Internal safety failures (for example, a failed initial/bootstrap write)
            # must remain explicit and must never be downgraded into a generic fallback.
            raise
        except Exception as e:
            print(f"[DB ERROR] Не удалось загрузить Neon: {e}")
            # Never start the live economy from a local backup while DATABASE_URL
            # is configured. Neon may become reachable again and an autosave of
            # the stale snapshot could overwrite real player progress.
            if DATABASE_URL:
                raise RuntimeError(
                    "Neon database could not be loaded; refusing to boot from local JSON."
                ) from e

    if ALLOW_JSON_BOOTSTRAP:
        local_data = _load_local_json()
        if local_data is not None:
            return normalize_loaded_data(local_data)
        print("[DB] DATABASE_URL не задан, но ALLOW_JSON_BOOTSTRAP=1; локальный JSON не найден — используются дефолты.")
    else:
        print("[DB] DATABASE_URL не задан. rests_data.json не используется без явного ALLOW_JSON_BOOTSTRAP=1.")

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
