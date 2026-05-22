"""Mismatch comparison service for SessionContext vs DB mirror state.

Accepts already-read values from both sides; never opens DB connections,
reads env vars, or mutates session state.  Designed to validate write-through
quality before trusting DB reads.

Design constraints
------------------
- Pure functions only — no I/O, no side effects.
- Does not import the database package.
- Does not access the process environment.
- Does not modify SessionContext.
- Does not include private user text beyond todo titles already in SessionContext.
"""

from __future__ import annotations

_PROGRESS_FIELDS = (
    "learn",
    "quiz",
    "portfolio_task",
    "interview_practice",
    "reflection",
)


# ── Topic progress comparison ─────────────────────────────────────────────────

def compare_topic_progress(
    *,
    session,
    legacy_topic_id: str,
    db_progress: dict | None,
) -> dict:
    """Compare topic_progress step statuses and completion_percent.

    Session side uses session.get_topic_progress() and
    session.topic_completion_percent().  DB side uses the normalised dict
    produced by learner_state_read_service.normalize_topic_progress_row().

    Returns a result dict describing any field-level mismatches.
    """
    session_steps   = session.get_topic_progress(legacy_topic_id)
    session_pct     = session.topic_completion_percent(legacy_topic_id)
    session_snapshot = {**session_steps, "completion_percent": session_pct}

    if db_progress is None:
        return {
            "type":             "topic_progress",
            "legacy_topic_id":  legacy_topic_id,
            "matches":          False,
            "db_missing":       True,
            "mismatches":       [],
            "session_snapshot": session_snapshot,
            "db_snapshot":      None,
        }

    db_snapshot = {
        field: db_progress.get(field, "not_started")
        for field in _PROGRESS_FIELDS
    }
    db_snapshot["completion_percent"] = int(db_progress.get("completion_percent") or 0)

    mismatches = []
    for field in _PROGRESS_FIELDS:
        s_val = session_steps.get(field, "not_started")
        d_val = db_snapshot[field]
        if s_val != d_val:
            mismatches.append({
                "field":         field,
                "session_value": s_val,
                "db_value":      d_val,
            })
    if session_pct != db_snapshot["completion_percent"]:
        mismatches.append({
            "field":         "completion_percent",
            "session_value": session_pct,
            "db_value":      db_snapshot["completion_percent"],
        })

    return {
        "type":             "topic_progress",
        "legacy_topic_id":  legacy_topic_id,
        "matches":          len(mismatches) == 0,
        "db_missing":       False,
        "mismatches":       mismatches,
        "session_snapshot": session_snapshot,
        "db_snapshot":      db_snapshot,
    }


# ── Todos comparison ──────────────────────────────────────────────────────────

def compare_todos(
    *,
    session,
    db_todos: list[dict] | None,
) -> dict:
    """Compare todos list between SessionContext and DB mirror.

    Checks: count, todo_id presence, and per-todo status/title/todo_type/linked_topic_id.

    Returns a result dict describing any item-level mismatches.
    """
    session_todos  = session.get_todos()
    session_count  = len(session_todos)

    if db_todos is None:
        return {
            "type":          "todos",
            "matches":       False,
            "db_missing":    True,
            "mismatches":    [],
            "session_count": session_count,
            "db_count":      None,
        }

    db_count = len(db_todos)
    session_by_id = {t["todo_id"]: t for t in session_todos}
    db_by_id      = {t["todo_id"]: t for t in db_todos}

    mismatches = []

    if session_count != db_count:
        mismatches.append({
            "field":         "count",
            "session_value": session_count,
            "db_value":      db_count,
        })

    for todo_id, s_todo in session_by_id.items():
        if todo_id not in db_by_id:
            mismatches.append({
                "field":         "todo_id_presence",
                "todo_id":       todo_id,
                "session_value": "present",
                "db_value":      "missing",
            })
            continue
        d_todo = db_by_id[todo_id]
        for field in ("status", "title", "todo_type", "linked_topic_id"):
            s_val = str(s_todo.get(field) or "")
            d_val = str(d_todo.get(field) or "")
            if s_val != d_val:
                mismatches.append({
                    "field":         field,
                    "todo_id":       todo_id,
                    "session_value": s_val,
                    "db_value":      d_val,
                })

    for todo_id in db_by_id:
        if todo_id not in session_by_id:
            mismatches.append({
                "field":         "todo_id_presence",
                "todo_id":       todo_id,
                "session_value": "missing",
                "db_value":      "present",
            })

    return {
        "type":          "todos",
        "matches":       len(mismatches) == 0,
        "db_missing":    False,
        "mismatches":    mismatches,
        "session_count": session_count,
        "db_count":      db_count,
    }


# ── Combined comparison ───────────────────────────────────────────────────────

def compare_learner_state(
    *,
    session,
    legacy_topic_id: str | None = None,
    db_progress: dict | None = None,
    db_todos: list[dict] | None = None,
) -> dict:
    """Run all applicable comparisons and return a combined result.

    Topic progress comparison is included only when legacy_topic_id is provided.
    Todos comparison is always included.

    Returns:
        {
            "matches":      bool,   # True only when every comparison matches
            "comparisons":  [...]   # list of individual comparison dicts
        }
    """
    comparisons = []

    if legacy_topic_id:
        comparisons.append(
            compare_topic_progress(
                session=session,
                legacy_topic_id=legacy_topic_id,
                db_progress=db_progress,
            )
        )

    comparisons.append(
        compare_todos(session=session, db_todos=db_todos)
    )

    overall_match = all(c["matches"] for c in comparisons)

    return {
        "matches":     overall_match,
        "comparisons": comparisons,
    }
