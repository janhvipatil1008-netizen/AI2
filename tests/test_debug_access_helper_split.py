"""
Verify that _debug_access has been moved from app.py into routes/deps.py
and that all debug/admin routes remain protected with identical behavior.

Does not start a real DB.  Relies on AI2_TEST_MODE=1 so module-level
assert_test_mode_off() in app.py is satisfied.
"""

from __future__ import annotations

import os

os.environ["AI2_TEST_MODE"] = "1"
os.environ["ANTHROPIC_API_KEY"] = "test-key"

import inspect

from fastapi.testclient import TestClient

import app as _app_module
import routes.deps as _deps
from app import app

client = TestClient(app)

_TOKEN = "split-test-debug-token-xyz"


# ── Structure checks ──────────────────────────────────────────────────────────

def test_routes_deps_exposes_debug_access():
    assert callable(getattr(_deps, "debug_access", None)), (
        "routes.deps must expose a callable named debug_access"
    )


def test_app_no_longer_defines_debug_access():
    app_path = os.path.join(os.path.dirname(__file__), "..", "app.py")
    with open(app_path, encoding="utf-8") as f:
        source = f.read()
    assert "def _debug_access" not in source, (
        "app.py still contains a def _debug_access; it should import from routes.deps instead"
    )


def test_app_debug_access_binding_is_routes_deps_function():
    """The _debug_access name in app.py must point to routes.deps.debug_access."""
    binding = getattr(_app_module, "_debug_access", None)
    assert binding is _deps.debug_access, (
        "app._debug_access must be the same object as routes.deps.debug_access"
    )


# ── Production 404 without token ─────────────────────────────────────────────

def test_production_missing_token_returns_404_storage_health(monkeypatch):
    monkeypatch.setenv("AI2_ENV", "production")
    monkeypatch.delenv("AI2_DEBUG_TOKEN", raising=False)
    assert client.get("/debug/storage-health").status_code == 404


def test_production_missing_token_returns_404_storage_status(monkeypatch):
    monkeypatch.setenv("AI2_ENV", "production")
    monkeypatch.delenv("AI2_DEBUG_TOKEN", raising=False)
    assert client.get("/debug/storage-status").status_code == 404


def test_production_missing_token_returns_404_admin_beta_metrics(monkeypatch):
    monkeypatch.setenv("AI2_ENV", "production")
    monkeypatch.delenv("AI2_DEBUG_TOKEN", raising=False)
    assert client.get("/admin/beta-metrics").status_code == 404


# ── Production 404 with wrong token ──────────────────────────────────────────

def test_production_wrong_token_returns_404(monkeypatch):
    monkeypatch.setenv("AI2_ENV", "production")
    monkeypatch.setenv("AI2_DEBUG_TOKEN", _TOKEN)
    resp = client.get("/debug/storage-status", headers={"X-AI2-Debug-Token": "wrong"})
    assert resp.status_code == 404


def test_production_wrong_token_admin_returns_404(monkeypatch):
    monkeypatch.setenv("AI2_ENV", "production")
    monkeypatch.setenv("AI2_DEBUG_TOKEN", _TOKEN)
    resp = client.get("/admin/beta-metrics", headers={"X-AI2-Debug-Token": "wrong"})
    assert resp.status_code == 404


# ── Production correct token passes ──────────────────────────────────────────

def test_production_correct_token_allows_storage_status(monkeypatch):
    monkeypatch.setenv("AI2_ENV", "production")
    monkeypatch.setenv("AI2_DEBUG_TOKEN", _TOKEN)
    resp = client.get("/debug/storage-status", headers={"X-AI2-Debug-Token": _TOKEN})
    assert resp.status_code == 200


def test_production_correct_token_allows_storage_health(monkeypatch):
    monkeypatch.setenv("AI2_ENV", "production")
    monkeypatch.setenv("AI2_DEBUG_TOKEN", _TOKEN)
    resp = client.get("/debug/storage-health", headers={"X-AI2-Debug-Token": _TOKEN})
    assert resp.status_code == 200


# ── Unauthorized request does not open DB connection ─────────────────────────

def test_unauthorized_debug_request_no_db_connection(monkeypatch):
    """Blocking an unauthorized request must not attempt any DB connection."""
    monkeypatch.setenv("AI2_ENV", "production")
    monkeypatch.delenv("AI2_DEBUG_TOKEN", raising=False)
    monkeypatch.delenv("SUPABASE_DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    resp = client.get("/debug/storage-health")
    assert resp.status_code == 404


# ── /admin/beta-metrics remains protected ────────────────────────────────────

def test_admin_beta_metrics_protected_in_production(monkeypatch):
    monkeypatch.setenv("AI2_ENV", "production")
    monkeypatch.delenv("AI2_DEBUG_TOKEN", raising=False)
    resp = client.get("/admin/beta-metrics")
    assert resp.status_code == 404


def test_admin_beta_metrics_accessible_in_dev(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    resp = client.get("/admin/beta-metrics")
    assert resp.status_code == 200


# ── Route URLs unchanged ──────────────────────────────────────────────────────

def test_debug_route_urls_unchanged(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    urls = [
        "/debug/storage-status",
        "/debug/storage-health",
        "/debug/storage-health-view",
        "/debug/curriculum-db-check",
        "/debug/curriculum-fallback-check",
        "/debug/modular-curriculum",
    ]
    for url in urls:
        resp = client.get(url)
        assert resp.status_code == 200, f"Expected 200 for {url}, got {resp.status_code}"


def test_admin_route_url_unchanged(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    resp = client.get("/admin/beta-metrics")
    assert resp.status_code == 200
