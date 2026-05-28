"""Tests for GET /debug/learner-state-db-check.

Verifies that the endpoint:
- exists and returns 200
- never opens a DB connection when both flags are off
- returns correct source/flag values in disabled and live states
- reads progress and todos only when their respective flags are on
- skips progress lookup when legacy_topic_id is absent and adds a note
- handles DB errors safely (HTTP 200, truncated message, no secrets)
- always closes the DB connection (success and error paths)
- does not call or modify any learner-facing route helpers
"""

from __future__ import annotations

import os

os.environ["AI2_TEST_MODE"] = "1"
os.environ["ANTHROPIC_API_KEY"] = "test-key"

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app import app

client = TestClient(app)

URL = "/debug/learner-state-db-check"


# ── Fake DB helpers ───────────────────────────────────────────────────────────

def _make_conn():
    conn = MagicMock()
    conn.close = MagicMock()
    return conn


def _fake_get_conn(conn):
    @contextmanager
    def _ctx():
        try:
            yield conn
        finally:
            conn.close()
    return _ctx


def _fake_get_conn_raises(exc):
    @contextmanager
    def _ctx():
        raise exc
        yield  # pragma: no cover
    return _ctx


_FAKE_PROGRESS = {
    "learn":               "done",
    "quiz":                "not_started",
    "portfolio_task":      "not_started",
    "interview_practice":  "not_started",
    "reflection":          "not_started",
    "completion_percent":  20,
    "legacy_topic_id":     "rag-basics",
    "metadata":            {},
}

_FAKE_TODOS = [
    {
        "todo_id":         "todo-1",
        "title":           "Read the RAG paper",
        "todo_type":       "daily",
        "status":          "todo",
        "linked_topic_id": "rag-basics",
        "created_by":      "agent",
        "due_label":       "today",
        "created_at":      "2026-01-01T00:00:00",
        "updated_at":      "2026-01-01T00:00:00",
    }
]


# ── Endpoint existence ────────────────────────────────────────────────────────

def test_endpoint_exists_returns_200():
    with patch("services.storage_flags.is_progress_db_reads_enabled", return_value=False), \
         patch("services.storage_flags.is_todos_db_reads_enabled",    return_value=False):
        r = client.get(URL, params={"session_id": "sess-1"})
    assert r.status_code == 200


def test_endpoint_returns_json():
    with patch("services.storage_flags.is_progress_db_reads_enabled", return_value=False), \
         patch("services.storage_flags.is_todos_db_reads_enabled",    return_value=False):
        r = client.get(URL, params={"session_id": "sess-1"})
    assert r.headers["content-type"].startswith("application/json")


def test_response_has_all_required_keys():
    with patch("services.storage_flags.is_progress_db_reads_enabled", return_value=False), \
         patch("services.storage_flags.is_todos_db_reads_enabled",    return_value=False):
        r = client.get(URL, params={"session_id": "sess-1"})
    data = r.json()
    required = {
        "progress_db_reads_enabled",
        "todos_db_reads_enabled",
        "attempted_db_connection",
        "session_id",
        "legacy_topic_id",
        "progress_found",
        "todos_found",
        "topic_progress",
        "todos",
        "source",
        "error",
        "notes",
    }
    assert required.issubset(data.keys()), f"Missing: {required - data.keys()}"


# ── Both flags off ────────────────────────────────────────────────────────────

def test_both_flags_off_no_db_connection_attempted():
    with patch(
        "database.pool._connect",
        side_effect=AssertionError("_connect must not be called"),
    ) as mock_connect, \
         patch("services.storage_flags.is_progress_db_reads_enabled", return_value=False), \
         patch("services.storage_flags.is_todos_db_reads_enabled",    return_value=False):
        r = client.get(URL, params={"session_id": "sess-1"})

    mock_connect.assert_not_called()
    assert r.status_code == 200
    assert r.json()["attempted_db_connection"] is False


def test_both_flags_off_source_is_disabled():
    with patch("services.storage_flags.is_progress_db_reads_enabled", return_value=False), \
         patch("services.storage_flags.is_todos_db_reads_enabled",    return_value=False):
        r = client.get(URL, params={"session_id": "sess-1"})
    assert r.json()["source"] == "disabled"


def test_both_flags_off_progress_and_todos_none():
    with patch("services.storage_flags.is_progress_db_reads_enabled", return_value=False), \
         patch("services.storage_flags.is_todos_db_reads_enabled",    return_value=False):
        r = client.get(URL, params={"session_id": "sess-1"})
    data = r.json()
    assert data["topic_progress"] is None
    assert data["todos"] is None
    assert data["progress_found"] is False
    assert data["todos_found"] is False
    assert data["error"] is None


def test_both_flags_off_notes_mention_disabled():
    with patch("services.storage_flags.is_progress_db_reads_enabled", return_value=False), \
         patch("services.storage_flags.is_todos_db_reads_enabled",    return_value=False):
        r = client.get(URL, params={"session_id": "sess-1"})
    notes_text = " ".join(r.json()["notes"]).lower()
    assert "disabled" in notes_text


# ── Progress flag on ──────────────────────────────────────────────────────────

def test_progress_flag_on_db_connection_attempted():
    conn = _make_conn()
    with patch("services.storage_flags.is_progress_db_reads_enabled", return_value=True), \
         patch("services.storage_flags.is_todos_db_reads_enabled",    return_value=False), \
         patch("routes.debug.get_conn", _fake_get_conn(conn)), \
         patch("services.learner_state_read_service.get_topic_progress_from_db", return_value=None):
        r = client.get(URL, params={"session_id": "sess-1", "legacy_topic_id": "rag-basics"})

    assert r.json()["attempted_db_connection"] is True
    assert r.json()["progress_db_reads_enabled"] is True


def test_progress_flag_on_progress_found_when_db_returns_row():
    conn = _make_conn()
    with patch("services.storage_flags.is_progress_db_reads_enabled", return_value=True), \
         patch("services.storage_flags.is_todos_db_reads_enabled",    return_value=False), \
         patch("routes.debug.get_conn", _fake_get_conn(conn)), \
         patch(
             "services.learner_state_read_service.get_topic_progress_from_db",
             return_value=_FAKE_PROGRESS,
         ):
        r = client.get(URL, params={"session_id": "sess-1", "legacy_topic_id": "rag-basics"})

    data = r.json()
    assert data["progress_found"] is True
    assert data["topic_progress"]["learn"] == "done"
    assert data["source"] == "db"


# ── Todos flag on ─────────────────────────────────────────────────────────────

def test_todos_flag_on_db_connection_attempted():
    conn = _make_conn()
    with patch("services.storage_flags.is_progress_db_reads_enabled", return_value=False), \
         patch("services.storage_flags.is_todos_db_reads_enabled",    return_value=True), \
         patch("routes.debug.get_conn", _fake_get_conn(conn)), \
         patch("services.learner_state_read_service.list_todos_from_db", return_value=[]):
        r = client.get(URL, params={"session_id": "sess-1"})

    assert r.json()["attempted_db_connection"] is True
    assert r.json()["todos_db_reads_enabled"] is True


def test_todos_flag_on_todos_found_when_db_returns_rows():
    conn = _make_conn()
    with patch("services.storage_flags.is_progress_db_reads_enabled", return_value=False), \
         patch("services.storage_flags.is_todos_db_reads_enabled",    return_value=True), \
         patch("routes.debug.get_conn", _fake_get_conn(conn)), \
         patch(
             "services.learner_state_read_service.list_todos_from_db",
             return_value=_FAKE_TODOS,
         ):
        r = client.get(URL, params={"session_id": "sess-1"})

    data = r.json()
    assert data["todos_found"] is True
    assert len(data["todos"]) == 1
    assert data["todos"][0]["todo_id"] == "todo-1"


# ── Both flags on ─────────────────────────────────────────────────────────────

def test_both_flags_on_both_reads_attempted():
    conn = _make_conn()
    mock_progress = MagicMock(return_value=_FAKE_PROGRESS)
    mock_todos    = MagicMock(return_value=_FAKE_TODOS)

    with patch("services.storage_flags.is_progress_db_reads_enabled", return_value=True), \
         patch("services.storage_flags.is_todos_db_reads_enabled",    return_value=True), \
         patch("routes.debug.get_conn", _fake_get_conn(conn)), \
         patch("services.learner_state_read_service.get_topic_progress_from_db", mock_progress), \
         patch("services.learner_state_read_service.list_todos_from_db", mock_todos):
        r = client.get(URL, params={"session_id": "sess-1", "legacy_topic_id": "rag-basics"})

    mock_progress.assert_called_once()
    mock_todos.assert_called_once()
    data = r.json()
    assert data["progress_found"] is True
    assert data["todos_found"] is True
    assert data["source"] == "db"


def test_both_flags_on_only_one_conn_opened():
    """Only a single DB connection should be used for both reads."""
    conn = _make_conn()
    connect_calls = []

    def _counting_get_conn():
        @contextmanager
        def _ctx():
            connect_calls.append(1)
            try:
                yield conn
            finally:
                conn.close()
        return _ctx()

    with patch("services.storage_flags.is_progress_db_reads_enabled", return_value=True), \
         patch("services.storage_flags.is_todos_db_reads_enabled",    return_value=True), \
         patch("routes.debug.get_conn", _counting_get_conn), \
         patch("services.learner_state_read_service.get_topic_progress_from_db", return_value=None), \
         patch("services.learner_state_read_service.list_todos_from_db", return_value=[]):
        client.get(URL, params={"session_id": "sess-1", "legacy_topic_id": "rag-basics"})

    assert len(connect_calls) == 1


# ── Missing legacy_topic_id skips progress ────────────────────────────────────

def test_missing_legacy_topic_id_skips_progress_lookup():
    conn = _make_conn()
    mock_progress = MagicMock()

    with patch("services.storage_flags.is_progress_db_reads_enabled", return_value=True), \
         patch("services.storage_flags.is_todos_db_reads_enabled",    return_value=False), \
         patch("routes.debug.get_conn", _fake_get_conn(conn)), \
         patch("services.learner_state_read_service.get_topic_progress_from_db", mock_progress):
        r = client.get(URL, params={"session_id": "sess-1"})

    mock_progress.assert_not_called()
    assert r.json()["progress_found"] is False


def test_missing_legacy_topic_id_adds_note():
    conn = _make_conn()

    with patch("services.storage_flags.is_progress_db_reads_enabled", return_value=True), \
         patch("services.storage_flags.is_todos_db_reads_enabled",    return_value=False), \
         patch("routes.debug.get_conn", _fake_get_conn(conn)), \
         patch("services.learner_state_read_service.get_topic_progress_from_db", return_value=None):
        r = client.get(URL, params={"session_id": "sess-1"})

    notes_text = " ".join(r.json()["notes"]).lower()
    assert "legacy_topic_id" in notes_text
    assert "skipped" in notes_text


# ── Error handling ────────────────────────────────────────────────────────────

def test_db_error_returns_http_200_with_source_error():
    with patch("services.storage_flags.is_progress_db_reads_enabled", return_value=True), \
         patch("services.storage_flags.is_todos_db_reads_enabled",    return_value=False), \
         patch("routes.debug.get_conn", _fake_get_conn_raises(RuntimeError("connection refused"))):
        r = client.get(URL, params={"session_id": "sess-1", "legacy_topic_id": "rag"})

    assert r.status_code == 200
    assert r.json()["source"] == "error"


def test_db_error_error_field_is_safe_string():
    with patch("services.storage_flags.is_progress_db_reads_enabled", return_value=True), \
         patch("services.storage_flags.is_todos_db_reads_enabled",    return_value=False), \
         patch("routes.debug.get_conn", _fake_get_conn_raises(RuntimeError("boom"))):
        r = client.get(URL, params={"session_id": "sess-1", "legacy_topic_id": "rag"})

    data = r.json()
    assert isinstance(data["error"], str)
    assert len(data["error"]) <= 400


def test_db_error_progress_and_todos_are_none():
    with patch("services.storage_flags.is_progress_db_reads_enabled", return_value=True), \
         patch("services.storage_flags.is_todos_db_reads_enabled",    return_value=True), \
         patch("routes.debug.get_conn", _fake_get_conn_raises(RuntimeError("boom"))):
        r = client.get(URL, params={"session_id": "sess-1", "legacy_topic_id": "rag"})

    data = r.json()
    assert data["topic_progress"] is None
    assert data["todos"] is None
    assert data["progress_found"] is False
    assert data["todos_found"] is False


def test_service_error_inside_conn_returns_source_error():
    conn = _make_conn()
    with patch("services.storage_flags.is_progress_db_reads_enabled", return_value=True), \
         patch("services.storage_flags.is_todos_db_reads_enabled",    return_value=False), \
         patch("routes.debug.get_conn", _fake_get_conn(conn)), \
         patch(
             "services.learner_state_read_service.get_topic_progress_from_db",
             side_effect=Exception("query failed"),
         ):
        r = client.get(URL, params={"session_id": "sess-1", "legacy_topic_id": "rag"})

    assert r.status_code == 200
    assert r.json()["source"] == "error"


# ── Connection lifecycle ──────────────────────────────────────────────────────

def test_connection_closed_on_success():
    conn = _make_conn()
    with patch("services.storage_flags.is_progress_db_reads_enabled", return_value=True), \
         patch("services.storage_flags.is_todos_db_reads_enabled",    return_value=False), \
         patch("routes.debug.get_conn", _fake_get_conn(conn)), \
         patch("services.learner_state_read_service.get_topic_progress_from_db", return_value=_FAKE_PROGRESS):
        client.get(URL, params={"session_id": "sess-1", "legacy_topic_id": "rag-basics"})

    conn.close.assert_called_once()


def test_connection_closed_on_service_error():
    conn = _make_conn()
    with patch("services.storage_flags.is_progress_db_reads_enabled", return_value=True), \
         patch("services.storage_flags.is_todos_db_reads_enabled",    return_value=False), \
         patch("routes.debug.get_conn", _fake_get_conn(conn)), \
         patch(
             "services.learner_state_read_service.get_topic_progress_from_db",
             side_effect=Exception("query failed"),
         ):
        client.get(URL, params={"session_id": "sess-1", "legacy_topic_id": "rag"})

    conn.close.assert_called_once()


# ── Security: no secrets ──────────────────────────────────────────────────────

def test_no_database_url_in_disabled_response():
    with patch("services.storage_flags.is_progress_db_reads_enabled", return_value=False), \
         patch("services.storage_flags.is_todos_db_reads_enabled",    return_value=False):
        r = client.get(URL, params={"session_id": "sess-1"})

    body = r.text.lower()
    assert "supabase_database_url" not in body
    assert "postgresql://" not in body
    assert "password" not in body


def test_no_database_url_in_error_response():
    with patch("services.storage_flags.is_progress_db_reads_enabled", return_value=True), \
         patch("services.storage_flags.is_todos_db_reads_enabled",    return_value=False), \
         patch(
             "routes.debug.get_conn",
             _fake_get_conn_raises(
                 RuntimeError("could not connect to postgresql://user:secret@host/db")
             ),
         ):
        r = client.get(URL, params={"session_id": "sess-1", "legacy_topic_id": "rag"})

    assert "SUPABASE_DATABASE_URL" not in r.text
    assert "ANTHROPIC_API_KEY"     not in r.text


def test_no_raw_env_var_names_in_any_response():
    with patch("services.storage_flags.is_progress_db_reads_enabled", return_value=False), \
         patch("services.storage_flags.is_todos_db_reads_enabled",    return_value=False):
        r = client.get(URL, params={"session_id": "sess-1"})

    for forbidden in ("ANTHROPIC_API_KEY", "SUPABASE_DATABASE_URL", "AI2_TEST_MODE"):
        assert forbidden not in r.text, f"Response must not contain {forbidden!r}"


def test_no_private_session_data_fields_in_response():
    with patch("services.storage_flags.is_progress_db_reads_enabled", return_value=False), \
         patch("services.storage_flags.is_todos_db_reads_enabled",    return_value=False):
        r = client.get(URL, params={"session_id": "sess-1"})

    data = r.json()
    for key in ("history", "quiz_scores", "user_id", "session_data"):
        assert key not in data, f"Forbidden key {key!r} in response"


# ── Learner routes untouched ──────────────────────────────────────────────────

def test_learner_get_session_data_not_called():
    with patch("services.storage_flags.is_progress_db_reads_enabled", return_value=False), \
         patch("services.storage_flags.is_todos_db_reads_enabled",    return_value=False), \
         patch("app._get_session_data") as mock_session:
        client.get(URL, params={"session_id": "sess-1"})

    mock_session.assert_not_called()


def test_only_progress_flag_on_todos_service_not_called():
    conn = _make_conn()
    mock_todos = MagicMock()

    with patch("services.storage_flags.is_progress_db_reads_enabled", return_value=True), \
         patch("services.storage_flags.is_todos_db_reads_enabled",    return_value=False), \
         patch("routes.debug.get_conn", _fake_get_conn(conn)), \
         patch("services.learner_state_read_service.get_topic_progress_from_db", return_value=None), \
         patch("services.learner_state_read_service.list_todos_from_db", mock_todos):
        client.get(URL, params={"session_id": "sess-1", "legacy_topic_id": "rag"})

    mock_todos.assert_not_called()


def test_only_todos_flag_on_progress_service_not_called():
    conn = _make_conn()
    mock_progress = MagicMock()

    with patch("services.storage_flags.is_progress_db_reads_enabled", return_value=False), \
         patch("services.storage_flags.is_todos_db_reads_enabled",    return_value=True), \
         patch("routes.debug.get_conn", _fake_get_conn(conn)), \
         patch("services.learner_state_read_service.get_topic_progress_from_db", mock_progress), \
         patch("services.learner_state_read_service.list_todos_from_db", return_value=[]):
        client.get(URL, params={"session_id": "sess-1", "legacy_topic_id": "rag"})

    mock_progress.assert_not_called()
