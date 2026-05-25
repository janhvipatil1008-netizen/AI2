"""Onboarding routes."""

import logging

import routes.deps as deps
from context.session import SessionContext
from database.pool import get_conn
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from services.learner_course_enrollment_service import ensure_course_enrollment

router = APIRouter()
logger = logging.getLogger(__name__)


def _onboarding_template_context(
    *,
    session_id: str,
    onboarding: dict | None = None,
    error: str = "",
) -> dict:
    return {
        "session_id": session_id,
        "onboarding": onboarding or {},
        "error": error,
        "goals": [
            ("aipm", "AI Product Manager"),
            ("ai_builder", "AI Builder"),
            ("interview_prep", "Interview Prep"),
        ],
        "levels": [
            ("beginner", "Beginner"),
            ("some_experience", "Some experience"),
            ("building_projects", "Building projects"),
            ("job_ready", "Job ready"),
        ],
        "weekly_times": [
            ("two_hours", "2 hours available"),
            ("five_hours", "5 hours available"),
            ("ten_hours", "10 hours available"),
        ],
        "test_mode": bool(deps.TEST_MODE),
    }


def _ensure_onboarding_course_enrollment(
    *,
    session: SessionContext,
    session_id: str,
    track_key: str | None,
) -> None:
    """Best-effort DB enrollment after onboarding; never blocks onboarding."""
    user_id = session.user_id or ""
    if not user_id or not session_id:
        return

    try:
        with get_conn() as conn:
            result = ensure_course_enrollment(
                conn,
                user_id=user_id,
                session_id=session_id,
                track_key=track_key,
                source="onboarding",
            )
            if result.get("source") == "error" or result.get("error"):
                raise RuntimeError("course enrollment failed")
    except Exception:
        logger.warning("onboarding course enrollment failed; continuing without DB enrollment")


@router.get("/onboarding/{session_id}", response_class=HTMLResponse)
async def onboarding_page(request: Request, session_id: str):
    data = deps.get_session_data(session_id, request.state.user_id or "")
    session: SessionContext = data["session"]
    return deps.templates.TemplateResponse(
        request=request,
        name="onboarding.html",
        context=_onboarding_template_context(
            session_id=session_id,
            onboarding=session.get_onboarding_profile(),
        ),
    )


@router.post("/onboarding/save")
async def onboarding_save(request: Request):
    form = await request.form()
    session_id = str(form.get("session_id", "")).strip()
    goal      = str(form.get("goal", "")).strip()
    level     = str(form.get("level", "")).strip()
    weekly_time = str(form.get("weekly_time", "")).strip()

    data = deps.get_session_data(session_id, request.state.user_id or "")
    session: SessionContext = data["session"]

    try:
        onboarding_profile = session.save_onboarding_profile(goal, level, weekly_time)
    except ValueError as exc:
        return deps.templates.TemplateResponse(
            request=request,
            name="onboarding.html",
            context=_onboarding_template_context(
                session_id=session_id,
                onboarding={
                    "goal":        goal,
                    "level":       level,
                    "weekly_time": weekly_time,
                },
                error=str(exc),
            ),
            status_code=422,
        )

    deps.save_session(session_id, session)
    _ensure_onboarding_course_enrollment(
        session=session,
        session_id=session_id,
        track_key=onboarding_profile.get("recommended_track"),
    )
    return RedirectResponse(url=f"/topics/{session_id}", status_code=302)
