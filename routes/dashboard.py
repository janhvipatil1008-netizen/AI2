"""Dashboard routes."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

import routes.deps as deps
from config import CareerTrack, TRACK_DISPLAY_NAMES, TRACK_TAGLINES
from context.session import SessionContext
from curriculum.topics import get_topics_for_week
from database.pool import _connect as _open_db_connection, get_conn
from services.dashboard_modular_progress_service import (
    build_dashboard_modular_progress_summary,
)
from services.learner_course_enrollment_service import (
    get_active_course_enrollment_with_fallback,
    normalize_course_key,
    summarize_enrollment_progress,
)
from services.modular_position_service import (
    build_legacy_position_fallback,
    build_position_summary,
)

router = APIRouter()


def build_dashboard_learning_summary(session, topics=None) -> dict:
    """Compute a quick learner stats dict for the dashboard. Pure - no Claude calls.

    Pass `topics` explicitly to count progress against a specific topic list
    (e.g. the v3 core-then-branch set).  When None the static curriculum for
    the session's track/week is used — flag-OFF callers need not change.
    """
    track = session.track.value
    current_week = session.current_week
    if topics is None:
        topics = get_topics_for_week(track, current_week)
    total_topics = len(topics)

    pcts = [session.topic_completion_percent(t.topic_id) for t in topics]
    tp_maps = [session.get_topic_progress(t.topic_id) for t in topics]

    completed = sum(1 for p in pcts if p == 100)
    in_progress = sum(
        1
        for p, tp in zip(pcts, tp_maps)
        if p < 100 and (p > 0 or "in_progress" in tp.values())
    )
    not_started = total_topics - completed - in_progress
    avg_pct = round(sum(pcts) / total_topics) if total_topics else 0

    counts = session.todo_counts()
    daily_count = len(session.get_todos("daily"))
    weekly_count = len(session.get_todos("weekly"))

    quiz_done = sum(1 for v in session.quiz_submissions.values() if v.get("evaluation"))
    portfolio_done = sum(
        1 for v in session.portfolio_submissions.values() if v.get("feedback")
    )
    interview_done = sum(
        1 for v in session.interview_submissions.values() if v.get("feedback")
    )
    reflections = sum(
        1
        for v in session.topic_notes.values()
        if v.get("reflection") or v.get("confusions") or v.get("application_idea")
    )

    return {
        "current_week": current_week,
        "total_topics": total_topics,
        "completed_topics": completed,
        "in_progress_topics": in_progress,
        "not_started_topics": not_started,
        "average_completion_percent": avg_pct,
        "total_todos": counts["total"],
        "daily_todos": daily_count,
        "weekly_todos": weekly_count,
        "done_todos": counts.get("done", 0),
        "in_progress_todos": counts.get("in_progress", 0),
        "quiz_evaluations_done": quiz_done,
        "portfolio_reviews_done": portfolio_done,
        "interview_feedback_done": interview_done,
        "reflections_saved": reflections,
        "usage_summary": session.usage_summary(),
    }


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    user_id = request.state.user_id or "test-user"

    display_name = "Learner"
    if not deps.TEST_MODE:
        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT display_name FROM users WHERE user_id = %s", (user_id,)
                    )
                    row = cur.fetchone()
            if row:
                display_name = row[0] or display_name
        except Exception:
            pass

    recent_sessions = deps.get_user_sessions(user_id, limit=5)
    profile = deps.load_profile_db(user_id)

    # Build learning summary from the most recent session
    recent_session = None
    recent_session_id = None
    if recent_sessions:
        recent_session_id = recent_sessions[0]["session_id"]
        try:
            recent_session = deps.get_session_data(recent_session_id, user_id)["session"]
        except Exception:
            recent_session = None
    elif deps.TEST_MODE and deps.session_cache:
        recent_session_id = list(deps.session_cache.keys())[-1]
        recent_session = deps.session_cache[recent_session_id]["session"]
        recent_sessions = [
            {
                "session_id": recent_session_id,
                "track": recent_session.track.value,
                "current_week": recent_session.current_week,
                "updated_at": "",
            }
        ]

    summary_topics = _v3_summary_topics(recent_session) if recent_session else None
    learning_summary = (
        build_dashboard_learning_summary(recent_session, topics=summary_topics)
        if recent_session else None
    )
    enrollment_user_id = ""
    if recent_session is not None:
        enrollment_user_id = recent_session.user_id or ("" if deps.TEST_MODE else user_id)
    enrollment_summary, modular_progress_summary = _dashboard_db_summaries(
        user_id=enrollment_user_id,
        session_id=recent_session_id,
        session=recent_session,
    )

    if modular_progress_summary.get("available"):
        _cp = {
            **modular_progress_summary,
            "unassigned_topics": modular_progress_summary.get("topics", []),
        }
        _raw = build_position_summary(_cp)
        position_summary = {
            "available": True,
            "current_topic_key": _raw["current"].get("topic_key"),
            "current_module_key": _raw["current"].get("module_key"),
            "next_topic_key": _raw["next"].get("topic_key")
            if _raw.get("has_next")
            else None,
            "progress_percent": _raw.get("course_progress_percent", 0),
            "source": "modular",
        }
    else:
        _fb = build_legacy_position_fallback(recent_session)
        position_summary = {
            "available": False,
            "current_module_label": _fb.get("current_module_label"),
            "source": _fb.get("source", "disabled"),
        }

    tracks = [
        {
            "value": str(t.value),
            "label": str(TRACK_DISPLAY_NAMES[t]),
            "tagline": str(TRACK_TAGLINES[t]),
        }
        for t in CareerTrack
    ]

    stats = {
        "session_count": profile.session_count if profile else 0,
        "total_quizzes": profile.total_quizzes if profile else 0,
        "topics_mastered": len(profile.topics_mastered) if profile else 0,
        "total_exchanges": profile.total_exchanges if profile else 0,
    }

    return deps.templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "display_name": display_name,
            "recent_sessions": recent_sessions,
            "tracks": tracks,
            "stats": stats,
            "learning_summary": learning_summary,
            "enrollment_summary": enrollment_summary,
            "modular_progress_summary": modular_progress_summary,
            "position_summary": position_summary,
            "recent_session_id": recent_session_id,
            "test_mode": bool(deps.TEST_MODE),
        },
    )


def _v3_summary_topics(session) -> list | None:
    """Return the v3 topic list for the session's selected course/role, or None.

    Returns None (→ static fallback) when:
    - the flag is OFF
    - the session has no (course_key, role_key) in onboarding
    - the DB lookup fails or returns an empty list
    """
    from services.storage_flags import is_modular_curriculum_reads_enabled
    if not is_modular_curriculum_reads_enabled():
        return None
    onboarding = session.onboarding if isinstance(session.onboarding, dict) else {}
    course_key = onboarding.get("course_key") or None
    role_key   = onboarding.get("role_key")   or None
    if not (course_key and role_key):
        return None
    try:
        import database.pool as pool
        from services.modular_curriculum_fallback_service import get_course_structure_with_fallback
        from services.modular_topic_adapter import course_structure_to_role_topic_cards
        with pool.get_conn() as conn:
            result = get_course_structure_with_fallback(
                conn, course_key=course_key, fallback_track_key=None
            )
        cs = result.get("course_structure")
        topics = course_structure_to_role_topic_cards(cs, track_key=role_key, role_key=role_key) if cs else []
        return topics or None
    except Exception:
        return None


def _dashboard_enrollment_summary(
    *,
    user_id: str | None,
    session_id: str | None,
    session: SessionContext | None,
    conn=None,
) -> dict:
    disabled = _disabled_dashboard_enrollment_summary(session)
    if not user_id or not session_id or session is None:
        return disabled

    track_key = session.track.value if getattr(session, "track", None) else None
    course_key = normalize_course_key(track_key)
    owns_conn = conn is None
    try:
        if conn is None:
            conn = _open_db_connection()
        result = get_active_course_enrollment_with_fallback(
            conn,
            user_id=user_id,
            session_id=session_id,
            track_key=track_key,
        )
        summary = summarize_enrollment_progress(enrollment=result.get("enrollment"))
        return {
            "source": result.get("source") or "fallback",
            "course_key": summary.get("course_key") or course_key,
            "status": summary.get("status") or "active",
            "progress_percent": int(summary.get("progress_percent") or 0),
            "current_module_key": summary.get("current_module_key"),
            "current_topic_key": summary.get("current_topic_key"),
            "current_legacy_topic_id": summary.get("current_legacy_topic_id"),
            "error": None,
        }
    except Exception:
        return {
            **disabled,
            "source": "error_fallback",
        }
    finally:
        if owns_conn and conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def _disabled_dashboard_enrollment_summary(session: SessionContext | None) -> dict:
    track_key = session.track.value if session and getattr(session, "track", None) else None
    course_key = normalize_course_key(track_key)
    return {
        "source": "disabled",
        "course_key": course_key,
        "status": "active",
        "progress_percent": 0,
        "current_module_key": None,
        "current_topic_key": None,
        "current_legacy_topic_id": None,
        "error": None,
    }


def _disabled_dashboard_modular_progress_summary() -> dict:
    return {
        "source": "disabled",
        "available": False,
        "progress_percent": 0,
        "modules": [],
        "topics": [],
        "error": None,
    }


def _dashboard_db_summaries(
    *,
    user_id: str | None,
    session_id: str | None,
    session: SessionContext | None,
) -> tuple[dict, dict]:
    enrollment_summary = _disabled_dashboard_enrollment_summary(session)
    modular_summary = _disabled_dashboard_modular_progress_summary()
    if not user_id or not session_id or session is None:
        return enrollment_summary, modular_summary

    conn = None
    try:
        conn = _open_db_connection()
        enrollment_summary = _dashboard_enrollment_summary(
            user_id=user_id,
            session_id=session_id,
            session=session,
            conn=conn,
        )
        track_key = session.track.value if getattr(session, "track", None) else None
        modular_summary = build_dashboard_modular_progress_summary(
            conn,
            user_id=user_id,
            session_id=session_id,
            track_key=track_key,
        )
    except Exception:
        modular_summary = {
            **_disabled_dashboard_modular_progress_summary(),
            "source": "error_fallback",
        }
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    return enrollment_summary, modular_summary
