"""
AI² Job Search — on-demand Claude enrichment for job descriptions.
One API call per JD returns 5 structured outputs as a JSON blob.
Called from the /jobs/{job_id} route when user first opens a job card.
"""
import json
import logging
import uuid
from datetime import datetime, timezone

import anthropic

from config import AGENT_MODEL

logger = logging.getLogger(__name__)

# ── Enrichment prompt ─────────────────────────────────────────────────────────
# Single call → all 5 outputs. Learner profile personalises match_score,
# you_already_have, gap_to_close, and from_your_syllabus.

ENRICHMENT_PROMPT = """\
You are an AI career coach enriching a job description for a specific learner on the AI² platform.

LEARNER PROFILE:
Track: {track}
Week: {current_week}/5
Background / goals: {goals}
Topics mastered: {topics_mastered}
Topics still building: {topics_struggling}

JOB POSTING:
Title: {title}
Company: {company}
Source: {source}
Full description:
{description}

Return ONLY a valid JSON object — no markdown fences, no explanation outside JSON.

{{
  "summary": {{
    "role_in_one_line": "string",
    "what_you_will_do": ["string", "string", "string"],
    "company_signal": "string — company stage, culture, AI maturity",
    "red_flags": ["string"],
    "green_flags": ["string"]
  }},
  "skills_needed": {{
    "must_have": ["string"],
    "nice_to_have": ["string"],
    "you_already_have": ["string — only if genuinely in learner's mastered list"],
    "gap_to_close": ["string — honest gap, specific not generic"]
  }},
  "possible_questions": [
    {{
      "question": "string",
      "type": "behavioral|technical|system design|case study",
      "why_they_ask": "string",
      "strong_answer_structure": "string — STAR or named framework"
    }}
  ],
  "learning_guide": {{
    "priority_topics": ["string"],
    "projects_to_reference": ["string — specific Agri-Saathi or AI² curriculum talking points"],
    "from_your_syllabus": ["string — e.g. Week 2 Day 4 covers X directly"]
  }},
  "quiz": [
    {{
      "question": "string",
      "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
      "correct": "A",
      "explanation": "string",
      "difficulty": "beginner|intermediate|advanced"
    }}
  ],
  "match_score": 74,
  "match_reasoning": "string — 1-2 honest sentences explaining the score"
}}

Include exactly 5 possible_questions and 5 quiz items.
match_score is 0-100 vs learner's current mastery (be realistic, not inflated).\
"""


def enrich_job(job_id: str, session=None) -> dict:
    """
    Enrich a single job synchronously. Saves result to jobs.db.
    Returns the enrichment data dict.

    session: optional SessionContext — used to personalise match_score.
             If None, uses generic learner defaults.
    """
    from jobs.database import get_conn

    with get_conn() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()

    if not row:
        raise ValueError(f"Job {job_id} not found in jobs.db")

    row = dict(row)

    # ── Build learner context ─────────────────────────────────────────────────
    if session is not None:
        from config import TRACK_DISPLAY_NAMES
        track        = TRACK_DISPLAY_NAMES.get(session.track, session.track.value)
        current_week = session.current_week
        goals        = ", ".join(session.goals[:3]) if session.goals else "land an AI role"
        mastered     = ", ".join(sorted(session.topics_explored)[:6]) if session.topics_explored else "AI fundamentals"
        struggling   = "advanced topics — still building"
    else:
        track        = row.get("role_category", "AI role")
        current_week = 1
        goals        = "land an AI role"
        mastered     = "AI fundamentals"
        struggling   = "advanced topics"

    description = (row.get("description") or "")[:6_000]   # cap to avoid token overflow

    prompt = ENRICHMENT_PROMPT.format(
        track=track,
        current_week=current_week,
        goals=goals,
        topics_mastered=mastered,
        topics_struggling=struggling,
        title=row.get("title", ""),
        company=row.get("company") or "Unknown",
        source=row.get("source", ""),
        description=description,
    )

    client = anthropic.Anthropic()

    # ── Claude call ───────────────────────────────────────────────────────────
    response = client.messages.create(
        model=AGENT_MODEL,
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # One retry with an explicit correction nudge
        logger.warning(f"JSON parse failed for job {job_id} — retrying")
        retry = client.messages.create(
            model=AGENT_MODEL,
            max_tokens=2000,
            messages=[
                {"role": "user",      "content": prompt},
                {"role": "assistant", "content": raw},
                {"role": "user",      "content": "That was not valid JSON. Return ONLY the raw JSON object — no markdown, no explanation."},
            ],
        )
        data = json.loads(retry.content[0].text.strip())

    cost = (response.usage.input_tokens * 3 + response.usage.output_tokens * 15) / 1_000_000
    logger.info(f"Enriched job {job_id}: match_score={data.get('match_score')}, cost≈${cost:.4f}")

    # ── Persist to jobs.db ────────────────────────────────────────────────────
    enrichment_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    from jobs.database import get_conn
    with get_conn() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO job_enrichments
               (id, job_id, summary, skills_needed, possible_questions,
                learning_guide, quiz, match_score, match_reasoning, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                enrichment_id,
                job_id,
                json.dumps(data.get("summary", {})),
                json.dumps(data.get("skills_needed", {})),
                json.dumps(data.get("possible_questions", [])),
                json.dumps(data.get("learning_guide", {})),
                json.dumps(data.get("quiz", [])),
                int(data.get("match_score", 0)),
                str(data.get("match_reasoning", "")),
                now,
            ),
        )
        conn.execute(
            "UPDATE jobs SET enriched=1, enriched_at=? WHERE id=?",
            (now, job_id),
        )

    return data
