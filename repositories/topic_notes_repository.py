"""Repository functions for the topic_notes DB table.

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


def upsert_topic_notes(
    conn,
    *,
    user_id: str | None,
    session_id: str | None,
    legacy_topic_id: str,
    notes: dict,
) -> None:
    """Insert or update a topic_notes row for (session_id, legacy_topic_id).

    NOTE: topic_notes has no UNIQUE constraint on (session_id, legacy_topic_id).
    We use SELECT-then-UPDATE/INSERT to avoid duplicate rows.
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT id FROM topic_notes"
            " WHERE session_id = %s AND legacy_topic_id = %s",
            (session_id, legacy_topic_id),
        )
        row = cur.fetchone()

    reflection       = notes.get("reflection") or None
    confusions       = notes.get("confusions") or None
    application_idea = notes.get("application_idea") or None
    metadata         = notes.get("metadata") or {}

    if row:
        sql = """
            UPDATE topic_notes
            SET reflection       = %s,
                confusions       = %s,
                application_idea = %s,
                metadata         = %s,
                updated_at       = NOW()
            WHERE session_id = %s AND legacy_topic_id = %s
        """
        with conn.cursor() as cur:
            cur.execute(sql, (
                reflection,
                confusions,
                application_idea,
                json.dumps(metadata),
                session_id,
                legacy_topic_id,
            ))
    else:
        sql = """
            INSERT INTO topic_notes
                (user_id, session_id, legacy_topic_id,
                 reflection, confusions, application_idea, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        with conn.cursor() as cur:
            cur.execute(sql, (
                user_id,
                session_id,
                legacy_topic_id,
                reflection,
                confusions,
                application_idea,
                json.dumps(metadata),
            ))


def get_topic_notes_by_legacy_id(
    conn,
    *,
    session_id: str,
    legacy_topic_id: str,
) -> dict | None:
    """Return a topic_notes row as a dict, or None if not found."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT * FROM topic_notes
            WHERE session_id = %s AND legacy_topic_id = %s
            LIMIT 1
            """,
            (session_id, legacy_topic_id),
        )
        row = cur.fetchone()
    return dict(row) if row else None
