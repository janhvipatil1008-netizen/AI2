"""Tests for modular position display on dashboard and todos.

Verifies:
- dashboard shows current/next topic when modular progress is available
- dashboard falls back to Module N when modular progress is unavailable
- todos can display module/path context without week wording
- no learner-facing DB error is shown
- existing dashboard cards still render
- existing todos still render
- current_week remains internally supported
- WEEKS/ROLE_TRACKS are not mutated
- no Claude call is made
- no seed script is called
- route URLs remain unchanged
"""

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
import routes.dashboard as dashboard_module
import routes.deps as deps_module
from config import CareerTrack
from context.session import SessionContext
from curriculum.syllabus import ROLE_TRACKS, WEEKS

client = TestClient(app_module.app)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _visible_text(response_text: str) -> str:
    without_scripts = re.sub(
        r"<script\b[^>]*>.*?</script>", " ", response_text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    without_comments = re.sub(r"<!--.*?-->", " ", without_scripts, flags=re.DOTALL)
    without_tags = re.sub(r"<[^>]+>", " ", without_comments)
    return re.sub(r"\s+", " ", html.unescape(without_tags))


def _put_session(
    *,
    session_id: str = "pos-display-test",
    user_id: str = "user-pos-1",
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


def _start_session(*, week: int = 2) -> str:
    app_module._sessions.clear()
    response = client.post("/session/start", json={"track": "aipm", "week": week})
    assert response.status_code == 200, response.text
    return response.json()["session_id"]


def _modular_summary_available(**overrides) -> dict:
    summary = {
        "source": "db",
        "available": True,
        "course_key": "aipm-foundations",
        "progress_percent": 40,
        "current_module_key": "module-01",
        "current_topic_key": "topic-alpha",
        "current_legacy_topic_id": "aipm-t-alpha",
        "modules": [
            {
                "module_key": "module-01",
                "status": "in_progress",
                "completed_topics": 1,
                "total_topics": 3,
                "progress_percent": 33,
            }
        ],
        "topics": [
            {
                "module_key": "module-01",
                "topic_key": "topic-done",
                "legacy_topic_id": "aipm-t-done",
                "status": "completed",
                "completion_percent": 100,
                "required_activities_completed": 3,
                "required_activities_total": 3,
            },
            {
                "module_key": "module-01",
                "topic_key": "topic-alpha",
                "legacy_topic_id": "aipm-t-alpha",
                "status": "in_progress",
                "completion_percent": 40,
                "required_activities_completed": 2,
                "required_activities_total": 5,
            },
            {
                "module_key": "module-01",
                "topic_key": "topic-beta",
                "legacy_topic_id": "aipm-t-beta",
                "status": "not_started",
                "completion_percent": 0,
                "required_activities_completed": 0,
                "required_activities_total": 5,
            },
        ],
        "error": None,
    }
    summary.update(overrides)
    return summary


def _modular_summary_unavailable() -> dict:
    return {
        "source": "fallback",
        "available": False,
        "progress_percent": 0,
        "modules": [],
        "topics": [],
        "error": None,
    }


def _enrollment_result_disabled() -> dict:
    return {
        "source": "disabled",
        "course_key": None,
        "status": "active",
        "progress_percent": 0,
        "current_module_key": None,
        "current_topic_key": None,
        "current_legacy_topic_id": None,
        "error": None,
    }


# ── Dashboard: modular position available ─────────────────────────────────────

def test_dashboard_shows_current_topic_when_modular_progress_available():
    session_id = "pos-dash-available"
    _put_session(session_id=session_id, current_week=2)

    with patch.object(
        dashboard_module,
        "_dashboard_db_summaries",
        return_value=(_enrollment_result_disabled(), _modular_summary_available()),
    ):
        response = client.get("/dashboard")

    assert response.status_code == 200
    visible = _visible_text(response.text)
    assert "Current Focus" in visible
    assert "topic-alpha" in visible


def test_dashboard_shows_next_topic_when_available():
    session_id = "pos-dash-next"
    _put_session(session_id=session_id, current_week=2)

    with patch.object(
        dashboard_module,
        "_dashboard_db_summaries",
        return_value=(_enrollment_result_disabled(), _modular_summary_available()),
    ):
        response = client.get("/dashboard")

    assert response.status_code == 200
    # topic-alpha is in_progress → both current and next will point to it
    # topic-beta is not_started (next after current completes)
    # position logic: pick_next_topic → first non-completed = topic-alpha (in_progress counts)
    assert "topic-alpha" in response.text


def test_dashboard_shows_current_focus_section_when_modular_available():
    session_id = "pos-dash-focus-section"
    _put_session(session_id=session_id, current_week=3)

    with patch.object(
        dashboard_module,
        "_dashboard_db_summaries",
        return_value=(_enrollment_result_disabled(), _modular_summary_available()),
    ):
        response = client.get("/dashboard")

    assert response.status_code == 200
    assert "Current Focus" in response.text


# ── Dashboard: modular progress unavailable — fallback to Module N ─────────────

def test_dashboard_falls_back_to_module_n_when_modular_unavailable():
    session_id = "pos-dash-fallback"
    _put_session(session_id=session_id, current_week=3)

    with patch.object(
        dashboard_module,
        "_dashboard_db_summaries",
        return_value=(_enrollment_result_disabled(), _modular_summary_unavailable()),
    ):
        response = client.get("/dashboard")

    assert response.status_code == 200
    visible = _visible_text(response.text)
    # Fallback: "Current module" label should show "Module 3"
    assert "Module 3" in visible


def test_dashboard_falls_back_to_module_n_when_db_fails():
    session_id = "pos-dash-db-fail"
    _put_session(session_id=session_id, current_week=4)

    with patch.object(
        dashboard_module,
        "_open_db_connection",
        side_effect=RuntimeError("connection refused"),
    ):
        response = client.get("/dashboard")

    assert response.status_code == 200
    visible = _visible_text(response.text)
    assert "Module 4" in visible


def test_dashboard_does_not_show_current_focus_when_no_session():
    app_module._sessions.clear()

    with patch.object(
        dashboard_module,
        "_open_db_connection",
        side_effect=RuntimeError("no db"),
    ):
        response = client.get("/dashboard")

    assert response.status_code == 200
    # No session → position_summary has available=False and no module label,
    # so the Current Focus card content must not be visible to the learner.
    visible = _visible_text(response.text)
    assert "Current Focus" not in visible


# ── Dashboard: no learner-facing DB error ─────────────────────────────────────

def test_dashboard_no_learner_facing_db_error():
    session_id = "pos-dash-no-error"
    _put_session(session_id=session_id)

    with patch.object(
        dashboard_module,
        "_open_db_connection",
        side_effect=RuntimeError("postgres://user:secret@localhost/db"),
    ):
        response = client.get("/dashboard")

    assert response.status_code == 200
    assert "postgres://" not in response.text
    assert "secret" not in response.text


# ── Dashboard: existing cards still render ────────────────────────────────────

def test_existing_dashboard_stats_still_render():
    session_id = "pos-dash-stats"
    _put_session(session_id=session_id, current_week=2)

    with patch.object(
        dashboard_module,
        "_open_db_connection",
        side_effect=RuntimeError("no db"),
    ):
        response = client.get("/dashboard")

    assert response.status_code == 200
    assert "Sessions" in response.text
    assert "Quizzes taken" in response.text
    assert "Topics mastered" in response.text


def test_existing_dashboard_learning_summary_still_renders():
    session_id = "pos-dash-learning-summary"
    _put_session(session_id=session_id, current_week=2)

    with patch.object(
        dashboard_module,
        "_open_db_connection",
        side_effect=RuntimeError("no db"),
    ):
        response = client.get("/dashboard")

    assert response.status_code == 200
    assert "Your Learning Summary" in response.text
    assert "Browse Module Topics" in response.text


def test_existing_dashboard_resume_card_still_renders():
    session_id = "pos-dash-resume"
    _put_session(session_id=session_id, current_week=2)

    with patch.object(
        dashboard_module,
        "_open_db_connection",
        side_effect=RuntimeError("no db"),
    ):
        response = client.get("/dashboard")

    assert response.status_code == 200
    assert "Continue Learning" in response.text
    assert "Resume" in response.text


# ── Todos: modular context display ────────────────────────────────────────────

def test_todos_display_module_key_from_modular_progress(monkeypatch):
    monkeypatch.delenv("AI2_TODOS_DB_READS_ENABLED", raising=False)
    session_id = _start_session(week=2)

    modular = _modular_summary_available(
        current_module_key="module-02",
        current_topic_key="topic-alpha",
    )
    monkeypatch.setattr(
        deps_module,
        "read_modular_progress_summary_safely",
        lambda session, *, user_id, session_id: modular,
    )

    response = client.get(f"/todos/{session_id}")

    assert response.status_code == 200
    visible = _visible_text(response.text)
    assert "module-02" in visible


def test_todos_display_topic_key_from_modular_progress(monkeypatch):
    monkeypatch.delenv("AI2_TODOS_DB_READS_ENABLED", raising=False)
    session_id = _start_session(week=2)

    modular = _modular_summary_available(
        current_module_key="module-01",
        current_topic_key="topic-alpha",
    )
    monkeypatch.setattr(
        deps_module,
        "read_modular_progress_summary_safely",
        lambda session, *, user_id, session_id: modular,
    )

    response = client.get(f"/todos/{session_id}")

    assert response.status_code == 200
    visible = _visible_text(response.text)
    assert "topic-alpha" in visible


def test_todos_fall_back_to_module_n_when_modular_unavailable(monkeypatch):
    monkeypatch.delenv("AI2_TODOS_DB_READS_ENABLED", raising=False)
    session_id = _start_session(week=3)

    monkeypatch.setattr(
        deps_module,
        "read_modular_progress_summary_safely",
        lambda session, *, user_id, session_id: _modular_summary_unavailable(),
    )

    response = client.get(f"/todos/{session_id}")

    assert response.status_code == 200
    visible = _visible_text(response.text)
    assert "Module 3" in visible


def test_todos_no_week_wording_in_visible_text(monkeypatch):
    monkeypatch.delenv("AI2_TODOS_DB_READS_ENABLED", raising=False)
    session_id = _start_session(week=2)

    monkeypatch.setattr(
        deps_module,
        "read_modular_progress_summary_safely",
        lambda session, *, user_id, session_id: _modular_summary_unavailable(),
    )

    response = client.get(f"/todos/{session_id}")
    visible = _visible_text(response.text)

    assert response.status_code == 200
    assert "Week" not in visible
    assert "weekly" not in visible.lower()
    assert "Learning Path Tasks" in visible


# ── Todos: existing behavior ──────────────────────────────────────────────────

def test_existing_todos_still_render(monkeypatch):
    monkeypatch.delenv("AI2_TODOS_DB_READS_ENABLED", raising=False)
    monkeypatch.delenv("AI2_DB_WRITE_THROUGH_ENABLED", raising=False)
    session_id = _start_session()

    client.post("/todos/create", json={
        "session_id": session_id, "title": "Daily task", "todo_type": "daily",
    })
    client.post("/todos/create", json={
        "session_id": session_id, "title": "Path task", "todo_type": "weekly",
    })

    monkeypatch.setattr(
        deps_module,
        "read_modular_progress_summary_safely",
        lambda session, *, user_id, session_id: _modular_summary_unavailable(),
    )
    response = client.get(f"/todos/{session_id}")

    assert response.status_code == 200
    assert "Daily task" in response.text
    assert "Path task" in response.text
    assert "My Learning Planner" in response.text


def test_weekly_todo_type_still_compatible(monkeypatch):
    monkeypatch.delenv("AI2_TODOS_DB_READS_ENABLED", raising=False)
    monkeypatch.delenv("AI2_DB_WRITE_THROUGH_ENABLED", raising=False)
    session_id = _start_session()

    created = client.post("/todos/create", json={
        "session_id": session_id,
        "title": "Module task",
        "todo_type": "weekly",
    })
    assert created.status_code == 200
    assert created.json()["todo"]["todo_type"] == "weekly"


def test_todos_no_learner_facing_db_error(monkeypatch):
    monkeypatch.delenv("AI2_TODOS_DB_READS_ENABLED", raising=False)
    session_id = _start_session()
    monkeypatch.setenv("AI2_TODOS_DB_READS_ENABLED", "1")

    with patch("database.pool.get_conn", side_effect=RuntimeError("private token=abc")):
        response = client.get(f"/todos/{session_id}")

    assert response.status_code == 200
    assert "private token=abc" not in response.text
    assert "abc" not in response.text


# ── Invariants ────────────────────────────────────────────────────────────────

def test_current_week_remains_supported_internally():
    session = _put_session(session_id="pos-current-week", current_week=5)

    with patch.object(
        dashboard_module,
        "_open_db_connection",
        side_effect=RuntimeError("no db"),
    ):
        response = client.get("/dashboard")

    assert response.status_code == 200
    assert session.current_week == 5
    assert session.to_dict()["current_week"] == 5


def test_weeks_and_role_tracks_not_mutated():
    _put_session(session_id="pos-curriculum-const")
    weeks_before = deepcopy(WEEKS)
    role_tracks_before = deepcopy(ROLE_TRACKS)

    with patch.object(
        dashboard_module,
        "_open_db_connection",
        side_effect=RuntimeError("no db"),
    ):
        response = client.get("/dashboard")

    assert response.status_code == 200
    assert WEEKS == weeks_before
    assert ROLE_TRACKS == role_tracks_before


def test_no_claude_call_made_on_dashboard():
    _put_session(session_id="pos-no-claude")

    with patch.object(
        app_module,
        "_make_client",
        side_effect=AssertionError("Claude must not be called"),
    ) as make_client:
        with patch.object(
            dashboard_module,
            "_open_db_connection",
            side_effect=RuntimeError("no db"),
        ):
            response = client.get("/dashboard")

    assert response.status_code == 200
    make_client.assert_not_called()


def test_no_claude_call_made_on_todos(monkeypatch):
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


def test_no_seed_script_called_on_dashboard():
    _put_session(session_id="pos-no-seed")

    with patch("runpy.run_module", side_effect=AssertionError("seed must not run")) as run_mod:
        with patch.object(
            dashboard_module,
            "_open_db_connection",
            side_effect=RuntimeError("no db"),
        ):
            response = client.get("/dashboard")

    assert response.status_code == 200
    run_mod.assert_not_called()


def test_no_seed_script_called_on_todos(monkeypatch):
    monkeypatch.delenv("AI2_TODOS_DB_READS_ENABLED", raising=False)
    session_id = _start_session()

    with patch("runpy.run_module", side_effect=AssertionError("seed must not run")) as run_mod:
        response = client.get(f"/todos/{session_id}")

    assert response.status_code == 200
    run_mod.assert_not_called()


def test_route_urls_remain_unchanged():
    routes = {
        (route.path, ",".join(sorted(getattr(route, "methods", set()) or [])))
        for route in app_module.app.routes
        if hasattr(route, "methods")
    }

    assert ("/dashboard", "GET") in routes
    assert ("/todos/{session_id}", "GET") in routes
    assert ("/todos/create", "POST") in routes
    assert ("/todos/status", "POST") in routes
