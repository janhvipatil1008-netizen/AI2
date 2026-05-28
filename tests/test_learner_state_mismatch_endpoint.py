"""Tests for GET /debug/learner-state-mismatch-check.

Verifies that the endpoint:
- exists and returns 200
- loads the session but never saves it
- skips DB entirely when both read flags are off
- opens exactly one connection when either flag is on
- reads progress and/or todos only for the enabled flags
- calls compare_learner_state with the data it read
- skips progress read when legacy_topic_id is absent and adds a note
- handles DB errors safely (HTTP 200, truncated message, no secrets)
- always closes the connection (success and error paths)
- does not expose secrets, raw env vars, or private session data
"""

from __future__ import annotations

import os

os.environ["AI2_TEST_MODE"] = "1"
os.environ["ANTHROPIC_API_KEY"] = "test-key"

from contextlib import contextmanager
from unittest.mock import MagicMock, call, patch

from fastapi.testclient import TestClient

from config import CareerTrack
from context.session import SessionContext
from app import app

client = TestClient(app)

URL = "/debug/learner-state-mismatch-check"

# ── Fake session helpers ──────────────────────────────────────────────────────

def _make_session(**kwargs) -> SessionContext:
    return SessionContext(track=CareerTrack.AI_PM, **kwargs)


def _fake_session_data(session=None) -> dict:
    s = session or _make_session()
    return {"session": s, "orch": None, "client": None, "profile": None}


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
        "title":           "Read paper",
        "todo_type":       "daily",
        "status":          "todo",
        "linked_topic_id": "",
    }
]

_FAKE_COMPARISON = {
    "matches":     True,
    "comparisons": [],
}


# ── Endpoint existence ────────────────────────────────────────────────────────

def test_endpoint_exists_returns_200():
    with patch("routes.deps.get_session_data", return_value=_fake_session_data()), \
         patch("services.storage_flags.is_progress_db_reads_enabled", return_value=False), \
         patch("services.storage_flags.is_todos_db_reads_enabled",    return_value=False):
        r = client.get(URL, params={"session_id": "sess-1"})
    assert r.status_code == 200


def test_endpoint_returns_json():
    with patch("routes.deps.get_session_data", return_value=_fake_session_data()), \
         patch("services.storage_flags.is_progress_db_reads_enabled", return_value=False), \
         patch("services.storage_flags.is_todos_db_reads_enabled",    return_value=False):
        r = client.get(URL, params={"session_id": "sess-1"})
    assert r.headers["content-type"].startswith("application/json")


def test_response_has_all_required_keys():
    with patch("routes.deps.get_session_data", return_value=_fake_session_data()), \
         patch("services.storage_flags.is_progress_db_reads_enabled", return_value=False), \
         patch("services.storage_flags.is_todos_db_reads_enabled",    return_value=False):
        r = client.get(URL, params={"session_id": "sess-1"})
    required = {
        "session_id", "legacy_topic_id",
        "progress_db_reads_enabled", "todos_db_reads_enabled",
        "attempted_db_connection", "source", "matches",
        "comparison", "error", "notes",
    }
    assert required.issubset(r.json().keys())


# ── Both flags off ────────────────────────────────────────────────────────────

def test_both_flags_off_no_db_connection_attempted():
    with patch("routes.deps.get_session_data", return_value=_fake_session_data()), \
         patch("database.pool._connect", side_effect=AssertionError("must not connect")) as mock_connect, \
         patch("services.storage_flags.is_progress_db_reads_enabled", return_value=False), \
         patch("services.storage_flags.is_todos_db_reads_enabled",    return_value=False):
        r = client.get(URL, params={"session_id": "sess-1"})

    mock_connect.assert_not_called()
    assert r.json()["attempted_db_connection"] is False


def test_both_flags_off_source_is_session_only():
    with patch("routes.deps.get_session_data", return_value=_fake_session_data()), \
         patch("services.storage_flags.is_progress_db_reads_enabled", return_value=False), \
         patch("services.storage_flags.is_todos_db_reads_enabled",    return_value=False):
        r = client.get(URL, params={"session_id": "sess-1"})
    assert r.json()["source"] == "session_only"


def test_both_flags_off_comparison_is_none():
    with patch("routes.deps.get_session_data", return_value=_fake_session_data()), \
         patch("services.storage_flags.is_progress_db_reads_enabled", return_value=False), \
         patch("services.storage_flags.is_todos_db_reads_enabled",    return_value=False):
        r = client.get(URL, params={"session_id": "sess-1"})
    data = r.json()
    assert data["comparison"] is None
    assert data["matches"] is None


def test_both_flags_off_notes_mention_read_flags():
    with patch("routes.deps.get_session_data", return_value=_fake_session_data()), \
         patch("services.storage_flags.is_progress_db_reads_enabled", return_value=False), \
         patch("services.storage_flags.is_todos_db_reads_enabled",    return_value=False):
        r = client.get(URL, params={"session_id": "sess-1"})
    notes_text = " ".join(r.json()["notes"]).lower()
    assert "progress" in notes_text or "todos" in notes_text


# ── Progress flag on ──────────────────────────────────────────────────────────

def test_progress_flag_on_db_connection_attempted():
    conn = _make_conn()
    with patch("routes.deps.get_session_data", return_value=_fake_session_data()), \
         patch("services.storage_flags.is_progress_db_reads_enabled", return_value=True), \
         patch("services.storage_flags.is_todos_db_reads_enabled",    return_value=False), \
         patch("routes.debug.get_conn", _fake_get_conn(conn)), \
         patch("services.learner_state_read_service.get_topic_progress_from_db", return_value=None), \
         patch("services.state_mismatch_service.compare_learner_state", return_value=_FAKE_COMPARISON):
        r = client.get(URL, params={"session_id": "sess-1", "legacy_topic_id": "rag"})

    assert r.json()["attempted_db_connection"] is True
    assert r.json()["source"] == "db_compare"


# ── Todos flag on ─────────────────────────────────────────────────────────────

def test_todos_flag_on_db_connection_attempted():
    conn = _make_conn()
    with patch("routes.deps.get_session_data", return_value=_fake_session_data()), \
         patch("services.storage_flags.is_progress_db_reads_enabled", return_value=False), \
         patch("services.storage_flags.is_todos_db_reads_enabled",    return_value=True), \
         patch("routes.debug.get_conn", _fake_get_conn(conn)), \
         patch("services.learner_state_read_service.list_todos_from_db", return_value=[]), \
         patch("services.state_mismatch_service.compare_learner_state", return_value=_FAKE_COMPARISON):
        r = client.get(URL, params={"session_id": "sess-1"})

    assert r.json()["attempted_db_connection"] is True


# ── Both flags on ─────────────────────────────────────────────────────────────

def test_both_flags_on_both_db_reads_attempted():
    conn = _make_conn()
    mock_progress = MagicMock(return_value=_FAKE_PROGRESS)
    mock_todos    = MagicMock(return_value=_FAKE_TODOS)

    with patch("routes.deps.get_session_data", return_value=_fake_session_data()), \
         patch("services.storage_flags.is_progress_db_reads_enabled", return_value=True), \
         patch("services.storage_flags.is_todos_db_reads_enabled",    return_value=True), \
         patch("routes.debug.get_conn", _fake_get_conn(conn)), \
         patch("services.learner_state_read_service.get_topic_progress_from_db", mock_progress), \
         patch("services.learner_state_read_service.list_todos_from_db", mock_todos), \
         patch("services.state_mismatch_service.compare_learner_state", return_value=_FAKE_COMPARISON):
        r = client.get(URL, params={"session_id": "sess-1", "legacy_topic_id": "rag"})

    mock_progress.assert_called_once()
    mock_todos.assert_called_once()
    assert r.json()["source"] == "db_compare"


def test_compare_learner_state_called_with_expected_values():
    conn = _make_conn()
    session = _make_session()
    mock_compare = MagicMock(return_value=_FAKE_COMPARISON)

    with patch("routes.deps.get_session_data", return_value=_fake_session_data(session)), \
         patch("services.storage_flags.is_progress_db_reads_enabled", return_value=True), \
         patch("services.storage_flags.is_todos_db_reads_enabled",    return_value=True), \
         patch("routes.debug.get_conn", _fake_get_conn(conn)), \
         patch("services.learner_state_read_service.get_topic_progress_from_db", return_value=_FAKE_PROGRESS), \
         patch("services.learner_state_read_service.list_todos_from_db", return_value=_FAKE_TODOS), \
         patch("services.state_mismatch_service.compare_learner_state", mock_compare):
        client.get(URL, params={"session_id": "sess-1", "legacy_topic_id": "rag"})

    mock_compare.assert_called_once()
    call_kwargs = mock_compare.call_args.kwargs
    assert call_kwargs["session"] is session
    assert call_kwargs["legacy_topic_id"] == "rag"
    assert call_kwargs["db_progress"] == _FAKE_PROGRESS
    assert call_kwargs["db_todos"] == _FAKE_TODOS


def test_comparison_result_in_response():
    conn = _make_conn()
    with patch("routes.deps.get_session_data", return_value=_fake_session_data()), \
         patch("services.storage_flags.is_progress_db_reads_enabled", return_value=True), \
         patch("services.storage_flags.is_todos_db_reads_enabled",    return_value=False), \
         patch("routes.debug.get_conn", _fake_get_conn(conn)), \
         patch("services.learner_state_read_service.get_topic_progress_from_db", return_value=None), \
         patch("services.state_mismatch_service.compare_learner_state", return_value=_FAKE_COMPARISON):
        r = client.get(URL, params={"session_id": "sess-1", "legacy_topic_id": "rag"})

    data = r.json()
    assert data["comparison"] == _FAKE_COMPARISON
    assert data["matches"] == _FAKE_COMPARISON["matches"]


# ── Missing legacy_topic_id ───────────────────────────────────────────────────

def test_missing_legacy_topic_id_skips_progress_read():
    conn = _make_conn()
    mock_progress = MagicMock()

    with patch("routes.deps.get_session_data", return_value=_fake_session_data()), \
         patch("services.storage_flags.is_progress_db_reads_enabled", return_value=True), \
         patch("services.storage_flags.is_todos_db_reads_enabled",    return_value=False), \
         patch("routes.debug.get_conn", _fake_get_conn(conn)), \
         patch("services.learner_state_read_service.get_topic_progress_from_db", mock_progress), \
         patch("services.state_mismatch_service.compare_learner_state", return_value=_FAKE_COMPARISON):
        r = client.get(URL, params={"session_id": "sess-1"})

    mock_progress.assert_not_called()


def test_missing_legacy_topic_id_adds_note():
    conn = _make_conn()
    with patch("routes.deps.get_session_data", return_value=_fake_session_data()), \
         patch("services.storage_flags.is_progress_db_reads_enabled", return_value=True), \
         patch("services.storage_flags.is_todos_db_reads_enabled",    return_value=False), \
         patch("routes.debug.get_conn", _fake_get_conn(conn)), \
         patch("services.learner_state_read_service.get_topic_progress_from_db", return_value=None), \
         patch("services.state_mismatch_service.compare_learner_state", return_value=_FAKE_COMPARISON):
        r = client.get(URL, params={"session_id": "sess-1"})

    notes_text = " ".join(r.json()["notes"]).lower()
    assert "legacy_topic_id" in notes_text
    assert "skipped" in notes_text


# ── Error handling ────────────────────────────────────────────────────────────

def test_db_error_returns_http_200_source_error():
    with patch("routes.deps.get_session_data", return_value=_fake_session_data()), \
         patch("services.storage_flags.is_progress_db_reads_enabled", return_value=True), \
         patch("services.storage_flags.is_todos_db_reads_enabled",    return_value=False), \
         patch("routes.debug.get_conn", _fake_get_conn_raises(RuntimeError("connection refused"))):
        r = client.get(URL, params={"session_id": "sess-1", "legacy_topic_id": "rag"})

    assert r.status_code == 200
    assert r.json()["source"] == "error"


def test_db_error_error_field_is_safe_string():
    with patch("routes.deps.get_session_data", return_value=_fake_session_data()), \
         patch("services.storage_flags.is_progress_db_reads_enabled", return_value=True), \
         patch("services.storage_flags.is_todos_db_reads_enabled",    return_value=False), \
         patch("routes.debug.get_conn", _fake_get_conn_raises(RuntimeError("boom"))):
        r = client.get(URL, params={"session_id": "sess-1", "legacy_topic_id": "rag"})

    data = r.json()
    assert isinstance(data["error"], str)
    assert len(data["error"]) <= 400


def test_db_error_comparison_is_none():
    with patch("routes.deps.get_session_data", return_value=_fake_session_data()), \
         patch("services.storage_flags.is_progress_db_reads_enabled", return_value=True), \
         patch("services.storage_flags.is_todos_db_reads_enabled",    return_value=False), \
         patch("routes.debug.get_conn", _fake_get_conn_raises(RuntimeError("boom"))):
        r = client.get(URL, params={"session_id": "sess-1", "legacy_topic_id": "rag"})

    data = r.json()
    assert data["comparison"] is None
    assert data["matches"] is None


def test_service_error_inside_conn_returns_source_error():
    conn = _make_conn()
    with patch("routes.deps.get_session_data", return_value=_fake_session_data()), \
         patch("services.storage_flags.is_progress_db_reads_enabled", return_value=True), \
         patch("services.storage_flags.is_todos_db_reads_enabled",    return_value=False), \
         patch("routes.debug.get_conn", _fake_get_conn(conn)), \
         patch("services.learner_state_read_service.get_topic_progress_from_db",
               side_effect=Exception("query failed")):
        r = client.get(URL, params={"session_id": "sess-1", "legacy_topic_id": "rag"})

    assert r.status_code == 200
    assert r.json()["source"] == "error"


# ── Connection lifecycle ──────────────────────────────────────────────────────

def test_connection_closed_on_success():
    conn = _make_conn()
    with patch("routes.deps.get_session_data", return_value=_fake_session_data()), \
         patch("services.storage_flags.is_progress_db_reads_enabled", return_value=True), \
         patch("services.storage_flags.is_todos_db_reads_enabled",    return_value=False), \
         patch("routes.debug.get_conn", _fake_get_conn(conn)), \
         patch("services.learner_state_read_service.get_topic_progress_from_db", return_value=_FAKE_PROGRESS), \
         patch("services.state_mismatch_service.compare_learner_state", return_value=_FAKE_COMPARISON):
        client.get(URL, params={"session_id": "sess-1", "legacy_topic_id": "rag"})

    conn.close.assert_called_once()


def test_connection_closed_on_service_error():
    conn = _make_conn()
    with patch("routes.deps.get_session_data", return_value=_fake_session_data()), \
         patch("services.storage_flags.is_progress_db_reads_enabled", return_value=True), \
         patch("services.storage_flags.is_todos_db_reads_enabled",    return_value=False), \
         patch("routes.debug.get_conn", _fake_get_conn(conn)), \
         patch("services.learner_state_read_service.get_topic_progress_from_db",
               side_effect=Exception("query failed")):
        client.get(URL, params={"session_id": "sess-1", "legacy_topic_id": "rag"})

    conn.close.assert_called_once()


# ── Save session never called ─────────────────────────────────────────────────

def test_endpoint_does_not_call_save_session():
    conn = _make_conn()
    with patch("routes.deps.get_session_data", return_value=_fake_session_data()), \
         patch("services.storage_flags.is_progress_db_reads_enabled", return_value=True), \
         patch("services.storage_flags.is_todos_db_reads_enabled",    return_value=False), \
         patch("routes.debug.get_conn", _fake_get_conn(conn)), \
         patch("services.learner_state_read_service.get_topic_progress_from_db", return_value=None), \
         patch("services.state_mismatch_service.compare_learner_state", return_value=_FAKE_COMPARISON), \
         patch("app._save_session") as mock_save:
        client.get(URL, params={"session_id": "sess-1", "legacy_topic_id": "rag"})

    mock_save.assert_not_called()


def test_endpoint_does_not_call_save_session_when_flags_off():
    with patch("routes.deps.get_session_data", return_value=_fake_session_data()), \
         patch("services.storage_flags.is_progress_db_reads_enabled", return_value=False), \
         patch("services.storage_flags.is_todos_db_reads_enabled",    return_value=False), \
         patch("app._save_session") as mock_save:
        client.get(URL, params={"session_id": "sess-1"})

    mock_save.assert_not_called()


# ── Security: no secrets ──────────────────────────────────────────────────────

def test_no_raw_env_var_names_in_flag_off_response():
    with patch("routes.deps.get_session_data", return_value=_fake_session_data()), \
         patch("services.storage_flags.is_progress_db_reads_enabled", return_value=False), \
         patch("services.storage_flags.is_todos_db_reads_enabled",    return_value=False):
        r = client.get(URL, params={"session_id": "sess-1"})

    for forbidden in ("ANTHROPIC_API_KEY", "SUPABASE_DATABASE_URL", "AI2_TEST_MODE"):
        assert forbidden not in r.text, f"Response must not contain {forbidden!r}"


def test_no_database_url_in_error_response():
    with patch("routes.deps.get_session_data", return_value=_fake_session_data()), \
         patch("services.storage_flags.is_progress_db_reads_enabled", return_value=True), \
         patch("services.storage_flags.is_todos_db_reads_enabled",    return_value=False), \
         patch("routes.debug.get_conn", _fake_get_conn_raises(
             RuntimeError("could not connect: postgresql://user:secret@host/db")
         )):
        r = client.get(URL, params={"session_id": "sess-1", "legacy_topic_id": "rag"})

    assert "SUPABASE_DATABASE_URL" not in r.text
    assert "ANTHROPIC_API_KEY"     not in r.text


def test_no_private_session_fields_in_response():
    with patch("routes.deps.get_session_data", return_value=_fake_session_data()), \
         patch("services.storage_flags.is_progress_db_reads_enabled", return_value=False), \
         patch("services.storage_flags.is_todos_db_reads_enabled",    return_value=False):
        r = client.get(URL, params={"session_id": "sess-1"})

    data = r.json()
    for key in ("history", "quiz_scores", "session_data",
                "generated_topic_content", "portfolio_submissions"):
        assert key not in data, f"Private key {key!r} must not appear in response"


# ── Session_id echoed correctly ───────────────────────────────────────────────

def test_session_id_reflected_in_response():
    with patch("routes.deps.get_session_data", return_value=_fake_session_data()), \
         patch("services.storage_flags.is_progress_db_reads_enabled", return_value=False), \
         patch("services.storage_flags.is_todos_db_reads_enabled",    return_value=False):
        r = client.get(URL, params={"session_id": "my-test-session"})

    assert r.json()["session_id"] == "my-test-session"
