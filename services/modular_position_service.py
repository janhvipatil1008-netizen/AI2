"""Pure helpers for modular learner position selection.

This module derives current and next topic pointers from calculated modular
course progress. It has no runtime wiring and does not access DB, env, app, or
route state.
"""

from __future__ import annotations

from services.modular_progress_service import clamp_percent


def _safe_str(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _safe_topic_shape(topic: dict | None, *, source: str) -> dict:
    safe = topic if isinstance(topic, dict) else {}
    return {
        "module_key": _safe_str(safe.get("module_key")),
        "topic_key": _safe_str(safe.get("topic_key")),
        "legacy_topic_id": _safe_str(safe.get("legacy_topic_id")),
        "status": _safe_str(safe.get("status")),
        "completion_percent": clamp_percent(safe.get("completion_percent")),
        "source": source,
    }


def _topic_copy(topic: dict, *, module_key: str | None = None) -> dict:
    copied = {
        "module_key": _safe_str(topic.get("module_key")) or module_key,
        "topic_key": _safe_str(topic.get("topic_key")),
        "legacy_topic_id": _safe_str(topic.get("legacy_topic_id")),
        "status": _safe_str(topic.get("status")),
        "completion_percent": clamp_percent(topic.get("completion_percent")),
    }
    if "sequence_order" in topic:
        copied["sequence_order"] = topic.get("sequence_order")
    return copied


def flatten_course_topics(course_progress: dict | None) -> list[dict]:
    """Return module topics followed by unassigned topics in display order."""
    if not isinstance(course_progress, dict):
        return []

    topics: list[dict] = []
    for module in course_progress.get("modules", []) or []:
        if not isinstance(module, dict):
            continue
        module_key = _safe_str(module.get("module_key"))
        for topic in module.get("topics", []) or []:
            if isinstance(topic, dict):
                topics.append(_topic_copy(topic, module_key=module_key))

    for topic in course_progress.get("unassigned_topics", []) or []:
        if isinstance(topic, dict):
            topics.append(_topic_copy(topic))

    return topics


def is_topic_completed(topic: dict) -> bool:
    if not isinstance(topic, dict):
        return False
    return (
        str(topic.get("status") or "").strip().lower() == "completed"
        or clamp_percent(topic.get("completion_percent")) >= 100
    )


def is_topic_in_progress(topic: dict) -> bool:
    if not isinstance(topic, dict) or is_topic_completed(topic):
        return False
    completion_percent = clamp_percent(topic.get("completion_percent"))
    return (
        str(topic.get("status") or "").strip().lower() == "in_progress"
        or 0 < completion_percent < 100
    )


def pick_current_topic(course_progress: dict | None) -> dict:
    topics = flatten_course_topics(course_progress)
    if not topics:
        return _safe_topic_shape(None, source="empty")

    in_progress = next((topic for topic in topics if is_topic_in_progress(topic)), None)
    if in_progress is not None:
        return _safe_topic_shape(in_progress, source="in_progress")

    incomplete = next((topic for topic in topics if not is_topic_completed(topic)), None)
    if incomplete is not None:
        return _safe_topic_shape(incomplete, source="next_not_started")

    return _safe_topic_shape(topics[-1], source="completed_fallback")


def pick_next_topic(course_progress: dict | None) -> dict:
    topics = flatten_course_topics(course_progress)
    for topic in topics:
        if not is_topic_completed(topic):
            return _safe_topic_shape(topic, source="next_not_started")
    return _safe_topic_shape(None, source="completed")


def build_position_summary(course_progress: dict | None) -> dict:
    safe_course = course_progress if isinstance(course_progress, dict) else {}
    next_topic = pick_next_topic(course_progress)
    return {
        "current": pick_current_topic(course_progress),
        "next": next_topic,
        "has_next": next_topic.get("source") != "completed",
        "course_progress_percent": clamp_percent(safe_course.get("progress_percent")),
        "course_status": _safe_str(safe_course.get("status")),
    }


def build_legacy_position_fallback(session=None) -> dict:
    current_week = getattr(session, "current_week", None)
    if current_week is None:
        return {"current_module_label": None, "source": "disabled"}
    return {
        "current_module_label": f"Module {current_week}",
        "source": "session_fallback",
    }
