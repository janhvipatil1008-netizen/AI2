"""
Verify that GET /debug/learner-state-mismatch-check and
GET /debug/learner-state-fallback-check have been moved from app.py to
routes/debug.py and all behavior is preserved.

Does not start a real DB.  Relies on AI2_TEST_MODE=1.
"""

from __future__ import annotations

import os

os.environ["AI2_TEST_MODE"] = "1"
os.environ["ANTHROPIC_API_KEY"] = "test-key"

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

import routes.debug as _debug_module
from app import app

client = TestClient(app)

_TOKEN = "learner-state-split-test-token"

URL_MISMATCH = "/debug/learner-state-mismatch-check"
URL_FALLBACK = "/debug/learner-state-fallback-check"


# ── Fake helpers ──────────────────────────────────────────────────────────────

def _make_conn():
    conn = MagicMock()
    conn.close = MagicMock()
    return conn


@contextmanager
def _fake_get_conn_raises(exc):
    raise exc
    yield  # pragma: no cover


_FAKE_FALLBACK_RESULT = {
    "topic_progress_result": {"source": "fallback", "topic_progress": {}, "error": None, "notes": []},
    "todos_result":          {"source": "fallback", "todos": [], "error": None, "notes": []},
    "source_summary":        {"topic_progress_source": "fallback", "todos_source": "fallback"},
    "notes": [],
}

_FAKE_COMPARISON = {"matches": True, "comparisons": []}


def _fake_session_data():
    from config import CareerTrack
    from context.session import SessionContext
    s = SessionContext(track=CareerTrack.AI_PM)
    return {"session": s, "orch": None, "client": None, "profile": None}


# ── Structure checks ──────────────────────────────────────────────────────────

def test_routes_debug_contains_learner_state_mismatch_check():
    assert callable(getattr(_debug_module, "debug_learner_state_mismatch_check", None))


def test_routes_debug_contains_learner_state_fallback_check():
    assert callable(getattr(_debug_module, "debug_learner_state_fallback_check", None))


def test_app_includes_debug_router_mismatch():
    paths = {r.path for r in app.routes}
    assert URL_MISMATCH in paths


def test_app_includes_debug_router_fallback():
    paths = {r.path for r in app.routes}
    assert URL_FALLBACK in paths


def test_app_no_longer_directly_defines_mismatch_check():
    app_path = os.path.join(os.path.dirname(__file__), "..", "app.py")
    with open(app_path, encoding="utf-8") as f:
        source = f.read()
    assert "async def debug_learner_state_mismatch_check" not in source


def test_app_no_longer_directly_defines_fallback_check():
    app_path = os.path.join(os.path.dirname(__file__), "..", "app.py")
    with open(app_path, encoding="utf-8") as f:
        source = f.read()
    assert "async def debug_learner_state_fallback_check" not in source


# ── Route URLs unchanged ──────────────────────────────────────────────────────

def test_mismatch_url_unchanged_returns_200(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    with patch("routes.deps.get_session_data", return_value=_fake_session_data()), \
         patch("services.storage_flags.is_progress_db_reads_enabled", return_value=False), \
         patch("services.storage_flags.is_todos_db_reads_enabled", return_value=False):
        assert client.get(URL_MISMATCH).status_code == 200


def test_fallback_url_unchanged_returns_200(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    with patch("routes.deps.get_session_data", return_value=_fake_session_data()), \
         patch("services.storage_flags.is_progress_db_reads_enabled", return_value=False), \
         patch("services.storage_flags.is_todos_db_reads_enabled", return_value=False):
        assert client.get(URL_FALLBACK).status_code == 200


# ── Production 404 protection ─────────────────────────────────────────────────

def test_missing_token_returns_404_mismatch(monkeypatch):
    monkeypatch.setenv("AI2_ENV", "production")
    monkeypatch.delenv("AI2_DEBUG_TOKEN", raising=False)
    assert client.get(URL_MISMATCH).status_code == 404


def test_missing_token_returns_404_fallback(monkeypatch):
    monkeypatch.setenv("AI2_ENV", "production")
    monkeypatch.delenv("AI2_DEBUG_TOKEN", raising=False)
    assert client.get(URL_FALLBACK).status_code == 404


def test_wrong_token_returns_404_mismatch(monkeypatch):
    monkeypatch.setenv("AI2_ENV", "production")
    monkeypatch.setenv("AI2_DEBUG_TOKEN", _TOKEN)
    assert client.get(URL_MISMATCH, headers={"X-AI2-Debug-Token": "wrong"}).status_code == 404


def test_correct_token_allows_mismatch(monkeypatch):
    monkeypatch.setenv("AI2_ENV", "production")
    monkeypatch.setenv("AI2_DEBUG_TOKEN", _TOKEN)
    with patch("routes.deps.get_session_data", return_value=_fake_session_data()), \
         patch("services.storage_flags.is_progress_db_reads_enabled", return_value=False), \
         patch("services.storage_flags.is_todos_db_reads_enabled", return_value=False):
        assert client.get(URL_MISMATCH, headers={"X-AI2-Debug-Token": _TOKEN}).status_code == 200


def test_correct_token_allows_fallback(monkeypatch):
    monkeypatch.setenv("AI2_ENV", "production")
    monkeypatch.setenv("AI2_DEBUG_TOKEN", _TOKEN)
    with patch("routes.deps.get_session_data", return_value=_fake_session_data()), \
         patch("services.storage_flags.is_progress_db_reads_enabled", return_value=False), \
         patch("services.storage_flags.is_todos_db_reads_enabled", return_value=False):
        assert client.get(URL_FALLBACK, headers={"X-AI2-Debug-Token": _TOKEN}).status_code == 200


# ── Unauthorized requests do not open DB connection ───────────────────────────

def test_unauthorized_mismatch_no_db(monkeypatch):
    monkeypatch.setenv("AI2_ENV", "production")
    monkeypatch.delenv("AI2_DEBUG_TOKEN", raising=False)
    with patch("database.pool._connect", side_effect=AssertionError("DB must not open")) as m:
        resp = client.get(URL_MISMATCH)
    assert resp.status_code == 404
    m.assert_not_called()


def test_unauthorized_fallback_no_db(monkeypatch):
    monkeypatch.setenv("AI2_ENV", "production")
    monkeypatch.delenv("AI2_DEBUG_TOKEN", raising=False)
    with patch("database.pool._connect", side_effect=AssertionError("DB must not open")) as m:
        resp = client.get(URL_FALLBACK)
    assert resp.status_code == 404
    m.assert_not_called()


# ── Both flags off: no DB connection ─────────────────────────────────────────

def test_mismatch_flags_off_no_db(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    with patch("routes.deps.get_session_data", return_value=_fake_session_data()), \
         patch("database.pool._connect", side_effect=AssertionError("DB must not open")) as m, \
         patch("services.storage_flags.is_progress_db_reads_enabled", return_value=False), \
         patch("services.storage_flags.is_todos_db_reads_enabled", return_value=False):
        resp = client.get(URL_MISMATCH)
    assert resp.status_code == 200
    assert resp.json()["attempted_db_connection"] is False
    m.assert_not_called()


def test_fallback_flags_off_no_db(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    with patch("routes.deps.get_session_data", return_value=_fake_session_data()), \
         patch("database.pool._connect", side_effect=AssertionError("DB must not open")) as m, \
         patch("services.storage_flags.is_progress_db_reads_enabled", return_value=False), \
         patch("services.storage_flags.is_todos_db_reads_enabled", return_value=False):
        resp = client.get(URL_FALLBACK)
    assert resp.status_code == 200
    assert resp.json()["attempted_db_connection"] is False
    m.assert_not_called()


# ── Response shape preserved ──────────────────────────────────────────────────

def test_mismatch_response_shape(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    with patch("routes.deps.get_session_data", return_value=_fake_session_data()), \
         patch("services.storage_flags.is_progress_db_reads_enabled", return_value=False), \
         patch("services.storage_flags.is_todos_db_reads_enabled", return_value=False):
        data = client.get(URL_MISMATCH).json()
    required = {
        "session_id", "legacy_topic_id",
        "progress_db_reads_enabled", "todos_db_reads_enabled",
        "attempted_db_connection", "source", "matches",
        "comparison", "error", "notes",
    }
    assert required.issubset(data.keys())


def test_fallback_response_shape(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    with patch("routes.deps.get_session_data", return_value=_fake_session_data()), \
         patch("services.storage_flags.is_progress_db_reads_enabled", return_value=False), \
         patch("services.storage_flags.is_todos_db_reads_enabled", return_value=False):
        data = client.get(URL_FALLBACK).json()
    required = {
        "session_id", "legacy_topic_id",
        "progress_db_reads_enabled", "todos_db_reads_enabled",
        "attempted_db_connection", "result", "source_summary",
        "error", "notes",
    }
    assert required.issubset(data.keys())


# ── No secrets / private data exposed ────────────────────────────────────────

def test_no_secrets_mismatch(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    monkeypatch.setenv("SUPABASE_DATABASE_URL", "postgresql://user:secret@host/db")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-live-secret")
    with patch("routes.deps.get_session_data", return_value=_fake_session_data()), \
         patch("services.storage_flags.is_progress_db_reads_enabled", return_value=False), \
         patch("services.storage_flags.is_todos_db_reads_enabled", return_value=False):
        resp = client.get(URL_MISMATCH)
    assert "postgresql://" not in resp.text
    assert "sk-live-secret" not in resp.text
    assert "SUPABASE_DATABASE_URL" not in resp.text


def test_no_secrets_fallback(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    monkeypatch.setenv("SUPABASE_DATABASE_URL", "postgresql://user:secret@host/db")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-live-secret")
    with patch("routes.deps.get_session_data", return_value=_fake_session_data()), \
         patch("services.storage_flags.is_progress_db_reads_enabled", return_value=False), \
         patch("services.storage_flags.is_todos_db_reads_enabled", return_value=False):
        resp = client.get(URL_FALLBACK)
    assert "postgresql://" not in resp.text
    assert "sk-live-secret" not in resp.text
    assert "SUPABASE_DATABASE_URL" not in resp.text


def test_no_secrets_in_mismatch_error_response(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    monkeypatch.setenv("SUPABASE_DATABASE_URL", "postgresql://user:secret@host/db")
    with patch("routes.deps.get_session_data", return_value=_fake_session_data()), \
         patch("services.storage_flags.is_progress_db_reads_enabled", return_value=True), \
         patch("services.storage_flags.is_todos_db_reads_enabled", return_value=False), \
         patch("routes.debug.get_conn", side_effect=RuntimeError("conn failed")):
        resp = client.get(URL_MISMATCH)
    assert resp.status_code == 200
    assert "SUPABASE_DATABASE_URL" not in resp.text
    assert "ANTHROPIC_API_KEY" not in resp.text


# ── Other routes still accessible / still in app.py ──────────────────────────

def test_storage_status_still_works(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    assert client.get("/debug/storage-status").status_code == 200


def test_storage_health_still_works(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    assert client.get("/debug/storage-health").status_code == 200


def test_learner_state_db_check_still_works(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    with patch("services.storage_flags.is_progress_db_reads_enabled", return_value=False), \
         patch("services.storage_flags.is_todos_db_reads_enabled", return_value=False):
        assert client.get("/debug/learner-state-db-check").status_code == 200


def test_admin_beta_metrics_still_in_app_py():
    app_path = os.path.join(os.path.dirname(__file__), "..", "app.py")
    with open(app_path, encoding="utf-8") as f:
        source = f.read()
    assert "async def admin_beta_metrics" in source


def test_modular_curriculum_not_in_app_py():
    app_path = os.path.join(os.path.dirname(__file__), "..", "app.py")
    with open(app_path, encoding="utf-8") as f:
        source = f.read()
    assert "async def debug_modular_curriculum" not in source


def test_moved_routes_not_in_app_py():
    app_path = os.path.join(os.path.dirname(__file__), "..", "app.py")
    with open(app_path, encoding="utf-8") as f:
        source = f.read()
    assert "async def debug_learner_state_mismatch_check" not in source
    assert "async def debug_learner_state_fallback_check" not in source
