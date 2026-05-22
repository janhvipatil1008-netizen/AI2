"""Tests for dashboard enrollment summary fallback behavior."""

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
    session_id: str = "dashboard-enrollment-session",
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


def _db_result(**overrides) -> dict:
    result = {
        "source": "db",
        "enrollment": {
            "course_key": "aipm-foundations",
            "status": "active",
            "progress_percent": 42,
            "current_module_key": "module-02",
            "current_topic_key": "topic-03",
            "current_legacy_topic_id": "aipm-week-2-topic-03",
            "metadata": {"secret": "do-not-render"},
            "feedback": "private",
            "generated_content": "private",
            "notes": "private",
        },
        "error": None,
    }
    result.update(overrides)
    return result


def test_dashboard_renders_with_db_enrollment_source():
    session_id = "dashboard-db-enrollment"
    _put_session(session_id=session_id)
    conn = FakeReadConn()

    with patch.object(app_module, "_open_db_connection", return_value=conn):
        with patch.object(
            app_module,
            "get_active_course_enrollment_with_fallback",
            return_value=_db_result(),
        ) as get_enrollment:
            response = client.get("/dashboard")

    assert response.status_code == 200
    assert "Learning path" in response.text
    assert "Course" in response.text
    assert "aipm-foundations" in response.text
    assert "42%" in response.text
    assert "module-02" in response.text
    get_enrollment.assert_called_once_with(
        conn,
        user_id="user-1",
        session_id=session_id,
        track_key="aipm",
    )
    assert conn.closed is True


def test_dashboard_renders_with_fallback_enrollment_source():
    _put_session(session_id="dashboard-fallback-enrollment")
    conn = FakeReadConn()

    with patch.object(app_module, "_open_db_connection", return_value=conn):
        with patch.object(
            app_module,
            "get_active_course_enrollment_with_fallback",
            return_value={
                "source": "fallback",
                "enrollment": {
                    "course_key": "aipm-foundations",
                    "status": "active",
                    "current_module_key": None,
                    "current_topic_key": None,
                    "current_legacy_topic_id": None,
                    "progress_percent": 0,
                },
                "error": None,
            },
        ):
            response = client.get("/dashboard")

    assert response.status_code == 200
    assert "Your adaptive learning dashboard" in response.text
    assert "Your Learning Summary" in response.text
    assert "Learning path" not in response.text
    assert conn.closed is True


def test_dashboard_renders_when_db_connection_fails():
    _put_session(session_id="dashboard-db-fails")

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
    _put_session(session_id="dashboard-no-error-leak")

    with patch.object(
        app_module,
        "_open_db_connection",
        side_effect=RuntimeError("postgres://user:secret@localhost/db"),
    ):
        response = client.get("/dashboard")

    assert response.status_code == 200
    assert "postgres://" not in response.text
    assert "secret" not in response.text


def test_enrollment_summary_contains_only_safe_fields():
    conn = FakeReadConn()
    session = SessionContext(track=CareerTrack.AI_PM, user_id="user-1")

    with patch.object(app_module, "_open_db_connection", return_value=conn):
        with patch.object(
            app_module,
            "get_active_course_enrollment_with_fallback",
            return_value=_db_result(),
        ):
            summary = app_module._dashboard_enrollment_summary(
                user_id="user-1",
                session_id="session-1",
                session=session,
            )

    assert summary == {
        "source": "db",
        "course_key": "aipm-foundations",
        "status": "active",
        "progress_percent": 42,
        "current_module_key": "module-02",
        "current_topic_key": "topic-03",
        "current_legacy_topic_id": "aipm-week-2-topic-03",
        "error": None,
    }
    forbidden = {
        "metadata",
        "submissions",
        "feedback",
        "notes",
        "generated_content",
    }
    assert forbidden.isdisjoint(summary.keys())


def test_old_dashboard_progress_still_appears():
    _put_session(session_id="dashboard-old-progress", current_week=3)

    with patch.object(
        app_module,
        "_open_db_connection",
        side_effect=RuntimeError("connection unavailable"),
    ):
        response = client.get("/dashboard")

    assert response.status_code == 200
    assert "Continue Learning" in response.text
    assert "Your Learning Summary" in response.text
    assert "Module 3" in response.text
    assert "Browse Module Topics" in response.text


def test_current_week_remains_supported_internally():
    session = _put_session(session_id="dashboard-current-week", current_week=5)

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
    _put_session(session_id="dashboard-curriculum-constants")
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


def test_no_claude_call_is_made():
    _put_session(session_id="dashboard-no-claude")

    with patch.object(app_module, "_make_client", side_effect=AssertionError("Claude must not be called")) as make_client:
        with patch.object(
            app_module,
            "_open_db_connection",
            side_effect=RuntimeError("connection unavailable"),
        ):
            response = client.get("/dashboard")

    assert response.status_code == 200
    make_client.assert_not_called()


def test_no_seed_script_is_called():
    _put_session(session_id="dashboard-no-seed")

    with patch("runpy.run_module", side_effect=AssertionError("seed scripts must not run")) as run_module:
        with patch.object(
            app_module,
            "_open_db_connection",
            side_effect=RuntimeError("connection unavailable"),
        ):
            response = client.get("/dashboard")

    assert response.status_code == 200
    run_module.assert_not_called()


def test_no_commit_or_rollback_called_for_read_only_dashboard():
    _put_session(session_id="dashboard-read-only")
    conn = FakeReadConn()

    with patch.object(app_module, "_open_db_connection", return_value=conn):
        with patch.object(
            app_module,
            "get_active_course_enrollment_with_fallback",
            return_value=_db_result(),
        ):
            response = client.get("/dashboard")

    assert response.status_code == 200
    assert conn.committed is False
    assert conn.rolled_back is False
    assert conn.closed is True


def test_no_db_connection_opened_without_user_context():
    _put_session(session_id="dashboard-no-user", user_id="")

    with patch.object(
        app_module,
        "_open_db_connection",
        side_effect=AssertionError("DB must not be opened without user context"),
    ) as open_db:
        response = client.get("/dashboard")

    assert response.status_code == 200
    open_db.assert_not_called()


def test_route_url_remains_unchanged():
    routes = {
        (route.path, ",".join(sorted(getattr(route, "methods", set()) or [])))
        for route in app_module.app.routes
        if hasattr(route, "methods")
    }

    assert ("/dashboard", "GET") in routes
