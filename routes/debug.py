"""Debug routes for AI² — config-only and storage-health endpoints.

Protected by debug_access dependency; returns 404 in production without a valid token.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse

import routes.deps as _deps
from routes.deps import debug_access, safe_debug_error_message
from context.session import SessionContext
from database.pool import get_conn

router = APIRouter()


@router.get("/debug/storage-status")
async def debug_storage_status(_: None = Depends(debug_access)):
    """Safe read-only status of the storage/write-through configuration.

    Returns only boolean flags and human-readable notes.
    Never returns env var values, secrets, DB URLs, or user data.
    Never opens a DB connection.
    """
    from services.storage_flags import (
        is_curriculum_db_reads_enabled,
        is_db_write_through_enabled,
        is_progress_db_reads_enabled,
        is_todos_db_reads_enabled,
    )
    wt_enabled = is_db_write_through_enabled()
    curriculum_reads_enabled = is_curriculum_db_reads_enabled()
    progress_reads_enabled = is_progress_db_reads_enabled()
    todos_reads_enabled = is_todos_db_reads_enabled()
    db_reads_enabled = any((
        curriculum_reads_enabled,
        progress_reads_enabled,
        todos_reads_enabled,
    ))
    if db_reads_enabled:
        storage_mode = "session_context_with_db_read_flags_enabled"
    elif wt_enabled:
        storage_mode = "session_context_with_db_write_through"
    else:
        storage_mode = "session_context_only"
    notes = [
        "SessionContext remains the runtime source of truth.",
        "New learning tables are not read by runtime routes yet.",
        "DB write-through is enabled for progress/todos mirrors." if wt_enabled
        else "DB write-through is disabled.",
    ]
    if db_reads_enabled:
        notes.append(
            "DB read flags may be enabled, but runtime routes have not been migrated to DB-primary reads yet."
        )
    return {
        "session_context_source_of_truth": True,
        "db_write_through_enabled":        wt_enabled,
        "db_reads_enabled":                db_reads_enabled,
        "curriculum_db_reads_enabled":     curriculum_reads_enabled,
        "progress_db_reads_enabled":       progress_reads_enabled,
        "todos_db_reads_enabled":          todos_reads_enabled,
        "storage_mode":                    storage_mode,
        "notes":                           notes,
    }


@router.get("/debug/storage-health")
async def debug_storage_health(
    request: Request,
    session_id: Optional[str] = None,
    legacy_topic_id: Optional[str] = None,
    _: None = Depends(debug_access),
):
    """Unified debug-only storage/mirror health summary.

    Reports storage flags and safe SessionContext counts only. Does not open a
    DB connection, call debug HTTP endpoints, or return private generated
    content, submissions, notes, usage metadata, or full session data.
    """
    return _build_storage_health_payload(request, session_id, legacy_topic_id)


@router.get("/debug/storage-health-view", response_class=HTMLResponse)
async def debug_storage_health_view(
    request: Request,
    session_id: Optional[str] = None,
    legacy_topic_id: Optional[str] = None,
    _: None = Depends(debug_access),
):
    """Minimal internal view for the safe storage health summary."""
    health = _build_storage_health_payload(request, session_id, legacy_topic_id)
    return _deps.templates.TemplateResponse(
        request=request,
        name="storage_health.html",
        context={
            "health": health,
            "session_id": session_id or "",
            "legacy_topic_id": legacy_topic_id or "",
            "test_mode": bool(_deps.TEST_MODE),
        },
    )


def _build_storage_health_payload(
    request: Request,
    session_id: Optional[str] = None,
    legacy_topic_id: Optional[str] = None,
) -> dict:
    from services.storage_flags import (
        is_curriculum_db_reads_enabled,
        is_db_write_through_enabled,
        is_progress_db_reads_enabled,
        is_todos_db_reads_enabled,
    )

    try:
        wt_enabled = is_db_write_through_enabled()
        curriculum_reads_enabled = is_curriculum_db_reads_enabled()
        progress_reads_enabled = is_progress_db_reads_enabled()
        todos_reads_enabled = is_todos_db_reads_enabled()
        db_reads_enabled = any((
            curriculum_reads_enabled,
            progress_reads_enabled,
            todos_reads_enabled,
        ))

        session = None
        session_status = None
        topic_status = None
        notes = [
            "SessionContext remains the runtime source of truth.",
            "This endpoint reports flags and safe counts only; it does not read DB mirrors.",
        ]

        if session_id:
            data = _deps.get_session_data(session_id, getattr(request.state, "user_id", "") or "")
            session = data["session"]
            session_status = _storage_health_session_status(session)
            notes.append("SessionContext loaded read-only for safe count summary.")

            if legacy_topic_id:
                topic_status = _storage_health_topic_status(session, legacy_topic_id)
                notes.append("Topic-level status is presence-only; no generated/user text is returned.")
        else:
            notes.append("No session_id provided; returning config-only health without DB access.")

        overall_status = _storage_health_overall_status(
            wt_enabled=wt_enabled,
            curriculum_reads_enabled=curriculum_reads_enabled,
            progress_reads_enabled=progress_reads_enabled,
            todos_reads_enabled=todos_reads_enabled,
        )

        return {
            "source_of_truth": {
                "session_context": True,
                "db_primary_reads": False,
            },
            "flags": {
                "db_write_through_enabled": wt_enabled,
                "curriculum_db_reads_enabled": curriculum_reads_enabled,
                "progress_db_reads_enabled": progress_reads_enabled,
                "todos_db_reads_enabled": todos_reads_enabled,
                "db_reads_enabled": db_reads_enabled,
            },
            "mirrors": {
                "curriculum": {
                    "schema_available": True,
                    "read_flag_enabled": curriculum_reads_enabled,
                    "debug_checks_available": True,
                },
                "learner_state": {
                    "schema_available": True,
                    "write_through_available": True,
                    "progress_read_flag_enabled": progress_reads_enabled,
                    "todos_read_flag_enabled": todos_reads_enabled,
                    "debug_checks_available": True,
                    "session_comparison_available": True,
                    **({"session_status": session_status} if session_status is not None else {}),
                    **({"topic_status": topic_status} if topic_status is not None else {}),
                },
                "generated_learning": {
                    "schema_available": True,
                    "write_through_available": True,
                    "debug_checks_available": True,
                    "session_comparison_available": True,
                    **({"topic_status": topic_status} if topic_status is not None else {}),
                },
                "usage_events": {
                    "schema_available": True,
                    "write_through_available": True,
                    "debug_checks_available": True,
                    "session_comparison_available": True,
                    **(
                        {"session_status": {
                            "session_loaded": True,
                            "usage_events_count": session_status["usage_events_count"],
                        }}
                        if session_status is not None else {}
                    ),
                },
            },
            "overall_status": overall_status,
            "notes": notes,
        }
    except HTTPException:
        raise
    except Exception as exc:
        return {
            "source_of_truth": {
                "session_context": True,
                "db_primary_reads": False,
            },
            "flags": {
                "db_write_through_enabled": False,
                "curriculum_db_reads_enabled": False,
                "progress_db_reads_enabled": False,
                "todos_db_reads_enabled": False,
                "db_reads_enabled": False,
            },
            "mirrors": {
                "curriculum": {},
                "learner_state": {},
                "generated_learning": {},
                "usage_events": {},
            },
            "overall_status": "error",
            "notes": [
                "Storage health summary failed.",
                safe_debug_error_message(exc),
            ],
        }


def _storage_health_overall_status(
    *,
    wt_enabled: bool,
    curriculum_reads_enabled: bool,
    progress_reads_enabled: bool,
    todos_reads_enabled: bool,
) -> str:
    if not any((wt_enabled, curriculum_reads_enabled, progress_reads_enabled, todos_reads_enabled)):
        return "not_configured"
    if wt_enabled and all((curriculum_reads_enabled, progress_reads_enabled, todos_reads_enabled)):
        return "healthy"
    return "partial"


def _storage_health_session_status(session: SessionContext) -> dict:
    topic_progress = getattr(session, "topic_progress", {}) or {}
    return {
        "session_loaded": True,
        "usage_events_count": len(getattr(session, "usage_events", []) or []),
        "todos_count": len(getattr(session, "todos", []) or []),
        "completed_topics_count": _storage_health_completed_topics_count(session, topic_progress),
    }


def _storage_health_completed_topics_count(session: SessionContext, topic_progress: dict) -> int:
    completed = 0
    for topic_id in topic_progress:
        try:
            if session.topic_completion_percent(topic_id) == 100:
                completed += 1
        except Exception:
            steps = topic_progress.get(topic_id) or {}
            if steps and all(status == "done" for status in steps.values()):
                completed += 1
    return completed


def _storage_health_topic_status(session: SessionContext, legacy_topic_id: str) -> dict:
    practice = (getattr(session, "generated_topic_practice", {}) or {}).get(legacy_topic_id) or {}
    return {
        "topic_progress_present": legacy_topic_id in (getattr(session, "topic_progress", {}) or {}),
        "generated_content_present": legacy_topic_id in (getattr(session, "generated_topic_content", {}) or {}),
        "practice_present": any(
            practice.get(kind) is not None
            for kind in ("quiz", "portfolio_task", "interview_practice")
        ),
        "quiz_submission_present": legacy_topic_id in (getattr(session, "quiz_submissions", {}) or {}),
        "portfolio_submission_present": legacy_topic_id in (getattr(session, "portfolio_submissions", {}) or {}),
        "interview_submission_present": legacy_topic_id in (getattr(session, "interview_submissions", {}) or {}),
        "notes_present": legacy_topic_id in (getattr(session, "topic_notes", {}) or {}),
    }


def _empty_generated_learning_state_found() -> dict:
    return {
        "generated_topic_content": False,
        "generated_topic_practice": {
            "quiz": False,
            "portfolio_task": False,
            "interview_practice": False,
        },
        "quiz_submission": False,
        "portfolio_submission": False,
        "interview_submission": False,
        "topic_notes": False,
    }


def _generated_learning_state_found(state: dict | None) -> dict:
    found = _empty_generated_learning_state_found()
    if not state:
        return found

    found["generated_topic_content"] = state.get("generated_topic_content") is not None
    practice = state.get("generated_topic_practice") or {}
    found["generated_topic_practice"] = {
        "quiz": practice.get("quiz") is not None,
        "portfolio_task": practice.get("portfolio_task") is not None,
        "interview_practice": practice.get("interview_practice") is not None,
    }
    found["quiz_submission"] = state.get("quiz_submission") is not None
    found["portfolio_submission"] = state.get("portfolio_submission") is not None
    found["interview_submission"] = state.get("interview_submission") is not None
    found["topic_notes"] = state.get("topic_notes") is not None
    return found


def _safe_debug_limit(value, *, default: int = 50, minimum: int = 1, maximum: int = 200) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(parsed, maximum))


def _flatten_generated_learning_found(found: dict) -> list[bool]:
    practice = found.get("generated_topic_practice") or {}
    return [
        bool(found.get("generated_topic_content")),
        bool(practice.get("quiz")),
        bool(practice.get("portfolio_task")),
        bool(practice.get("interview_practice")),
        bool(found.get("quiz_submission")),
        bool(found.get("portfolio_submission")),
        bool(found.get("interview_submission")),
        bool(found.get("topic_notes")),
    ]


_GENERATED_LEARNING_PRIVATE_FIELDS = frozenset({
    "content",
    "answers",
    "evaluation",
    "submission",
    "feedback",
    "answer",
    "reflection",
    "confusions",
    "application_idea",
})


def _redact_generated_learning_state(state):
    if state is None:
        return None
    if isinstance(state, list):
        return [_redact_generated_learning_state(item) for item in state]
    if not isinstance(state, dict):
        return state

    redacted = {}
    for key, value in state.items():
        if value is None:
            redacted[key] = None
        elif key == "metadata":
            redacted[key] = {}
        elif key in _GENERATED_LEARNING_PRIVATE_FIELDS:
            redacted[key] = "[redacted]"
        else:
            redacted[key] = _redact_generated_learning_state(value)
    return redacted


def _redact_usage_event(event):
    if not isinstance(event, dict):
        return event
    return {
        key: ({} if key == "metadata" and value is not None else value)
        for key, value in event.items()
    }


@router.get("/debug/generated-learning-db-check")
async def debug_generated_learning_db_check(
    session_id: str,
    legacy_topic_id: str,
    _: None = Depends(debug_access),
):
    """Debug-only: inspect generated-learning DB mirror state.

    Opens one DB connection only when this endpoint is called. Returns redacted
    generated-learning mirror state from generated_learning_read_service.
    Never returns env var values, DB URLs, stack traces, or full session data.
    """
    from services.generated_learning_read_service import get_generated_learning_state_from_db

    state = None
    error_msg = None
    source = "db"
    notes: list[str] = []

    try:
        with get_conn() as conn:
            state = get_generated_learning_state_from_db(
                conn,
                session_id=session_id,
                legacy_topic_id=legacy_topic_id,
            )
    except Exception as exc:
        source = "error"
        state = None
        error_msg = safe_debug_error_message(exc)
        notes.append("Generated-learning DB mirror read failed. Check DB connectivity and schema.")

    if source == "db":
        notes.append("Generated-learning DB mirror read completed.")
        if not any(_flatten_generated_learning_found(_generated_learning_state_found(state))):
            notes.append("No generated-learning mirror state found for this session/topic.")

    return {
        "session_id": session_id,
        "legacy_topic_id": legacy_topic_id,
        "attempted_db_connection": True,
        "source": source,
        "state_found": _generated_learning_state_found(state),
        "state": _redact_generated_learning_state(state),
        "error": error_msg,
        "notes": notes,
    }


@router.get("/debug/usage-events-db-check")
async def debug_usage_events_db_check(
    session_id: str,
    limit: str = "50",
    _: None = Depends(debug_access),
):
    """Debug-only: inspect usage_events DB mirror state for a session.

    Opens one DB connection only when this endpoint is called. Returns only
    usage_events mirror rows with metadata redacted and aggregate counts from the usage-events
    repository. Never returns env var values, DB URLs, stack traces, or full
    session data.
    """
    from repositories.usage_events_repository import (
        list_usage_events_for_session,
        usage_event_summary_for_session,
    )

    safe_limit = _safe_debug_limit(limit)
    events = []
    summary = None
    error_msg = None
    source = "db"
    notes: list[str] = []

    try:
        with get_conn() as conn:
            events = list_usage_events_for_session(
                conn,
                session_id=session_id,
                limit=safe_limit,
            )
            summary = usage_event_summary_for_session(
                conn,
                session_id=session_id,
            )
    except Exception as exc:
        source = "error"
        events = []
        summary = None
        error_msg = safe_debug_error_message(exc)
        notes.append("Usage-events DB mirror read failed. Check DB connectivity and schema.")

    if source == "db":
        notes.append("Usage-events DB mirror read completed.")
        if not events:
            notes.append("No usage_events mirror rows found for this session.")

    return {
        "session_id": session_id,
        "attempted_db_connection": True,
        "source": source,
        "events_count": len(events),
        "summary": summary,
        "events": [_redact_usage_event(event) for event in events],
        "error": error_msg,
        "notes": notes,
    }


@router.get("/debug/usage-events-mismatch-check")
async def debug_usage_events_mismatch_check(
    request: Request,
    session_id: str,
    limit: str = "200",
    _: None = Depends(debug_access),
):
    """Debug-only: compare usage_events DB mirror state against SessionContext.

    Loads SessionContext read-only, then reads usage_events DB mirror state
    and returns only the sanitized comparison output. Never calls save_session.
    """
    from repositories.usage_events_repository import (
        list_usage_events_for_session,
        usage_event_summary_for_session,
    )
    from services.usage_events_mismatch_service import compare_usage_events_state

    data = _deps.get_session_data(session_id, getattr(request.state, "user_id", "") or "")
    session = data["session"]
    safe_limit = _safe_debug_limit(limit, default=200, minimum=1, maximum=500)

    comparison = None
    error_msg = None
    source = "db_compare"
    notes: list[str] = []

    try:
        with get_conn() as conn:
            db_events = list_usage_events_for_session(
                conn,
                session_id=session_id,
                limit=safe_limit,
            )
            db_summary = usage_event_summary_for_session(
                conn,
                session_id=session_id,
            )
            comparison = compare_usage_events_state(
                session=session,
                db_summary=db_summary,
                db_events=db_events,
            )
    except Exception as exc:
        source = "error"
        comparison = None
        error_msg = safe_debug_error_message(exc)
        notes.append("Usage-events DB mirror comparison failed. Check DB connectivity and schema.")

    if source == "db_compare":
        notes.append("Usage-events DB mirror comparison completed.")

    return {
        "session_id": session_id,
        "attempted_db_connection": True,
        "source": source,
        "matches": comparison.get("matches") if comparison is not None else None,
        "comparison": comparison,
        "error": error_msg,
        "notes": notes,
    }


@router.get("/debug/generated-learning-mismatch-check")
async def debug_generated_learning_mismatch_check(
    request: Request,
    session_id: str,
    legacy_topic_id: str,
    _: None = Depends(debug_access),
):
    """Debug-only: compare generated-learning DB mirror state against SessionContext.

    Loads SessionContext read-only, then reads generated-learning DB mirror state
    and returns only the sanitized comparison output. Never calls save_session.
    """
    from services.generated_learning_read_service import get_generated_learning_state_from_db
    from services.generated_learning_mismatch_service import compare_generated_learning_state

    data = _deps.get_session_data(session_id, getattr(request.state, "user_id", "") or "")
    session = data["session"]

    comparison = None
    error_msg = None
    source = "db_compare"
    notes: list[str] = []

    try:
        with get_conn() as conn:
            db_state = get_generated_learning_state_from_db(
                conn,
                session_id=session_id,
                legacy_topic_id=legacy_topic_id,
            )
            comparison = compare_generated_learning_state(
                session=session,
                legacy_topic_id=legacy_topic_id,
                db_state=db_state,
            )
    except Exception as exc:
        source = "error"
        comparison = None
        error_msg = safe_debug_error_message(exc)
        notes.append("Generated-learning DB mirror comparison failed. Check DB connectivity and schema.")

    if source == "db_compare":
        notes.append("Generated-learning DB mirror comparison completed.")

    return {
        "session_id": session_id,
        "legacy_topic_id": legacy_topic_id,
        "attempted_db_connection": True,
        "source": source,
        "matches": comparison.get("matches") if comparison is not None else None,
        "comparison": comparison,
        "error": error_msg,
        "notes": notes,
    }


@router.get("/debug/curriculum-db-check")
async def debug_curriculum_db_check(
    track_key: str = "aipm",
    legacy_topic_id: Optional[str] = None,
    _: None = Depends(debug_access),
):
    """Debug-only: attempt curriculum DB reads and report readiness.

    Returns only boolean flags, normalised row dicts, and human-readable notes.
    Never returns env var values, secrets, DB URLs, stack traces, or user data.
    Safe to call when AI2_CURRICULUM_DB_READS_ENABLED is off — no DB connection
    is opened in that case.
    """
    from services.storage_flags import is_curriculum_db_reads_enabled
    from services.curriculum_read_service import (
        get_track_by_key_from_db,
        get_topic_by_legacy_id_from_db,
    )
    from core.logging import safe_error_metadata

    reads_enabled = is_curriculum_db_reads_enabled()
    topic_id = legacy_topic_id or ""

    if not reads_enabled:
        return {
            "curriculum_db_reads_enabled": False,
            "attempted_db_connection": False,
            "track_key": track_key,
            "legacy_topic_id": topic_id,
            "track_found": False,
            "topic_found": False,
            "track": None,
            "topic": None,
            "source": "disabled",
            "error": None,
            "notes": [
                "Curriculum DB reads are disabled.",
                "Set AI2_CURRICULUM_DB_READS_ENABLED=1 to enable.",
            ],
        }

    track_row = None
    topic_row = None
    error_msg = None
    source = "db"

    try:
        with get_conn() as conn:
            track_row = get_track_by_key_from_db(conn, track_key)
            if topic_id:
                topic_row = get_topic_by_legacy_id_from_db(conn, topic_id)
    except Exception as exc:
        meta = safe_error_metadata(exc)
        error_msg = f"{meta['error_type']}: {meta['error_message']}"
        source = "error"
        track_row = None
        topic_row = None

    notes: list[str] = []
    if source == "db":
        notes.append("Curriculum DB reads are enabled.")
        if not topic_id:
            notes.append("No legacy_topic_id provided; topic lookup skipped.")
        elif topic_row is None:
            notes.append(f"No topic found for legacy_topic_id={topic_id!r}.")
        if track_row is None:
            notes.append(f"No track found for track_key={track_key!r}.")
    else:
        notes.append("DB read failed. Check DB connectivity and schema.")

    return {
        "curriculum_db_reads_enabled": True,
        "attempted_db_connection": True,
        "track_key": track_key,
        "legacy_topic_id": topic_id,
        "track_found": track_row is not None,
        "topic_found": topic_row is not None,
        "track": track_row,
        "topic": topic_row,
        "source": source,
        "error": error_msg,
        "notes": notes,
    }


@router.get("/debug/curriculum-fallback-check")
async def debug_curriculum_fallback_check(
    track_key: str = "aipm",
    legacy_topic_id: Optional[str] = None,
    include_topics: bool = False,
    _: None = Depends(debug_access),
):
    """Debug-only: inspect curriculum fallback reader behavior.

    Shows whether track, topic, and topics-list data come from DB or the
    existing syllabus helpers.  Safe to call when
    AI2_CURRICULUM_DB_READS_ENABLED is off — no DB connection is opened.
    Never returns secrets, env var values, DB URLs, stack traces, or user
    session data.
    """
    from services.storage_flags import is_curriculum_db_reads_enabled
    from services.curriculum_fallback_service import (
        get_track_with_fallback,
        get_topic_with_fallback,
        get_topics_for_track_with_fallback,
    )
    from core.logging import safe_error_metadata

    reads_enabled = is_curriculum_db_reads_enabled()
    topic_id      = legacy_topic_id or ""

    track_result:  dict | None = None
    topic_result:  dict | None = None
    topics_result: dict | None = None
    error_msg:     str  | None = None
    notes: list[str] = []

    if not reads_enabled:
        track_result = get_track_with_fallback(conn=None, track_key=track_key)
        if topic_id:
            topic_result = get_topic_with_fallback(conn=None, legacy_topic_id=topic_id)
        if include_topics:
            topics_result = get_topics_for_track_with_fallback(conn=None, track_key=track_key)
        notes.append(
            "AI2_CURRICULUM_DB_READS_ENABLED is off; all results from fallback."
        )
        return {
            "track_key":                   track_key,
            "legacy_topic_id":             topic_id,
            "include_topics":              include_topics,
            "curriculum_db_reads_enabled": False,
            "attempted_db_connection":     False,
            "track_result":                track_result,
            "topic_result":                topic_result,
            "topics_result":               topics_result,
            "source_summary": {
                "track_source":  track_result.get("source") if track_result else None,
                "topic_source":  topic_result.get("source") if topic_result else None,
                "topics_source": topics_result.get("source") if topics_result else None,
            },
            "error": None,
            "notes": notes,
        }

    try:
        with get_conn() as conn:
            track_result = get_track_with_fallback(conn=conn, track_key=track_key)
            if topic_id:
                topic_result = get_topic_with_fallback(conn=conn, legacy_topic_id=topic_id)
            if include_topics:
                topics_result = get_topics_for_track_with_fallback(conn=conn, track_key=track_key)
    except Exception as exc:
        meta      = safe_error_metadata(exc)
        error_msg = f"{meta['error_type']}: {meta['error_message']}"
        notes.append("DB connection failed; results unavailable.")

    return {
        "track_key":                   track_key,
        "legacy_topic_id":             topic_id,
        "include_topics":              include_topics,
        "curriculum_db_reads_enabled": True,
        "attempted_db_connection":     True,
        "track_result":                track_result,
        "topic_result":                topic_result,
        "topics_result":               topics_result,
        "source_summary": {
            "track_source":  track_result.get("source") if track_result else None,
            "topic_source":  topic_result.get("source") if topic_result else None,
            "topics_source": topics_result.get("source") if topics_result else None,
        },
        "error": error_msg,
        "notes": notes,
    }


@router.get("/debug/learner-state-db-check")
async def debug_learner_state_db_check(
    session_id: str = "",
    legacy_topic_id: Optional[str] = None,
    _: None = Depends(debug_access),
):
    """Debug-only: attempt learner-state DB reads and report readiness.

    Reads from topic_progress and todos mirrors via flag-gated service functions.
    Never returns raw env values, secrets, DB URLs, stack traces, or private session data.
    Safe to call when both read flags are off — no DB connection is opened in that case.
    """
    from services.storage_flags import (
        is_progress_db_reads_enabled,
        is_todos_db_reads_enabled,
    )
    from services.learner_state_read_service import (
        get_topic_progress_from_db,
        list_todos_from_db,
    )
    from core.logging import safe_error_metadata

    progress_enabled = is_progress_db_reads_enabled()
    todos_enabled    = is_todos_db_reads_enabled()
    topic_id         = legacy_topic_id or ""

    if not progress_enabled and not todos_enabled:
        return {
            "progress_db_reads_enabled": False,
            "todos_db_reads_enabled":    False,
            "attempted_db_connection":   False,
            "session_id":                session_id,
            "legacy_topic_id":           topic_id,
            "progress_found":            False,
            "todos_found":               False,
            "topic_progress":            None,
            "todos":                     None,
            "source":                    "disabled",
            "error":                     None,
            "notes": [
                "Learner-state DB reads are disabled.",
                "Set AI2_PROGRESS_DB_READS_ENABLED=1 or AI2_TODOS_DB_READS_ENABLED=1 to enable.",
            ],
        }

    topic_progress = None
    todos          = None
    error_msg      = None
    source         = "db"
    notes: list[str] = []

    try:
        with get_conn() as conn:
            if progress_enabled:
                if topic_id:
                    topic_progress = get_topic_progress_from_db(
                        conn,
                        session_id=session_id,
                        legacy_topic_id=topic_id,
                    )
                else:
                    notes.append(
                        "legacy_topic_id is required for topic progress DB check; "
                        "progress lookup skipped."
                    )
            if todos_enabled:
                todos = list_todos_from_db(conn, session_id=session_id)
    except Exception as exc:
        meta      = safe_error_metadata(exc)
        error_msg = f"{meta['error_type']}: {meta['error_message']}"
        source         = "error"
        topic_progress = None
        todos          = None

    if source == "db":
        active = []
        if progress_enabled:
            active.append("progress")
        if todos_enabled:
            active.append("todos")
        notes.insert(0, f"Learner-state DB reads enabled for: {', '.join(active)}.")
        if progress_enabled and topic_id and topic_progress is None:
            notes.append(f"No progress found for legacy_topic_id={topic_id!r}.")
        if todos_enabled and todos is not None and len(todos) == 0:
            notes.append("No todos found for this session.")
    else:
        notes.append("DB read failed. Check DB connectivity and schema.")

    return {
        "progress_db_reads_enabled": progress_enabled,
        "todos_db_reads_enabled":    todos_enabled,
        "attempted_db_connection":   True,
        "session_id":                session_id,
        "legacy_topic_id":           topic_id,
        "progress_found":            topic_progress is not None,
        "todos_found":               bool(todos),
        "topic_progress":            topic_progress,
        "todos":                     todos,
        "source":                    source,
        "error":                     error_msg,
        "notes":                     notes,
    }
