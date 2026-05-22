"""
Tests for /debug/* endpoint production protection.

Verifies that:
- In non-production mode, debug endpoints are accessible without a token.
- In production mode with no AI2_DEBUG_TOKEN, debug endpoints return 404.
- In production mode with a wrong token, debug endpoints return 404.
- In production mode with the correct token, debug endpoints are accessible.
- Token values are never reflected in response bodies.
- Learner-facing routes are not affected by the debug protection.
- No DB connection is opened by the protection check itself.

These tests do not require a real DB.
app is imported with AI2_TEST_MODE=1, so the module-level assert_test_mode_off()
passes (AI2_ENV is not set to production at import time).
Per-test monkeypatching of AI2_ENV to "production" exercises the per-request
is_debug_access_allowed() check without re-triggering the startup assertion.
"""

from __future__ import annotations

import os

os.environ["AI2_TEST_MODE"] = "1"
os.environ["ANTHROPIC_API_KEY"] = "test-key"

from fastapi.testclient import TestClient

from app import app

client = TestClient(app)

_TOKEN = "test-debug-token-abc123"

# ── /debug/storage-health ─────────────────────────────────────────────────────

class TestStorageHealthProtection:
    def test_accessible_in_dev_without_token(self, monkeypatch):
        monkeypatch.delenv("AI2_ENV", raising=False)
        resp = client.get("/debug/storage-health")
        assert resp.status_code == 200

    def test_blocked_in_production_no_token_configured(self, monkeypatch):
        monkeypatch.setenv("AI2_ENV", "production")
        monkeypatch.delenv("AI2_DEBUG_TOKEN", raising=False)
        resp = client.get("/debug/storage-health")
        assert resp.status_code == 404

    def test_blocked_in_production_no_header(self, monkeypatch):
        monkeypatch.setenv("AI2_ENV", "production")
        monkeypatch.setenv("AI2_DEBUG_TOKEN", _TOKEN)
        resp = client.get("/debug/storage-health")
        assert resp.status_code == 404

    def test_blocked_in_production_wrong_token(self, monkeypatch):
        monkeypatch.setenv("AI2_ENV", "production")
        monkeypatch.setenv("AI2_DEBUG_TOKEN", _TOKEN)
        resp = client.get("/debug/storage-health", headers={"X-AI2-Debug-Token": "wrong-token"})
        assert resp.status_code == 404

    def test_allowed_in_production_correct_token(self, monkeypatch):
        monkeypatch.setenv("AI2_ENV", "production")
        monkeypatch.setenv("AI2_DEBUG_TOKEN", _TOKEN)
        resp = client.get("/debug/storage-health", headers={"X-AI2-Debug-Token": _TOKEN})
        assert resp.status_code == 200

    def test_token_not_in_response_body_on_block(self, monkeypatch):
        monkeypatch.setenv("AI2_ENV", "production")
        monkeypatch.setenv("AI2_DEBUG_TOKEN", _TOKEN)
        resp = client.get("/debug/storage-health", headers={"X-AI2-Debug-Token": "wrong"})
        assert resp.status_code == 404
        body = resp.text
        assert _TOKEN not in body
        assert "AI2_DEBUG_TOKEN" not in body

    def test_token_not_in_response_body_on_allow(self, monkeypatch):
        monkeypatch.setenv("AI2_ENV", "production")
        monkeypatch.setenv("AI2_DEBUG_TOKEN", _TOKEN)
        resp = client.get("/debug/storage-health", headers={"X-AI2-Debug-Token": _TOKEN})
        assert resp.status_code == 200
        body = resp.text
        assert _TOKEN not in body
        assert "AI2_DEBUG_TOKEN" not in body


# ── /debug/storage-status ─────────────────────────────────────────────────────

class TestStorageStatusProtection:
    def test_accessible_in_dev_without_token(self, monkeypatch):
        monkeypatch.delenv("AI2_ENV", raising=False)
        resp = client.get("/debug/storage-status")
        assert resp.status_code == 200

    def test_blocked_in_production_no_token(self, monkeypatch):
        monkeypatch.setenv("AI2_ENV", "production")
        monkeypatch.delenv("AI2_DEBUG_TOKEN", raising=False)
        resp = client.get("/debug/storage-status")
        assert resp.status_code == 404

    def test_allowed_in_production_correct_token(self, monkeypatch):
        monkeypatch.setenv("AI2_ENV", "production")
        monkeypatch.setenv("AI2_DEBUG_TOKEN", _TOKEN)
        resp = client.get("/debug/storage-status", headers={"X-AI2-Debug-Token": _TOKEN})
        assert resp.status_code == 200


# ── /debug/storage-health-view ────────────────────────────────────────────────

class TestStorageHealthViewProtection:
    def test_accessible_in_dev_without_token(self, monkeypatch):
        monkeypatch.delenv("AI2_ENV", raising=False)
        resp = client.get("/debug/storage-health-view")
        assert resp.status_code == 200

    def test_blocked_in_production_no_token(self, monkeypatch):
        monkeypatch.setenv("AI2_ENV", "production")
        monkeypatch.delenv("AI2_DEBUG_TOKEN", raising=False)
        resp = client.get("/debug/storage-health-view")
        assert resp.status_code == 404

    def test_allowed_in_production_correct_token(self, monkeypatch):
        monkeypatch.setenv("AI2_ENV", "production")
        monkeypatch.setenv("AI2_DEBUG_TOKEN", _TOKEN)
        resp = client.get("/debug/storage-health-view", headers={"X-AI2-Debug-Token": _TOKEN})
        assert resp.status_code == 200


# ── /debug/usage-events-mismatch-check ───────────────────────────────────────

class TestUsageEventsMismatchProtection:
    def test_accessible_in_dev_without_token(self, monkeypatch):
        monkeypatch.delenv("AI2_ENV", raising=False)
        # Endpoint requires session_id; use a dummy value — no DB in TEST_MODE
        resp = client.get("/debug/usage-events-mismatch-check?session_id=test-session")
        assert resp.status_code in (200, 422, 404)  # any non-auth error is fine
        # Must not be a 404 caused by the debug protection (no AI2_ENV=production)
        if resp.status_code == 404:
            assert "Not found" not in resp.text or "session" in resp.text.lower()

    def test_blocked_in_production_no_token(self, monkeypatch):
        monkeypatch.setenv("AI2_ENV", "production")
        monkeypatch.delenv("AI2_DEBUG_TOKEN", raising=False)
        resp = client.get("/debug/usage-events-mismatch-check?session_id=test-session")
        assert resp.status_code == 404

    def test_allowed_in_production_correct_token(self, monkeypatch):
        monkeypatch.setenv("AI2_ENV", "production")
        monkeypatch.setenv("AI2_DEBUG_TOKEN", _TOKEN)
        resp = client.get(
            "/debug/usage-events-mismatch-check?session_id=test-session",
            headers={"X-AI2-Debug-Token": _TOKEN},
        )
        # Protection passed. The endpoint itself may return 404 (session not found)
        # but that detail will differ from the generic gate message "Not found."
        if resp.status_code == 404:
            detail = resp.json().get("detail", "")
            assert detail != "Not found.", (
                "Got the debug protection gate's 404, not the endpoint's own 404. "
                "Token was correct — protection should have passed."
            )


# ── Learner-facing routes are unaffected ─────────────────────────────────────

class TestLearnerRoutesUnaffected:
    def test_health_not_protected(self, monkeypatch):
        monkeypatch.setenv("AI2_ENV", "production")
        monkeypatch.delenv("AI2_DEBUG_TOKEN", raising=False)
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_no_token_required(self, monkeypatch):
        monkeypatch.setenv("AI2_ENV", "production")
        resp = client.get("/health")
        # /health is not a debug endpoint and must never require a debug token
        assert resp.status_code == 200

    def test_login_page_not_protected(self, monkeypatch):
        monkeypatch.setenv("AI2_ENV", "production")
        monkeypatch.delenv("AI2_DEBUG_TOKEN", raising=False)
        resp = client.get("/login", follow_redirects=False)
        # In TEST_MODE, /login redirects to dashboard or serves the page
        assert resp.status_code in (200, 302)
        # Must not be blocked by the debug gate
        assert resp.status_code != 404


# ── No debug route URL changed ────────────────────────────────────────────────

class TestRouteUrlsUnchanged:
    def test_storage_health_url_unchanged(self, monkeypatch):
        monkeypatch.delenv("AI2_ENV", raising=False)
        resp = client.get("/debug/storage-health")
        assert resp.status_code == 200

    def test_storage_status_url_unchanged(self, monkeypatch):
        monkeypatch.delenv("AI2_ENV", raising=False)
        resp = client.get("/debug/storage-status")
        assert resp.status_code == 200

    def test_storage_health_view_url_unchanged(self, monkeypatch):
        monkeypatch.delenv("AI2_ENV", raising=False)
        resp = client.get("/debug/storage-health-view")
        assert resp.status_code == 200


# ── Protection does not open DB on its own ────────────────────────────────────

class TestDebugProtectionNoDB:
    def test_production_block_requires_no_db(self, monkeypatch):
        """Blocking an unauthorized request must not attempt a DB connection."""
        monkeypatch.setenv("AI2_ENV", "production")
        monkeypatch.delenv("AI2_DEBUG_TOKEN", raising=False)
        monkeypatch.delenv("SUPABASE_DATABASE_URL", raising=False)
        # Should return 404 without trying to connect to any DB
        resp = client.get("/debug/storage-health")
        assert resp.status_code == 404
