"""Shared psycopg2 connection management for AI2."""
import os
import re
import threading
from contextlib import contextmanager
from urllib.parse import unquote

import psycopg2
import psycopg2.pool

DATABASE_URL = os.getenv("SUPABASE_DATABASE_URL", "")
DB_POOL_MINCONN = 1
DB_POOL_MAXCONN = 5

_pool = None
_pool_lock = threading.Lock()


def _connection_args():
    """
    Build psycopg2 connection arguments from DATABASE_URL.

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
            raise ValueError("SUPABASE_DATABASE_URL missing '@' - check format")

        credentials = without_scheme[:at]
        host_part = without_scheme[at + 1:]

        colon = credentials.index(":")
        user = unquote(credentials[:colon])
        password = credentials[colon + 1:]  # raw - no URL-decode needed

        m = re.match(r"([^:/?#]+)(?::(\d+))?(?:/([^?#]*))?", host_part)
        if not m:
            raise ValueError(f"Cannot parse host from SUPABASE_DATABASE_URL: {host_part!r}")
        host = m.group(1)
        port = int(m.group(2) or 5432)
        dbname = m.group(3) or "postgres"

        return (), {
            "host": host,
            "port": port,
            "dbname": dbname,
            "user": user,
            "password": password,
            "connect_timeout": 10,
            "sslmode": "require",
        }

    # key=value DSN - pass through as-is
    return (DATABASE_URL,), {"connect_timeout": 10}


def _connect() -> psycopg2.extensions.connection:
    """Open a direct psycopg2 connection from DATABASE_URL."""
    args, kwargs = _connection_args()
    return psycopg2.connect(*args, **kwargs)


def _get_pool():
    """Create the process-local connection pool on first use."""
    global _pool

    if _pool is None:
        with _pool_lock:
            if _pool is None:
                args, kwargs = _connection_args()
                _pool = psycopg2.pool.ThreadedConnectionPool(
                    DB_POOL_MINCONN,
                    DB_POOL_MAXCONN,
                    *args,
                    **kwargs,
                )

    return _pool


@contextmanager
def get_conn():
    """Borrow a pooled connection; commit on success, rollback on error."""
    pool = _get_pool()
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


def close_all_connections():
    """Close all pooled connections and reset lazy initialization state."""
    global _pool

    with _pool_lock:
        if _pool is not None:
            _pool.closeall()
            _pool = None
