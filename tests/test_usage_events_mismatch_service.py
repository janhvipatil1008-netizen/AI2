"""Tests for services/usage_events_mismatch_service.py."""

from __future__ import annotations

import json
from pathlib import Path

from services.usage_events_mismatch_service import (
    compare_usage_events_state,
    compare_usage_summaries,
    normalize_usage_summary,
)

SERVICE_PATH = Path(__file__).parent.parent / "services" / "usage_events_mismatch_service.py"


class FakeSession:
    def __init__(self, events):
        self.usage_events = events

    def usage_summary(self):
        by_event_type: dict[str, int] = {}
        for event in self.usage_events:
            event_type = event.get("event_type", "")
            by_event_type[event_type] = by_event_type.get(event_type, 0) + 1
        return {
            "total_events": len(self.usage_events),
            "claude_events": sum(1 for e in self.usage_events if e.get("source") == "claude"),
            "cache_events": sum(1 for e in self.usage_events if e.get("source") == "cache"),
            "test_mode_events": sum(1 for e in self.usage_events if e.get("source") == "test_mode"),
            "error_events": sum(1 for e in self.usage_events if e.get("status") == "error"),
            "by_event_type": by_event_type,
        }


def _event(event_id: str, *, event_type="quiz_evaluation", source="claude", status="success"):
    return {
        "event_id": event_id,
        "event_type": event_type,
        "topic_id": "topic-1",
        "source": source,
        "status": status,
        "metadata": {
            "prompt": "private prompt text",
            "answers": "private learner answer",
            "generated_content": "private generated content",
        },
    }


def _summary(**overrides):
    summary = {
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
    summary.update(overrides)
    return summary


def test_normalize_usage_summary_defaults_missing_values():
    assert normalize_usage_summary(None) == {
        "total_events": 0,
        "claude_events": 0,
        "cache_events": 0,
        "test_mode_events": 0,
        "error_events": 0,
        "by_event_type": {},
    }


def test_normalize_usage_summary_normalizes_counts():
    result = normalize_usage_summary({
        "total_events": "3",
        "claude_events": "2.0",
        "cache_events": None,
        "by_event_type": {"quiz": "2"},
    })

    assert result["total_events"] == 3
    assert result["claude_events"] == 2
    assert result["cache_events"] == 0
    assert result["by_event_type"] == {"quiz": 2}


def test_compare_usage_summaries_matches_when_values_equal():
    result = compare_usage_summaries(
        session_summary=_summary(),
        db_summary=_summary(),
    )

    assert result["matches"] is True
    assert result["db_missing"] is False
    assert result["mismatches"] == []


def test_compare_usage_summaries_mismatch_on_total_events():
    result = compare_usage_summaries(
        session_summary=_summary(total_events=2),
        db_summary=_summary(total_events=1),
    )

    mismatch = result["mismatches"][0]
    assert result["matches"] is False
    assert mismatch["field"] == "total_events"
    assert mismatch["session_value"] == 2
    assert mismatch["db_value"] == 1


def test_compare_usage_summaries_mismatch_on_claude_events():
    result = compare_usage_summaries(
        session_summary=_summary(claude_events=2),
        db_summary=_summary(claude_events=1),
    )

    assert any(m["field"] == "claude_events" for m in result["mismatches"])


def test_compare_usage_summaries_mismatch_on_error_events():
    result = compare_usage_summaries(
        session_summary=_summary(error_events=1),
        db_summary=_summary(error_events=0),
    )

    assert any(m["field"] == "error_events" for m in result["mismatches"])


def test_compare_usage_summaries_mismatch_on_by_event_type():
    result = compare_usage_summaries(
        session_summary=_summary(by_event_type={"quiz_evaluation": 2}),
        db_summary=_summary(by_event_type={"quiz_evaluation": 1}),
    )

    mismatch = next(m for m in result["mismatches"] if m["field"] == "by_event_type")
    assert mismatch["session_value"] == {"quiz_evaluation": 2}
    assert mismatch["db_value"] == {"quiz_evaluation": 1}


def test_compare_usage_summaries_db_missing_true_when_db_summary_none():
    result = compare_usage_summaries(
        session_summary=_summary(),
        db_summary=None,
    )

    assert result["matches"] is False
    assert result["db_missing"] is True
    assert result["db_summary"] is None
    assert result["session_summary"]["total_events"] == 2


def test_compare_usage_events_state_matches_when_summaries_match():
    session = FakeSession([
        _event("evt-1", event_type="quiz_evaluation", source="claude"),
        _event("evt-2", event_type="topic_learning_content", source="cache"),
    ])

    result = compare_usage_events_state(
        session=session,
        db_summary=session.usage_summary(),
    )

    assert result["matches"] is True
    assert len(result["comparisons"]) == 1
    assert result["comparisons"][0]["type"] == "usage_events_summary"


def test_compare_usage_events_state_detects_missing_event_ids_in_db():
    session = FakeSession([
        _event("evt-1"),
        _event("evt-2", source="cache"),
    ])

    result = compare_usage_events_state(
        session=session,
        db_summary=session.usage_summary(),
        db_events=[{"event_id": "evt-1"}],
    )

    coverage = result["comparisons"][1]
    assert result["matches"] is False
    assert coverage["type"] == "usage_events_event_ids"
    assert coverage["missing_in_db"] == ["evt-2"]
    assert coverage["extra_in_db"] == []


def test_compare_usage_events_state_detects_extra_event_ids_in_db():
    session = FakeSession([_event("evt-1")])

    result = compare_usage_events_state(
        session=session,
        db_summary=session.usage_summary(),
        db_events=[{"event_id": "evt-1"}, {"event_id": "evt-extra"}],
    )

    coverage = result["comparisons"][1]
    assert result["matches"] is False
    assert coverage["missing_in_db"] == []
    assert coverage["extra_in_db"] == ["evt-extra"]


def test_event_id_comparison_skipped_when_db_events_none():
    session = FakeSession([_event("evt-1")])

    result = compare_usage_events_state(
        session=session,
        db_summary=session.usage_summary(),
        db_events=None,
    )

    assert [c["type"] for c in result["comparisons"]] == ["usage_events_summary"]


def test_output_does_not_include_full_metadata():
    session = FakeSession([_event("evt-1")])

    result = compare_usage_events_state(
        session=session,
        db_summary=session.usage_summary(),
        db_events=[{"event_id": "evt-1", "metadata": {"prompt": "db private prompt"}}],
    )
    encoded = json.dumps(result)

    assert "metadata" not in encoded
    assert "private prompt text" not in encoded
    assert "private learner answer" not in encoded
    assert "private generated content" not in encoded
    assert "db private prompt" not in encoded


def test_service_does_not_import_database_pool():
    source = SERVICE_PATH.read_text(encoding="utf-8")

    assert "database.pool" not in source
    assert "from database" not in source
    assert "import database" not in source


def test_service_does_not_read_os_environ():
    source = SERVICE_PATH.read_text(encoding="utf-8")

    assert "import os" not in source
    assert "os.environ" not in source
    assert "os.getenv" not in source
