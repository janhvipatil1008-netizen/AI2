"""Safe formatting helpers for the internal beta metrics view."""

from __future__ import annotations


NOT_AVAILABLE = "not available yet"


def build_beta_metrics_payload(
    *,
    db_available: bool,
    db_metrics: dict | None = None,
) -> dict:
    """Combine config-level health with optional aggregate DB metrics."""
    return {
        "storage_config": storage_config_summary(),
        "db_available": db_available,
        "session_user_summary": _section(
            db_metrics,
            "session_user_summary",
            ["total_sessions", "total_users"],
        ),
        "usage_summary": _section(
            db_metrics,
            "usage_summary",
            ["total_usage_events", "claude_events", "cache_events", "limit_blocked_events"],
        ),
        "learning_outcomes_summary": _section(
            db_metrics,
            "learning_outcomes_summary",
            [
                "total_outcomes",
                "baseline_completed_count",
                "post_completed_count",
                "improved_count",
                "average_improvement_delta",
            ],
        ),
        "beta_feedback_summary": {
            **_section(
                db_metrics,
                "beta_feedback_summary",
                [
                    "total_feedback_submissions",
                    "average_usefulness_score",
                    "average_clarity_score",
                ],
            ),
            "willingness_to_pay_counts": (
                _safe_willingness_counts(
                    (db_metrics or {})
                    .get("beta_feedback_summary", {})
                    .get("willingness_to_pay_counts", {})
                )
                if db_available else {}
            ),
        },
        "cache_summary": _section(
            db_metrics,
            "cache_summary",
            ["total_rows", "active_rows", "stale_rows"],
        ),
        "notes": _notes(db_available),
    }


def storage_config_summary() -> dict:
    from services.storage_flags import (
        is_curriculum_db_reads_enabled,
        is_db_write_through_enabled,
        is_progress_db_reads_enabled,
        is_todos_db_reads_enabled,
        is_usage_limits_enabled,
    )

    curriculum_reads = is_curriculum_db_reads_enabled()
    progress_reads = is_progress_db_reads_enabled()
    todos_reads = is_todos_db_reads_enabled()
    return {
        "source_of_truth": "SessionContext",
        "db_primary_reads": False,
        "db_write_through_enabled": is_db_write_through_enabled(),
        "curriculum_db_reads_enabled": curriculum_reads,
        "progress_db_reads_enabled": progress_reads,
        "todos_db_reads_enabled": todos_reads,
        "db_reads_enabled": any((curriculum_reads, progress_reads, todos_reads)),
        "usage_limits_enabled": is_usage_limits_enabled(),
    }


def _section(db_metrics: dict | None, section_name: str, keys: list[str]) -> dict:
    section = (db_metrics or {}).get(section_name, {})
    return {key: section.get(key, NOT_AVAILABLE) for key in keys}


def _safe_willingness_counts(counts: dict) -> dict:
    allowed = {"yes", "no", "maybe", "other", "not_specified"}
    return {key: counts.get(key, 0) for key in allowed if key in counts}


def _notes(db_available: bool) -> list[str]:
    notes = [
        "Counts only; no learner emails, submissions, notes, generated content, or feedback text are shown.",
        "SessionContext remains the runtime source of truth for learner-facing behavior.",
    ]
    if db_available:
        notes.append("Aggregate DB metrics loaded with one read-only connection.")
    else:
        notes.append("DB metrics are unavailable; showing configuration-level health only.")
    return notes
