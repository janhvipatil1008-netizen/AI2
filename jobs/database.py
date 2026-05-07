"""
AI² Job Search — jobs.db setup and query helpers.
Separate SQLite database; same raw sqlite3 pattern as app.py.
"""
import json
import os
import sqlite3
from pathlib import Path

_DB_DIR      = "." if os.getenv("AI2_TEST_MODE") == "1" else os.getenv("DB_DIR", "/data")
JOBS_DB_PATH = os.getenv("AI2_JOBS_DB", os.path.join(_DB_DIR, "jobs.db"))


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(JOBS_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create jobs and job_enrichments tables if they don't exist."""
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS jobs (
                id            TEXT PRIMARY KEY,
                external_id   TEXT UNIQUE NOT NULL,
                source        TEXT NOT NULL,
                title         TEXT NOT NULL,
                company       TEXT,
                location      TEXT,
                salary        TEXT,
                description   TEXT,
                date_posted   TEXT,
                job_url       TEXT NOT NULL,
                role_category TEXT,
                enriched      INTEGER DEFAULT 0,
                enriched_at   TEXT,
                created_at    TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_jobs_role     ON jobs(role_category);
            CREATE INDEX IF NOT EXISTS idx_jobs_enriched ON jobs(enriched);
            CREATE INDEX IF NOT EXISTS idx_jobs_created  ON jobs(created_at);

            CREATE TABLE IF NOT EXISTS job_enrichments (
                id                 TEXT PRIMARY KEY,
                job_id             TEXT NOT NULL REFERENCES jobs(id),
                summary            TEXT,
                skills_needed      TEXT,
                possible_questions TEXT,
                learning_guide     TEXT,
                quiz               TEXT,
                match_score        INTEGER,
                match_reasoning    TEXT,
                created_at         TEXT NOT NULL
            );
        """)


def get_jobs(
    role_category: str | None = None,
    limit: int = 20,
    only_enriched: bool = False,
    min_score: int = 0,
) -> list[dict]:
    """Return jobs ordered by match_score DESC, newest first."""
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
        sql += " AND j.role_category = ?"
        params.append(role_category)
    if only_enriched:
        sql += " AND j.enriched = 1"
    if min_score:
        sql += " AND (e.match_score >= ? OR e.match_score IS NULL)"
        params.append(min_score)

    sql += " ORDER BY e.match_score DESC, j.created_at DESC LIMIT ?"
    params.append(limit)

    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()

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
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if not row:
            return None
        job = dict(row)

        enr = conn.execute(
            "SELECT * FROM job_enrichments WHERE job_id = ?", (job_id,)
        ).fetchone()

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
        total    = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        enriched = conn.execute("SELECT COUNT(*) FROM jobs WHERE enriched=1").fetchone()[0]
        last     = conn.execute("SELECT MAX(created_at) FROM jobs").fetchone()[0]
    return {"total": total, "enriched": enriched, "pending": total - enriched, "last_fetch": last}
