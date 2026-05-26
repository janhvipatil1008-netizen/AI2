"""Tests for jobs route module split."""

from __future__ import annotations

import os
from pathlib import Path

os.environ["AI2_TEST_MODE"] = "1"
os.environ["ANTHROPIC_API_KEY"] = "test-key"

from fastapi.testclient import TestClient

import app as app_module
import routes.jobs as jobs_module


client = TestClient(app_module.app)


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def _routes() -> set[tuple[str, str]]:
    return {
        (route.path, ",".join(sorted(getattr(route, "methods", set()) or [])))
        for route in app_module.app.routes
        if hasattr(route, "methods")
    }


def test_jobs_py_exists_and_defines_router():
    source = _read("routes/jobs.py")
    assert "router = APIRouter()" in source
    assert '@router.get("/jobs", response_class=HTMLResponse)' in source
    assert '@router.get("/jobs/{job_id}", response_class=HTMLResponse)' in source
    assert '@router.get("/api/jobs/health")' in source
    assert '@router.post("/api/jobs/enrich/{job_id}")' in source
    assert '@router.post("/api/jobs/refresh")' in source


def test_app_includes_jobs_router():
    source = _read("app.py")
    assert "from routes.jobs import router as jobs_router" in source
    assert "app.include_router(jobs_router)" in source


def test_jobs_route_urls_unchanged():
    routes = _routes()
    assert ("/jobs", "GET") in routes
    assert ("/jobs/{job_id}", "GET") in routes
    assert ("/api/jobs/health", "GET") in routes
    assert ("/api/jobs/enrich/{job_id}", "POST") in routes
    assert ("/api/jobs/refresh", "POST") in routes


def test_jobs_page_still_loads_with_fallback_on_db_failure(monkeypatch):
    def _raise(*args, **kwargs):
        raise RuntimeError("db unavailable")

    monkeypatch.setattr(jobs_module, "_get_jobs", _raise, raising=False)
    monkeypatch.setattr(jobs_module, "_get_jobs_stats", _raise, raising=False)

    response = client.get("/jobs")

    assert response.status_code == 200
    assert "Find Your Next AI Role" in response.text
    assert "No jobs yet" in response.text


def test_jobs_page_still_renders_jobs_and_stats(monkeypatch):
    monkeypatch.setattr(
        jobs_module,
        "_get_jobs",
        lambda limit=50: [
            {
                "id": "job-1",
                "title": "AI Product Manager",
                "company": "Acme AI",
                "location": "Remote",
                "source": "Indeed",
                "role_category": "ai_pm",
                "match_score": 88,
                "summary": {"role_in_one_line": "Own AI product workflows."},
            }
        ],
        raising=False,
    )
    monkeypatch.setattr(
        jobs_module,
        "_get_jobs_stats",
        lambda: {"total": 1, "enriched": 1, "pending": 0, "last_fetch": None},
        raising=False,
    )

    response = client.get("/jobs")

    assert response.status_code == 200
    assert "AI Product Manager" in response.text
    assert "Acme AI" in response.text
    assert "88% match" in response.text


def test_job_detail_404_behavior_is_preserved(monkeypatch):
    monkeypatch.setattr(jobs_module, "_get_job_detail", lambda job_id: None, raising=False)

    response = client.get("/jobs/missing")

    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found"


def test_jobs_health_behavior_is_preserved(monkeypatch):
    monkeypatch.setattr(
        jobs_module,
        "_get_jobs_stats",
        lambda: {"total": 3, "enriched": 2, "pending": 1, "last_fetch": None},
        raising=False,
    )

    response = client.get("/api/jobs/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "total": 3,
        "enriched": 2,
        "pending": 1,
        "last_fetch": None,
    }


def test_app_no_longer_defines_jobs_route_handlers_directly():
    source = _read("app.py")
    assert '@app.get("/jobs"' not in source
    assert '@app.get("/jobs/{job_id}"' not in source
    assert '@app.get("/api/jobs/health")' not in source
    assert '@app.post("/api/jobs/enrich/{job_id}")' not in source
    assert '@app.post("/api/jobs/refresh")' not in source


def test_non_jobs_routes_not_moved_in_this_step():
    app_source = _read("app.py")
    jobs_source = _read("routes/jobs.py")

    assert "from routes.public import router as public_router" in app_source
    assert "from routes.auth_routes import router as auth_router" in app_source
    assert "from routes.dashboard import router as dashboard_router" in app_source
    assert "from routes.onboarding import router as onboarding_router" in app_source
    assert "from routes.syllabus import router as syllabus_router" in app_source
    assert '@app.get("/debug/storage-status")' in app_source
    assert '@app.post("/chat")' in app_source

    assert '"/login"' not in jobs_source
    assert '"/dashboard"' not in jobs_source
    assert '"/onboarding/' not in jobs_source
    assert '"/syllabus/{session_id}"' not in jobs_source
    assert '"/debug/' not in jobs_source
    assert '"/chat"' not in jobs_source
