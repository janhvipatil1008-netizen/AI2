"""Optional write-through helper for topic_progress and todos.

Controlled entirely by the AI2_DB_WRITE_THROUGH_ENABLED environment variable.
When the flag is off (the default), every public function is a no-op.

Design constraints
------------------
- Never opens a DB connection — callers pass one in.
- Never commits or rolls back — that is the caller's responsibility.
- Never mutates SessionContext — reads only.
- Not wired into any route or service yet.
"""

from __future__ import annotations

from services.storage_flags import is_db_write_through_enabled


def maybe_write_topic_progress(
    *,
    conn,
    session,
    user_id: str | None,
    session_id: str | None,
    legacy_topic_id: str,
) -> bool:
    """Write topic progress from SessionContext to DB if the flag is on.

    Returns True when a write was attempted, False when skipped.
    Raises on DB errors so the caller can decide to rollback.
    """
    if not is_db_write_through_enabled() or conn is None:
        return False

    from repositories.progress_repository import upsert_topic_progress

    progress = session.get_topic_progress(legacy_topic_id)
    completion_percent = session.topic_completion_percent(legacy_topic_id)

    upsert_topic_progress(
        conn,
        user_id=user_id,
        session_id=session_id,
        legacy_topic_id=legacy_topic_id,
        progress=progress,
        completion_percent=completion_percent,
    )
    return True


def maybe_write_todos(
    *,
    conn,
    session,
    user_id: str | None,
    session_id: str | None,
) -> int:
    """Write all session todos from SessionContext to DB if the flag is on.

    Returns the number of todos written (0 when skipped).
    Raises on DB errors so the caller can decide to rollback.
    """
    if not is_db_write_through_enabled() or conn is None:
        return 0

    from repositories.todos_repository import upsert_todo

    todos = session.get_todos()
    for todo in todos:
        upsert_todo(conn, user_id=user_id, session_id=session_id, todo=todo)
    return len(todos)


def maybe_write_topic_and_todos(
    *,
    conn,
    session,
    user_id: str | None,
    session_id: str | None,
    legacy_topic_id: str | None = None,
) -> dict:
    """Convenience wrapper: write topic progress (if a legacy_topic_id is given) and all todos.

    Returns {"progress": bool, "todos": int}.
    Raises on DB errors so the caller can decide to rollback.
    """
    progress_written = False
    if legacy_topic_id:
        progress_written = maybe_write_topic_progress(
            conn=conn,
            session=session,
            user_id=user_id,
            session_id=session_id,
            legacy_topic_id=legacy_topic_id,
        )

    todos_written = maybe_write_todos(
        conn=conn,
        session=session,
        user_id=user_id,
        session_id=session_id,
    )

    return {"progress": progress_written, "todos": todos_written}
