"""Tests for module wording in chat/session learner context."""

from __future__ import annotations

import os
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

os.environ["AI2_TEST_MODE"] = "1"
os.environ["ANTHROPIC_API_KEY"] = "test-key"

from fastapi.testclient import TestClient

import app as app_module
from config import CareerTrack
from context.session import SessionContext
from curriculum.syllabus import ROLE_TRACKS, WEEKS


client = TestClient(app_module.app)


def test_learner_prompt_context_no_longer_says_current_week():
    session = SessionContext(track=CareerTrack.AI_PM, current_week=2)

    context_text = session.as_prompt_context()
    summary_text = session.progress_summary()

    assert "Current week" not in context_text
    assert "Current week" not in summary_text
    assert "Week:" not in context_text
    assert "week progress" not in context_text.lower()


def test_learner_prompt_context_says_current_module():
    session = SessionContext(track=CareerTrack.AI_PM, current_week=2)

    context_text = session.as_prompt_context()
    summary_text = session.progress_summary()

    assert "Current module: 2" in context_text
    assert "Current module: 2" in summary_text
    assert "Current learning path: aipm" in context_text


def test_current_week_still_exists_internally():
    session = SessionContext(track=CareerTrack.EVALS, current_week=4)

    assert session.current_week == 4
    assert hasattr(session, "advance_week")


def test_session_serialization_preserves_current_week():
    session = SessionContext(track=CareerTrack.CONTEXT_ENGINEER, current_week=3)
    session.add_goal("Ship a context engineering portfolio project")

    restored = SessionContext.from_dict(session.to_dict())

    assert restored.current_week == 3
    assert restored.to_dict()["current_week"] == 3
    assert restored.goals == ["Ship a context engineering portfolio project"]


def test_orchestrator_imports_were_not_changed_for_enrollment_context():
    source = Path("orchestrator.py").read_text(encoding="utf-8")

    assert "learner_course_enrollment_service" not in source
    assert "get_active_course_enrollment_with_fallback" not in source
    assert "database.pool" not in source


def test_context_building_opens_no_db_connection():
    session = SessionContext(track=CareerTrack.AI_PM, current_week=2)

    with patch("database.pool._connect", side_effect=AssertionError("DB must not open")):
        with patch.object(app_module, "get_conn", side_effect=AssertionError("DB must not open")):
            with patch.object(
                app_module,
                "_open_db_connection",
                side_effect=AssertionError("DB must not open"),
                create=True,
            ):
                assert "Current module" in session.as_prompt_context()
                assert "Current module" in session.progress_summary()


def test_chat_route_still_works_without_db_or_claude_calls():
    app_module._sessions.clear()

    with patch.object(app_module, "_make_client", side_effect=AssertionError("Claude must not be called")) as make_client:
        with patch.object(app_module, "get_conn", side_effect=AssertionError("DB must not open")) as get_conn:
            with patch.object(
                app_module,
                "_open_db_connection",
                side_effect=AssertionError("DB must not open"),
                create=True,
            ) as open_db:
                start = client.post("/session/start", json={"track": "aipm", "week": 2})
                assert start.status_code == 200, start.text
                session_id = start.json()["session_id"]

                response = client.post(
                    "/chat",
                    json={
                        "session_id": session_id,
                        "message": "Explain attention in transformers",
                    },
                )

    assert response.status_code == 200, response.text
    assert response.json()["agent_used"] == "learning_coach"
    assert "response" in response.json()
    make_client.assert_not_called()
    get_conn.assert_not_called()
    open_db.assert_not_called()


def test_weeks_and_role_tracks_are_not_mutated():
    weeks_before = deepcopy(WEEKS)
    role_tracks_before = deepcopy(ROLE_TRACKS)
    session = SessionContext(track=CareerTrack.AI_PM, current_week=2)

    session.as_prompt_context()
    session.progress_summary()

    assert WEEKS == weeks_before
    assert ROLE_TRACKS == role_tracks_before


def test_no_seed_script_is_called_by_context_or_chat():
    app_module._sessions.clear()
    session = SessionContext(track=CareerTrack.AI_PM, current_week=2)

    with patch("runpy.run_module", side_effect=AssertionError("seed scripts must not run")) as run_module:
        assert "Current module" in session.as_prompt_context()
        start = client.post("/session/start", json={"track": "aipm", "week": 2})
        assert start.status_code == 200, start.text

    run_module.assert_not_called()
