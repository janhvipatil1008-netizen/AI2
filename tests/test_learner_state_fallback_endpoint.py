"""Tests for GET /debug/learner-state-fallback-check endpoint."""

from __future__ import annotations

import os

# Must be set before app is imported so TEST_MODE=True bypasses auth middleware.
os.environ["AI2_TEST_MODE"]     = "1"
os.environ["ANTHROPIC_API_KEY"] = "test-key"

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from config import CareerTrack
from context.session import SessionContext
from app import app

client = TestClient(app)

URL = "/debug/learner-state-fallback-check"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_session() -> SessionContext:
    return SessionContext(track=CareerTrack.AI_PM)


def _fake_session_data(session=None) -> dict:
    s = session or _make_session()
    return {"session": s, "orch": None, "client": None, "profile": None}


def _make_conn() -> MagicMock:
    conn = MagicMock()
    conn.close = MagicMock()
    return conn


def _fake_get_conn(conn):
    @contextmanager
    def _ctx():
        try:
            yield conn
        finally:
            conn.close()
    return _ctx


def _fake_get_conn_raises(exc):
    @contextmanager
    def _ctx():
        raise exc
        yield  # pragma: no cover
    return _ctx


_FAKE_FALLBACK_RESULT = {
    "topic_progress_result": {
        "source":         "fallback",
        "topic_progress": {
            "learn": "not_started", "quiz": "not_started",
            "portfolio_task": "not_started", "interview_practice": "not_started",
            "reflection": "not_started", "completion_percent": 0,
            "legacy_topic_id": "rag-basics",
        },
        "error": None,
        "notes": [],
    },
    "todos_result": {
        "source": "fallback",
        "todos":  [],
        "error":  None,
        "notes":  [],
    },
    "source_summary": {
        "topic_progress_source": "fallback",
        "todos_source":          "fallback",
    },
    "notes": [],
}

_FAKE_DB_RESULT = {
    "topic_progress_result": {
        "source":         "db",
        "topic_progress": {
            "learn": "done", "quiz": "not_started",
            "portfolio_task": "not_started", "interview_practice": "not_started",
            "reflection": "not_started", "completion_percent": 20,
            "legacy_topic_id": "rag-basics",
        },
        "error": None,
        "notes": [],
    },
    "todos_result": {
        "source": "db",
        "todos":  [],
        "error":  None,
        "notes":  [],
    },
    "source_summary": {
        "topic_progress_source": "db",
        "todos_source":          "db",
    },
    "notes": [],
}

_FLAGS_OFF = [
    patch("services.storage_flags.is_progress_db_reads_enabled", return_value=False),
    patch("services.storage_flags.is_todos_db_reads_enabled",    return_value=False),
]

_PROGRESS_ON = [
    patch("services.storage_flags.is_progress_db_reads_enabled", return_value=True),
    patch("services.storage_flags.is_todos_db_reads_enabled",    return_value=False),
]

_TODOS_ON = [
    patch("services.storage_flags.is_progress_db_reads_enabled", return_value=False),
    patch("services.storage_flags.is_todos_db_reads_enabled",    return_value=True),
]

_BOTH_ON = [
    patch("services.storage_flags.is_progress_db_reads_enabled", return_value=True),
    patch("services.storage_flags.is_todos_db_reads_enabled",    return_value=True),
]


def _apply(*patches):
    """Context manager that enters multiple patches at once."""
    from contextlib import ExitStack

    class _Multi:
        def __enter__(self_):
            self_._stack = ExitStack()
            for p in patches:
                self_._stack.enter_context(p)
            return self_

        def __exit__(self_, *a):
            self_._stack.__exit__(*a)

    return _Multi()


# ── Existence and shape ───────────────────────────────────────────────────────

def test_endpoint_exists_returns_200():
    with patch("routes.deps.get_session_data", return_value=_fake_session_data()):
        with _apply(*_FLAGS_OFF):
            resp = client.get(URL)
    assert resp.status_code == 200


def test_endpoint_returns_json():
    with patch("routes.deps.get_session_data", return_value=_fake_session_data()):
        with _apply(*_FLAGS_OFF):
            resp = client.get(URL)
    assert resp.headers["content-type"].startswith("application/json")


def test_response_has_all_required_keys():
    with patch("routes.deps.get_session_data", return_value=_fake_session_data()):
        with _apply(*_FLAGS_OFF):
            resp = client.get(URL)
    data = resp.json()
    for key in (
        "session_id", "legacy_topic_id",
        "progress_db_reads_enabled", "todos_db_reads_enabled",
        "attempted_db_connection", "result",
        "source_summary", "error", "notes",
    ):
        assert key in data, f"Missing key: {key}"


def test_source_summary_has_required_keys():
    with patch("routes.deps.get_session_data", return_value=_fake_session_data()):
        with _apply(*_FLAGS_OFF):
            with patch(
                "services.learner_state_fallback_service.get_learner_state_with_fallback",
                return_value=_FAKE_FALLBACK_RESULT,
            ):
                resp = client.get(URL)
    summary = resp.json()["source_summary"]
    assert "topic_progress_source" in summary
    assert "todos_source" in summary


# ── Flags off: no DB connection ───────────────────────────────────────────────

def test_flags_off_attempted_db_connection_false():
    with patch("routes.deps.get_session_data", return_value=_fake_session_data()):
        with _apply(*_FLAGS_OFF):
            resp = client.get(URL)
    assert resp.json()["attempted_db_connection"] is False


def test_flags_off_get_conn_not_called():
    with patch("routes.deps.get_session_data", return_value=_fake_session_data()):
        with _apply(*_FLAGS_OFF):
            with patch("routes.debug.get_conn") as mock_conn:
                client.get(URL)
    mock_conn.assert_not_called()


def test_flags_off_result_uses_session_fallback_sources():
    with patch("routes.deps.get_session_data", return_value=_fake_session_data()):
        with _apply(*_FLAGS_OFF):
            with patch(
                "services.learner_state_fallback_service.get_learner_state_with_fallback",
                return_value=_FAKE_FALLBACK_RESULT,
            ):
                resp = client.get(URL)
    data = resp.json()
    assert data["source_summary"]["todos_source"] == "fallback"
    assert data["progress_db_reads_enabled"] is False
    assert data["todos_db_reads_enabled"] is False


def test_flags_off_notes_mention_flags_off():
    with patch("routes.deps.get_session_data", return_value=_fake_session_data()):
        with _apply(*_FLAGS_OFF):
            with patch(
                "services.learner_state_fallback_service.get_learner_state_with_fallback",
                return_value=_FAKE_FALLBACK_RESULT,
            ):
                resp = client.get(URL)
    notes = resp.json()["notes"]
    assert any("fallback" in n.lower() or "off" in n.lower() for n in notes)


# ── Flags on: DB connection attempted ────────────────────────────────────────

def test_progress_flag_on_db_connection_attempted():
    conn = _make_conn()
    with patch("routes.deps.get_session_data", return_value=_fake_session_data()):
        with _apply(*_PROGRESS_ON):
            with patch("routes.debug.get_conn", _fake_get_conn(conn)):
                with patch(
                    "services.learner_state_fallback_service.get_learner_state_with_fallback",
                    return_value=_FAKE_FALLBACK_RESULT,
                ):
                    resp = client.get(URL)
    assert resp.json()["attempted_db_connection"] is True
    assert resp.json()["progress_db_reads_enabled"] is True


def test_todos_flag_on_db_connection_attempted():
    conn = _make_conn()
    with patch("routes.deps.get_session_data", return_value=_fake_session_data()):
        with _apply(*_TODOS_ON):
            with patch("routes.debug.get_conn", _fake_get_conn(conn)):
                with patch(
                    "services.learner_state_fallback_service.get_learner_state_with_fallback",
                    return_value=_FAKE_FALLBACK_RESULT,
                ):
                    resp = client.get(URL)
    assert resp.json()["attempted_db_connection"] is True
    assert resp.json()["todos_db_reads_enabled"] is True


def test_both_flags_on_one_connection_opened():
    conn = _make_conn()
    with patch("routes.deps.get_session_data", return_value=_fake_session_data()):
        with _apply(*_BOTH_ON):
            with patch("routes.debug.get_conn", _fake_get_conn(conn)):
                with patch(
                    "services.learner_state_fallback_service.get_learner_state_with_fallback",
                    return_value=_FAKE_DB_RESULT,
                ):
                    client.get(URL)
    conn.close.assert_called_once()


def test_flag_on_db_result_source_summary_shows_db():
    conn = _make_conn()
    with patch("routes.deps.get_session_data", return_value=_fake_session_data()):
        with _apply(*_BOTH_ON):
            with patch("routes.debug.get_conn", _fake_get_conn(conn)):
                with patch(
                    "services.learner_state_fallback_service.get_learner_state_with_fallback",
                    return_value=_FAKE_DB_RESULT,
                ):
                    resp = client.get(URL)
    data = resp.json()
    assert data["source_summary"]["todos_source"] == "db"
    assert data["error"] is None


# ── Error handling ────────────────────────────────────────────────────────────

def test_db_connection_error_returns_http_200():
    with patch("routes.deps.get_session_data", return_value=_fake_session_data()):
        with _apply(*_BOTH_ON):
            with patch("routes.debug.get_conn", _fake_get_conn_raises(RuntimeError("DB down"))):
                resp = client.get(URL)
    assert resp.status_code == 200


def test_db_connection_error_sets_error_field():
    with patch("routes.deps.get_session_data", return_value=_fake_session_data()):
        with _apply(*_BOTH_ON):
            with patch("routes.debug.get_conn", _fake_get_conn_raises(RuntimeError("refused"))):
                resp = client.get(URL)
    data = resp.json()
    assert data["error"] is not None
    assert "RuntimeError" in data["error"]


def test_db_connection_error_result_is_none():
    with patch("routes.deps.get_session_data", return_value=_fake_session_data()):
        with _apply(*_BOTH_ON):
            with patch("routes.debug.get_conn", _fake_get_conn_raises(RuntimeError("DB down"))):
                resp = client.get(URL)
    assert resp.json()["result"] is None


def test_service_error_inside_conn_returns_safe_response():
    conn = _make_conn()
    with patch("routes.deps.get_session_data", return_value=_fake_session_data()):
        with _apply(*_BOTH_ON):
            with patch("routes.debug.get_conn", _fake_get_conn(conn)):
                with patch(
                    "services.learner_state_fallback_service.get_learner_state_with_fallback",
                    side_effect=RuntimeError("service explosion"),
                ):
                    resp = client.get(URL)
    assert resp.status_code == 200
    assert resp.json()["error"] is not None


# ── Connection lifecycle ──────────────────────────────────────────────────────

def test_connection_closed_on_success():
    conn = _make_conn()
    with patch("routes.deps.get_session_data", return_value=_fake_session_data()):
        with _apply(*_BOTH_ON):
            with patch("routes.debug.get_conn", _fake_get_conn(conn)):
                with patch(
                    "services.learner_state_fallback_service.get_learner_state_with_fallback",
                    return_value=_FAKE_DB_RESULT,
                ):
                    client.get(URL)
    conn.close.assert_called_once()


def test_connection_closed_on_service_error():
    conn = _make_conn()
    with patch("routes.deps.get_session_data", return_value=_fake_session_data()):
        with _apply(*_BOTH_ON):
            with patch("routes.debug.get_conn", _fake_get_conn(conn)):
                with patch(
                    "services.learner_state_fallback_service.get_learner_state_with_fallback",
                    side_effect=RuntimeError("boom"),
                ):
                    client.get(URL)
    conn.close.assert_called_once()


# ── Session safety ────────────────────────────────────────────────────────────

def test_endpoint_does_not_call_save_session():
    with patch("routes.deps.get_session_data", return_value=_fake_session_data()):
        with _apply(*_FLAGS_OFF):
            with patch("app._save_session") as mock_save:
                client.get(URL)
    mock_save.assert_not_called()


def test_endpoint_does_not_call_save_session_when_flags_on():
    conn = _make_conn()
    with patch("routes.deps.get_session_data", return_value=_fake_session_data()):
        with _apply(*_BOTH_ON):
            with patch("routes.debug.get_conn", _fake_get_conn(conn)):
                with patch(
                    "services.learner_state_fallback_service.get_learner_state_with_fallback",
                    return_value=_FAKE_DB_RESULT,
                ):
                    with patch("app._save_session") as mock_save:
                        client.get(URL)
    mock_save.assert_not_called()


# ── Security ──────────────────────────────────────────────────────────────────

def test_no_raw_env_var_names_in_flags_off_response():
    with patch("routes.deps.get_session_data", return_value=_fake_session_data()):
        with _apply(*_FLAGS_OFF):
            resp = client.get(URL)
    body = resp.text
    for secret in ("SUPABASE_DATABASE_URL", "ANTHROPIC_API_KEY", "AI2_TEST_MODE"):
        assert secret not in body, f"Secret leaked: {secret}"


def test_no_database_url_in_error_response():
    exc = Exception("postgresql://user:secret@db.supabase.co/postgres")
    with patch("routes.deps.get_session_data", return_value=_fake_session_data()):
        with _apply(*_BOTH_ON):
            with patch("routes.debug.get_conn", _fake_get_conn_raises(exc)):
                resp = client.get(URL)
    assert "SUPABASE_DATABASE_URL" not in resp.text
    assert resp.json()["error"] is not None
    assert len(resp.json()["error"]) <= 400


def test_error_message_is_truncated():
    exc = RuntimeError("X" * 400)
    with patch("routes.deps.get_session_data", return_value=_fake_session_data()):
        with _apply(*_BOTH_ON):
            with patch("routes.debug.get_conn", _fake_get_conn_raises(exc)):
                resp = client.get(URL)
    assert len(resp.json()["error"]) <= 350


def test_session_id_reflected_in_response():
    with patch("routes.deps.get_session_data", return_value=_fake_session_data()):
        with _apply(*_FLAGS_OFF):
            resp = client.get(URL, params={"session_id": "test-session-42"})
    assert resp.json()["session_id"] == "test-session-42"
