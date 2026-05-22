"""
Production auth/config safety tests.

Verifies that core/security_config.py enforces production-mode rules correctly:
- AUTH_SECRET is required in production, optional in dev/test.
- TEST_MODE is blocked in production, allowed in dev/test.
- Cookie Secure flag is True in production, False in dev/test.
- Error messages are safe and contain no secret values.

These tests do not require a real DB or a running server.
All env vars are controlled with monkeypatch.
"""

import pytest

from core.security_config import (
    assert_auth_secret_set,
    assert_test_mode_off,
    get_cookie_secure,
    is_production,
)


# ── is_production ─────────────────────────────────────────────────────────────

class TestIsProduction:
    def test_false_when_env_unset(self, monkeypatch):
        monkeypatch.delenv("AI2_ENV", raising=False)
        assert is_production() is False

    def test_false_when_development(self, monkeypatch):
        monkeypatch.setenv("AI2_ENV", "development")
        assert is_production() is False

    def test_false_when_test(self, monkeypatch):
        monkeypatch.setenv("AI2_ENV", "test")
        assert is_production() is False

    def test_true_when_production(self, monkeypatch):
        monkeypatch.setenv("AI2_ENV", "production")
        assert is_production() is True

    def test_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("AI2_ENV", "PRODUCTION")
        assert is_production() is True


# ── get_cookie_secure ─────────────────────────────────────────────────────────

class TestCookieSecure:
    def test_false_in_dev(self, monkeypatch):
        monkeypatch.delenv("AI2_ENV", raising=False)
        assert get_cookie_secure() is False

    def test_false_when_development(self, monkeypatch):
        monkeypatch.setenv("AI2_ENV", "development")
        assert get_cookie_secure() is False

    def test_true_in_production(self, monkeypatch):
        monkeypatch.setenv("AI2_ENV", "production")
        assert get_cookie_secure() is True


# ── assert_auth_secret_set ────────────────────────────────────────────────────

class TestAssertAuthSecretSet:
    def test_no_error_in_dev_without_secret(self, monkeypatch):
        monkeypatch.delenv("AI2_ENV", raising=False)
        monkeypatch.delenv("AUTH_SECRET", raising=False)
        assert_auth_secret_set()  # must not raise

    def test_no_error_in_dev_with_secret(self, monkeypatch):
        monkeypatch.delenv("AI2_ENV", raising=False)
        monkeypatch.setenv("AUTH_SECRET", "a" * 64)
        assert_auth_secret_set()  # must not raise

    def test_raises_in_production_without_secret(self, monkeypatch):
        monkeypatch.setenv("AI2_ENV", "production")
        monkeypatch.delenv("AUTH_SECRET", raising=False)
        with pytest.raises(RuntimeError) as exc_info:
            assert_auth_secret_set()
        assert "AUTH_SECRET must be set in production." in str(exc_info.value)

    def test_no_error_in_production_with_secret(self, monkeypatch):
        monkeypatch.setenv("AI2_ENV", "production")
        monkeypatch.setenv("AUTH_SECRET", "a" * 64)
        assert_auth_secret_set()  # must not raise

    def test_error_message_is_exact_safe_string(self, monkeypatch):
        monkeypatch.setenv("AI2_ENV", "production")
        monkeypatch.delenv("AUTH_SECRET", raising=False)
        with pytest.raises(RuntimeError) as exc_info:
            assert_auth_secret_set()
        assert str(exc_info.value) == "AUTH_SECRET must be set in production."

    def test_error_message_contains_no_env_introspection(self, monkeypatch):
        monkeypatch.setenv("AI2_ENV", "production")
        monkeypatch.delenv("AUTH_SECRET", raising=False)
        with pytest.raises(RuntimeError) as exc_info:
            assert_auth_secret_set()
        msg = str(exc_info.value)
        assert "os.getenv" not in msg
        assert "os.environ" not in msg


# ── assert_test_mode_off ──────────────────────────────────────────────────────

class TestAssertTestModeOff:
    def test_no_error_in_dev_with_test_mode_on(self, monkeypatch):
        monkeypatch.delenv("AI2_ENV", raising=False)
        monkeypatch.setenv("AI2_TEST_MODE", "1")
        assert_test_mode_off()  # must not raise

    def test_no_error_in_dev_with_test_mode_off(self, monkeypatch):
        monkeypatch.delenv("AI2_ENV", raising=False)
        monkeypatch.setenv("AI2_TEST_MODE", "0")
        assert_test_mode_off()  # must not raise

    def test_raises_in_production_with_test_mode_on(self, monkeypatch):
        monkeypatch.setenv("AI2_ENV", "production")
        monkeypatch.setenv("AI2_TEST_MODE", "1")
        with pytest.raises(RuntimeError) as exc_info:
            assert_test_mode_off()
        assert "TEST_MODE cannot be enabled in production." in str(exc_info.value)

    def test_no_error_in_production_with_test_mode_off(self, monkeypatch):
        monkeypatch.setenv("AI2_ENV", "production")
        monkeypatch.setenv("AI2_TEST_MODE", "0")
        assert_test_mode_off()  # must not raise

    def test_no_error_in_production_without_test_mode_var(self, monkeypatch):
        monkeypatch.setenv("AI2_ENV", "production")
        monkeypatch.delenv("AI2_TEST_MODE", raising=False)
        assert_test_mode_off()  # must not raise

    def test_error_message_is_exact_safe_string(self, monkeypatch):
        monkeypatch.setenv("AI2_ENV", "production")
        monkeypatch.setenv("AI2_TEST_MODE", "1")
        with pytest.raises(RuntimeError) as exc_info:
            assert_test_mode_off()
        assert str(exc_info.value) == "TEST_MODE cannot be enabled in production."

    def test_error_message_contains_no_env_introspection(self, monkeypatch):
        monkeypatch.setenv("AI2_ENV", "production")
        monkeypatch.setenv("AI2_TEST_MODE", "1")
        with pytest.raises(RuntimeError) as exc_info:
            assert_test_mode_off()
        msg = str(exc_info.value)
        assert "os.getenv" not in msg
        assert "os.environ" not in msg


# ── import safety ─────────────────────────────────────────────────────────────

class TestImportSafety:
    def test_import_safe_in_test_environment(self, monkeypatch):
        monkeypatch.delenv("AI2_ENV", raising=False)
        monkeypatch.setenv("AI2_TEST_MODE", "1")
        # In non-production mode, importing and using functions must not raise
        assert is_production() is False
        assert get_cookie_secure() is False
        assert_test_mode_off()   # must not raise
        assert_auth_secret_set() # must not raise (no AUTH_SECRET, but not production)

    def test_both_error_messages_are_safe(self, monkeypatch):
        monkeypatch.setenv("AI2_ENV", "production")
        monkeypatch.delenv("AUTH_SECRET", raising=False)
        monkeypatch.setenv("AI2_TEST_MODE", "1")

        secret_err = None
        test_mode_err = None

        try:
            assert_auth_secret_set()
        except RuntimeError as exc:
            secret_err = str(exc)

        try:
            assert_test_mode_off()
        except RuntimeError as exc:
            test_mode_err = str(exc)

        assert secret_err is not None, "assert_auth_secret_set should have raised"
        assert test_mode_err is not None, "assert_test_mode_off should have raised"

        for msg in (secret_err, test_mode_err):
            assert len(msg) < 200          # no large env dumps
            assert "os.getenv" not in msg
            assert "os.environ" not in msg
