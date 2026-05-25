"""Tests for auth route module split."""

from __future__ import annotations

import os
from pathlib import Path

os.environ["AI2_TEST_MODE"] = "1"
os.environ["ANTHROPIC_API_KEY"] = "test-key"

from fastapi.testclient import TestClient

from auth import AUTH_COOKIE
from app import app


client = TestClient(app)


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def _routes() -> set[tuple[str, str]]:
    return {
        (route.path, ",".join(sorted(getattr(route, "methods", set()) or [])))
        for route in app.routes
        if hasattr(route, "methods")
    }


def test_auth_routes_py_exists_and_defines_router():
    source = _read("routes/auth_routes.py")
    assert "router = APIRouter()" in source
    assert '@router.get("/login", response_class=HTMLResponse)' in source
    assert '@router.post("/login")' in source
    assert '@router.get("/signup", response_class=HTMLResponse)' in source
    assert '@router.post("/signup")' in source
    assert '@router.get("/logout")' in source


def test_app_includes_auth_router():
    source = _read("app.py")
    assert "from routes.auth_routes import router as auth_router" in source
    assert "app.include_router(auth_router)" in source


def test_auth_route_urls_unchanged():
    routes = _routes()
    assert ("/login", "GET") in routes
    assert ("/login", "POST") in routes
    assert ("/signup", "GET") in routes
    assert ("/signup", "POST") in routes
    assert ("/logout", "GET") in routes


def test_login_and_signup_pages_still_load():
    login = client.get("/login", follow_redirects=False)
    signup = client.get("/signup", follow_redirects=False)

    assert login.status_code == 200
    assert "login" in login.text.lower()
    assert signup.status_code == 200
    assert "signup" in signup.text.lower() or "sign up" in signup.text.lower()


def test_login_post_test_mode_sets_same_cookie_and_redirects(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    response = client.post(
        "/login",
        data={"email": "learner@example.com", "password": "password123"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"] == "/dashboard"
    set_cookie = response.headers["set-cookie"]
    assert f"{AUTH_COOKIE}=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie
    assert "Max-Age=2592000" in set_cookie
    assert "Secure" not in set_cookie


def test_login_cookie_secure_flag_still_follows_production_env(monkeypatch):
    monkeypatch.setenv("AI2_ENV", "production")
    response = client.post(
        "/login",
        data={"email": "learner@example.com", "password": "password123"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert "Secure" in response.headers["set-cookie"]


def test_signup_validation_behavior_still_renders_signup_template():
    response = client.post(
        "/signup",
        data={
            "email": "",
            "display_name": "",
            "password": "",
            "confirm_password": "",
        },
        follow_redirects=False,
    )

    assert response.status_code == 422
    assert "Email and password are required." in response.text


def test_logout_route_clears_auth_cookie_and_redirects():
    response = client.get("/logout", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "/login"
    assert f"{AUTH_COOKIE}=" in response.headers["set-cookie"]


def test_app_py_no_longer_defines_auth_route_handlers_directly():
    source = _read("app.py")
    assert '@app.get("/login"' not in source
    assert '@app.post("/login")' not in source
    assert '@app.get("/signup"' not in source
    assert '@app.post("/signup")' not in source
    assert '@app.get("/logout")' not in source


def test_auth_middleware_allowlist_unchanged():
    source = _read("app.py")
    assert '_PUBLIC_PATHS = {"/login", "/signup", "/health", "/privacy", "/terms"}' in source
    assert "auth_middleware" in source
    assert "path in _PUBLIC_PATHS" in source


def test_non_auth_routes_not_moved_into_auth_routes():
    app_source = _read("app.py")
    auth_source = _read("routes/auth_routes.py")

    assert '@app.get("/debug/storage-status")' in app_source
    assert "from routes.dashboard import router as dashboard_router" in app_source
    assert "from routes.onboarding import router as onboarding_router" in app_source
    assert '@app.get("/chat/{session_id}"' in app_source
    assert "from routes.syllabus import router as syllabus_router" in app_source
    assert '@app.get("/jobs"' in app_source

    assert '"/debug/' not in auth_source
    assert '@router.get("/dashboard"' not in auth_source
    assert '"/onboarding/' not in auth_source
    assert '"/chat/{session_id}"' not in auth_source
    assert '"/syllabus/{session_id}"' not in auth_source
    assert '"/jobs"' not in auth_source
