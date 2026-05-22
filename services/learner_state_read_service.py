"""Learner-state DB read service (progress + todos).

Provides normalised read access to topic_progress and todos rows.
Each read family is controlled by its own flag via storage_flags:
  - topic_progress: AI2_PROGRESS_DB_READS_ENABLED
  - todos:          AI2_TODOS_DB_READS_ENABLED

Design constraints
------------------
- Does not open DB connections — callers pass one in.
- Does not read environment variables directly — delegates to storage_flags.
- Does not run queries at import time.
- Not wired into any learner-facing route or service yet.
- Low-level functions (get_*/list_*_from_db) let repository exceptions propagate.
- maybe_* functions return None/[] when the flag is off or inputs are missing.
"""

from __future__ import annotations

from services.storage_flags import (
    is_progress_db_reads_enabled,
    is_todos_db_reads_enabled,
)


# ── Row normalizers ───────────────────────────────────────────────────────────

def normalize_topic_progress_row(row: dict) -> dict:
    """Return a safe, SessionContext-compatible dict from a topic_progress row.

    DB column → output key mapping:
      learn_status              -> learn
      quiz_status               -> quiz
      portfolio_task_status     -> portfolio_task
      interview_practice_status -> interview_practice
      reflection_status         -> reflection
    """
    metadata = row.get("metadata") or {}
    if isinstance(metadata, str):
        import json
        try:
            metadata = json.loads(metadata)
        except Exception:
            metadata = {}

    return {
        "learn":               str(row.get("learn_status")              or "not_started"),
        "quiz":                str(row.get("quiz_status")               or "not_started"),
        "portfolio_task":      str(row.get("portfolio_task_status")     or "not_started"),
        "interview_practice":  str(row.get("interview_practice_status") or "not_started"),
        "reflection":          str(row.get("reflection_status")         or "not_started"),
        "completion_percent":  int(row.get("completion_percent") or 0),
        "legacy_topic_id":     str(row.get("legacy_topic_id") or ""),
        "metadata":            metadata if isinstance(metadata, dict) else {},
    }


def normalize_todo_row(row: dict) -> dict:
    """Return a safe, SessionContext-compatible dict from a todos row.

    DB column → output key mapping:
      todo_key               -> todo_id
      legacy_linked_topic_id -> linked_topic_id
    """
    return {
        "todo_id":         str(row.get("todo_key")               or ""),
        "title":           str(row.get("title")                  or ""),
        "todo_type":       str(row.get("todo_type")              or ""),
        "status":          str(row.get("status")                 or ""),
        "linked_topic_id": str(row.get("legacy_linked_topic_id") or ""),
        "created_by":      str(row.get("created_by")             or ""),
        "due_label":       str(row.get("due_label")              or ""),
        "created_at":      str(row.get("created_at")             or ""),
        "updated_at":      str(row.get("updated_at")             or ""),
    }


# ── Low-level DB read functions ───────────────────────────────────────────────

def get_topic_progress_from_db(
    conn,
    *,
    session_id: str,
    legacy_topic_id: str,
) -> dict | None:
    """Fetch a topic_progress row and return a normalised dict.

    Returns None if the repository returns no row.
    Repository exceptions propagate to the caller.
    """
    from repositories.progress_repository import get_topic_progress_by_legacy_id

    row = get_topic_progress_by_legacy_id(
        conn,
        session_id=session_id,
        legacy_topic_id=legacy_topic_id,
    )
    if row is None:
        return None
    return normalize_topic_progress_row(row)


def list_todos_from_db(conn, *, session_id: str) -> list[dict]:
    """Fetch all todos for a session and return normalised dicts.

    Returns [] if the repository returns no rows.
    Repository exceptions propagate to the caller.
    """
    from repositories.todos_repository import list_todos_for_session

    rows = list_todos_for_session(conn, session_id)
    return [normalize_todo_row(row) for row in rows]


# ── Flag-gated helpers ────────────────────────────────────────────────────────

def maybe_get_topic_progress_from_db(
    conn,
    *,
    session_id: str,
    legacy_topic_id: str,
) -> dict | None:
    """Return normalised progress dict only when the progress DB reads flag is on.

    Returns None when:
    - AI2_PROGRESS_DB_READS_ENABLED is not truthy
    - conn is None
    - session_id or legacy_topic_id is empty
    """
    if not is_progress_db_reads_enabled():
        return None
    if conn is None:
        return None
    if not session_id or not legacy_topic_id:
        return None
    return get_topic_progress_from_db(conn, session_id=session_id, legacy_topic_id=legacy_topic_id)


def maybe_list_todos_from_db(conn, *, session_id: str) -> list[dict] | None:
    """Return normalised todos list only when the todos DB reads flag is on.

    Returns None (not []) when the flag is off or inputs are missing, so callers
    can distinguish "disabled" from "enabled but empty".
    Returns [] when the flag is on and the DB has no todos for the session.
    """
    if not is_todos_db_reads_enabled():
        return None
    if conn is None:
        return None
    if not session_id:
        return None
    return list_todos_from_db(conn, session_id=session_id)
