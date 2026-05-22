"""Repository functions for the usage_events DB table.

All functions accept an open psycopg2 connection. They do not open connections
themselves, read env vars, mutate SessionContext, or manage transactions.

SessionContext remains the runtime source of truth. This repository is not wired
into routes or services yet.
"""

from __future__ import annotations

import json

import psycopg2.extras


def insert_usage_event(
    conn,
    *,
    user_id: str | None,
    session_id: str | None,
    event: dict,
) -> None:
    """Insert one usage event, ignoring duplicate event_id rows."""
    legacy_topic_id = event.get("topic_id") or event.get("legacy_topic_id")
    metadata = event.get("metadata") or {}

    sql = """
        INSERT INTO usage_events
            (event_id, user_id, session_id, legacy_topic_id,
             event_type, model, source, status, metadata, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s,
                COALESCE(%s::timestamptz, NOW()))
        ON CONFLICT (event_id) DO NOTHING
    """
    with conn.cursor() as cur:
        cur.execute(sql, (
            event["event_id"],
            user_id,
            session_id,
            legacy_topic_id,
            event["event_type"],
            event.get("model") or None,
            event["source"],
            event["status"],
            json.dumps(metadata),
            event.get("created_at") or None,
        ))


def insert_usage_events(
    conn,
    *,
    user_id: str | None,
    session_id: str | None,
    events: list[dict],
) -> int:
    """Insert multiple usage events and return the number attempted."""
    if not events:
        return 0

    for event in events:
        insert_usage_event(
            conn,
            user_id=user_id,
            session_id=session_id,
            event=event,
        )
    return len(events)


def list_usage_events_for_session(
    conn,
    *,
    session_id: str,
    limit: int = 100,
) -> list[dict]:
    """Return recent usage_events for a session, newest first."""
    safe_limit = _safe_limit(limit)
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT *
            FROM usage_events
            WHERE session_id = %s
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (session_id, safe_limit),
        )
        rows = cur.fetchall()
    return [dict(row) for row in rows]


def usage_event_summary_for_session(
    conn,
    *,
    session_id: str,
) -> dict:
    """Return usage counters for one session."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT
                COUNT(*)::int AS total_events,
                COUNT(*) FILTER (WHERE source = 'claude')::int AS claude_events,
                COUNT(*) FILTER (WHERE source = 'cache')::int AS cache_events,
                COUNT(*) FILTER (WHERE source = 'test_mode')::int AS test_mode_events,
                COUNT(*) FILTER (WHERE status = 'error')::int AS error_events
            FROM usage_events
            WHERE session_id = %s
            """,
            (session_id,),
        )
        counts = cur.fetchone() or {}

        cur.execute(
            """
            SELECT event_type, COUNT(*)::int AS count
            FROM usage_events
            WHERE session_id = %s
            GROUP BY event_type
            """,
            (session_id,),
        )
        type_rows = cur.fetchall()

    by_event_type = {
        str(_row_value(row, "event_type", 0, "")): int(_row_value(row, "count", 1, 0) or 0)
        for row in type_rows
    }

    return {
        "total_events":     int(_row_value(counts, "total_events", 0, 0) or 0),
        "claude_events":    int(_row_value(counts, "claude_events", 1, 0) or 0),
        "cache_events":     int(_row_value(counts, "cache_events", 2, 0) or 0),
        "test_mode_events": int(_row_value(counts, "test_mode_events", 3, 0) or 0),
        "error_events":     int(_row_value(counts, "error_events", 4, 0) or 0),
        "by_event_type":    by_event_type,
    }


def _safe_limit(limit: int) -> int:
    try:
        parsed = int(limit)
    except (TypeError, ValueError):
        return 100
    return max(1, min(parsed, 1000))


def _row_value(row, key: str, index: int, default=None):
    if isinstance(row, dict):
        return row.get(key, default)
    try:
        return row[index]
    except (IndexError, TypeError):
        return default
