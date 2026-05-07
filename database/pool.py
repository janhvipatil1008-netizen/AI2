"""Shared psycopg2 connection pool for AI² — imported by app.py and jobs modules."""
import os
from contextlib import contextmanager

import psycopg2
from psycopg2.pool import ThreadedConnectionPool

DATABASE_URL = os.getenv("SUPABASE_DATABASE_URL", "")
_pool: ThreadedConnectionPool | None = None


def _get_pool() -> ThreadedConnectionPool:
    global _pool
    if _pool is None:
        if not DATABASE_URL:
            raise RuntimeError("SUPABASE_DATABASE_URL env var is not set")
        _pool = ThreadedConnectionPool(minconn=2, maxconn=10, dsn=DATABASE_URL)
    return _pool


@contextmanager
def get_conn():
    """Yield a psycopg2 connection; commit on success, rollback on exception."""
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
