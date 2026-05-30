"""Structural tests for docs/ai2-database-pool-audit.md.

Verifies the audit document exists and covers all required topics.
Does not execute any application code and does not change runtime behaviour.
"""

from __future__ import annotations

from pathlib import Path

DOC = Path("docs/ai2-database-pool-audit.md")


def _doc() -> str:
    return DOC.read_text(encoding="utf-8")


# ── Document exists ───────────────────────────────────────────────────────────

def test_audit_doc_exists():
    assert DOC.exists(), f"{DOC} not found"


def test_audit_doc_is_not_empty():
    assert len(_doc()) > 500


# ── Mentions key files and symbols ───────────────────────────────────────────

def test_doc_mentions_pool_py():
    assert "database/pool.py" in _doc()


def test_doc_mentions_get_conn():
    assert "get_conn" in _doc()


def test_doc_mentions_connect():
    assert "_connect" in _doc()


# ── Lazy initialization ───────────────────────────────────────────────────────

def test_doc_mentions_lazy_initialization():
    doc = _doc().lower()
    assert "lazy" in doc and ("init" in doc or "initial" in doc)


def test_doc_mentions_pool_none_at_import():
    doc = _doc()
    assert "_pool" in doc or "None" in doc


# ── Caller close behavior ─────────────────────────────────────────────────────

def test_doc_mentions_caller_close_behavior():
    doc = _doc().lower()
    assert "close" in doc and ("caller" in doc or "conn.close" in doc)


def test_doc_mentions_putconn():
    assert "putconn" in _doc()


def test_doc_confirms_no_caller_closes_manually():
    doc = _doc().lower()
    assert "no caller" in doc or "never" in doc


# ── Tests monkeypatching ──────────────────────────────────────────────────────

def test_doc_mentions_tests_monkeypatching_get_conn():
    doc = _doc()
    assert "routes.admin.get_conn" in doc or "monkeypatch" in doc.lower() or "patch" in doc.lower()


def test_doc_mentions_module_local_patching():
    doc = _doc().lower()
    assert "module" in doc and ("patch" in doc or "local" in doc)


# ── Render / Postgres connection limits ──────────────────────────────────────

def test_doc_mentions_render_postgres_limits():
    doc = _doc().lower()
    assert "render" in doc and ("max_connections" in doc or "connection limit" in doc or "max conn" in doc)


def test_doc_mentions_maxconn():
    doc = _doc().lower()
    assert "maxconn" in doc or "max_conn" in doc or "maxconn" in doc


# ── ThreadedConnectionPool ────────────────────────────────────────────────────

def test_doc_recommends_threaded_connection_pool():
    assert "ThreadedConnectionPool" in _doc()


def test_doc_explains_why_not_simple_pool():
    doc = _doc().lower()
    assert "thread" in doc and ("safe" in doc or "simple" in doc)


# ── close_all_connections ─────────────────────────────────────────────────────

def test_doc_mentions_close_all_connections():
    assert "close_all_connections" in _doc()


# ── TEST_MODE safety ──────────────────────────────────────────────────────────

def test_doc_mentions_test_mode_safety():
    doc = _doc()
    assert "TEST_MODE" in doc or "test_mode" in doc.lower()


# ── Implement in database/pool.py only ───────────────────────────────────────

def test_doc_recommends_implementing_pool_py_only():
    doc = _doc().lower()
    assert "database/pool.py" in _doc()
    assert "only" in doc or "no other file" in doc


def test_doc_says_no_other_files_need_to_change():
    doc = _doc().lower()
    assert "no other file" in doc or "only" in doc


# ── Risk coverage ─────────────────────────────────────────────────────────────

def test_doc_mentions_connection_leak_risk():
    doc = _doc().lower()
    assert "leak" in doc


def test_doc_mentions_pool_exhaustion_risk():
    doc = _doc().lower()
    assert "exhaust" in doc or "pool error" in doc or "poolerror" in doc


def test_doc_mentions_stale_connections():
    doc = _doc().lower()
    assert "stale" in doc or "idle" in doc or "keepalive" in doc


# ── Caller table coverage ─────────────────────────────────────────────────────

def test_doc_covers_routes_admin():
    assert "routes/admin.py" in _doc()


def test_doc_covers_routes_debug():
    assert "routes/debug.py" in _doc()


def test_doc_covers_services_session_persistence():
    assert "services/session_persistence.py" in _doc()


def test_doc_covers_routes_deps_lazy_import():
    doc = _doc()
    assert "routes/deps.py" in doc
    assert "lazy" in doc.lower()


def test_doc_covers_jobs_database():
    assert "jobs/database.py" in _doc()


def test_doc_covers_repositories():
    doc = _doc().lower()
    assert "repositor" in doc
