"""Manual modular curriculum seed script.

Builds the modular curriculum export and upserts it into the new schema tables:
courses, course_modules, skills, course_topics, topic_skills, topic_activities.

Usage:
    python scripts/seed_modular_curriculum.py

Requires SUPABASE_DATABASE_URL to be set in the environment (or .env loaded
before running).  The script never runs automatically — it must be invoked
explicitly.

Safe to re-run: all upserts use ON CONFLICT DO UPDATE, so repeated runs are
idempotent once the unique constraints are satisfied.
"""

from __future__ import annotations

import sys


def _get_connection():
    """Open a psycopg2 connection using the existing pool helper.

    Reads SUPABASE_DATABASE_URL only inside this function, never at import time.
    Raises RuntimeError with a clear message if the env var is missing.
    """
    try:
        from database.pool import _connect
        return _connect()
    except RuntimeError as exc:
        raise RuntimeError(
            "Cannot connect to database. "
            "Set SUPABASE_DATABASE_URL before running this script."
        ) from exc


def run_seed(conn) -> dict:
    """Build the modular curriculum export and seed it via the repository layer.

    Accepts an open psycopg2 connection; does not commit or close it —
    that is the caller's responsibility.

    Returns a dict with counts of rows upserted/linked:
        {"courses": int, "modules": int, "topics": int,
         "skills": int, "topic_skills": int, "activities": int}
    """
    from curriculum.modular_seed_export import build_modular_curriculum_seed_export
    from repositories.modular_curriculum_repository import (
        link_topic_skill,
        upsert_course,
        upsert_course_module,
        upsert_course_topic,
        upsert_skill,
        upsert_topic_activity,
    )

    export = build_modular_curriculum_seed_export()

    counts: dict[str, int] = {
        "courses":     0,
        "modules":     0,
        "topics":      0,
        "skills":      0,
        "topic_skills": 0,
        "activities":  0,
    }

    # ── Step 1: upsert courses ─────────────────────────────────────────────
    course_id_map: dict[str, int] = {}   # course_key -> course_id

    for course in export.courses:
        cid = upsert_course(
            conn,
            course_key=course.course_key,
            title=course.title,
            description=course.description,
            target_audience=course.target_audience,
            level=course.level,
            status=course.status,
            version=course.version,
            sequence_order=course.sequence_order,
            metadata=course.metadata,
        )
        if cid is not None:
            course_id_map[course.course_key] = cid
            counts["courses"] += 1

    # ── Step 2: upsert modules ─────────────────────────────────────────────
    module_id_map: dict[tuple[str, str], int] = {}  # (course_key, module_key) -> module_id

    for module in export.modules:
        course_id = course_id_map.get(module.course_key)
        if course_id is None:
            continue  # parent course was not upserted — skip
        mid = upsert_course_module(
            conn,
            course_id=course_id,
            module_key=module.module_key,
            title=module.title,
            description=module.description,
            sequence_order=module.sequence_order,
            estimated_minutes=module.estimated_minutes,
            status=module.status,
            metadata=module.metadata,
        )
        if mid is not None:
            module_id_map[(module.course_key, module.module_key)] = mid
            counts["modules"] += 1

    # ── Step 3: collect and upsert unique skills ───────────────────────────
    skill_id_map: dict[str, int] = {}   # skill_key -> skill_id (deduped)

    for topic in export.topics:
        for skill in topic.skills:
            if skill.skill_key in skill_id_map:
                continue  # already upserted this skill
            sid = upsert_skill(
                conn,
                skill_key=skill.skill_key,
                title=skill.title,
                description=skill.description,
                category=skill.category,
                level=skill.level,
            )
            if sid is not None:
                skill_id_map[skill.skill_key] = sid
                counts["skills"] += 1

    # ── Step 4: upsert topics, then link skills and upsert activities ──────
    for topic in export.topics:
        course_id = course_id_map.get(topic.course_key)
        if course_id is None:
            continue  # parent course was not upserted — skip

        # module_id may be None if module upsert failed; topic is still inserted
        module_id = module_id_map.get((topic.course_key, topic.module_key))

        tid = upsert_course_topic(
            conn,
            course_id=course_id,
            module_id=module_id,
            topic_key=topic.topic_key,
            title=topic.title,
            description=topic.description,
            legacy_topic_id=topic.legacy_topic_id,
            difficulty_level=topic.difficulty_level,
            sequence_order=topic.sequence_order,
            estimated_minutes=topic.estimated_minutes,
            status=topic.status,
            metadata=topic.metadata,
        )
        if tid is None:
            continue  # upsert returned no ID — skip child rows

        counts["topics"] += 1

        # Link inferred skills to this topic
        for skill in topic.skills:
            skill_id = skill_id_map.get(skill.skill_key)
            if skill_id is not None:
                link_topic_skill(conn, topic_id=tid, skill_id=skill_id, importance="core")
                counts["topic_skills"] += 1

        # Upsert default activities for this topic
        for act in topic.activities:
            aid = upsert_topic_activity(
                conn,
                topic_id=tid,
                activity_key=act.activity_key,
                activity_type=act.activity_type,
                title=act.title,
                instructions=act.instructions,
                rubric_key=act.rubric_key,
                sequence_order=act.sequence_order,
                is_required=act.is_required,
                metadata={},
            )
            if aid is not None:
                counts["activities"] += 1

    return counts


def main() -> None:
    """Entry point — connect, seed, commit, and report counts."""
    print("AI² Modular Curriculum Seed Script")
    print("Building modular curriculum export...")

    try:
        conn = _get_connection()
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        counts = run_seed(conn)
        conn.commit()
        print(f"  Courses          seeded : {counts['courses']}")
        print(f"  Modules          seeded : {counts['modules']}")
        print(f"  Topics           seeded : {counts['topics']}")
        print(f"  Skills           seeded : {counts['skills']}")
        print(f"  Topic-skills     linked : {counts['topic_skills']}")
        print(f"  Activities       seeded : {counts['activities']}")
        print("Done.")
    except Exception as exc:
        conn.rollback()
        print(f"ERROR: Seeding failed — {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
