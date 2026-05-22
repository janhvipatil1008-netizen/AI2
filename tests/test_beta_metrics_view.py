"""Tests for the protected internal beta metrics view."""

from __future__ import annotations

import os
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

os.environ["AI2_TEST_MODE"] = "1"
os.environ["ANTHROPIC_API_KEY"] = "test-key"

from fastapi.testclient import TestClient

from app import app
from curriculum.topics import get_topics_for_week


client = TestClient(app)

URL = "/admin/beta-metrics"
TOKEN = "beta-metrics-debug-token"
PRIVATE_FEEDBACK = "private beta feedback text should not render"
PRIVATE_CONTENT = "private generated lesson content should not render"
PRIVATE_SUBMISSION = "private learner submission should not render"
PRIVATE_NOTE = "private topic note should not render"
SECRET_URL = "postgresql://user:secret@host/db"


@contextmanager
def _conn_context():
    yield MagicMock()


def _metrics(**overrides):
    data = {
        "session_user_summary": {
            "total_sessions": 12,
            "total_users": 5,
            "private_email": "learner@example.com",
        },
        "usage_summary": {
            "total_usage_events": 44,
            "claude_events": 20,
            "cache_events": 10,
            "limit_blocked_events": 2,
            "metadata": "raw usage metadata",
        },
        "learning_outcomes_summary": {
            "total_outcomes": 8,
            "baseline_completed_count": 7,
            "post_completed_count": 6,
            "improved_count": 5,
            "average_improvement_delta": 2.5,
            "post_answer": PRIVATE_SUBMISSION,
        },
        "beta_feedback_summary": {
            "total_feedback_submissions": 9,
            "average_usefulness_score": 4.4,
            "average_clarity_score": 4.1,
            "willingness_to_pay_counts": {
                "yes": 3,
                "maybe": 2,
                PRIVATE_FEEDBACK: 99,
            },
            "feedback_text": PRIVATE_FEEDBACK,
        },
        "cache_summary": {
            "total_rows": 18,
            "active_rows": 16,
            "stale_rows": 2,
            "content": PRIVATE_CONTENT,
        },
        "topic_notes": PRIVATE_NOTE,
    }
    data.update(overrides)
    return data


def _start_session() -> str:
    response = client.post("/session/start", json={"track": "aipm", "week": 1})
    assert response.status_code == 200, response.text
    return response.json()["session_id"]


def test_beta_metrics_route_exists_non_production_without_token(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    with patch("app.get_conn", side_effect=RuntimeError("no test DB")):
        response = client.get(URL)

    assert response.status_code == 200
    assert "AI² Beta Metrics" in response.text
    assert "DB metrics: unavailable" in response.text


def test_production_access_requires_debug_token(monkeypatch):
    monkeypatch.setenv("AI2_ENV", "production")
    monkeypatch.delenv("AI2_DEBUG_TOKEN", raising=False)

    with patch("app.get_conn", side_effect=AssertionError("DB must not be opened")) as get_conn:
        response = client.get(URL)

    assert response.status_code == 404
    get_conn.assert_not_called()


def test_production_access_blocks_wrong_token(monkeypatch):
    monkeypatch.setenv("AI2_ENV", "production")
    monkeypatch.setenv("AI2_DEBUG_TOKEN", TOKEN)

    response = client.get(URL, headers={"X-AI2-Debug-Token": "wrong"})

    assert response.status_code == 404
    assert TOKEN not in response.text
    assert "AI2_DEBUG_TOKEN" not in response.text


def test_production_access_allows_correct_token(monkeypatch):
    monkeypatch.setenv("AI2_ENV", "production")
    monkeypatch.setenv("AI2_DEBUG_TOKEN", TOKEN)

    with patch("app.get_conn", side_effect=RuntimeError("no test DB")):
        response = client.get(URL, headers={"X-AI2-Debug-Token": TOKEN})

    assert response.status_code == 200
    assert "AI² Beta Metrics" in response.text
    assert TOKEN not in response.text


def test_db_success_shows_safe_counts(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    get_conn = MagicMock(return_value=_conn_context())

    with patch("app.get_conn", get_conn), patch(
        "repositories.beta_metrics_repository.collect_beta_metrics",
        return_value=_metrics(),
    ):
        response = client.get(URL)

    assert response.status_code == 200
    assert "DB metrics: available" in response.text
    for value in ("12", "5", "44", "20", "10", "2", "8", "7", "6", "4.4", "4.1", "18", "16"):
        assert value in response.text
    assert "willingness_to_pay_yes" in response.text
    assert get_conn.call_count == 1


def test_db_failure_shows_friendly_unavailable_state(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)

    with patch("app.get_conn", side_effect=RuntimeError(f"cannot connect {SECRET_URL}")) as get_conn:
        response = client.get(URL)

    assert response.status_code == 200
    assert "DB metrics: unavailable" in response.text
    assert "not available yet" in response.text
    assert "postgresql://" not in response.text
    assert get_conn.call_count == 1


def test_private_feedback_generated_content_submissions_and_notes_not_exposed(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)

    with patch("app.get_conn", return_value=_conn_context()), patch(
        "repositories.beta_metrics_repository.collect_beta_metrics",
        return_value=_metrics(),
    ):
        response = client.get(URL)

    assert response.status_code == 200
    assert PRIVATE_FEEDBACK not in response.text
    assert PRIVATE_CONTENT not in response.text
    assert PRIVATE_SUBMISSION not in response.text
    assert PRIVATE_NOTE not in response.text
    assert "learner@example.com" not in response.text
    assert "raw usage metadata" not in response.text


def test_no_secrets_or_raw_env_values_are_exposed(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    monkeypatch.setenv("SUPABASE_DATABASE_URL", SECRET_URL)
    monkeypatch.setenv("DATABASE_URL", SECRET_URL)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-secret-value")

    with patch("app.get_conn", side_effect=RuntimeError(f"failure {SECRET_URL} ANTHROPIC_API_KEY=sk-secret-value")):
        response = client.get(URL)

    assert response.status_code == 200
    assert "postgresql://" not in response.text
    assert "sk-secret-value" not in response.text
    assert "ANTHROPIC_API_KEY" not in response.text
    assert "SUPABASE_DATABASE_URL" not in response.text
    assert "DATABASE_URL" not in response.text


def test_one_db_connection_max(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    get_conn = MagicMock(return_value=_conn_context())

    with patch("app.get_conn", get_conn), patch(
        "repositories.beta_metrics_repository.collect_beta_metrics",
        return_value=_metrics(),
    ):
        response = client.get(URL)

    assert response.status_code == 200
    get_conn.assert_called_once()


def test_learner_facing_routes_are_unaffected(monkeypatch):
    monkeypatch.delenv("AI2_ENV", raising=False)
    session_id = _start_session()
    topic = get_topics_for_week("aipm", 1)[0]

    dashboard = client.get("/dashboard")
    topic_page = client.get(f"/topic/{session_id}/{topic.topic_id}")
    privacy = client.get("/privacy")

    assert dashboard.status_code == 200
    assert "Your adaptive learning dashboard" in dashboard.text
    assert topic_page.status_code == 200
    assert topic.topic_title in topic_page.text
    assert privacy.status_code == 200
