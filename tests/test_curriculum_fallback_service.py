"""Tests for services/curriculum_fallback_service.py.

No DB connection is required — real syllabus data is used for fallback
paths; DB calls are always mocked.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from services.curriculum_fallback_service import (
    get_topic_with_fallback,
    get_topics_for_track_with_fallback,
    get_track_with_fallback,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _conn() -> MagicMock:
    return MagicMock()


_FAKE_TRACK_ROW = {
    "id":          "track-uuid-1",
    "track_key":   "aipm",
    "title":       "AI Product Manager (DB)",
    "description": "From DB",
    "status":      "active",
    "version":     "2.0",
    "metadata":    {},
}

_FAKE_TOPIC_ROW = {
    "id":               "topic-uuid-1",
    "topic_key":        "aipm-week-1-ai-vs-ml-vs-dl",
    "title":            "AI vs ML vs DL (DB)",
    "description":      "From DB description",
    "freshness_label":  "Stable concept",
    "estimated_minutes": 45,
    "legacy_topic_id":  "aipm-week-1-ai-vs-ml-vs-dl",
}

_KNOWN_TOPIC_ID = "aipm-week-1-ai-vs-ml-vs-dl"


# ── Module import ─────────────────────────────────────────────────────────────

def test_module_imports_without_db_connection():
    import services.curriculum_fallback_service  # noqa: F401 — import is the test


# ── get_track_with_fallback: flag off ─────────────────────────────────────────

def test_get_track_flag_off_source_is_fallback():
    with patch(
        "services.curriculum_fallback_service.is_curriculum_db_reads_enabled",
        return_value=False,
    ):
        result = get_track_with_fallback(conn=_conn(), track_key="aipm")
    assert result["source"] == "fallback"


def test_get_track_flag_off_does_not_call_db_reader():
    with patch(
        "services.curriculum_fallback_service.is_curriculum_db_reads_enabled",
        return_value=False,
    ):
        with patch(
            "services.curriculum_read_service.get_track_by_key_from_db"
        ) as mock_db:
            get_track_with_fallback(conn=_conn(), track_key="aipm")
    mock_db.assert_not_called()


def test_get_track_flag_off_track_from_syllabus():
    with patch(
        "services.curriculum_fallback_service.is_curriculum_db_reads_enabled",
        return_value=False,
    ):
        result = get_track_with_fallback(conn=_conn(), track_key="aipm")
    assert result["track"] is not None
    assert result["track"]["track_key"] == "aipm"
    assert result["track"]["title"] == "AI Product Manager"
    assert result["error"] is None


def test_get_track_conn_none_source_is_fallback_even_when_flag_on():
    with patch(
        "services.curriculum_fallback_service.is_curriculum_db_reads_enabled",
        return_value=True,
    ):
        with patch(
            "services.curriculum_read_service.get_track_by_key_from_db"
        ) as mock_db:
            result = get_track_with_fallback(conn=None, track_key="aipm")
    assert result["source"] == "fallback"
    mock_db.assert_not_called()


def test_get_track_unknown_track_key_returns_none_track():
    with patch(
        "services.curriculum_fallback_service.is_curriculum_db_reads_enabled",
        return_value=False,
    ):
        result = get_track_with_fallback(conn=_conn(), track_key="unknown-track")
    assert result["track"] is None
    assert result["source"] == "fallback"


# ── get_track_with_fallback: flag on ──────────────────────────────────────────

def test_get_track_flag_on_db_returns_row_source_db():
    with patch(
        "services.curriculum_fallback_service.is_curriculum_db_reads_enabled",
        return_value=True,
    ):
        with patch(
            "services.curriculum_read_service.get_track_by_key_from_db",
            return_value=_FAKE_TRACK_ROW,
        ):
            result = get_track_with_fallback(conn=_conn(), track_key="aipm")
    assert result["source"] == "db"
    assert result["track"] == _FAKE_TRACK_ROW
    assert result["error"] is None


def test_get_track_flag_on_db_missing_uses_fallback():
    with patch(
        "services.curriculum_fallback_service.is_curriculum_db_reads_enabled",
        return_value=True,
    ):
        with patch(
            "services.curriculum_read_service.get_track_by_key_from_db",
            return_value=None,
        ):
            result = get_track_with_fallback(conn=_conn(), track_key="aipm")
    assert result["source"] == "fallback"
    assert result["track"] is not None
    assert result["error"] is None


def test_get_track_flag_on_db_missing_adds_note():
    with patch(
        "services.curriculum_fallback_service.is_curriculum_db_reads_enabled",
        return_value=True,
    ):
        with patch(
            "services.curriculum_read_service.get_track_by_key_from_db",
            return_value=None,
        ):
            result = get_track_with_fallback(conn=_conn(), track_key="aipm")
    assert any("fallback" in n for n in result["notes"])


def test_get_track_db_raises_source_error_fallback():
    with patch(
        "services.curriculum_fallback_service.is_curriculum_db_reads_enabled",
        return_value=True,
    ):
        with patch(
            "services.curriculum_read_service.get_track_by_key_from_db",
            side_effect=RuntimeError("connection refused"),
        ):
            result = get_track_with_fallback(conn=_conn(), track_key="aipm")
    assert result["source"] == "error_fallback"
    assert result["track"] is not None
    assert result["error"] is not None
    assert "RuntimeError" in result["error"]


def test_get_track_db_error_message_is_truncated():
    long_msg = "X" * 400
    with patch(
        "services.curriculum_fallback_service.is_curriculum_db_reads_enabled",
        return_value=True,
    ):
        with patch(
            "services.curriculum_read_service.get_track_by_key_from_db",
            side_effect=RuntimeError(long_msg),
        ):
            result = get_track_with_fallback(conn=_conn(), track_key="aipm")
    # safe_error_metadata truncates to 300; combined string is type + ": " + 300 chars
    assert len(result["error"]) <= 350


# ── get_topic_with_fallback: flag off ─────────────────────────────────────────

def test_get_topic_flag_off_source_is_fallback():
    with patch(
        "services.curriculum_fallback_service.is_curriculum_db_reads_enabled",
        return_value=False,
    ):
        result = get_topic_with_fallback(conn=_conn(), legacy_topic_id=_KNOWN_TOPIC_ID)
    assert result["source"] == "fallback"


def test_get_topic_flag_off_does_not_call_db_reader():
    with patch(
        "services.curriculum_fallback_service.is_curriculum_db_reads_enabled",
        return_value=False,
    ):
        with patch(
            "services.curriculum_read_service.get_topic_by_legacy_id_from_db"
        ) as mock_db:
            get_topic_with_fallback(conn=_conn(), legacy_topic_id=_KNOWN_TOPIC_ID)
    mock_db.assert_not_called()


def test_get_topic_flag_off_topic_from_syllabus():
    with patch(
        "services.curriculum_fallback_service.is_curriculum_db_reads_enabled",
        return_value=False,
    ):
        result = get_topic_with_fallback(conn=_conn(), legacy_topic_id=_KNOWN_TOPIC_ID)
    assert result["topic"] is not None
    assert result["topic"]["legacy_topic_id"] == _KNOWN_TOPIC_ID
    assert result["topic"]["title"] == "AI vs ML vs DL"
    assert result["error"] is None


def test_get_topic_unknown_id_returns_none_topic():
    with patch(
        "services.curriculum_fallback_service.is_curriculum_db_reads_enabled",
        return_value=False,
    ):
        result = get_topic_with_fallback(conn=_conn(), legacy_topic_id="no-such-topic")
    assert result["topic"] is None
    assert result["source"] == "fallback"


# ── get_topic_with_fallback: flag on ─────────────────────────────────────────

def test_get_topic_flag_on_db_returns_row_source_db():
    with patch(
        "services.curriculum_fallback_service.is_curriculum_db_reads_enabled",
        return_value=True,
    ):
        with patch(
            "services.curriculum_read_service.get_topic_by_legacy_id_from_db",
            return_value=_FAKE_TOPIC_ROW,
        ):
            result = get_topic_with_fallback(conn=_conn(), legacy_topic_id=_KNOWN_TOPIC_ID)
    assert result["source"] == "db"
    assert result["topic"] == _FAKE_TOPIC_ROW
    assert result["error"] is None


def test_get_topic_flag_on_db_missing_uses_fallback():
    with patch(
        "services.curriculum_fallback_service.is_curriculum_db_reads_enabled",
        return_value=True,
    ):
        with patch(
            "services.curriculum_read_service.get_topic_by_legacy_id_from_db",
            return_value=None,
        ):
            result = get_topic_with_fallback(conn=_conn(), legacy_topic_id=_KNOWN_TOPIC_ID)
    assert result["source"] == "fallback"
    assert result["topic"] is not None
    assert result["error"] is None


def test_get_topic_db_raises_source_error_fallback():
    with patch(
        "services.curriculum_fallback_service.is_curriculum_db_reads_enabled",
        return_value=True,
    ):
        with patch(
            "services.curriculum_read_service.get_topic_by_legacy_id_from_db",
            side_effect=RuntimeError("DB down"),
        ):
            result = get_topic_with_fallback(conn=_conn(), legacy_topic_id=_KNOWN_TOPIC_ID)
    assert result["source"] == "error_fallback"
    assert result["error"] is not None
    assert result["topic"] is not None


def test_get_topic_conn_none_source_fallback_even_when_flag_on():
    with patch(
        "services.curriculum_fallback_service.is_curriculum_db_reads_enabled",
        return_value=True,
    ):
        with patch(
            "services.curriculum_read_service.get_topic_by_legacy_id_from_db"
        ) as mock_db:
            result = get_topic_with_fallback(conn=None, legacy_topic_id=_KNOWN_TOPIC_ID)
    assert result["source"] == "fallback"
    mock_db.assert_not_called()


# ── get_topics_for_track_with_fallback ────────────────────────────────────────

def test_get_topics_for_track_source_is_fallback():
    result = get_topics_for_track_with_fallback(conn=None, track_key="aipm")
    assert result["source"] == "fallback"


def test_get_topics_for_track_returns_non_empty_list():
    result = get_topics_for_track_with_fallback(conn=None, track_key="aipm")
    assert isinstance(result["topics"], list)
    assert len(result["topics"]) > 0


def test_get_topics_for_track_topics_have_required_fields():
    result = get_topics_for_track_with_fallback(conn=None, track_key="aipm")
    first = result["topics"][0]
    for field in ("legacy_topic_id", "topic_key", "title", "description"):
        assert field in first, f"Missing field: {field}"


def test_get_topics_for_track_error_is_none():
    result = get_topics_for_track_with_fallback(conn=None, track_key="aipm")
    assert result["error"] is None


def test_get_topics_for_track_flag_on_adds_not_implemented_note():
    with patch(
        "services.curriculum_fallback_service.is_curriculum_db_reads_enabled",
        return_value=True,
    ):
        result = get_topics_for_track_with_fallback(conn=None, track_key="aipm")
    assert result["source"] == "fallback"
    assert any("not implemented" in n for n in result["notes"])


def test_get_topics_for_unknown_track_returns_empty_list():
    result = get_topics_for_track_with_fallback(conn=None, track_key="no-such-track")
    assert result["topics"] == []
    assert result["source"] == "fallback"


# ── Source constraints ────────────────────────────────────────────────────────

def test_service_does_not_import_database_pool():
    source = Path("services/curriculum_fallback_service.py").read_text(encoding="utf-8")
    assert "database.pool" not in source
    assert "from database" not in source
    assert "import database" not in source


def test_service_does_not_read_os_environ():
    source = Path("services/curriculum_fallback_service.py").read_text(encoding="utf-8")
    assert "import os" not in source
    assert "os.environ" not in source
    assert "os.getenv" not in source


def test_no_raw_secrets_in_error_output():
    secret_exc = Exception(
        "postgresql://postgres:SuperSecretPassword@db.supabase.co:5432/postgres"
    )
    with patch(
        "services.curriculum_fallback_service.is_curriculum_db_reads_enabled",
        return_value=True,
    ):
        with patch(
            "services.curriculum_read_service.get_track_by_key_from_db",
            side_effect=secret_exc,
        ):
            result = get_track_with_fallback(conn=_conn(), track_key="aipm")
    assert result["error"] is not None
    assert isinstance(result["error"], str)
    assert len(result["error"]) <= 400
