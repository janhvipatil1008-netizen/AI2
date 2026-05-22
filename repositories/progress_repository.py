"""Repository functions for topic_progress DB table.

All functions accept an open psycopg2 connection.  They do not open
connections themselves, read env vars, or mutate SessionContext.

Uses legacy_topic_id (TEXT) for transition compatibility while SessionContext
string topic IDs remain the runtime source of truth.

Not wired into routes or services yet.
"""

from __future__ import annotations

import json

import psycopg2.extras


def upsert_topic_progress(
    conn,
    *,
    user_id: str | None,
    session_id: str | None,
    legacy_topic_id: str,
    progress: dict,
    completion_percent: int,
) -> None:
    """Insert or update a topic_progress row for (session_id, legacy_topic_id).

    NOTE: topic_progress has no UNIQUE constraint on (session_id, legacy_topic_id),
    only a regular index.  We therefore do a SELECT-then-UPDATE/INSERT to avoid
    duplicate rows.  A future migration can add the constraint and switch to
    ON CONFLICT once the data is clean.
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT id FROM topic_progress WHERE session_id = %s AND legacy_topic_id = %s",
            (session_id, legacy_topic_id),
        )
        row = cur.fetchone()

    if row:
        sql = """
            UPDATE topic_progress
            SET learn_status              = %s,
                quiz_status               = %s,
                portfolio_task_status     = %s,
                interview_practice_status = %s,
                reflection_status         = %s,
                completion_percent        = %s,
                last_activity_at          = NOW(),
                updated_at                = NOW()
            WHERE session_id = %s AND legacy_topic_id = %s
        """
        with conn.cursor() as cur:
            cur.execute(sql, (
                progress.get("learn",               "not_started"),
                progress.get("quiz",                "not_started"),
                progress.get("portfolio_task",      "not_started"),
                progress.get("interview_practice",  "not_started"),
                progress.get("reflection",          "not_started"),
                completion_percent,
                session_id,
                legacy_topic_id,
            ))
    else:
        sql = """
            INSERT INTO topic_progress
                (user_id, session_id, legacy_topic_id,
                 learn_status, quiz_status, portfolio_task_status,
                 interview_practice_status, reflection_status,
                 completion_percent, last_activity_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """
        with conn.cursor() as cur:
            cur.execute(sql, (
                user_id,
                session_id,
                legacy_topic_id,
                progress.get("learn",               "not_started"),
                progress.get("quiz",                "not_started"),
                progress.get("portfolio_task",      "not_started"),
                progress.get("interview_practice",  "not_started"),
                progress.get("reflection",          "not_started"),
                completion_percent,
            ))


def get_topic_progress_by_legacy_id(
    conn,
    *,
    session_id: str,
    legacy_topic_id: str,
) -> dict | None:
    """Return a topic_progress row as a dict, or None if not found."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT * FROM topic_progress
            WHERE session_id = %s AND legacy_topic_id = %s
            LIMIT 1
            """,
            (session_id, legacy_topic_id),
        )
        row = cur.fetchone()
    return dict(row) if row else None
