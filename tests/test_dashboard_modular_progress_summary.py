"""Tests for dashboard modular progress summary fallback behavior."""

from __future__ import annotations

import os
from copy import deepcopy
from unittest.mock import patch

os.environ["AI2_TEST_MODE"] = "1"
os.environ["ANTHROPIC_API_KEY"] = "test-key"

from fastapi.testclient import TestClient

import app as app_module
from config import CareerTrack
from context.session import SessionContext
from curriculum.syllabus import ROLE_TRACKS, WEEKS
from services import dashboard_modular_progress_service as progress_service


client = TestClient(app_module.app)


class FakeReadConn:
    def __init__(self):
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def _put_session(
    *,
    session_id: str = "dashboard-modular-progress",
    user_id: str = "user-1",
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


def _enrollment_result() -> dict:
    return {
        "source": "db",
        "enrollment": {
            "enrollment_id": 7,
            "course_key": "aipm-foundations",
            "status": "active",
            "progress_percent": 64,
            "current_module_key": "module-02",
            "current_topic_key": "topic-03",
            "current_legacy_topic_id": "aipm-week-2-topic-03",
            "metadata": {"private": "do-not-render"},
        },
        "error": None,
    }


def _modular_summary(**overrides) -> dict:
    summary = {
        "source": "db",
        "available": True,
        "course_key": "aipm-foundations",
        "progress_percent": 64,
        "current_module_key": "module-02",
        "current_topic_key": "topic-03",
        "current_legacy_topic_id": "aipm-week-2-topic-03",
        "modules": [
            {
                "module_key": "module-01",
                "status": "completed",
                "completed_topics": 3,
                "total_topics": 3,
                "progress_percent": 100,
            },
            {
                "module_key": "module-02",
                "status": "in_progress",
                "completed_topics": 1,
                "total_topics": 3,
                "progress_percent": 33,
            },
        ],
        "topics": [
            {
                "module_key": "module-02",
                "topic_key": "topic-03",
                "legacy_topic_id": "aipm-week-2-topic-03",
                "status": "in_progress",
                "completion_percent": 40,
                "required_activities_completed": 2,
                "required_activities_total": 5,
            }
        ],
        "error": None,
    }
    summary.update(overrides)
    return summary


def test_dashboard_renders_with_modular_progress_available():
    session_id = "dashboard-modular-db"
    _put_session(session_id=session_id)
    conn = FakeReadConn()

    with patch.object(app_module, "_open_db_connection", return_value=conn):
        with patch.object(
            app_module,
            "get_active_course_enrollment_with_fallback",
            return_value=_enrollment_result(),
        ):
            with patch.object(
                app_module,
                "build_dashboard_modular_progress_summary",
                return_value=_modular_summary(),
            ) as build_summary:
                response = client.get("/dashboard")

    assert response.status_code == 200
    assert "Learning progress" in response.text
    assert "aipm-foundations" in response.text
    assert "64%" in response.text
    assert "module-02" in response.text
    assert "topic-03" in response.text
    build_summary.assert_called_once_with(
        conn,
        user_id="user-1",
        session_id=session_id,
        track_key="aipm",
    )
    assert conn.closed is True


def test_dashboard_renders_with_no_modular_progress():
    _put_session(session_id="dashboard-modular-missing")
    conn = FakeReadConn()

    with patch.object(app_module, "_open_db_connection", return_value=conn):
        with patch.object(
            app_module,
            "get_active_course_enrollment_with_fallback",
            return_value={
                "source": "fallback",
                "enrollment": {"course_key": "aipm-foundations"},
                "error": None,
            },
        ):
            with patch.object(
                app_module,
                "build_dashboard_modular_progress_summary",
                return_value={
                    "source": "fallback",
                    "available": False,
                    "progress_percent": 0,
                    "modules": [],
                    "topics": [],
                    "error": None,
                },
            ):
                response = client.get("/dashboard")

    assert response.status_code == 200
    assert "Your adaptive learning dashboard" in response.text
    assert "Your Learning Summary" in response.text
    assert "Learning progress" not in response.text


def test_dashboard_renders_when_db_fails():
    _put_session(session_id="dashboard-modular-db-fails")

    with patch.object(
        app_module,
        "_open_db_connection",
        side_effect=RuntimeError("postgres://user:secret@localhost/db"),
    ):
        response = client.get("/dashboard")

    assert response.status_code == 200
    assert "Your adaptive learning dashboard" in response.text
    assert "Your Learning Summary" in response.text


def test_no_learner_facing_db_error_is_shown():
    _put_session(session_id="dashboard-modular-error-hidden")

    with patch.object(
        app_module,
        "_open_db_connection",
        side_effect=RuntimeError("postgres://user:secret@localhost/db"),
    ):
        response = client.get("/dashboard")

    assert response.status_code == 200
    assert "postgres://" not in response.text
    assert "secret" not in response.text


def test_summary_excludes_private_fields(monkeypatch):
    conn = object()

    monkeypatch.setattr(
        progress_service,
        "get_active_course_enrollment_with_fallback",
        lambda conn, **kwargs: _enrollment_result(),
    )
    monkeypatch.setattr(
        progress_service,
        "list_module_progress",
        lambda conn, **kwargs: [
            {
                "module_key": "module-01",
                "status": "in_progress",
                "completed_topics": 1,
                "total_topics": 2,
                "progress_percent": 50,
                "metadata": {"private": "module-secret"},
                "notes": "private notes",
            }
        ],
    )
    monkeypatch.setattr(
        progress_service,
        "list_topic_progress",
        lambda conn, **kwargs: [
            {
                "module_key": "module-01",
                "topic_key": "topic-01",
                "legacy_topic_id": "legacy-01",
                "status": "completed",
                "completion_percent": 100,
                "required_activities_completed": 5,
                "required_activities_total": 5,
                "metadata": {"private": "topic-secret"},
                "submission": "private submission",
                "generated_content": "private generated content",
                "feedback": "private feedback",
                "notes": "private notes",
            }
        ],
    )

    summary = progress_service.build_dashboard_modular_progress_summary(
        conn,
        user_id="user-1",
        session_id="session-1",
        track_key="aipm",
    )

    assert summary["available"] is True
    forbidden = {
        "metadata",
        "submission",
        "submissions",
        "generated_content",
        "feedback",
        "notes",
    }
    assert forbidden.isdisjoint(summary.keys())
    assert forbidden.isdisjoint(summary["modules"][0].keys())
    assert forbidden.isdisjoint(summary["topics"][0].keys())
    assert "module-secret" not in str(summary)
    assert "private submission" not in str(summary)
    assert "private generated content" not in str(summary)
    assert "private feedback" not in str(summary)


def test_old_dashboard_progress_still_appears():
    _put_session(session_id="dashboard-modular-old-progress", current_week=3)

    with patch.object(
        app_module,
        "_open_db_connection",
        side_effect=RuntimeError("connection unavailable"),
    ):
        response = client.get("/dashboard")

    assert response.status_code == 200
    assert "Your Learning Summary" in response.text
    assert "Module 3" in response.text
    assert "Browse Module Topics" in response.text


def test_no_commit_or_rollback_for_read_only_dashboard():
    _put_session(session_id="dashboard-modular-read-only")
    conn = FakeReadConn()

    with patch.object(app_module, "_open_db_connection", return_value=conn):
        with patch.object(
            app_module,
            "get_active_course_enrollment_with_fallback",
            return_value=_enrollment_result(),
        ):
            with patch.object(
                app_module,
                "build_dashboard_modular_progress_summary",
                return_value=_modular_summary(),
            ):
                response = client.get("/dashboard")

    assert response.status_code == 200
    assert conn.committed is False
    assert conn.rolled_back is False
    assert conn.closed is True


def test_no_claude_call_is_made():
    _put_session(session_id="dashboard-modular-no-claude")

    with patch.object(
        app_module,
        "_make_client",
        side_effect=AssertionError("Claude must not be called"),
    ) as make_client:
        with patch.object(
            app_module,
            "_open_db_connection",
            side_effect=RuntimeError("connection unavailable"),
        ):
            response = client.get("/dashboard")

    assert response.status_code == 200
    make_client.assert_not_called()


def test_no_seed_script_is_called():
    _put_session(session_id="dashboard-modular-no-seed")

    with patch(
        "runpy.run_module",
        side_effect=AssertionError("seed scripts must not run"),
    ) as run_module:
        with patch.object(
            app_module,
            "_open_db_connection",
            side_effect=RuntimeError("connection unavailable"),
        ):
            response = client.get("/dashboard")

    assert response.status_code == 200
    run_module.assert_not_called()


def test_current_week_remains_supported_internally():
    session = _put_session(session_id="dashboard-modular-current-week", current_week=5)

    with patch.object(
        app_module,
        "_open_db_connection",
        side_effect=RuntimeError("connection unavailable"),
    ):
        response = client.get("/dashboard")

    assert response.status_code == 200
    assert session.current_week == 5
    assert session.to_dict()["current_week"] == 5


def test_weeks_and_role_tracks_are_not_mutated():
    _put_session(session_id="dashboard-modular-curriculum-constants")
    weeks_before = deepcopy(WEEKS)
    role_tracks_before = deepcopy(ROLE_TRACKS)

    with patch.object(
        app_module,
        "_open_db_connection",
        side_effect=RuntimeError("connection unavailable"),
    ):
        response = client.get("/dashboard")

    assert response.status_code == 200
    assert WEEKS == weeks_before
    assert ROLE_TRACKS == role_tracks_before


def test_route_url_remains_unchanged():
    routes = {
        (route.path, ",".join(sorted(getattr(route, "methods", set()) or [])))
        for route in app_module.app.routes
        if hasattr(route, "methods")
    }

    assert ("/dashboard", "GET") in routes
