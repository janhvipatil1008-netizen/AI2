"""Repository functions for generated_topic_content and generated_topic_practice tables.

All functions accept an open psycopg2 connection.  They do not open
connections themselves, read env vars, or mutate SessionContext.
The caller is responsible for commit/rollback (use get_conn from the pool module).

Not wired into routes or services yet.
"""

from __future__ import annotations

import json

import psycopg2.extras


def upsert_generated_topic_content(
    conn,
    *,
    user_id: str | None,
    session_id: str | None,
    legacy_topic_id: str,
    content_record: dict,
) -> None:
    """Insert or update a generated_topic_content row for (session_id, legacy_topic_id).

    NOTE: generated_topic_content has no UNIQUE constraint on (session_id, legacy_topic_id).
    We use SELECT-then-UPDATE/INSERT to avoid duplicate rows.
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT id FROM generated_topic_content"
            " WHERE session_id = %s AND legacy_topic_id = %s",
            (session_id, legacy_topic_id),
        )
        row = cur.fetchone()

    content         = content_record.get("content", "")
    model           = content_record.get("model") or None
    version         = content_record.get("version", "v1")
    freshness_label = content_record.get("freshness_label") or None
    source          = content_record.get("source", "claude")
    metadata        = content_record.get("metadata") or {}
    generated_at    = content_record.get("generated_at") or None

    if row:
        sql = """
            UPDATE generated_topic_content
            SET content         = %s,
                model           = %s,
                version         = %s,
                freshness_label = %s,
                source          = %s,
                metadata        = %s,
                updated_at      = NOW()
            WHERE session_id = %s AND legacy_topic_id = %s
        """
        with conn.cursor() as cur:
            cur.execute(sql, (
                content,
                model,
                version,
                freshness_label,
                source,
                json.dumps(metadata),
                session_id,
                legacy_topic_id,
            ))
    else:
        sql = """
            INSERT INTO generated_topic_content
                (user_id, session_id, legacy_topic_id,
                 content, model, version, freshness_label, source, metadata,
                 generated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s,
                    COALESCE(%s::timestamptz, NOW()))
        """
        with conn.cursor() as cur:
            cur.execute(sql, (
                user_id,
                session_id,
                legacy_topic_id,
                content,
                model,
                version,
                freshness_label,
                source,
                json.dumps(metadata),
                generated_at,
            ))


def get_generated_topic_content_by_legacy_id(
    conn,
    *,
    session_id: str,
    legacy_topic_id: str,
) -> dict | None:
    """Return the most recent generated_topic_content row as a dict, or None."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT * FROM generated_topic_content
            WHERE session_id = %s AND legacy_topic_id = %s
            ORDER BY generated_at DESC
            LIMIT 1
            """,
            (session_id, legacy_topic_id),
        )
        row = cur.fetchone()
    return dict(row) if row else None


def upsert_generated_topic_practice(
    conn,
    *,
    user_id: str | None,
    session_id: str | None,
    legacy_topic_id: str,
    practice_type: str,
    practice_record: dict,
) -> None:
    """Insert or update a generated_topic_practice row for
    (session_id, legacy_topic_id, practice_type).
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT id FROM generated_topic_practice"
            " WHERE session_id = %s AND legacy_topic_id = %s AND practice_type = %s",
            (session_id, legacy_topic_id, practice_type),
        )
        row = cur.fetchone()

    content         = practice_record.get("content", "")
    model           = practice_record.get("model") or None
    version         = practice_record.get("version", "v1")
    freshness_label = practice_record.get("freshness_label") or None
    source          = practice_record.get("source", "claude")
    metadata        = practice_record.get("metadata") or {}
    generated_at    = practice_record.get("generated_at") or None

    if row:
        sql = """
            UPDATE generated_topic_practice
            SET content         = %s,
                model           = %s,
                version         = %s,
                freshness_label = %s,
                source          = %s,
                metadata        = %s,
                updated_at      = NOW()
            WHERE session_id = %s AND legacy_topic_id = %s AND practice_type = %s
        """
        with conn.cursor() as cur:
            cur.execute(sql, (
                content,
                model,
                version,
                freshness_label,
                source,
                json.dumps(metadata),
                session_id,
                legacy_topic_id,
                practice_type,
            ))
    else:
        sql = """
            INSERT INTO generated_topic_practice
                (user_id, session_id, legacy_topic_id, practice_type,
                 content, model, version, freshness_label, source, metadata,
                 generated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    COALESCE(%s::timestamptz, NOW()))
        """
        with conn.cursor() as cur:
            cur.execute(sql, (
                user_id,
                session_id,
                legacy_topic_id,
                practice_type,
                content,
                model,
                version,
                freshness_label,
                source,
                json.dumps(metadata),
                generated_at,
            ))


def get_generated_topic_practice_by_legacy_id(
    conn,
    *,
    session_id: str,
    legacy_topic_id: str,
    practice_type: str,
) -> dict | None:
    """Return the most recent generated_topic_practice row as a dict, or None."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT * FROM generated_topic_practice
            WHERE session_id = %s AND legacy_topic_id = %s AND practice_type = %s
            ORDER BY generated_at DESC
            LIMIT 1
            """,
            (session_id, legacy_topic_id, practice_type),
        )
        row = cur.fetchone()
    return dict(row) if row else None
