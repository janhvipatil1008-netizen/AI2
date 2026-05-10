"""Shared psycopg2 connection management for AI²."""
import os
import re
from contextlib import contextmanager
from urllib.parse import unquote

import psycopg2

DATABASE_URL = os.getenv("SUPABASE_DATABASE_URL", "")


def _connect() -> psycopg2.extensions.connection:
    """
    Open a psycopg2 connection from DATABASE_URL.

    Uses rfind('@') to split credentials from host so that special characters
    in the password (# [ ] ! etc.) never confuse the URL parser.
    Falls back to passing the DSN directly for key=value format strings.
    """
    if not DATABASE_URL:
        raise RuntimeError("SUPABASE_DATABASE_URL env var is not set")

    if DATABASE_URL.startswith(("postgresql://", "postgres://")):
        without_scheme = re.sub(r"^postgresql?://", "", DATABASE_URL)
        at = without_scheme.rfind("@")
        if at == -1:
            raise ValueError("SUPABASE_DATABASE_URL missing '@' — check format")

        credentials = without_scheme[:at]
        host_part   = without_scheme[at + 1:]

        colon = credentials.index(":")
        user     = unquote(credentials[:colon])
        password = credentials[colon + 1:]          # raw — no URL-decode needed

        m = re.match(r"([^:/?#]+)(?::(\d+))?(?:/([^?#]*))?", host_part)
        if not m:
            raise ValueError(f"Cannot parse host from SUPABASE_DATABASE_URL: {host_part!r}")
        host   = m.group(1)
        port   = int(m.group(2) or 5432)
        dbname = m.group(3) or "postgres"

        return psycopg2.connect(
            host=host, port=port, dbname=dbname,
            user=user, password=password,
            connect_timeout=10, sslmode="require",
        )

    # key=value DSN — pass through as-is
    return psycopg2.connect(DATABASE_URL, connect_timeout=10)


@contextmanager
def get_conn():
    """Open a fresh connection per request; commit on success, rollback on error."""
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
