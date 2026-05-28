"""Tests for GET /debug/usage-events-db-check."""

from __future__ import annotations

import os
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

os.environ["AI2_TEST_MODE"] = "1"
os.environ["ANTHROPIC_API_KEY"] = "test-key"

from fastapi.testclient import TestClient

from app import app


client = TestClient(app)
URL = "/debug/usage-events-db-check"


def _make_conn():
    conn = MagicMock()
    conn.close = MagicMock()
    return conn


def _fake_get_conn(conn, calls=None):
    @contextmanager
    def _ctx():
        if calls is not None:
            calls.append("open")
        try:
            yield conn
        finally:
            conn.close()
    return _ctx


def _fake_get_conn_raises(exc, conn=None, calls=None):
    @contextmanager
    def _ctx():
        if calls is not None:
            calls.append("open")
        try:
            raise exc
            yield  # pragma: no cover
        finally:
            if conn is not None:
                conn.close()
    return _ctx


def _events():
    return [
        {
            "event_id": "evt-2",
            "session_id": "sess-1",
            "legacy_topic_id": "topic-1",
            "event_type": "quiz_evaluation",
            "source": "cache",
            "status": "success",
            "metadata": {},
        },
        {
            "event_id": "evt-1",
            "session_id": "sess-1",
            "legacy_topic_id": "topic-1",
            "event_type": "topic_learning_content",
            "source": "claude",
            "status": "success",
            "metadata": {"refresh": False},
        },
    ]


def _redacted_events():
    return [{**event, "metadata": {}} for event in _events()]


def _summary():
    return {
        "total_events": 2,
        "claude_events": 1,
        "cache_events": 1,
        "test_mode_events": 0,
        "error_events": 0,
        "by_event_type": {
            "quiz_evaluation": 1,
            "topic_learning_content": 1,
        },
    }


def _params(**overrides):
    params = {"session_id": "sess-1"}
    params.update(overrides)
    return params


def test_endpoint_exists():
    conn = _make_conn()
    with patch("routes.debug.get_conn", _fake_get_conn(conn)), patch(
        "repositories.usage_events_repository.list_usage_events_for_session",
        return_value=[],
    ), patch(
        "repositories.usage_events_repository.usage_event_summary_for_session",
        return_value=_summary(),
    ):
        response = client.get(URL, params=_params())

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")


def test_endpoint_requires_session_id():
    assert client.get(URL).status_code == 422


def test_endpoint_attempts_one_db_connection():
    conn = _make_conn()
    calls = []
    with patch("routes.debug.get_conn", _fake_get_conn(conn, calls)), patch(
        "repositories.usage_events_repository.list_usage_events_for_session",
        return_value=[],
    ), patch(
        "repositories.usage_events_repository.usage_event_summary_for_session",
        return_value=_summary(),
    ):
        response = client.get(URL, params=_params())

    assert response.status_code == 200
    assert calls == ["open"]
    assert response.json()["attempted_db_connection"] is True


def test_fake_db_events_return_source_db():
    conn = _make_conn()
    with patch("routes.debug.get_conn", _fake_get_conn(conn)), patch(
        "repositories.usage_events_repository.list_usage_events_for_session",
        return_value=_events(),
    ), patch(
        "repositories.usage_events_repository.usage_event_summary_for_session",
        return_value=_summary(),
    ):
        response = client.get(URL, params=_params())

    data = response.json()
    assert data["source"] == "db"
    assert data["events"] == _redacted_events()
    assert '"refresh"' not in response.text
    assert data["error"] is None


def test_events_count_equals_len_events():
    conn = _make_conn()
    with patch("routes.debug.get_conn", _fake_get_conn(conn)), patch(
        "repositories.usage_events_repository.list_usage_events_for_session",
        return_value=_events(),
    ), patch(
        "repositories.usage_events_repository.usage_event_summary_for_session",
        return_value=_summary(),
    ):
        data = client.get(URL, params=_params()).json()

    assert data["events_count"] == 2


def test_summary_is_returned():
    conn = _make_conn()
    with patch("routes.debug.get_conn", _fake_get_conn(conn)), patch(
        "repositories.usage_events_repository.list_usage_events_for_session",
        return_value=_events(),
    ), patch(
        "repositories.usage_events_repository.usage_event_summary_for_session",
        return_value=_summary(),
    ):
        data = client.get(URL, params=_params()).json()

    assert data["summary"] == _summary()


def test_limit_is_clamped_to_max_200():
    conn = _make_conn()
    list_fn = MagicMock(return_value=[])
    with patch("routes.debug.get_conn", _fake_get_conn(conn)), patch(
        "repositories.usage_events_repository.list_usage_events_for_session",
        list_fn,
    ), patch(
        "repositories.usage_events_repository.usage_event_summary_for_session",
        return_value=_summary(),
    ):
        client.get(URL, params=_params(limit="5000"))

    assert list_fn.call_args.kwargs["limit"] == 200


def test_limit_below_one_becomes_one():
    conn = _make_conn()
    list_fn = MagicMock(return_value=[])
    with patch("routes.debug.get_conn", _fake_get_conn(conn)), patch(
        "repositories.usage_events_repository.list_usage_events_for_session",
        list_fn,
    ), patch(
        "repositories.usage_events_repository.usage_event_summary_for_session",
        return_value=_summary(),
    ):
        client.get(URL, params=_params(limit="-10"))

    assert list_fn.call_args.kwargs["limit"] == 1


def test_invalid_limit_falls_back_to_50():
    conn = _make_conn()
    list_fn = MagicMock(return_value=[])
    with patch("routes.debug.get_conn", _fake_get_conn(conn)), patch(
        "repositories.usage_events_repository.list_usage_events_for_session",
        list_fn,
    ), patch(
        "repositories.usage_events_repository.usage_event_summary_for_session",
        return_value=_summary(),
    ):
        response = client.get(URL, params=_params(limit="not-an-int"))

    assert response.status_code == 200
    assert list_fn.call_args.kwargs["limit"] == 50


def test_db_errors_return_safe_error(monkeypatch):
    monkeypatch.setenv("SUPABASE_DATABASE_URL", "postgresql://user:secret@db.example/prod")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-super-secret")
    conn = _make_conn()
    exc = RuntimeError(
        "failed SUPABASE_DATABASE_URL=postgresql://user:secret@db.example/prod "
        "ANTHROPIC_API_KEY=sk-ant-super-secret Traceback line"
    )
    with patch("routes.debug.get_conn", _fake_get_conn_raises(exc, conn=conn)):
        data = client.get(URL, params=_params()).json()

    assert data["source"] == "error"
    assert data["events"] == []
    assert data["events_count"] == 0
    assert data["summary"] is None
    assert len(data["error"]) <= 320
    body = str(data)
    assert "postgresql://" not in body
    assert "user:secret" not in body
    assert "sk-ant-super-secret" not in body
    assert "SUPABASE_DATABASE_URL" not in body
    assert "ANTHROPIC_API_KEY" not in body
    assert "Traceback" not in body


def test_connection_is_closed_on_success():
    conn = _make_conn()
    with patch("routes.debug.get_conn", _fake_get_conn(conn)), patch(
        "repositories.usage_events_repository.list_usage_events_for_session",
        return_value=[],
    ), patch(
        "repositories.usage_events_repository.usage_event_summary_for_session",
        return_value=_summary(),
    ):
        client.get(URL, params=_params())

    conn.close.assert_called_once()


def test_connection_is_closed_on_error():
    conn = _make_conn()
    with patch("routes.debug.get_conn", _fake_get_conn_raises(RuntimeError("DB down"), conn=conn)):
        response = client.get(URL, params=_params())

    assert response.status_code == 200
    conn.close.assert_called_once()


def test_no_secrets_or_raw_env_values_appear_in_success_response(monkeypatch):
    monkeypatch.setenv("SUPABASE_DATABASE_URL", "postgresql://user:secret@host/db")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-super-secret")
    conn = _make_conn()
    with patch("routes.debug.get_conn", _fake_get_conn(conn)), patch(
        "repositories.usage_events_repository.list_usage_events_for_session",
        return_value=[],
    ), patch(
        "repositories.usage_events_repository.usage_event_summary_for_session",
        return_value=_summary(),
    ):
        body = client.get(URL, params=_params()).text

    assert "postgresql://" not in body
    assert "user:secret" not in body
    assert "sk-ant-test-super-secret" not in body
    assert "SUPABASE_DATABASE_URL" not in body
    assert "ANTHROPIC_API_KEY" not in body


def test_learner_facing_session_loading_is_not_called():
    conn = _make_conn()
    with patch("routes.debug.get_conn", _fake_get_conn(conn)), patch(
        "routes.deps.get_session_data",
        side_effect=AssertionError("session loading must not be called"),
    ) as loader, patch(
        "repositories.usage_events_repository.list_usage_events_for_session",
        return_value=[],
    ), patch(
        "repositories.usage_events_repository.usage_event_summary_for_session",
        return_value=_summary(),
    ):
        response = client.get(URL, params=_params())

    assert response.status_code == 200
    loader.assert_not_called()


def test_endpoint_does_not_call_save_session():
    conn = _make_conn()
    with patch("routes.debug.get_conn", _fake_get_conn(conn)), patch(
        "routes.deps.save_session",
        side_effect=AssertionError("save_session must not be called"),
    ) as saver, patch(
        "repositories.usage_events_repository.list_usage_events_for_session",
        return_value=[],
    ), patch(
        "repositories.usage_events_repository.usage_event_summary_for_session",
        return_value=_summary(),
    ):
        response = client.get(URL, params=_params())

    assert response.status_code == 200
    saver.assert_not_called()


def test_no_learner_facing_route_behavior_changes():
    paths = {route.path for route in app.routes}
    assert {
        "/topics/{session_id}",
        "/topic/{session_id}/{topic_id}",
        "/topic/content/generate",
        "/topic/practice/generate",
        "/quiz/evaluate",
        "/portfolio/feedback",
        "/interview/feedback",
        URL,
    }.issubset(paths)
