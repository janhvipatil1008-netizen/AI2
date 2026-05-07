"""
AI² Job Search — jobs query helpers (PostgreSQL via shared pool).
"""
import json

import psycopg2.extras

from database.pool import get_conn  # re-exported for fetcher/enricher backward compat

__all__ = ["get_conn", "init_db", "get_jobs", "get_job_with_enrichment", "get_stats"]


def init_db() -> None:
    """No-op: schema is created centrally by app.py _startup_db at launch."""
    pass


def get_jobs(
    role_category: str | None = None,
    limit: int = 20,
    only_enriched: bool = False,
    min_score: int = 0,
) -> list[dict]:
    """Return jobs ordered by match_score DESC NULLS LAST, newest first."""
    sql = """
        SELECT j.id, j.title, j.company, j.location, j.salary, j.job_url,
               j.source, j.role_category, j.date_posted, j.enriched, j.created_at,
               e.match_score, e.summary
        FROM jobs j
        LEFT JOIN job_enrichments e ON e.job_id = j.id
        WHERE 1=1
    """
    params: list = []

    if role_category:
        sql += " AND j.role_category = %s"
        params.append(role_category)
    if only_enriched:
        sql += " AND j.enriched = 1"
    if min_score:
        sql += " AND (e.match_score >= %s OR e.match_score IS NULL)"
        params.append(min_score)

    sql += " ORDER BY e.match_score DESC NULLS LAST, j.created_at DESC LIMIT %s"
    params.append(limit)

    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    result = []
    for row in rows:
        d = dict(row)
        if d.get("summary"):
            try:
                d["summary"] = json.loads(d["summary"])
            except Exception:
                d["summary"] = {}
        result.append(d)
    return result


def get_job_with_enrichment(job_id: str) -> dict | None:
    """Return a job dict with its enrichment sub-dict (or enrichment=None)."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM jobs WHERE id = %s", (job_id,))
            row = cur.fetchone()
            if not row:
                return None
            job = dict(row)

            cur.execute(
                "SELECT * FROM job_enrichments WHERE job_id = %s", (job_id,)
            )
            enr = cur.fetchone()

    if enr:
        e = dict(enr)
        for key in ["summary", "skills_needed", "possible_questions", "learning_guide", "quiz"]:
            if e.get(key):
                try:
                    e[key] = json.loads(e[key])
                except Exception:
                    pass
        job["enrichment"] = e
    else:
        job["enrichment"] = None

    return job


def get_stats() -> dict:
    """Return counts for the health endpoint."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM jobs")
            total = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM jobs WHERE enriched = 1")
            enriched = cur.fetchone()[0]
            cur.execute("SELECT MAX(created_at) FROM jobs")
            last = cur.fetchone()[0]
    return {"total": total, "enriched": enriched, "pending": total - enriched, "last_fetch": last}
