"""Tests for services/write_through_service.py.

All tests run without a real database connection or a real SessionContext.
"""

from __future__ import annotations

import importlib
import os
from pathlib import Path
from unittest.mock import MagicMock, call, patch

SERVICE_PATH = Path(__file__).parent.parent / "services" / "write_through_service.py"


def _import():
    import services.write_through_service as m
    importlib.reload(m)
    return m


# ── File existence ────────────────────────────────────────────────────────────

def test_service_file_exists():
    assert SERVICE_PATH.exists(), f"write_through_service.py not found at {SERVICE_PATH}"


# ── Source-code structural checks ─────────────────────────────────────────────

def test_source_does_not_read_env_at_module_level():
    src = SERVICE_PATH.read_text(encoding="utf-8")
    # os.environ / os.getenv must only appear inside function bodies
    # We check that there is no bare module-level usage before any def/class
    lines = src.splitlines()
    inside_function = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("def ") or stripped.startswith("class "):
            inside_function = True
        if not inside_function and ("os.environ" in line or "os.getenv" in line):
            assert False, f"os.environ/getenv used at module level: {line!r}"


def test_source_does_not_import_psycopg2_at_module_level():
    src = SERVICE_PATH.read_text(encoding="utf-8")
    top = src.split("def is_db_write_through_enabled")[0]
    assert "import psycopg2" not in top


def test_source_does_not_open_connection():
    src = SERVICE_PATH.read_text(encoding="utf-8")
    assert "psycopg2.connect(" not in src
    assert "get_conn(" not in src


def test_source_does_not_commit_or_rollback():
    src = SERVICE_PATH.read_text(encoding="utf-8")
    assert ".commit()" not in src
    assert ".rollback()" not in src


# ── Function existence ────────────────────────────────────────────────────────

def test_module_has_expected_functions():
    m = _import()
    for fn in (
        "is_db_write_through_enabled",
        "maybe_write_topic_progress",
        "maybe_write_todos",
        "maybe_write_topic_and_todos",
    ):
        assert callable(getattr(m, fn, None)), f"missing: write_through_service.{fn}"


# ── is_db_write_through_enabled ───────────────────────────────────────────────

def test_flag_off_by_default(monkeypatch):
    monkeypatch.delenv("AI2_DB_WRITE_THROUGH_ENABLED", raising=False)
    m = _import()
    assert m.is_db_write_through_enabled() is False


def test_flag_on_for_one(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    m = _import()
    assert m.is_db_write_through_enabled() is True


def test_flag_on_for_true(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "true")
    m = _import()
    assert m.is_db_write_through_enabled() is True


def test_flag_on_for_true_uppercase(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "TRUE")
    m = _import()
    assert m.is_db_write_through_enabled() is True


def test_flag_on_for_yes(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "yes")
    m = _import()
    assert m.is_db_write_through_enabled() is True


def test_flag_on_for_on(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "on")
    m = _import()
    assert m.is_db_write_through_enabled() is True


def test_flag_off_for_false(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "false")
    m = _import()
    assert m.is_db_write_through_enabled() is False


def test_flag_off_for_zero(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "0")
    m = _import()
    assert m.is_db_write_through_enabled() is False


def test_flag_off_for_empty(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "")
    m = _import()
    assert m.is_db_write_through_enabled() is False


def test_flag_off_for_random_string(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "enabled")
    m = _import()
    assert m.is_db_write_through_enabled() is False


# ── Fake helpers ──────────────────────────────────────────────────────────────

def _fake_session(*, topic_progress=None, completion_percent=50, todos=None):
    session = MagicMock()
    session.get_topic_progress.return_value = topic_progress or {"learn": "done", "quiz": "not_started"}
    session.topic_completion_percent.return_value = completion_percent
    session.get_todos.return_value = todos or []
    return session


# ── maybe_write_topic_progress ────────────────────────────────────────────────

def test_maybe_write_topic_progress_returns_false_when_flag_off(monkeypatch):
    monkeypatch.delenv("AI2_DB_WRITE_THROUGH_ENABLED", raising=False)
    m = _import()
    result = m.maybe_write_topic_progress(
        conn=MagicMock(), session=_fake_session(), user_id=None,
        session_id="s1", legacy_topic_id="aipm-t1",
    )
    assert result is False


def test_maybe_write_topic_progress_returns_false_when_conn_is_none(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    m = _import()
    result = m.maybe_write_topic_progress(
        conn=None, session=_fake_session(), user_id=None,
        session_id="s1", legacy_topic_id="aipm-t1",
    )
    assert result is False


def test_maybe_write_topic_progress_returns_true_when_enabled(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    m = _import()
    fake_upsert = MagicMock()
    with patch("repositories.progress_repository.upsert_topic_progress", fake_upsert):
        result = m.maybe_write_topic_progress(
            conn=MagicMock(), session=_fake_session(), user_id="u1",
            session_id="s1", legacy_topic_id="aipm-t1",
        )
    assert result is True


def test_maybe_write_topic_progress_calls_upsert_with_legacy_id(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    m = _import()
    fake_upsert = MagicMock()
    conn = MagicMock()
    with patch("repositories.progress_repository.upsert_topic_progress", fake_upsert):
        m.maybe_write_topic_progress(
            conn=conn, session=_fake_session(), user_id="u1",
            session_id="s1", legacy_topic_id="aipm-t1",
        )
    fake_upsert.assert_called_once()
    args, kwargs = fake_upsert.call_args
    assert kwargs["legacy_topic_id"] == "aipm-t1"
    # conn is the first positional argument
    assert args[0] is conn


def test_maybe_write_topic_progress_reads_session_progress(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    m = _import()
    session = _fake_session(topic_progress={"learn": "done"}, completion_percent=20)
    fake_upsert = MagicMock()
    with patch("repositories.progress_repository.upsert_topic_progress", fake_upsert):
        m.maybe_write_topic_progress(
            conn=MagicMock(), session=session, user_id=None,
            session_id="s1", legacy_topic_id="aipm-t1",
        )
    session.get_topic_progress.assert_called_once_with("aipm-t1")
    session.topic_completion_percent.assert_called_once_with("aipm-t1")
    _, kwargs = fake_upsert.call_args
    assert kwargs["progress"] == {"learn": "done"}
    assert kwargs["completion_percent"] == 20


def test_maybe_write_topic_progress_does_not_read_session_when_flag_off(monkeypatch):
    monkeypatch.delenv("AI2_DB_WRITE_THROUGH_ENABLED", raising=False)
    m = _import()
    session = _fake_session()
    m.maybe_write_topic_progress(
        conn=MagicMock(), session=session, user_id=None,
        session_id="s1", legacy_topic_id="aipm-t1",
    )
    session.get_topic_progress.assert_not_called()


# ── maybe_write_todos ─────────────────────────────────────────────────────────

def test_maybe_write_todos_returns_zero_when_flag_off(monkeypatch):
    monkeypatch.delenv("AI2_DB_WRITE_THROUGH_ENABLED", raising=False)
    m = _import()
    result = m.maybe_write_todos(
        conn=MagicMock(), session=_fake_session(todos=[{"todo_id": "x"}]),
        user_id=None, session_id="s1",
    )
    assert result == 0


def test_maybe_write_todos_returns_zero_when_conn_is_none(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    m = _import()
    result = m.maybe_write_todos(
        conn=None, session=_fake_session(todos=[{"todo_id": "x"}]),
        user_id=None, session_id="s1",
    )
    assert result == 0


def test_maybe_write_todos_returns_count_of_todos(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    m = _import()
    todos = [{"todo_id": "a"}, {"todo_id": "b"}, {"todo_id": "c"}]
    fake_upsert = MagicMock()
    with patch("repositories.todos_repository.upsert_todo", fake_upsert):
        result = m.maybe_write_todos(
            conn=MagicMock(), session=_fake_session(todos=todos),
            user_id="u1", session_id="s1",
        )
    assert result == 3


def test_maybe_write_todos_calls_upsert_for_each_todo(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    m = _import()
    todos = [{"todo_id": "a", "title": "T1"}, {"todo_id": "b", "title": "T2"}]
    fake_upsert = MagicMock()
    conn = MagicMock()
    with patch("repositories.todos_repository.upsert_todo", fake_upsert):
        m.maybe_write_todos(
            conn=conn, session=_fake_session(todos=todos),
            user_id="u1", session_id="s1",
        )
    assert fake_upsert.call_count == 2


def test_maybe_write_todos_passes_session_id_to_each_upsert(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    m = _import()
    todos = [{"todo_id": "a"}]
    fake_upsert = MagicMock()
    with patch("repositories.todos_repository.upsert_todo", fake_upsert):
        m.maybe_write_todos(
            conn=MagicMock(), session=_fake_session(todos=todos),
            user_id=None, session_id="sess-99",
        )
    _, kwargs = fake_upsert.call_args
    assert kwargs["session_id"] == "sess-99"


def test_maybe_write_todos_returns_zero_for_empty_todos(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    m = _import()
    fake_upsert = MagicMock()
    with patch("repositories.todos_repository.upsert_todo", fake_upsert):
        result = m.maybe_write_todos(
            conn=MagicMock(), session=_fake_session(todos=[]),
            user_id=None, session_id="s1",
        )
    assert result == 0
    fake_upsert.assert_not_called()


# ── maybe_write_topic_and_todos ───────────────────────────────────────────────

def test_maybe_write_topic_and_todos_returns_dict(monkeypatch):
    monkeypatch.delenv("AI2_DB_WRITE_THROUGH_ENABLED", raising=False)
    m = _import()
    result = m.maybe_write_topic_and_todos(
        conn=MagicMock(), session=_fake_session(),
        user_id=None, session_id="s1",
    )
    assert isinstance(result, dict)
    assert "progress" in result
    assert "todos" in result


def test_maybe_write_topic_and_todos_both_false_when_flag_off(monkeypatch):
    monkeypatch.delenv("AI2_DB_WRITE_THROUGH_ENABLED", raising=False)
    m = _import()
    result = m.maybe_write_topic_and_todos(
        conn=MagicMock(), session=_fake_session(),
        user_id=None, session_id="s1", legacy_topic_id="aipm-t1",
    )
    assert result == {"progress": False, "todos": 0}


def test_maybe_write_topic_and_todos_skips_progress_when_no_legacy_id(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    m = _import()
    fake_progress = MagicMock(return_value=True)
    fake_todos = MagicMock(return_value=2)
    with patch.object(m, "maybe_write_topic_progress", fake_progress):
        with patch.object(m, "maybe_write_todos", fake_todos):
            result = m.maybe_write_topic_and_todos(
                conn=MagicMock(), session=_fake_session(),
                user_id=None, session_id="s1",
                # no legacy_topic_id
            )
    fake_progress.assert_not_called()
    assert result["progress"] is False
    assert result["todos"] == 2


def test_maybe_write_topic_and_todos_calls_both_when_legacy_id_given(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    m = _import()
    fake_progress = MagicMock(return_value=True)
    fake_todos = MagicMock(return_value=3)
    with patch.object(m, "maybe_write_topic_progress", fake_progress):
        with patch.object(m, "maybe_write_todos", fake_todos):
            result = m.maybe_write_topic_and_todos(
                conn=MagicMock(), session=_fake_session(),
                user_id="u1", session_id="s1",
                legacy_topic_id="aipm-t1",
            )
    fake_progress.assert_called_once()
    fake_todos.assert_called_once()
    assert result == {"progress": True, "todos": 3}


def test_maybe_write_topic_and_todos_passes_legacy_id_to_progress(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    m = _import()
    fake_progress = MagicMock(return_value=True)
    fake_todos = MagicMock(return_value=0)
    conn = MagicMock()
    session = _fake_session()
    with patch.object(m, "maybe_write_topic_progress", fake_progress):
        with patch.object(m, "maybe_write_todos", fake_todos):
            m.maybe_write_topic_and_todos(
                conn=conn, session=session,
                user_id="u1", session_id="s1",
                legacy_topic_id="aipm-week-3-rag",
            )
    _, kwargs = fake_progress.call_args
    assert kwargs["legacy_topic_id"] == "aipm-week-3-rag"
    assert kwargs["conn"] is conn
    assert kwargs["session"] is session
