"""
AI² production safety configuration.

Reads environment variables at call time (not at import) so tests can
monkeypatch env vars without module reloading.

Production mode is enabled when AI2_ENV=production.
"""

import hmac
import os


def is_production() -> bool:
    """Return True when AI2_ENV is set to 'production' (case-insensitive)."""
    return os.getenv("AI2_ENV", "").lower() == "production"


def get_cookie_secure() -> bool:
    """Return True in production so auth cookies use the Secure flag."""
    return is_production()


def assert_auth_secret_set() -> None:
    """Raise RuntimeError if AUTH_SECRET is missing in production mode."""
    if is_production() and not os.getenv("AUTH_SECRET", ""):
        raise RuntimeError("AUTH_SECRET must be set in production.")


def assert_test_mode_off() -> None:
    """Raise RuntimeError if TEST_MODE is enabled in production mode."""
    if is_production() and os.getenv("AI2_TEST_MODE", "") == "1":
        raise RuntimeError("TEST_MODE cannot be enabled in production.")


def is_debug_access_allowed(request) -> bool:
    """Return True if the request is permitted to reach a debug endpoint.

    In non-production mode, always returns True (no token required).
    In production, requires the X-AI2-Debug-Token header to match the
    AI2_DEBUG_TOKEN env var.  Uses constant-time comparison to avoid
    timing side-channels.  Returns False silently when the token is not
    configured — no hint that a token exists is exposed to callers.
    """
    if not is_production():
        return True
    expected = os.getenv("AI2_DEBUG_TOKEN", "")
    if not expected:
        return False
    provided = request.headers.get("X-AI2-Debug-Token", "")
    if not provided:
        return False
    return hmac.compare_digest(
        expected.encode("utf-8"),
        provided.encode("utf-8"),
    )
