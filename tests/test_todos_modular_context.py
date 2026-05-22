"""Tests for module/path todo planner context."""

from __future__ import annotations

import html
import os
import re
from copy import deepcopy
from unittest.mock import patch

os.environ["AI2_TEST_MODE"] = "1"
os.environ["ANTHROPIC_API_KEY"] = "test-key"

from fastapi.testclient import TestClient

import app as app_module
from config import CareerTrack
from context.session import SessionContext
from curriculum.syllabus import ROLE_TRACKS, WEEKS
from services.todo_context_service import build_todo_learning_context


client = TestClient(app_module.app)


def _visible_text(response_text: str) -> str:
    without_scripts = re.sub(
        r"<script\b[^>]*>.*?</script>",
        " ",
        response_text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    without_comments = re.sub(r"<!--.*?-->", " ", without_scripts, flags=re.DOTALL)
    without_tags = re.sub(r"<[^>]+>", " ", without_comments)
    return re.sub(r"\s+", " ", html.unescape(without_tags))


def _start_session(*, week: int = 2) -> str:
    app_module._sessions.clear()
    response = client.post("/session/start", json={"track": "aipm", "week": week})
    assert response.status_code == 200, response.text
    return response.json()["session_id"]


def _create_todo(session_id: str, title: str, todo_type: str = "daily") -> dict:
    response = client.post(
        "/todos/create",
        json={
            "session_id": session_id,
            "title": title,
            "todo_type": todo_type,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_todos_page_still_renders_with_existing_session_context_todos(monkeypatch):
    monkeypatch.delenv("AI2_TODOS_DB_READS_ENABLED", raising=False)
    monkeypatch.delenv("AI2_DB_WRITE_THROUGH_ENABLED", raising=False)
    session_id = _start_session()
    _create_todo(session_id, "Read the paper", "daily")
    _create_todo(session_id, "Build the demo", "weekly")

    response = client.get(f"/todos/{session_id}")

    assert response.status_code == 200
    assert "Read the paper" in response.text
    assert "Build the demo" in response.text
    assert "My Learning Planner" in response.text


def test_todos_page_still_renders_when_db_todo_reads_fail(monkeypatch):
    monkeypatch.delenv("AI2_TODOS_DB_READS_ENABLED", raising=False)
    monkeypatch.delenv("AI2_DB_WRITE_THROUGH_ENABLED", raising=False)
    session_id = _start_session()
    _create_todo(session_id, "Session fallback todo", "daily")

    monkeypatch.setenv("AI2_TODOS_DB_READS_ENABLED", "1")
    with patch(
        "database.pool.get_conn",
        side_effect=RuntimeError("postgres://user:secret@localhost/db"),
    ):
        response = client.get(f"/todos/{session_id}")

    assert response.status_code == 200
    assert "Session fallback todo" in response.text
    assert "postgres://" not in response.text
    assert "secret" not in response.text


def test_todo_visible_wording_uses_module_path_language(monkeypatch):
    monkeypatch.delenv("AI2_TODOS_DB_READS_ENABLED", raising=False)
    session_id = _start_session(week=3)

    response = client.get(f"/todos/{session_id}")
    visible = _visible_text(response.text)

    assert response.status_code == 200
    assert "Module 3" in visible
    assert "Learning Path Tasks" in visible
    assert "learning path tasks" in visible
    assert "Module Topics" in visible
    assert "Week" not in visible
    assert "this week" not in visible.lower()
    assert "Weekly" not in visible


def test_todo_learning_context_prefers_modular_context():
    session = SessionContext(track=CareerTrack.AI_PM, current_week=4)
    context = build_todo_learning_context(
        modular_progress_summary={
            "source": "db",
            "available": True,
            "course_key": "aipm-foundations",
            "current_module_key": "module-02",
            "current_topic_key": "topic-03",
            "current_legacy_topic_id": "legacy-03",
            "metadata": {"secret": "no"},
            "feedback": "private",
        },
        enrollment_summary={
            "source": "db",
            "course_key": "other",
            "current_module_key": "other-module",
        },
        session=session,
    )

    assert context == {
        "course_key": "aipm-foundations",
        "current_module_key": "module-02",
        "current_topic_key": "topic-03",
        "current_legacy_topic_id": "legacy-03",
        "source": "db",
    }
    assert "metadata" not in context
    assert "feedback" not in context


def test_todo_learning_context_falls_back_to_enrollment_context():
    context = build_todo_learning_context(
        enrollment_summary={
            "source": "db",
            "course_key": "aipm-foundations",
            "current_module_key": "module-01",
            "current_topic_key": "topic-01",
            "current_legacy_topic_id": "legacy-01",
            "generated_content": "private",
        },
        modular_progress_summary={"source": "fallback", "available": False},
        session=SessionContext(track=CareerTrack.AI_PM, current_week=5),
    )

    assert context["source"] == "db"
    assert context["current_module_key"] == "module-01"
    assert context["current_topic_key"] == "topic-01"
    assert "generated_content" not in context


def test_todo_learning_context_falls_back_to_session_current_week_safely():
    session = SessionContext(track=CareerTrack.AI_PM, current_week=5)

    context = build_todo_learning_context(session=session)

    assert context == {
        "course_key": "aipm-foundations",
        "current_module_key": "Module 5",
        "current_topic_key": None,
        "current_legacy_topic_id": None,
        "source": "session",
    }
    assert session.current_week == 5


def test_no_learner_facing_db_error_is_shown(monkeypatch):
    monkeypatch.delenv("AI2_TODOS_DB_READS_ENABLED", raising=False)
    session_id = _start_session()
    monkeypatch.setenv("AI2_TODOS_DB_READS_ENABLED", "1")

    with patch(
        "database.pool.get_conn",
        side_effect=RuntimeError("private DB error token=abc123"),
    ):
        response = client.get(f"/todos/{session_id}")

    assert response.status_code == 200
    assert "private DB error" not in response.text
    assert "abc123" not in response.text


def test_existing_todo_create_and_update_behavior_remains_unchanged(monkeypatch):
    monkeypatch.delenv("AI2_TODOS_DB_READS_ENABLED", raising=False)
    monkeypatch.delenv("AI2_DB_WRITE_THROUGH_ENABLED", raising=False)
    session_id = _start_session()

    created = _create_todo(session_id, "Module task", "weekly")
    todo_id = created["todo"]["todo_id"]
    assert created["todo"]["todo_type"] == "weekly"
    assert created["todo_counts"]["total"] == 1

    response = client.post(
        "/todos/status",
        json={
            "session_id": session_id,
            "todo_id": todo_id,
            "status": "done",
        },
    )

    assert response.status_code == 200
    assert response.json()["todo"]["status"] == "done"
    assert response.json()["todo_counts"]["done"] == 1


def test_current_week_remains_supported_internally(monkeypatch):
    monkeypatch.delenv("AI2_TODOS_DB_READS_ENABLED", raising=False)
    session_id = _start_session(week=4)
    session = app_module._sessions[session_id]["session"]

    response = client.get(f"/todos/{session_id}")

    assert response.status_code == 200
    assert session.current_week == 4
    assert session.to_dict()["current_week"] == 4


def test_weeks_and_role_tracks_are_not_mutated(monkeypatch):
    monkeypatch.delenv("AI2_TODOS_DB_READS_ENABLED", raising=False)
    weeks_before = deepcopy(WEEKS)
    role_tracks_before = deepcopy(ROLE_TRACKS)
    session_id = _start_session()

    response = client.get(f"/todos/{session_id}")

    assert response.status_code == 200
    assert WEEKS == weeks_before
    assert ROLE_TRACKS == role_tracks_before


def test_no_claude_call_is_made(monkeypatch):
    monkeypatch.delenv("AI2_TODOS_DB_READS_ENABLED", raising=False)
    session_id = _start_session()

    with patch.object(
        app_module,
        "_make_client",
        side_effect=AssertionError("Claude must not be called"),
    ) as make_client:
        response = client.get(f"/todos/{session_id}")

    assert response.status_code == 200
    make_client.assert_not_called()


def test_no_seed_script_is_called(monkeypatch):
    monkeypatch.delenv("AI2_TODOS_DB_READS_ENABLED", raising=False)
    session_id = _start_session()

    with patch(
        "runpy.run_module",
        side_effect=AssertionError("seed scripts must not run"),
    ) as run_module:
        response = client.get(f"/todos/{session_id}")

    assert response.status_code == 200
    run_module.assert_not_called()


def test_route_urls_remain_unchanged():
    routes = {
        (route.path, ",".join(sorted(getattr(route, "methods", set()) or [])))
        for route in app_module.app.routes
        if hasattr(route, "methods")
    }

    assert ("/todos/{session_id}", "GET") in routes
    assert ("/todos/create", "POST") in routes
    assert ("/todos/status", "POST") in routes
