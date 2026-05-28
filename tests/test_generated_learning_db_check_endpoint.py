"""Tests for GET /debug/generated-learning-db-check."""

from __future__ import annotations

import os

os.environ["AI2_TEST_MODE"] = "1"
os.environ["ANTHROPIC_API_KEY"] = "test-key"

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app import app

client = TestClient(app)

URL = "/debug/generated-learning-db-check"


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


def _fake_state():
    return {
        "generated_topic_content": {
            "content": "Learning content",
            "model": "claude-test",
            "version": "1",
            "freshness_label": "AI-generated",
            "source": "claude",
            "legacy_topic_id": "rag-basics",
            "metadata": {},
            "generated_at": "2026-05-18T10:00:00",
        },
        "generated_topic_practice": {
            "quiz": {
                "content": "Quiz content",
                "practice_type": "quiz",
                "legacy_topic_id": "rag-basics",
                "metadata": {},
            },
            "portfolio_task": None,
            "interview_practice": {
                "content": "Interview content",
                "practice_type": "interview_practice",
                "legacy_topic_id": "rag-basics",
                "metadata": {},
            },
        },
        "quiz_submission": {
            "answers": "Q1: A",
            "evaluation": "Good",
            "score": 8,
            "legacy_topic_id": "rag-basics",
            "metadata": {},
            "submitted_at": "2026-05-18T10:01:00",
            "evaluated_at": "2026-05-18T10:02:00",
        },
        "portfolio_submission": None,
        "interview_submission": {
            "answer": "Interview answer",
            "feedback": "Strong",
            "score": 9,
            "legacy_topic_id": "rag-basics",
            "metadata": {},
            "submitted_at": "2026-05-18T10:03:00",
            "reviewed_at": "2026-05-18T10:04:00",
        },
        "topic_notes": {
            "reflection": "Reflection",
            "confusions": "",
            "application_idea": "Build a demo",
            "legacy_topic_id": "rag-basics",
            "metadata": {},
            "updated_at": "2026-05-18T10:05:00",
        },
    }


def _empty_state():
    return {
        "generated_topic_content": None,
        "generated_topic_practice": {
            "quiz": None,
            "portfolio_task": None,
            "interview_practice": None,
        },
        "quiz_submission": None,
        "portfolio_submission": None,
        "interview_submission": None,
        "topic_notes": None,
    }


def _params():
    return {"session_id": "sess-1", "legacy_topic_id": "rag-basics"}


def test_endpoint_exists():
    conn = _make_conn()
    with patch("routes.debug.get_conn", _fake_get_conn(conn)), patch(
        "services.generated_learning_read_service.get_generated_learning_state_from_db",
        return_value=_empty_state(),
    ):
        response = client.get(URL, params=_params())

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")


def test_endpoint_requires_session_id_and_legacy_topic_id():
    assert client.get(URL, params={"session_id": "sess-1"}).status_code == 422
    assert client.get(URL, params={"legacy_topic_id": "rag-basics"}).status_code == 422


def test_endpoint_attempts_one_db_connection():
    conn = _make_conn()
    calls = []
    with patch("routes.debug.get_conn", _fake_get_conn(conn, calls)), patch(
        "services.generated_learning_read_service.get_generated_learning_state_from_db",
        return_value=_empty_state(),
    ):
        response = client.get(URL, params=_params())

    assert response.status_code == 200
    assert calls == ["open"]
    assert response.json()["attempted_db_connection"] is True


def test_fake_db_state_returns_source_db_and_state():
    conn = _make_conn()
    with patch("routes.debug.get_conn", _fake_get_conn(conn)), patch(
        "services.generated_learning_read_service.get_generated_learning_state_from_db",
        return_value=_fake_state(),
    ):
        response = client.get(URL, params=_params())

    data = response.json()
    assert data["source"] == "db"
    assert data["state"]["generated_topic_content"]["content"] == "[redacted]"
    assert "Learning content" not in response.text
    assert "Quiz content" not in response.text
    assert "Interview content" not in response.text
    assert "Q1: A" not in response.text
    assert "Reflection" not in response.text
    assert data["error"] is None


def test_read_service_called_with_session_and_topic():
    conn = _make_conn()
    service = MagicMock(return_value=_empty_state())
    with patch("routes.debug.get_conn", _fake_get_conn(conn)), patch(
        "services.generated_learning_read_service.get_generated_learning_state_from_db",
        service,
    ):
        client.get(URL, params=_params())

    service.assert_called_once_with(
        conn,
        session_id="sess-1",
        legacy_topic_id="rag-basics",
    )


def test_state_found_marks_generated_topic_content():
    conn = _make_conn()
    state = _empty_state()
    state["generated_topic_content"] = {"content": "x"}
    with patch("routes.debug.get_conn", _fake_get_conn(conn)), patch(
        "services.generated_learning_read_service.get_generated_learning_state_from_db",
        return_value=state,
    ):
        data = client.get(URL, params=_params()).json()

    assert data["state_found"]["generated_topic_content"] is True


def test_state_found_marks_practice_types():
    conn = _make_conn()
    state = _empty_state()
    state["generated_topic_practice"] = {
        "quiz": {"content": "quiz"},
        "portfolio_task": None,
        "interview_practice": {"content": "interview"},
    }
    with patch("routes.debug.get_conn", _fake_get_conn(conn)), patch(
        "services.generated_learning_read_service.get_generated_learning_state_from_db",
        return_value=state,
    ):
        found = client.get(URL, params=_params()).json()["state_found"]["generated_topic_practice"]

    assert found == {
        "quiz": True,
        "portfolio_task": False,
        "interview_practice": True,
    }


def test_state_found_marks_submissions_and_notes():
    conn = _make_conn()
    with patch("routes.debug.get_conn", _fake_get_conn(conn)), patch(
        "services.generated_learning_read_service.get_generated_learning_state_from_db",
        return_value=_fake_state(),
    ):
        found = client.get(URL, params=_params()).json()["state_found"]

    assert found["quiz_submission"] is True
    assert found["portfolio_submission"] is False
    assert found["interview_submission"] is True
    assert found["topic_notes"] is True


def test_empty_state_returns_false_values():
    conn = _make_conn()
    with patch("routes.debug.get_conn", _fake_get_conn(conn)), patch(
        "services.generated_learning_read_service.get_generated_learning_state_from_db",
        return_value=_empty_state(),
    ):
        data = client.get(URL, params=_params()).json()

    assert data["state_found"] == {
        "generated_topic_content": False,
        "generated_topic_practice": {
            "quiz": False,
            "portfolio_task": False,
            "interview_practice": False,
        },
        "quiz_submission": False,
        "portfolio_submission": False,
        "interview_submission": False,
        "topic_notes": False,
    }


def test_db_errors_return_source_error_with_safe_truncated_error():
    secret_url = "postgresql://user:secret_password@host:5432/db"
    error = RuntimeError(
        f"failed {secret_url} ANTHROPIC_API_KEY=sk-secret SUPABASE_DATABASE_URL={secret_url}"
        + "x" * 600
    )
    with patch("routes.debug.get_conn", _fake_get_conn_raises(error)):
        response = client.get(URL, params=_params())

    data = response.json()
    assert response.status_code == 200
    assert data["source"] == "error"
    assert data["state"] is None
    assert len(data["error"]) <= 320
    assert "postgresql://" not in response.text
    assert "secret_password" not in response.text
    assert "sk-secret" not in response.text
    assert "SUPABASE_DATABASE_URL" not in response.text
    assert "ANTHROPIC_API_KEY" not in response.text


def test_error_state_found_values_are_false():
    with patch("routes.debug.get_conn", _fake_get_conn_raises(RuntimeError("boom"))):
        found = client.get(URL, params=_params()).json()["state_found"]

    assert found == {
        "generated_topic_content": False,
        "generated_topic_practice": {
            "quiz": False,
            "portfolio_task": False,
            "interview_practice": False,
        },
        "quiz_submission": False,
        "portfolio_submission": False,
        "interview_submission": False,
        "topic_notes": False,
    }


def test_connection_closed_on_success():
    conn = _make_conn()
    with patch("routes.debug.get_conn", _fake_get_conn(conn)), patch(
        "services.generated_learning_read_service.get_generated_learning_state_from_db",
        return_value=_empty_state(),
    ):
        client.get(URL, params=_params())

    conn.close.assert_called_once()


def test_connection_closed_on_error():
    conn = _make_conn()
    with patch("routes.debug.get_conn", _fake_get_conn_raises(RuntimeError("boom"), conn=conn)):
        client.get(URL, params=_params())

    conn.close.assert_called_once()


def test_no_secrets_or_raw_env_values_appear_in_success_response(monkeypatch):
    monkeypatch.setenv("SUPABASE_DATABASE_URL", "postgresql://user:secret@host/db")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-live-secret")
    conn = _make_conn()
    with patch("routes.debug.get_conn", _fake_get_conn(conn)), patch(
        "services.generated_learning_read_service.get_generated_learning_state_from_db",
        return_value=_empty_state(),
    ):
        response = client.get(URL, params=_params())

    assert "postgresql://" not in response.text
    assert "sk-live-secret" not in response.text
    assert "SUPABASE_DATABASE_URL" not in response.text
    assert "ANTHROPIC_API_KEY" not in response.text


def test_learner_facing_session_loading_is_not_called():
    conn = _make_conn()
    with patch("routes.debug.get_conn", _fake_get_conn(conn)), patch(
        "services.generated_learning_read_service.get_generated_learning_state_from_db",
        return_value=_empty_state(),
    ), patch("routes.deps.get_session_data") as get_session:
        client.get(URL, params=_params())

    get_session.assert_not_called()


def test_endpoint_does_not_call_save_session():
    conn = _make_conn()
    with patch("routes.debug.get_conn", _fake_get_conn(conn)), patch(
        "services.generated_learning_read_service.get_generated_learning_state_from_db",
        return_value=_empty_state(),
    ), patch("routes.deps.save_session") as save_session:
        client.get(URL, params=_params())

    save_session.assert_not_called()


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
