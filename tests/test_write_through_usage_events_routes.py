"""Tests for usage_events write-through wiring in mutation routes.

These tests avoid real DB connections and keep SessionContext as the runtime
source of truth.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

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


def test_content_generation_flag_off_no_usage_event_db_connection(monkeypatch):
    monkeypatch.delenv("AI2_DB_WRITE_THROUGH_ENABLED", raising=False)
    session_id = _start_session()
    topic = _first_topic()

    with patch("database.pool._connect", side_effect=AssertionError("DB must not be opened")) as connect, \
         patch(
             "services.write_through_usage_events_service.maybe_write_usage_events_for_topic",
             side_effect=AssertionError("usage-events service must not be called"),
         ) as service:
        response = _generate_content(session_id, topic.topic_id)

    assert response.status_code == 200
    assert set(response.json().keys()) == {
        "topic_id",
        "content",
        "generated_topic_content",
    }
    connect.assert_not_called()
    service.assert_not_called()


def test_content_generation_flag_on_attempts_usage_event_write_through(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    session_id = _start_session()
    topic = _first_topic()

    with patch("routes.deps.write_through_topic_progress"), \
         patch("routes.deps.write_through_generated_learning_state"), \
         patch("routes.deps.write_through_usage_events") as write_through:
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


def test_content_generation_usage_write_through_failure_still_succeeds(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    session_id = _start_session()
    topic = _first_topic()

    with patch("database.pool._connect", side_effect=RuntimeError("DB down")):
        response = _generate_content(session_id, topic.topic_id)

    assert response.status_code == 200
    data = response.json()
    assert data["topic_id"] == topic.topic_id
    assert data["content"]
    assert "generated_topic_content" in data


def test_practice_generation_flag_on_attempts_usage_event_write_through(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    session_id = _start_session()
    topic = _first_topic()

    with patch("routes.deps.write_through_topic_progress"), \
         patch("routes.deps.write_through_generated_learning_state"), \
         patch("routes.deps.write_through_usage_events") as write_through:
        response = _generate_practice(session_id, topic.topic_id)

    assert response.status_code == 200
    assert set(response.json().keys()) == {
        "topic_id",
        "practice_type",
        "content",
        "generated_practice",
    }
    write_through.assert_called_once()
    assert write_through.call_args.kwargs["legacy_topic_id"] == topic.topic_id


def test_quiz_evaluation_flag_on_attempts_usage_event_write_through(monkeypatch):
    monkeypatch.delenv("AI2_DB_WRITE_THROUGH_ENABLED", raising=False)
    session_id = _start_session()
    topic = _first_topic()
    assert _quiz_submit(session_id, topic.topic_id).status_code == 200

    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    with patch("routes.deps.write_through_topic_progress"), \
         patch("routes.deps.write_through_generated_learning_state"), \
         patch("routes.deps.write_through_usage_events") as write_through:
        response = _quiz_evaluate(session_id, topic.topic_id)

    assert response.status_code == 200
    assert "quiz_submission" in response.json()
    write_through.assert_called_once()
    assert write_through.call_args.kwargs["session_id"] == session_id
    assert write_through.call_args.kwargs["legacy_topic_id"] == topic.topic_id


def test_portfolio_feedback_flag_on_attempts_usage_event_write_through(monkeypatch):
    monkeypatch.delenv("AI2_DB_WRITE_THROUGH_ENABLED", raising=False)
    session_id = _start_session()
    topic = _first_topic()
    assert _portfolio_submit(session_id, topic.topic_id).status_code == 200

    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    with patch("routes.deps.write_through_topic_progress"), \
         patch("routes.deps.write_through_generated_learning_state"), \
         patch("routes.deps.write_through_usage_events") as write_through:
        response = _portfolio_feedback(session_id, topic.topic_id)

    assert response.status_code == 200
    assert "portfolio_submission" in response.json()
    write_through.assert_called_once()
    assert write_through.call_args.kwargs["legacy_topic_id"] == topic.topic_id


def test_interview_feedback_flag_on_attempts_usage_event_write_through(monkeypatch):
    monkeypatch.delenv("AI2_DB_WRITE_THROUGH_ENABLED", raising=False)
    session_id = _start_session()
    topic = _first_topic()
    assert _interview_submit(session_id, topic.topic_id).status_code == 200

    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    with patch("routes.deps.write_through_topic_progress"), \
         patch("routes.deps.write_through_generated_learning_state"), \
         patch("routes.deps.write_through_usage_events") as write_through:
        response = _interview_feedback(session_id, topic.topic_id)

    assert response.status_code == 200
    assert "interview_submission" in response.json()
    write_through.assert_called_once()
    assert write_through.call_args.kwargs["legacy_topic_id"] == topic.topic_id


def test_response_payloads_remain_unchanged_when_usage_write_through_is_patched(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    session_id = _start_session()
    topic = _first_topic()

    with patch("routes.deps.write_through_topic_progress"), \
         patch("routes.deps.write_through_generated_learning_state"), \
         patch("routes.deps.write_through_usage_events"):
        content_response = _generate_content(session_id, topic.topic_id)
        practice_response = _generate_practice(session_id, topic.topic_id)

    assert set(content_response.json().keys()) == {
        "topic_id",
        "content",
        "generated_topic_content",
    }
    assert set(practice_response.json().keys()) == {
        "topic_id",
        "practice_type",
        "content",
        "generated_practice",
    }


def test_save_session_happens_before_usage_event_write_through(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    session_id = _start_session()
    topic = _first_topic()
    calls: list[str] = []

    def fake_save_session(_session_id, _session):
        calls.append("save_session")

    def fake_usage_write_through(_session, **_kwargs):
        calls.append("usage_write_through")

    with patch("routes.deps.save_session", side_effect=fake_save_session), \
         patch("routes.deps.write_through_topic_progress"), \
         patch("routes.deps.write_through_generated_learning_state"), \
         patch("routes.deps.write_through_usage_events", side_effect=fake_usage_write_through):
        response = _generate_content(session_id, topic.topic_id)

    assert response.status_code == 200
    assert calls == ["save_session", "usage_write_through"]


def test_no_usage_events_db_reads_are_introduced():
    source = "\n".join([
        Path("routes/deps.py").read_text(encoding="utf-8"),
        Path("routes/topics.py").read_text(encoding="utf-8"),
        Path("routes/submissions.py").read_text(encoding="utf-8"),
    ])
    forbidden = [
        "list_usage_events_for_session",
        "usage_event_summary_for_session",
        "SELECT * FROM usage_events",
        "FROM usage_events",
    ]
    for name in forbidden:
        assert name not in source


def test_learner_facing_route_urls_remain_registered():
    paths = {route.path for route in app.routes}
    assert {
        "/topic/content/generate",
        "/topic/practice/generate",
        "/quiz/evaluate",
        "/portfolio/feedback",
        "/interview/feedback",
    }.issubset(paths)
