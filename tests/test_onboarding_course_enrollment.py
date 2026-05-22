"""Tests for best-effort course enrollment after onboarding save."""

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


class FakeConn:
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


class FakeConnManager:
    def __init__(self, conn: FakeConn):
        self.conn = conn
        self.entered = False

    def __enter__(self):
        self.entered = True
        return self.conn

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.conn.commit()
        else:
            self.conn.rollback()
        self.conn.close()
        return False


def _form(session_id: str, **overrides) -> dict:
    data = {
        "session_id": session_id,
        "goal": "aipm",
        "level": "beginner",
        "weekly_time": "five_hours",
    }
    data.update(overrides)
    return data


def _put_session(
    *,
    session_id: str = "enrollment-session",
    user_id: str = "user-1",
    current_week: int = 3,
) -> SessionContext:
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


def test_onboarding_still_succeeds_when_enrollment_db_write_succeeds():
    session_id = "enrollment-success"
    _put_session(session_id=session_id)
    conn = FakeConn()
    conn_manager = FakeConnManager(conn)

    with patch.object(app_module, "get_conn", return_value=conn_manager):
        with patch.object(
            app_module,
            "ensure_course_enrollment",
            return_value={
                "source": "created",
                "enrollment": {"enrollment_id": 1},
                "created": True,
                "error": None,
            },
        ) as ensure:
            response = client.post(
                "/onboarding/save",
                data=_form(session_id),
                follow_redirects=False,
            )

    assert response.status_code == 302
    assert response.headers["location"] == f"/topics/{session_id}"
    assert conn.committed is True
    assert conn.rolled_back is False
    assert conn.closed is True
    ensure.assert_called_once_with(
        conn,
        user_id="user-1",
        session_id=session_id,
        track_key="aipm",
        source="onboarding",
    )


def test_onboarding_still_succeeds_when_db_connection_fails():
    session_id = "enrollment-connect-fails"
    session = _put_session(session_id=session_id)

    with patch.object(
        app_module,
        "get_conn",
        side_effect=RuntimeError("postgres://user:secret@localhost/db"),
    ):
        with patch.object(app_module, "ensure_course_enrollment") as ensure:
            response = client.post(
                "/onboarding/save",
                data=_form(session_id),
                follow_redirects=False,
            )

    assert response.status_code == 302
    assert response.headers["location"] == f"/topics/{session_id}"
    assert session.has_completed_onboarding() is True
    ensure.assert_not_called()


def test_onboarding_still_succeeds_when_ensure_course_enrollment_returns_error():
    session_id = "enrollment-service-error"
    _put_session(session_id=session_id)
    conn = FakeConn()

    with patch.object(app_module, "get_conn", return_value=FakeConnManager(conn)):
        with patch.object(
            app_module,
            "ensure_course_enrollment",
            return_value={
                "source": "error",
                "enrollment": None,
                "created": False,
                "error": "safe error",
            },
        ):
            response = client.post(
                "/onboarding/save",
                data=_form(session_id),
                follow_redirects=False,
            )

    assert response.status_code == 302
    assert conn.committed is False
    assert conn.rolled_back is True
    assert conn.closed is True


def test_ensure_course_enrollment_is_called_with_onboarding_source():
    session_id = "enrollment-source"
    _put_session(session_id=session_id)
    conn = FakeConn()

    with patch.object(app_module, "get_conn", return_value=FakeConnManager(conn)):
        with patch.object(
            app_module,
            "ensure_course_enrollment",
            return_value={
                "source": "existing",
                "enrollment": {"enrollment_id": 2},
                "created": False,
                "error": None,
            },
        ) as ensure:
            response = client.post(
                "/onboarding/save",
                data=_form(session_id),
                follow_redirects=False,
            )

    assert response.status_code == 302
    assert ensure.call_args.kwargs["source"] == "onboarding"


def test_recommended_track_is_passed_to_enrollment_service():
    session_id = "enrollment-track"
    _put_session(session_id=session_id)
    conn = FakeConn()

    with patch.object(app_module, "get_conn", return_value=FakeConnManager(conn)):
        with patch.object(
            app_module,
            "ensure_course_enrollment",
            return_value={
                "source": "created",
                "enrollment": {"enrollment_id": 3},
                "created": True,
                "error": None,
            },
        ) as ensure:
            response = client.post(
                "/onboarding/save",
                data=_form(
                    session_id,
                    goal="ai_builder",
                    level="building_projects",
                    weekly_time="ten_hours",
                ),
                follow_redirects=False,
            )

    assert response.status_code == 302
    assert ensure.call_args.kwargs["track_key"] == "context"


def test_rollback_happens_on_enrollment_exception_if_connection_was_opened():
    session_id = "enrollment-raises"
    _put_session(session_id=session_id)
    conn = FakeConn()

    with patch.object(app_module, "get_conn", return_value=FakeConnManager(conn)):
        with patch.object(
            app_module,
            "ensure_course_enrollment",
            side_effect=RuntimeError("db write failed password=secret"),
        ):
            response = client.post(
                "/onboarding/save",
                data=_form(session_id),
                follow_redirects=False,
            )

    assert response.status_code == 302
    assert conn.committed is False
    assert conn.rolled_back is True
    assert conn.closed is True


def test_no_db_connection_opened_if_user_context_is_missing():
    session_id = "enrollment-no-user"
    session = _put_session(session_id=session_id, user_id="")

    with patch.object(
        app_module,
        "get_conn",
        side_effect=AssertionError("DB must not be opened without user context"),
    ) as get_conn:
        with patch.object(app_module, "ensure_course_enrollment") as ensure:
            response = client.post(
                "/onboarding/save",
                data=_form(session_id),
                follow_redirects=False,
            )

    assert response.status_code == 302
    assert session.has_completed_onboarding() is True
    get_conn.assert_not_called()
    ensure.assert_not_called()


def test_no_learner_facing_db_error_is_shown():
    session_id = "enrollment-no-error-leak"
    _put_session(session_id=session_id)

    with patch.object(
        app_module,
        "get_conn",
        side_effect=RuntimeError("postgres://user:secret@localhost/db"),
    ):
        response = client.post(
            "/onboarding/save",
            data=_form(session_id),
            follow_redirects=False,
        )

    assert response.status_code == 302
    assert "postgres://" not in response.text
    assert "secret" not in response.text
    assert "postgres://" not in response.headers["location"]
    assert "secret" not in response.headers["location"]


def test_session_context_onboarding_behavior_remains_unchanged():
    session_id = "enrollment-session-behavior"
    session = _put_session(session_id=session_id, current_week=4)

    with patch.object(
        app_module,
        "get_conn",
        side_effect=RuntimeError("connection unavailable"),
    ):
        response = client.post(
            "/onboarding/save",
            data=_form(
                session_id,
                goal="interview_prep",
                level="job_ready",
                weekly_time="two_hours",
            ),
            follow_redirects=False,
        )

    profile = session.get_onboarding_profile()
    assert response.status_code == 302
    assert profile["goal"] == "interview_prep"
    assert profile["level"] == "job_ready"
    assert profile["weekly_time"] == "two_hours"
    assert profile["recommended_track"] == "aipm"
    assert session.has_completed_onboarding() is True


def test_current_week_remains_unchanged():
    session_id = "enrollment-current-week"
    session = _put_session(session_id=session_id, current_week=6)

    with patch.object(
        app_module,
        "get_conn",
        side_effect=RuntimeError("connection unavailable"),
    ):
        response = client.post(
            "/onboarding/save",
            data=_form(session_id),
            follow_redirects=False,
        )

    assert response.status_code == 302
    assert session.current_week == 6


def test_weeks_and_role_tracks_are_not_mutated():
    session_id = "enrollment-curriculum-constants"
    _put_session(session_id=session_id)
    weeks_before = deepcopy(WEEKS)
    role_tracks_before = deepcopy(ROLE_TRACKS)

    with patch.object(
        app_module,
        "get_conn",
        side_effect=RuntimeError("connection unavailable"),
    ):
        response = client.post(
            "/onboarding/save",
            data=_form(session_id),
            follow_redirects=False,
        )

    assert response.status_code == 302
    assert WEEKS == weeks_before
    assert ROLE_TRACKS == role_tracks_before


def test_route_url_remains_unchanged():
    routes = {
        (route.path, ",".join(sorted(getattr(route, "methods", set()) or [])))
        for route in app_module.app.routes
        if hasattr(route, "methods")
    }

    assert ("/onboarding/save", "POST") in routes
    assert ("/onboarding/{session_id}", "GET") in routes


def test_save_session_still_receives_onboarding_session():
    session_id = "enrollment-save-session"
    _put_session(session_id=session_id)

    with patch.object(
        app_module,
        "get_conn",
        side_effect=RuntimeError("connection unavailable"),
    ):
        with patch.object(app_module, "_save_session") as save_session:
            response = client.post(
                "/onboarding/save",
                data=_form(session_id),
                follow_redirects=False,
            )

    assert response.status_code == 302
    save_session.assert_called_once()
    saved_session = save_session.call_args.args[1]
    assert saved_session.has_completed_onboarding() is True


def test_generic_warning_does_not_log_db_secret(caplog):
    session_id = "enrollment-log"
    _put_session(session_id=session_id)

    with patch.object(
        app_module,
        "get_conn",
        side_effect=RuntimeError("postgres://user:secret@localhost/db"),
    ):
        response = client.post(
            "/onboarding/save",
            data=_form(session_id),
            follow_redirects=False,
        )

    assert response.status_code == 302
    assert "secret" not in caplog.text
    assert "postgres://" not in caplog.text
    assert "onboarding course enrollment failed" in caplog.text


def test_no_claude_call_for_onboarding_enrollment():
    session_id = "enrollment-no-claude"
    _put_session(session_id=session_id)
    conn = FakeConn()

    with patch.object(app_module, "_make_client", side_effect=AssertionError("Claude must not be called")) as make_client:
        with patch.object(app_module, "get_conn", return_value=FakeConnManager(conn)):
            with patch.object(
                app_module,
                "ensure_course_enrollment",
                return_value={
                    "source": "created",
                    "enrollment": {"enrollment_id": 4},
                    "created": True,
                    "error": None,
                },
            ):
                response = client.post(
                    "/onboarding/save",
                    data=_form(session_id),
                    follow_redirects=False,
                )

    assert response.status_code == 302
    make_client.assert_not_called()
