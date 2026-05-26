"""Job search routes."""

import asyncio
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

import routes.deps as deps

logger = logging.getLogger("app")
router = APIRouter()


# Import jobs DB helpers - schema is created centrally by app.py via schema.sql.
try:
    from jobs.database import (
        get_jobs as _get_jobs,
        get_job_with_enrichment as _get_job_detail,
        get_stats as _get_jobs_stats,
    )
except Exception as _jobs_db_err:
    logger.warning(f"jobs helpers import failed: {_jobs_db_err}")


@router.get("/jobs", response_class=HTMLResponse)
async def jobs_page(request: Request):
    """Job list page - shows all fetched jobs with match scores."""
    user_id = request.state.user_id or "test-user"
    try:
        jobs = _get_jobs(limit=50)
    except Exception:
        jobs = []
    try:
        stats = _get_jobs_stats()
    except Exception:
        stats = {"total": 0, "enriched": 0, "pending": 0, "last_fetch": None}
    return deps.templates.TemplateResponse(
        request=request,
        name="jobs.html",
        context={
            "jobs":      jobs,
            "stats":     stats,
            "test_mode": bool(deps.TEST_MODE),
        },
    )


@router.get("/jobs/{job_id}", response_class=HTMLResponse)
async def job_detail_page(request: Request, job_id: str):
    """Job detail page - shows enriched JD analysis or triggers enrichment."""
    try:
        job = _get_job_detail(job_id)
    except Exception:
        job = None
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return deps.templates.TemplateResponse(
        request=request,
        name="job_detail.html",
        context={
            "job":       job,
            "test_mode": bool(deps.TEST_MODE),
        },
    )


@router.get("/api/jobs/health")
async def jobs_health():
    """Returns job DB stats - no auth required."""
    try:
        return {"status": "ok", **_get_jobs_stats()}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


@router.post("/api/jobs/enrich/{job_id}")
async def enrich_job_endpoint(job_id: str, request: Request):
    """Trigger on-demand enrichment for a single job. Returns enrichment data."""
    session_id = request.query_params.get("session_id")
    learner_context = None
    if session_id:
        try:
            s = deps.get_session_data(session_id, request.state.user_id or "")["session"]
            learner_context = {
                "track":           s.track.value,
                "current_week":    s.current_week,
                "background":      "; ".join(s.goals[:3]) if s.goals else "",
                "goals":           s.goals,
                "quiz_scores":     s.quiz_scores,
                "topics_explored": sorted(s.topics_explored)[:10],
            }
        except Exception:
            pass

    from jobs.enricher import enrich_job
    try:
        data = await deps.run_blocking(enrich_job, job_id, learner_context=learner_context)
        return {"status": "ok", "job_id": job_id, "match_score": data.get("match_score"), "data": data}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/api/jobs/refresh")
async def refresh_jobs(category: str = "all"):
    """Trigger a job fetch run in the background. Returns immediately."""
    from jobs.fetcher import fetch_and_store

    async def _bg():
        try:
            result = await deps.run_blocking(fetch_and_store, category)
            logger.info(f"Background job fetch: {result}")
        except Exception as exc:
            logger.error(f"Background job fetch failed: {exc}")

    asyncio.create_task(_bg())
    return {"status": "queued", "message": f"Fetching '{category}' jobs in background"}
