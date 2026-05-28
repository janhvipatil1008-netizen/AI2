"""
Verify that GET /debug/modular-curriculum has been moved from app.py to
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

_TOKEN = "modular-curriculum-split-test-token"
URL = "/debug/modular-curriculum"
_FALLBACK_SVC = "services.modular_curriculum_fallback_service"


# ── Fake helpers ──────────────────────────────────────────────────────────────

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


def _fake_course_result(source="fallback"):
    return {
        "source": source,
        "course_structure": {
            "course": {"course_key": "aipm-foundations", "course_id": None},
            "modules": [],
            "unassigned_topics": [],
        },
        "error": None,
    }


# ── Structure checks ──────────────────────────────────────────────────────────

def test_routes_debug_contains_modular_curriculum():
    assert callable(getattr(_debug_module, "debug_modular_curriculum", None))


def test_app_includes_debug_router():
    paths = {r.path for r in app.routes}
    assert URL in paths


def test_app_no_longer_directly_defines_modular_curriculum():
    app_path = os.path.join(os.path.dirname(__file__), "..", "app.py")
    with open(app_path, encoding="utf-8") as f:
        source = f.read()
    assert "async def debug_modular_curriculum" not in source


# ── Route URL unchanged ───────────────────────────────────────────────────────

def test_url_unchanged_returns_200(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    with patch("routes.debug.get_conn", _fake_get_conn_raises(RuntimeError("no db"))):
        assert client.get(URL).status_code == 200


def test_url_returns_json(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    with patch("routes.debug.get_conn", _fake_get_conn_raises(RuntimeError("no db"))):
        resp = client.get(URL)
    assert resp.headers["content-type"].startswith("application/json")


# ── Production 404 protection ─────────────────────────────────────────────────

def test_missing_token_returns_404(monkeypatch):
    monkeypatch.setenv("AI2_ENV", "production")
    monkeypatch.delenv("AI2_DEBUG_TOKEN", raising=False)
    assert client.get(URL).status_code == 404


def test_wrong_token_returns_404(monkeypatch):
    monkeypatch.setenv("AI2_ENV", "production")
    monkeypatch.setenv("AI2_DEBUG_TOKEN", _TOKEN)
    assert client.get(URL, headers={"X-AI2-Debug-Token": "wrong"}).status_code == 404


def test_correct_token_returns_200(monkeypatch):
    monkeypatch.setenv("AI2_ENV", "production")
    monkeypatch.setenv("AI2_DEBUG_TOKEN", _TOKEN)
    with patch("routes.debug.get_conn", _fake_get_conn_raises(RuntimeError("no db"))):
        resp = client.get(URL, headers={"X-AI2-Debug-Token": _TOKEN})
    assert resp.status_code == 200


# ── Unauthorized requests do not open DB connection ───────────────────────────

def test_unauthorized_no_db(monkeypatch):
    monkeypatch.setenv("AI2_ENV", "production")
    monkeypatch.delenv("AI2_DEBUG_TOKEN", raising=False)
    with patch("database.pool._connect", side_effect=AssertionError("DB must not open")) as m:
        resp = client.get(URL)
    assert resp.status_code == 404
    m.assert_not_called()


# ── Response shape preserved ──────────────────────────────────────────────────

def test_course_mode_response_shape(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    conn = _make_conn()
    with patch("routes.debug.get_conn", _fake_get_conn(conn)), \
         patch(f"{_FALLBACK_SVC}.get_course_structure_with_fallback",
               return_value=_fake_course_result("db")):
        data = client.get(URL).json()
    required = {"mode", "course_key", "source", "course_structure", "error", "notes"}
    assert required.issubset(data.keys())
    assert data["mode"] == "course"


def test_topic_mode_response_shape(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    conn = _make_conn()
    topic_result = {"source": "db", "topic": {"legacy_topic_id": "rag-basics"}, "error": None}
    with patch("routes.debug.get_conn", _fake_get_conn(conn)), \
         patch(f"{_FALLBACK_SVC}.get_topic_structure_by_legacy_id_with_fallback",
               return_value=topic_result):
        data = client.get(URL, params={"legacy_topic_id": "rag-basics"}).json()
    required = {"mode", "legacy_topic_id", "source", "topic", "error", "notes"}
    assert required.issubset(data.keys())
    assert data["mode"] == "topic"


def test_fallback_on_db_error_returns_200(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    with patch("routes.debug.get_conn", _fake_get_conn_raises(RuntimeError("timeout"))):
        resp = client.get(URL)
    assert resp.status_code == 200
    assert resp.json()["course_structure"] is not None


# ── No secrets / private data exposed ────────────────────────────────────────

def test_no_secrets_in_success_response(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    monkeypatch.setenv("SUPABASE_DATABASE_URL", "postgresql://user:secret@host/db")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-live-secret")
    conn = _make_conn()
    with patch("routes.debug.get_conn", _fake_get_conn(conn)), \
         patch(f"{_FALLBACK_SVC}.get_course_structure_with_fallback",
               return_value=_fake_course_result("db")):
        resp = client.get(URL)
    assert "postgresql://" not in resp.text
    assert "sk-live-secret" not in resp.text
    assert "SUPABASE_DATABASE_URL" not in resp.text


def test_no_secrets_in_error_response(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    monkeypatch.setenv("SUPABASE_DATABASE_URL", "postgresql://user:secret@host/db")
    with patch("routes.debug.get_conn",
               _fake_get_conn_raises(RuntimeError("connect failed: postgresql://user:secret@host/db"))):
        resp = client.get(URL)
    assert "postgresql://" not in resp.text
    assert "secret" not in resp.text
    assert "SUPABASE_DATABASE_URL" not in resp.text


# ── Other routes still work ───────────────────────────────────────────────────

def test_storage_status_still_works(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    assert client.get("/debug/storage-status").status_code == 200


def test_storage_health_still_works(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    assert client.get("/debug/storage-health").status_code == 200


def test_learner_state_mismatch_still_works(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    with patch("routes.deps.get_session_data",
               return_value={"session": None, "orch": None, "client": None, "profile": None}), \
         patch("services.storage_flags.is_progress_db_reads_enabled", return_value=False), \
         patch("services.storage_flags.is_todos_db_reads_enabled", return_value=False):
        assert client.get("/debug/learner-state-mismatch-check").status_code == 200


# ── /admin/beta-metrics remains in app.py ────────────────────────────────────

def test_admin_beta_metrics_still_in_app_py():
    app_path = os.path.join(os.path.dirname(__file__), "..", "app.py")
    with open(app_path, encoding="utf-8") as f:
        source = f.read()
    assert "async def admin_beta_metrics" in source


def test_moved_route_not_in_app_py():
    app_path = os.path.join(os.path.dirname(__file__), "..", "app.py")
    with open(app_path, encoding="utf-8") as f:
        source = f.read()
    assert "async def debug_modular_curriculum" not in source
