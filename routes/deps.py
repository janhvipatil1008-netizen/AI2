"""Shared runtime dependencies for route modules. Populated by app.py at startup."""
from typing import Any, Callable

from fastapi import HTTPException, Request
from core.security_config import is_debug_access_allowed


def debug_access(request: Request) -> None:
    """FastAPI dependency: blocks debug/admin endpoints in production without a valid token."""
    if not is_debug_access_allowed(request):
        raise HTTPException(status_code=404, detail="Not found.")

templates:        Any      = None
get_session_data: Callable = None
get_user_history: Callable = None
get_user_sessions: Callable = None
load_profile_db:  Callable = None
save_exchange_to_history: Callable = None
save_profile_db: Callable = None
save_session:     Callable = None
session_progress: Callable = None
make_client:      Callable = None
run_blocking:     Callable = None
track_from_str:   Callable = None
mock_orchestrator_response: Callable = None
mock_responses:   dict     = {}
limiter:          Any      = None
CHAT_RATE_LIMIT:  str      = ""
PRACTICE_RATE_LIMIT: str   = ""
session_cache:    dict     = {}
TEST_MODE:        bool     = False


def write_through_topic_progress(
    session,
    *,
    session_id: str,
    user_id,
    legacy_topic_id: str,
) -> None:
    """Best-effort DB mirror of topic progress after a SessionContext save.

    Checks the feature flag first; returns immediately (no DB call) when off.
    Swallows all exceptions so a DB failure never breaks the user-facing request.
    """
    from services.write_through_service import is_db_write_through_enabled, maybe_write_topic_progress
    if not is_db_write_through_enabled():
        return
    from core.logging import get_logger, safe_error_metadata
    try:
        from database.pool import get_conn
        with get_conn() as conn:
            maybe_write_topic_progress(
                conn=conn,
                session=session,
                user_id=user_id or None,
                session_id=session_id,
                legacy_topic_id=legacy_topic_id,
            )
    except Exception as exc:
        get_logger("routes.write_through").warning(
            "write-through topic_progress failed: %s",
            safe_error_metadata(exc, topic_id=legacy_topic_id),
        )


def write_through_modular_progress_snapshot(
    session,
    *,
    session_id: str,
    user_id,
) -> None:
    """Best-effort DB mirror of calculated modular course progress.

    Uses the existing write-through flag. Swallows all exceptions so modular
    progress mirroring never blocks the learner-facing action.
    """
    from services.storage_flags import is_db_write_through_enabled
    if not is_db_write_through_enabled():
        return
    if not user_id or not session_id:
        return

    from core.logging import get_logger, safe_error_metadata
    try:
        from database.pool import get_conn
        from services.modular_progress_snapshot_service import (
            write_modular_progress_snapshot_safely,
        )
        with get_conn() as conn:
            result = write_modular_progress_snapshot_safely(
                conn=conn,
                user_id=str(user_id),
                session_id=session_id,
                session=session,
            )
            if result.get("error") and not result.get("skipped"):
                raise RuntimeError("modular progress snapshot failed")
    except Exception as exc:
        get_logger("routes.write_through").warning(
            "write-through modular progress snapshot failed: %s",
            safe_error_metadata(exc, session_id=session_id),
        )


def write_through_todos(
    session,
    *,
    session_id: str,
    user_id,
) -> None:
    """Best-effort DB mirror of todos after a SessionContext save.

    Checks the feature flag first; returns immediately (no DB call) when off.
    Swallows all exceptions so a DB failure never breaks the user-facing request.
    """
    from services.write_through_service import is_db_write_through_enabled, maybe_write_todos
    if not is_db_write_through_enabled():
        return
    from core.logging import get_logger, safe_error_metadata
    try:
        from database.pool import get_conn
        with get_conn() as conn:
            maybe_write_todos(
                conn=conn,
                session=session,
                user_id=user_id or None,
                session_id=session_id,
            )
    except Exception as exc:
        get_logger("routes.write_through").warning(
            "write-through todos failed: %s",
            safe_error_metadata(exc, session_id=session_id),
        )


def write_through_generated_learning_state(
    session,
    *,
    session_id: str | None,
    user_id: str | None,
    legacy_topic_id: str,
) -> None:
    """Best-effort DB mirror of generated-learning state after SessionContext save.

    Checks the feature flag first; returns immediately (no DB call) when off.
    Swallows all exceptions so a DB failure never breaks the user-facing request.
    """
    from services.storage_flags import is_db_write_through_enabled
    if not is_db_write_through_enabled() or not legacy_topic_id:
        return
    from core.logging import get_logger, safe_error_metadata
    try:
        from database.pool import get_conn
        from services.write_through_generated_learning_service import (
            maybe_write_generated_learning_state,
        )
        with get_conn() as conn:
            maybe_write_generated_learning_state(
                conn=conn,
                session=session,
                user_id=user_id or None,
                session_id=session_id,
                legacy_topic_id=legacy_topic_id,
            )
    except Exception as exc:
        get_logger("routes.write_through").warning(
            "write-through generated_learning failed: %s",
            safe_error_metadata(
                exc,
                session_id=session_id,
                topic_id=legacy_topic_id,
            ),
        )


def read_todos_with_fallback(
    session,
    *,
    session_id: str,
    user_id: str | None,
) -> list[dict]:
    """Return todos for a session, preferring DB when AI2_TODOS_DB_READS_ENABLED is on.

    - Flag off: returns SessionContext todos. No DB connection is opened.
    - Flag on:  opens one DB connection, calls the fallback service, closes it.
      If the DB read succeeds, returns DB todos.
      If the DB read fails, the fallback service returns SessionContext todos.
    - Connection errors: logs a safe warning and returns SessionContext todos.
    """
    from services.storage_flags import is_todos_db_reads_enabled
    from services.learner_state_fallback_service import list_todos_with_fallback

    if not is_todos_db_reads_enabled():
        result = list_todos_with_fallback(conn=None, session=session, session_id=session_id)
        return result["todos"]

    from core.logging import get_logger, safe_error_metadata
    try:
        from database.pool import get_conn
        with get_conn() as conn:
            result = list_todos_with_fallback(conn=conn, session=session, session_id=session_id)
            return result["todos"]
    except Exception as exc:
        get_logger("routes.todos_db_read").warning(
            "DB connection for todos read failed, using session fallback: %s",
            safe_error_metadata(exc, session_id=session_id),
        )
        return list(session.get_todos())


_PROGRESS_STEP_KEYS = frozenset({
    "learn", "quiz", "portfolio_task", "interview_practice", "reflection"
})


def read_topic_progress_with_fallback(
    session,
    *,
    session_id: str,
    user_id: str | None,
    legacy_topic_id: str,
) -> dict:
    """Return topic progress for one topic, preferring DB when AI2_PROGRESS_DB_READS_ENABLED is on.

    Returns {"topic_progress": steps_dict, "completion_percent": int}.
    Flag off: session methods called directly, no DB connection opened.
    Flag on: DB-first with fallback; connection errors log safely and fall back.
    """
    from services.storage_flags import is_progress_db_reads_enabled

    if not is_progress_db_reads_enabled():
        return {
            "topic_progress":     session.get_topic_progress(legacy_topic_id),
            "completion_percent": session.topic_completion_percent(legacy_topic_id),
        }

    from core.logging import get_logger, safe_error_metadata
    from services.learner_state_fallback_service import get_topic_progress_with_fallback
    try:
        from database.pool import get_conn
        with get_conn() as conn:
            result = get_topic_progress_with_fallback(
                conn=conn,
                session=session,
                session_id=session_id,
                legacy_topic_id=legacy_topic_id,
            )
            tp_raw = result["topic_progress"]
            steps  = {k: v for k, v in tp_raw.items() if k in _PROGRESS_STEP_KEYS}
            pct    = int(tp_raw.get("completion_percent", 0))
            return {"topic_progress": steps, "completion_percent": pct}
    except Exception as exc:
        get_logger("routes.progress_db_read").warning(
            "DB connection for topic progress read failed, using session fallback: %s",
            safe_error_metadata(exc, session_id=session_id, topic_id=legacy_topic_id),
        )
        return {
            "topic_progress":     session.get_topic_progress(legacy_topic_id),
            "completion_percent": session.topic_completion_percent(legacy_topic_id),
        }


def build_limit_enforcer(session):
    """Return a callable that raises AIActionLimitError when over the AI limit.

    Returns None when AI2_USAGE_LIMITS_ENABLED is off so callers can guard
    with `if limit_enforcer is not None` without importing the service.
    """
    from services.storage_flags import is_usage_limits_enabled
    if not is_usage_limits_enabled():
        return None
    from services.usage_limit_service import enforce_ai_action_limit
    return lambda: enforce_ai_action_limit(session)


def build_content_cache_fns(
    *,
    track_key: str | None,
    legacy_topic_id: str,
) -> tuple:
    """Return (read_fn, write_fn) callables for the shared content cache.

    Both callables wrap DB access in try/except so they never propagate.
    read_fn()              → dict | None
    write_fn(content, model) → None
    """
    from core.logging import get_logger, safe_error_metadata
    from services.content_cache_service import get_shared_cached_content, save_shared_cached_content

    def _read() -> dict | None:
        try:
            from database.pool import get_conn
            with get_conn() as conn:
                return get_shared_cached_content(
                    conn,
                    track_key=track_key,
                    legacy_topic_id=legacy_topic_id,
                    content_type="base_lesson",
                )
        except Exception as exc:
            get_logger("routes.content_cache").warning(
                "content_cache read failed, skipping: %s",
                safe_error_metadata(exc, topic_id=legacy_topic_id),
            )
            return None

    def _write(content: str, model: str | None = None) -> None:
        try:
            from database.pool import get_conn
            with get_conn() as conn:
                save_shared_cached_content(
                    conn,
                    track_key=track_key,
                    legacy_topic_id=legacy_topic_id,
                    content_type="base_lesson",
                    content=content,
                    model=model,
                )
        except Exception as exc:
            get_logger("routes.content_cache").warning(
                "content_cache write failed, content not cached: %s",
                safe_error_metadata(exc, topic_id=legacy_topic_id),
            )

    return (_read, _write)


def read_modular_progress_summary_safely(
    session,
    *,
    user_id: str | None,
    session_id: str | None,
) -> dict:
    """Return modular course progress summary with a safe disabled fallback.

    Never raises. Returns available=False on any error or missing data.
    """
    _empty: dict = {
        "source": "disabled",
        "available": False,
        "progress_percent": 0,
        "modules": [],
        "topics": [],
        "error": None,
    }
    if not user_id or not session_id or session is None:
        return _empty
    from core.logging import get_logger, safe_error_metadata
    try:
        from database.pool import get_conn
        from services.dashboard_modular_progress_service import (
            build_dashboard_modular_progress_summary,
        )
        track_key = session.track.value if getattr(session, "track", None) else None
        with get_conn() as conn:
            return build_dashboard_modular_progress_summary(
                conn,
                user_id=str(user_id),
                session_id=str(session_id),
                track_key=track_key,
            )
    except Exception as exc:
        get_logger("routes.modular_progress").warning(
            "modular progress read failed: %s",
            safe_error_metadata(exc, session_id=session_id),
        )
        return {**_empty, "source": "error_fallback"}


def write_through_usage_events(
    session,
    *,
    session_id: str | None,
    user_id: str | None,
    legacy_topic_id: str | None = None,
) -> None:
    """Best-effort DB mirror of usage_events after SessionContext save.

    Checks the feature flag first; returns immediately (no DB call) when off.
    Swallows all exceptions so a DB failure never breaks the user-facing request.
    """
    from services.storage_flags import is_db_write_through_enabled
    if not is_db_write_through_enabled():
        return
    from core.logging import get_logger, safe_error_metadata
    try:
        from database.pool import get_conn
        from services.write_through_usage_events_service import (
            maybe_write_usage_events,
            maybe_write_usage_events_for_topic,
        )
        with get_conn() as conn:
            if legacy_topic_id:
                maybe_write_usage_events_for_topic(
                    conn=conn,
                    session=session,
                    user_id=user_id or None,
                    session_id=session_id,
                    legacy_topic_id=legacy_topic_id,
                )
            else:
                maybe_write_usage_events(
                    conn=conn,
                    session=session,
                    user_id=user_id or None,
                    session_id=session_id,
                )
    except Exception as exc:
        get_logger("routes.write_through").warning(
            "write-through usage_events failed: %s",
            safe_error_metadata(
                exc,
                session_id=session_id,
                topic_id=legacy_topic_id,
            ),
        )
