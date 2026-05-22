"""Tests for write-through wiring in mutation routes.

Verifies that:
- With AI2_DB_WRITE_THROUGH_ENABLED unset/off, routes work and no DB calls happen.
- With flag on, routes call the write-through helpers with correct arguments.
- If write-through fails (DB error), routes still return the correct success response.
- Response payloads are unchanged in all flag states.
- SessionContext remains the source of truth (state persists even when DB fails).

All tests run without a real DB connection.
"""

from __future__ import annotations

import os

os.environ["AI2_TEST_MODE"] = "1"
os.environ["ANTHROPIC_API_KEY"] = "test-key"

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app import app
from curriculum.topics import get_topics_for_week

client = TestClient(app)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _start_session(track: str = "aipm", week: int = 1) -> str:
    r = client.post("/session/start", json={"track": track, "week": week})
    assert r.status_code == 200, r.text
    return r.json()["session_id"]


def _first_topic():
    return get_topics_for_week("aipm", 1)[0]


# ── Flag OFF: routes work exactly as before ───────────────────────────────────

def test_topic_progress_flag_off_returns_correct_payload(monkeypatch):
    monkeypatch.delenv("AI2_DB_WRITE_THROUGH_ENABLED", raising=False)
    session_id = _start_session()
    topic = _first_topic()
    r = client.post("/topic/progress", json={
        "session_id": session_id,
        "topic_id":   topic.topic_id,
        "step":       "learn",
        "status":     "done",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["topic_id"] == topic.topic_id
    assert data["step"] == "learn"
    assert data["status"] == "done"
    assert data["topic_progress"]["learn"] == "done"
    assert data["completion_percent"] == 20


def test_topic_notes_flag_off_returns_correct_payload(monkeypatch):
    monkeypatch.delenv("AI2_DB_WRITE_THROUGH_ENABLED", raising=False)
    session_id = _start_session()
    topic = _first_topic()
    r = client.post("/topic/notes", json={
        "session_id":  session_id,
        "topic_id":    topic.topic_id,
        "reflection":  "I learned a lot",
        "confusions":  "",
        "application_idea": "",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["topic_id"] == topic.topic_id
    assert "topic_progress" in data
    assert "completion_percent" in data
    assert data["notes"]["reflection"] == "I learned a lot"


def test_todo_create_flag_off_returns_correct_payload(monkeypatch):
    monkeypatch.delenv("AI2_DB_WRITE_THROUGH_ENABLED", raising=False)
    session_id = _start_session()
    r = client.post("/todos/create", json={
        "session_id": session_id,
        "title":      "Read papers",
        "todo_type":  "daily",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["todo"]["title"] == "Read papers"
    assert data["todo"]["status"] == "todo"
    assert "todo_counts" in data


def test_todo_status_flag_off_returns_correct_payload(monkeypatch):
    monkeypatch.delenv("AI2_DB_WRITE_THROUGH_ENABLED", raising=False)
    session_id = _start_session()
    create_r = client.post("/todos/create", json={
        "session_id": session_id, "title": "Task A", "todo_type": "daily",
    })
    todo_id = create_r.json()["todo"]["todo_id"]
    r = client.post("/todos/status", json={
        "session_id": session_id, "todo_id": todo_id, "status": "done",
    })
    assert r.status_code == 200
    assert r.json()["todo"]["status"] == "done"
    assert "todo_counts" in r.json()


# ── Flag OFF: no DB connection is ever attempted ──────────────────────────────

def test_topic_progress_flag_off_no_db_connect(monkeypatch):
    """With flag off the write-through helper exits before touching the DB."""
    monkeypatch.delenv("AI2_DB_WRITE_THROUGH_ENABLED", raising=False)
    session_id = _start_session()
    topic = _first_topic()
    with patch("database.pool._connect", side_effect=AssertionError("_connect must not be called")) as mock_c:
        r = client.post("/topic/progress", json={
            "session_id": session_id,
            "topic_id":   topic.topic_id,
            "step":       "quiz",
            "status":     "in_progress",
        })
    assert r.status_code == 200
    mock_c.assert_not_called()


def test_todo_create_flag_off_no_db_connect(monkeypatch):
    monkeypatch.delenv("AI2_DB_WRITE_THROUGH_ENABLED", raising=False)
    session_id = _start_session()
    with patch("database.pool._connect", side_effect=AssertionError("_connect must not be called")) as mock_c:
        r = client.post("/todos/create", json={
            "session_id": session_id, "title": "No DB task", "todo_type": "weekly",
        })
    assert r.status_code == 200
    mock_c.assert_not_called()


def test_todo_status_flag_off_no_db_connect(monkeypatch):
    monkeypatch.delenv("AI2_DB_WRITE_THROUGH_ENABLED", raising=False)
    session_id = _start_session()
    create_r = client.post("/todos/create", json={
        "session_id": session_id, "title": "Task", "todo_type": "daily",
    })
    todo_id = create_r.json()["todo"]["todo_id"]
    with patch("database.pool._connect", side_effect=AssertionError("_connect must not be called")) as mock_c:
        r = client.post("/todos/status", json={
            "session_id": session_id, "todo_id": todo_id, "status": "in_progress",
        })
    assert r.status_code == 200
    mock_c.assert_not_called()


# ── Flag ON: write-through helpers are called ─────────────────────────────────

def test_topic_progress_flag_on_write_through_called(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    session_id = _start_session()
    topic = _first_topic()
    with patch("routes.deps.write_through_topic_progress") as mock_wt:
        r = client.post("/topic/progress", json={
            "session_id": session_id,
            "topic_id":   topic.topic_id,
            "step":       "learn",
            "status":     "done",
        })
    assert r.status_code == 200
    mock_wt.assert_called_once()
    kwargs = mock_wt.call_args[1]
    assert kwargs["session_id"] == session_id
    assert kwargs["legacy_topic_id"] == topic.topic_id


def test_topic_notes_flag_on_write_through_called(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    session_id = _start_session()
    topic = _first_topic()
    with patch("routes.deps.write_through_topic_progress") as mock_wt:
        r = client.post("/topic/notes", json={
            "session_id":  session_id,
            "topic_id":    topic.topic_id,
            "reflection":  "great stuff",
            "confusions":  "",
            "application_idea": "",
        })
    assert r.status_code == 200
    mock_wt.assert_called_once()
    kwargs = mock_wt.call_args[1]
    assert kwargs["legacy_topic_id"] == topic.topic_id
    assert kwargs["session_id"] == session_id


def test_todo_create_flag_on_write_through_todos_called(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    session_id = _start_session()
    with patch("routes.deps.write_through_todos") as mock_wt:
        r = client.post("/todos/create", json={
            "session_id": session_id, "title": "Flag on task", "todo_type": "daily",
        })
    assert r.status_code == 200
    mock_wt.assert_called_once()
    kwargs = mock_wt.call_args[1]
    assert kwargs["session_id"] == session_id


def test_todo_status_flag_on_write_through_todos_called(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    session_id = _start_session()
    create_r = client.post("/todos/create", json={
        "session_id": session_id, "title": "Task", "todo_type": "daily",
    })
    todo_id = create_r.json()["todo"]["todo_id"]
    with patch("routes.deps.write_through_todos") as mock_wt:
        r = client.post("/todos/status", json={
            "session_id": session_id, "todo_id": todo_id, "status": "done",
        })
    assert r.status_code == 200
    mock_wt.assert_called_once()
    kwargs = mock_wt.call_args[1]
    assert kwargs["session_id"] == session_id


def test_portfolio_submit_flag_on_write_through_called(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    session_id = _start_session()
    topic = _first_topic()
    with patch("routes.deps.write_through_topic_progress") as mock_wt:
        r = client.post("/portfolio/submit", json={
            "session_id": session_id,
            "topic_id":   topic.topic_id,
            "submission": "Here is my portfolio answer.",
        })
    assert r.status_code == 200
    mock_wt.assert_called_once()
    assert mock_wt.call_args[1]["legacy_topic_id"] == topic.topic_id


def test_quiz_submit_flag_on_write_through_called(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    session_id = _start_session()
    topic = _first_topic()
    with patch("routes.deps.write_through_topic_progress") as mock_wt:
        r = client.post("/quiz/submit", json={
            "session_id": session_id,
            "topic_id":   topic.topic_id,
            "answers":    "1: A, 2: B",
        })
    assert r.status_code == 200
    mock_wt.assert_called_once()
    assert mock_wt.call_args[1]["legacy_topic_id"] == topic.topic_id


def test_interview_submit_flag_on_write_through_called(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    session_id = _start_session()
    topic = _first_topic()
    with patch("routes.deps.write_through_topic_progress") as mock_wt:
        r = client.post("/interview/submit", json={
            "session_id": session_id,
            "topic_id":   topic.topic_id,
            "answer":     "My interview answer.",
        })
    assert r.status_code == 200
    mock_wt.assert_called_once()
    assert mock_wt.call_args[1]["legacy_topic_id"] == topic.topic_id


# ── Flag ON: DB failure is swallowed — route still succeeds ───────────────────

def test_topic_progress_db_failure_does_not_break_route(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    session_id = _start_session()
    topic = _first_topic()
    with patch("database.pool._connect", side_effect=RuntimeError("DB down")):
        r = client.post("/topic/progress", json={
            "session_id": session_id,
            "topic_id":   topic.topic_id,
            "step":       "portfolio_task",
            "status":     "in_progress",
        })
    assert r.status_code == 200
    assert r.json()["topic_progress"]["portfolio_task"] == "in_progress"


def test_topic_notes_db_failure_does_not_break_route(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    session_id = _start_session()
    topic = _first_topic()
    with patch("database.pool._connect", side_effect=RuntimeError("DB down")):
        r = client.post("/topic/notes", json={
            "session_id":  session_id,
            "topic_id":    topic.topic_id,
            "reflection":  "Learned a lot",
            "confusions":  "",
            "application_idea": "",
        })
    assert r.status_code == 200
    assert r.json()["notes"]["reflection"] == "Learned a lot"


def test_todo_create_db_failure_does_not_break_route(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    session_id = _start_session()
    with patch("database.pool._connect", side_effect=RuntimeError("DB down")):
        r = client.post("/todos/create", json={
            "session_id": session_id,
            "title":      "Task despite DB failure",
            "todo_type":  "daily",
        })
    assert r.status_code == 200
    assert r.json()["todo"]["title"] == "Task despite DB failure"


def test_todo_status_db_failure_does_not_break_route(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    session_id = _start_session()
    create_r = client.post("/todos/create", json={
        "session_id": session_id, "title": "Task", "todo_type": "daily",
    })
    todo_id = create_r.json()["todo"]["todo_id"]
    with patch("database.pool._connect", side_effect=RuntimeError("DB down")):
        r = client.post("/todos/status", json={
            "session_id": session_id, "todo_id": todo_id, "status": "in_progress",
        })
    assert r.status_code == 200
    assert r.json()["todo"]["status"] == "in_progress"


# ── SessionContext remains source of truth ────────────────────────────────────

def test_topic_progress_persists_in_session_when_db_fails(monkeypatch):
    """After a mutation with DB failure, SessionContext still holds the update."""
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    session_id = _start_session()
    topic = _first_topic()
    with patch("database.pool._connect", side_effect=RuntimeError("DB down")):
        client.post("/topic/progress", json={
            "session_id": session_id,
            "topic_id":   topic.topic_id,
            "step":       "learn",
            "status":     "done",
        })
    # Read back via topic detail page — rendered from SessionContext, not DB
    r = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert r.status_code == 200
    assert "done" in r.text.lower() or "Done" in r.text


def test_todo_persists_in_session_when_db_fails(monkeypatch):
    """After todo create with DB failure, todo still appears in todos page."""
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    session_id = _start_session()
    with patch("database.pool._connect", side_effect=RuntimeError("DB down")):
        client.post("/todos/create", json={
            "session_id": session_id,
            "title":      "Persistent task",
            "todo_type":  "daily",
        })
    r = client.get(f"/todos/{session_id}")
    assert r.status_code == 200
    assert "Persistent task" in r.text


# ── Response payloads are unchanged by write-through ─────────────────────────

def test_topic_progress_response_keys_unchanged_flag_on(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    session_id = _start_session()
    topic = _first_topic()
    with patch("routes.deps.write_through_topic_progress"):
        r = client.post("/topic/progress", json={
            "session_id": session_id,
            "topic_id":   topic.topic_id,
            "step":       "quiz",
            "status":     "done",
        })
    assert r.status_code == 200
    data = r.json()
    for key in ("topic_id", "step", "status", "topic_progress", "completion_percent"):
        assert key in data, f"Missing response key: {key}"


def test_todo_create_response_keys_unchanged_flag_on(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    session_id = _start_session()
    with patch("routes.deps.write_through_todos"):
        r = client.post("/todos/create", json={
            "session_id": session_id, "title": "Task", "todo_type": "weekly",
        })
    assert r.status_code == 200
    data = r.json()
    assert "todo" in data
    assert "todo_counts" in data
    assert data["todo"]["title"] == "Task"


def test_todo_status_response_keys_unchanged_flag_on(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    session_id = _start_session()
    create_r = client.post("/todos/create", json={
        "session_id": session_id, "title": "Task", "todo_type": "daily",
    })
    todo_id = create_r.json()["todo"]["todo_id"]
    with patch("routes.deps.write_through_todos"):
        r = client.post("/todos/status", json={
            "session_id": session_id, "todo_id": todo_id, "status": "done",
        })
    assert r.status_code == 200
    data = r.json()
    assert "todo" in data
    assert "todo_counts" in data
    assert data["todo"]["status"] == "done"


# ── No DB reads from new tables ───────────────────────────────────────────────

def test_no_db_read_in_topic_progress_route(monkeypatch):
    """Topic progress route reads state only from SessionContext, not from DB."""
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    session_id = _start_session()
    topic = _first_topic()
    # Mock _connect so any SELECT attempt raises; route should still work
    with patch("database.pool._connect", side_effect=RuntimeError("no reads allowed")):
        r = client.post("/topic/progress", json={
            "session_id": session_id,
            "topic_id":   topic.topic_id,
            "step":       "learn",
            "status":     "done",
        })
    assert r.status_code == 200
    # The progress in the response comes from SessionContext, not DB
    assert r.json()["topic_progress"]["learn"] == "done"
