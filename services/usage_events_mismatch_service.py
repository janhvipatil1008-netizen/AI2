"""Pure mismatch comparison for SessionContext usage_events vs DB mirrors.

Accepts already-read DB usage summaries/events and a SessionContext-like object.
Never opens DB connections, reads env vars, imports routes, logs, or mutates
session state. Output intentionally excludes usage event metadata payloads.
"""

from __future__ import annotations

_SUMMARY_FIELDS = (
    "total_events",
    "claude_events",
    "cache_events",
    "test_mode_events",
    "error_events",
)


def normalize_usage_summary(summary: dict | None) -> dict:
    summary = summary or {}
    by_event_type = summary.get("by_event_type") or {}
    if not isinstance(by_event_type, dict):
        by_event_type = {}

    normalized = {
        field: _safe_int(summary.get(field))
        for field in _SUMMARY_FIELDS
    }
    normalized["by_event_type"] = {
        str(event_type): _safe_int(count)
        for event_type, count in by_event_type.items()
    }
    return normalized


def compare_usage_summaries(
    *,
    session_summary: dict,
    db_summary: dict | None,
) -> dict:
    session_normalized = normalize_usage_summary(session_summary)

    if db_summary is None:
        return {
            "type": "usage_events_summary",
            "matches": False,
            "db_missing": True,
            "mismatches": [],
            "session_summary": session_normalized,
            "db_summary": None,
        }

    db_normalized = normalize_usage_summary(db_summary)
    mismatches = []

    for field in _SUMMARY_FIELDS:
        _add_mismatch_if_needed(
            mismatches,
            field,
            session_normalized[field],
            db_normalized[field],
        )

    _add_mismatch_if_needed(
        mismatches,
        "by_event_type",
        session_normalized["by_event_type"],
        db_normalized["by_event_type"],
    )

    return {
        "type": "usage_events_summary",
        "matches": len(mismatches) == 0,
        "db_missing": False,
        "mismatches": mismatches,
        "session_summary": session_normalized,
        "db_summary": db_normalized,
    }


def compare_usage_events_state(
    *,
    session,
    db_summary: dict | None,
    db_events: list[dict] | None = None,
) -> dict:
    comparisons = [
        compare_usage_summaries(
            session_summary=session.usage_summary(),
            db_summary=db_summary,
        )
    ]

    if db_events is not None:
        comparisons.append(
            compare_usage_event_id_coverage(
                session_events=getattr(session, "usage_events", []) or [],
                db_events=db_events,
            )
        )

    return {
        "matches": all(comparison["matches"] for comparison in comparisons),
        "comparisons": comparisons,
    }


def compare_usage_event_id_coverage(
    *,
    session_events: list[dict],
    db_events: list[dict],
) -> dict:
    session_ids = _event_ids(session_events)
    db_ids = _event_ids(db_events)
    missing_in_db = sorted(session_ids - db_ids)
    extra_in_db = sorted(db_ids - session_ids)

    return {
        "type": "usage_events_event_ids",
        "matches": not missing_in_db and not extra_in_db,
        "db_missing": False,
        "missing_in_db": missing_in_db,
        "extra_in_db": extra_in_db,
        "session_event_count": len(session_ids),
        "db_event_count": len(db_ids),
    }


def _safe_int(value) -> int:
    try:
        parsed = int(float(value))
    except (TypeError, ValueError):
        return 0
    return max(parsed, 0)


def _add_mismatch_if_needed(mismatches: list[dict], field: str, session_value, db_value) -> None:
    if session_value != db_value:
        mismatches.append({
            "field": field,
            "session_value": session_value,
            "db_value": db_value,
        })


def _event_ids(events: list[dict]) -> set[str]:
    ids = set()
    for event in events:
        event_id = event.get("event_id")
        if event_id:
            ids.add(str(event_id))
    return ids
