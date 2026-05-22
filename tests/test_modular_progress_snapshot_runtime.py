"""Runtime tests for best-effort modular progress snapshot mirroring."""

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
from curriculum.topics import get_topics_for_week
from services import modular_progress_snapshot_service as snapshot_service


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


class FakeConnContext:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self.conn

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.conn.commit()
        else:
            self.conn.rollback()
        self.conn.close()
        return False


def _topic_id() -> str:
    return get_topics_for_week("aipm", 1)[0].topic_id


def _put_session(
    *,
    session_id: str = "modular-progress-runtime",
    user_id: str = "user-1",
    current_week: int = 1,
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


def _progress_payload(session_id: str, **overrides) -> dict:
    data = {
        "session_id": session_id,
        "topic_id": _topic_id(),
        "step": "learn",
        "status": "done",
    }
    data.update(overrides)
    return data


def _course_structure(topic_id: str) -> dict:
    return {
        "course": {"course_key": "aipm-foundations"},
        "modules": [
            {
                "module_key": "module-01",
                "sequence_order": 0,
                "topics": [
                    {
                        "module_key": "module-01",
                        "topic_key": "topic-1",
                        "legacy_topic_id": topic_id,
                        "activities": [
                            {"activity_type": "lesson", "is_required": True},
                            {"activity_type": "quiz", "is_required": True},
                        ],
                        "metadata": {"private": "do-not-write"},
                    }
                ],
            }
        ],
        "unassigned_topics": [],
    }


def test_existing_topic_progress_action_still_succeeds_when_modular_write_succeeds(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    session_id = "modular-write-success"
    _put_session(session_id=session_id)
    conn = FakeConn()

    with patch("routes.deps.write_through_topic_progress"):
        with patch("database.pool.get_conn", return_value=FakeConnContext(conn)):
            with patch(
                "services.modular_progress_snapshot_service.write_modular_progress_snapshot_safely",
                return_value={"updated": True, "skipped": False, "source": "db", "error": None},
            ) as snapshot:
                response = client.post("/topic/progress", json=_progress_payload(session_id))

    assert response.status_code == 200
    assert response.json()["topic_progress"]["learn"] == "done"
    assert response.json()["completion_percent"] == 20
    assert conn.committed is True
    assert conn.rolled_back is False
    assert conn.closed is True
    snapshot.assert_called_once()


def test_existing_topic_progress_action_still_succeeds_when_db_connection_fails(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    session_id = "modular-db-fails"
    session = _put_session(session_id=session_id)

    with patch("routes.deps.write_through_topic_progress"):
        with patch(
            "database.pool.get_conn",
            side_effect=RuntimeError("postgres://user:secret@localhost/db"),
        ):
            response = client.post("/topic/progress", json=_progress_payload(session_id))

    assert response.status_code == 200
    assert response.json()["topic_progress"]["learn"] == "done"
    assert session.get_topic_progress(_topic_id())["learn"] == "done"


def test_existing_topic_progress_action_still_succeeds_when_snapshot_helper_returns_error(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    session_id = "modular-helper-error"
    session = _put_session(session_id=session_id)
    conn = FakeConn()

    with patch("routes.deps.write_through_topic_progress"):
        with patch("database.pool.get_conn", return_value=FakeConnContext(conn)):
            with patch(
                "services.modular_progress_snapshot_service.write_modular_progress_snapshot_safely",
                return_value={
                    "updated": False,
                    "skipped": False,
                    "source": "write_error",
                    "error": "safe error",
                },
            ):
                response = client.post("/topic/progress", json=_progress_payload(session_id))

    assert response.status_code == 200
    assert response.json()["topic_progress"]["learn"] == "done"
    assert session.get_topic_progress(_topic_id())["learn"] == "done"
    assert conn.committed is False
    assert conn.rolled_back is True
    assert conn.closed is True


def test_modular_snapshot_helper_calculates_progress_using_legacy_topic_id_bridge(monkeypatch):
    topic_id = _topic_id()
    session = SessionContext(track=CareerTrack.AI_PM, user_id="user-1")
    session.mark_topic_step(topic_id, "learn", "done")
    captured = {}

    monkeypatch.setattr(
        snapshot_service,
        "get_active_course_enrollment_with_fallback",
        lambda *args, **kwargs: {
            "source": "db",
            "enrollment": {"enrollment_id": 11, "course_key": "aipm-foundations"},
            "error": None,
        },
    )
    monkeypatch.setattr(
        snapshot_service,
        "get_course_structure_with_fallback",
        lambda *args, **kwargs: {
            "source": "db",
            "course_structure": _course_structure(topic_id),
            "error": None,
        },
    )

    def fake_write(conn, *, enrollment_id, course_progress):
        captured["enrollment_id"] = enrollment_id
        captured["course_progress"] = course_progress
        return {"updated": True, "error": None}

    monkeypatch.setattr(snapshot_service, "write_modular_progress_snapshot", fake_write)

    result = snapshot_service.write_modular_progress_snapshot_safely(
        conn=object(),
        user_id="user-1",
        session_id="session-1",
        session=session,
    )

    assert result["updated"] is True
    assert captured["enrollment_id"] == 11
    topic_progress = captured["course_progress"]["topic_progress"][0]
    assert topic_progress["legacy_topic_id"] == topic_id
    assert topic_progress["required_activities_completed"] == 1
    assert topic_progress["completion_percent"] == 50


def test_no_learner_facing_db_error_is_shown(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    session_id = "modular-no-error-leak"
    _put_session(session_id=session_id)

    with patch("routes.deps.write_through_topic_progress"):
        with patch(
            "database.pool.get_conn",
            side_effect=RuntimeError("postgres://user:secret@localhost/db"),
        ):
            response = client.post("/topic/progress", json=_progress_payload(session_id))

    assert response.status_code == 200
    assert "postgres://" not in response.text
    assert "secret" not in response.text


def test_session_context_progress_remains_source_of_truth(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    session_id = "modular-session-source"
    session = _put_session(session_id=session_id)
    topic_id = _topic_id()

    with patch("routes.deps.write_through_topic_progress"):
        with patch("database.pool.get_conn", side_effect=RuntimeError("db down")):
            response = client.post(
                "/topic/progress",
                json=_progress_payload(session_id, topic_id=topic_id, step="quiz", status="done"),
            )

    assert response.status_code == 200
    assert response.json()["topic_progress"]["quiz"] == "done"
    assert session.get_topic_progress(topic_id)["quiz"] == "done"
    assert session.topic_completion_percent(topic_id) == 20


def test_current_week_remains_unchanged(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    session_id = "modular-current-week"
    session = _put_session(session_id=session_id, current_week=4)

    with patch("routes.deps.write_through_topic_progress"):
        with patch("database.pool.get_conn", side_effect=RuntimeError("db down")):
            response = client.post("/topic/progress", json=_progress_payload(session_id))

    assert response.status_code == 200
    assert session.current_week == 4
    assert session.to_dict()["current_week"] == 4


def test_weeks_and_role_tracks_are_not_mutated(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    session_id = "modular-constants"
    _put_session(session_id=session_id)
    weeks_before = deepcopy(WEEKS)
    role_tracks_before = deepcopy(ROLE_TRACKS)

    with patch("routes.deps.write_through_topic_progress"):
        with patch("database.pool.get_conn", side_effect=RuntimeError("db down")):
            response = client.post("/topic/progress", json=_progress_payload(session_id))

    assert response.status_code == 200
    assert WEEKS == weeks_before
    assert ROLE_TRACKS == role_tracks_before


def test_no_claude_call_is_made(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    session_id = "modular-no-claude"
    _put_session(session_id=session_id)

    with patch.object(app_module, "_make_client", side_effect=AssertionError("Claude must not be called")) as make_client:
        with patch("routes.deps.write_through_topic_progress"):
            with patch("database.pool.get_conn", side_effect=RuntimeError("db down")):
                response = client.post("/topic/progress", json=_progress_payload(session_id))

    assert response.status_code == 200
    make_client.assert_not_called()


def test_no_seed_script_is_called(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    session_id = "modular-no-seed"
    _put_session(session_id=session_id)

    with patch("runpy.run_module", side_effect=AssertionError("seed scripts must not run")) as run_module:
        with patch("routes.deps.write_through_topic_progress"):
            with patch("database.pool.get_conn", side_effect=RuntimeError("db down")):
                response = client.post("/topic/progress", json=_progress_payload(session_id))

    assert response.status_code == 200
    run_module.assert_not_called()


def test_route_urls_unchanged():
    routes = {
        (route.path, ",".join(sorted(getattr(route, "methods", set()) or [])))
        for route in app_module.app.routes
        if hasattr(route, "methods")
    }

    assert ("/topic/progress", "POST") in routes
    assert ("/topic/notes", "POST") in routes


def test_private_generated_content_and_submission_text_not_written_to_snapshot(monkeypatch):
    topic_id = _topic_id()
    session = SessionContext(track=CareerTrack.AI_PM, user_id="user-1")
    session.generated_topic_content[topic_id] = {"content": "PRIVATE GENERATED"}
    session.quiz_submissions[topic_id] = {
        "answers": "PRIVATE ANSWERS",
        "evaluation": "PRIVATE EVAL",
    }
    session.portfolio_submissions[topic_id] = {
        "submission": "PRIVATE SUBMISSION",
        "feedback": "PRIVATE FEEDBACK",
    }
    session.interview_submissions[topic_id] = {
        "answer": "PRIVATE ANSWER",
        "feedback": "PRIVATE INTERVIEW",
    }
    captured = {}

    monkeypatch.setattr(
        snapshot_service,
        "get_active_course_enrollment_with_fallback",
        lambda *args, **kwargs: {
            "source": "db",
            "enrollment": {"enrollment_id": 11, "course_key": "aipm-foundations"},
            "error": None,
        },
    )
    monkeypatch.setattr(
        snapshot_service,
        "get_course_structure_with_fallback",
        lambda *args, **kwargs: {
            "source": "db",
            "course_structure": _course_structure(topic_id),
            "error": None,
        },
    )
    def fake_write(conn, *, enrollment_id, course_progress):
        captured["course_progress"] = course_progress
        return {"updated": True, "error": None}

    monkeypatch.setattr(snapshot_service, "write_modular_progress_snapshot", fake_write)

    result = snapshot_service.write_modular_progress_snapshot_safely(
        conn=object(),
        user_id="user-1",
        session_id="session-1",
        session=session,
    )

    rendered = repr(captured["course_progress"])
    assert result["updated"] is True
    assert "PRIVATE GENERATED" not in rendered
    assert "PRIVATE ANSWERS" not in rendered
    assert "PRIVATE SUBMISSION" not in rendered
    assert "PRIVATE ANSWER" not in rendered
