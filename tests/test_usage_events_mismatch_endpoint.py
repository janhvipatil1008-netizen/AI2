"""Tests for GET /debug/usage-events-mismatch-check."""

from __future__ import annotations

import os
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

os.environ["AI2_TEST_MODE"] = "1"
os.environ["ANTHROPIC_API_KEY"] = "test-key"

from fastapi.testclient import TestClient

from app import app


client = TestClient(app)
URL = "/debug/usage-events-mismatch-check"

PRIVATE_METADATA = "full usage metadata should never appear"
PRIVATE_SESSION_DATA = "full session_data JSON should never appear"


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


def _fake_get_conn_raises(exc, calls=None, conn=None):
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


def _fake_session():
    session = MagicMock()
    session.private_payload = PRIVATE_SESSION_DATA
    return session


def _fake_session_data(session=None):
    return {"session": session or _fake_session(), "orch": None, "client": None, "profile": None}


def _params(**overrides):
    params = {"session_id": "sess-1"}
    params.update(overrides)
    return params


def _db_events():
    return [
        {
            "event_id": "evt-2",
            "session_id": "sess-1",
            "legacy_topic_id": "topic-1",
            "event_type": "quiz_evaluation",
            "source": "cache",
            "status": "success",
            "metadata": {"private": PRIVATE_METADATA},
        },
        {
            "event_id": "evt-1",
            "session_id": "sess-1",
            "legacy_topic_id": "topic-1",
            "event_type": "topic_learning_content",
            "source": "claude",
            "status": "success",
            "metadata": {"private": PRIVATE_METADATA},
        },
    ]


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


def _comparison(matches=True):
    return {
        "matches": matches,
        "comparisons": [
            {
                "type": "usage_events_summary",
                "matches": matches,
                "db_missing": False,
                "mismatches": [] if matches else [
                    {"field": "total_events", "session_value": 3, "db_value": 2}
                ],
                "session_summary": _summary() | {"total_events": 3 if not matches else 2},
                "db_summary": _summary(),
            },
            {
                "type": "usage_events_event_ids",
                "matches": matches,
                "db_missing": False,
                "missing_in_db": [] if matches else ["evt-3"],
                "extra_in_db": [],
                "session_event_count": 2 if matches else 3,
                "db_event_count": 2,
            },
        ],
    }


def test_endpoint_exists():
    conn = _make_conn()
    with patch("app._get_session_data", return_value=_fake_session_data()), patch(
        "app.get_conn", _fake_get_conn(conn)
    ), patch(
        "repositories.usage_events_repository.list_usage_events_for_session",
        return_value=_db_events(),
    ), patch(
        "repositories.usage_events_repository.usage_event_summary_for_session",
        return_value=_summary(),
    ), patch(
        "services.usage_events_mismatch_service.compare_usage_events_state",
        return_value=_comparison(True),
    ):
        response = client.get(URL, params=_params())

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")


def test_endpoint_requires_session_id():
    assert client.get(URL).status_code == 422


def test_endpoint_loads_session_context_read_only():
    conn = _make_conn()
    session = _fake_session()
    with patch("app._get_session_data", return_value=_fake_session_data(session)) as get_session, patch(
        "app._save_session"
    ) as save_session, patch(
        "app.get_conn", _fake_get_conn(conn)
    ), patch(
        "repositories.usage_events_repository.list_usage_events_for_session",
        return_value=_db_events(),
    ), patch(
        "repositories.usage_events_repository.usage_event_summary_for_session",
        return_value=_summary(),
    ), patch(
        "services.usage_events_mismatch_service.compare_usage_events_state",
        return_value=_comparison(True),
    ) as compare:
        client.get(URL, params=_params())

    get_session.assert_called_once_with("sess-1", "")
    save_session.assert_not_called()
    assert compare.call_args.kwargs["session"] is session


def test_endpoint_attempts_one_db_connection():
    conn = _make_conn()
    calls = []
    with patch("app._get_session_data", return_value=_fake_session_data()), patch(
        "app.get_conn", _fake_get_conn(conn, calls)
    ), patch(
        "repositories.usage_events_repository.list_usage_events_for_session",
        return_value=_db_events(),
    ), patch(
        "repositories.usage_events_repository.usage_event_summary_for_session",
        return_value=_summary(),
    ), patch(
        "services.usage_events_mismatch_service.compare_usage_events_state",
        return_value=_comparison(True),
    ):
        response = client.get(URL, params=_params())

    assert response.status_code == 200
    assert calls == ["open"]
    assert response.json()["attempted_db_connection"] is True


def test_fake_db_events_and_summary_comparison_returns_source_db_compare():
    conn = _make_conn()
    list_events = MagicMock(return_value=_db_events())
    summary = MagicMock(return_value=_summary())
    compare = MagicMock(return_value=_comparison(True))
    session = _fake_session()
    with patch("app._get_session_data", return_value=_fake_session_data(session)), patch(
        "app.get_conn", _fake_get_conn(conn)
    ), patch(
        "repositories.usage_events_repository.list_usage_events_for_session",
        list_events,
    ), patch(
        "repositories.usage_events_repository.usage_event_summary_for_session",
        summary,
    ), patch(
        "services.usage_events_mismatch_service.compare_usage_events_state",
        compare,
    ):
        response = client.get(URL, params=_params())

    data = response.json()
    assert data["source"] == "db_compare"
    assert data["error"] is None
    list_events.assert_called_once_with(conn, session_id="sess-1", limit=200)
    summary.assert_called_once_with(conn, session_id="sess-1")
    compare.assert_called_once_with(
        session=session,
        db_summary=_summary(),
        db_events=_db_events(),
    )


def test_matches_true_when_comparison_says_true():
    conn = _make_conn()
    with patch("app._get_session_data", return_value=_fake_session_data()), patch(
        "app.get_conn", _fake_get_conn(conn)
    ), patch(
        "repositories.usage_events_repository.list_usage_events_for_session",
        return_value=_db_events(),
    ), patch(
        "repositories.usage_events_repository.usage_event_summary_for_session",
        return_value=_summary(),
    ), patch(
        "services.usage_events_mismatch_service.compare_usage_events_state",
        return_value=_comparison(True),
    ):
        data = client.get(URL, params=_params()).json()

    assert data["source"] == "db_compare"
    assert data["matches"] is True
    assert data["comparison"]["matches"] is True


def test_matches_false_when_comparison_says_false():
    conn = _make_conn()
    with patch("app._get_session_data", return_value=_fake_session_data()), patch(
        "app.get_conn", _fake_get_conn(conn)
    ), patch(
        "repositories.usage_events_repository.list_usage_events_for_session",
        return_value=_db_events(),
    ), patch(
        "repositories.usage_events_repository.usage_event_summary_for_session",
        return_value=_summary(),
    ), patch(
        "services.usage_events_mismatch_service.compare_usage_events_state",
        return_value=_comparison(False),
    ):
        data = client.get(URL, params=_params()).json()

    assert data["source"] == "db_compare"
    assert data["matches"] is False
    assert data["comparison"]["matches"] is False


def test_db_errors_return_source_error_with_safe_error():
    secret_url = "postgresql://user:secret_password@host:5432/db"
    error = RuntimeError(
        f"failed {secret_url} ANTHROPIC_API_KEY=sk-secret SUPABASE_DATABASE_URL={secret_url}"
        + "x" * 600
    )
    with patch("app._get_session_data", return_value=_fake_session_data()), patch(
        "app.get_conn", _fake_get_conn_raises(error)
    ):
        response = client.get(URL, params=_params())

    data = response.json()
    assert response.status_code == 200
    assert data["source"] == "error"
    assert data["matches"] is None
    assert data["comparison"] is None
    assert len(data["error"]) <= 320
    assert "postgresql://" not in response.text
    assert "secret_password" not in response.text
    assert "sk-secret" not in response.text
    assert "SUPABASE_DATABASE_URL" not in response.text
    assert "ANTHROPIC_API_KEY" not in response.text


def test_comparison_errors_return_source_error_with_safe_error():
    conn = _make_conn()
    with patch("app._get_session_data", return_value=_fake_session_data()), patch(
        "app.get_conn", _fake_get_conn(conn)
    ), patch(
        "repositories.usage_events_repository.list_usage_events_for_session",
        return_value=_db_events(),
    ), patch(
        "repositories.usage_events_repository.usage_event_summary_for_session",
        return_value=_summary(),
    ), patch(
        "services.usage_events_mismatch_service.compare_usage_events_state",
        side_effect=RuntimeError("comparison failed DATABASE_URL=postgresql://user:secret@host/db"),
    ):
        response = client.get(URL, params=_params())

    data = response.json()
    assert data["source"] == "error"
    assert data["matches"] is None
    assert data["comparison"] is None
    assert "postgresql://" not in response.text
    assert "DATABASE_URL" not in response.text


def test_connection_is_closed_on_success():
    conn = _make_conn()
    with patch("app._get_session_data", return_value=_fake_session_data()), patch(
        "app.get_conn", _fake_get_conn(conn)
    ), patch(
        "repositories.usage_events_repository.list_usage_events_for_session",
        return_value=_db_events(),
    ), patch(
        "repositories.usage_events_repository.usage_event_summary_for_session",
        return_value=_summary(),
    ), patch(
        "services.usage_events_mismatch_service.compare_usage_events_state",
        return_value=_comparison(True),
    ):
        client.get(URL, params=_params())

    conn.close.assert_called_once()


def test_connection_is_closed_on_error():
    conn = _make_conn()
    with patch("app._get_session_data", return_value=_fake_session_data()), patch(
        "app.get_conn", _fake_get_conn(conn)
    ), patch(
        "repositories.usage_events_repository.list_usage_events_for_session",
        side_effect=RuntimeError("query failed"),
    ):
        client.get(URL, params=_params())

    conn.close.assert_called_once()


def test_limit_is_clamped_to_minimum_one():
    conn = _make_conn()
    list_events = MagicMock(return_value=_db_events())
    with patch("app._get_session_data", return_value=_fake_session_data()), patch(
        "app.get_conn", _fake_get_conn(conn)
    ), patch(
        "repositories.usage_events_repository.list_usage_events_for_session",
        list_events,
    ), patch(
        "repositories.usage_events_repository.usage_event_summary_for_session",
        return_value=_summary(),
    ), patch(
        "services.usage_events_mismatch_service.compare_usage_events_state",
        return_value=_comparison(True),
    ):
        client.get(URL, params=_params(limit="-10"))

    assert list_events.call_args.kwargs["limit"] == 1


def test_limit_is_clamped_to_maximum_500():
    conn = _make_conn()
    list_events = MagicMock(return_value=_db_events())
    with patch("app._get_session_data", return_value=_fake_session_data()), patch(
        "app.get_conn", _fake_get_conn(conn)
    ), patch(
        "repositories.usage_events_repository.list_usage_events_for_session",
        list_events,
    ), patch(
        "repositories.usage_events_repository.usage_event_summary_for_session",
        return_value=_summary(),
    ), patch(
        "services.usage_events_mismatch_service.compare_usage_events_state",
        return_value=_comparison(True),
    ):
        client.get(URL, params=_params(limit="5000"))

    assert list_events.call_args.kwargs["limit"] == 500


def test_invalid_limit_falls_back_to_200():
    conn = _make_conn()
    list_events = MagicMock(return_value=_db_events())
    with patch("app._get_session_data", return_value=_fake_session_data()), patch(
        "app.get_conn", _fake_get_conn(conn)
    ), patch(
        "repositories.usage_events_repository.list_usage_events_for_session",
        list_events,
    ), patch(
        "repositories.usage_events_repository.usage_event_summary_for_session",
        return_value=_summary(),
    ), patch(
        "services.usage_events_mismatch_service.compare_usage_events_state",
        return_value=_comparison(True),
    ):
        response = client.get(URL, params=_params(limit="not-an-int"))

    assert response.status_code == 200
    assert list_events.call_args.kwargs["limit"] == 200


def test_endpoint_does_not_call_save_session():
    conn = _make_conn()
    with patch("app._get_session_data", return_value=_fake_session_data()), patch(
        "app._save_session",
        side_effect=AssertionError("save_session must not be called"),
    ) as save_session, patch(
        "app.get_conn", _fake_get_conn(conn)
    ), patch(
        "repositories.usage_events_repository.list_usage_events_for_session",
        return_value=_db_events(),
    ), patch(
        "repositories.usage_events_repository.usage_event_summary_for_session",
        return_value=_summary(),
    ), patch(
        "services.usage_events_mismatch_service.compare_usage_events_state",
        return_value=_comparison(True),
    ):
        response = client.get(URL, params=_params())

    assert response.status_code == 200
    save_session.assert_not_called()


def test_no_secrets_or_raw_env_values_appear_in_response(monkeypatch):
    monkeypatch.setenv("SUPABASE_DATABASE_URL", "postgresql://user:secret@host/db")
    monkeypatch.setenv("DATABASE_URL", "postgresql://other:secret@host/db")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-live-secret")
    conn = _make_conn()
    with patch("app._get_session_data", return_value=_fake_session_data()), patch(
        "app.get_conn", _fake_get_conn(conn)
    ), patch(
        "repositories.usage_events_repository.list_usage_events_for_session",
        return_value=_db_events(),
    ), patch(
        "repositories.usage_events_repository.usage_event_summary_for_session",
        return_value=_summary(),
    ), patch(
        "services.usage_events_mismatch_service.compare_usage_events_state",
        return_value=_comparison(True),
    ):
        response = client.get(URL, params=_params())

    assert "postgresql://" not in response.text
    assert "sk-live-secret" not in response.text
    assert "SUPABASE_DATABASE_URL" not in response.text
    assert "DATABASE_URL" not in response.text
    assert "ANTHROPIC_API_KEY" not in response.text


def test_no_full_session_data_or_usage_event_metadata_appears_in_response():
    conn = _make_conn()
    with patch("app._get_session_data", return_value=_fake_session_data()), patch(
        "app.get_conn", _fake_get_conn(conn)
    ), patch(
        "repositories.usage_events_repository.list_usage_events_for_session",
        return_value=_db_events(),
    ), patch(
        "repositories.usage_events_repository.usage_event_summary_for_session",
        return_value=_summary(),
    ), patch(
        "services.usage_events_mismatch_service.compare_usage_events_state",
        return_value=_comparison(True),
    ):
        response = client.get(URL, params=_params())

    assert PRIVATE_SESSION_DATA not in response.text
    assert PRIVATE_METADATA not in response.text
    assert '"metadata"' not in response.text


def test_no_learner_facing_route_behavior_changes():
    paths = {route.path for route in app.routes}
    assert {
        "/topics/{session_id}",
        "/topic/{session_id}/{topic_id}",
        "/topic/notes",
        "/topic/content/generate",
        "/topic/practice/generate",
        "/todos/{session_id}",
        "/quiz/submit",
        "/portfolio/submit",
        "/interview/submit",
        URL,
    }.issubset(paths)
