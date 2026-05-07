"""
Session ownership tests.

These require a real (non-TEST_MODE) server so that auth middleware
and the SQL-level ownership check in _get_session_data are exercised.
A second server is started on port 8766 with a temp SQLite DB and a
known AUTH_SECRET; the existing port-8765 test suite is unaffected.
"""

import os
import sys
import time
import tempfile
import subprocess

import requests
import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

_AUTH_PORT   = "8766"
_AUTH_BASE   = f"http://localhost:{_AUTH_PORT}"
_AUTH_SECRET = "a" * 64


# ── Server fixture ────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def auth_server():
    """
    Start a non-TEST_MODE server on port 8766 with a temp DB.
    Yields the base URL; tears down after all tests in this module complete.
    """
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)

    env = {
        **os.environ,
        "AI2_TEST_MODE":     "0",
        "ANTHROPIC_API_KEY": "test-key",
        "AUTH_SECRET":       _AUTH_SECRET,
        "AI2_SESSION_DB":    db_path,
    }
    proc = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn", "app:app",
            "--host", "127.0.0.1",
            "--port", _AUTH_PORT,
            "--log-level", "warning",
        ],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    deadline = time.time() + 60
    while time.time() < deadline:
        try:
            if requests.get(f"{_AUTH_BASE}/health", timeout=3).status_code == 200:
                break
        except requests.exceptions.ConnectionError:
            pass
        time.sleep(0.5)
    else:
        proc.terminate()
        stderr_out = proc.stderr.read(2000).decode(errors="replace") if proc.stderr else ""
        raise RuntimeError(f"Auth server failed to start.\nstderr: {stderr_out}")

    yield _AUTH_BASE

    proc.terminate()
    proc.wait(timeout=5)
    try:
        os.unlink(db_path)
    except OSError:
        pass


# ── Helpers ───────────────────────────────────────────────────────────────────

def _signup_and_get_cookie(base_url: str, email: str, password: str) -> str:
    """Sign up a new user and return the raw ai2_user_token cookie value."""
    r = requests.post(
        f"{base_url}/signup",
        data={
            "email":            email,
            "display_name":     email.split("@")[0],
            "password":         password,
            "confirm_password": password,
        },
        allow_redirects=False,
    )
    assert r.status_code == 302, f"Signup failed: {r.status_code} — {r.text[:200]}"
    val = r.cookies.get("ai2_user_token")
    assert val, "No ai2_user_token cookie in signup response"
    return val


def _start_session(base_url: str, cookie: str) -> str:
    """Start an AIPM session authenticated as the given cookie owner."""
    r = requests.post(
        f"{base_url}/session/start",
        json={"track": "aipm", "week": 1},
        cookies={"ai2_user_token": cookie},
    )
    assert r.status_code == 200, f"session/start failed: {r.status_code} — {r.text[:200]}"
    return r.json()["session_id"]


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_session_ownership_enforced(auth_server):
    """User B must get HTTP 403 when accessing a session owned by user A."""
    cookie_a   = _signup_and_get_cookie(auth_server, "usera@ownership.test", "password123")
    cookie_b   = _signup_and_get_cookie(auth_server, "userb@ownership.test", "password123")
    session_id = _start_session(auth_server, cookie_a)

    r = requests.get(
        f"{auth_server}/chat/{session_id}",
        cookies={"ai2_user_token": cookie_b},
        allow_redirects=False,
    )
    assert r.status_code == 403, (
        f"Expected 403 (access denied), got {r.status_code}. "
        f"User B should not access user A's session."
    )


def test_own_session_accessible(auth_server):
    """User A must get HTTP 200 when accessing their own session."""
    cookie_a   = _signup_and_get_cookie(auth_server, "usera2@ownership.test", "password123")
    session_id = _start_session(auth_server, cookie_a)

    r = requests.get(
        f"{auth_server}/chat/{session_id}",
        cookies={"ai2_user_token": cookie_a},
        allow_redirects=False,
    )
    assert r.status_code == 200, (
        f"Expected 200 (owner access), got {r.status_code}. "
        f"User A should access their own session."
    )
