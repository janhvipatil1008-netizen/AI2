"""Tests for services/learner_state_read_service.py.

Verifies:
- Module imports without opening a DB connection.
- Normalizers correctly map DB column names to output keys and apply defaults.
- Low-level read functions delegate to the right repository and normalize results.
- maybe_* helpers respect their feature flags and guard against missing inputs.
- The service never calls database.pool._connect or reads os.environ directly.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from unittest.mock import patch, MagicMock

import services.learner_state_read_service as service


# ── Import safety ─────────────────────────────────────────────────────────────

def test_module_imports_without_db_connection():
    with patch(
        "database.pool._connect",
        side_effect=AssertionError("_connect must not be called at import"),
    ) as mock_connect:
        importlib.reload(service)

    mock_connect.assert_not_called()


# ── normalize_topic_progress_row ──────────────────────────────────────────────

def test_normalize_topic_progress_row_maps_all_five_statuses():
    row = {
        "learn_status":              "done",
        "quiz_status":               "in_progress",
        "portfolio_task_status":     "not_started",
        "interview_practice_status": "done",
        "reflection_status":         "in_progress",
        "completion_percent":        60,
        "legacy_topic_id":           "rag-basics",
        "metadata":                  {},
    }

    result = service.normalize_topic_progress_row(row)

    assert result["learn"]              == "done"
    assert result["quiz"]               == "in_progress"
    assert result["portfolio_task"]     == "not_started"
    assert result["interview_practice"] == "done"
    assert result["reflection"]         == "in_progress"


def test_normalize_topic_progress_row_defaults_missing_statuses_to_not_started():
    result = service.normalize_topic_progress_row({})

    assert result["learn"]              == "not_started"
    assert result["quiz"]               == "not_started"
    assert result["portfolio_task"]     == "not_started"
    assert result["interview_practice"] == "not_started"
    assert result["reflection"]         == "not_started"


def test_normalize_topic_progress_row_defaults_completion_percent_to_zero():
    result = service.normalize_topic_progress_row({})

    assert result["completion_percent"] == 0


def test_normalize_topic_progress_row_preserves_completion_percent():
    result = service.normalize_topic_progress_row({"completion_percent": 80})

    assert result["completion_percent"] == 80


def test_normalize_topic_progress_row_preserves_legacy_topic_id():
    result = service.normalize_topic_progress_row({"legacy_topic_id": "topic-abc"})

    assert result["legacy_topic_id"] == "topic-abc"


def test_normalize_topic_progress_row_parses_json_string_metadata():
    result = service.normalize_topic_progress_row(
        {"metadata": '{"source": "write_through"}'}
    )

    assert result["metadata"] == {"source": "write_through"}


def test_normalize_topic_progress_row_handles_none_metadata():
    result = service.normalize_topic_progress_row({"metadata": None})

    assert result["metadata"] == {}


# ── normalize_todo_row ────────────────────────────────────────────────────────

def test_normalize_todo_row_maps_todo_key_to_todo_id():
    row = {"todo_key": "todo-abc", "title": "Read the paper"}

    result = service.normalize_todo_row(row)

    assert result["todo_id"] == "todo-abc"


def test_normalize_todo_row_maps_legacy_linked_topic_id_to_linked_topic_id():
    row = {"legacy_linked_topic_id": "rag-basics"}

    result = service.normalize_todo_row(row)

    assert result["linked_topic_id"] == "rag-basics"


def test_normalize_todo_row_maps_all_fields():
    row = {
        "todo_key":               "todo-1",
        "title":                  "Review RAG",
        "todo_type":              "daily",
        "status":                 "todo",
        "legacy_linked_topic_id": "rag-basics",
        "created_by":             "agent",
        "due_label":              "today",
        "created_at":             "2026-01-01T00:00:00",
        "updated_at":             "2026-01-02T00:00:00",
    }

    result = service.normalize_todo_row(row)

    assert result["todo_id"]         == "todo-1"
    assert result["title"]           == "Review RAG"
    assert result["todo_type"]       == "daily"
    assert result["status"]          == "todo"
    assert result["linked_topic_id"] == "rag-basics"
    assert result["created_by"]      == "agent"
    assert result["due_label"]       == "today"
    assert result["created_at"]      == "2026-01-01T00:00:00"
    assert result["updated_at"]      == "2026-01-02T00:00:00"


def test_normalize_todo_row_handles_missing_optional_fields():
    result = service.normalize_todo_row({})

    assert result["todo_id"]         == ""
    assert result["title"]           == ""
    assert result["todo_type"]       == ""
    assert result["status"]          == ""
    assert result["linked_topic_id"] == ""
    assert result["created_by"]      == ""
    assert result["due_label"]       == ""
    assert result["created_at"]      == ""
    assert result["updated_at"]      == ""


# ── get_topic_progress_from_db ────────────────────────────────────────────────

def test_get_topic_progress_from_db_calls_repository_and_normalizes():
    conn = object()
    raw_row = {
        "learn_status":              "done",
        "quiz_status":               "not_started",
        "portfolio_task_status":     "not_started",
        "interview_practice_status": "not_started",
        "reflection_status":         "not_started",
        "completion_percent":        40,
        "legacy_topic_id":           "rag-basics",
        "metadata":                  {},
    }

    with patch(
        "repositories.progress_repository.get_topic_progress_by_legacy_id",
        return_value=raw_row,
    ) as mock_repo:
        result = service.get_topic_progress_from_db(
            conn,
            session_id="sess-1",
            legacy_topic_id="rag-basics",
        )

    mock_repo.assert_called_once_with(conn, session_id="sess-1", legacy_topic_id="rag-basics")
    assert result["learn"]             == "done"
    assert result["completion_percent"] == 40


def test_get_topic_progress_from_db_returns_none_when_repository_returns_none():
    with patch(
        "repositories.progress_repository.get_topic_progress_by_legacy_id",
        return_value=None,
    ):
        result = service.get_topic_progress_from_db(
            object(),
            session_id="sess-1",
            legacy_topic_id="missing-topic",
        )

    assert result is None


# ── list_todos_from_db ────────────────────────────────────────────────────────

def test_list_todos_from_db_calls_repository_and_normalizes_rows():
    conn = object()
    raw_rows = [
        {"todo_key": "todo-1", "title": "Read paper", "legacy_linked_topic_id": "rag"},
        {"todo_key": "todo-2", "title": "Build demo", "legacy_linked_topic_id": ""},
    ]

    with patch(
        "repositories.todos_repository.list_todos_for_session",
        return_value=raw_rows,
    ) as mock_repo:
        result = service.list_todos_from_db(conn, session_id="sess-1")

    mock_repo.assert_called_once_with(conn, "sess-1")
    assert len(result) == 2
    assert result[0]["todo_id"] == "todo-1"
    assert result[1]["todo_id"] == "todo-2"
    assert result[0]["linked_topic_id"] == "rag"


def test_list_todos_from_db_returns_empty_list_when_repository_returns_empty():
    with patch(
        "repositories.todos_repository.list_todos_for_session",
        return_value=[],
    ):
        result = service.list_todos_from_db(object(), session_id="sess-1")

    assert result == []


# ── maybe_get_topic_progress_from_db ─────────────────────────────────────────

def test_maybe_get_topic_progress_from_db_returns_none_when_flag_disabled():
    with patch(
        "services.learner_state_read_service.is_progress_db_reads_enabled",
        return_value=False,
    ), patch(
        "services.learner_state_read_service.get_topic_progress_from_db",
    ) as mock_get:
        result = service.maybe_get_topic_progress_from_db(
            object(),
            session_id="sess-1",
            legacy_topic_id="rag",
        )

    assert result is None
    mock_get.assert_not_called()


def test_maybe_get_topic_progress_from_db_returns_none_when_conn_is_none():
    with patch(
        "services.learner_state_read_service.is_progress_db_reads_enabled",
        return_value=True,
    ), patch(
        "services.learner_state_read_service.get_topic_progress_from_db",
    ) as mock_get:
        result = service.maybe_get_topic_progress_from_db(
            None,
            session_id="sess-1",
            legacy_topic_id="rag",
        )

    assert result is None
    mock_get.assert_not_called()


def test_maybe_get_topic_progress_from_db_returns_none_when_session_id_empty():
    with patch(
        "services.learner_state_read_service.is_progress_db_reads_enabled",
        return_value=True,
    ), patch(
        "services.learner_state_read_service.get_topic_progress_from_db",
    ) as mock_get:
        result = service.maybe_get_topic_progress_from_db(
            object(),
            session_id="",
            legacy_topic_id="rag",
        )

    assert result is None
    mock_get.assert_not_called()


def test_maybe_get_topic_progress_from_db_returns_none_when_legacy_topic_id_empty():
    with patch(
        "services.learner_state_read_service.is_progress_db_reads_enabled",
        return_value=True,
    ), patch(
        "services.learner_state_read_service.get_topic_progress_from_db",
    ) as mock_get:
        result = service.maybe_get_topic_progress_from_db(
            object(),
            session_id="sess-1",
            legacy_topic_id="",
        )

    assert result is None
    mock_get.assert_not_called()


def test_maybe_get_topic_progress_from_db_calls_db_when_flag_enabled():
    conn = object()
    expected = {"learn": "done", "completion_percent": 40}

    with patch(
        "services.learner_state_read_service.is_progress_db_reads_enabled",
        return_value=True,
    ), patch(
        "services.learner_state_read_service.get_topic_progress_from_db",
        return_value=expected,
    ) as mock_get:
        result = service.maybe_get_topic_progress_from_db(
            conn,
            session_id="sess-1",
            legacy_topic_id="rag",
        )

    assert result == expected
    mock_get.assert_called_once_with(conn, session_id="sess-1", legacy_topic_id="rag")


# ── maybe_list_todos_from_db ──────────────────────────────────────────────────

def test_maybe_list_todos_from_db_returns_none_when_flag_disabled():
    with patch(
        "services.learner_state_read_service.is_todos_db_reads_enabled",
        return_value=False,
    ), patch(
        "services.learner_state_read_service.list_todos_from_db",
    ) as mock_list:
        result = service.maybe_list_todos_from_db(object(), session_id="sess-1")

    assert result is None
    mock_list.assert_not_called()


def test_maybe_list_todos_from_db_returns_none_when_conn_is_none():
    with patch(
        "services.learner_state_read_service.is_todos_db_reads_enabled",
        return_value=True,
    ), patch(
        "services.learner_state_read_service.list_todos_from_db",
    ) as mock_list:
        result = service.maybe_list_todos_from_db(None, session_id="sess-1")

    assert result is None
    mock_list.assert_not_called()


def test_maybe_list_todos_from_db_returns_none_when_session_id_empty():
    with patch(
        "services.learner_state_read_service.is_todos_db_reads_enabled",
        return_value=True,
    ), patch(
        "services.learner_state_read_service.list_todos_from_db",
    ) as mock_list:
        result = service.maybe_list_todos_from_db(object(), session_id="")

    assert result is None
    mock_list.assert_not_called()


def test_maybe_list_todos_from_db_calls_db_when_flag_enabled():
    conn = object()
    expected = [{"todo_id": "todo-1"}]

    with patch(
        "services.learner_state_read_service.is_todos_db_reads_enabled",
        return_value=True,
    ), patch(
        "services.learner_state_read_service.list_todos_from_db",
        return_value=expected,
    ) as mock_list:
        result = service.maybe_list_todos_from_db(conn, session_id="sess-1")

    assert result == expected
    mock_list.assert_called_once_with(conn, session_id="sess-1")


def test_maybe_list_todos_from_db_returns_empty_list_when_db_has_no_todos():
    conn = object()

    with patch(
        "services.learner_state_read_service.is_todos_db_reads_enabled",
        return_value=True,
    ), patch(
        "services.learner_state_read_service.list_todos_from_db",
        return_value=[],
    ):
        result = service.maybe_list_todos_from_db(conn, session_id="sess-1")

    assert result == []


# ── Security constraints ──────────────────────────────────────────────────────

def test_service_does_not_call_database_pool_connect():
    with patch(
        "database.pool._connect",
        side_effect=AssertionError("_connect must not be called"),
    ) as mock_connect:
        with patch(
            "services.learner_state_read_service.is_progress_db_reads_enabled",
            return_value=False,
        ), patch(
            "services.learner_state_read_service.is_todos_db_reads_enabled",
            return_value=False,
        ):
            assert service.maybe_get_topic_progress_from_db(
                object(), session_id="sess-1", legacy_topic_id="rag"
            ) is None
            assert service.maybe_list_todos_from_db(
                object(), session_id="sess-1"
            ) is None

    mock_connect.assert_not_called()


def test_service_does_not_read_os_environ_directly():
    source = Path("services/learner_state_read_service.py").read_text(encoding="utf-8")

    assert "import os" not in source
    assert "os.environ" not in source
    assert "os.getenv" not in source
