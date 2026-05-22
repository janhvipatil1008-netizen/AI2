"""Write-through helpers for calculated modular progress snapshots.

Callers provide an existing DB connection and a safe progress summary from
modular_progress_service. This module does not own transactions or runtime
wiring.
"""

from __future__ import annotations

import re

from repositories.learner_course_enrollment_repository import (
    update_current_position,
    upsert_module_progress,
    upsert_topic_progress,
)
from services.modular_progress_service import clamp_percent, pick_current_position_from_progress


def sanitize_progress_write_error(error: Exception | str) -> str:
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


def _explicit_position(course_progress: dict) -> dict:
    nested = course_progress.get("current_position")
    if isinstance(nested, dict):
        return {
            "current_module_key": nested.get("current_module_key"),
            "current_topic_key": nested.get("current_topic_key"),
            "current_legacy_topic_id": nested.get("current_legacy_topic_id"),
        }
    return {
        "current_module_key": course_progress.get("current_module_key"),
        "current_topic_key": course_progress.get("current_topic_key"),
        "current_legacy_topic_id": course_progress.get("current_legacy_topic_id"),
    }


def _has_position(position: dict) -> bool:
    return any(
        position.get(key)
        for key in (
            "current_module_key",
            "current_topic_key",
            "current_legacy_topic_id",
        )
    )


def write_modular_progress_snapshot(
    conn,
    *,
    enrollment_id: int,
    course_progress: dict,
) -> dict:
    modules_written = 0
    topics_written = 0
    position_updated = False

    try:
        for module in course_progress.get("modules", []) or []:
            module_key = module.get("module_key")
            if not module_key:
                continue
            upsert_module_progress(
                conn,
                enrollment_id=enrollment_id,
                module_key=module_key,
                status=module.get("status") or "not_started",
                completed_topics=int(module.get("completed_topics") or 0),
                total_topics=int(module.get("total_topics") or 0),
                progress_percent=clamp_percent(module.get("progress_percent")),
            )
            modules_written += 1

        for topic in course_progress.get("topic_progress", []) or []:
            topic_key = topic.get("topic_key")
            if not topic_key:
                continue
            upsert_topic_progress(
                conn,
                enrollment_id=enrollment_id,
                topic_key=topic_key,
                module_key=topic.get("module_key"),
                legacy_topic_id=topic.get("legacy_topic_id"),
                status=topic.get("status") or "not_started",
                completion_percent=clamp_percent(topic.get("completion_percent")),
                required_activities_completed=int(
                    topic.get("required_activities_completed") or 0
                ),
                required_activities_total=int(
                    topic.get("required_activities_total") or 0
                ),
            )
            topics_written += 1

        position = _explicit_position(course_progress)
        if not _has_position(position):
            position = pick_current_position_from_progress(course_progress)

        update_current_position(
            conn,
            enrollment_id=enrollment_id,
            current_module_key=position.get("current_module_key"),
            current_topic_key=position.get("current_topic_key"),
            current_legacy_topic_id=position.get("current_legacy_topic_id"),
            progress_percent=clamp_percent(course_progress.get("progress_percent")),
        )
        position_updated = True

        return {
            "updated": True,
            "modules": modules_written,
            "topics": topics_written,
            "position_updated": position_updated,
            "error": None,
        }
    except Exception as exc:
        return {
            "updated": False,
            "modules": modules_written,
            "topics": topics_written,
            "position_updated": position_updated,
            "error": sanitize_progress_write_error(exc),
        }
