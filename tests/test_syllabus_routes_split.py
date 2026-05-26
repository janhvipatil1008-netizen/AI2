"""Tests for syllabus route module split."""

from __future__ import annotations

import os
from pathlib import Path

os.environ["AI2_TEST_MODE"] = "1"
os.environ["ANTHROPIC_API_KEY"] = "test-key"

from fastapi.testclient import TestClient

import app as app_module
from curriculum.syllabus import WEEKS, get_task_key


client = TestClient(app_module.app)


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def _routes() -> set[tuple[str, str]]:
    return {
        (route.path, ",".join(sorted(getattr(route, "methods", set()) or [])))
        for route in app_module.app.routes
        if hasattr(route, "methods")
    }


def _start_session(track: str = "aipm", week: int = 1) -> str:
    response = client.post("/session/start", json={"track": track, "week": week})
    assert response.status_code == 200, response.text
    return response.json()["session_id"]


def _first_task_key() -> str:
    week = WEEKS[0]
    return get_task_key(week["num"], week["days"][0]["day_idx"], "all", 0)


def test_syllabus_py_exists_and_defines_router():
    source = _read("routes/syllabus.py")
    assert "router = APIRouter()" in source
    assert '@router.get("/syllabus/{session_id}", response_class=HTMLResponse)' in source
    assert '@router.post("/task/toggle")' in source


def test_app_includes_syllabus_router():
    source = _read("app.py")
    assert "from routes.syllabus import router as syllabus_router" in source
    assert "app.include_router(syllabus_router)" in source


def test_syllabus_route_urls_unchanged():
    routes = _routes()
    assert ("/syllabus/{session_id}", "GET") in routes
    assert ("/task/toggle", "POST") in routes


def test_syllabus_page_still_loads():
    session_id = _start_session()
    response = client.get(f"/syllabus/{session_id}")

    assert response.status_code == 200
    assert "Browse Module Topics" in response.text
    assert "My Planner" in response.text


def test_task_toggle_behavior_is_preserved():
    session_id = _start_session()
    task_key = _first_task_key()

    response = client.post(
        "/task/toggle",
        json={"session_id": session_id, "task_key": task_key, "status": "done"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["task_key"] == task_key
    assert data["status"] == "done"
    assert data["tasks_done"] == 1
    assert data["overall"]["done"] >= 1


def test_task_toggle_invalid_status_still_returns_422():
    session_id = _start_session()
    response = client.post(
        "/task/toggle",
        json={"session_id": session_id, "task_key": _first_task_key(), "status": "bad"},
    )

    assert response.status_code == 422
    assert "status must be one of" in response.text


def test_track_specific_syllabus_context_is_preserved():
    session_id = _start_session(track="evals")
    response = client.get(f"/syllabus/{session_id}")

    assert response.status_code == 200
    assert "AI Evals Specialist" in response.text


def test_app_no_longer_defines_syllabus_route_handlers_directly():
    source = _read("app.py")
    assert '@app.get("/syllabus/{session_id}"' not in source
    assert '@app.post("/task/toggle")' not in source
    assert "class TaskToggleRequest" not in source


def test_non_syllabus_routes_not_moved_in_this_step():
    app_source = _read("app.py")
    syllabus_source = _read("routes/syllabus.py")

    assert "from routes.auth_routes import router as auth_router" in app_source
    assert "from routes.public import router as public_router" in app_source
    assert "from routes.dashboard import router as dashboard_router" in app_source
    assert "from routes.onboarding import router as onboarding_router" in app_source
    assert '@app.get("/debug/storage-status")' in app_source
    assert '@app.post("/chat")' in app_source
    assert "from routes.jobs import router as jobs_router" in app_source

    assert '"/login"' not in syllabus_source
    assert '"/dashboard"' not in syllabus_source
    assert '"/onboarding/' not in syllabus_source
    assert '"/debug/' not in syllabus_source
    assert '"/chat"' not in syllabus_source
    assert '"/jobs"' not in syllabus_source
