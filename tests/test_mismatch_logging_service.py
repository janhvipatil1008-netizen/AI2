"""Tests for safe mismatch logging helpers."""

from __future__ import annotations

import inspect
from unittest.mock import MagicMock

from services import mismatch_logging_service as service
from services.mismatch_logging_service import (
    log_mismatch_summary,
    summarize_mismatch_result,
)


PRIVATE_CONTENT = "full generated content should never appear"
PRIVATE_SUBMISSION = "full learner submission should never appear"
PRIVATE_NOTE = "full private topic note should never appear"
PRIVATE_METADATA = "full usage metadata should never appear"


def _matching_comparison():
    return {
        "matches": True,
        "comparisons": [
            {
                "type": "topic_progress",
                "matches": True,
                "mismatches": [],
            }
        ],
    }


def _mismatch_comparison():
    return {
        "matches": False,
        "legacy_topic_id": "topic-1",
        "comparisons": [
            {
                "type": "generated_topic_content",
                "matches": False,
                "mismatches": [
                    {
                        "field": "content_length",
                        "session_value": PRIVATE_CONTENT,
                        "db_value": "short",
                    },
                    {
                        "field": "model",
                        "session_value": "claude",
                        "db_value": "cache",
                    },
                ],
                "session_snapshot": {"content": PRIVATE_CONTENT},
            },
            {
                "type": "quiz_submission",
                "matches": False,
                "mismatches": [
                    {
                        "field": "answers_length",
                        "session_value": PRIVATE_SUBMISSION,
                        "db_value": "",
                    },
                ],
                "session_snapshot": {"answers": PRIVATE_SUBMISSION},
            },
            {
                "type": "topic_notes",
                "matches": True,
                "mismatches": [
                    {
                        "field": "reflection",
                        "session_value": PRIVATE_NOTE,
                        "db_value": "",
                    },
                ],
            },
        ],
    }


def _usage_event_id_mismatch_comparison():
    return {
        "matches": False,
        "comparisons": [
            {
                "type": "usage_events_summary",
                "matches": False,
                "mismatches": [
                    {
                        "field": "by_event_type",
                        "session_value": {"topic_learning_content": 2},
                        "db_value": {"topic_learning_content": 1},
                        "metadata": PRIVATE_METADATA,
                    },
                ],
            },
            {
                "type": "usage_events_event_ids",
                "matches": False,
                "missing_in_db": ["evt-session-only"],
                "extra_in_db": ["evt-db-only-1", "evt-db-only-2"],
            },
            {
                "type": "todos",
                "matches": False,
                "mismatches": [],
                "db_missing": True,
            },
        ],
    }


def test_summarize_handles_none_comparison():
    assert summarize_mismatch_result(domain="learner_state", comparison=None) == {
        "domain": "learner_state",
        "matches": None,
        "comparison_count": 0,
        "mismatch_count": 0,
        "mismatch_types": [],
    }


def test_summarize_handles_matches_true():
    summary = summarize_mismatch_result(
        domain="learner_state",
        comparison=_matching_comparison(),
    )

    assert summary["matches"] is True
    assert summary["comparison_count"] == 1
    assert summary["mismatch_count"] == 0
    assert summary["mismatch_types"] == []


def test_summarize_handles_matches_false():
    summary = summarize_mismatch_result(
        domain="generated_learning",
        comparison=_mismatch_comparison(),
    )

    assert summary["matches"] is False
    assert summary["comparison_count"] == 3
    assert summary["mismatch_count"] == 3
    assert summary["mismatch_types"] == ["generated_topic_content", "quiz_submission"]


def test_mismatch_count_is_counted_correctly():
    summary = summarize_mismatch_result(
        domain="usage_events",
        comparison=_usage_event_id_mismatch_comparison(),
    )

    assert summary["mismatch_count"] == 5


def test_mismatch_types_are_extracted_safely():
    summary = summarize_mismatch_result(
        domain="usage_events",
        comparison=_usage_event_id_mismatch_comparison(),
    )

    assert summary["mismatch_types"] == [
        "usage_events_summary",
        "usage_events_event_ids",
        "todos",
    ]


def test_raw_mismatch_values_are_not_included():
    summary = summarize_mismatch_result(
        domain="generated_learning",
        comparison=_mismatch_comparison(),
    )

    body = str(summary)
    assert PRIVATE_CONTENT not in body
    assert PRIVATE_SUBMISSION not in body
    assert "session_value" not in body
    assert "db_value" not in body
    assert "session_snapshot" not in body


def test_log_mismatch_summary_logs_info_for_match():
    logger = MagicMock()
    summary = log_mismatch_summary(
        logger=logger,
        domain="learner_state",
        comparison=_matching_comparison(),
    )

    assert summary["matches"] is True
    logger.info.assert_called_once()
    logger.warning.assert_not_called()


def test_log_mismatch_summary_logs_warning_for_mismatch():
    logger = MagicMock()
    summary = log_mismatch_summary(
        logger=logger,
        domain="generated_learning",
        comparison=_mismatch_comparison(),
    )

    assert summary["matches"] is False
    logger.warning.assert_called_once()
    logger.info.assert_not_called()


def test_logger_none_does_not_raise():
    summary = log_mismatch_summary(
        logger=None,
        domain="usage_events",
        comparison=None,
    )

    assert summary["matches"] is None


def test_unsafe_context_keys_are_ignored():
    logger = MagicMock()
    summary = log_mismatch_summary(
        logger=logger,
        domain="usage_events",
        comparison=_usage_event_id_mismatch_comparison(),
        context={
            "session_id": "sess-1",
            "legacy_topic_id": "topic-1",
            "user_id": "user-1",
            "source": "db_compare",
            "session_data": {"private": PRIVATE_CONTENT},
            "metadata": {"private": PRIVATE_METADATA},
            "api_key": "sk-secret",
            "database_url": "postgresql://user:secret@host/db",
        },
    )

    assert summary["context"] == {
        "session_id": "sess-1",
        "legacy_topic_id": "topic-1",
        "user_id": "user-1",
        "source": "db_compare",
    }
    body = str(summary)
    assert "session_data" not in body
    assert "metadata" not in body
    assert "api_key" not in body
    assert "postgresql://" not in body
    assert "sk-secret" not in body


def test_output_does_not_include_generated_content_text():
    summary = log_mismatch_summary(
        logger=MagicMock(),
        domain="generated_learning",
        comparison=_mismatch_comparison(),
    )

    assert PRIVATE_CONTENT not in str(summary)


def test_output_does_not_include_submission_text():
    summary = log_mismatch_summary(
        logger=MagicMock(),
        domain="generated_learning",
        comparison=_mismatch_comparison(),
    )

    assert PRIVATE_SUBMISSION not in str(summary)


def test_output_does_not_include_notes_text():
    summary = log_mismatch_summary(
        logger=MagicMock(),
        domain="generated_learning",
        comparison=_mismatch_comparison(),
    )

    assert PRIVATE_NOTE not in str(summary)


def test_output_does_not_include_usage_metadata():
    summary = log_mismatch_summary(
        logger=MagicMock(),
        domain="usage_events",
        comparison=_usage_event_id_mismatch_comparison(),
    )

    assert PRIVATE_METADATA not in str(summary)
    assert "metadata" not in str(summary)


def test_service_does_not_import_database_pool():
    src = inspect.getsource(service)

    assert "database.pool" not in src
    assert "get_conn" not in src
    assert "psycopg" not in src


def test_service_does_not_read_os_environ_or_getenv():
    src = inspect.getsource(service)

    assert "os.environ" not in src
    assert "os.getenv" not in src
    assert "getenv(" not in src
