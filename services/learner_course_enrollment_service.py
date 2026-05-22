"""Service helpers for learner course enrollments.

This module is intentionally not wired into runtime routes. Callers pass an
existing DB connection, and repository errors are converted to safe result
dicts so enrollment reads/writes can be adopted incrementally.
"""

from __future__ import annotations

import re

from repositories.learner_course_enrollment_repository import (
    get_active_enrollment,
    update_current_position,
    upsert_course_enrollment,
)


DEFAULT_COURSE_KEY = "aipm-foundations"

# Compatibility bridge from existing track/session keys to modular course keys.
COURSE_KEY_BY_TRACK_KEY = {
    "aipm": "aipm-foundations",
    "evals": "evals-foundations",
    "context": "context-engineering-foundations",
    "ai_builder": "ai-builder-foundations",
    "ai_job_ready": "ai-job-ready",
}


def normalize_course_key(track_key: str | None) -> str:
    """Map known legacy track keys to modular course keys.

    Unknown or empty values intentionally fall back to AI PM foundations to
    preserve the existing default learner experience.
    """
    if not track_key:
        return DEFAULT_COURSE_KEY
    normalized = str(track_key).strip().lower()
    if not normalized:
        return DEFAULT_COURSE_KEY
    return COURSE_KEY_BY_TRACK_KEY.get(normalized, DEFAULT_COURSE_KEY)


def build_default_enrollment_metadata(
    *,
    source: str = "system",
    track_key: str | None = None,
) -> dict:
    """Return safe metadata for a default enrollment record."""
    metadata = {"source": str(source or "system")}
    if track_key:
        metadata["track_key"] = str(track_key)
    return metadata


def sanitize_enrollment_error(error: Exception | str) -> str:
    """Return a short, redacted error string safe for service results."""
    message = str(error)
    message = re.sub(
        r"\bpostgres(?:ql)?://[^\s\"']+",
        "[redacted-postgres-url]",
        message,
        flags=re.IGNORECASE,
    )
    message = re.sub(
        r"(?i)\b(password|passwd|pwd|token|api[_-]?key|secret)=([^\s&;]+)",
        r"\1=[redacted]",
        message,
    )
    if len(message) > 300:
        return message[:300]
    return message


def _fallback_enrollment(final_course_key: str) -> dict:
    return {
        "course_key": final_course_key,
        "status": "active",
        "current_module_key": None,
        "current_topic_key": None,
        "current_legacy_topic_id": None,
        "progress_percent": 0,
    }


def ensure_course_enrollment(
    conn,
    *,
    user_id: str,
    session_id: str,
    track_key: str | None = None,
    course_key: str | None = None,
    course_id: int | None = None,
    source: str = "system",
) -> dict:
    final_course_key = course_key or normalize_course_key(track_key)
    try:
        existing = get_active_enrollment(
            conn,
            user_id=user_id,
            session_id=session_id,
            course_key=final_course_key,
        )
        if existing is not None:
            return {
                "source": "existing",
                "enrollment": existing,
                "created": False,
                "error": None,
            }

        upsert_course_enrollment(
            conn,
            user_id=user_id,
            session_id=session_id,
            course_key=final_course_key,
            course_id=course_id,
            metadata=build_default_enrollment_metadata(
                source=source,
                track_key=track_key,
            ),
        )
        created = get_active_enrollment(
            conn,
            user_id=user_id,
            session_id=session_id,
            course_key=final_course_key,
        )
        return {
            "source": "created" if created is not None else "created_unreadable",
            "enrollment": created,
            "created": True,
            "error": None,
        }
    except Exception as exc:
        return {
            "source": "error",
            "enrollment": None,
            "created": False,
            "error": sanitize_enrollment_error(exc),
        }


def get_active_course_enrollment_with_fallback(
    conn,
    *,
    user_id: str,
    session_id: str,
    track_key: str | None = None,
    course_key: str | None = None,
) -> dict:
    final_course_key = course_key or normalize_course_key(track_key)
    fallback = _fallback_enrollment(final_course_key)
    try:
        enrollment = get_active_enrollment(
            conn,
            user_id=user_id,
            session_id=session_id,
            course_key=final_course_key,
        )
        if enrollment is not None:
            return {"source": "db", "enrollment": enrollment, "error": None}
        return {"source": "fallback", "enrollment": fallback, "error": None}
    except Exception as exc:
        return {
            "source": "error_fallback",
            "enrollment": fallback,
            "error": sanitize_enrollment_error(exc),
        }


def update_enrollment_position_safely(
    conn,
    *,
    enrollment_id: int,
    current_module_id: int | None = None,
    current_module_key: str | None = None,
    current_topic_id: int | None = None,
    current_topic_key: str | None = None,
    current_legacy_topic_id: str | None = None,
    progress_percent: int | None = None,
) -> dict:
    try:
        update_current_position(
            conn,
            enrollment_id=enrollment_id,
            current_module_id=current_module_id,
            current_module_key=current_module_key,
            current_topic_id=current_topic_id,
            current_topic_key=current_topic_key,
            current_legacy_topic_id=current_legacy_topic_id,
            progress_percent=progress_percent,
        )
        return {"updated": True, "error": None}
    except Exception as exc:
        return {"updated": False, "error": sanitize_enrollment_error(exc)}


def summarize_enrollment_progress(
    *,
    enrollment: dict | None,
    module_progress: list[dict] | None = None,
    topic_progress: list[dict] | None = None,
) -> dict:
    safe_enrollment = enrollment or {}
    safe_modules = module_progress or []
    safe_topics = topic_progress or []
    completed_topic_count = sum(
        1
        for topic in safe_topics
        if topic.get("status") == "completed"
        or topic.get("completion_percent") == 100
    )
    return {
        "course_key": safe_enrollment.get("course_key"),
        "status": safe_enrollment.get("status"),
        "progress_percent": safe_enrollment.get("progress_percent", 0),
        "current_module_key": safe_enrollment.get("current_module_key"),
        "current_topic_key": safe_enrollment.get("current_topic_key"),
        "current_legacy_topic_id": safe_enrollment.get("current_legacy_topic_id"),
        "module_count": len(safe_modules),
        "topic_count": len(safe_topics),
        "completed_topic_count": completed_topic_count,
    }
