"""Repository functions for the learning_outcomes DB table.

All functions accept an open psycopg2 connection. They do not open connections
themselves, read env vars, mutate SessionContext, or manage transactions.

This is foundation storage only and is not wired into learner-facing routes.
"""

from __future__ import annotations

import json

import psycopg2.extras

from services.learning_outcome_service import (
    calculate_improvement_delta,
    classify_learning_outcome,
)


def upsert_baseline_outcome(
    conn,
    *,
    user_id: str | None,
    session_id: str,
    legacy_topic_id: str,
    baseline_prompt: str | None,
    baseline_answer: str | None,
    baseline_score: int | None,
    metadata: dict | None = None,
) -> None:
    """Insert or update baseline learning outcome data."""
    sql = """
        INSERT INTO learning_outcomes
            (user_id, session_id, legacy_topic_id,
             baseline_prompt, baseline_answer, baseline_score,
             status, metadata, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, 'baseline_completed', %s, NOW())
        ON CONFLICT (session_id, legacy_topic_id) DO UPDATE
        SET user_id          = EXCLUDED.user_id,
            baseline_prompt  = EXCLUDED.baseline_prompt,
            baseline_answer  = EXCLUDED.baseline_answer,
            baseline_score   = EXCLUDED.baseline_score,
            status           = 'baseline_completed',
            metadata         = learning_outcomes.metadata || EXCLUDED.metadata,
            updated_at       = NOW()
    """
    with conn.cursor() as cur:
        cur.execute(sql, (
            user_id,
            session_id,
            legacy_topic_id,
            baseline_prompt,
            baseline_answer,
            baseline_score,
            json.dumps(metadata or {}),
        ))


def upsert_post_outcome(
    conn,
    *,
    user_id: str | None,
    session_id: str,
    legacy_topic_id: str,
    post_prompt: str | None,
    post_answer: str | None,
    post_score: int | None,
    metadata: dict | None = None,
) -> None:
    """Insert or update post-topic learning outcome data."""
    baseline_score = _baseline_score_for_outcome(
        conn,
        session_id=session_id,
        legacy_topic_id=legacy_topic_id,
    )
    improvement_delta = calculate_improvement_delta(baseline_score, post_score)
    status = classify_learning_outcome(improvement_delta)

    sql = """
        INSERT INTO learning_outcomes
            (user_id, session_id, legacy_topic_id,
             post_prompt, post_answer, post_score,
             improvement_delta, status, metadata, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (session_id, legacy_topic_id) DO UPDATE
        SET user_id            = EXCLUDED.user_id,
            post_prompt        = EXCLUDED.post_prompt,
            post_answer        = EXCLUDED.post_answer,
            post_score         = EXCLUDED.post_score,
            improvement_delta  = CASE
                WHEN learning_outcomes.baseline_score IS NOT NULL
                 AND EXCLUDED.post_score IS NOT NULL
                THEN EXCLUDED.post_score - learning_outcomes.baseline_score
                ELSE EXCLUDED.improvement_delta
            END,
            status             = CASE
                WHEN learning_outcomes.baseline_score IS NOT NULL
                 AND EXCLUDED.post_score IS NOT NULL
                 AND EXCLUDED.post_score - learning_outcomes.baseline_score < 0
                THEN 'needs_review'
                WHEN learning_outcomes.baseline_score IS NOT NULL
                 AND EXCLUDED.post_score IS NOT NULL
                THEN 'improved'
                ELSE EXCLUDED.status
            END,
            metadata           = learning_outcomes.metadata || EXCLUDED.metadata,
            updated_at         = NOW()
    """
    with conn.cursor() as cur:
        cur.execute(sql, (
            user_id,
            session_id,
            legacy_topic_id,
            post_prompt,
            post_answer,
            post_score,
            improvement_delta,
            status,
            json.dumps(metadata or {}),
        ))


def get_learning_outcome(
    conn,
    *,
    session_id: str,
    legacy_topic_id: str,
) -> dict | None:
    """Return one learning_outcomes row for a session/topic, or None."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT *
            FROM learning_outcomes
            WHERE session_id = %s AND legacy_topic_id = %s
            LIMIT 1
            """,
            (session_id, legacy_topic_id),
        )
        row = cur.fetchone()
    return dict(row) if row else None


def list_learning_outcomes_for_session(
    conn,
    *,
    session_id: str,
) -> list[dict]:
    """Return all learning outcome rows for a session."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT *
            FROM learning_outcomes
            WHERE session_id = %s
            ORDER BY updated_at DESC, created_at DESC
            """,
            (session_id,),
        )
        rows = cur.fetchall()
    return [dict(row) for row in rows]


def _baseline_score_for_outcome(
    conn,
    *,
    session_id: str,
    legacy_topic_id: str,
) -> int | None:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT baseline_score
            FROM learning_outcomes
            WHERE session_id = %s AND legacy_topic_id = %s
            LIMIT 1
            """,
            (session_id, legacy_topic_id),
        )
        row = cur.fetchone()
    if not row:
        return None
    if isinstance(row, dict):
        return row.get("baseline_score")
    return row[0]
