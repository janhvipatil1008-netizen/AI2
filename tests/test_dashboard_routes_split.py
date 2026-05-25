"""Tests for the dashboard route module split."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

os.environ["AI2_TEST_MODE"] = "1"
os.environ["ANTHROPIC_API_KEY"] = "test-key"

from fastapi.testclient import TestClient

import app as app_module
import routes.dashboard as dashboard_module
from config import CareerTrack
from context.session import SessionContext


client = TestClient(app_module.app)


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def _put_session(
    *,
    session_id: str = "dashboard-routes-split-session",
    user_id: str = "user-dashboard-routes",
    current_week: int = 2,
) -> SessionContext:
    app_module._sessions.clear()
    session = SessionContext(
        track=CareerTrack.AI_PM,
        user_id=user_id,
        current_week=current_week,
    )
    app_module._sessions[session_id] = {
        "session": session,
        "orch": None,
        "client": None,
        "profile": None,
    }
    return session


def _enrollment_summary() -> dict:
    return {
        "source": "db",
        "course_key": "aipm-foundations",
        "status": "active",
        "progress_percent": 42,
        "current_module_key": "module-02",
        "current_topic_key": "topic-03",
        "current_legacy_topic_id": "aipm-week-2-topic-03",
        "error": None,
    }


def _modular_progress_summary() -> dict:
    return {
        "source": "db",
        "available": True,
        "course_key": "aipm-foundations",
        "progress_percent": 42,
        "current_module_key": "module-02",
        "current_topic_key": "topic-03",
        "current_legacy_topic_id": "aipm-week-2-topic-03",
        "modules": [
            {
                "module_key": "module-02",
                "status": "in_progress",
                "completed_topics": 1,
                "total_topics": 3,
                "progress_percent": 42,
            }
        ],
        "topics": [
            {
                "module_key": "module-02",
                "topic_key": "topic-03",
                "legacy_topic_id": "aipm-week-2-topic-03",
                "status": "in_progress",
                "completion_percent": 42,
                "required_activities_completed": 2,
                "required_activities_total": 5,
            }
        ],
        "error": None,
    }


def test_dashboard_py_exists_and_defines_router():
    source = _read("routes/dashboard.py")
    assert "router = APIRouter()" in source
    assert '@router.get("/dashboard", response_class=HTMLResponse)' in source


def test_app_includes_dashboard_router():
    source = _read("app.py")
    assert "from routes.dashboard import router as dashboard_router" in source
    assert "app.include_router(dashboard_router)" in source


def test_dashboard_route_url_unchanged():
    routes = {
        (route.path, ",".join(sorted(getattr(route, "methods", set()) or [])))
        for route in app_module.app.routes
        if hasattr(route, "methods")
    }
    assert ("/dashboard", "GET") in routes


def test_dashboard_still_renders():
    _put_session()
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "Your adaptive learning dashboard" in response.text


def test_dashboard_context_summary_behavior_is_preserved():
    _put_session()
    with patch.object(
        dashboard_module,
        "_dashboard_db_summaries",
        return_value=(_enrollment_summary(), _modular_progress_summary()),
    ):
        response = client.get("/dashboard")

    assert response.status_code == 200
    assert "Learning path" in response.text
    assert "Learning progress" in response.text
    assert "Current Focus" in response.text
    assert "aipm-foundations" in response.text
    assert "topic-03" in response.text


def test_dashboard_source_keeps_context_summary_keys():
    source = _read("routes/dashboard.py")
    assert '"enrollment_summary": enrollment_summary' in source
    assert '"modular_progress_summary": modular_progress_summary' in source
    assert '"position_summary": position_summary' in source


def test_dashboard_db_failure_fallback_behavior_is_preserved():
    _put_session(current_week=4)
    with patch.object(
        dashboard_module,
        "_open_db_connection",
        side_effect=RuntimeError("postgres://user:secret@localhost/db"),
    ):
        response = client.get("/dashboard")

    assert response.status_code == 200
    assert "Your adaptive learning dashboard" in response.text
    assert "Module 4" in response.text
    assert "postgres://" not in response.text
    assert "secret" not in response.text


def test_app_no_longer_defines_dashboard_route_directly():
    assert '@app.get("/dashboard"' not in _read("app.py")


def test_non_dashboard_routes_not_moved_in_this_slice():
    app_source = _read("app.py")
    dashboard_source = _read("routes/dashboard.py")

    assert '@app.get("/chat/{session_id}"' in app_source
    assert "from routes.syllabus import router as syllabus_router" in app_source
    assert '@app.get("/debug/storage-status")' in app_source
    assert "from routes.onboarding import router as onboarding_router" in app_source

    assert '"/chat/{session_id}"' not in dashboard_source
    assert '"/syllabus/{session_id}"' not in dashboard_source
    assert '"/debug/' not in dashboard_source
    assert '"/onboarding/' not in dashboard_source
