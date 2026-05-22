"""Repository functions for the todos DB table.

All functions accept an open psycopg2 connection.  They do not open
connections themselves, read env vars, or mutate SessionContext.

Uses legacy_linked_topic_id (TEXT) for transition compatibility while
SessionContext string topic IDs remain the runtime source of truth.

Not wired into routes or services yet.
"""

from __future__ import annotations

import json

import psycopg2.extras


def upsert_todo(
    conn,
    *,
    user_id: str | None,
    session_id: str | None,
    todo: dict,
) -> None:
    """Insert or update a todos row keyed on (session_id, todo_key).

    todo dict is expected to match the SessionContext todo schema:
      todo_id, title, todo_type, status, linked_topic_id (legacy string),
      created_by, due_label, created_at.

    NOTE: todos has no UNIQUE constraint on (session_id, todo_key), only
    a regular index.  We use SELECT-then-UPDATE/INSERT to avoid duplicates.
    A future migration can add the constraint and switch to ON CONFLICT.
    """
    todo_key = todo.get("todo_id", "")
    title    = todo.get("title", "")
    todo_type = todo.get("todo_type", "daily")
    status   = todo.get("status", "todo")
    legacy_linked_topic_id = todo.get("linked_topic_id") or ""
    created_by = todo.get("created_by", "learner")
    due_label  = todo.get("due_label") or None
    metadata   = {k: v for k, v in todo.items()
                  if k not in ("todo_id", "title", "todo_type", "status",
                               "linked_topic_id", "created_by", "due_label")}

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT id FROM todos WHERE session_id = %s AND todo_key = %s",
            (session_id, todo_key),
        )
        row = cur.fetchone()

    if row:
        sql = """
            UPDATE todos
            SET title                  = %s,
                todo_type              = %s,
                status                 = %s,
                legacy_linked_topic_id = %s,
                due_label              = %s,
                metadata               = %s,
                updated_at             = NOW()
            WHERE session_id = %s AND todo_key = %s
        """
        with conn.cursor() as cur:
            cur.execute(sql, (
                title,
                todo_type,
                status,
                legacy_linked_topic_id,
                due_label,
                json.dumps(metadata),
                session_id,
                todo_key,
            ))
    else:
        sql = """
            INSERT INTO todos
                (user_id, session_id, todo_key, title, todo_type, status,
                 legacy_linked_topic_id, created_by, due_label, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        with conn.cursor() as cur:
            cur.execute(sql, (
                user_id,
                session_id,
                todo_key,
                title,
                todo_type,
                status,
                legacy_linked_topic_id,
                created_by,
                due_label,
                json.dumps(metadata),
            ))


def list_todos_for_session(conn, session_id: str) -> list[dict]:
    """Return all todos for a session ordered by creation time."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT * FROM todos WHERE session_id = %s ORDER BY created_at ASC",
            (session_id,),
        )
        rows = cur.fetchall()
    return [dict(row) for row in rows]
