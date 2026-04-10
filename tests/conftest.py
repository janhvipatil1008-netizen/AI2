"""
AI² Test Suite — Shared fixtures and server lifecycle.

All tests run against the FastAPI app in TEST_MODE (AI2_TEST_MODE=1),
which returns mock responses so no real Claude API calls are made.
The server starts once per session on port 8765 and is torn down after all tests.
"""

import os
import sys
import time
import subprocess
import requests
import pytest

# ── Ensure the project root is on sys.path ────────────────────────────────────
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

_PORT     = os.getenv("AI2_TEST_PORT", "8765")
BASE_URL  = f"http://localhost:{_PORT}"
SERVER_TIMEOUT = 60   # seconds to wait for server to become healthy


# ── Server lifecycle ──────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def live_server():
    """
    Start the FastAPI server in TEST_MODE before the test session,
    yield the base URL, then kill it after all tests complete.
    """
    env = {**os.environ, "AI2_TEST_MODE": "1", "ANTHROPIC_API_KEY": "test-key"}
    proc = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn",
            "app:app",
            "--host", "127.0.0.1",
            "--port", _PORT,
            "--log-level", "warning",
        ],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait until /health responds
    deadline = time.time() + SERVER_TIMEOUT
    last_exc = None
    while time.time() < deadline:
        try:
            r = requests.get(f"{BASE_URL}/health", timeout=3)
            if r.status_code == 200:
                break
        except requests.exceptions.ConnectionError:
            # Server not yet listening — normal during startup
            pass
        except Exception as exc:
            last_exc = exc
        time.sleep(0.5)
    else:
        proc.terminate()
        stderr_out = proc.stderr.read(2000).decode(errors="replace") if proc.stderr else ""
        raise RuntimeError(
            f"Server failed to start within {SERVER_TIMEOUT}s. "
            f"Last error: {last_exc}\nServer stderr: {stderr_out}"
        )

    yield BASE_URL

    proc.terminate()
    proc.wait(timeout=5)


# ── HTTP helpers ──────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def api(live_server):
    """Return a simple callable that wraps requests against the live server."""

    class API:
        base = live_server

        def get(self, path, **kw):
            return requests.get(f"{self.base}{path}", timeout=15, **kw)

        def post(self, path, **kw):
            return requests.post(f"{self.base}{path}", timeout=15, **kw)

    return API()


@pytest.fixture
def session_aipm(api):
    """Start an AIPM track session and return {session_id, progress}."""
    r = api.post("/session/start", json={"track": "aipm", "week": 5})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture
def session_evals(api):
    """Start an Evals track session at week 8."""
    r = api.post("/session/start", json={"track": "evals", "week": 8})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture
def session_context(api):
    """Start a Context Engineer track session at week 6."""
    r = api.post("/session/start", json={"track": "context", "week": 6})
    assert r.status_code == 200, r.text
    return r.json()


# ── Playwright browser fixture ────────────────────────────────────────────────

@pytest.fixture(scope="session")
def browser_context(live_server):
    """
    Playwright browser context for UI tests.
    Uses the sync API so tests don't need async.
    Yields a playwright Page object pointed at the live server.
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx     = browser.new_context(base_url=live_server)
        page    = ctx.new_page()
        yield page
        ctx.close()
        browser.close()


@pytest.fixture
def page(browser_context):
    """Per-test alias for the shared Playwright page (navigates to / before each test)."""
    browser_context.goto("/")
    return browser_context
