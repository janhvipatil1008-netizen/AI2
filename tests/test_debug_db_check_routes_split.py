"""
Verify that GET /debug/curriculum-db-check, GET /debug/curriculum-fallback-check,
and GET /debug/learner-state-db-check have been moved from app.py to
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

_TOKEN = "db-check-split-test-token"

URL_CURRICULUM   = "/debug/curriculum-db-check"
URL_FALLBACK     = "/debug/curriculum-fallback-check"
URL_LEARNER      = "/debug/learner-state-db-check"


# ── Fake DB helpers ───────────────────────────────────────────────────────────

def _make_conn():
    conn = MagicMock()
    conn.close = MagicMock()
    return conn


def _fake_get_conn(conn):
    @contextmanager
    def _ctx():
        try:
            yield conn
        finally:
            conn.close()
    return _ctx


def _fake_get_conn_raises(exc):
    @contextmanager
    def _ctx():
        raise exc
        yield  # pragma: no cover
    return _ctx


# ── Structure checks ──────────────────────────────────────────────────────────

def test_routes_debug_contains_curriculum_db_check():
    assert callable(getattr(_debug_module, "debug_curriculum_db_check", None))


def test_routes_debug_contains_curriculum_fallback_check():
    assert callable(getattr(_debug_module, "debug_curriculum_fallback_check", None))


def test_routes_debug_contains_learner_state_db_check():
    assert callable(getattr(_debug_module, "debug_learner_state_db_check", None))


def test_app_includes_debug_router():
    paths = {r.path for r in app.routes}
    assert URL_CURRICULUM in paths
    assert URL_FALLBACK   in paths
    assert URL_LEARNER    in paths


def test_app_no_longer_directly_defines_curriculum_db_check():
    app_path = os.path.join(os.path.dirname(__file__), "..", "app.py")
    with open(app_path, encoding="utf-8") as f:
        source = f.read()
    assert "async def debug_curriculum_db_check" not in source


def test_app_no_longer_directly_defines_curriculum_fallback_check():
    app_path = os.path.join(os.path.dirname(__file__), "..", "app.py")
    with open(app_path, encoding="utf-8") as f:
        source = f.read()
    assert "async def debug_curriculum_fallback_check" not in source


def test_app_no_longer_directly_defines_learner_state_db_check():
    app_path = os.path.join(os.path.dirname(__file__), "..", "app.py")
    with open(app_path, encoding="utf-8") as f:
        source = f.read()
    assert "async def debug_learner_state_db_check" not in source


# ── Route URLs unchanged ──────────────────────────────────────────────────────

def test_curriculum_db_check_url_unchanged(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    with patch("services.storage_flags.is_curriculum_db_reads_enabled", return_value=False):
        assert client.get(URL_CURRICULUM).status_code == 200


def test_curriculum_fallback_url_unchanged(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    with patch("services.storage_flags.is_curriculum_db_reads_enabled", return_value=False):
        assert client.get(URL_FALLBACK).status_code == 200


def test_learner_state_db_check_url_unchanged(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    with patch("services.storage_flags.is_progress_db_reads_enabled", return_value=False), \
         patch("services.storage_flags.is_todos_db_reads_enabled", return_value=False):
        assert client.get(URL_LEARNER).status_code == 200


# ── Production 404 protection ─────────────────────────────────────────────────

def test_missing_token_returns_404_curriculum(monkeypatch):
    monkeypatch.setenv("AI2_ENV", "production")
    monkeypatch.delenv("AI2_DEBUG_TOKEN", raising=False)
    assert client.get(URL_CURRICULUM).status_code == 404


def test_missing_token_returns_404_fallback(monkeypatch):
    monkeypatch.setenv("AI2_ENV", "production")
    monkeypatch.delenv("AI2_DEBUG_TOKEN", raising=False)
    assert client.get(URL_FALLBACK).status_code == 404


def test_missing_token_returns_404_learner(monkeypatch):
    monkeypatch.setenv("AI2_ENV", "production")
    monkeypatch.delenv("AI2_DEBUG_TOKEN", raising=False)
    assert client.get(URL_LEARNER).status_code == 404


def test_wrong_token_returns_404_curriculum(monkeypatch):
    monkeypatch.setenv("AI2_ENV", "production")
    monkeypatch.setenv("AI2_DEBUG_TOKEN", _TOKEN)
    assert client.get(URL_CURRICULUM, headers={"X-AI2-Debug-Token": "wrong"}).status_code == 404


def test_correct_token_allows_curriculum(monkeypatch):
    monkeypatch.setenv("AI2_ENV", "production")
    monkeypatch.setenv("AI2_DEBUG_TOKEN", _TOKEN)
    with patch("services.storage_flags.is_curriculum_db_reads_enabled", return_value=False):
        assert client.get(URL_CURRICULUM, headers={"X-AI2-Debug-Token": _TOKEN}).status_code == 200


def test_correct_token_allows_fallback(monkeypatch):
    monkeypatch.setenv("AI2_ENV", "production")
    monkeypatch.setenv("AI2_DEBUG_TOKEN", _TOKEN)
    with patch("services.storage_flags.is_curriculum_db_reads_enabled", return_value=False):
        assert client.get(URL_FALLBACK, headers={"X-AI2-Debug-Token": _TOKEN}).status_code == 200


def test_correct_token_allows_learner(monkeypatch):
    monkeypatch.setenv("AI2_ENV", "production")
    monkeypatch.setenv("AI2_DEBUG_TOKEN", _TOKEN)
    with patch("services.storage_flags.is_progress_db_reads_enabled", return_value=False), \
         patch("services.storage_flags.is_todos_db_reads_enabled", return_value=False):
        assert client.get(URL_LEARNER, headers={"X-AI2-Debug-Token": _TOKEN}).status_code == 200


# ── Unauthorized requests do not open DB connection ───────────────────────────

def test_unauthorized_curriculum_no_db(monkeypatch):
    monkeypatch.setenv("AI2_ENV", "production")
    monkeypatch.delenv("AI2_DEBUG_TOKEN", raising=False)
    with patch("database.pool._connect", side_effect=AssertionError("DB must not open")) as m:
        resp = client.get(URL_CURRICULUM)
    assert resp.status_code == 404
    m.assert_not_called()


def test_unauthorized_learner_no_db(monkeypatch):
    monkeypatch.setenv("AI2_ENV", "production")
    monkeypatch.delenv("AI2_DEBUG_TOKEN", raising=False)
    with patch("database.pool._connect", side_effect=AssertionError("DB must not open")) as m:
        resp = client.get(URL_LEARNER)
    assert resp.status_code == 404
    m.assert_not_called()


# ── Flag-off / no-DB behavior preserved ──────────────────────────────────────

def test_curriculum_flag_off_no_db_connection(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    with patch("database.pool._connect", side_effect=AssertionError("DB must not open")) as m, \
         patch("services.storage_flags.is_curriculum_db_reads_enabled", return_value=False):
        resp = client.get(URL_CURRICULUM)
    assert resp.status_code == 200
    assert resp.json()["attempted_db_connection"] is False
    m.assert_not_called()


def test_fallback_flag_off_no_db_connection(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    with patch("database.pool._connect", side_effect=AssertionError("DB must not open")) as m, \
         patch("services.storage_flags.is_curriculum_db_reads_enabled", return_value=False):
        resp = client.get(URL_FALLBACK)
    assert resp.status_code == 200
    assert resp.json()["attempted_db_connection"] is False
    m.assert_not_called()


def test_learner_both_flags_off_no_db_connection(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    with patch("database.pool._connect", side_effect=AssertionError("DB must not open")) as m, \
         patch("services.storage_flags.is_progress_db_reads_enabled", return_value=False), \
         patch("services.storage_flags.is_todos_db_reads_enabled", return_value=False):
        resp = client.get(URL_LEARNER)
    assert resp.status_code == 200
    assert resp.json()["attempted_db_connection"] is False
    m.assert_not_called()


# ── Response shape preserved ──────────────────────────────────────────────────

def test_curriculum_response_shape(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    with patch("services.storage_flags.is_curriculum_db_reads_enabled", return_value=False):
        data = client.get(URL_CURRICULUM).json()
    required = {
        "curriculum_db_reads_enabled", "attempted_db_connection",
        "track_key", "legacy_topic_id", "track_found", "topic_found",
        "track", "topic", "source", "error", "notes",
    }
    assert required.issubset(data.keys())


def test_fallback_response_shape(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    with patch("services.storage_flags.is_curriculum_db_reads_enabled", return_value=False):
        data = client.get(URL_FALLBACK).json()
    required = {
        "track_key", "legacy_topic_id", "include_topics",
        "curriculum_db_reads_enabled", "attempted_db_connection",
        "track_result", "topic_result", "topics_result",
        "source_summary", "error", "notes",
    }
    assert required.issubset(data.keys())


def test_learner_response_shape(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    with patch("services.storage_flags.is_progress_db_reads_enabled", return_value=False), \
         patch("services.storage_flags.is_todos_db_reads_enabled", return_value=False):
        data = client.get(URL_LEARNER).json()
    required = {
        "progress_db_reads_enabled", "todos_db_reads_enabled",
        "attempted_db_connection", "session_id", "legacy_topic_id",
        "progress_found", "todos_found", "topic_progress", "todos",
        "source", "error", "notes",
    }
    assert required.issubset(data.keys())


# ── No secrets / private data exposed ────────────────────────────────────────

def test_no_secrets_curriculum_flag_off(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    monkeypatch.setenv("SUPABASE_DATABASE_URL", "postgresql://user:secret@host/db")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-live-secret")
    with patch("services.storage_flags.is_curriculum_db_reads_enabled", return_value=False):
        resp = client.get(URL_CURRICULUM)
    assert "postgresql://" not in resp.text
    assert "sk-live-secret" not in resp.text
    assert "SUPABASE_DATABASE_URL" not in resp.text
    assert "ANTHROPIC_API_KEY" not in resp.text


def test_no_secrets_learner_flag_off(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    monkeypatch.setenv("SUPABASE_DATABASE_URL", "postgresql://user:secret@host/db")
    with patch("services.storage_flags.is_progress_db_reads_enabled", return_value=False), \
         patch("services.storage_flags.is_todos_db_reads_enabled", return_value=False):
        resp = client.get(URL_LEARNER)
    assert "postgresql://" not in resp.text
    assert "SUPABASE_DATABASE_URL" not in resp.text


def test_no_secrets_in_curriculum_error_response(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    monkeypatch.setenv("SUPABASE_DATABASE_URL", "postgresql://user:secret@host/db")
    with patch("services.storage_flags.is_curriculum_db_reads_enabled", return_value=True), \
         patch("routes.debug.get_conn", _fake_get_conn_raises(RuntimeError("conn failed"))):
        resp = client.get(URL_CURRICULUM)
    assert resp.status_code == 200
    assert "SUPABASE_DATABASE_URL" not in resp.text
    assert "ANTHROPIC_API_KEY" not in resp.text


# ── Other endpoints still work ────────────────────────────────────────────────

def test_storage_status_still_works(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    assert client.get("/debug/storage-status").status_code == 200


def test_storage_health_still_works(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    assert client.get("/debug/storage-health").status_code == 200


def test_admin_beta_metrics_still_in_app_py():
    app_path = os.path.join(os.path.dirname(__file__), "..", "app.py")
    with open(app_path, encoding="utf-8") as f:
        source = f.read()
    assert "async def admin_beta_metrics" not in source


def test_other_debug_routes_still_in_app_py():
    app_path = os.path.join(os.path.dirname(__file__), "..", "app.py")
    with open(app_path, encoding="utf-8") as f:
        source = f.read()
    assert "async def debug_curriculum_db_check" not in source
    assert "async def debug_curriculum_fallback_check" not in source
    assert "async def debug_learner_state_db_check" not in source
    assert "async def debug_generated_learning_db_check" not in source
    assert "async def debug_usage_events_db_check" not in source
    assert "async def debug_modular_curriculum" not in source
