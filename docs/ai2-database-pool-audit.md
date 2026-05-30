# AI² Database Pool Audit

## 1. Current database/pool.py Behavior

`database/pool.py` opens a **fresh psycopg2 connection on every call** to `get_conn()`.

```python
@contextmanager
def get_conn():
    conn = _connect()   # new TCP handshake + TLS + auth every time
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()    # connection destroyed, not recycled
```

`_connect()` parses `SUPABASE_DATABASE_URL`, splits credentials from host using
`rfind('@')` (safe for passwords containing `#`, `[`, `!`, etc.), and calls
`psycopg2.connect(... connect_timeout=10, sslmode="require")`.

**Consequence:** Every DB-touching request opens, authenticates, and tears down a
full TLS connection to Supabase/Postgres. On Render's free tier this adds ~50–200 ms
of latency per request and counts against the Postgres `max_connections` limit every
time a request is in flight.

`_connect()` is also exported and used directly in `routes/dashboard.py` as
`_open_db_connection`. This is the only caller that bypasses the context manager.

---

## 2. Current get_conn Callers

| File | Function / Route | Import style | Closes conn? | Risk |
|---|---|---|---|---|
| `app.py` | `_load_session_from_db`, `_ensure_schema` | top-level `from database.pool import get_conn` | No — context manager handles it | Low |
| `routes/admin.py` | `GET /admin/beta-metrics` | top-level import | No — CM | Low |
| `routes/auth_routes.py` | login / register handlers | top-level import | No — CM | Low |
| `routes/dashboard.py` | `GET /dashboard` | top-level import (also imports `_connect` directly) | No — CM | **Medium** — `_connect` import will break if pool removes `_connect` |
| `routes/debug.py` | 10 debug endpoints | top-level import | No — CM | Low |
| `routes/deps.py` | `get_session_data`, `save_session`, `get_user_history`, `load_profile_db`, `save_profile_db`, and others | **lazy** — `from database.pool import get_conn` inside each function body | No — CM | **Medium** — lazy import creates a new binding per call; patching `database.pool.get_conn` will work but patching `routes.deps.get_conn` will NOT (no module-level binding exists) |
| `routes/onboarding.py` | onboarding handlers | top-level import | No — CM | Low |
| `routes/submissions.py` | `POST /quiz/submit` etc. | lazy import inside function | No — CM | Medium — same lazy-import caveat as deps.py |
| `routes/topics.py` | topic content/practice generate | lazy import inside functions | No — CM | Medium |
| `services/session_persistence.py` | `save_session`, `get_session_data`, `get_user_history`, `save_profile_db`, `load_profile_db`, `get_learner_history` | top-level import | No — CM | Low |
| `jobs/database.py` | `get_jobs`, `get_job_with_enrichment`, `get_stats` | top-level import; re-exports `get_conn` for `fetcher`/`enricher` | No — CM | Low |
| `jobs/fetcher.py` | `fetch_jobs` | lazy import from `jobs.database` | No — CM | Low |
| `jobs/enricher.py` | `enrich_job`, `save_enrichment` | lazy import from `jobs.database` | No — CM | Low |
| `repositories/*.py` | All repository functions | **None** — repositories accept an injected connection; they do not call `get_conn` themselves | N/A — caller owns conn lifetime | Low |

**Summary:** Every caller uses `with get_conn() as conn:`. No caller calls `conn.close()`
manually. The context manager owns the full connection lifecycle.

---

## 3. Required Compatibility

A replacement pool must preserve all of the following:

1. **`get_conn()` remains a context manager (`@contextmanager`).**
   All call sites use `with get_conn() as conn:` — changing this signature would
   require touching every caller.

2. **`conn.close()` behavior must be safe for callers that never call it.**
   Since no caller calls `conn.close()` outside the CM, a pool that intercepts
   `close()` to return the connection to the pool is transparent to all existing code.
   The CM's `finally: conn.close()` is the only close path.

3. **Caller commit/rollback is not required.**
   The CM commits on exit and rolls back on exception. Callers do not call
   `conn.commit()` or `conn.rollback()` themselves.

4. **Tests that monkeypatch module-local `get_conn` must continue to work.**
   Tests patch `routes.admin.get_conn`, `routes.debug.get_conn`, `app_module.get_conn`,
   etc. These work because those modules do `from database.pool import get_conn` at
   the top level, creating a module-level name. Any pool refactor must not change the
   public `get_conn` name in `database/pool.py`.

5. **DB unavailable fallback behavior must be preserved.**
   Every caller wraps `with get_conn() as conn:` in a `try/except` and falls back
   gracefully. The pool must raise an exception (not hang) on connection failure.
   `connect_timeout=10` must be preserved.

6. **No schema changes.** The pool is purely a runtime connection management change.

7. **No import-time migrations.** `_ensure_schema` in `app.py` runs schema SQL at
   startup event — the pool must not run migrations at import time.

8. **`TEST_MODE` paths must not open connections.**
   Callers in `services/session_persistence.py` and `routes/deps.py` guard DB calls
   with `if not TEST_MODE`. The pool must not eagerly open connections on startup
   when `AI2_TEST_MODE=1`.

9. **`_connect()` must remain accessible** (or `routes/dashboard.py` must be updated).
   `routes/dashboard.py` imports `_connect as _open_db_connection` at module level.
   If `_connect` is removed or renamed, `routes/dashboard.py` will break at import time.

---

## 4. Recommended Pool Design

Use `psycopg2.pool.ThreadedConnectionPool` with **lazy initialization** — the pool
object is created on first use, not at import time.

```python
# database/pool.py  (proposed design — not yet implemented)

import threading
from contextlib import contextmanager
from psycopg2.pool import ThreadedConnectionPool

_pool: ThreadedConnectionPool | None = None
_pool_lock = threading.Lock()

MIN_CONN = 1
MAX_CONN = 5   # safe for Render free-tier Postgres (max_connections ~25)

def _get_pool() -> ThreadedConnectionPool:
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:          # double-checked locking
                _pool = ThreadedConnectionPool(
                    MIN_CONN, MAX_CONN,
                    dsn=_build_dsn(),   # existing _connect() DSN logic
                    connect_timeout=10,
                    sslmode="require",
                )
    return _pool

@contextmanager
def get_conn():
    """Borrow a connection from the pool; return it on exit."""
    pool = _get_pool()
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)   # returns to pool — never destroys

def close_all_connections():
    """Drain the pool — for graceful shutdown and test teardown."""
    global _pool
    if _pool is not None:
        _pool.closeall()
        _pool = None
```

Key decisions:

- **Lazy initialization** — `_pool` is `None` at import time; first `with get_conn()`
  call triggers `_get_pool()`. No connection is opened during `import database.pool`.
- **`ThreadedConnectionPool`** — safe for FastAPI's sync thread pool (used by
  `run_in_executor`). `SimpleConnectionPool` is not thread-safe.
- **`minconn=1, maxconn=5`** — conservative for Render free-tier (max_connections ~25).
  Leaves room for Supabase dashboard, pgAdmin, and other app instances.
- **`pool.putconn(conn)`** replaces `conn.close()` in the CM `finally` block. All
  callers continue using `with get_conn() as conn:` with no code changes required.
- **`close_all_connections()`** — provides a clean shutdown hook for
  `@app.on_event("shutdown")` and test teardown. Also resets `_pool = None`
  so the next `get_conn()` reinitializes the pool (useful in test isolation).
- **`_connect()` kept** — as an internal helper that builds the DSN. `routes/dashboard.py`
  imports it as `_open_db_connection`; keeping it avoids a breaking change in that file.
- **`TEST_MODE` safety** — when `AI2_TEST_MODE=1` all callers guard with `if not TEST_MODE`
  before calling `get_conn()`. The pool is never initialized in test runs because
  `get_conn()` is never reached. No additional test-mode guard needed in `pool.py`.

---

## 5. Risks

| Risk | Description | Mitigation |
|---|---|---|
| **Connection leak** | If a caller `break`s out of the `with` block early or an exception bypasses the CM exit, the connection is not returned to the pool. | The `@contextmanager` `finally` block guarantees `putconn` even on exception. `break` inside a `with` block still triggers `__exit__`. |
| **Callers calling `conn.close()`** | If any caller manually closes the connection, it is removed from the pool rather than returned. The pool shrinks below `minconn`. | Audit confirmed **no caller calls `conn.close()` manually**. The CM's `finally: pool.putconn(conn)` is the only close path. |
| **Tests patching wrong target** | Tests that patch `routes.admin.get_conn` patch the module-level name bound at import time. This continues to work. Tests that would try to patch `routes.deps.get_conn` would fail — no such module-level binding exists there (lazy imports). | Do not add module-level `get_conn` to `routes/deps.py`. Keep lazy imports. Patch the correct target per-module. |
| **Pool initialized at import time** | If `_get_pool()` is called during `import database.pool` (e.g., at module scope), it will attempt a live DB connection during test collection. | Lazy init with `_pool = None` at module scope prevents this. Pool is only created on first `with get_conn()`. |
| **Render / Postgres `max_connections`** | Render free Postgres allows ~25 connections. Multiple Render dyno instances each hold a pool. `maxconn=5` × N dynos must not exceed `max_connections`. | Start with `maxconn=5`. Monitor with `SELECT count(*) FROM pg_stat_activity`. Increase only with evidence. |
| **Pool exhaustion under load** | `ThreadedConnectionPool.getconn()` raises `PoolError` when all connections are checked out. | `PoolError` propagates as a 500 to the route handler, which is caught by existing `try/except` fallbacks. Log and monitor; raise `maxconn` if needed. |
| **Stale connections** | Long-lived pool connections may go idle and be terminated by Supabase/Postgres (typically after 5–10 min of inactivity). | Set `keepalives=1, keepalives_idle=30` in `psycopg2.connect()`. Or catch `OperationalError` in the CM and reinitialize the pool. |

---

## 6. Test Plan

Tests to write in `tests/test_database_pool.py` after implementation:

| Test | What it verifies |
|---|---|
| `test_get_conn_import_compatible` | `from database.pool import get_conn` succeeds; `get_conn` is callable |
| `test_get_conn_is_context_manager` | `get_conn()` can be used with `with ... as conn:` when pool is mocked |
| `test_pool_lazy_initializes` | `_pool` is `None` immediately after import; only non-None after first `get_conn()` call with live DB or mock |
| `test_pool_not_initialized_in_test_mode` | When `AI2_TEST_MODE=1` and all callers guard with `if not TEST_MODE`, `_pool` remains `None` throughout a full test session |
| `test_putconn_called_on_normal_exit` | Mocked `pool.putconn` is called after a successful `with get_conn()` block |
| `test_putconn_called_on_exception` | Mocked `pool.putconn` is called even when the `with` block raises |
| `test_rollback_called_on_exception` | `conn.rollback()` is called when the `with` block raises |
| `test_close_all_connections_drains_pool` | `close_all_connections()` calls `pool.closeall()` and resets `_pool = None` |
| `test_db_failure_raises_not_hangs` | If `_connect()` raises `psycopg2.OperationalError`, `get_conn()` propagates it within 15 s |
| `test_existing_route_tests_still_pass` | All tests that patch `routes.admin.get_conn`, `routes.debug.get_conn`, etc. continue to pass unchanged |

---

## 7. Recommended Next Implementation Step

**Implement the pool in `database/pool.py` only.**

1. Replace the `@contextmanager def get_conn()` body with a `ThreadedConnectionPool`
   implementation as designed in Section 4.
2. Keep `_connect()` as a private helper (preserves `routes/dashboard.py`).
3. Keep `get_conn()` as a `@contextmanager` with identical call signature.
4. Add `close_all_connections()` and wire it to `@app.on_event("shutdown")` in `app.py`.
5. No other file needs to change.
6. Run the full focused regression (408 tests) to confirm no regressions.

Do **not** change routes, services, repositories, schema, or tests in this step.
The pool is an internal implementation detail of `database/pool.py`.
