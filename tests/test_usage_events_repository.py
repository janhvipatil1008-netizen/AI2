"""Tests for repositories/usage_events_repository.py.

All tests use fake connection/cursor objects. No real database is required.
"""

from __future__ import annotations

from pathlib import Path

import pytest


REPO_PATH = Path(__file__).parent.parent / "repositories" / "usage_events_repository.py"


def _src() -> str:
    return REPO_PATH.read_text(encoding="utf-8")


def _event(**overrides) -> dict:
    event = {
        "event_id": "evt-1",
        "event_type": "topic_learning_content",
        "topic_id": "topic-1",
        "model": "claude-test",
        "source": "claude",
        "status": "success",
        "metadata": {"cache_hit": False},
        "created_at": "2026-05-19T12:00:00+00:00",
    }
    event.update(overrides)
    return event


class FakeCursor:
    def __init__(self, *, fetchone_row=None, fetchall_rows=None):
        self.executed: list[tuple[str, tuple]] = []
        self.fetchone_row = fetchone_row
        self.fetchall_rows = fetchall_rows or []

    def execute(self, sql: str, params: tuple = ()) -> None:
        self.executed.append((sql.strip(), params))

    def fetchone(self):
        return self.fetchone_row

    def fetchall(self):
        return self.fetchall_rows

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class FakeConn:
    def __init__(self, *, fetchone_row=None, fetchall_rows=None):
        self.cursor_obj = FakeCursor(
            fetchone_row=fetchone_row,
            fetchall_rows=fetchall_rows,
        )
        self.cursor_kwargs: list[dict] = []
        self.committed = False
        self.rolled_back = False

    def cursor(self, **kwargs):
        self.cursor_kwargs.append(kwargs)
        return self.cursor_obj

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    @property
    def executed(self):
        return self.cursor_obj.executed


def _all_sql(conn: FakeConn) -> str:
    return " ".join(sql for sql, _ in conn.executed)


def _all_params(conn: FakeConn) -> list:
    return [param for _, params in conn.executed for param in (params or [])]


def test_usage_events_repository_imports_safely():
    import repositories.usage_events_repository  # noqa: F401


def test_usage_events_repository_has_expected_functions():
    from repositories import usage_events_repository as repo

    for fn in (
        "insert_usage_event",
        "insert_usage_events",
        "list_usage_events_for_session",
        "usage_event_summary_for_session",
    ):
        assert callable(getattr(repo, fn, None)), f"missing: {fn}"


def test_usage_events_repository_does_not_read_env_vars():
    src = _src()
    assert "os.environ" not in src
    assert "os.getenv" not in src


def test_usage_events_repository_does_not_open_db_connections():
    src = _src()
    assert "database.pool" not in src
    assert "psycopg2.connect" not in src
    assert "get_conn(" not in src


def test_usage_events_repository_references_usage_events_table():
    assert "usage_events" in _src()


def test_usage_events_repository_uses_percent_s_placeholders():
    assert "%s" in _src()


def test_insert_usage_event_executes_parameterized_sql():
    from repositories.usage_events_repository import insert_usage_event

    conn = FakeConn()
    insert_usage_event(conn, user_id="u1", session_id="s1", event=_event())

    assert conn.executed
    sql, params = conn.executed[-1]
    assert "INSERT INTO usage_events" in sql
    assert "ON CONFLICT (event_id) DO NOTHING" in sql
    assert "%s" in sql
    assert isinstance(params, tuple)
    assert "evt-1" in params


def test_insert_usage_event_maps_topic_id_to_legacy_topic_id():
    from repositories.usage_events_repository import insert_usage_event

    conn = FakeConn()
    insert_usage_event(
        conn,
        user_id=None,
        session_id="s1",
        event=_event(topic_id="legacy-topic-from-topic-id"),
    )

    assert "legacy-topic-from-topic-id" in _all_params(conn)


def test_insert_usage_event_handles_legacy_topic_id_directly():
    from repositories.usage_events_repository import insert_usage_event

    event = _event(topic_id=None, legacy_topic_id="legacy-topic-direct")
    conn = FakeConn()
    insert_usage_event(conn, user_id=None, session_id="s1", event=event)

    assert "legacy-topic-direct" in _all_params(conn)


def test_insert_usage_event_passes_required_event_fields():
    from repositories.usage_events_repository import insert_usage_event

    conn = FakeConn()
    insert_usage_event(
        conn,
        user_id="u1",
        session_id="s1",
        event=_event(event_type="quiz_evaluation", source="test_mode", status="error"),
    )

    params = _all_params(conn)
    assert "quiz_evaluation" in params
    assert "test_mode" in params
    assert "error" in params
    assert "claude-test" in params


def test_insert_usage_events_returns_zero_for_empty_list():
    from repositories.usage_events_repository import insert_usage_events

    conn = FakeConn()
    result = insert_usage_events(conn, user_id=None, session_id="s1", events=[])

    assert result == 0
    assert conn.executed == []


def test_insert_usage_events_calls_insert_per_event(monkeypatch: pytest.MonkeyPatch):
    from repositories import usage_events_repository as repo

    calls = []

    def fake_insert(conn, *, user_id, session_id, event):
        calls.append((conn, user_id, session_id, event["event_id"]))

    monkeypatch.setattr(repo, "insert_usage_event", fake_insert)
    conn = FakeConn()

    result = repo.insert_usage_events(
        conn,
        user_id="u1",
        session_id="s1",
        events=[_event(event_id="evt-1"), _event(event_id="evt-2")],
    )

    assert result == 2
    assert calls == [
        (conn, "u1", "s1", "evt-1"),
        (conn, "u1", "s1", "evt-2"),
    ]


def test_list_usage_events_for_session_returns_list_of_dicts():
    from repositories.usage_events_repository import list_usage_events_for_session

    rows = [
        {"event_id": "evt-2", "session_id": "s1", "source": "cache"},
        {"event_id": "evt-1", "session_id": "s1", "source": "claude"},
    ]
    conn = FakeConn(fetchall_rows=rows)

    result = list_usage_events_for_session(conn, session_id="s1", limit=2)

    assert result == rows
    assert all(isinstance(row, dict) for row in result)


def test_list_usage_events_for_session_uses_session_id_and_limit_params():
    from repositories.usage_events_repository import list_usage_events_for_session

    conn = FakeConn()
    list_usage_events_for_session(conn, session_id="session-123", limit=25)

    sql, params = conn.executed[-1]
    assert "WHERE session_id = %s" in sql
    assert "LIMIT %s" in sql
    assert params == ("session-123", 25)


def test_list_usage_events_for_session_clamps_unsafe_limit():
    from repositories.usage_events_repository import list_usage_events_for_session

    conn = FakeConn()
    list_usage_events_for_session(conn, session_id="s1", limit=50000)

    assert conn.executed[-1][1] == ("s1", 1000)


def test_usage_event_summary_for_session_returns_expected_counts():
    from repositories.usage_events_repository import usage_event_summary_for_session

    conn = FakeConn(
        fetchone_row={
            "total_events": 5,
            "claude_events": 2,
            "cache_events": 1,
            "test_mode_events": 1,
            "error_events": 1,
        },
        fetchall_rows=[
            {"event_type": "topic_learning_content", "count": 3},
            {"event_type": "quiz_evaluation", "count": 2},
        ],
    )

    result = usage_event_summary_for_session(conn, session_id="s1")

    assert result == {
        "total_events": 5,
        "claude_events": 2,
        "cache_events": 1,
        "test_mode_events": 1,
        "error_events": 1,
        "by_event_type": {
            "topic_learning_content": 3,
            "quiz_evaluation": 2,
        },
    }


def test_usage_event_summary_for_session_uses_session_id_params():
    from repositories.usage_events_repository import usage_event_summary_for_session

    conn = FakeConn()
    usage_event_summary_for_session(conn, session_id="session-summary")

    assert len(conn.executed) == 2
    assert conn.executed[0][1] == ("session-summary",)
    assert conn.executed[1][1] == ("session-summary",)


def test_usage_events_repository_does_not_commit_or_rollback():
    from repositories.usage_events_repository import (
        insert_usage_event,
        list_usage_events_for_session,
        usage_event_summary_for_session,
    )

    conn = FakeConn()
    insert_usage_event(conn, user_id=None, session_id="s1", event=_event())
    list_usage_events_for_session(conn, session_id="s1")
    usage_event_summary_for_session(conn, session_id="s1")

    assert conn.committed is False
    assert conn.rolled_back is False
