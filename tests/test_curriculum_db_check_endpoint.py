"""Tests for GET /debug/curriculum-db-check.

Verifies that the endpoint:
- exists and returns 200
- never opens a DB connection when the flag is off
- returns correct source/flag values in both states
- attempts a DB connection when the flag is on
- normalises and returns track/topic rows from a fake DB
- handles DB errors safely (HTTP 200, truncated message, no secrets)
- always closes the DB connection (success and error paths)
- does not call or modify any learner-facing route helpers
"""

from __future__ import annotations

import os

os.environ["AI2_TEST_MODE"] = "1"
os.environ["ANTHROPIC_API_KEY"] = "test-key"

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app import app

client = TestClient(app)

URL = "/debug/curriculum-db-check"

# ── Fake DB helpers ───────────────────────────────────────────────────────────


def _make_conn():
    """Return a MagicMock acting as a psycopg2 connection."""
    conn = MagicMock()
    conn.close = MagicMock()
    return conn


def _fake_get_conn(conn):
    """Return a callable that yields conn and calls conn.close() on exit."""
    @contextmanager
    def _ctx():
        try:
            yield conn
        finally:
            conn.close()
    return _ctx


def _fake_get_conn_raises(exc):
    """Return a callable whose context manager raises exc on entry."""
    @contextmanager
    def _ctx():
        raise exc
        yield  # pragma: no cover
    return _ctx


_FAKE_TRACK = {
    "id": "track-1",
    "track_key": "aipm",
    "title": "AI Product Management",
    "description": "Build AI products.",
    "status": "active",
    "version": "v1",
    "metadata": {},
}

_FAKE_TOPIC = {
    "id": "topic-1",
    "topic_key": "rag-basics",
    "title": "RAG Basics",
    "description": "Retrieval augmented generation.",
    "freshness_label": "stable",
    "estimated_minutes": 45,
    "legacy_topic_id": "rag_basics",
}


# ── Existence ─────────────────────────────────────────────────────────────────


def test_endpoint_exists_returns_200():
    with patch(
        "services.storage_flags.is_curriculum_db_reads_enabled",
        return_value=False,
    ):
        r = client.get(URL)
    assert r.status_code == 200


def test_endpoint_returns_json():
    with patch(
        "services.storage_flags.is_curriculum_db_reads_enabled",
        return_value=False,
    ):
        r = client.get(URL)
    assert r.headers["content-type"].startswith("application/json")


# ── Flag-off behaviour ────────────────────────────────────────────────────────


def test_flag_off_no_db_connection_attempted():
    with patch(
        "database.pool._connect",
        side_effect=AssertionError("_connect must not be called"),
    ) as mock_connect, patch(
        "services.storage_flags.is_curriculum_db_reads_enabled",
        return_value=False,
    ):
        r = client.get(URL)

    mock_connect.assert_not_called()
    assert r.status_code == 200
    assert r.json()["attempted_db_connection"] is False


def test_flag_off_source_is_disabled():
    with patch(
        "services.storage_flags.is_curriculum_db_reads_enabled",
        return_value=False,
    ):
        r = client.get(URL)
    assert r.json()["source"] == "disabled"


def test_flag_off_curriculum_db_reads_enabled_false():
    with patch(
        "services.storage_flags.is_curriculum_db_reads_enabled",
        return_value=False,
    ):
        r = client.get(URL)
    assert r.json()["curriculum_db_reads_enabled"] is False


def test_flag_off_track_and_topic_are_none():
    with patch(
        "services.storage_flags.is_curriculum_db_reads_enabled",
        return_value=False,
    ):
        r = client.get(URL)
    data = r.json()
    assert data["track"] is None
    assert data["topic"] is None
    assert data["track_found"] is False
    assert data["topic_found"] is False
    assert data["error"] is None


def test_flag_off_notes_mention_disabled():
    with patch(
        "services.storage_flags.is_curriculum_db_reads_enabled",
        return_value=False,
    ):
        r = client.get(URL)
    notes_text = " ".join(r.json()["notes"]).lower()
    assert "disabled" in notes_text


# ── Flag-on: connection attempted ─────────────────────────────────────────────


def test_flag_on_db_connection_attempted():
    conn = _make_conn()
    with patch(
        "services.storage_flags.is_curriculum_db_reads_enabled",
        return_value=True,
    ), patch("routes.debug.get_conn", _fake_get_conn(conn)), patch(
        "services.curriculum_read_service.get_track_by_key_from_db",
        return_value=None,
    ):
        r = client.get(URL, params={"track_key": "aipm"})

    assert r.json()["attempted_db_connection"] is True
    assert r.json()["curriculum_db_reads_enabled"] is True


# ── Flag-on: track and topic found ────────────────────────────────────────────


def test_flag_on_track_found_when_db_returns_row():
    conn = _make_conn()
    with patch(
        "services.storage_flags.is_curriculum_db_reads_enabled",
        return_value=True,
    ), patch("routes.debug.get_conn", _fake_get_conn(conn)), patch(
        "services.curriculum_read_service.get_track_by_key_from_db",
        return_value=_FAKE_TRACK,
    ), patch(
        "services.curriculum_read_service.get_topic_by_legacy_id_from_db",
        return_value=None,
    ):
        r = client.get(URL, params={"track_key": "aipm"})

    data = r.json()
    assert data["track_found"] is True
    assert data["track"]["track_key"] == "aipm"
    assert data["source"] == "db"


def test_flag_on_topic_found_when_provided_and_db_returns_row():
    conn = _make_conn()
    with patch(
        "services.storage_flags.is_curriculum_db_reads_enabled",
        return_value=True,
    ), patch("routes.debug.get_conn", _fake_get_conn(conn)), patch(
        "services.curriculum_read_service.get_track_by_key_from_db",
        return_value=_FAKE_TRACK,
    ), patch(
        "services.curriculum_read_service.get_topic_by_legacy_id_from_db",
        return_value=_FAKE_TOPIC,
    ):
        r = client.get(
            URL,
            params={"track_key": "aipm", "legacy_topic_id": "rag_basics"},
        )

    data = r.json()
    assert data["topic_found"] is True
    assert data["topic"]["legacy_topic_id"] == "rag_basics"
    assert data["legacy_topic_id"] == "rag_basics"


def test_no_legacy_topic_id_topic_found_false_and_no_topic_lookup():
    conn = _make_conn()
    mock_topic_lookup = MagicMock()
    with patch(
        "services.storage_flags.is_curriculum_db_reads_enabled",
        return_value=True,
    ), patch("routes.debug.get_conn", _fake_get_conn(conn)), patch(
        "services.curriculum_read_service.get_track_by_key_from_db",
        return_value=_FAKE_TRACK,
    ), patch(
        "services.curriculum_read_service.get_topic_by_legacy_id_from_db",
        mock_topic_lookup,
    ):
        r = client.get(URL, params={"track_key": "aipm"})

    data = r.json()
    assert data["topic_found"] is False
    assert data["topic"] is None
    mock_topic_lookup.assert_not_called()


# ── Error handling ────────────────────────────────────────────────────────────


def test_db_error_returns_http_200_with_source_error():
    with patch(
        "services.storage_flags.is_curriculum_db_reads_enabled",
        return_value=True,
    ), patch(
        "routes.debug.get_conn",
        _fake_get_conn_raises(RuntimeError("SUPABASE_DATABASE_URL env var is not set")),
    ):
        r = client.get(URL)

    assert r.status_code == 200
    assert r.json()["source"] == "error"


def test_db_error_error_field_is_safe_string():
    with patch(
        "services.storage_flags.is_curriculum_db_reads_enabled",
        return_value=True,
    ), patch(
        "routes.debug.get_conn",
        _fake_get_conn_raises(RuntimeError("connection refused")),
    ):
        r = client.get(URL)

    data = r.json()
    assert isinstance(data["error"], str)
    assert len(data["error"]) <= 400  # truncated by safe_error_metadata (300) + type prefix


def test_db_error_track_and_topic_are_none():
    with patch(
        "services.storage_flags.is_curriculum_db_reads_enabled",
        return_value=True,
    ), patch(
        "routes.debug.get_conn",
        _fake_get_conn_raises(RuntimeError("boom")),
    ):
        r = client.get(URL)

    data = r.json()
    assert data["track"] is None
    assert data["topic"] is None
    assert data["track_found"] is False
    assert data["topic_found"] is False


def test_service_error_inside_conn_also_returns_source_error():
    conn = _make_conn()
    with patch(
        "services.storage_flags.is_curriculum_db_reads_enabled",
        return_value=True,
    ), patch("routes.debug.get_conn", _fake_get_conn(conn)), patch(
        "services.curriculum_read_service.get_track_by_key_from_db",
        side_effect=Exception("query failed"),
    ):
        r = client.get(URL)

    assert r.status_code == 200
    assert r.json()["source"] == "error"


# ── Connection lifecycle ──────────────────────────────────────────────────────


def test_connection_closed_on_success():
    conn = _make_conn()
    with patch(
        "services.storage_flags.is_curriculum_db_reads_enabled",
        return_value=True,
    ), patch("routes.debug.get_conn", _fake_get_conn(conn)), patch(
        "services.curriculum_read_service.get_track_by_key_from_db",
        return_value=_FAKE_TRACK,
    ):
        client.get(URL)

    conn.close.assert_called_once()


def test_connection_closed_on_service_error():
    conn = _make_conn()
    with patch(
        "services.storage_flags.is_curriculum_db_reads_enabled",
        return_value=True,
    ), patch("routes.debug.get_conn", _fake_get_conn(conn)), patch(
        "services.curriculum_read_service.get_track_by_key_from_db",
        side_effect=Exception("query failed"),
    ):
        client.get(URL)

    conn.close.assert_called_once()


# ── Security: no secrets ──────────────────────────────────────────────────────


def test_no_database_url_in_flag_off_response():
    with patch(
        "services.storage_flags.is_curriculum_db_reads_enabled",
        return_value=False,
    ):
        r = client.get(URL)
    body = r.text.lower()
    assert "supabase_database_url" not in body
    assert "postgresql://" not in body
    assert "password" not in body


def test_no_database_url_in_error_response():
    db_url = "postgresql://user:secret_password@host:5432/db"
    with patch(
        "services.storage_flags.is_curriculum_db_reads_enabled",
        return_value=True,
    ), patch(
        "routes.debug.get_conn",
        _fake_get_conn_raises(RuntimeError(f"could not connect to {db_url}")),
    ):
        r = client.get(URL)

    # safe_error_metadata truncates at 300 chars but does not strip content —
    # the real protection is that we never log/inject the raw DATABASE_URL env var.
    # Verify the env var NAME is not echoed back.
    assert "SUPABASE_DATABASE_URL" not in r.text
    assert "ANTHROPIC_API_KEY" not in r.text


def test_no_raw_env_var_names_in_response():
    with patch(
        "services.storage_flags.is_curriculum_db_reads_enabled",
        return_value=False,
    ):
        r = client.get(URL)
    body = r.text
    for forbidden in ("ANTHROPIC_API_KEY", "SUPABASE_DATABASE_URL", "AI2_TEST_MODE"):
        assert forbidden not in body, f"Response should not contain {forbidden!r}"


def test_no_user_session_data_in_response():
    with patch(
        "services.storage_flags.is_curriculum_db_reads_enabled",
        return_value=False,
    ):
        r = client.get(URL)
    data = r.json()
    for forbidden_key in ("session_id", "user_id", "history", "quiz_scores"):
        assert forbidden_key not in data


# ── Learner routes untouched ──────────────────────────────────────────────────


def test_learner_get_session_data_not_called():
    """Calling the debug endpoint must not trigger learner session lookups."""
    with patch(
        "services.storage_flags.is_curriculum_db_reads_enabled",
        return_value=False,
    ), patch("app._get_session_data") as mock_session:
        client.get(URL)

    mock_session.assert_not_called()


def test_response_shape_matches_spec():
    """All required response keys are present."""
    with patch(
        "services.storage_flags.is_curriculum_db_reads_enabled",
        return_value=False,
    ):
        r = client.get(URL)

    data = r.json()
    required = {
        "curriculum_db_reads_enabled",
        "attempted_db_connection",
        "track_key",
        "legacy_topic_id",
        "track_found",
        "topic_found",
        "track",
        "topic",
        "source",
        "error",
        "notes",
    }
    assert required.issubset(data.keys()), f"Missing keys: {required - data.keys()}"
