"""Optional write-through helpers for usage_events.

Controlled entirely by the AI2_DB_WRITE_THROUGH_ENABLED environment variable.
When the flag is off (the default), every public function is a no-op.

Design constraints
------------------
- Never opens a DB connection; callers pass one in.
- Never commits or rolls back; that is the caller's responsibility.
- Never mutates SessionContext; reads only.
- Not wired into any route or service yet.
"""

from __future__ import annotations

from services.storage_flags import is_db_write_through_enabled


def maybe_write_usage_events(
    *,
    conn,
    session,
    user_id: str | None,
    session_id: str | None,
) -> int:
    """Write all SessionContext usage events to DB if the flag is on.

    Returns the number of events attempted (0 when skipped).
    Raises on DB errors so the caller can decide to rollback.
    """
    if not is_db_write_through_enabled() or conn is None:
        return 0

    events = list(getattr(session, "usage_events", []) or [])
    if not events:
        return 0

    from repositories.usage_events_repository import insert_usage_events

    return insert_usage_events(
        conn,
        user_id=user_id,
        session_id=session_id,
        events=events,
    )


def maybe_write_latest_usage_event(
    *,
    conn,
    session,
    user_id: str | None,
    session_id: str | None,
) -> bool:
    """Write only the latest SessionContext usage event if the flag is on.

    Returns True when a repository call was made, False when skipped.
    Raises on DB errors so the caller can decide to rollback.
    """
    if not is_db_write_through_enabled() or conn is None:
        return False

    events = getattr(session, "usage_events", []) or []
    if not events:
        return False

    from repositories.usage_events_repository import insert_usage_event

    insert_usage_event(
        conn,
        user_id=user_id,
        session_id=session_id,
        event=events[-1],
    )
    return True


def maybe_write_usage_events_for_topic(
    *,
    conn,
    session,
    user_id: str | None,
    session_id: str | None,
    legacy_topic_id: str,
) -> int:
    """Write usage events matching a legacy topic ID if the flag is on.

    Matches either event["topic_id"] or event["legacy_topic_id"].
    Returns the number of matching events attempted (0 when skipped).
    Raises on DB errors so the caller can decide to rollback.
    """
    if not is_db_write_through_enabled() or conn is None or not legacy_topic_id:
        return 0

    events = getattr(session, "usage_events", []) or []
    matching_events = [
        event
        for event in events
        if event.get("topic_id") == legacy_topic_id
        or event.get("legacy_topic_id") == legacy_topic_id
    ]
    if not matching_events:
        return 0

    from repositories.usage_events_repository import insert_usage_events

    return insert_usage_events(
        conn,
        user_id=user_id,
        session_id=session_id,
        events=matching_events,
    )
