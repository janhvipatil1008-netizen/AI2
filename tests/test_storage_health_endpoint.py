"""Tests for GET /debug/storage-health."""

from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import patch

os.environ["AI2_TEST_MODE"] = "1"
os.environ["ANTHROPIC_API_KEY"] = "test-key"

from fastapi.testclient import TestClient

from app import app


client = TestClient(app)
URL = "/debug/storage-health"

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
            {
                "event_id": "evt-1",
                "event_type": "topic_learning_content",
                "metadata": {"private": PRIVATE_METADATA},
            },
            {
                "event_id": "evt-2",
                "event_type": "quiz_evaluation",
                "metadata": {"private": PRIVATE_METADATA},
            },
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


def test_endpoint_exists(monkeypatch):
    _clear_flags(monkeypatch)
    response = client.get(URL)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")


def test_no_session_id_returns_config_only_health(monkeypatch):
    _clear_flags(monkeypatch)
    data = client.get(URL).json()

    assert data["source_of_truth"] == {
        "session_context": True,
        "db_primary_reads": False,
    }
    assert data["mirrors"]["curriculum"]["schema_available"] is True
    assert "session_status" not in data["mirrors"]["learner_state"]
    assert "topic_status" not in data["mirrors"]["generated_learning"]


def test_no_session_id_does_not_load_session(monkeypatch):
    _clear_flags(monkeypatch)
    with patch("app._get_session_data", side_effect=AssertionError("session must not load")) as loader:
        response = client.get(URL)

    assert response.status_code == 200
    loader.assert_not_called()


def test_no_session_id_does_not_open_db_connection(monkeypatch):
    _clear_flags(monkeypatch)
    with patch("app.get_conn", side_effect=AssertionError("DB must not be opened")) as get_conn:
        response = client.get(URL)

    assert response.status_code == 200
    get_conn.assert_not_called()


def test_flags_are_reported_correctly(monkeypatch):
    _set_flags(monkeypatch, write_through=True, curriculum=True, progress=False, todos=True)
    data = client.get(URL).json()

    assert data["flags"] == {
        "db_write_through_enabled": True,
        "curriculum_db_reads_enabled": True,
        "progress_db_reads_enabled": False,
        "todos_db_reads_enabled": True,
        "db_reads_enabled": True,
    }
    assert data["mirrors"]["curriculum"]["read_flag_enabled"] is True
    assert data["mirrors"]["learner_state"]["progress_read_flag_enabled"] is False
    assert data["mirrors"]["learner_state"]["todos_read_flag_enabled"] is True


def test_overall_status_not_configured_when_flags_off(monkeypatch):
    _clear_flags(monkeypatch)
    data = client.get(URL).json()

    assert data["overall_status"] == "not_configured"


def test_overall_status_partial_when_write_through_flag_on(monkeypatch):
    _set_flags(monkeypatch, write_through=True)
    data = client.get(URL).json()

    assert data["overall_status"] == "partial"


def test_session_id_loads_session_context_read_only(monkeypatch):
    _clear_flags(monkeypatch)
    session = _fake_session()
    with patch("app._get_session_data", return_value=_fake_session_data(session)) as loader, patch(
        "app._save_session",
    ) as save_session:
        response = client.get(URL, params={"session_id": "sess-1"})

    assert response.status_code == 200
    loader.assert_called_once_with("sess-1", "")
    save_session.assert_not_called()


def test_session_summary_includes_counts_only(monkeypatch):
    _clear_flags(monkeypatch)
    with patch("app._get_session_data", return_value=_fake_session_data()):
        data = client.get(URL, params={"session_id": "sess-1"}).json()

    session_status = data["mirrors"]["learner_state"]["session_status"]
    assert session_status == {
        "session_loaded": True,
        "usage_events_count": 2,
        "todos_count": 3,
        "completed_topics_count": 1,
    }
    assert data["mirrors"]["usage_events"]["session_status"] == {
        "session_loaded": True,
        "usage_events_count": 2,
    }


def test_legacy_topic_id_adds_topic_level_booleans_only(monkeypatch):
    _clear_flags(monkeypatch)
    with patch("app._get_session_data", return_value=_fake_session_data()):
        data = client.get(
            URL,
            params={"session_id": "sess-1", "legacy_topic_id": "topic-1"},
        ).json()

    expected = {
        "topic_progress_present": True,
        "generated_content_present": True,
        "practice_present": True,
        "quiz_submission_present": True,
        "portfolio_submission_present": True,
        "interview_submission_present": True,
        "notes_present": True,
    }
    assert data["mirrors"]["learner_state"]["topic_status"] == expected
    assert data["mirrors"]["generated_learning"]["topic_status"] == expected


def test_endpoint_does_not_call_save_session(monkeypatch):
    _clear_flags(monkeypatch)
    with patch("app._get_session_data", return_value=_fake_session_data()), patch(
        "app._save_session",
        side_effect=AssertionError("save_session must not be called"),
    ) as save_session:
        response = client.get(URL, params={"session_id": "sess-1"})

    assert response.status_code == 200
    save_session.assert_not_called()


def test_endpoint_does_not_expose_full_session_data(monkeypatch):
    _clear_flags(monkeypatch)
    with patch("app._get_session_data", return_value=_fake_session_data()):
        response = client.get(URL, params={"session_id": "sess-1"})

    assert PRIVATE_SESSION_DATA not in response.text
    assert "private_payload" not in response.text


def test_endpoint_does_not_expose_generated_content_submission_or_note_text(monkeypatch):
    _clear_flags(monkeypatch)
    with patch("app._get_session_data", return_value=_fake_session_data()):
        response = client.get(
            URL,
            params={"session_id": "sess-1", "legacy_topic_id": "topic-1"},
        )

    assert PRIVATE_CONTENT not in response.text
    assert PRIVATE_SUBMISSION not in response.text
    assert PRIVATE_NOTE not in response.text


def test_endpoint_does_not_expose_usage_metadata(monkeypatch):
    _clear_flags(monkeypatch)
    with patch("app._get_session_data", return_value=_fake_session_data()):
        response = client.get(URL, params={"session_id": "sess-1"})

    assert PRIVATE_METADATA not in response.text
    assert '"metadata"' not in response.text


def test_no_secrets_or_raw_env_values_appear_in_response(monkeypatch):
    _clear_flags(monkeypatch)
    monkeypatch.setenv("SUPABASE_DATABASE_URL", "postgresql://user:secret@host/db")
    monkeypatch.setenv("DATABASE_URL", "postgresql://other:secret@host/db")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-live-secret")
    with patch("app._get_session_data", return_value=_fake_session_data()):
        response = client.get(URL, params={"session_id": "sess-1", "legacy_topic_id": "topic-1"})

    assert "postgresql://" not in response.text
    assert "sk-live-secret" not in response.text
    assert "SUPABASE_DATABASE_URL" not in response.text
    assert "DATABASE_URL" not in response.text
    assert "ANTHROPIC_API_KEY" not in response.text


def test_no_learner_facing_route_behavior_changes():
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
