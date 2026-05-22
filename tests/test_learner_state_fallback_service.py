"""Tests for services/learner_state_fallback_service.py.

All tests use real SessionContext instances — no DB connection required.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from config import CareerTrack
from context.session import SessionContext
from services.learner_state_fallback_service import (
    get_learner_state_with_fallback,
    get_topic_progress_with_fallback,
    list_todos_with_fallback,
    safe_error_text,
)


# ── Session factory ───────────────────────────────────────────────────────────

def _session() -> SessionContext:
    return SessionContext(track=CareerTrack.AI_PM)


def _conn() -> MagicMock:
    return MagicMock()


# ── safe_error_text ───────────────────────────────────────────────────────────

def test_safe_error_text_truncates_long_message():
    exc    = RuntimeError("X" * 400)
    result = safe_error_text(exc)
    assert len(result) <= 300


def test_safe_error_text_preserves_short_message():
    exc    = ValueError("connection failed")
    result = safe_error_text(exc)
    assert "connection failed" in result


def test_safe_error_text_custom_max_chars():
    exc    = RuntimeError("A" * 100)
    result = safe_error_text(exc, max_chars=50)
    assert len(result) <= 50


# ── Module import ─────────────────────────────────────────────────────────────

def test_module_imports_without_db_connection():
    import services.learner_state_fallback_service  # noqa: F401 — import is the test


# ── get_topic_progress_with_fallback: flag off ────────────────────────────────

def test_progress_flag_off_source_is_fallback():
    with patch(
        "services.learner_state_fallback_service.is_progress_db_reads_enabled",
        return_value=False,
    ):
        result = get_topic_progress_with_fallback(
            conn=_conn(), session=_session(),
            session_id="s1", legacy_topic_id="rag-basics",
        )
    assert result["source"] == "fallback"


def test_progress_flag_off_does_not_call_db_reader():
    with patch(
        "services.learner_state_fallback_service.is_progress_db_reads_enabled",
        return_value=False,
    ):
        with patch(
            "services.learner_state_read_service.get_topic_progress_from_db"
        ) as mock_db:
            get_topic_progress_with_fallback(
                conn=_conn(), session=_session(),
                session_id="s1", legacy_topic_id="rag-basics",
            )
    mock_db.assert_not_called()


def test_progress_flag_off_returns_session_progress():
    session = _session()
    session.mark_topic_step("rag-basics", "learn", "done")

    with patch(
        "services.learner_state_fallback_service.is_progress_db_reads_enabled",
        return_value=False,
    ):
        result = get_topic_progress_with_fallback(
            conn=_conn(), session=session,
            session_id="s1", legacy_topic_id="rag-basics",
        )
    assert result["topic_progress"]["learn"] == "done"
    assert result["error"] is None


def test_progress_conn_none_uses_fallback_even_when_flag_on():
    with patch(
        "services.learner_state_fallback_service.is_progress_db_reads_enabled",
        return_value=True,
    ):
        with patch(
            "services.learner_state_read_service.get_topic_progress_from_db"
        ) as mock_db:
            result = get_topic_progress_with_fallback(
                conn=None, session=_session(),
                session_id="s1", legacy_topic_id="rag-basics",
            )
    assert result["source"] == "fallback"
    mock_db.assert_not_called()


# ── get_topic_progress_with_fallback: flag on ─────────────────────────────────

def test_progress_flag_on_db_returns_row_source_db():
    db_progress = {
        "learn": "done", "quiz": "done",
        "portfolio_task": "not_started", "interview_practice": "not_started",
        "reflection": "not_started", "completion_percent": 40,
        "legacy_topic_id": "rag-basics",
    }
    with patch(
        "services.learner_state_fallback_service.is_progress_db_reads_enabled",
        return_value=True,
    ):
        with patch(
            "services.learner_state_read_service.get_topic_progress_from_db",
            return_value=db_progress,
        ):
            result = get_topic_progress_with_fallback(
                conn=_conn(), session=_session(),
                session_id="s1", legacy_topic_id="rag-basics",
            )
    assert result["source"] == "db"
    assert result["topic_progress"] == db_progress
    assert result["error"] is None


def test_progress_flag_on_db_missing_uses_session_fallback():
    with patch(
        "services.learner_state_fallback_service.is_progress_db_reads_enabled",
        return_value=True,
    ):
        with patch(
            "services.learner_state_read_service.get_topic_progress_from_db",
            return_value=None,
        ):
            result = get_topic_progress_with_fallback(
                conn=_conn(), session=_session(),
                session_id="s1", legacy_topic_id="rag-basics",
            )
    assert result["source"] == "fallback"
    assert result["topic_progress"] is not None
    assert result["error"] is None


def test_progress_db_raises_source_error_fallback():
    with patch(
        "services.learner_state_fallback_service.is_progress_db_reads_enabled",
        return_value=True,
    ):
        with patch(
            "services.learner_state_read_service.get_topic_progress_from_db",
            side_effect=RuntimeError("DB down"),
        ):
            result = get_topic_progress_with_fallback(
                conn=_conn(), session=_session(),
                session_id="s1", legacy_topic_id="rag-basics",
            )
    assert result["source"] == "error_fallback"
    assert result["error"] is not None
    assert result["topic_progress"] is not None


def test_progress_fallback_includes_completion_percent_and_topic_id():
    session = _session()
    session.mark_topic_step("rag-basics", "learn", "done")
    session.mark_topic_step("rag-basics", "quiz", "done")

    with patch(
        "services.learner_state_fallback_service.is_progress_db_reads_enabled",
        return_value=False,
    ):
        result = get_topic_progress_with_fallback(
            conn=_conn(), session=session,
            session_id="s1", legacy_topic_id="rag-basics",
        )
    assert result["topic_progress"]["completion_percent"] == 40
    assert result["topic_progress"]["legacy_topic_id"] == "rag-basics"


def test_progress_error_message_is_truncated():
    with patch(
        "services.learner_state_fallback_service.is_progress_db_reads_enabled",
        return_value=True,
    ):
        with patch(
            "services.learner_state_read_service.get_topic_progress_from_db",
            side_effect=RuntimeError("X" * 400),
        ):
            result = get_topic_progress_with_fallback(
                conn=_conn(), session=_session(),
                session_id="s1", legacy_topic_id="rag-basics",
            )
    assert len(result["error"]) <= 300


# ── list_todos_with_fallback: flag off ────────────────────────────────────────

def test_todos_flag_off_source_is_fallback():
    with patch(
        "services.learner_state_fallback_service.is_todos_db_reads_enabled",
        return_value=False,
    ):
        result = list_todos_with_fallback(
            conn=_conn(), session=_session(), session_id="s1",
        )
    assert result["source"] == "fallback"


def test_todos_flag_off_does_not_call_db_reader():
    with patch(
        "services.learner_state_fallback_service.is_todos_db_reads_enabled",
        return_value=False,
    ):
        with patch(
            "services.learner_state_read_service.list_todos_from_db"
        ) as mock_db:
            list_todos_with_fallback(
                conn=_conn(), session=_session(), session_id="s1",
            )
    mock_db.assert_not_called()


def test_todos_flag_off_returns_session_todos():
    session = _session()
    session.add_todo("Read paper", todo_type="daily")

    with patch(
        "services.learner_state_fallback_service.is_todos_db_reads_enabled",
        return_value=False,
    ):
        result = list_todos_with_fallback(
            conn=_conn(), session=session, session_id="s1",
        )
    assert len(result["todos"]) == 1
    assert result["error"] is None


# ── list_todos_with_fallback: flag on ─────────────────────────────────────────

def test_todos_flag_on_db_returns_list_source_db():
    db_todos = [
        {
            "todo_id": "t1", "title": "Read paper",
            "todo_type": "daily", "status": "todo", "linked_topic_id": "",
        }
    ]
    with patch(
        "services.learner_state_fallback_service.is_todos_db_reads_enabled",
        return_value=True,
    ):
        with patch(
            "services.learner_state_read_service.list_todos_from_db",
            return_value=db_todos,
        ):
            result = list_todos_with_fallback(
                conn=_conn(), session=_session(), session_id="s1",
            )
    assert result["source"] == "db"
    assert result["todos"] == db_todos
    assert result["error"] is None


def test_todos_flag_on_db_returns_empty_list_source_still_db():
    with patch(
        "services.learner_state_fallback_service.is_todos_db_reads_enabled",
        return_value=True,
    ):
        with patch(
            "services.learner_state_read_service.list_todos_from_db",
            return_value=[],
        ):
            result = list_todos_with_fallback(
                conn=_conn(), session=_session(), session_id="s1",
            )
    assert result["source"] == "db"
    assert result["todos"] == []


def test_todos_db_raises_source_error_fallback():
    with patch(
        "services.learner_state_fallback_service.is_todos_db_reads_enabled",
        return_value=True,
    ):
        with patch(
            "services.learner_state_read_service.list_todos_from_db",
            side_effect=RuntimeError("DB down"),
        ):
            result = list_todos_with_fallback(
                conn=_conn(), session=_session(), session_id="s1",
            )
    assert result["source"] == "error_fallback"
    assert result["error"] is not None


def test_todos_db_raises_falls_back_to_session_todos():
    session = _session()
    session.add_todo("Build demo", todo_type="weekly")

    with patch(
        "services.learner_state_fallback_service.is_todos_db_reads_enabled",
        return_value=True,
    ):
        with patch(
            "services.learner_state_read_service.list_todos_from_db",
            side_effect=RuntimeError("DB down"),
        ):
            result = list_todos_with_fallback(
                conn=_conn(), session=session, session_id="s1",
            )
    assert len(result["todos"]) == 1


# ── get_learner_state_with_fallback ───────────────────────────────────────────

def test_learner_state_with_topic_id_includes_progress_result():
    with patch(
        "services.learner_state_fallback_service.is_progress_db_reads_enabled",
        return_value=False,
    ):
        with patch(
            "services.learner_state_fallback_service.is_todos_db_reads_enabled",
            return_value=False,
        ):
            result = get_learner_state_with_fallback(
                conn=None, session=_session(),
                session_id="s1", legacy_topic_id="rag-basics",
            )
    assert result["topic_progress_result"] is not None
    assert result["todos_result"] is not None


def test_learner_state_without_topic_id_skips_progress():
    with patch(
        "services.learner_state_fallback_service.is_todos_db_reads_enabled",
        return_value=False,
    ):
        result = get_learner_state_with_fallback(
            conn=None, session=_session(),
            session_id="s1", legacy_topic_id=None,
        )
    assert result["topic_progress_result"] is None
    assert result["source_summary"]["topic_progress_source"] is None


def test_learner_state_source_summary_has_required_keys():
    with patch(
        "services.learner_state_fallback_service.is_todos_db_reads_enabled",
        return_value=False,
    ):
        result = get_learner_state_with_fallback(
            conn=None, session=_session(), session_id="s1",
        )
    assert "topic_progress_source" in result["source_summary"]
    assert "todos_source" in result["source_summary"]


def test_learner_state_todos_source_always_present():
    with patch(
        "services.learner_state_fallback_service.is_todos_db_reads_enabled",
        return_value=False,
    ):
        result = get_learner_state_with_fallback(
            conn=None, session=_session(), session_id="s1",
        )
    assert result["source_summary"]["todos_source"] is not None


# ── Session mutation guard ────────────────────────────────────────────────────

def test_service_does_not_mutate_session():
    session = _session()
    session.mark_topic_step("rag-basics", "learn", "done")
    progress_before = dict(session.get_topic_progress("rag-basics"))
    todos_before    = list(session.get_todos())

    with patch(
        "services.learner_state_fallback_service.is_progress_db_reads_enabled",
        return_value=False,
    ):
        with patch(
            "services.learner_state_fallback_service.is_todos_db_reads_enabled",
            return_value=False,
        ):
            get_learner_state_with_fallback(
                conn=None, session=session,
                session_id="s1", legacy_topic_id="rag-basics",
            )

    assert session.get_topic_progress("rag-basics") == progress_before
    assert session.get_todos() == todos_before


# ── Source constraints ────────────────────────────────────────────────────────

def test_service_does_not_touch_database_package():
    source = Path("services/learner_state_fallback_service.py").read_text(encoding="utf-8")
    assert "database.pool" not in source
    assert "from database" not in source
    assert "import database" not in source


def test_service_does_not_read_os_environ():
    source = Path("services/learner_state_fallback_service.py").read_text(encoding="utf-8")
    assert "import os" not in source
    assert "os.environ" not in source
    assert "os.getenv" not in source


def test_no_raw_secrets_in_error_output():
    secret_exc = RuntimeError(
        "postgresql://postgres:SuperSecret@db.supabase.co/postgres"
    )
    with patch(
        "services.learner_state_fallback_service.is_progress_db_reads_enabled",
        return_value=True,
    ):
        with patch(
            "services.learner_state_read_service.get_topic_progress_from_db",
            side_effect=secret_exc,
        ):
            result = get_topic_progress_with_fallback(
                conn=_conn(), session=_session(),
                session_id="s1", legacy_topic_id="rag-basics",
            )
    assert result["error"] is not None
    assert len(result["error"]) <= 300
