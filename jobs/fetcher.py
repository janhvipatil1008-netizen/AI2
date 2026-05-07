"""
AI² Job Search — job fetcher using python-jobspy.
Scrapes Indeed and Google Jobs (free, no proxies needed).
Covers India + Remote + US + UK for broad AI role discovery.
"""
import hashlib
import logging
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Broad AI role categories with search terms
SEARCH_TERMS: dict[str, list[str]] = {
    "ai_engineer":   ["AI Engineer", "ML Engineer", "LLM Engineer", "GenAI Engineer"],
    "ai_pm":         ["AI Product Manager", "AI PM", "LLM Product Manager", "GenAI Product Manager"],
    "ai_researcher": ["AI Research Scientist", "NLP Engineer", "ML Researcher"],
    "ai_infra":      ["RAG Engineer", "Prompt Engineer", "Context Engineer", "AI Infrastructure Engineer"],
    "ai_evals":      ["AI Evaluations Engineer", "LLM Evals", "AI Quality Engineer", "Model Evaluation Engineer"],
    "data_ai":       ["AI Data Scientist", "ML Data Scientist", "AI Analyst"],
    "ai_solutions":  ["AI Solutions Architect", "AI Consultant", "AI Strategist"],
}

# Search all locations for global + remote coverage
SEARCH_LOCATIONS = ["India", "Remote", "United States", "United Kingdom"]


def compute_external_id(job_url: str) -> str:
    """SHA-256 of job_url → first 16 hex chars. Used for dedup."""
    return hashlib.sha256(job_url.encode()).hexdigest()[:16]


def _scrape_one(term: str, location: str, hours_old: int = 72) -> list[dict]:
    """Run JobSpy for a single search term + location. Returns raw row dicts."""
    from jobspy import scrape_jobs  # lazy import — not needed at startup

    try:
        df = scrape_jobs(
            site_name=["indeed", "google"],
            search_term=term,
            location=location,
            results_wanted=20,
            hours_old=hours_old,
            description_format="markdown",
        )
        if df is None or df.empty:
            logger.info(f"  '{term}' @ {location}: 0 results")
            return []
        logger.info(f"  '{term}' @ {location}: {len(df)} results")
        return [dict(row) for _, row in df.iterrows()]
    except Exception as exc:
        logger.warning(f"  '{term}' @ {location} failed: {exc}")
        return []


def fetch_and_store(category: str = "all") -> dict:
    """
    Fetch jobs for a category (or 'all') across all locations.
    Inserts new jobs into jobs.db, skips duplicates via external_id.
    Returns: {"fetched": N, "new": N, "skipped": N}
    """
    from jobs.database import get_conn, init_db

    init_db()

    # ── Prune stale rows before fetching new ones ─────────────────────────────
    with get_conn() as conn:
        cur     = conn.execute("DELETE FROM jobs WHERE created_at < datetime('now', '-7 days')")
        deleted = cur.rowcount
        conn.execute("DELETE FROM job_enrichments WHERE job_id NOT IN (SELECT id FROM jobs)")
    if deleted:
        logger.info(f"Pruned {deleted} stale job(s) older than 7 days")

    cats = list(SEARCH_TERMS.keys()) if category == "all" else [category]
    fetched = new = skipped = 0

    for cat in cats:
        logger.info(f"Fetching category: {cat}")
        seen_urls: set[str] = set()

        for location in SEARCH_LOCATIONS:
            for term in SEARCH_TERMS[cat]:
                raw_jobs = _scrape_one(term, location)
                fetched += len(raw_jobs)

                with get_conn() as conn:
                    for job in raw_jobs:
                        url = str(job.get("job_url") or "").strip()
                        if not url or url in seen_urls:
                            skipped += 1
                            continue
                        seen_urls.add(url)

                        ext_id = compute_external_id(url)
                        exists = conn.execute(
                            "SELECT 1 FROM jobs WHERE external_id = ?", (ext_id,)
                        ).fetchone()
                        if exists:
                            skipped += 1
                            continue

                        # Cap description to 10 000 chars to keep DB lean
                        desc = str(job.get("description") or "")[:10_000]

                        conn.execute(
                            """INSERT INTO jobs
                               (id, external_id, source, title, company, location,
                                salary, description, date_posted, job_url,
                                role_category, created_at)
                               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                            (
                                str(uuid.uuid4()),
                                ext_id,
                                str(job.get("site") or "unknown"),
                                str(job.get("title") or "").strip(),
                                str(job.get("company") or "").strip(),
                                str(job.get("location") or location).strip(),
                                str(job.get("min_amount") or "").strip(),
                                desc,
                                str(job.get("date_posted") or "").strip(),
                                url,
                                cat,
                                datetime.now(timezone.utc).isoformat(),
                            ),
                        )
                        new += 1

    logger.info(f"Fetch complete — fetched={fetched}, new={new}, skipped={skipped}")
    return {"fetched": fetched, "new": new, "skipped": skipped}
