"""Tests for private beta privacy and terms pages."""

from __future__ import annotations

import os

os.environ["AI2_TEST_MODE"] = "1"
os.environ["ANTHROPIC_API_KEY"] = "test-key"
os.environ["DATABASE_URL"] = "postgresql://user:secret@host/db"
os.environ["SUPABASE_DATABASE_URL"] = "postgresql://user:secret@host/db"

from fastapi.testclient import TestClient

from app import app
from curriculum.topics import get_topics_for_week


client = TestClient(app)


def _start_session() -> str:
    response = client.post("/session/start", json={"track": "aipm", "week": 1})
    assert response.status_code == 200, response.text
    return response.json()["session_id"]


def _assert_no_secrets(body: str) -> None:
    assert "postgresql://" not in body
    assert "user:secret" not in body
    assert "sk-" not in body
    assert "test-key" not in body
    assert "SUPABASE_DATABASE_URL" not in body
    assert "DATABASE_URL" not in body
    assert "ANTHROPIC_API_KEY" not in body


def test_privacy_page_returns_200():
    response = client.get("/privacy")

    assert response.status_code == 200
    assert "Privacy" in response.text


def test_terms_page_returns_200():
    response = client.get("/terms")

    assert response.status_code == 200
    assert "Terms" in response.text


def test_privacy_mentions_ai_provider_claude_or_anthropic():
    response = client.get("/privacy")

    assert "Claude" in response.text or "Anthropic" in response.text


def test_privacy_mentions_learner_data_progress_and_submissions():
    response = client.get("/privacy")
    body = response.text.lower()

    assert "learning progress" in body
    assert "todos" in body
    assert "topic notes" in body
    assert "quiz submissions" in body
    assert "portfolio submissions" in body
    assert "interview submissions" in body


def test_privacy_mentions_deletion_and_export_request():
    response = client.get("/privacy")
    body = response.text.lower()

    assert "deletion" in body
    assert "export" in body
    assert "request" in body


def test_terms_mentions_ai_feedback_may_be_imperfect():
    response = client.get("/terms")
    body = response.text.lower()

    assert "ai feedback may be imperfect" in body


def test_terms_mentions_free_trial_and_limits():
    response = client.get("/terms")
    body = response.text.lower()

    assert "free trial" in body
    assert "limits" in body


def test_pages_do_not_expose_secrets_or_raw_env_values():
    for path in ("/privacy", "/terms"):
        response = client.get(path)
        assert response.status_code == 200
        _assert_no_secrets(response.text)


def test_login_page_links_to_privacy_and_terms():
    response = client.get("/login", follow_redirects=False)

    assert response.status_code in (200, 302)
    if response.status_code == 200:
        assert "/privacy" in response.text
        assert "/terms" in response.text


def test_dashboard_and_topic_routes_still_work():
    session_id = _start_session()
    dashboard = client.get("/dashboard")
    topic = get_topics_for_week("aipm", 1)[0]
    topic_page = client.get(f"/topic/{session_id}/{topic.topic_id}")

    assert dashboard.status_code == 200
    assert "Your adaptive learning dashboard" in dashboard.text
    assert topic_page.status_code == 200
    assert topic.topic_title in topic_page.text
