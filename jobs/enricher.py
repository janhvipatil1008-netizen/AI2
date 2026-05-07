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
import psycopg2.extras

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


def enrich_job(job_id: str, learner_context: dict = None) -> dict:
    """
    Enrich a single job synchronously. Saves result to jobs.db.
    Returns the enrichment data dict.

    session: optional SessionContext — used to personalise match_score.
             If None, uses generic learner defaults.
    """
    from jobs.database import get_conn

    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM jobs WHERE id = %s", (job_id,))
            row = cur.fetchone()

    if not row:
        raise ValueError(f"Job {job_id} not found in jobs.db")

    row = dict(row)

    # ── Build learner context ─────────────────────────────────────────────────
    if learner_context is not None:
        from config import TRACK_DISPLAY_NAMES, CareerTrack
        raw_track = learner_context.get("track", "")
        try:
            track = TRACK_DISPLAY_NAMES.get(CareerTrack(raw_track), raw_track)
        except ValueError:
            track = raw_track or row.get("role_category", "AI role")
        current_week = learner_context.get("current_week", 1)
        goals_list   = learner_context.get("goals", [])
        background   = learner_context.get("background", "")
        goals        = background or (", ".join(goals_list[:3]) if goals_list else "land an AI role")
        explored     = learner_context.get("topics_explored", [])
        mastered     = ", ".join(explored[:6]) if explored else "AI fundamentals"
        low_scores   = [q["topic"] for q in learner_context.get("quiz_scores", [])
                        if q.get("pct", 100) < 60]
        struggling   = ", ".join(low_scores[:4]) if low_scores else "advanced topics — still building"
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
    _summary    = json.dumps(data.get("summary", {}))
    _skills     = json.dumps(data.get("skills_needed", {}))
    _questions  = json.dumps(data.get("possible_questions", []))
    _guide      = json.dumps(data.get("learning_guide", {}))
    _quiz       = json.dumps(data.get("quiz", []))
    _score      = int(data.get("match_score", 0))
    _reasoning  = str(data.get("match_reasoning", ""))
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO job_enrichments
                   (id, job_id, summary, skills_needed, possible_questions,
                    learning_guide, quiz, match_score, match_reasoning, created_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (job_id) DO UPDATE SET
                     id=%s, summary=%s, skills_needed=%s, possible_questions=%s,
                     learning_guide=%s, quiz=%s, match_score=%s,
                     match_reasoning=%s, created_at=%s""",
                (
                    enrichment_id, job_id,
                    _summary, _skills, _questions, _guide, _quiz,
                    _score, _reasoning, now,
                    enrichment_id,
                    _summary, _skills, _questions, _guide, _quiz,
                    _score, _reasoning, now,
                ),
            )
            cur.execute(
                "UPDATE jobs SET enriched=1, enriched_at=%s WHERE id=%s",
                (now, job_id),
            )

    return data
