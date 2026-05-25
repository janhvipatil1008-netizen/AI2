"""Tests for simple beta onboarding flow."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

os.environ["AI2_TEST_MODE"] = "1"
os.environ["ANTHROPIC_API_KEY"] = "test-key"

from fastapi.testclient import TestClient

from app import app
from config import CareerTrack
from context.session import SessionContext


client = TestClient(app)


def _start_session() -> str:
    response = client.post("/session/start", json={"track": "aipm", "week": 1})
    assert response.status_code == 200, response.text
    return response.json()["session_id"]


def _valid_form(session_id: str, **overrides) -> dict:
    data = {
        "session_id": session_id,
        "goal": "aipm",
        "level": "beginner",
        "weekly_time": "five_hours",
    }
    data.update(overrides)
    return data


def test_session_context_onboarding_defaults_empty_not_completed():
    session = SessionContext(track=CareerTrack.AI_PM)

    assert session.get_onboarding_profile() == {}
    assert session.has_completed_onboarding() is False


def test_save_onboarding_profile_stores_fields():
    session = SessionContext(track=CareerTrack.AI_PM)
    profile = session.save_onboarding_profile("aipm", "beginner", "five_hours")

    assert profile["goal"] == "aipm"
    assert profile["level"] == "beginner"
    assert profile["weekly_time"] == "five_hours"
    assert profile["recommended_track"] == "aipm"
    assert profile["completed_at"]
    assert session.has_completed_onboarding() is True


def test_ai_builder_recommends_closest_existing_track():
    session = SessionContext(track=CareerTrack.AI_PM)
    profile = session.save_onboarding_profile("ai_builder", "building_projects", "ten_hours")

    assert profile["recommended_track"] == "context"
    assert "closest available track" in profile["recommendation_note"]


def test_invalid_goal_raises_validation_error():
    session = SessionContext(track=CareerTrack.AI_PM)

    try:
        session.save_onboarding_profile("bad_goal", "beginner", "five_hours")
    except ValueError as exc:
        assert "Invalid onboarding goal" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError")


def test_invalid_level_raises_validation_error():
    session = SessionContext(track=CareerTrack.AI_PM)

    try:
        session.save_onboarding_profile("aipm", "expert", "five_hours")
    except ValueError as exc:
        assert "Invalid onboarding level" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError")


def test_invalid_weekly_time_raises_validation_error():
    session = SessionContext(track=CareerTrack.AI_PM)

    try:
        session.save_onboarding_profile("aipm", "beginner", "all_day")
    except ValueError as exc:
        assert "Invalid onboarding weekly_time" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError")


def test_get_onboarding_renders_form():
    session_id = _start_session()
    response = client.get(f"/onboarding/{session_id}")

    assert response.status_code == 200
    assert "Set up your learning path" in response.text
    assert "This helps AI2 recommend where to start." in response.text
    assert "Learning goal" in response.text
    assert "Current level" in response.text
    assert "Time available" in response.text


def test_post_onboarding_save_saves_valid_profile():
    session_id = _start_session()
    with patch("routes.deps.save_session") as save_session:
        response = client.post(
            "/onboarding/save",
            data=_valid_form(session_id, goal="interview_prep", level="job_ready", weekly_time="two_hours"),
            follow_redirects=False,
        )

    assert response.status_code == 302
    save_session.assert_called_once()
    saved_session = save_session.call_args.args[1]
    profile = saved_session.get_onboarding_profile()
    assert profile["goal"] == "interview_prep"
    assert profile["level"] == "job_ready"
    assert profile["weekly_time"] == "two_hours"
    assert profile["recommended_track"] == "aipm"


def test_post_redirects_safely_after_save():
    session_id = _start_session()
    response = client.post(
        "/onboarding/save",
        data=_valid_form(session_id),
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"] == f"/topics/{session_id}"


def test_invalid_post_returns_friendly_error():
    session_id = _start_session()
    response = client.post(
        "/onboarding/save",
        data=_valid_form(session_id, goal="not-real"),
    )

    assert response.status_code == 422
    assert "Invalid onboarding goal" in response.text
    assert "Set up your learning path" in response.text


def test_onboarding_persists_through_to_dict_from_dict():
    session = SessionContext(track=CareerTrack.AI_PM)
    session.save_onboarding_profile("aipm", "some_experience", "ten_hours")

    restored = SessionContext.from_dict(session.to_dict())

    assert restored.get_onboarding_profile()["goal"] == "aipm"
    assert restored.get_onboarding_profile()["level"] == "some_experience"
    assert restored.get_onboarding_profile()["weekly_time"] == "ten_hours"
    assert restored.has_completed_onboarding() is True


def test_existing_session_and_dashboard_routes_still_work():
    session_id = _start_session()
    dashboard = client.get("/dashboard")

    assert dashboard.status_code == 200
    assert "Your adaptive learning dashboard" in dashboard.text
    assert f"/onboarding/{session_id}" in dashboard.text


def test_no_claude_call_is_made():
    session_id = _start_session()
    with patch("app._make_client", side_effect=AssertionError("Claude must not be called")) as make_client:
        response = client.post(
            "/onboarding/save",
            data=_valid_form(session_id),
            follow_redirects=False,
        )

    assert response.status_code == 302
    make_client.assert_not_called()


def test_no_usage_limit_enforcement_is_triggered():
    session_id = _start_session()
    with patch("routes.deps.build_limit_enforcer", side_effect=AssertionError("usage limits not part of onboarding")) as limiter:
        response = client.post(
            "/onboarding/save",
            data=_valid_form(session_id),
            follow_redirects=False,
        )

    assert response.status_code == 302
    limiter.assert_not_called()


def test_no_db_connection_required_for_onboarding_get_or_save():
    session_id = _start_session()
    with patch("app.get_conn", side_effect=AssertionError("DB must not be opened")) as get_conn:
        get_response = client.get(f"/onboarding/{session_id}")
        post_response = client.post(
            "/onboarding/save",
            data=_valid_form(session_id),
            follow_redirects=False,
        )

    assert get_response.status_code == 200
    assert post_response.status_code == 302
    get_conn.assert_not_called()


def test_session_ownership_helper_is_used_on_get():
    session = SessionContext(track=CareerTrack.AI_PM)
    loader = MagicMock(return_value={"session": session})
    with patch("routes.deps.get_session_data", loader):
        response = client.get("/onboarding/session-123")

    assert response.status_code == 200
    loader.assert_called_once_with("session-123", "")


def test_session_ownership_helper_is_used_on_post():
    session = SessionContext(track=CareerTrack.AI_PM)
    loader = MagicMock(return_value={"session": session})
    with patch("routes.deps.get_session_data", loader), patch("routes.deps.save_session"):
        response = client.post(
            "/onboarding/save",
            data=_valid_form("session-123"),
            follow_redirects=False,
        )

    assert response.status_code == 302
    loader.assert_called_once_with("session-123", "")
