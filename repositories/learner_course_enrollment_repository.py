"""Repository helpers for learner course enrollments and modular progress."""

from __future__ import annotations

import json


def _metadata_json(metadata: dict | None) -> str:
    return json.dumps(metadata or {})


def _row_to_dict(cur, row) -> dict | None:
    if row is None:
        return None
    if isinstance(row, dict):
        return dict(row)
    cols = [desc[0] for desc in cur.description]
    return dict(zip(cols, row))


def _rows_to_dicts(cur, rows) -> list[dict]:
    return [_row_to_dict(cur, row) for row in rows]


def _row_id(row, key: str) -> int | None:
    if not row:
        return None
    if isinstance(row, dict):
        return row.get(key)
    return row[0]


def upsert_course_enrollment(
    conn,
    *,
    user_id: str,
    session_id: str,
    course_key: str,
    course_id: int | None = None,
    status: str = "active",
    current_module_id: int | None = None,
    current_module_key: str | None = None,
    current_topic_id: int | None = None,
    current_topic_key: str | None = None,
    current_legacy_topic_id: str | None = None,
    progress_percent: int = 0,
    metadata: dict | None = None,
) -> int | None:
    sql = """
        INSERT INTO learner_course_enrollments
            (user_id, session_id, course_id, course_key, status,
             current_module_id, current_module_key, current_topic_id,
             current_topic_key, current_legacy_topic_id, progress_percent,
             metadata, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT(user_id, session_id, course_key) DO UPDATE SET
            course_id                = EXCLUDED.course_id,
            status                   = EXCLUDED.status,
            current_module_id        = EXCLUDED.current_module_id,
            current_module_key       = EXCLUDED.current_module_key,
            current_topic_id         = EXCLUDED.current_topic_id,
            current_topic_key        = EXCLUDED.current_topic_key,
            current_legacy_topic_id  = EXCLUDED.current_legacy_topic_id,
            progress_percent         = EXCLUDED.progress_percent,
            metadata                 = EXCLUDED.metadata,
            updated_at               = NOW()
        RETURNING enrollment_id
    """
    params = (
        user_id,
        session_id,
        course_id,
        course_key,
        status,
        current_module_id,
        current_module_key,
        current_topic_id,
        current_topic_key,
        current_legacy_topic_id,
        progress_percent,
        _metadata_json(metadata),
    )
    with conn.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
        return _row_id(row, "enrollment_id")


def get_active_enrollment(
    conn,
    *,
    user_id: str,
    session_id: str,
    course_key: str | None = None,
) -> dict | None:
    if course_key is None:
        sql = """
            SELECT enrollment_id, user_id, session_id, course_id, course_key,
                   status, started_at, completed_at, current_module_id,
                   current_module_key, current_topic_id, current_topic_key,
                   current_legacy_topic_id, progress_percent, metadata,
                   created_at, updated_at
            FROM learner_course_enrollments
            WHERE user_id = %s
              AND session_id = %s
              AND status = %s
            ORDER BY updated_at DESC, created_at DESC
            LIMIT 1
        """
        params = (user_id, session_id, "active")
    else:
        sql = """
            SELECT enrollment_id, user_id, session_id, course_id, course_key,
                   status, started_at, completed_at, current_module_id,
                   current_module_key, current_topic_id, current_topic_key,
                   current_legacy_topic_id, progress_percent, metadata,
                   created_at, updated_at
            FROM learner_course_enrollments
            WHERE user_id = %s
              AND session_id = %s
              AND course_key = %s
              AND status = %s
            ORDER BY updated_at DESC, created_at DESC
            LIMIT 1
        """
        params = (user_id, session_id, course_key, "active")
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return _row_to_dict(cur, cur.fetchone())


def list_enrollments_for_session(
    conn,
    *,
    user_id: str,
    session_id: str,
) -> list[dict]:
    sql = """
        SELECT enrollment_id, user_id, session_id, course_id, course_key,
               status, started_at, completed_at, current_module_id,
               current_module_key, current_topic_id, current_topic_key,
               current_legacy_topic_id, progress_percent, metadata,
               created_at, updated_at
        FROM learner_course_enrollments
        WHERE user_id = %s
          AND session_id = %s
        ORDER BY CASE WHEN status = %s THEN 0 ELSE 1 END, updated_at DESC
    """
    with conn.cursor() as cur:
        cur.execute(sql, (user_id, session_id, "active"))
        return _rows_to_dicts(cur, cur.fetchall())


def update_current_position(
    conn,
    *,
    enrollment_id: int,
    current_module_id: int | None = None,
    current_module_key: str | None = None,
    current_topic_id: int | None = None,
    current_topic_key: str | None = None,
    current_legacy_topic_id: str | None = None,
    progress_percent: int | None = None,
) -> None:
    fields = [
        ("current_module_id", current_module_id),
        ("current_module_key", current_module_key),
        ("current_topic_id", current_topic_id),
        ("current_topic_key", current_topic_key),
        ("current_legacy_topic_id", current_legacy_topic_id),
        ("progress_percent", progress_percent),
    ]
    assignments = [name + " = %s" for name, value in fields if value is not None]
    params = tuple(value for _, value in fields if value is not None)

    if not assignments:
        return

    sql = """
        UPDATE learner_course_enrollments
        SET __ASSIGNMENTS__,
            updated_at = NOW()
        WHERE enrollment_id = %s
    """.replace("__ASSIGNMENTS__", ",\n            ".join(assignments))
    with conn.cursor() as cur:
        cur.execute(sql, (*params, enrollment_id))


def upsert_module_progress(
    conn,
    *,
    enrollment_id: int,
    module_key: str,
    module_id: int | None = None,
    status: str = "not_started",
    completed_topics: int = 0,
    total_topics: int = 0,
    progress_percent: int = 0,
    metadata: dict | None = None,
) -> int | None:
    sql = """
        INSERT INTO learner_module_progress
            (enrollment_id, module_id, module_key, status, completed_topics,
             total_topics, progress_percent, metadata, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT(enrollment_id, module_key) DO UPDATE SET
            module_id        = EXCLUDED.module_id,
            status           = EXCLUDED.status,
            completed_topics = EXCLUDED.completed_topics,
            total_topics     = EXCLUDED.total_topics,
            progress_percent = EXCLUDED.progress_percent,
            metadata         = EXCLUDED.metadata,
            updated_at       = NOW()
        RETURNING module_progress_id
    """
    params = (
        enrollment_id,
        module_id,
        module_key,
        status,
        completed_topics,
        total_topics,
        progress_percent,
        _metadata_json(metadata),
    )
    with conn.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
        return _row_id(row, "module_progress_id")


def upsert_topic_progress(
    conn,
    *,
    enrollment_id: int,
    topic_key: str,
    module_key: str | None = None,
    topic_id: int | None = None,
    legacy_topic_id: str | None = None,
    status: str = "not_started",
    completion_percent: int = 0,
    required_activities_completed: int = 0,
    required_activities_total: int = 0,
    metadata: dict | None = None,
) -> int | None:
    sql = """
        INSERT INTO learner_topic_progress
            (enrollment_id, module_key, topic_id, topic_key, legacy_topic_id,
             status, completion_percent, required_activities_completed,
             required_activities_total, metadata, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT(enrollment_id, topic_key) DO UPDATE SET
            module_key                    = EXCLUDED.module_key,
            topic_id                      = EXCLUDED.topic_id,
            legacy_topic_id               = EXCLUDED.legacy_topic_id,
            status                        = EXCLUDED.status,
            completion_percent            = EXCLUDED.completion_percent,
            required_activities_completed = EXCLUDED.required_activities_completed,
            required_activities_total     = EXCLUDED.required_activities_total,
            metadata                      = EXCLUDED.metadata,
            updated_at                    = NOW()
        RETURNING topic_progress_id
    """
    params = (
        enrollment_id,
        module_key,
        topic_id,
        topic_key,
        legacy_topic_id,
        status,
        completion_percent,
        required_activities_completed,
        required_activities_total,
        _metadata_json(metadata),
    )
    with conn.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
        return _row_id(row, "topic_progress_id")


def list_module_progress(conn, *, enrollment_id: int) -> list[dict]:
    sql = """
        SELECT module_progress_id, enrollment_id, module_id, module_key,
               status, completed_topics, total_topics, progress_percent,
               started_at, completed_at, metadata, created_at, updated_at
        FROM learner_module_progress
        WHERE enrollment_id = %s
        ORDER BY module_key
    """
    with conn.cursor() as cur:
        cur.execute(sql, (enrollment_id,))
        return _rows_to_dicts(cur, cur.fetchall())


def list_topic_progress(conn, *, enrollment_id: int) -> list[dict]:
    sql = """
        SELECT topic_progress_id, enrollment_id, module_key, topic_id,
               topic_key, legacy_topic_id, status, completion_percent,
               required_activities_completed, required_activities_total,
               started_at, completed_at, metadata, created_at, updated_at
        FROM learner_topic_progress
        WHERE enrollment_id = %s
        ORDER BY module_key, topic_key
    """
    with conn.cursor() as cur:
        cur.execute(sql, (enrollment_id,))
        return _rows_to_dicts(cur, cur.fetchall())


def get_topic_progress_by_legacy_id(
    conn,
    *,
    enrollment_id: int,
    legacy_topic_id: str,
) -> dict | None:
    sql = """
        SELECT topic_progress_id, enrollment_id, module_key, topic_id,
               topic_key, legacy_topic_id, status, completion_percent,
               required_activities_completed, required_activities_total,
               started_at, completed_at, metadata, created_at, updated_at
        FROM learner_topic_progress
        WHERE enrollment_id = %s
          AND legacy_topic_id = %s
        LIMIT 1
    """
    with conn.cursor() as cur:
        cur.execute(sql, (enrollment_id, legacy_topic_id))
        return _row_to_dict(cur, cur.fetchone())
