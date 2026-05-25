"""Public routes — no auth, no session, no DB required."""

import routes.deps as deps
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok", "test_mode": deps.TEST_MODE}


@router.get("/privacy", response_class=HTMLResponse)
async def privacy_page(request: Request):
    return deps.templates.TemplateResponse(
        request=request,
        name="privacy.html",
        context={"test_mode": bool(deps.TEST_MODE)},
    )


@router.get("/terms", response_class=HTMLResponse)
async def terms_page(request: Request):
    return deps.templates.TemplateResponse(
        request=request,
        name="terms.html",
        context={"test_mode": bool(deps.TEST_MODE)},
    )


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    if deps.TEST_MODE or request.state.user_id:
        return RedirectResponse(url="/dashboard", status_code=302)
    return RedirectResponse(url="/login", status_code=302)
