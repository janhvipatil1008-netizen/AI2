"""Debug routes for AI² — config-only and storage-health endpoints.

Protected by debug_access dependency; returns 404 in production without a valid token.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse

import routes.deps as _deps
from routes.deps import debug_access, safe_debug_error_message
from context.session import SessionContext

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
