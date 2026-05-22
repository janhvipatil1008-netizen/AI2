"""Tests for the opt-in curriculum DB read service.

The service is intentionally not wired into learner-facing routes. These tests
verify normalization, repository delegation, and that no DB connection is
opened unless a caller explicitly provides one and enables the read flag.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from unittest.mock import patch

import services.curriculum_read_service as service


def test_module_imports_without_db_connection():
    with patch("database.pool._connect", side_effect=AssertionError("_connect must not be called")) as mock_connect:
        importlib.reload(service)

    mock_connect.assert_not_called()


def test_normalize_track_row_handles_full_row():
    row = {
        "id": 123,
        "track_key": "ai-product",
        "title": "AI Product",
        "description": "Build AI products.",
        "status": "active",
        "version": "v1",
        "metadata": {"source": "seed"},
    }

    result = service.normalize_track_row(row)

    assert result == {
        "id": "123",
        "track_key": "ai-product",
        "title": "AI Product",
        "description": "Build AI products.",
        "status": "active",
        "version": "v1",
        "metadata": {"source": "seed"},
    }


def test_normalize_track_row_handles_missing_optional_fields():
    result = service.normalize_track_row({"track_key": "ai-product", "metadata": None})

    assert result == {
        "id": "",
        "track_key": "ai-product",
        "title": "",
        "description": "",
        "status": "",
        "version": "",
        "metadata": {},
    }


def test_normalize_topic_row_extracts_legacy_topic_id_from_metadata():
    row = {
        "id": "topic-row-1",
        "topic_key": "rag-basics",
        "title": "RAG Basics",
        "description": "Retrieval augmented generation.",
        "freshness_label": "stable",
        "estimated_minutes": 45,
        "metadata": {"legacy_topic_id": "rag_basics"},
    }

    result = service.normalize_topic_row(row)

    assert result == {
        "id": "topic-row-1",
        "topic_key": "rag-basics",
        "title": "RAG Basics",
        "description": "Retrieval augmented generation.",
        "freshness_label": "stable",
        "estimated_minutes": 45,
        "legacy_topic_id": "rag_basics",
    }


def test_normalize_topic_row_handles_missing_metadata():
    result = service.normalize_topic_row({"topic_key": "rag-basics"})

    assert result == {
        "id": "",
        "topic_key": "rag-basics",
        "title": "",
        "description": "",
        "freshness_label": "",
        "estimated_minutes": None,
        "legacy_topic_id": "",
    }


def test_normalize_topic_row_handles_json_metadata_string():
    result = service.normalize_topic_row({
        "topic_key": "rag-basics",
        "metadata": '{"legacy_topic_id": "legacy-rag"}',
    })

    assert result["legacy_topic_id"] == "legacy-rag"


def test_get_track_by_key_from_db_calls_repository_and_normalizes_row():
    conn = object()
    row = {"id": "track-1", "track_key": "ai-product", "title": "AI Product"}

    with patch(
        "services.curriculum_read_service.curriculum_repository.get_learning_track_by_key",
        return_value=row,
    ) as mock_get:
        result = service.get_track_by_key_from_db(conn, "ai-product")

    mock_get.assert_called_once_with(conn, "ai-product")
    assert result["id"] == "track-1"
    assert result["track_key"] == "ai-product"
    assert result["title"] == "AI Product"


def test_get_track_by_key_from_db_returns_none_when_repository_returns_none():
    with patch(
        "services.curriculum_read_service.curriculum_repository.get_learning_track_by_key",
        return_value=None,
    ):
        assert service.get_track_by_key_from_db(object(), "missing") is None


def test_get_topic_by_legacy_id_from_db_calls_repository_and_normalizes_row():
    conn = object()
    row = {
        "id": "topic-1",
        "topic_key": "rag-basics",
        "title": "RAG Basics",
        "metadata": {"legacy_topic_id": "legacy-rag"},
    }

    with patch(
        "services.curriculum_read_service.curriculum_repository.get_learning_topic_by_legacy_id",
        return_value=row,
    ) as mock_get:
        result = service.get_topic_by_legacy_id_from_db(conn, "legacy-rag")

    mock_get.assert_called_once_with(conn, "legacy-rag")
    assert result["id"] == "topic-1"
    assert result["topic_key"] == "rag-basics"
    assert result["legacy_topic_id"] == "legacy-rag"


def test_get_topic_by_legacy_id_from_db_returns_none_when_repository_returns_none():
    with patch(
        "services.curriculum_read_service.curriculum_repository.get_learning_topic_by_legacy_id",
        return_value=None,
    ):
        assert service.get_topic_by_legacy_id_from_db(object(), "missing") is None


def test_maybe_get_track_by_key_returns_none_when_flag_disabled():
    with patch(
        "services.curriculum_read_service.storage_flags.is_curriculum_db_reads_enabled",
        return_value=False,
    ), patch("services.curriculum_read_service.get_track_by_key_from_db") as mock_get:
        result = service.maybe_get_track_by_key(object(), "ai-product")

    assert result is None
    mock_get.assert_not_called()


def test_maybe_get_track_by_key_returns_none_when_conn_is_none():
    with patch(
        "services.curriculum_read_service.storage_flags.is_curriculum_db_reads_enabled",
        return_value=True,
    ), patch("services.curriculum_read_service.get_track_by_key_from_db") as mock_get:
        result = service.maybe_get_track_by_key(None, "ai-product")

    assert result is None
    mock_get.assert_not_called()


def test_maybe_get_track_by_key_returns_none_when_track_key_empty():
    with patch(
        "services.curriculum_read_service.storage_flags.is_curriculum_db_reads_enabled",
        return_value=True,
    ), patch("services.curriculum_read_service.get_track_by_key_from_db") as mock_get:
        result = service.maybe_get_track_by_key(object(), "")

    assert result is None
    mock_get.assert_not_called()


def test_maybe_get_track_by_key_calls_db_when_flag_enabled():
    conn = object()
    expected = {"track_key": "ai-product"}

    with patch(
        "services.curriculum_read_service.storage_flags.is_curriculum_db_reads_enabled",
        return_value=True,
    ), patch(
        "services.curriculum_read_service.get_track_by_key_from_db",
        return_value=expected,
    ) as mock_get:
        result = service.maybe_get_track_by_key(conn, "ai-product")

    assert result == expected
    mock_get.assert_called_once_with(conn, "ai-product")


def test_maybe_get_topic_by_legacy_id_returns_none_when_flag_disabled():
    with patch(
        "services.curriculum_read_service.storage_flags.is_curriculum_db_reads_enabled",
        return_value=False,
    ), patch("services.curriculum_read_service.get_topic_by_legacy_id_from_db") as mock_get:
        result = service.maybe_get_topic_by_legacy_id(object(), "legacy-rag")

    assert result is None
    mock_get.assert_not_called()


def test_maybe_get_topic_by_legacy_id_returns_none_when_conn_is_none():
    with patch(
        "services.curriculum_read_service.storage_flags.is_curriculum_db_reads_enabled",
        return_value=True,
    ), patch("services.curriculum_read_service.get_topic_by_legacy_id_from_db") as mock_get:
        result = service.maybe_get_topic_by_legacy_id(None, "legacy-rag")

    assert result is None
    mock_get.assert_not_called()


def test_maybe_get_topic_by_legacy_id_returns_none_when_legacy_topic_id_empty():
    with patch(
        "services.curriculum_read_service.storage_flags.is_curriculum_db_reads_enabled",
        return_value=True,
    ), patch("services.curriculum_read_service.get_topic_by_legacy_id_from_db") as mock_get:
        result = service.maybe_get_topic_by_legacy_id(object(), "")

    assert result is None
    mock_get.assert_not_called()


def test_maybe_get_topic_by_legacy_id_calls_db_when_flag_enabled():
    conn = object()
    expected = {"legacy_topic_id": "legacy-rag"}

    with patch(
        "services.curriculum_read_service.storage_flags.is_curriculum_db_reads_enabled",
        return_value=True,
    ), patch(
        "services.curriculum_read_service.get_topic_by_legacy_id_from_db",
        return_value=expected,
    ) as mock_get:
        result = service.maybe_get_topic_by_legacy_id(conn, "legacy-rag")

    assert result == expected
    mock_get.assert_called_once_with(conn, "legacy-rag")


def test_service_does_not_call_database_pool_connect():
    with patch("database.pool._connect", side_effect=AssertionError("_connect must not be called")) as mock_connect:
        with patch(
            "services.curriculum_read_service.storage_flags.is_curriculum_db_reads_enabled",
            return_value=False,
        ):
            assert service.maybe_get_track_by_key(object(), "ai-product") is None
            assert service.maybe_get_topic_by_legacy_id(object(), "legacy-rag") is None

    mock_connect.assert_not_called()


def test_service_does_not_read_os_environ_directly():
    source = Path("services/curriculum_read_service.py").read_text(encoding="utf-8")

    assert "import os" not in source
    assert "os.environ" not in source
    assert "os.getenv" not in source
