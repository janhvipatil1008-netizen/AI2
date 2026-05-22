"""Repository functions for private beta feedback storage."""

from __future__ import annotations

import json


def insert_beta_feedback(
    conn,
    *,
    user_id: str | None,
    session_id: str,
    legacy_topic_id: str | None,
    feedback_context: str,
    usefulness_score: int | None,
    clarity_score: int | None,
    confusion: str | None,
    improvement_suggestion: str | None,
    willingness_to_pay: str | None,
    metadata: dict | None = None,
) -> None:
    """Insert one beta feedback row using an existing DB connection."""
    sql = """
        INSERT INTO beta_feedback
            (user_id, session_id, legacy_topic_id, feedback_context,
             usefulness_score, clarity_score, confusion,
             improvement_suggestion, willingness_to_pay, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    with conn.cursor() as cur:
        cur.execute(sql, (
            user_id,
            session_id,
            legacy_topic_id,
            feedback_context,
            usefulness_score,
            clarity_score,
            confusion,
            improvement_suggestion,
            willingness_to_pay,
            json.dumps(metadata or {}),
        ))
