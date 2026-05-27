"""
Verify that GET /debug/storage-health and GET /debug/storage-health-view
have been moved from app.py to routes/debug.py and all behavior is preserved.

Does not start a real DB. Relies on AI2_TEST_MODE=1.
"""

from __future__ import annotations

import os

os.environ["AI2_TEST_MODE"] = "1"
os.environ["ANTHROPIC_API_KEY"] = "test-key"

from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

import app as _app_module
import routes.debug as _debug_module
from app import app

client = TestClient(app)

_TOKEN = "storage-health-split-test-token"
URL_JSON = "/debug/storage-health"
URL_VIEW = "/debug/storage-health-view"


def _fake_session():
    return SimpleNamespace(
        usage_events=[{"id": "e1"}, {"id": "e2"}],
        todos=[{"id": "t1"}],
        topic_progress={"topic-1": {"learn": "done", "quiz": "done", "portfolio_task": "done",
                                     "interview_practice": "done", "reflection": "done"}},
        generated_topic_content={"topic-1": "content"},
        generated_topic_practice={"topic-1": {"quiz": "q", "portfolio_task": None, "interview_practice": None}},
        quiz_submissions={"topic-1": {}},
        portfolio_submissions={},
        interview_submissions={},
        topic_notes={},
        topic_completion_percent=lambda tid: 100 if tid == "topic-1" else 0,
    )


def _fake_session_data():
    return {"session": _fake_session(), "orch": None, "client": None, "profile": None}


# ── Structure checks ──────────────────────────────────────────────────────────

def test_routes_debug_contains_storage_health():
    assert callable(getattr(_debug_module, "debug_storage_health", None))


def test_routes_debug_contains_storage_health_view():
    assert callable(getattr(_debug_module, "debug_storage_health_view", None))


def test_app_includes_debug_router():
    paths = {r.path for r in app.routes}
    assert URL_JSON in paths
    assert URL_VIEW in paths


def test_app_no_longer_directly_defines_storage_health():
    app_path = os.path.join(os.path.dirname(__file__), "..", "app.py")
    with open(app_path, encoding="utf-8") as f:
        source = f.read()
    assert "async def debug_storage_health" not in source
    assert "async def debug_storage_health_view" not in source


def test_app_no_longer_defines_build_storage_health_payload():
    app_path = os.path.join(os.path.dirname(__file__), "..", "app.py")
    with open(app_path, encoding="utf-8") as f:
        source = f.read()
    assert "def _build_storage_health_payload" not in source


# ── /debug/storage-health URL unchanged ──────────────────────────────────────

def test_json_url_unchanged_returns_200(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    assert client.get(URL_JSON).status_code == 200


def test_view_url_unchanged_returns_200(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    assert client.get(URL_VIEW).status_code == 200


def test_view_returns_html(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    resp = client.get(URL_VIEW)
    assert resp.headers["content-type"].startswith("text/html")


# ── Production 404 protection ─────────────────────────────────────────────────

def test_missing_token_returns_404_json(monkeypatch):
    monkeypatch.setenv("AI2_ENV", "production")
    monkeypatch.delenv("AI2_DEBUG_TOKEN", raising=False)
    assert client.get(URL_JSON).status_code == 404


def test_missing_token_returns_404_view(monkeypatch):
    monkeypatch.setenv("AI2_ENV", "production")
    monkeypatch.delenv("AI2_DEBUG_TOKEN", raising=False)
    assert client.get(URL_VIEW).status_code == 404


def test_wrong_token_returns_404_json(monkeypatch):
    monkeypatch.setenv("AI2_ENV", "production")
    monkeypatch.setenv("AI2_DEBUG_TOKEN", _TOKEN)
    assert client.get(URL_JSON, headers={"X-AI2-Debug-Token": "wrong"}).status_code == 404


def test_correct_token_allows_json(monkeypatch):
    monkeypatch.setenv("AI2_ENV", "production")
    monkeypatch.setenv("AI2_DEBUG_TOKEN", _TOKEN)
    assert client.get(URL_JSON, headers={"X-AI2-Debug-Token": _TOKEN}).status_code == 200


def test_correct_token_allows_view(monkeypatch):
    monkeypatch.setenv("AI2_ENV", "production")
    monkeypatch.setenv("AI2_DEBUG_TOKEN", _TOKEN)
    assert client.get(URL_VIEW, headers={"X-AI2-Debug-Token": _TOKEN}).status_code == 200


# ── No-session mode opens no DB connection ────────────────────────────────────

def test_no_session_json_no_db(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    with patch("database.pool._connect", side_effect=AssertionError("DB must not open")) as m:
        resp = client.get(URL_JSON)
    assert resp.status_code == 200
    m.assert_not_called()


def test_no_session_view_no_db(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    with patch("database.pool._connect", side_effect=AssertionError("DB must not open")) as m:
        resp = client.get(URL_VIEW)
    assert resp.status_code == 200
    m.assert_not_called()


# ── Session-id mode returns safe fields only ─────────────────────────────────

def test_session_id_returns_safe_counts(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    with patch("routes.deps.get_session_data", return_value=_fake_session_data()):
        data = client.get(URL_JSON, params={"session_id": "sess-1"}).json()
    ss = data["mirrors"]["learner_state"]["session_status"]
    assert ss["session_loaded"] is True
    assert ss["usage_events_count"] == 2
    assert ss["todos_count"] == 1


def test_session_id_does_not_expose_private_content(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    with patch("routes.deps.get_session_data", return_value=_fake_session_data()):
        resp = client.get(URL_JSON, params={"session_id": "sess-1", "legacy_topic_id": "topic-1"})
    assert "content" not in resp.text or '"content"' not in resp.text


# ── Template rendered by view ─────────────────────────────────────────────────

def test_view_renders_storage_health_template(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    text = client.get(URL_VIEW).text
    assert "Storage Health" in text


def test_view_no_session_shows_config_only_note(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    text = client.get(URL_VIEW).text
    assert "No session_id provided" in text


# ── No secrets/private data in response ──────────────────────────────────────

def test_no_secrets_in_json_response(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    monkeypatch.setenv("SUPABASE_DATABASE_URL", "postgresql://user:secret@host/db")
    resp = client.get(URL_JSON)
    assert "postgresql://" not in resp.text
    assert "secret" not in resp.text


def test_no_secrets_in_view_response(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-live-secret-key")
    resp = client.get(URL_VIEW)
    assert "sk-live-secret-key" not in resp.text


# ── /debug/storage-status still works ────────────────────────────────────────

def test_storage_status_still_works(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    assert client.get("/debug/storage-status").status_code == 200


# ── Other debug/admin routes still in app.py ─────────────────────────────────

def test_admin_beta_metrics_still_accessible(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    assert client.get("/admin/beta-metrics").status_code == 200


def test_curriculum_db_check_still_accessible(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    assert client.get("/debug/curriculum-db-check").status_code == 200


def test_other_debug_routes_still_in_app_py():
    app_path = os.path.join(os.path.dirname(__file__), "..", "app.py")
    with open(app_path, encoding="utf-8") as f:
        source = f.read()
    assert "async def admin_beta_metrics" in source
    assert "async def debug_curriculum_db_check" in source
