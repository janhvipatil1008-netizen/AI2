"""Safe learning-context helpers for the todo planner."""

from __future__ import annotations

from services.learner_course_enrollment_service import normalize_course_key


def _safe_str(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _track_key(session) -> str | None:
    track = getattr(session, "track", None)
    value = getattr(track, "value", track)
    return _safe_str(value)


def _session_context(session) -> dict:
    if session is None:
        return {
            "course_key": None,
            "current_module_key": None,
            "current_topic_key": None,
            "current_legacy_topic_id": None,
            "source": "disabled",
        }
    current_week = getattr(session, "current_week", None)
    module_label = None
    if current_week is not None:
        module_label = f"Module {current_week}"
    track_key = _track_key(session)
    return {
        "course_key": normalize_course_key(track_key),
        "current_module_key": module_label,
        "current_topic_key": None,
        "current_legacy_topic_id": None,
        "source": "session",
    }


def _has_modular_context(summary: dict) -> bool:
    return bool(
        summary.get("available")
        or summary.get("current_module_key")
        or summary.get("current_topic_key")
        or summary.get("current_legacy_topic_id")
    )


def build_todo_learning_context(
    *,
    enrollment_summary: dict | None = None,
    modular_progress_summary: dict | None = None,
    session=None,
) -> dict:
    """Return display-safe course/module/topic context for the todo planner."""
    modular = dict(modular_progress_summary or {})
    if modular.get("source") == "db" and _has_modular_context(modular):
        return {
            "course_key": _safe_str(modular.get("course_key")),
            "current_module_key": _safe_str(modular.get("current_module_key")),
            "current_topic_key": _safe_str(modular.get("current_topic_key")),
            "current_legacy_topic_id": _safe_str(
                modular.get("current_legacy_topic_id")
            ),
            "source": "db",
        }

    enrollment = dict(enrollment_summary or {})
    if enrollment.get("source") == "db":
        return {
            "course_key": _safe_str(enrollment.get("course_key")),
            "current_module_key": _safe_str(enrollment.get("current_module_key")),
            "current_topic_key": _safe_str(enrollment.get("current_topic_key")),
            "current_legacy_topic_id": _safe_str(
                enrollment.get("current_legacy_topic_id")
            ),
            "source": "db",
        }

    return _session_context(session)
