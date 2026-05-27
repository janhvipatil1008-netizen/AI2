"""Debug routes for AI² — config-only endpoints (no DB connections).

Protected by debug_access dependency; returns 404 in production without a valid token.
"""

from fastapi import APIRouter, Depends

from routes.deps import debug_access

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
