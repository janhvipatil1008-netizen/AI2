"""
Verify that GET /debug/storage-status has been moved from app.py to routes/debug.py
and that all behavior is preserved.

Does not start a real DB. Relies on AI2_TEST_MODE=1.
"""

from __future__ import annotations

import os

os.environ["AI2_TEST_MODE"] = "1"
os.environ["ANTHROPIC_API_KEY"] = "test-key"

from unittest.mock import patch

from fastapi import APIRouter
from fastapi.testclient import TestClient

import app as _app_module
import routes.debug as _debug_module
from app import app

client = TestClient(app)

_TOKEN = "storage-status-split-test-token"
URL = "/debug/storage-status"


# ── Structure checks ──────────────────────────────────────────────────────────

def test_routes_debug_module_exists():
    import importlib
    mod = importlib.import_module("routes.debug")
    assert mod is not None


def test_routes_debug_defines_api_router():
    assert isinstance(_debug_module.router, APIRouter)


def test_app_includes_debug_router():
    routes = [r.path for r in app.routes]
    assert URL in routes, f"{URL} not found in app routes: {routes}"


def test_app_no_longer_directly_defines_debug_storage_status():
    app_path = os.path.join(os.path.dirname(__file__), "..", "app.py")
    with open(app_path, encoding="utf-8") as f:
        source = f.read()
    assert 'async def debug_storage_status' not in source, (
        "app.py still directly defines debug_storage_status; it should be in routes/debug.py"
    )


def test_debug_storage_status_defined_in_routes_debug():
    assert callable(getattr(_debug_module, "debug_storage_status", None)), (
        "routes.debug must define debug_storage_status"
    )


# ── Route URL unchanged ───────────────────────────────────────────────────────

def test_route_url_unchanged_returns_200(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    assert client.get(URL).status_code == 200


def test_route_url_returns_json(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    resp = client.get(URL)
    assert resp.headers["content-type"].startswith("application/json")


# ── Production protection preserved ──────────────────────────────────────────

def test_missing_token_returns_404_in_production(monkeypatch):
    monkeypatch.setenv("AI2_ENV", "production")
    monkeypatch.delenv("AI2_DEBUG_TOKEN", raising=False)
    assert client.get(URL).status_code == 404


def test_wrong_token_returns_404_in_production(monkeypatch):
    monkeypatch.setenv("AI2_ENV", "production")
    monkeypatch.setenv("AI2_DEBUG_TOKEN", _TOKEN)
    assert client.get(URL, headers={"X-AI2-Debug-Token": "wrong"}).status_code == 404


def test_correct_token_returns_200_in_production(monkeypatch):
    monkeypatch.setenv("AI2_ENV", "production")
    monkeypatch.setenv("AI2_DEBUG_TOKEN", _TOKEN)
    assert client.get(URL, headers={"X-AI2-Debug-Token": _TOKEN}).status_code == 200


# ── No DB connection for unauthorized requests ────────────────────────────────

def test_unauthorized_request_no_db_connection(monkeypatch):
    monkeypatch.setenv("AI2_ENV", "production")
    monkeypatch.delenv("AI2_DEBUG_TOKEN", raising=False)
    monkeypatch.delenv("SUPABASE_DATABASE_URL", raising=False)
    assert client.get(URL).status_code == 404


def test_authorized_request_no_db_connection(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    with patch("database.pool._connect", side_effect=AssertionError("DB must not be opened")) as mock_c:
        resp = client.get(URL)
    assert resp.status_code == 200
    mock_c.assert_not_called()


# ── Response shape unchanged ──────────────────────────────────────────────────

def test_response_shape_unchanged(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    data = client.get(URL).json()
    expected_keys = {
        "session_context_source_of_truth",
        "db_write_through_enabled",
        "db_reads_enabled",
        "curriculum_db_reads_enabled",
        "progress_db_reads_enabled",
        "todos_db_reads_enabled",
        "storage_mode",
        "notes",
    }
    assert expected_keys.issubset(data.keys()), f"Missing keys: {expected_keys - data.keys()}"


def test_session_context_source_of_truth_still_true(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    assert client.get(URL).json()["session_context_source_of_truth"] is True


def test_notes_is_still_a_list(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    assert isinstance(client.get(URL).json()["notes"], list)


# ── Other debug/admin routes still in app.py ─────────────────────────────────

def test_storage_health_still_accessible(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    assert client.get("/debug/storage-health").status_code == 200


def test_admin_beta_metrics_still_accessible(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    assert client.get("/admin/beta-metrics").status_code == 200


def test_other_debug_routes_still_in_app_py():
    app_path = os.path.join(os.path.dirname(__file__), "..", "app.py")
    with open(app_path, encoding="utf-8") as f:
        source = f.read()
    assert "async def debug_storage_health" not in source
    assert "async def admin_beta_metrics" not in source
