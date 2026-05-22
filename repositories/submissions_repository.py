"""Repository functions for quiz_submissions, portfolio_submissions,
and interview_submissions DB tables.

All functions accept an open psycopg2 connection.  They do not open
connections themselves, read env vars, or mutate SessionContext.
The caller is responsible for commit/rollback (use get_conn from the pool module).

Uses legacy_topic_id (TEXT) for transition compatibility while SessionContext
string topic IDs remain the runtime source of truth.

Not wired into routes or services yet.
"""

from __future__ import annotations

import json

import psycopg2.extras


# ── Quiz submissions ──────────────────────────────────────────────────────────

def upsert_quiz_submission(
    conn,
    *,
    user_id: str | None,
    session_id: str | None,
    legacy_topic_id: str,
    submission: dict,
) -> None:
    """Insert or update a quiz_submissions row for (session_id, legacy_topic_id).

    NOTE: quiz_submissions has no UNIQUE constraint on (session_id, legacy_topic_id).
    We use SELECT-then-UPDATE/INSERT to avoid duplicate rows.
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT id FROM quiz_submissions"
            " WHERE session_id = %s AND legacy_topic_id = %s",
            (session_id, legacy_topic_id),
        )
        row = cur.fetchone()

    answers      = submission.get("answers", "")
    evaluation   = submission.get("evaluation") or None
    score        = submission.get("score") or None
    model        = submission.get("model") or None
    metadata     = submission.get("metadata") or {}
    submitted_at = submission.get("submitted_at") or None
    evaluated_at = submission.get("evaluated_at") or None

    if row:
        sql = """
            UPDATE quiz_submissions
            SET answers      = %s,
                evaluation   = %s,
                score        = %s,
                model        = %s,
                metadata     = %s,
                evaluated_at = %s,
                updated_at   = NOW()
            WHERE session_id = %s AND legacy_topic_id = %s
        """
        with conn.cursor() as cur:
            cur.execute(sql, (
                answers,
                evaluation,
                score,
                model,
                json.dumps(metadata),
                evaluated_at,
                session_id,
                legacy_topic_id,
            ))
    else:
        sql = """
            INSERT INTO quiz_submissions
                (user_id, session_id, legacy_topic_id,
                 answers, evaluation, score, model, metadata,
                 submitted_at, evaluated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s,
                    COALESCE(%s::timestamptz, NOW()), %s)
        """
        with conn.cursor() as cur:
            cur.execute(sql, (
                user_id,
                session_id,
                legacy_topic_id,
                answers,
                evaluation,
                score,
                model,
                json.dumps(metadata),
                submitted_at,
                evaluated_at,
            ))


def get_quiz_submission_by_legacy_id(
    conn,
    *,
    session_id: str,
    legacy_topic_id: str,
) -> dict | None:
    """Return the most recent quiz_submissions row as a dict, or None."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT * FROM quiz_submissions
            WHERE session_id = %s AND legacy_topic_id = %s
            ORDER BY submitted_at DESC
            LIMIT 1
            """,
            (session_id, legacy_topic_id),
        )
        row = cur.fetchone()
    return dict(row) if row else None


# ── Portfolio submissions ─────────────────────────────────────────────────────

def upsert_portfolio_submission(
    conn,
    *,
    user_id: str | None,
    session_id: str | None,
    legacy_topic_id: str,
    submission: dict,
) -> None:
    """Insert or update a portfolio_submissions row for (session_id, legacy_topic_id)."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT id FROM portfolio_submissions"
            " WHERE session_id = %s AND legacy_topic_id = %s",
            (session_id, legacy_topic_id),
        )
        row = cur.fetchone()

    submission_text = submission.get("submission", "")
    feedback        = submission.get("feedback") or None
    score           = submission.get("score") or None
    model           = submission.get("model") or None
    metadata        = submission.get("metadata") or {}
    submitted_at    = submission.get("submitted_at") or None
    reviewed_at     = submission.get("reviewed_at") or None

    if row:
        sql = """
            UPDATE portfolio_submissions
            SET submission  = %s,
                feedback    = %s,
                score       = %s,
                model       = %s,
                metadata    = %s,
                reviewed_at = %s,
                updated_at  = NOW()
            WHERE session_id = %s AND legacy_topic_id = %s
        """
        with conn.cursor() as cur:
            cur.execute(sql, (
                submission_text,
                feedback,
                score,
                model,
                json.dumps(metadata),
                reviewed_at,
                session_id,
                legacy_topic_id,
            ))
    else:
        sql = """
            INSERT INTO portfolio_submissions
                (user_id, session_id, legacy_topic_id,
                 submission, feedback, score, model, metadata,
                 submitted_at, reviewed_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s,
                    COALESCE(%s::timestamptz, NOW()), %s)
        """
        with conn.cursor() as cur:
            cur.execute(sql, (
                user_id,
                session_id,
                legacy_topic_id,
                submission_text,
                feedback,
                score,
                model,
                json.dumps(metadata),
                submitted_at,
                reviewed_at,
            ))


def get_portfolio_submission_by_legacy_id(
    conn,
    *,
    session_id: str,
    legacy_topic_id: str,
) -> dict | None:
    """Return the most recent portfolio_submissions row as a dict, or None."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT * FROM portfolio_submissions
            WHERE session_id = %s AND legacy_topic_id = %s
            ORDER BY submitted_at DESC
            LIMIT 1
            """,
            (session_id, legacy_topic_id),
        )
        row = cur.fetchone()
    return dict(row) if row else None


# ── Interview submissions ─────────────────────────────────────────────────────

def upsert_interview_submission(
    conn,
    *,
    user_id: str | None,
    session_id: str | None,
    legacy_topic_id: str,
    submission: dict,
) -> None:
    """Insert or update an interview_submissions row for (session_id, legacy_topic_id)."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT id FROM interview_submissions"
            " WHERE session_id = %s AND legacy_topic_id = %s",
            (session_id, legacy_topic_id),
        )
        row = cur.fetchone()

    answer      = submission.get("answer", "")
    feedback    = submission.get("feedback") or None
    score       = submission.get("score") or None
    model       = submission.get("model") or None
    metadata    = submission.get("metadata") or {}
    submitted_at = submission.get("submitted_at") or None
    reviewed_at  = submission.get("reviewed_at") or None

    if row:
        sql = """
            UPDATE interview_submissions
            SET answer      = %s,
                feedback    = %s,
                score       = %s,
                model       = %s,
                metadata    = %s,
                reviewed_at = %s,
                updated_at  = NOW()
            WHERE session_id = %s AND legacy_topic_id = %s
        """
        with conn.cursor() as cur:
            cur.execute(sql, (
                answer,
                feedback,
                score,
                model,
                json.dumps(metadata),
                reviewed_at,
                session_id,
                legacy_topic_id,
            ))
    else:
        sql = """
            INSERT INTO interview_submissions
                (user_id, session_id, legacy_topic_id,
                 answer, feedback, score, model, metadata,
                 submitted_at, reviewed_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s,
                    COALESCE(%s::timestamptz, NOW()), %s)
        """
        with conn.cursor() as cur:
            cur.execute(sql, (
                user_id,
                session_id,
                legacy_topic_id,
                answer,
                feedback,
                score,
                model,
                json.dumps(metadata),
                submitted_at,
                reviewed_at,
            ))


def get_interview_submission_by_legacy_id(
    conn,
    *,
    session_id: str,
    legacy_topic_id: str,
) -> dict | None:
    """Return the most recent interview_submissions row as a dict, or None."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT * FROM interview_submissions
            WHERE session_id = %s AND legacy_topic_id = %s
            ORDER BY submitted_at DESC
            LIMIT 1
            """,
            (session_id, legacy_topic_id),
        )
        row = cur.fetchone()
    return dict(row) if row else None
