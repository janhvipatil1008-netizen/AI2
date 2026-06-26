"""Repository helpers for the modular curriculum schema.

Covers: courses, course_modules, skills, course_topics, topic_skills,
topic_activities.

Rules:
- Accept an injected conn only; never create connections.
- Never commit or rollback — the caller owns the transaction.
- Use parameterized SQL (%s placeholders) only.
- No env-var reads, no database.pool imports, no route/service imports.
"""

from __future__ import annotations

import json


# ── Write / upsert helpers ────────────────────────────────────────────────────

def upsert_course(
    conn,
    *,
    course_key: str,
    title: str,
    description: str | None = None,
    target_audience: str | None = None,
    level: str = "beginner",
    status: str = "draft",
    version: str = "v1",
    sequence_order: int = 0,
    metadata: dict | None = None,
) -> int | None:
    meta = json.dumps(metadata or {})
    sql = """
        INSERT INTO courses
            (course_key, title, description, target_audience, level, status,
             version, sequence_order, metadata, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (course_key) DO UPDATE SET
            title           = EXCLUDED.title,
            description     = EXCLUDED.description,
            target_audience = EXCLUDED.target_audience,
            level           = EXCLUDED.level,
            status          = EXCLUDED.status,
            version         = EXCLUDED.version,
            sequence_order  = EXCLUDED.sequence_order,
            metadata        = EXCLUDED.metadata,
            updated_at      = NOW()
        RETURNING course_id
    """
    with conn.cursor() as cur:
        cur.execute(sql, (
            course_key, title, description, target_audience,
            level, status, version, sequence_order, meta,
        ))
        row = cur.fetchone()
        return row[0] if row else None


def upsert_course_module(
    conn,
    *,
    course_id: int,
    module_key: str,
    title: str,
    description: str | None = None,
    sequence_order: int = 0,
    estimated_minutes: int | None = None,
    status: str = "active",
    metadata: dict | None = None,
) -> int | None:
    meta = json.dumps(metadata or {})
    sql = """
        INSERT INTO course_modules
            (course_id, module_key, title, description, sequence_order,
             estimated_minutes, status, metadata, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (course_id, module_key) DO UPDATE SET
            title             = EXCLUDED.title,
            description       = EXCLUDED.description,
            sequence_order    = EXCLUDED.sequence_order,
            estimated_minutes = EXCLUDED.estimated_minutes,
            status            = EXCLUDED.status,
            metadata          = EXCLUDED.metadata,
            updated_at        = NOW()
        RETURNING module_id
    """
    with conn.cursor() as cur:
        cur.execute(sql, (
            course_id, module_key, title, description,
            sequence_order, estimated_minutes, status, meta,
        ))
        row = cur.fetchone()
        return row[0] if row else None


def upsert_skill(
    conn,
    *,
    skill_key: str,
    title: str,
    description: str | None = None,
    category: str | None = None,
    level: str | None = None,
    metadata: dict | None = None,
) -> int | None:
    meta = json.dumps(metadata or {})
    sql = """
        INSERT INTO skills
            (skill_key, title, description, category, level, metadata, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (skill_key) DO UPDATE SET
            title       = EXCLUDED.title,
            description = EXCLUDED.description,
            category    = EXCLUDED.category,
            level       = EXCLUDED.level,
            metadata    = EXCLUDED.metadata,
            updated_at  = NOW()
        RETURNING skill_id
    """
    with conn.cursor() as cur:
        cur.execute(sql, (skill_key, title, description, category, level, meta))
        row = cur.fetchone()
        return row[0] if row else None


def upsert_course_topic(
    conn,
    *,
    course_id: int,
    module_id: int | None,
    topic_key: str,
    title: str,
    description: str | None = None,
    legacy_topic_id: str | None = None,
    difficulty_level: str = "beginner",
    sequence_order: int = 0,
    estimated_minutes: int | None = None,
    status: str = "active",
    metadata: dict | None = None,
) -> int | None:
    meta = json.dumps(metadata or {})
    sql = """
        INSERT INTO course_topics
            (course_id, module_id, legacy_topic_id, topic_key, title, description,
             difficulty_level, sequence_order, estimated_minutes, status,
             metadata, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (course_id, topic_key) DO UPDATE SET
            module_id         = EXCLUDED.module_id,
            legacy_topic_id   = EXCLUDED.legacy_topic_id,
            title             = EXCLUDED.title,
            description       = EXCLUDED.description,
            difficulty_level  = EXCLUDED.difficulty_level,
            sequence_order    = EXCLUDED.sequence_order,
            estimated_minutes = EXCLUDED.estimated_minutes,
            status            = EXCLUDED.status,
            metadata          = EXCLUDED.metadata,
            updated_at        = NOW()
        RETURNING topic_id
    """
    with conn.cursor() as cur:
        cur.execute(sql, (
            course_id, module_id, legacy_topic_id, topic_key, title, description,
            difficulty_level, sequence_order, estimated_minutes, status, meta,
        ))
        row = cur.fetchone()
        return row[0] if row else None


def link_topic_skill(
    conn,
    *,
    topic_id: int,
    skill_id: int,
    importance: str = "core",
) -> None:
    sql = """
        INSERT INTO topic_skills (topic_id, skill_id, importance)
        VALUES (%s, %s, %s)
        ON CONFLICT (topic_id, skill_id) DO UPDATE SET
            importance = EXCLUDED.importance
    """
    with conn.cursor() as cur:
        cur.execute(sql, (topic_id, skill_id, importance))


def upsert_topic_activity(
    conn,
    *,
    topic_id: int,
    activity_key: str,
    activity_type: str,
    title: str | None = None,
    instructions: str | None = None,
    rubric_key: str | None = None,
    sequence_order: int = 0,
    is_required: bool = True,
    metadata: dict | None = None,
) -> int | None:
    meta = json.dumps(metadata or {})
    sql = """
        INSERT INTO topic_activities
            (topic_id, activity_key, activity_type, title, instructions,
             rubric_key, sequence_order, is_required, metadata, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (topic_id, activity_key) DO UPDATE SET
            activity_type  = EXCLUDED.activity_type,
            title          = EXCLUDED.title,
            instructions   = EXCLUDED.instructions,
            rubric_key     = EXCLUDED.rubric_key,
            sequence_order = EXCLUDED.sequence_order,
            is_required    = EXCLUDED.is_required,
            metadata       = EXCLUDED.metadata,
            updated_at     = NOW()
        RETURNING activity_id
    """
    with conn.cursor() as cur:
        cur.execute(sql, (
            topic_id, activity_key, activity_type, title, instructions,
            rubric_key, sequence_order, is_required, meta,
        ))
        row = cur.fetchone()
        return row[0] if row else None


# ── Read helpers ──────────────────────────────────────────────────────────────

def get_course_by_key(conn, *, course_key: str) -> dict | None:
    sql = """
        SELECT course_id, course_key, title, description, target_audience,
               level, status, version, sequence_order, metadata,
               created_at, updated_at
        FROM courses
        WHERE course_key = %s
    """
    with conn.cursor() as cur:
        cur.execute(sql, (course_key,))
        row = cur.fetchone()
        if row is None:
            return None
        cols = [d[0] for d in cur.description]
        return dict(zip(cols, row))


def list_courses(conn, *, status: str | None = "active") -> list[dict]:
    if status is not None:
        sql = """
            SELECT course_id, course_key, title, description, target_audience,
                   level, status, version, sequence_order, metadata,
                   created_at, updated_at
            FROM courses
            WHERE status = %s
            ORDER BY sequence_order, course_id
        """
        params: tuple = (status,)
    else:
        sql = """
            SELECT course_id, course_key, title, description, target_audience,
                   level, status, version, sequence_order, metadata,
                   created_at, updated_at
            FROM courses
            ORDER BY sequence_order, course_id
        """
        params = ()
    with conn.cursor() as cur:
        cur.execute(sql, params)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def list_modules_for_course(conn, *, course_id: int) -> list[dict]:
    sql = """
        SELECT module_id, course_id, module_key, title, description,
               sequence_order, estimated_minutes, status, metadata,
               created_at, updated_at
        FROM course_modules
        WHERE course_id = %s
        ORDER BY sequence_order, module_id
    """
    with conn.cursor() as cur:
        cur.execute(sql, (course_id,))
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def list_topics_for_course(conn, *, course_id: int) -> list[dict]:
    sql = """
        SELECT topic_id, course_id, module_id, legacy_topic_id, topic_key,
               title, description, difficulty_level, sequence_order,
               estimated_minutes, status, metadata, created_at, updated_at
        FROM course_topics
        WHERE course_id = %s
        ORDER BY sequence_order, topic_id
    """
    with conn.cursor() as cur:
        cur.execute(sql, (course_id,))
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def list_topics_for_module(conn, *, module_id: int) -> list[dict]:
    sql = """
        SELECT topic_id, course_id, module_id, legacy_topic_id, topic_key,
               title, description, difficulty_level, sequence_order,
               estimated_minutes, status, metadata, created_at, updated_at
        FROM course_topics
        WHERE module_id = %s
        ORDER BY sequence_order, topic_id
    """
    with conn.cursor() as cur:
        cur.execute(sql, (module_id,))
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def get_topic_by_legacy_id(conn, *, legacy_topic_id: str) -> dict | None:
    sql = """
        SELECT topic_id, course_id, module_id, legacy_topic_id, topic_key,
               title, description, difficulty_level, sequence_order,
               estimated_minutes, status, metadata, created_at, updated_at
        FROM course_topics
        WHERE legacy_topic_id = %s
        LIMIT 1
    """
    with conn.cursor() as cur:
        cur.execute(sql, (legacy_topic_id,))
        row = cur.fetchone()
        if row is None:
            return None
        cols = [d[0] for d in cur.description]
        return dict(zip(cols, row))


def get_topic_by_topic_key(conn, *, topic_key: str) -> dict | None:
    sql = """
        SELECT topic_id, course_id, module_id, legacy_topic_id, topic_key,
               title, description, difficulty_level, sequence_order,
               estimated_minutes, status, metadata, created_at, updated_at
        FROM course_topics
        WHERE topic_key = %s
        LIMIT 1
    """
    with conn.cursor() as cur:
        cur.execute(sql, (topic_key,))
        row = cur.fetchone()
        if row is None:
            return None
        cols = [d[0] for d in cur.description]
        return dict(zip(cols, row))


def list_activities_for_topic(conn, *, topic_id: int) -> list[dict]:
    sql = """
        SELECT activity_id, topic_id, activity_key, activity_type, title,
               instructions, rubric_key, sequence_order, is_required,
               metadata, created_at, updated_at
        FROM topic_activities
        WHERE topic_id = %s
        ORDER BY sequence_order, activity_id
    """
    with conn.cursor() as cur:
        cur.execute(sql, (topic_id,))
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def list_skills_for_topic(conn, *, topic_id: int) -> list[dict]:
    sql = """
        SELECT s.skill_id, s.skill_key, s.title, s.description,
               s.category, s.level, ts.importance
        FROM topic_skills ts
        JOIN skills s ON s.skill_id = ts.skill_id
        WHERE ts.topic_id = %s
        ORDER BY s.skill_key
    """
    with conn.cursor() as cur:
        cur.execute(sql, (topic_id,))
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
