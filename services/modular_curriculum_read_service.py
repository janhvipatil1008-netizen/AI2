"""Modular curriculum read service.

Loads structured course data from the modular curriculum DB tables.
Not yet wired into the learner-facing runtime — the caller must provide
an open DB connection.

No DB connection creation, no env reads, no Claude calls, no commit/rollback.
WEEKS and ROLE_TRACKS are not touched here.
"""

from __future__ import annotations


# ── Normalizers ───────────────────────────────────────────────────────────────
# Each normalizer returns a safe plain dict copy; the input row is never mutated.


def normalize_course(row: dict | None) -> dict | None:
    """Return a normalised course dict, or None if row is None."""
    if row is None:
        return None
    return {
        "course_id":       row.get("course_id"),
        "course_key":      row.get("course_key", ""),
        "title":           row.get("title", ""),
        "description":     row.get("description", ""),
        "target_audience": row.get("target_audience", ""),
        "level":           row.get("level", "beginner"),
        "status":          row.get("status", "draft"),
        "version":         row.get("version", "v1"),
        "sequence_order":  row.get("sequence_order", 0),
        "metadata":        row.get("metadata") or {},
    }


def normalize_module(row: dict | None) -> dict | None:
    """Return a normalised module dict, or None if row is None."""
    if row is None:
        return None
    return {
        "module_id":         row.get("module_id"),
        "course_id":         row.get("course_id"),
        "module_key":        row.get("module_key", ""),
        "title":             row.get("title", ""),
        "description":       row.get("description", ""),
        "sequence_order":    row.get("sequence_order", 0),
        "estimated_minutes": row.get("estimated_minutes"),
        "status":            row.get("status", "active"),
        "metadata":          row.get("metadata") or {},
    }


def normalize_topic(row: dict | None) -> dict | None:
    """Return a normalised topic dict, or None if row is None."""
    if row is None:
        return None
    return {
        "topic_id":          row.get("topic_id"),
        "course_id":         row.get("course_id"),
        "module_id":         row.get("module_id"),
        "legacy_topic_id":   row.get("legacy_topic_id", ""),
        "topic_key":         row.get("topic_key", ""),
        "title":             row.get("title", ""),
        "description":       row.get("description", ""),
        "difficulty_level":  row.get("difficulty_level", "beginner"),
        "sequence_order":    row.get("sequence_order", 0),
        "estimated_minutes": row.get("estimated_minutes"),
        "status":            row.get("status", "active"),
        "metadata":          row.get("metadata") or {},
    }


def normalize_skill(row: dict | None) -> dict | None:
    """Return a normalised skill dict (including join-derived importance), or None."""
    if row is None:
        return None
    return {
        "skill_id":    row.get("skill_id"),
        "skill_key":   row.get("skill_key", ""),
        "title":       row.get("title", ""),
        "description": row.get("description", ""),
        "category":    row.get("category", ""),
        "level":       row.get("level", ""),
        "importance":  row.get("importance", "core"),
    }


def normalize_activity(row: dict | None) -> dict | None:
    """Return a normalised activity dict, or None if row is None."""
    if row is None:
        return None
    return {
        "activity_id":    row.get("activity_id"),
        "topic_id":       row.get("topic_id"),
        "activity_key":   row.get("activity_key", ""),
        "activity_type":  row.get("activity_type", ""),
        "title":          row.get("title", ""),
        "instructions":   row.get("instructions", ""),
        "rubric_key":     row.get("rubric_key", ""),
        "sequence_order": row.get("sequence_order", 0),
        "is_required":    row.get("is_required", True),
        "metadata":       row.get("metadata") or {},
    }


# ── Read functions ────────────────────────────────────────────────────────────

def get_course_structure(conn, *, course_key: str) -> dict | None:
    """Load a full course tree: course → modules → topics → skills + activities.

    Topics whose module_id is None, or whose module_id does not match any
    fetched module, are collected in "unassigned_topics".

    Returns None if the course is not found in the DB.
    """
    from repositories.modular_curriculum_repository import (
        get_course_by_key,
        list_activities_for_topic,
        list_modules_for_course,
        list_skills_for_topic,
        list_topics_for_course,
    )

    course_row = get_course_by_key(conn, course_key=course_key)
    if course_row is None:
        return None

    course    = normalize_course(course_row)
    course_id = course_row["course_id"]

    module_rows = list_modules_for_course(conn, course_id=course_id)
    topic_rows  = list_topics_for_course(conn, course_id=course_id)

    # Build module_id → enriched-module dict; preserve repo order
    module_by_id:    dict[int, dict] = {}
    modules_ordered: list[dict]      = []
    for m_row in module_rows:
        m           = normalize_module(m_row)
        m["topics"] = []
        mid         = m_row.get("module_id")
        if mid is not None:
            module_by_id[mid] = m
        modules_ordered.append(m)

    unassigned_topics: list[dict] = []

    for t_row in topic_rows:
        tid = t_row.get("topic_id")
        if tid is not None:
            skill_rows    = list_skills_for_topic(conn, topic_id=tid)
            activity_rows = list_activities_for_topic(conn, topic_id=tid)
        else:
            skill_rows    = []
            activity_rows = []

        t               = normalize_topic(t_row)
        t["skills"]     = [normalize_skill(s)    for s in skill_rows]
        t["activities"] = [normalize_activity(a) for a in activity_rows]

        mid = t_row.get("module_id")
        if mid is not None and mid in module_by_id:
            module_by_id[mid]["topics"].append(t)
        else:
            unassigned_topics.append(t)

    return {
        "course":            course,
        "modules":           modules_ordered,
        "unassigned_topics": unassigned_topics,
    }


def list_available_courses(conn, *, status: str | None = "active") -> list[dict]:
    """Return a normalised list of courses, optionally filtered by status."""
    from repositories.modular_curriculum_repository import list_courses

    rows = list_courses(conn, status=status)
    return [c for c in (normalize_course(r) for r in rows) if c is not None]


def get_topic_structure_by_legacy_id(conn, *, legacy_topic_id: str) -> dict | None:
    """Look up a topic by legacy ID or, for v3 catalog-native topics, by topic_key.

    Lookup order:
    1. legacy_topic_id match — covers old static-curriculum topics migrated into the DB.
    2. topic_key match — covers v3 catalog topics that have no legacy ancestor
       (legacy_topic_id is empty in the DB row, so the adapter uses topic_key as the
       URL slug; that slug arrives here as the lookup value).

    Returns None if not found by either path.
    """
    from repositories.modular_curriculum_repository import (
        get_topic_by_legacy_id,
        get_topic_by_topic_key,
        list_activities_for_topic,
        list_skills_for_topic,
    )

    topic_row = get_topic_by_legacy_id(conn, legacy_topic_id=legacy_topic_id)
    if topic_row is None:
        topic_row = get_topic_by_topic_key(conn, topic_key=legacy_topic_id)
    if topic_row is None:
        return None

    tid = topic_row.get("topic_id")
    if tid is None:
        t               = normalize_topic(topic_row)
        t["skills"]     = []
        t["activities"] = []
        return t

    skill_rows    = list_skills_for_topic(conn, topic_id=tid)
    activity_rows = list_activities_for_topic(conn, topic_id=tid)

    t               = normalize_topic(topic_row)
    t["skills"]     = [normalize_skill(s)    for s in skill_rows]
    t["activities"] = [normalize_activity(a) for a in activity_rows]
    return t
