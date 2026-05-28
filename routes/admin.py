"""Admin routes for AI² — internal protected views.

Protected by debug_access dependency; returns 404 in production without a valid token.
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

import routes.deps as _deps
from database.pool import get_conn
from routes.deps import debug_access, safe_debug_error_message

router = APIRouter()


@router.get("/admin/beta-metrics", response_class=HTMLResponse)
async def admin_beta_metrics(
    request: Request,
    _: None = Depends(debug_access),
):
    """Simple protected internal view for private beta aggregate metrics."""
    from core.logging import get_logger
    from services.beta_metrics_service import build_beta_metrics_payload

    logger = get_logger("routes.admin")

    db_available = False
    db_metrics = None
    try:
        from repositories.beta_metrics_repository import collect_beta_metrics

        with get_conn() as conn:
            db_metrics = collect_beta_metrics(conn)
        db_available = True
    except Exception as exc:
        logger.warning("beta metrics unavailable: %s", safe_debug_error_message(exc))

    metrics = build_beta_metrics_payload(
        db_available=db_available,
        db_metrics=db_metrics,
    )
    return _deps.templates.TemplateResponse(
        request=request,
        name="beta_metrics.html",
        context={
            "metrics": metrics,
            "test_mode": bool(_deps.TEST_MODE),
        },
    )
