"""Tests for the optional learning outcome section on topic detail pages."""

from __future__ import annotations

import os
from unittest.mock import patch

os.environ["AI2_TEST_MODE"] = "1"
os.environ["ANTHROPIC_API_KEY"] = "test-key"

from fastapi.testclient import TestClient

from app import app
from curriculum.topics import get_topics_for_week


client = TestClient(app)

PRIVATE_BASELINE = "private baseline answer should not be rendered"
PRIVATE_POST = "private post answer should not be rendered"
SECRET_ERROR = "postgresql://user:secret@host/db ANTHROPIC_API_KEY=sk-secret"


def _start_session() -> str:
    response = client.post("/session/start", json={"track": "aipm", "week": 1})
    assert response.status_code == 200, response.text
    return response.json()["session_id"]


def _first_topic():
    return get_topics_for_week("aipm", 1)[0]


def _summary(**overrides):
    summary = {
        "has_baseline": True,
        "has_post": True,
        "baseline_score": 3,
        "post_score": 8,
        "improvement_delta": 5,
        "status": "improved",
    }
    summary.update(overrides)
    return summary


def test_topic_detail_page_renders_learning_outcome_section():
    session_id = _start_session()
    topic = _first_topic()

    response = client.get(f"/topic/{session_id}/{topic.topic_id}")

    assert response.status_code == 200
    assert "Check your learning improvement" in response.text
    assert 'id="learning-outcome"' in response.text


def test_baseline_form_exists_and_submits_to_existing_endpoint():
    session_id = _start_session()
    topic = _first_topic()

    response = client.get(f"/topic/{session_id}/{topic.topic_id}")
    html = response.text

    assert response.status_code == 200
    assert 'method="post" action="/topic/outcome/baseline"' in html
    assert 'name="baseline_answer"' in html
    assert 'name="baseline_score"' in html
    assert 'name="session_id" value="' in html
    assert 'name="topic_id" value="' in html


def test_post_topic_form_exists_and_submits_to_existing_endpoint():
    session_id = _start_session()
    topic = _first_topic()

    response = client.get(f"/topic/{session_id}/{topic.topic_id}")
    html = response.text

    assert response.status_code == 200
    assert 'method="post" action="/topic/outcome/post"' in html
    assert 'name="post_answer"' in html
    assert 'name="post_score"' in html


def test_score_inputs_support_zero_to_ten():
    session_id = _start_session()
    topic = _first_topic()

    response = client.get(f"/topic/{session_id}/{topic.topic_id}")
    html = response.text

    assert response.status_code == 200
    for score in range(0, 11):
        assert f'value="{score}"' in html
        assert f"{score}/10" in html


def test_safe_summary_is_displayed_when_available():
    session_id = _start_session()
    topic = _first_topic()

    with patch(
        "routes.topics._topic_detail_learning_outcome_summary",
        return_value=(_summary(), False),
    ):
        response = client.get(f"/topic/{session_id}/{topic.topic_id}")

    html = response.text
    assert response.status_code == 200
    assert "Baseline saved: Yes" in html
    assert "Post-topic saved: Yes" in html
    assert "Baseline score: 3" in html
    assert "Post score: 8" in html
    assert "Improvement delta: 5" in html
    assert "Status: improved" in html


def test_full_baseline_and_post_answers_are_not_displayed():
    session_id = _start_session()
    topic = _first_topic()

    with patch(
        "routes.topics._topic_detail_learning_outcome_summary",
        return_value=(_summary(), False),
    ):
        response = client.get(f"/topic/{session_id}/{topic.topic_id}")

    assert response.status_code == 200
    assert PRIVATE_BASELINE not in response.text
    assert PRIVATE_POST not in response.text
    assert "baseline_answer" in response.text
    assert "post_answer" in response.text


def test_db_read_failure_does_not_break_topic_page_or_expose_secrets():
    session_id = _start_session()
    topic = _first_topic()

    with patch("routes.topics.TEST_MODE", False), patch(
        "database.pool.DATABASE_URL", "postgresql://configured"
    ), patch("database.pool.get_conn", side_effect=RuntimeError(SECRET_ERROR)):
        response = client.get(f"/topic/{session_id}/{topic.topic_id}")

    assert response.status_code == 200
    assert "Learning outcome summary is temporarily unavailable." in response.text
    assert "AI Learning Content" in response.text
    assert "postgresql://" not in response.text
    assert "sk-secret" not in response.text
    assert "ANTHROPIC_API_KEY" not in response.text


def test_no_claude_call_is_made_for_learning_outcome_section():
    session_id = _start_session()
    topic = _first_topic()

    with patch(
        "routes.topics.deps.make_client",
        side_effect=AssertionError("Claude must not be called"),
    ) as make_client:
        response = client.get(f"/topic/{session_id}/{topic.topic_id}")

    assert response.status_code == 200
    make_client.assert_not_called()


def test_usage_limit_enforcement_is_not_triggered_for_learning_outcome_section():
    session_id = _start_session()
    topic = _first_topic()

    with patch(
        "routes.topics.deps.build_limit_enforcer",
        side_effect=AssertionError("usage limits should not run"),
    ) as build_limit:
        response = client.get(f"/topic/{session_id}/{topic.topic_id}")

    assert response.status_code == 200
    build_limit.assert_not_called()


def test_existing_topic_detail_content_still_renders():
    session_id = _start_session()
    topic = _first_topic()

    response = client.get(f"/topic/{session_id}/{topic.topic_id}")

    assert response.status_code == 200
    assert topic.topic_title in response.text
    assert "AI Learning Content" in response.text
    assert "Topic Journey" in response.text
