"""Tests for GET /debug/storage-health-view."""

from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import patch

os.environ["AI2_TEST_MODE"] = "1"
os.environ["ANTHROPIC_API_KEY"] = "test-key"

from fastapi.testclient import TestClient

from app import app


client = TestClient(app)
URL = "/debug/storage-health-view"

PRIVATE_SESSION_DATA = "full session_data JSON should never appear"
PRIVATE_CONTENT = "full generated content should never appear"
PRIVATE_SUBMISSION = "full learner submission should never appear"
PRIVATE_NOTE = "full private topic note should never appear"
PRIVATE_METADATA = "full usage metadata should never appear"

FLAG_NAMES = (
    "AI2_DB_WRITE_THROUGH_ENABLED",
    "AI2_CURRICULUM_DB_READS_ENABLED",
    "AI2_PROGRESS_DB_READS_ENABLED",
    "AI2_TODOS_DB_READS_ENABLED",
)


def _clear_flags(monkeypatch):
    for name in FLAG_NAMES:
        monkeypatch.delenv(name, raising=False)


def _set_flags(monkeypatch, **values):
    _clear_flags(monkeypatch)
    mapping = {
        "write_through": "AI2_DB_WRITE_THROUGH_ENABLED",
        "curriculum": "AI2_CURRICULUM_DB_READS_ENABLED",
        "progress": "AI2_PROGRESS_DB_READS_ENABLED",
        "todos": "AI2_TODOS_DB_READS_ENABLED",
    }
    for key, enabled in values.items():
        monkeypatch.setenv(mapping[key], "1" if enabled else "0")


def _fake_session():
    topic_progress = {
        "topic-1": {
            "learn": "done",
            "quiz": "done",
            "portfolio_task": "done",
            "interview_practice": "done",
            "reflection": "done",
        },
        "topic-2": {"learn": "in_progress"},
    }

    def topic_completion_percent(topic_id):
        return 100 if topic_id == "topic-1" else 20

    return SimpleNamespace(
        private_payload=PRIVATE_SESSION_DATA,
        usage_events=[
            {"event_id": "evt-1", "metadata": {"private": PRIVATE_METADATA}},
            {"event_id": "evt-2", "metadata": {"private": PRIVATE_METADATA}},
        ],
        todos=[
            {"todo_id": "todo-1", "title": "todo one"},
            {"todo_id": "todo-2", "title": "todo two"},
            {"todo_id": "todo-3", "title": "todo three"},
        ],
        topic_progress=topic_progress,
        generated_topic_content={
            "topic-1": {"content": PRIVATE_CONTENT},
        },
        generated_topic_practice={
            "topic-1": {
                "quiz": {"content": PRIVATE_CONTENT},
                "portfolio_task": None,
                "interview_practice": None,
            },
        },
        quiz_submissions={
            "topic-1": {"answers": PRIVATE_SUBMISSION},
        },
        portfolio_submissions={
            "topic-1": {"submission": PRIVATE_SUBMISSION},
        },
        interview_submissions={
            "topic-1": {"answer": PRIVATE_SUBMISSION},
        },
        topic_notes={
            "topic-1": {"reflection": PRIVATE_NOTE},
        },
        topic_completion_percent=topic_completion_percent,
    )


def _fake_session_data(session=None):
    return {"session": session or _fake_session(), "orch": None, "client": None, "profile": None}


def test_route_page_exists(monkeypatch):
    _clear_flags(monkeypatch)
    response = client.get(URL)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")


def test_page_renders_with_no_session_id(monkeypatch):
    _clear_flags(monkeypatch)
    response = client.get(URL)

    assert response.status_code == 200
    assert "Storage Health" in response.text
    assert "No session_id provided" in response.text


def test_page_shows_source_of_truth(monkeypatch):
    _clear_flags(monkeypatch)
    text = client.get(URL).text

    assert "Source Of Truth" in text
    assert "SessionContext" in text
    assert "DB primary reads" in text
    assert "false" in text


def test_page_shows_write_through_and_read_flags(monkeypatch):
    _set_flags(monkeypatch, write_through=True, curriculum=True, progress=False, todos=True)
    text = client.get(URL).text

    assert "DB write-through enabled" in text
    assert "Curriculum DB reads enabled" in text
    assert "Progress DB reads enabled" in text
    assert "Todos DB reads enabled" in text
    assert "true" in text
    assert "false" in text


def test_page_shows_overall_status(monkeypatch):
    _clear_flags(monkeypatch)
    text = client.get(URL).text

    assert "Overall status: not_configured" in text


def test_page_shows_mirror_sections(monkeypatch):
    _clear_flags(monkeypatch)
    text = client.get(URL).text

    assert "curriculum" in text
    assert "learner_state" in text
    assert "generated_learning" in text
    assert "usage_events" in text


def test_with_session_id_page_shows_safe_counts_only(monkeypatch):
    _clear_flags(monkeypatch)
    with patch("app._get_session_data", return_value=_fake_session_data()):
        text = client.get(URL, params={"session_id": "sess-1"}).text

    assert "Session Counts" in text
    assert "usage_events_count" in text
    assert "todos_count" in text
    assert "completed_topics_count" in text
    assert ">2<" in text
    assert ">3<" in text
    assert ">1<" in text
    assert "todo one" not in text


def test_with_legacy_topic_id_page_shows_safe_booleans_only(monkeypatch):
    _clear_flags(monkeypatch)
    with patch("app._get_session_data", return_value=_fake_session_data()):
        text = client.get(
            URL,
            params={"session_id": "sess-1", "legacy_topic_id": "topic-1"},
        ).text

    assert "Topic Presence" in text
    assert "topic_progress_present" in text
    assert "generated_content_present" in text
    assert "practice_present" in text
    assert "quiz_submission_present" in text
    assert "portfolio_submission_present" in text
    assert "interview_submission_present" in text
    assert "notes_present" in text


def test_page_does_not_expose_generated_content_text(monkeypatch):
    _clear_flags(monkeypatch)
    with patch("app._get_session_data", return_value=_fake_session_data()):
        text = client.get(URL, params={"session_id": "sess-1", "legacy_topic_id": "topic-1"}).text

    assert PRIVATE_CONTENT not in text


def test_page_does_not_expose_submission_text(monkeypatch):
    _clear_flags(monkeypatch)
    with patch("app._get_session_data", return_value=_fake_session_data()):
        text = client.get(URL, params={"session_id": "sess-1", "legacy_topic_id": "topic-1"}).text

    assert PRIVATE_SUBMISSION not in text


def test_page_does_not_expose_notes_text(monkeypatch):
    _clear_flags(monkeypatch)
    with patch("app._get_session_data", return_value=_fake_session_data()):
        text = client.get(URL, params={"session_id": "sess-1", "legacy_topic_id": "topic-1"}).text

    assert PRIVATE_NOTE not in text


def test_page_does_not_expose_usage_metadata(monkeypatch):
    _clear_flags(monkeypatch)
    with patch("app._get_session_data", return_value=_fake_session_data()):
        text = client.get(URL, params={"session_id": "sess-1"}).text

    assert PRIVATE_METADATA not in text
    assert "metadata" not in text


def test_page_does_not_expose_session_data_json(monkeypatch):
    _clear_flags(monkeypatch)
    with patch("app._get_session_data", return_value=_fake_session_data()):
        text = client.get(URL, params={"session_id": "sess-1"}).text

    assert PRIVATE_SESSION_DATA not in text
    assert "private_payload" not in text
    assert "session_data" not in text


def test_page_does_not_expose_secrets_or_raw_env_values(monkeypatch):
    _clear_flags(monkeypatch)
    monkeypatch.setenv("SUPABASE_DATABASE_URL", "postgresql://user:secret@host/db")
    monkeypatch.setenv("DATABASE_URL", "postgresql://other:secret@host/db")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-live-secret")
    with patch("app._get_session_data", return_value=_fake_session_data()):
        text = client.get(URL, params={"session_id": "sess-1", "legacy_topic_id": "topic-1"}).text

    assert "postgresql://" not in text
    assert "sk-live-secret" not in text
    assert "SUPABASE_DATABASE_URL" not in text
    assert "DATABASE_URL" not in text
    assert "ANTHROPIC_API_KEY" not in text


def test_page_does_not_open_db_connection(monkeypatch):
    _clear_flags(monkeypatch)
    with patch("app.get_conn", side_effect=AssertionError("DB must not be opened")) as get_conn:
        response = client.get(URL)

    assert response.status_code == 200
    get_conn.assert_not_called()


def test_page_does_not_call_save_session(monkeypatch):
    _clear_flags(monkeypatch)
    with patch("app._get_session_data", return_value=_fake_session_data()), patch(
        "app._save_session",
        side_effect=AssertionError("save_session must not be called"),
    ) as save_session:
        response = client.get(URL, params={"session_id": "sess-1"})

    assert response.status_code == 200
    save_session.assert_not_called()


def test_no_learner_facing_route_behavior_changed():
    paths = {route.path for route in app.routes}
    assert {
        "/topics/{session_id}",
        "/topic/{session_id}/{topic_id}",
        "/topic/notes",
        "/topic/content/generate",
        "/topic/practice/generate",
        "/todos/{session_id}",
        "/quiz/submit",
        "/portfolio/submit",
        "/interview/submit",
        URL,
    }.issubset(paths)
