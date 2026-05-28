"""
Verify that GET /admin/beta-metrics has been moved from app.py to
routes/admin.py and all behavior is preserved.

Does not start a real DB.  Relies on AI2_TEST_MODE=1.
"""

from __future__ import annotations

import os

os.environ["AI2_TEST_MODE"] = "1"
os.environ["ANTHROPIC_API_KEY"] = "test-key"

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

import routes.admin as _admin_module
from app import app

client = TestClient(app)

_TOKEN = "admin-split-test-token"
URL = "/admin/beta-metrics"


# ── Fake helpers ──────────────────────────────────────────────────────────────

@contextmanager
def _conn_ctx():
    yield MagicMock()


def _fake_metrics():
    return {
        "session_user_summary":     {"total_sessions": 1, "total_users": 1},
        "usage_summary":            {"total_usage_events": 0, "claude_events": 0,
                                     "cache_events": 0, "limit_blocked_events": 0},
        "learning_outcomes_summary": {"total_outcomes": 0, "baseline_completed_count": 0,
                                      "post_completed_count": 0, "improved_count": 0,
                                      "average_improvement_delta": 0.0},
        "beta_feedback_summary":    {"total_feedback_submissions": 0,
                                     "average_usefulness_score": 0.0,
                                     "average_clarity_score": 0.0,
                                     "willingness_to_pay_counts": {}},
        "cache_summary":            {"total_rows": 0, "active_rows": 0, "stale_rows": 0},
        "topic_notes":              None,
    }


# ── Structure checks ──────────────────────────────────────────────────────────

def test_routes_admin_module_exists():
    import routes.admin
    assert routes.admin is not None


def test_routes_admin_defines_router():
    from fastapi import APIRouter
    assert isinstance(_admin_module.router, APIRouter)


def test_routes_admin_contains_admin_beta_metrics():
    assert callable(getattr(_admin_module, "admin_beta_metrics", None))


def test_app_includes_admin_router():
    paths = {r.path for r in app.routes}
    assert URL in paths


def test_app_no_longer_directly_defines_admin_beta_metrics():
    app_path = os.path.join(os.path.dirname(__file__), "..", "app.py")
    with open(app_path, encoding="utf-8") as f:
        source = f.read()
    assert "async def admin_beta_metrics" not in source


# ── Route URL unchanged ───────────────────────────────────────────────────────

def test_url_unchanged_returns_200(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    with patch("routes.admin.get_conn", side_effect=RuntimeError("no db")):
        assert client.get(URL).status_code == 200


def test_url_returns_html(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    with patch("routes.admin.get_conn", side_effect=RuntimeError("no db")):
        resp = client.get(URL)
    assert resp.headers["content-type"].startswith("text/html")


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
    with patch("routes.admin.get_conn", side_effect=RuntimeError("no db")):
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


# ── DB-unavailable fallback preserved ────────────────────────────────────────

def test_db_unavailable_returns_200(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    with patch("routes.admin.get_conn", side_effect=RuntimeError("timeout")):
        resp = client.get(URL)
    assert resp.status_code == 200


def test_db_unavailable_shows_unavailable_text(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    with patch("routes.admin.get_conn", side_effect=RuntimeError("timeout")):
        resp = client.get(URL)
    assert "DB metrics: unavailable" in resp.text


def test_db_available_shows_available_text(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    with patch("routes.admin.get_conn", return_value=_conn_ctx()), \
         patch("repositories.beta_metrics_repository.collect_beta_metrics",
               return_value=_fake_metrics()):
        resp = client.get(URL)
    assert "DB metrics: available" in resp.text


# ── Template rendering ────────────────────────────────────────────────────────

def test_renders_beta_metrics_template(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    with patch("routes.admin.get_conn", side_effect=RuntimeError("no db")):
        resp = client.get(URL)
    assert "AI² Beta Metrics" in resp.text


def test_at_most_one_db_connection(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    mock_conn = MagicMock(return_value=_conn_ctx())
    with patch("routes.admin.get_conn", mock_conn), \
         patch("repositories.beta_metrics_repository.collect_beta_metrics",
               return_value=_fake_metrics()):
        client.get(URL)
    assert mock_conn.call_count <= 1


# ── No secrets / private data exposed ────────────────────────────────────────

def test_no_secrets_in_error_response(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    monkeypatch.setenv("SUPABASE_DATABASE_URL", "postgresql://user:secret@host/db")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-live-secret")
    with patch("routes.admin.get_conn",
               side_effect=RuntimeError("connect failed: postgresql://user:secret@host/db")):
        resp = client.get(URL)
    assert "postgresql://" not in resp.text
    assert "sk-live-secret" not in resp.text
    assert "SUPABASE_DATABASE_URL" not in resp.text
    assert "ANTHROPIC_API_KEY" not in resp.text


def test_token_not_in_response_body(monkeypatch):
    monkeypatch.setenv("AI2_ENV", "production")
    monkeypatch.setenv("AI2_DEBUG_TOKEN", _TOKEN)
    with patch("routes.admin.get_conn", side_effect=RuntimeError("no db")):
        resp = client.get(URL, headers={"X-AI2-Debug-Token": _TOKEN})
    assert _TOKEN not in resp.text
    assert "AI2_DEBUG_TOKEN" not in resp.text


# ── /debug/* routes still work ───────────────────────────────────────────────

def test_debug_storage_status_still_works(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    assert client.get("/debug/storage-status").status_code == 200


def test_debug_storage_health_still_works(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    assert client.get("/debug/storage-health").status_code == 200


def test_debug_modular_curriculum_still_works(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    with patch("routes.debug.get_conn", side_effect=RuntimeError("no db")):
        assert client.get("/debug/modular-curriculum").status_code == 200
