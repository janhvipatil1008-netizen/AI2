"""
AI² — Job Search Agent
Helps learners browse, analyze, and prepare for AI job opportunities.
Same module-function pattern as learning_coach.py, practice_arena.py, idea_generator.py.
"""
import json
import logging

import anthropic

from config import AGENT_MODEL, AGENT_MAX_TOKENS, TRACK_DISPLAY_NAMES
from context.session import SessionContext

logger = logging.getLogger(__name__)

# ── Intent detection ──────────────────────────────────────────────────────────

_INTENT_KEYWORDS: dict[str, list[str]] = {
    "analyze":  ["analyze", "analyse", "break down", "tell me about this job",
                 "explain this role", "what does this role", "is this role good"],
    "prep":     ["prep", "prepare", "interview questions", "practice for",
                 "get ready for", "questions for this", "help me prepare"],
    "quiz":     ["quiz", "test me", "assess me", "am i ready", "how ready",
                 "quiz me on this"],
    "apply":    ["apply", "cover letter", "cold message", "outreach",
                 "reach out", "message the recruiter", "how do i apply"],
    "match":    ["match", "best role", "which role", "rank jobs", "most suited",
                 "which company", "fit for me", "which job", "am i ready for"],
}


def detect_intent(message: str) -> str:
    msg = message.lower()
    for intent, keywords in _INTENT_KEYWORDS.items():
        if any(k in msg for k in keywords):
            return intent
    return "browse"


# ── System prompt ─────────────────────────────────────────────────────────────

_SYSTEM = """\
You are the Job Search Agent inside AI², an AI career learning platform.
Your job: help the learner find, understand, and get ready for AI roles.

LEARNER PROFILE:
Track: {track} | Week: {current_week}/5
Topics mastered: {topics_mastered}
Goals: {goals}

AVAILABLE JOBS (sorted by match score — enriched jobs first):
{top_jobs}

INTENT DETECTED: {intent}

HOW TO RESPOND BY INTENT:

BROWSE
  List up to 5 jobs. For each: title, company, location, match_score (show "Not scored yet" if null),
  role_in_one_line. End with: "Want me to analyze any of these? Just name the company or role."

ANALYZE
  Full breakdown of the job the user mentioned: what you'll do, company signal,
  green flags, red flags, skills you already have vs skills gap. Be direct.

PREP
  5 interview questions for the role with: question, why they ask it,
  strong_answer_structure. Reference Agri-Saathi or AI² curriculum projects
  where the skills genuinely overlap. Don't pad.

QUIZ
  Present 3 role-specific questions one at a time. State difficulty.
  Wait for the user to answer before showing the next one.

APPLY
  Write a 3-sentence cold outreach message to the recruiter for this specific role.
  Use the company name, the specific tech stack from the JD, and one concrete signal
  from the learner's background. No generic fluff.

MATCH
  Rank ALL listed jobs by fit vs learner's current mastery.
  For each: match_score (or estimated fit), honest 1-sentence gap explanation.
  Be realistic — if they're not ready, say what to build first.

RULES:
- Never show a match_score without a 1-line explanation
- Keep responses under 500 words unless PREP or QUIZ
- Always connect gaps to specific AI² curriculum weeks where possible
- If no jobs are loaded, tell the user to click "Refresh Jobs" on the /jobs page\
"""


# ── DB helper ─────────────────────────────────────────────────────────────────

def _get_top_jobs(limit: int = 8) -> list[dict]:
    try:
        from jobs.database import get_jobs
        jobs = get_jobs(limit=limit)
        result = []
        for j in jobs:
            summary = j.get("summary") or {}
            result.append({
                "id":             j["id"],
                "title":          j["title"],
                "company":        j.get("company", ""),
                "location":       j.get("location", ""),
                "role_category":  j.get("role_category", ""),
                "date_posted":    j.get("date_posted", ""),
                "match_score":    j.get("match_score"),
                "role_in_one_line": (summary.get("role_in_one_line", "")
                                     if isinstance(summary, dict) else ""),
                "job_url":        j.get("job_url", ""),
            })
        return result
    except Exception as exc:
        logger.warning(f"Could not load jobs from jobs.db: {exc}")
        return []


# ── Main agent function ───────────────────────────────────────────────────────

def respond(
    client: anthropic.Anthropic,
    query: str,
    session: SessionContext,
    intent: str = "",
    profile=None,
) -> str:
    """
    Handle a job-search query. Intent is pre-detected by the orchestrator
    or auto-detected here from the query text.
    """
    if not intent:
        intent = detect_intent(query)

    top_jobs = _get_top_jobs()
    jobs_text = (
        json.dumps(top_jobs, indent=2)
        if top_jobs
        else "No jobs loaded. User should visit /jobs and click 'Refresh Jobs'."
    )

    system = _SYSTEM.format(
        track         = TRACK_DISPLAY_NAMES.get(session.track, session.track.value),
        current_week  = session.current_week,
        topics_mastered = ", ".join(sorted(session.topics_explored)[:6]) or "still building foundations",
        goals         = ", ".join(session.goals[:2]) or "land an AI role",
        top_jobs      = jobs_text,
        intent        = intent.upper(),
    )

    history = []
    for exchange in session.recent_history(n=3):
        history.append({"role": "user",      "content": exchange.user_message})
        history.append({"role": "assistant",  "content": exchange.assistant_reply})
    history.append({"role": "user", "content": query})

    response = client.messages.create(
        model      = AGENT_MODEL,
        max_tokens = AGENT_MAX_TOKENS,
        system     = system,
        messages   = history,
    )
    return response.content[0].text
