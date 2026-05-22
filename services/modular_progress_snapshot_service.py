"""Safe orchestration for modular progress snapshot writes.

This helper composes existing modular curriculum, progress calculation, and
write-through services using an injected DB connection. It does not create
connections or own transactions.
"""

from __future__ import annotations

import re

from services.learner_course_enrollment_service import (
    get_active_course_enrollment_with_fallback,
    normalize_course_key,
)
from services.modular_curriculum_fallback_service import get_course_structure_with_fallback
from services.modular_progress_service import calculate_course_progress
from services.modular_progress_write_through_service import write_modular_progress_snapshot


def sanitize_modular_snapshot_error(error: Exception | str) -> str:
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
    return message[:300]


def _session_attr(session, *names: str) -> dict:
    for name in names:
        value = getattr(session, name, None)
        if isinstance(value, dict):
            return value
    return {}


def write_modular_progress_snapshot_safely(
    *,
    conn,
    user_id: str,
    session_id: str,
    session,
    course_key: str | None = None,
) -> dict:
    try:
        track_key = getattr(getattr(session, "track", None), "value", None)
        final_course_key = course_key or normalize_course_key(track_key)

        enrollment_result = get_active_course_enrollment_with_fallback(
            conn,
            user_id=user_id,
            session_id=session_id,
            track_key=track_key,
            course_key=final_course_key,
        )
        enrollment = enrollment_result.get("enrollment") or {}
        enrollment_id = enrollment.get("enrollment_id")
        if not enrollment_id:
            return {
                "updated": False,
                "skipped": True,
                "source": enrollment_result.get("source") or "no_enrollment",
                "error": None,
            }

        course_result = get_course_structure_with_fallback(
            conn,
            course_key=final_course_key,
            fallback_track_key=track_key,
        )
        course_structure = course_result.get("course_structure") if isinstance(course_result, dict) else None
        if not course_structure:
            return {
                "updated": False,
                "skipped": True,
                "source": course_result.get("source", "no_course") if isinstance(course_result, dict) else "no_course",
                "error": None,
            }

        course_progress = calculate_course_progress(
            course_structure=course_structure,
            session_progress=_session_attr(session, "topic_progress", "progress"),
            generated_content=_session_attr(session, "generated_topic_content", "generated_content"),
            quiz_submissions=_session_attr(session, "quiz_submissions"),
            portfolio_submissions=_session_attr(session, "portfolio_submissions"),
            interview_submissions=_session_attr(session, "interview_submissions"),
        )
        write_result = write_modular_progress_snapshot(
            conn,
            enrollment_id=int(enrollment_id),
            course_progress=course_progress,
        )
        if not write_result.get("updated"):
            return {
                "updated": False,
                "skipped": False,
                "source": "write_error",
                "error": write_result.get("error"),
            }
        return {
            "updated": True,
            "skipped": False,
            "source": course_result.get("source", enrollment_result.get("source")) if isinstance(course_result, dict) else enrollment_result.get("source"),
            "error": None,
        }
    except Exception as exc:
        return {
            "updated": False,
            "skipped": False,
            "source": "error",
            "error": sanitize_modular_snapshot_error(exc),
        }
