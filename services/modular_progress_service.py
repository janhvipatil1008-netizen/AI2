"""Pure modular course progress calculations.

This service derives course/module/topic progress from modular curriculum
structures and existing SessionContext-style completion dictionaries.

Safety constraints:
- No DB connection creation.
- No env reads.
- No app/routes imports.
- No SessionContext mutation.
- No WEEKS/ROLE_TRACKS mutation.
- No provider calls.
- No commit/rollback.
- No runtime wiring.
"""

from __future__ import annotations


_ACTIVITY_TYPE_MAP = {
    "lesson": "lesson",
    "learn": "lesson",
    "learning_content": "lesson",
    "content": "lesson",
    "practice": "practice",
    "practice_task": "practice",
    "quiz": "quiz",
    "portfolio": "portfolio",
    "portfolio_task": "portfolio",
    "interview": "interview",
    "interview_practice": "interview",
    "reflection": "reflection",
}

_DONE_VALUES = {"done", "completed"}


def clamp_percent(value: int | float | None) -> int:
    if value is None:
        return 0
    try:
        rounded = int(round(float(value)))
    except (TypeError, ValueError):
        return 0
    return max(0, min(100, rounded))


def normalize_activity_type(value: str | None) -> str:
    if not value:
        return "unknown"
    normalized = str(value).strip().lower()
    if not normalized:
        return "unknown"
    return _ACTIVITY_TYPE_MAP.get(normalized, "unknown")


def _topic_entry(source: dict | None, legacy_topic_id: str) -> dict:
    if not isinstance(source, dict):
        return {}
    entry = source.get(legacy_topic_id)
    return entry if isinstance(entry, dict) else {}


def _has_review_or_score(entry: dict, *, feedback_key: str) -> bool:
    if not entry:
        return False
    if entry.get("score") is not None:
        return True
    return bool(str(entry.get(feedback_key) or "").strip())


def infer_completed_activity_types(
    *,
    legacy_topic_id: str,
    session_progress: dict | None = None,
    generated_content: dict | None = None,
    quiz_submissions: dict | None = None,
    portfolio_submissions: dict | None = None,
    interview_submissions: dict | None = None,
) -> set[str]:
    """Infer completed modular activity types from existing session dictionaries.

    Generated lesson/practice content is intentionally not treated as completion
    by itself; existing SessionContext progress or evaluated submissions remain
    the source of completion truth.
    """
    del generated_content
    completed: set[str] = set()
    progress = _topic_entry(session_progress, legacy_topic_id)
    for raw_type, status in progress.items():
        if str(status or "").strip().lower() in _DONE_VALUES:
            activity_type = normalize_activity_type(raw_type)
            if activity_type != "unknown":
                completed.add(activity_type)

    if _has_review_or_score(_topic_entry(quiz_submissions, legacy_topic_id), feedback_key="evaluation"):
        completed.add("quiz")
    if _has_review_or_score(_topic_entry(portfolio_submissions, legacy_topic_id), feedback_key="feedback"):
        completed.add("portfolio")
    if _has_review_or_score(_topic_entry(interview_submissions, legacy_topic_id), feedback_key="feedback"):
        completed.add("interview")

    return completed


def calculate_topic_progress(
    *,
    topic: dict,
    completed_activity_types: set[str] | None = None,
) -> dict:
    completed_types = set(completed_activity_types or set())
    required_activities = [
        activity
        for activity in topic.get("activities", []) or []
        if activity.get("is_required", True)
    ]
    required_types = [
        normalize_activity_type(activity.get("activity_type"))
        for activity in required_activities
    ]
    required_total = len(required_types)
    required_completed = sum(1 for activity_type in required_types if activity_type in completed_types)
    completion_percent = clamp_percent(
        (required_completed / required_total * 100) if required_total else 0
    )

    if required_completed <= 0:
        status = "not_started"
    elif required_total and required_completed >= required_total:
        status = "completed"
    else:
        status = "in_progress"

    return {
        "topic_key": topic.get("topic_key"),
        "legacy_topic_id": topic.get("legacy_topic_id"),
        "module_key": topic.get("module_key"),
        "required_activities_total": required_total,
        "required_activities_completed": required_completed,
        "completion_percent": completion_percent,
        "status": status,
    }


def calculate_module_progress(
    *,
    module: dict,
) -> dict:
    topics = list(module.get("topics", []) or [])
    topic_progress = [
        topic
        if {"completion_percent", "status"}.issubset(topic.keys())
        else calculate_topic_progress(topic=topic)
        for topic in topics
    ]
    total_topics = len(topic_progress)
    completed_topics = sum(1 for topic in topic_progress if topic.get("status") == "completed")
    progress_percent = clamp_percent(
        sum(clamp_percent(topic.get("completion_percent")) for topic in topic_progress) / total_topics
        if total_topics
        else 0
    )

    if total_topics == 0 or progress_percent <= 0:
        status = "not_started"
    elif completed_topics >= total_topics:
        status = "completed"
    else:
        status = "in_progress"

    return {
        "module_key": module.get("module_key"),
        "sequence_order": module.get("sequence_order"),
        "total_topics": total_topics,
        "completed_topics": completed_topics,
        "progress_percent": progress_percent,
        "status": status,
        "topics": topic_progress,
    }


def _topic_with_module_key(topic: dict, module_key: str | None) -> dict:
    if topic.get("module_key") == module_key:
        return topic
    copied = dict(topic)
    copied["module_key"] = module_key
    return copied


def _calculate_topic_from_session_state(
    *,
    topic: dict,
    session_progress: dict | None,
    generated_content: dict | None,
    quiz_submissions: dict | None,
    portfolio_submissions: dict | None,
    interview_submissions: dict | None,
) -> dict:
    legacy_topic_id = str(topic.get("legacy_topic_id") or "")
    completed = infer_completed_activity_types(
        legacy_topic_id=legacy_topic_id,
        session_progress=session_progress,
        generated_content=generated_content,
        quiz_submissions=quiz_submissions,
        portfolio_submissions=portfolio_submissions,
        interview_submissions=interview_submissions,
    )
    return calculate_topic_progress(topic=topic, completed_activity_types=completed)


def calculate_course_progress(
    *,
    course_structure: dict,
    session_progress: dict | None = None,
    generated_content: dict | None = None,
    quiz_submissions: dict | None = None,
    portfolio_submissions: dict | None = None,
    interview_submissions: dict | None = None,
) -> dict:
    course = course_structure.get("course") or {}
    modules: list[dict] = []
    all_topic_progress: list[dict] = []

    for module in course_structure.get("modules", []) or []:
        module_key = module.get("module_key")
        calculated_topics = [
            _calculate_topic_from_session_state(
                topic=_topic_with_module_key(topic, module_key),
                session_progress=session_progress,
                generated_content=generated_content,
                quiz_submissions=quiz_submissions,
                portfolio_submissions=portfolio_submissions,
                interview_submissions=interview_submissions,
            )
            for topic in module.get("topics", []) or []
        ]
        module_progress = calculate_module_progress(
            module={
                "module_key": module_key,
                "sequence_order": module.get("sequence_order"),
                "topics": calculated_topics,
            }
        )
        modules.append(module_progress)
        all_topic_progress.extend(calculated_topics)

    unassigned_topics = [
        _calculate_topic_from_session_state(
            topic=topic,
            session_progress=session_progress,
            generated_content=generated_content,
            quiz_submissions=quiz_submissions,
            portfolio_submissions=portfolio_submissions,
            interview_submissions=interview_submissions,
        )
        for topic in course_structure.get("unassigned_topics", []) or []
    ]
    all_topic_progress.extend(unassigned_topics)

    total_topics = len(all_topic_progress)
    completed_topics = sum(1 for topic in all_topic_progress if topic.get("status") == "completed")
    progress_percent = clamp_percent(
        sum(clamp_percent(topic.get("completion_percent")) for topic in all_topic_progress) / total_topics
        if total_topics
        else 0
    )

    if total_topics == 0 or progress_percent <= 0:
        status = "not_started"
    elif completed_topics >= total_topics:
        status = "completed"
    else:
        status = "in_progress"

    return {
        "course_key": course.get("course_key"),
        "progress_percent": progress_percent,
        "status": status,
        "modules": modules,
        "unassigned_topics": unassigned_topics,
        "topic_progress": all_topic_progress,
        "completed_topics": completed_topics,
        "total_topics": total_topics,
    }


def pick_current_position_from_progress(course_progress: dict) -> dict:
    topics = list(course_progress.get("topic_progress", []) or [])
    selected = None
    for status in ("in_progress", "not_started"):
        selected = next((topic for topic in topics if topic.get("status") == status), None)
        if selected is not None:
            break
    if selected is None and topics:
        selected = topics[-1]

    return {
        "current_module_key": selected.get("module_key") if selected else None,
        "current_topic_key": selected.get("topic_key") if selected else None,
        "current_legacy_topic_id": selected.get("legacy_topic_id") if selected else None,
    }
