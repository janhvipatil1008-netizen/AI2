"""Tests for GET /debug/generated-learning-mismatch-check."""

from __future__ import annotations

import os

os.environ["AI2_TEST_MODE"] = "1"
os.environ["ANTHROPIC_API_KEY"] = "test-key"

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app import app

client = TestClient(app)

URL = "/debug/generated-learning-mismatch-check"

PRIVATE_CONTENT = "full generated content should never appear"
PRIVATE_ANSWERS = "full quiz answers should never appear"
PRIVATE_NOTES = "full private notes should never appear"


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


def _fake_session_data(session=None):
    return {"session": session or object(), "orch": None, "client": None, "profile": None}


def _params():
    return {"session_id": "sess-1", "legacy_topic_id": "rag-basics"}


def _db_state():
    return {
        "generated_topic_content": {"content": PRIVATE_CONTENT},
        "generated_topic_practice": {"quiz": None, "portfolio_task": None, "interview_practice": None},
        "quiz_submission": {"answers": PRIVATE_ANSWERS},
        "portfolio_submission": None,
        "interview_submission": None,
        "topic_notes": {"reflection": PRIVATE_NOTES},
    }


def _comparison(matches=True):
    return {
        "matches": matches,
        "legacy_topic_id": "rag-basics",
        "comparisons": [
            {
                "type": "generated_topic_content",
                "matches": matches,
                "session_snapshot": {"content_present": True, "content_length": 40},
                "db_snapshot": {"content_present": True, "content_length": 40},
                "mismatches": [] if matches else [{"field": "content_length", "session_value": 40, "db_value": 41}],
            }
        ],
    }


def test_endpoint_exists():
    conn = _make_conn()
    with patch("app._get_session_data", return_value=_fake_session_data()), patch(
        "app.get_conn", _fake_get_conn(conn)
    ), patch(
        "services.generated_learning_read_service.get_generated_learning_state_from_db",
        return_value=_db_state(),
    ), patch(
        "services.generated_learning_mismatch_service.compare_generated_learning_state",
        return_value=_comparison(True),
    ):
        response = client.get(URL, params=_params())

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")


def test_endpoint_requires_session_id_and_legacy_topic_id():
    assert client.get(URL, params={"session_id": "sess-1"}).status_code == 422
    assert client.get(URL, params={"legacy_topic_id": "rag-basics"}).status_code == 422


def test_endpoint_loads_session_context_read_only():
    conn = _make_conn()
    session = object()
    with patch("app._get_session_data", return_value=_fake_session_data(session)) as get_session, patch(
        "app._save_session"
    ) as save_session, patch(
        "app.get_conn", _fake_get_conn(conn)
    ), patch(
        "services.generated_learning_read_service.get_generated_learning_state_from_db",
        return_value=_db_state(),
    ), patch(
        "services.generated_learning_mismatch_service.compare_generated_learning_state",
        return_value=_comparison(True),
    ):
        client.get(URL, params=_params())

    get_session.assert_called_once_with("sess-1", "")
    save_session.assert_not_called()


def test_endpoint_attempts_one_db_connection():
    conn = _make_conn()
    calls = []
    with patch("app._get_session_data", return_value=_fake_session_data()), patch(
        "app.get_conn", _fake_get_conn(conn, calls)
    ), patch(
        "services.generated_learning_read_service.get_generated_learning_state_from_db",
        return_value=_db_state(),
    ), patch(
        "services.generated_learning_mismatch_service.compare_generated_learning_state",
        return_value=_comparison(True),
    ):
        response = client.get(URL, params=_params())

    assert calls == ["open"]
    assert response.json()["attempted_db_connection"] is True


def test_fake_db_state_and_comparison_returns_source_db_compare():
    conn = _make_conn()
    read_service = MagicMock(return_value=_db_state())
    compare_service = MagicMock(return_value=_comparison(True))
    session = object()
    with patch("app._get_session_data", return_value=_fake_session_data(session)), patch(
        "app.get_conn", _fake_get_conn(conn)
    ), patch(
        "services.generated_learning_read_service.get_generated_learning_state_from_db",
        read_service,
    ), patch(
        "services.generated_learning_mismatch_service.compare_generated_learning_state",
        compare_service,
    ):
        response = client.get(URL, params=_params())

    data = response.json()
    assert data["source"] == "db_compare"
    assert data["comparison"]["legacy_topic_id"] == "rag-basics"
    assert data["error"] is None
    read_service.assert_called_once_with(conn, session_id="sess-1", legacy_topic_id="rag-basics")
    compare_service.assert_called_once_with(
        session=session,
        legacy_topic_id="rag-basics",
        db_state=_db_state(),
    )


def test_matches_true_when_comparison_says_true():
    conn = _make_conn()
    with patch("app._get_session_data", return_value=_fake_session_data()), patch(
        "app.get_conn", _fake_get_conn(conn)
    ), patch(
        "services.generated_learning_read_service.get_generated_learning_state_from_db",
        return_value=_db_state(),
    ), patch(
        "services.generated_learning_mismatch_service.compare_generated_learning_state",
        return_value=_comparison(True),
    ):
        data = client.get(URL, params=_params()).json()

    assert data["matches"] is True


def test_matches_false_when_comparison_says_false():
    conn = _make_conn()
    with patch("app._get_session_data", return_value=_fake_session_data()), patch(
        "app.get_conn", _fake_get_conn(conn)
    ), patch(
        "services.generated_learning_read_service.get_generated_learning_state_from_db",
        return_value=_db_state(),
    ), patch(
        "services.generated_learning_mismatch_service.compare_generated_learning_state",
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
        "services.generated_learning_read_service.get_generated_learning_state_from_db",
        return_value=_db_state(),
    ), patch(
        "services.generated_learning_mismatch_service.compare_generated_learning_state",
        side_effect=RuntimeError("comparison failed DATABASE_URL=postgresql://user:secret@host/db"),
    ):
        response = client.get(URL, params=_params())

    data = response.json()
    assert data["source"] == "error"
    assert data["matches"] is None
    assert data["comparison"] is None
    assert "postgresql://" not in response.text
    assert "DATABASE_URL" not in response.text


def test_connection_closed_on_success():
    conn = _make_conn()
    with patch("app._get_session_data", return_value=_fake_session_data()), patch(
        "app.get_conn", _fake_get_conn(conn)
    ), patch(
        "services.generated_learning_read_service.get_generated_learning_state_from_db",
        return_value=_db_state(),
    ), patch(
        "services.generated_learning_mismatch_service.compare_generated_learning_state",
        return_value=_comparison(True),
    ):
        client.get(URL, params=_params())

    conn.close.assert_called_once()


def test_connection_closed_on_error():
    conn = _make_conn()
    with patch("app._get_session_data", return_value=_fake_session_data()), patch(
        "app.get_conn", _fake_get_conn(conn)
    ), patch(
        "services.generated_learning_read_service.get_generated_learning_state_from_db",
        side_effect=RuntimeError("query failed"),
    ):
        client.get(URL, params=_params())

    conn.close.assert_called_once()


def test_endpoint_does_not_call_save_session():
    conn = _make_conn()
    with patch("app._get_session_data", return_value=_fake_session_data()), patch(
        "app._save_session"
    ) as save_session, patch(
        "app.get_conn", _fake_get_conn(conn)
    ), patch(
        "services.generated_learning_read_service.get_generated_learning_state_from_db",
        return_value=_db_state(),
    ), patch(
        "services.generated_learning_mismatch_service.compare_generated_learning_state",
        return_value=_comparison(True),
    ):
        client.get(URL, params=_params())

    save_session.assert_not_called()


def test_no_secrets_or_raw_env_values_appear_in_response(monkeypatch):
    monkeypatch.setenv("SUPABASE_DATABASE_URL", "postgresql://user:secret@host/db")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-live-secret")
    conn = _make_conn()
    with patch("app._get_session_data", return_value=_fake_session_data()), patch(
        "app.get_conn", _fake_get_conn(conn)
    ), patch(
        "services.generated_learning_read_service.get_generated_learning_state_from_db",
        return_value=_db_state(),
    ), patch(
        "services.generated_learning_mismatch_service.compare_generated_learning_state",
        return_value=_comparison(True),
    ):
        response = client.get(URL, params=_params())

    assert "postgresql://" not in response.text
    assert "sk-live-secret" not in response.text
    assert "SUPABASE_DATABASE_URL" not in response.text
    assert "ANTHROPIC_API_KEY" not in response.text


def test_no_full_generated_or_user_text_appears_in_response():
    conn = _make_conn()
    with patch("app._get_session_data", return_value=_fake_session_data()), patch(
        "app.get_conn", _fake_get_conn(conn)
    ), patch(
        "services.generated_learning_read_service.get_generated_learning_state_from_db",
        return_value=_db_state(),
    ), patch(
        "services.generated_learning_mismatch_service.compare_generated_learning_state",
        return_value=_comparison(True),
    ):
        response = client.get(URL, params=_params())

    for forbidden in (PRIVATE_CONTENT, PRIVATE_ANSWERS, PRIVATE_NOTES):
        assert forbidden not in response.text


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
    }.issubset(paths)
