"""Modular curriculum fallback service.

Provides safe wrappers around the modular curriculum read service that fall
back to the static WEEKS / ROLE_TRACKS curriculum when the DB is unavailable,
returns nothing, or raises an error.

Always returns a consistent envelope shape so callers never need to branch on
missing infrastructure.

Safety constraints (all enforced):
- No DB connection creation.
- No env reads.
- No app / routes imports.
- No SessionContext mutation.
- No WEEKS / ROLE_TRACKS mutation.
- No Claude / LLM calls.
- No commit / rollback.
- Safe, redacted error messages only.
"""

from __future__ import annotations

import re

from curriculum.syllabus import ROLE_TRACKS
from curriculum.topics import get_topics_for_track


# ── Course key ↔ track key mapping ────────────────────────────────────────────

_COURSE_KEY_TO_TRACK: dict[str, str] = {
    "aipm-foundations":                "aipm",
    "evals-foundations":               "evals",
    "context-engineering-foundations": "context",
}

_TRACK_TO_COURSE_KEY: dict[str, str] = {v: k for k, v in _COURSE_KEY_TO_TRACK.items()}


# ── Default activities (plain dicts — no DB, no dataclasses) ──────────────────

_ACTIVITY_TEMPLATES: list[dict] = [
    {"activity_key": "lesson",     "activity_type": "lesson",             "title": "Read & Learn",   "sequence_order": 1, "is_required": True},
    {"activity_key": "practice",   "activity_type": "practice_task",      "title": "Practice Task",  "sequence_order": 2, "is_required": True},
    {"activity_key": "quiz",       "activity_type": "quiz",               "title": "Quiz",           "sequence_order": 3, "is_required": True},
    {"activity_key": "portfolio",  "activity_type": "portfolio_task",     "title": "Portfolio Task", "sequence_order": 4, "is_required": True},
    {"activity_key": "interview",  "activity_type": "interview_practice", "title": "Interview Prep", "sequence_order": 5, "is_required": True},
    {"activity_key": "reflection", "activity_type": "reflection",         "title": "Reflection",     "sequence_order": 6, "is_required": False},
]


def _default_activities() -> list[dict]:
    return [dict(a) for a in _ACTIVITY_TEMPLATES]


# ── Helpers ───────────────────────────────────────────────────────────────────

_URL_PATTERN = re.compile(r"postgres(?:ql)?://\S+", re.IGNORECASE)


def _safe_error(exc: Exception) -> str:
    """Return a truncated, sanitized error string safe to surface to callers."""
    msg = _URL_PATTERN.sub("[DB_URL_REDACTED]", str(exc))
    return msg[:300]


def _slugify(value: str) -> str:
    key = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return key or "untitled"


def _track_from_legacy_id(legacy_topic_id: str) -> str | None:
    """Derive a track_key from a legacy topic ID like 'aipm-week-1-...'."""
    for track_key in ROLE_TRACKS:
        if legacy_topic_id.startswith(f"{track_key}-"):
            return track_key
    return None


# ── Static → modular converters ───────────────────────────────────────────────

def static_topic_to_modular_topic(topic, *, sequence_order: int = 0) -> dict:
    """Convert a TopicCard into a modular-like topic dict.

    Does not mutate the topic object.  Adds empty skills list and default
    activity stubs so callers get the same shape as a DB-backed topic.
    """
    return {
        "topic_id":          None,
        "course_id":         None,
        "module_id":         None,
        "legacy_topic_id":   topic.topic_id,
        "topic_key":         _slugify(topic.topic_title),
        "title":             topic.topic_title,
        "description":       topic.description,
        "difficulty_level":  "beginner",
        "sequence_order":    sequence_order,
        "estimated_minutes": None,
        "status":            "active",
        "metadata":          {},
        "skills":            [],
        "activities":        _default_activities(),
    }


def static_track_to_modular_course(track_key: str) -> dict | None:
    """Build a modular-like course structure from the static curriculum.

    Returns the same shape as get_course_structure:
        {"course": {...}, "modules": [... each with "topics": [...]],
         "unassigned_topics": []}

    - Modules use module-{NN} keys; week_number is NOT a public field.
    - Preserves legacy_topic_id for every topic.
    - Does not mutate WEEKS or ROLE_TRACKS.
    - Returns None for unknown track keys.
    """
    if track_key not in ROLE_TRACKS:
        return None

    track_info = ROLE_TRACKS[track_key]
    course_key = _TRACK_TO_COURSE_KEY.get(track_key, f"{_slugify(track_key)}-foundations")

    course = {
        "course_id":        None,
        "course_key":       course_key,
        "title":            f"{track_info['label']} Foundations",
        "description":      f"Foundations learning path for {track_info['label']}.",
        "target_audience":  f"Aspiring {track_info['label']}s",
        "level":            "beginner",
        "status":           "draft",
        "version":          "v1",
        "sequence_order":   0,
        "metadata": {
            "source_track_key": track_key,
            "icon":             track_info.get("icon", ""),
            "color":            track_info.get("color", ""),
        },
    }

    track_topics = get_topics_for_track(track_key)

    by_week: dict[int, list] = {}
    for topic in track_topics:
        by_week.setdefault(topic.week_num, []).append(topic)

    modules: list[dict] = []
    for week_num in sorted(by_week.keys()):
        week_topics = by_week[week_num]
        first       = week_topics[0]
        module_key  = f"module-{week_num:02d}"

        module_topics = [
            static_topic_to_modular_topic(t, sequence_order=idx)
            for idx, t in enumerate(week_topics)
        ]

        modules.append({
            "module_id":         None,
            "course_id":         None,
            "module_key":        module_key,
            "title":             first.module_title,
            "description":       first.module_theme,
            "sequence_order":    week_num - 1,
            "estimated_minutes": None,
            "status":            "active",
            "metadata":          {"source_week_num": week_num},
            "topics":            module_topics,
        })

    return {
        "course":            course,
        "modules":           modules,
        "unassigned_topics": [],
    }


# ── Public fallback functions ─────────────────────────────────────────────────

def get_course_structure_with_fallback(
    conn,
    *,
    course_key: str,
    fallback_track_key: str | None = None,
) -> dict:
    """Try modular DB read; fall back to static curriculum on failure or miss.

    Returns:
        {
            "source":           "db" | "fallback" | "error_fallback",
            "course_structure": dict | None,
            "error":            str | None,
        }
    """
    if conn is not None:
        try:
            from services.modular_curriculum_read_service import (
                get_course_structure as _get_course_structure,
            )
            result = _get_course_structure(conn, course_key=course_key)
            if result is not None:
                return {"source": "db", "course_structure": result, "error": None}
            source   = "fallback"
            exc_msg  = None
        except Exception as exc:
            source   = "error_fallback"
            exc_msg  = _safe_error(exc)
    else:
        source  = "fallback"
        exc_msg = None

    track_key  = fallback_track_key or _COURSE_KEY_TO_TRACK.get(course_key)
    static_cs  = static_track_to_modular_course(track_key) if track_key else None

    return {
        "source":           source,
        "course_structure": static_cs,
        "error":            exc_msg,
    }


def list_courses_with_fallback(conn=None) -> dict:
    """Return available courses from DB or static tracks.

    Queries all courses (status=None) so draft DB courses are visible.

    Returns:
        {
            "source":  "db" | "fallback" | "error_fallback",
            "courses": list[dict],
            "error":   str | None,
        }
    """
    if conn is not None:
        try:
            from services.modular_curriculum_read_service import (
                list_available_courses as _list_available_courses,
            )
            db_courses = _list_available_courses(conn, status=None)
            if db_courses:
                return {"source": "db", "courses": db_courses, "error": None}
            source  = "fallback"
            exc_msg = None
        except Exception as exc:
            source  = "error_fallback"
            exc_msg = _safe_error(exc)
    else:
        source  = "fallback"
        exc_msg = None

    static_courses: list[dict] = []
    for idx, (track_key, track_info) in enumerate(ROLE_TRACKS.items()):
        course_key = _TRACK_TO_COURSE_KEY.get(track_key, f"{_slugify(track_key)}-foundations")
        static_courses.append({
            "course_id":       None,
            "course_key":      course_key,
            "title":           f"{track_info['label']} Foundations",
            "description":     f"Foundations learning path for {track_info['label']}.",
            "target_audience": f"Aspiring {track_info['label']}s",
            "level":           "beginner",
            "status":          "draft",
            "version":         "v1",
            "sequence_order":  idx,
            "metadata": {
                "source_track_key": track_key,
                "icon":             track_info.get("icon", ""),
                "color":            track_info.get("color", ""),
            },
        })

    return {"source": source, "courses": static_courses, "error": exc_msg}


def get_topic_structure_by_legacy_id_with_fallback(
    conn,
    *,
    legacy_topic_id: str,
) -> dict:
    """Try modular DB topic lookup; fall back to static curriculum on failure.

    Returns:
        {
            "source": "db" | "fallback" | "error_fallback",
            "topic":  dict | None,
            "error":  str | None,
        }
    """
    if conn is not None:
        try:
            from services.modular_curriculum_read_service import (
                get_topic_structure_by_legacy_id as _get_topic,
            )
            result = _get_topic(conn, legacy_topic_id=legacy_topic_id)
            if result is not None:
                return {"source": "db", "topic": result, "error": None}
            source  = "fallback"
            exc_msg = None
        except Exception as exc:
            source  = "error_fallback"
            exc_msg = _safe_error(exc)
    else:
        source  = "fallback"
        exc_msg = None

    track_key    = _track_from_legacy_id(legacy_topic_id)
    static_topic = None
    if track_key:
        from curriculum.topics import get_topic as _get_static_topic
        card = _get_static_topic(track_key, legacy_topic_id)
        if card is not None:
            static_topic = static_topic_to_modular_topic(card)

    return {"source": source, "topic": static_topic, "error": exc_msg}
