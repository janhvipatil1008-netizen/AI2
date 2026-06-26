"""Course + role selection routes.

GET  /select-course/{session_id}  — render the two-level course/role picker
POST /select-course/{session_id}  — validate and save (course_key, role_key) to session,
                                    redirect to /topics/{session_id}

The (course_key, role_key) selection is stored in SessionContext.onboarding so it
persists across requests without a schema change.  topics.py reads it back when
building the filtered topic listing.

Flag AI2_MODULAR_CURRICULUM_READS_ENABLED is OFF by default; the picker is always
accessible (it only stores state), but the topic listing only uses the selection
when the flag is ON.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

import routes.deps as deps

router = APIRouter()


@router.get("/select-course/{session_id}", response_class=HTMLResponse)
async def course_select_page(request: Request, session_id: str):
    data    = deps.get_session_data(session_id, request.state.user_id or "")
    session = data["session"]

    selector = None
    selector_error = None
    try:
        import database.pool as pool
        from services.course_selector import get_selector_data
        with pool.get_conn() as conn:
            selector = get_selector_data(conn)
    except Exception as exc:
        selector_error = "Could not load course list — please try again."

    onboarding         = session.onboarding if isinstance(session.onboarding, dict) else {}
    current_course_key = onboarding.get("course_key", "")
    current_role_key   = onboarding.get("role_key", "")

    return deps.templates.TemplateResponse(
        request=request,
        name="course_select.html",
        context={
            "session_id":          session_id,
            "selector":            selector,
            "selector_error":      selector_error,
            "current_course_key":  current_course_key,
            "current_role_key":    current_role_key,
        },
    )


@router.post("/select-course/{session_id}")
async def course_select_save(request: Request, session_id: str):
    form      = await request.form()
    selection = str(form.get("selection", "")).strip()

    if ":" not in selection:
        return RedirectResponse(f"/select-course/{session_id}?error=pick_role", status_code=303)

    course_key, role_key = selection.split(":", 1)

    from services.course_selector import COURSE_ROLE_CONFIG
    valid_roles = {r["track_key"] for r in COURSE_ROLE_CONFIG.get(course_key, [])}
    if not course_key or role_key not in valid_roles:
        return RedirectResponse(f"/select-course/{session_id}?error=invalid", status_code=303)

    data    = deps.get_session_data(session_id, request.state.user_id or "")
    session = data["session"]
    if not isinstance(session.onboarding, dict):
        session.onboarding = {}
    session.onboarding["course_key"] = course_key
    session.onboarding["role_key"]   = role_key
    deps.save_session(session_id, session)

    return RedirectResponse(f"/topics/{session_id}", status_code=303)
