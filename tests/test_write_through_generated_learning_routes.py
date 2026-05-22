"""Tests for generated-learning write-through wiring in mutation routes.

All tests avoid real DB connections and keep SessionContext as the runtime
source of truth.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

os.environ["AI2_TEST_MODE"] = "1"
os.environ["ANTHROPIC_API_KEY"] = "test-key"

from app import app
from curriculum.topics import get_topics_for_week

client = TestClient(app)


def _start_session(track: str = "aipm", week: int = 1) -> str:
    response = client.post("/session/start", json={"track": track, "week": week})
    assert response.status_code == 200, response.text
    return response.json()["session_id"]


def _first_topic():
    return get_topics_for_week("aipm", 1)[0]


def _generate_content(session_id: str, topic_id: str):
    return client.post("/topic/content/generate", json={
        "session_id": session_id,
        "topic_id": topic_id,
        "refresh": False,
    })


def _generate_practice(session_id: str, topic_id: str):
    return client.post("/topic/practice/generate", json={
        "session_id": session_id,
        "topic_id": topic_id,
        "practice_type": "quiz",
        "refresh": False,
    })


def _save_notes(session_id: str, topic_id: str):
    return client.post("/topic/notes", json={
        "session_id": session_id,
        "topic_id": topic_id,
        "reflection": "Useful reflection",
        "confusions": "",
        "application_idea": "",
    })


def _quiz_submit(session_id: str, topic_id: str):
    return client.post("/quiz/submit", json={
        "session_id": session_id,
        "topic_id": topic_id,
        "answers": "Q1: A, Q2: B",
    })


def _quiz_evaluate(session_id: str, topic_id: str):
    return client.post("/quiz/evaluate", json={
        "session_id": session_id,
        "topic_id": topic_id,
        "refresh": False,
    })


def _portfolio_submit(session_id: str, topic_id: str):
    return client.post("/portfolio/submit", json={
        "session_id": session_id,
        "topic_id": topic_id,
        "submission": "Portfolio submission",
    })


def _portfolio_feedback(session_id: str, topic_id: str):
    return client.post("/portfolio/feedback", json={
        "session_id": session_id,
        "topic_id": topic_id,
        "refresh": False,
    })


def _interview_submit(session_id: str, topic_id: str):
    return client.post("/interview/submit", json={
        "session_id": session_id,
        "topic_id": topic_id,
        "answer": "Interview answer",
    })


def _interview_feedback(session_id: str, topic_id: str):
    return client.post("/interview/feedback", json={
        "session_id": session_id,
        "topic_id": topic_id,
        "refresh": False,
    })


def test_generated_content_flag_off_no_db_connect_and_no_service_call(monkeypatch):
    monkeypatch.delenv("AI2_DB_WRITE_THROUGH_ENABLED", raising=False)
    session_id = _start_session()
    topic = _first_topic()

    with patch("database.pool._connect", side_effect=AssertionError("DB must not be opened")) as connect, \
         patch(
             "services.write_through_generated_learning_service.maybe_write_generated_learning_state",
             side_effect=AssertionError("generated-learning service must not be called"),
         ) as service:
        response = _generate_content(session_id, topic.topic_id)

    assert response.status_code == 200
    assert response.json()["topic_id"] == topic.topic_id
    connect.assert_not_called()
    service.assert_not_called()


def test_generated_content_flag_on_attempts_generated_learning_write_through(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    session_id = _start_session()
    topic = _first_topic()

    with patch("routes.deps.write_through_topic_progress"), \
         patch("routes.deps.write_through_generated_learning_state") as write_through:
        response = _generate_content(session_id, topic.topic_id)

    assert response.status_code == 200
    assert set(response.json().keys()) == {
        "topic_id",
        "content",
        "generated_topic_content",
    }
    write_through.assert_called_once()
    assert write_through.call_args.kwargs["session_id"] == session_id
    assert write_through.call_args.kwargs["legacy_topic_id"] == topic.topic_id


def test_generated_content_write_through_failure_does_not_break_route(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    session_id = _start_session()
    topic = _first_topic()

    with patch("routes.deps.write_through_topic_progress"), \
         patch("database.pool._connect", side_effect=RuntimeError("DB down")):
        response = _generate_content(session_id, topic.topic_id)

    assert response.status_code == 200
    data = response.json()
    assert data["topic_id"] == topic.topic_id
    assert data["content"] != ""
    assert "generated_topic_content" in data


def test_save_session_happens_before_generated_learning_write_through(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    session_id = _start_session()
    topic = _first_topic()
    events: list[str] = []

    def fake_save_session(_session_id, _session):
        events.append("save_session")

    def fake_write_through(_session, **_kwargs):
        events.append("generated_write_through")

    with patch("routes.deps.save_session", side_effect=fake_save_session), \
         patch("routes.deps.write_through_topic_progress"), \
         patch("routes.deps.write_through_generated_learning_state", side_effect=fake_write_through):
        response = _generate_content(session_id, topic.topic_id)

    assert response.status_code == 200
    assert events == ["save_session", "generated_write_through"]


@pytest.mark.parametrize(
    ("call_route", "expected_keys"),
    [
        (_generate_practice, {"topic_id", "practice_type", "content", "generated_practice"}),
        (_save_notes, {"topic_id", "notes", "topic_progress", "completion_percent"}),
    ],
)
def test_topic_mutation_routes_attempt_generated_learning_write_through(
    monkeypatch,
    call_route,
    expected_keys,
):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    session_id = _start_session()
    topic = _first_topic()

    with patch("routes.deps.write_through_topic_progress"), \
         patch("routes.deps.write_through_generated_learning_state") as write_through:
        response = call_route(session_id, topic.topic_id)

    assert response.status_code == 200
    assert set(response.json().keys()) == expected_keys
    write_through.assert_called_once()
    assert write_through.call_args.kwargs["legacy_topic_id"] == topic.topic_id


@pytest.mark.parametrize(
    ("prepare", "call_route", "expected_payload_key"),
    [
        (None, _quiz_submit, "quiz_submission"),
        (_quiz_submit, _quiz_evaluate, "quiz_submission"),
        (None, _portfolio_submit, "portfolio_submission"),
        (_portfolio_submit, _portfolio_feedback, "portfolio_submission"),
        (None, _interview_submit, "interview_submission"),
        (_interview_submit, _interview_feedback, "interview_submission"),
    ],
)
def test_submission_routes_attempt_generated_learning_write_through(
    monkeypatch,
    prepare,
    call_route,
    expected_payload_key,
):
    monkeypatch.delenv("AI2_DB_WRITE_THROUGH_ENABLED", raising=False)
    session_id = _start_session()
    topic = _first_topic()
    if prepare is not None:
        prep_response = prepare(session_id, topic.topic_id)
        assert prep_response.status_code == 200

    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    with patch("routes.deps.write_through_topic_progress"), \
         patch("routes.deps.write_through_generated_learning_state") as write_through:
        response = call_route(session_id, topic.topic_id)

    assert response.status_code == 200
    data = response.json()
    assert data["topic_id"] == topic.topic_id
    assert expected_payload_key in data
    assert "topic_progress" in data
    assert "completion_percent" in data
    write_through.assert_called_once()
    assert write_through.call_args.kwargs["session_id"] == session_id
    assert write_through.call_args.kwargs["legacy_topic_id"] == topic.topic_id


def test_no_generated_learning_db_read_helpers_are_imported_by_routes():
    topics_source = Path("routes/topics.py").read_text(encoding="utf-8")
    submissions_source = Path("routes/submissions.py").read_text(encoding="utf-8")
    route_source = topics_source + "\n" + submissions_source

    forbidden = [
        "get_generated_topic_content_by_legacy_id",
        "get_generated_topic_practice_by_legacy_id",
        "get_quiz_submission_by_legacy_id",
        "get_portfolio_submission_by_legacy_id",
        "get_interview_submission_by_legacy_id",
        "get_topic_notes_by_legacy_id",
        "learner_state_read_service",
        "curriculum_read_service",
    ]
    for name in forbidden:
        assert name not in route_source


def test_learner_facing_route_urls_remain_registered():
    paths = {route.path for route in app.routes}
    assert {
        "/topic/notes",
        "/topic/content/generate",
        "/topic/practice/generate",
        "/quiz/submit",
        "/quiz/evaluate",
        "/portfolio/submit",
        "/portfolio/feedback",
        "/interview/submit",
        "/interview/feedback",
    }.issubset(paths)
