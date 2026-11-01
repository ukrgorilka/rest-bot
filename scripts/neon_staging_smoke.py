#!/usr/bin/env python3
"""Safe Neon smoke test for NyaBot's real core.database snapshot adapter.

Required environment:
  NYABOT_TEST_DATABASE_URL=<separate, empty Neon test database URL>
  NYABOT_STAGING_CONFIRM=I_CREATED_A_SEPARATE_NEON_TEST_DATABASE
Optional production URL comparison:
  DATABASE_URL or NYABOT_PRODUCTION_DATABASE_URL

The script refuses to touch a non-empty bot_state row or active bot lease. It
writes one temporary marker with core.database._pg_save(), reads it using the
adapter's fresh-connection _pg_load(), and deletes only the marker it created.
"""
from __future__ import annotations

import os
import sys
import uuid
from urllib.parse import urlparse

CONFIRM = "I_CREATED_A_SEPARATE_NEON_TEST_DATABASE"


def _endpoint(url: str) -> tuple[str, str]:
    parsed = urlparse(url)
    return (parsed.hostname or "").lower(), parsed.path.strip("/")


def main() -> int:
    test_url = os.environ.get("NYABOT_TEST_DATABASE_URL", "").strip()
    if not test_url:
        print("BLOCKED: set NYABOT_TEST_DATABASE_URL to a separate Neon staging database.", file=sys.stderr)
        return 2
    if os.environ.get("NYABOT_STAGING_CONFIRM", "").strip() != CONFIRM:
        print(f"BLOCKED: set NYABOT_STAGING_CONFIRM={CONFIRM} only after verifying that the database is disposable.", file=sys.stderr)
        return 2

    parsed = urlparse(test_url)
    if parsed.scheme not in ("postgres", "postgresql") or not parsed.hostname:
        print("BLOCKED: NYABOT_TEST_DATABASE_URL is not a PostgreSQL URL.", file=sys.stderr)
        return 2
    if "neon.tech" not in (parsed.hostname or "").lower() and os.environ.get("NYABOT_TEST_ALLOW_NON_NEON") != "1":
        print("BLOCKED: this smoke test expects a Neon endpoint (neon.tech).", file=sys.stderr)
        return 2
    production_url = os.environ.get("DATABASE_URL", "").strip() or os.environ.get("NYABOT_PRODUCTION_DATABASE_URL", "").strip()
    if production_url and _endpoint(test_url) == _endpoint(production_url):
        print("BLOCKED: staging and production point at the same host/database.", file=sys.stderr)
        return 2

    # core.database reads DATABASE_URL at import time; explicitly override it
    # before importing any app persistence module. No bot polling is started.
    os.environ["DATABASE_URL"] = test_url
    os.environ["ALLOW_JSON_BOOTSTRAP"] = "0"
    try:
        import psycopg2
    except ImportError:
        print("BLOCKED: install project requirements (psycopg2-binary).", file=sys.stderr)
        return 2

    try:
        with psycopg2.connect(test_url, connect_timeout=10, application_name="nyabot-v014-staging-preflight") as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT current_database(), current_user")
                db_name, db_user = cur.fetchone()
                cur.execute("""SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema='public' AND table_name='bot_state'
                )""")
                has_state_table = cur.fetchone()[0]
                if has_state_table:
                    cur.execute("SELECT 1 FROM bot_state WHERE id=1 LIMIT 1")
                    if cur.fetchone():
                        print("BLOCKED: staging bot_state already contains a snapshot; use a fresh empty Neon test database.", file=sys.stderr)
                        return 2
                cur.execute("""SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema='public' AND table_name='bot_runtime_lock'
                )""")
                if cur.fetchone()[0]:
                    cur.execute("SELECT 1 FROM bot_runtime_lock WHERE expires_at > NOW() LIMIT 1")
                    if cur.fetchone():
                        print("BLOCKED: an active bot runtime lease exists in this database.", file=sys.stderr)
                        return 2
    except Exception as exc:
        print(f"NEON PREFLIGHT FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    from core import database
    marker = {"_nyabot_staging_probe": str(uuid.uuid4()), "version": "0.14", "probe": True}
    row_created = False
    try:
        # The preflight established that this row is absent; matching-marker
        # cleanup is safe even if the server committed but the client errored.
        row_created = True
        if not database._pg_save(marker):
            raise RuntimeError("_pg_save() returned False")
        loaded = database._pg_load()
        if loaded != marker:
            raise RuntimeError("fresh-connection _pg_load() did not match the saved marker")
        print(f"PASS: core.database Neon snapshot round-trip succeeded (database={db_name}, role={db_user}).")
        return 0
    except Exception as exc:
        print(f"NEON SNAPSHOT TEST FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    finally:
        if row_created:
            try:
                with psycopg2.connect(test_url, connect_timeout=10, application_name="nyabot-v014-staging-cleanup") as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "DELETE FROM bot_state WHERE id=1 AND data->>'_nyabot_staging_probe' = %s",
                            (marker["_nyabot_staging_probe"],),
                        )
            except Exception as exc:
                print(f"WARNING: staging marker cleanup failed; inspect the disposable test DB bot_state row: {type(exc).__name__}: {exc}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
