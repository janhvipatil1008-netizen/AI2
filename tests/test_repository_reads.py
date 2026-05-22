"""Fake-cursor tests for repository read functions.

These tests do not require a live database. They verify read behavior,
parameterized SQL, and legacy ID transition lookups.
"""

from repositories.curriculum_repository import (
    get_learning_topic_by_legacy_id,
    get_learning_track_by_key,
)
from repositories.progress_repository import get_topic_progress_by_legacy_id
from repositories.todos_repository import list_todos_for_session


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=None):
        self.conn.executed.append((sql, params))

    def fetchone(self):
        if self.conn.fetchone_rows:
            return self.conn.fetchone_rows.pop(0)
        return None

    def fetchall(self):
        return list(self.conn.fetchall_rows)


class FakeConn:
    def __init__(self, *, fetchone_rows=None, fetchall_rows=None):
        self.fetchone_rows = list(fetchone_rows or [])
        self.fetchall_rows = list(fetchall_rows or [])
        self.executed = []
        self.cursor_factories = []

    def cursor(self, *args, **kwargs):
        self.cursor_factories.append(kwargs.get("cursor_factory"))
        return FakeCursor(self)


def _last_sql(conn):
    return conn.executed[-1][0]


def _last_params(conn):
    return conn.executed[-1][1]


def test_get_learning_track_by_key_returns_dict_when_row_exists():
    conn = FakeConn(fetchone_rows=[{"id": "track-1", "track_key": "aipm"}])

    result = get_learning_track_by_key(conn, "aipm")

    assert result == {"id": "track-1", "track_key": "aipm"}


def test_get_learning_track_by_key_returns_none_when_no_row():
    conn = FakeConn()

    result = get_learning_track_by_key(conn, "missing")

    assert result is None


def test_get_learning_track_by_key_uses_parameterized_placeholder():
    conn = FakeConn()

    get_learning_track_by_key(conn, "aipm")

    assert "track_key = %s" in _last_sql(conn)
    assert _last_params(conn) == ("aipm",)


def test_get_learning_topic_by_legacy_id_returns_dict_when_row_exists():
    conn = FakeConn(fetchone_rows=[{"id": "topic-1", "title": "RAG"}])

    result = get_learning_topic_by_legacy_id(conn, "legacy-topic-1")

    assert result == {"id": "topic-1", "title": "RAG"}


def test_get_learning_topic_by_legacy_id_returns_none_when_no_row():
    conn = FakeConn()

    result = get_learning_topic_by_legacy_id(conn, "missing-topic")

    assert result is None


def test_get_learning_topic_by_legacy_id_uses_parameterized_placeholder():
    conn = FakeConn()

    get_learning_topic_by_legacy_id(conn, "legacy-topic-1")

    assert "%s" in _last_sql(conn)
    assert _last_params(conn) == ("legacy-topic-1",)


def test_get_learning_topic_by_legacy_id_uses_metadata_legacy_topic_id_lookup():
    conn = FakeConn()

    get_learning_topic_by_legacy_id(conn, "legacy-topic-1")

    assert "metadata->>'legacy_topic_id'" in _last_sql(conn)


def test_get_topic_progress_by_legacy_id_returns_dict_when_row_exists():
    conn = FakeConn(fetchone_rows=[{
        "session_id": "sess-1",
        "legacy_topic_id": "topic-1",
        "completion_percent": 40,
    }])

    result = get_topic_progress_by_legacy_id(
        conn,
        session_id="sess-1",
        legacy_topic_id="topic-1",
    )

    assert result["session_id"] == "sess-1"
    assert result["legacy_topic_id"] == "topic-1"
    assert result["completion_percent"] == 40


def test_get_topic_progress_by_legacy_id_returns_none_when_no_row():
    conn = FakeConn()

    result = get_topic_progress_by_legacy_id(
        conn,
        session_id="sess-1",
        legacy_topic_id="missing-topic",
    )

    assert result is None


def test_get_topic_progress_by_legacy_id_uses_session_and_legacy_params():
    conn = FakeConn()

    get_topic_progress_by_legacy_id(
        conn,
        session_id="sess-1",
        legacy_topic_id="topic-1",
    )

    assert "session_id = %s" in _last_sql(conn)
    assert "legacy_topic_id = %s" in _last_sql(conn)
    assert _last_params(conn) == ("sess-1", "topic-1")


def test_get_topic_progress_by_legacy_id_does_not_require_real_db():
    conn = FakeConn(fetchone_rows=[{"id": "progress-1"}])

    result = get_topic_progress_by_legacy_id(
        conn,
        session_id="sess-1",
        legacy_topic_id="topic-1",
    )

    assert result == {"id": "progress-1"}
    assert conn.executed


def test_list_todos_for_session_returns_list_of_dicts():
    conn = FakeConn(fetchall_rows=[
        {"todo_key": "todo-1", "title": "Read"},
        {"todo_key": "todo-2", "title": "Practice"},
    ])

    result = list_todos_for_session(conn, "sess-1")

    assert result == [
        {"todo_key": "todo-1", "title": "Read"},
        {"todo_key": "todo-2", "title": "Practice"},
    ]


def test_list_todos_for_session_returns_empty_list_when_no_rows():
    conn = FakeConn()

    result = list_todos_for_session(conn, "sess-1")

    assert result == []


def test_list_todos_for_session_uses_session_id_parameter():
    conn = FakeConn()

    list_todos_for_session(conn, "sess-1")

    assert "session_id = %s" in _last_sql(conn)
    assert _last_params(conn) == ("sess-1",)


def test_list_todos_for_session_does_not_require_real_db():
    conn = FakeConn(fetchall_rows=[{"id": "todo-1"}])

    result = list_todos_for_session(conn, "sess-1")

    assert result == [{"id": "todo-1"}]
    assert conn.executed
