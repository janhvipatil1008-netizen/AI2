"""Fallback-safe learner state reader.

Attempts DB reads when the relevant flag is ON and a connection is provided;
falls back to SessionContext when the flag is off, the connection is absent,
the row is missing, or the DB raises.

Design constraints
------------------
- Never opens DB connections — callers pass one in.
- Never runs queries at import time.
- Never mutates SessionContext.
- Never reads env vars directly — delegates to storage_flags.
- Never touches the database package.
"""

from __future__ import annotations

from services.storage_flags import (
    is_progress_db_reads_enabled,
    is_todos_db_reads_enabled,
)


# ── Error helper ──────────────────────────────────────────────────────────────

def safe_error_text(error: Exception, max_chars: int = 300) -> str:
    """Return a safely truncated error string with no stack trace."""
    return str(error)[:max_chars]


# ── Topic progress ────────────────────────────────────────────────────────────

def get_topic_progress_with_fallback(
    *,
    conn,
    session,
    session_id: str,
    legacy_topic_id: str,
) -> dict:
    """Return topic progress, preferring DB when enabled, else SessionContext.

    Returns:
        {
            "source": "db" | "fallback" | "error_fallback",
            "topic_progress": dict,
            "error": str | None,
            "notes": list[str],
        }
    """
    notes: list[str] = []

    if is_progress_db_reads_enabled() and conn is not None and session_id and legacy_topic_id:
        try:
            from services.learner_state_read_service import get_topic_progress_from_db
            row = get_topic_progress_from_db(
                conn,
                session_id=session_id,
                legacy_topic_id=legacy_topic_id,
            )
            if row is not None:
                return {
                    "source":         "db",
                    "topic_progress": row,
                    "error":          None,
                    "notes":          notes,
                }
            notes.append(
                f"No DB row for legacy_topic_id={legacy_topic_id!r}; "
                "using session fallback."
            )
        except Exception as exc:
            notes.append("DB read failed; using session fallback.")
            return {
                "source":         "error_fallback",
                "topic_progress": _progress_from_session(session, legacy_topic_id),
                "error":          safe_error_text(exc),
                "notes":          notes,
            }

    return {
        "source":         "fallback",
        "topic_progress": _progress_from_session(session, legacy_topic_id),
        "error":          None,
        "notes":          notes,
    }


# ── Todos ─────────────────────────────────────────────────────────────────────

def list_todos_with_fallback(
    *,
    conn,
    session,
    session_id: str,
) -> dict:
    """Return todos list, preferring DB when enabled, else SessionContext.

    An empty list [] from the DB still counts as source="db" — it means the
    DB was queried and found no todos, which is distinct from "flag off".

    Returns:
        {
            "source": "db" | "fallback" | "error_fallback",
            "todos": list[dict],
            "error": str | None,
            "notes": list[str],
        }
    """
    notes: list[str] = []

    if is_todos_db_reads_enabled() and conn is not None and session_id:
        try:
            from services.learner_state_read_service import list_todos_from_db
            todos = list_todos_from_db(conn, session_id=session_id)
            return {
                "source": "db",
                "todos":  todos,
                "error":  None,
                "notes":  notes,
            }
        except Exception as exc:
            notes.append("DB read failed; using session fallback.")
            return {
                "source": "error_fallback",
                "todos":  list(session.get_todos()),
                "error":  safe_error_text(exc),
                "notes":  notes,
            }

    return {
        "source": "fallback",
        "todos":  list(session.get_todos()),
        "error":  None,
        "notes":  notes,
    }


# ── Combined ──────────────────────────────────────────────────────────────────

def get_learner_state_with_fallback(
    *,
    conn,
    session,
    session_id: str,
    legacy_topic_id: str | None = None,
) -> dict:
    """Run topic progress and todos reads with fallback; return combined result.

    Topic progress is included only when legacy_topic_id is provided.

    Returns:
        {
            "topic_progress_result": dict | None,
            "todos_result": dict,
            "source_summary": {
                "topic_progress_source": str | None,
                "todos_source": str,
            },
            "notes": list[str],
        }
    """
    topic_progress_result = None
    combined_notes: list[str] = []

    if legacy_topic_id:
        topic_progress_result = get_topic_progress_with_fallback(
            conn=conn,
            session=session,
            session_id=session_id,
            legacy_topic_id=legacy_topic_id,
        )
        combined_notes.extend(topic_progress_result.get("notes", []))

    todos_result = list_todos_with_fallback(
        conn=conn,
        session=session,
        session_id=session_id,
    )
    combined_notes.extend(todos_result.get("notes", []))

    return {
        "topic_progress_result": topic_progress_result,
        "todos_result":          todos_result,
        "source_summary": {
            "topic_progress_source": (
                topic_progress_result["source"] if topic_progress_result else None
            ),
            "todos_source": todos_result["source"],
        },
        "notes": combined_notes,
    }


# ── Session helpers ───────────────────────────────────────────────────────────

def _progress_from_session(session, legacy_topic_id: str) -> dict:
    steps = session.get_topic_progress(legacy_topic_id)
    return {
        **steps,
        "completion_percent": session.topic_completion_percent(legacy_topic_id),
        "legacy_topic_id":    legacy_topic_id,
    }
