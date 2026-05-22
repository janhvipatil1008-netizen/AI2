"""Safe dashboard summaries for modular course progress.

Callers provide an existing DB connection. This service performs read-only
repository calls and returns display-safe fields only.
"""

from __future__ import annotations

from repositories.learner_course_enrollment_repository import (
    list_module_progress,
    list_topic_progress,
)
from services.learner_course_enrollment_service import (
    get_active_course_enrollment_with_fallback,
    normalize_course_key,
)
from services.modular_progress_service import clamp_percent


def _empty_summary(source: str = "fallback") -> dict:
    return {
        "source": source,
        "available": False,
        "progress_percent": 0,
        "modules": [],
        "topics": [],
        "error": None,
    }


def _safe_str(value) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _safe_module(row: dict) -> dict:
    return {
        "module_key": _safe_str(row.get("module_key")),
        "status": _safe_str(row.get("status")) or "not_started",
        "completed_topics": int(row.get("completed_topics") or 0),
        "total_topics": int(row.get("total_topics") or 0),
        "progress_percent": clamp_percent(row.get("progress_percent")),
    }


def _safe_topic(row: dict) -> dict:
    return {
        "module_key": _safe_str(row.get("module_key")),
        "topic_key": _safe_str(row.get("topic_key")),
        "legacy_topic_id": _safe_str(row.get("legacy_topic_id")),
        "status": _safe_str(row.get("status")) or "not_started",
        "completion_percent": clamp_percent(row.get("completion_percent")),
        "required_activities_completed": int(
            row.get("required_activities_completed") or 0
        ),
        "required_activities_total": int(row.get("required_activities_total") or 0),
    }


def build_dashboard_modular_progress_summary(
    conn,
    *,
    user_id: str,
    session_id: str,
    track_key: str | None = None,
) -> dict:
    course_key = normalize_course_key(track_key)
    try:
        enrollment_result = get_active_course_enrollment_with_fallback(
            conn,
            user_id=user_id,
            session_id=session_id,
            track_key=track_key,
        )
        enrollment = enrollment_result.get("enrollment") or {}
        enrollment_id = enrollment.get("enrollment_id")
        if enrollment_result.get("source") != "db" or not enrollment_id:
            return _empty_summary("fallback")

        modules = [
            _safe_module(row)
            for row in list_module_progress(conn, enrollment_id=int(enrollment_id))
            if row.get("module_key")
        ]
        topics = [
            _safe_topic(row)
            for row in list_topic_progress(conn, enrollment_id=int(enrollment_id))
            if row.get("topic_key")
        ]
        return {
            "source": "db",
            "available": True,
            "course_key": _safe_str(enrollment.get("course_key")) or course_key,
            "progress_percent": clamp_percent(enrollment.get("progress_percent")),
            "current_module_key": _safe_str(enrollment.get("current_module_key")),
            "current_topic_key": _safe_str(enrollment.get("current_topic_key")),
            "current_legacy_topic_id": _safe_str(
                enrollment.get("current_legacy_topic_id")
            ),
            "modules": modules,
            "topics": topics,
            "error": None,
        }
    except Exception:
        return _empty_summary("error_fallback")
