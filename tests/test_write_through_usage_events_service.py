"""Tests for services/write_through_usage_events_service.py.

All tests use fake sessions and patched repository functions. No real database
connection is required.
"""

from __future__ import annotations

import copy
import importlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


SERVICE_PATH = (
    Path(__file__).parent.parent
    / "services"
    / "write_through_usage_events_service.py"
)


def _import():
    import services.write_through_usage_events_service as m
    importlib.reload(m)
    return m


def _event(**overrides) -> dict:
    event = {
        "event_id": "evt-1",
        "event_type": "topic_learning_content",
        "topic_id": "topic-1",
        "model": "claude-test",
        "source": "claude",
        "status": "success",
        "metadata": {"k": "v"},
        "created_at": "2026-05-19T12:00:00+00:00",
    }
    event.update(overrides)
    return event


class FakeSession:
    def __init__(self, usage_events=None):
        self.usage_events = usage_events or []


class FakeConn:
    def __init__(self):
        self.committed = False
        self.rolled_back = False

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


def test_flag_disabled_by_default_means_helpers_noop(monkeypatch):
    monkeypatch.delenv("AI2_DB_WRITE_THROUGH_ENABLED", raising=False)
    m = _import()
    session = FakeSession([_event()])
    conn = FakeConn()

    assert m.maybe_write_usage_events(
        conn=conn, session=session, user_id=None, session_id="s1"
    ) == 0
    assert m.maybe_write_latest_usage_event(
        conn=conn, session=session, user_id=None, session_id="s1"
    ) is False
    assert m.maybe_write_usage_events_for_topic(
        conn=conn, session=session, user_id=None,
        session_id="s1", legacy_topic_id="topic-1",
    ) == 0


def test_conn_none_means_noop(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    m = _import()
    session = FakeSession([_event()])

    assert m.maybe_write_usage_events(
        conn=None, session=session, user_id=None, session_id="s1"
    ) == 0
    assert m.maybe_write_latest_usage_event(
        conn=None, session=session, user_id=None, session_id="s1"
    ) is False
    assert m.maybe_write_usage_events_for_topic(
        conn=None, session=session, user_id=None,
        session_id="s1", legacy_topic_id="topic-1",
    ) == 0


def test_no_usage_events_means_noop(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    m = _import()
    session = FakeSession([])

    with patch("repositories.usage_events_repository.insert_usage_events") as fake_many:
        with patch("repositories.usage_events_repository.insert_usage_event") as fake_one:
            assert m.maybe_write_usage_events(
                conn=FakeConn(), session=session, user_id=None, session_id="s1"
            ) == 0
            assert m.maybe_write_latest_usage_event(
                conn=FakeConn(), session=session, user_id=None, session_id="s1"
            ) is False
            assert m.maybe_write_usage_events_for_topic(
                conn=FakeConn(), session=session, user_id=None,
                session_id="s1", legacy_topic_id="topic-1",
            ) == 0

    fake_many.assert_not_called()
    fake_one.assert_not_called()


def test_maybe_write_usage_events_calls_repository_when_enabled_and_events_exist(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    m = _import()
    events = [_event(event_id="evt-1"), _event(event_id="evt-2")]
    session = FakeSession(events)
    conn = FakeConn()

    with patch(
        "repositories.usage_events_repository.insert_usage_events",
        MagicMock(return_value=2),
    ) as fake_insert:
        result = m.maybe_write_usage_events(
            conn=conn, session=session, user_id="u1", session_id="s1"
        )

    assert result == 2
    fake_insert.assert_called_once_with(
        conn,
        user_id="u1",
        session_id="s1",
        events=events,
    )


def test_maybe_write_latest_usage_event_writes_only_last_event(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    m = _import()
    first = _event(event_id="evt-1")
    last = _event(event_id="evt-2")
    conn = FakeConn()

    with patch("repositories.usage_events_repository.insert_usage_event") as fake_insert:
        result = m.maybe_write_latest_usage_event(
            conn=conn,
            session=FakeSession([first, last]),
            user_id="u1",
            session_id="s1",
        )

    assert result is True
    fake_insert.assert_called_once_with(
        conn,
        user_id="u1",
        session_id="s1",
        event=last,
    )


def test_maybe_write_usage_events_for_topic_filters_by_topic_id(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    m = _import()
    matching = _event(event_id="evt-1", topic_id="topic-a")
    other = _event(event_id="evt-2", topic_id="topic-b")

    with patch(
        "repositories.usage_events_repository.insert_usage_events",
        MagicMock(return_value=1),
    ) as fake_insert:
        result = m.maybe_write_usage_events_for_topic(
            conn=FakeConn(),
            session=FakeSession([matching, other]),
            user_id=None,
            session_id="s1",
            legacy_topic_id="topic-a",
        )

    assert result == 1
    _, kwargs = fake_insert.call_args
    assert kwargs["events"] == [matching]


def test_maybe_write_usage_events_for_topic_filters_by_legacy_topic_id(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    m = _import()
    matching = _event(event_id="evt-1", topic_id=None, legacy_topic_id="legacy-a")
    other = _event(event_id="evt-2", topic_id=None, legacy_topic_id="legacy-b")

    with patch(
        "repositories.usage_events_repository.insert_usage_events",
        MagicMock(return_value=1),
    ) as fake_insert:
        result = m.maybe_write_usage_events_for_topic(
            conn=FakeConn(),
            session=FakeSession([matching, other]),
            user_id=None,
            session_id="s1",
            legacy_topic_id="legacy-a",
        )

    assert result == 1
    _, kwargs = fake_insert.call_args
    assert kwargs["events"] == [matching]


def test_maybe_write_usage_events_for_topic_empty_legacy_topic_id_returns_zero(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    m = _import()

    with patch("repositories.usage_events_repository.insert_usage_events") as fake_insert:
        result = m.maybe_write_usage_events_for_topic(
            conn=FakeConn(),
            session=FakeSession([_event()]),
            user_id=None,
            session_id="s1",
            legacy_topic_id="",
        )

    assert result == 0
    fake_insert.assert_not_called()


def test_repository_exceptions_propagate(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    m = _import()

    with patch(
        "repositories.usage_events_repository.insert_usage_events",
        MagicMock(side_effect=RuntimeError("db failed")),
    ):
        with pytest.raises(RuntimeError, match="db failed"):
            m.maybe_write_usage_events(
                conn=FakeConn(),
                session=FakeSession([_event()]),
                user_id=None,
                session_id="s1",
            )


def test_service_does_not_commit_or_rollback(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    m = _import()
    conn = FakeConn()

    with patch(
        "repositories.usage_events_repository.insert_usage_events",
        MagicMock(return_value=1),
    ):
        m.maybe_write_usage_events(
            conn=conn, session=FakeSession([_event()]), user_id=None, session_id="s1"
        )

    assert conn.committed is False
    assert conn.rolled_back is False


def test_service_does_not_create_db_connection():
    src = SERVICE_PATH.read_text(encoding="utf-8")
    assert "psycopg2.connect" not in src
    assert "get_conn(" not in src


def test_service_does_not_mutate_session(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    m = _import()
    events = [_event(event_id="evt-1"), _event(event_id="evt-2")]
    before = copy.deepcopy(events)
    session = FakeSession(events)

    with patch(
        "repositories.usage_events_repository.insert_usage_events",
        MagicMock(return_value=2),
    ):
        m.maybe_write_usage_events(
            conn=FakeConn(), session=session, user_id=None, session_id="s1"
        )

    assert session.usage_events == before


def test_service_does_not_import_database_pool():
    assert "database.pool" not in SERVICE_PATH.read_text(encoding="utf-8")


def test_service_does_not_read_os_environ_directly():
    src = SERVICE_PATH.read_text(encoding="utf-8")
    assert "os.environ" not in src
    assert "os.getenv" not in src
