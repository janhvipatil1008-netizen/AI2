"""Tests for GET /debug/curriculum-fallback-check endpoint."""

from __future__ import annotations

import os

# Must be set before app is imported so TEST_MODE=True bypasses auth middleware.
os.environ["AI2_TEST_MODE"]      = "1"
os.environ["ANTHROPIC_API_KEY"]  = "test-key"

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app import app

client = TestClient(app)


# ── Helpers ───────────────────────────────────────────────────────────────────

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


_FLAG_OFF = patch(
    "services.storage_flags.is_curriculum_db_reads_enabled", return_value=False
)
_FLAG_ON = patch(
    "services.storage_flags.is_curriculum_db_reads_enabled", return_value=True
)

_FAKE_TRACK_FALLBACK = {
    "source":    "fallback",
    "track_key": "aipm",
    "track": {
        "track_key": "aipm", "title": "AI Product Manager",
        "description": "Build AI products that matter.",
        "status": "active", "version": "", "metadata": {},
    },
    "error": None,
    "notes": [],
}

_FAKE_TRACK_DB = {
    "source":    "db",
    "track_key": "aipm",
    "track": {
        "track_key": "aipm", "title": "AI PM (DB)",
        "description": "From DB", "status": "active", "version": "2.0", "metadata": {},
    },
    "error": None,
    "notes": [],
}

_FAKE_TOPIC_FALLBACK = {
    "source":          "fallback",
    "legacy_topic_id": "aipm-week-1-ai-vs-ml-vs-dl",
    "topic": {
        "legacy_topic_id": "aipm-week-1-ai-vs-ml-vs-dl",
        "title": "AI vs ML vs DL", "description": "...",
        "freshness_label": "", "estimated_minutes": None,
    },
    "error": None,
    "notes": [],
}

_FAKE_TOPICS_FALLBACK = {
    "source":    "fallback",
    "track_key": "aipm",
    "topics": [
        {
            "legacy_topic_id": "aipm-week-1-ai-vs-ml-vs-dl",
            "title": "AI vs ML vs DL", "description": "...",
            "freshness_label": "", "estimated_minutes": None,
        }
    ],
    "error": None,
    "notes": [],
}


# ── Existence and shape ───────────────────────────────────────────────────────

def test_endpoint_exists_returns_200():
    with _FLAG_OFF:
        resp = client.get("/debug/curriculum-fallback-check")
    assert resp.status_code == 200


def test_endpoint_returns_json():
    with _FLAG_OFF:
        resp = client.get("/debug/curriculum-fallback-check")
    assert resp.headers["content-type"].startswith("application/json")


def test_response_has_all_required_keys():
    with _FLAG_OFF:
        resp = client.get("/debug/curriculum-fallback-check")
    data = resp.json()
    for key in (
        "track_key", "legacy_topic_id", "include_topics",
        "curriculum_db_reads_enabled", "attempted_db_connection",
        "track_result", "topic_result", "topics_result",
        "source_summary", "error", "notes",
    ):
        assert key in data, f"Missing key: {key}"


def test_source_summary_has_required_keys():
    with _FLAG_OFF:
        resp = client.get("/debug/curriculum-fallback-check")
    summary = resp.json()["source_summary"]
    for key in ("track_source", "topic_source", "topics_source"):
        assert key in summary, f"Missing source_summary key: {key}"


def test_track_key_reflected_in_response():
    with _FLAG_OFF:
        resp = client.get("/debug/curriculum-fallback-check", params={"track_key": "evals"})
    assert resp.json()["track_key"] == "evals"


# ── Flag off: no DB connection ────────────────────────────────────────────────

def test_flag_off_attempted_db_connection_false():
    with _FLAG_OFF:
        resp = client.get("/debug/curriculum-fallback-check")
    assert resp.json()["attempted_db_connection"] is False


def test_flag_off_curriculum_db_reads_enabled_false():
    with _FLAG_OFF:
        resp = client.get("/debug/curriculum-fallback-check")
    assert resp.json()["curriculum_db_reads_enabled"] is False


def test_flag_off_get_conn_not_called():
    with _FLAG_OFF:
        with patch("routes.debug.get_conn") as mock_conn:
            client.get("/debug/curriculum-fallback-check")
    mock_conn.assert_not_called()


# ── Flag off: fallback sources ────────────────────────────────────────────────

def test_flag_off_track_result_source_is_fallback():
    with _FLAG_OFF:
        with patch(
            "services.curriculum_fallback_service.get_track_with_fallback",
            return_value=_FAKE_TRACK_FALLBACK,
        ):
            resp = client.get("/debug/curriculum-fallback-check")
    data = resp.json()
    assert data["track_result"]["source"] == "fallback"
    assert data["source_summary"]["track_source"] == "fallback"


def test_flag_off_topic_result_none_when_no_topic_id():
    with _FLAG_OFF:
        resp = client.get("/debug/curriculum-fallback-check")
    data = resp.json()
    assert data["topic_result"] is None
    assert data["source_summary"]["topic_source"] is None


def test_flag_off_with_legacy_topic_id_returns_topic_result():
    with _FLAG_OFF:
        with patch(
            "services.curriculum_fallback_service.get_track_with_fallback",
            return_value=_FAKE_TRACK_FALLBACK,
        ):
            with patch(
                "services.curriculum_fallback_service.get_topic_with_fallback",
                return_value=_FAKE_TOPIC_FALLBACK,
            ):
                resp = client.get(
                    "/debug/curriculum-fallback-check",
                    params={"legacy_topic_id": "aipm-week-1-ai-vs-ml-vs-dl"},
                )
    data = resp.json()
    assert data["topic_result"] is not None
    assert data["topic_result"]["source"] == "fallback"
    assert data["source_summary"]["topic_source"] == "fallback"


def test_flag_off_include_topics_false_returns_none():
    with _FLAG_OFF:
        resp = client.get("/debug/curriculum-fallback-check", params={"include_topics": "false"})
    data = resp.json()
    assert data["topics_result"] is None
    assert data["source_summary"]["topics_source"] is None


def test_flag_off_include_topics_true_returns_topics_result():
    with _FLAG_OFF:
        with patch(
            "services.curriculum_fallback_service.get_track_with_fallback",
            return_value=_FAKE_TRACK_FALLBACK,
        ):
            with patch(
                "services.curriculum_fallback_service.get_topics_for_track_with_fallback",
                return_value=_FAKE_TOPICS_FALLBACK,
            ):
                resp = client.get(
                    "/debug/curriculum-fallback-check",
                    params={"include_topics": "true"},
                )
    data = resp.json()
    assert data["topics_result"] is not None
    assert data["source_summary"]["topics_source"] == "fallback"


# ── Flag on: DB connection attempted ─────────────────────────────────────────

def test_flag_on_attempted_db_connection_true():
    conn = _make_conn()
    with _FLAG_ON:
        with patch("routes.debug.get_conn", _fake_get_conn(conn)):
            with patch(
                "services.curriculum_fallback_service.get_track_with_fallback",
                return_value=_FAKE_TRACK_FALLBACK,
            ):
                resp = client.get("/debug/curriculum-fallback-check")
    assert resp.json()["attempted_db_connection"] is True
    assert resp.json()["curriculum_db_reads_enabled"] is True


def test_flag_on_db_returns_row_track_source_db():
    conn = _make_conn()
    with _FLAG_ON:
        with patch("routes.debug.get_conn", _fake_get_conn(conn)):
            with patch(
                "services.curriculum_fallback_service.get_track_with_fallback",
                return_value=_FAKE_TRACK_DB,
            ):
                resp = client.get("/debug/curriculum-fallback-check")
    data = resp.json()
    assert data["track_result"]["source"] == "db"
    assert data["source_summary"]["track_source"] == "db"
    assert data["error"] is None


def test_flag_on_db_missing_row_track_source_fallback():
    conn = _make_conn()
    with _FLAG_ON:
        with patch("routes.debug.get_conn", _fake_get_conn(conn)):
            with patch(
                "services.curriculum_fallback_service.get_track_with_fallback",
                return_value=_FAKE_TRACK_FALLBACK,
            ):
                resp = client.get("/debug/curriculum-fallback-check")
    assert resp.json()["source_summary"]["track_source"] == "fallback"


# ── Error handling ────────────────────────────────────────────────────────────

def test_db_connection_error_returns_http_200():
    with _FLAG_ON:
        with patch("routes.debug.get_conn", _fake_get_conn_raises(RuntimeError("DB down"))):
            resp = client.get("/debug/curriculum-fallback-check")
    assert resp.status_code == 200


def test_db_connection_error_sets_error_field():
    with _FLAG_ON:
        with patch("routes.debug.get_conn", _fake_get_conn_raises(RuntimeError("connection refused"))):
            resp = client.get("/debug/curriculum-fallback-check")
    data = resp.json()
    assert data["error"] is not None
    assert "RuntimeError" in data["error"]


def test_db_connection_error_track_result_is_none():
    with _FLAG_ON:
        with patch("routes.debug.get_conn", _fake_get_conn_raises(RuntimeError("DB down"))):
            resp = client.get("/debug/curriculum-fallback-check")
    assert resp.json()["track_result"] is None


def test_service_error_inside_conn_returns_safe_response():
    conn = _make_conn()
    with _FLAG_ON:
        with patch("routes.debug.get_conn", _fake_get_conn(conn)):
            with patch(
                "services.curriculum_fallback_service.get_track_with_fallback",
                side_effect=RuntimeError("service explosion"),
            ):
                resp = client.get("/debug/curriculum-fallback-check")
    assert resp.status_code == 200
    assert resp.json()["error"] is not None


# ── Connection lifecycle ──────────────────────────────────────────────────────

def test_connection_closed_on_success():
    conn = _make_conn()
    with _FLAG_ON:
        with patch("routes.debug.get_conn", _fake_get_conn(conn)):
            with patch(
                "services.curriculum_fallback_service.get_track_with_fallback",
                return_value=_FAKE_TRACK_FALLBACK,
            ):
                client.get("/debug/curriculum-fallback-check")
    conn.close.assert_called_once()


def test_connection_closed_on_service_error():
    conn = _make_conn()
    with _FLAG_ON:
        with patch("routes.debug.get_conn", _fake_get_conn(conn)):
            with patch(
                "services.curriculum_fallback_service.get_track_with_fallback",
                side_effect=RuntimeError("boom"),
            ):
                client.get("/debug/curriculum-fallback-check")
    conn.close.assert_called_once()


# ── Security ──────────────────────────────────────────────────────────────────

def test_no_raw_env_var_names_in_flag_off_response():
    with _FLAG_OFF:
        resp = client.get("/debug/curriculum-fallback-check")
    body = resp.text
    for secret in ("SUPABASE_DATABASE_URL", "ANTHROPIC_API_KEY", "AI2_TEST_MODE"):
        assert secret not in body, f"Secret leaked: {secret}"


def test_no_database_url_in_error_response():
    exc = Exception("postgresql://user:secret@db.supabase.co/postgres")
    with _FLAG_ON:
        with patch("routes.debug.get_conn", _fake_get_conn_raises(exc)):
            resp = client.get("/debug/curriculum-fallback-check")
    assert "SUPABASE_DATABASE_URL" not in resp.text
    assert resp.json()["error"] is not None
    assert len(resp.json()["error"]) <= 400


def test_db_error_message_is_truncated():
    exc = RuntimeError("X" * 400)
    with _FLAG_ON:
        with patch("routes.debug.get_conn", _fake_get_conn_raises(exc)):
            resp = client.get("/debug/curriculum-fallback-check")
    assert len(resp.json()["error"]) <= 350


def test_learner_session_not_loaded():
    with _FLAG_OFF:
        with patch("app._get_session_data") as mock_session:
            client.get("/debug/curriculum-fallback-check")
    mock_session.assert_not_called()
