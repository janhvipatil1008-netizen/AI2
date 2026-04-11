"""
AI² Platform — Practice Arena Sub-Agent

Two dedicated practice engines that activate after a learner completes a topic:

  MCQ QUIZ        — 15 multiple-choice questions per topic across three difficulty
                    levels (5 Beginner · 5 Intermediate · 5 Advanced), with instant
                    answer feedback and a score summary.

  INTERVIEW PREP  — 15 topic-specific interview questions across three levels
                    (5 Conceptual · 5 Technical · 5 Scenario/Design), with model
                    answers, evaluation of the learner's written response, and
                    coaching on how to improve.

Both modes are personalised to the learner's track (AIPM / Evals / Context Engineer)
and calibrated to the current phase of the curriculum.
"""

import anthropic
from context.session import SessionContext
from curriculum.syllabus import get_full_track_summary, format_week_context, _WEEK_TO_PHASE
from config import AGENT_MODEL, PRACTICE_AGENT_MAX_TOKENS as AGENT_MAX_TOKENS

# ── Role-specific question angle descriptions ─────────────────────────────────
# Injected into prompts so questions are framed from the right professional lens.

_ROLE_LENS = {
    "aipm": (
        "AI Product Manager lens: frame questions around product decisions, "
        "tradeoffs, stakeholder communication, metrics, roadmap prioritisation, "
        "and what an AIPM would actually do with this knowledge on the job."
    ),
    "evals": (
        "AI Evals Specialist lens: frame questions around measurement, rigor, "
        "statistical validity, tooling, failure modes, and how this knowledge "
        "directly improves evaluation pipelines and model quality."
    ),
    "context": (
        "Context Engineer lens: frame questions around system design, context "
        "assembly, token efficiency, retrieval quality, and how this knowledge "
        "shapes the information architecture of AI systems."
    ),
}

# ── MCQ Quiz System Prompt ────────────────────────────────────────────────────

_MCQ_SYSTEM_PROMPT = """\
You are the Practice Arena for AI² — an expert at designing rigorous, well-crafted
multiple-choice assessments that test both conceptual understanding and practical
application.

YOUR MISSION
Generate exactly 15 MCQ questions for the requested topic, grouped into three
difficulty levels (5 questions each). Every question must be immediately useful
for knowledge consolidation AND real interview preparation.

════════════════════════════════════════════════════════
QUESTION DESIGN STANDARDS
════════════════════════════════════════════════════════

BEGINNER (Q1–5) — Conceptual foundations
  • Test that the learner understands WHAT and WHY
  • One clearly correct answer; distractors are common misconceptions
  • Stems are direct: "What is...?", "Which of the following best describes...?"
  • Example: testing definitions, mechanics, basic use cases

INTERMEDIATE (Q6–10) — Applied understanding
  • Test that the learner can apply the concept in a realistic scenario
  • Require comparison, analysis, or selecting between valid-sounding options
  • Stems involve a mini-scenario: "A team is building X and observes Y. What should they do?"
  • Distractors are plausible — the learner must reason, not just recall

ADVANCED (Q11–15) — Expert judgment
  • Test nuanced tradeoffs, edge cases, and architectural decisions
  • All four options may be partially correct — learner must identify the BEST answer
  • Stems involve complex constraints: latency, cost, accuracy, scale, safety
  • These questions should feel like actual interview questions at senior level

OPTION QUALITY RULES
  • Always exactly 4 options: A, B, C, D
  • Correct answer rotates across positions — avoid always placing it at B
  • Each distractor must represent a specific, common mistake or misconception
  • No "all of the above" or "none of the above"
  • Options roughly equal in length — avoid giving away the answer by length

════════════════════════════════════════════════════════
REQUIRED OUTPUT FORMAT (follow exactly)
════════════════════════════════════════════════════════

Output a clean, well-formatted quiz. Use this structure precisely:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📝  QUIZ: [TOPIC] — [TRACK] Track
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🟢 BEGINNER  (Q1–5)
─────────────────────────────────────────────────────
Q1. [Question stem]

   A) [Option]
   B) [Option]
   C) [Option]
   D) [Option]

✅ Answer: [Letter]) [Correct option text]
💡 Why: [2–3 sentence explanation of why this is correct AND why each wrong option fails]

[Repeat for Q2–Q5]


🟡 INTERMEDIATE  (Q6–10)
─────────────────────────────────────────────────────
[Same format]


🔴 ADVANCED  (Q11–15)
─────────────────────────────────────────────────────
[Same format]


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊  QUIZ COMPLETE
  15 questions · Beginner: Q1–5 · Intermediate: Q6–10 · Advanced: Q11–15
  Tip: [One actionable next-step based on what the quiz tested]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

════════════════════════════════════════════════════════
CURRICULUM CONTEXT
════════════════════════════════════════════════════════
{full_syllabus}
"""

# ── Interview Prep System Prompt ──────────────────────────────────────────────

_INTERVIEW_SYSTEM_PROMPT = """\
You are the Practice Arena for AI² — a seasoned interview coach with deep knowledge
of what hiring managers at AI-first companies actually ask, and what separates a
good answer from a great one.

YOUR MISSION
Generate exactly 15 interview questions for the requested topic, grouped into three
levels (5 questions each). For each question, provide what a strong answer covers
and a model answer calibrated to the learner's track. When the learner provides
their own answer, evaluate it with specific, actionable feedback.

════════════════════════════════════════════════════════
QUESTION DESIGN BY LEVEL
════════════════════════════════════════════════════════

CONCEPTUAL (Q1–5) — "Show me you understand it"
  • Test foundational knowledge and the ability to explain clearly
  • Format: "What is X?", "Explain the difference between X and Y",
    "Why does X matter for AI products/evals/systems?"
  • Ideal for: phone screens, recruiter calls, entry-to-mid level roles
  • Strong answer: clear definition + one concrete example + why it matters

TECHNICAL (Q6–10) — "Show me you can apply it"
  • Test practical depth and decision-making
  • Format: "How would you...", "Walk me through...", "What would you do if..."
  • Ideal for: technical rounds, hiring manager interviews, mid-to-senior roles
  • Strong answer: structured approach + tradeoffs considered + specific tools/methods

SCENARIO / DESIGN (Q11–15) — "Show me you can lead it"
  • Test systems thinking, prioritisation under constraints, stakeholder awareness
  • Format: Complex open-ended situations with ambiguity and competing constraints
  • Ideal for: system design rounds, director/senior IC roles, take-home cases
  • Strong answer: problem framing + structured approach + tradeoffs + example outcome

════════════════════════════════════════════════════════
REQUIRED OUTPUT FORMAT
════════════════════════════════════════════════════════

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯  INTERVIEW PREP: [TOPIC] — [TRACK] Track
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💬 CONCEPTUAL  (Q1–5)  |  Phone screen · Entry–Mid level
─────────────────────────────────────────────────────
Q1. [Interview question]

   🎯 What a strong answer covers:
      • [Point 1 — the core concept the interviewer is testing for]
      • [Point 2 — the nuance or real-world connection they want to hear]
      • [Point 3 — the signal that separates good from great answers]

   ✨ Model answer:
      [2–4 sentence model answer written in first person, the way you'd
       actually say it in an interview. Confident, specific, concise.]

[Repeat for Q2–Q5]


⚙️  TECHNICAL  (Q6–10)  |  Technical round · Mid–Senior level
─────────────────────────────────────────────────────
[Same format]


🏗️  SCENARIO / DESIGN  (Q11–15)  |  Design round · Senior–Lead level
─────────────────────────────────────────────────────
[Same format]


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🏁  INTERVIEW PREP COMPLETE — 15 questions across 3 levels
   To practice answering: reply with your answer to any question above.
   I'll evaluate it and give you specific coaching feedback.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

════════════════════════════════════════════════════════
CURRICULUM CONTEXT
════════════════════════════════════════════════════════
{full_syllabus}
"""

# ── Answer Evaluation System Prompt ──────────────────────────────────────────

_EVAL_SYSTEM_PROMPT = """\
You are the Practice Arena for AI² — a rigorous but encouraging interview coach.
A learner has just attempted to answer an interview question. Your job is to give
them the most useful feedback they could possibly receive.

════════════════════════════════════════════════════════
EVALUATION FRAMEWORK
════════════════════════════════════════════════════════

Score the answer on 4 dimensions (0–10 each, then a composite out of 40):

  CLARITY (0–10)
  Is the answer well-structured and easy to follow?
  Does it open with a clear statement, not rambling?

  ACCURACY (0–10)
  Are the technical claims correct?
  Are there misconceptions, gaps, or oversimplifications?

  DEPTH (0–10)
  Does it go beyond surface-level? Does it show genuine mastery?
  Are tradeoffs, nuance, or edge cases considered?

  RELEVANCE (0–10)
  Does the answer directly address what was asked?
  Is it calibrated to the track (AIPM / Evals / Context Engineer)?

════════════════════════════════════════════════════════
REQUIRED OUTPUT FORMAT
════════════════════════════════════════════════════════

📋  ANSWER EVALUATION
─────────────────────────────────────────────────────
Question: [Repeat the question]

Your answer: [Repeat the learner's answer verbatim]

─────────────────────────────────────────────────────
SCORECARD
  Clarity    : [X]/10 — [One-sentence rationale]
  Accuracy   : [X]/10 — [One-sentence rationale]
  Depth      : [X]/10 — [One-sentence rationale]
  Relevance  : [X]/10 — [One-sentence rationale]
  ─────────────────────────
  TOTAL      : [X]/40  ([X]%)  [Emoji: ⭐ <50% | ⭐⭐ 50–74% | ⭐⭐⭐ 75–89% | 🏆 90%+]

─────────────────────────────────────────────────────
✅  WHAT YOU GOT RIGHT
[2–3 specific things the learner did well — be precise, not generic]

🔧  WHERE TO IMPROVE
[2–3 specific gaps with concrete suggestions — what to add, what to reframe]

✨  MODEL ANSWER (for comparison)
[Write the ideal answer to this exact question for this learner's track,
 the way you'd say it in a real interview. 3–5 sentences.]

💡  ONE DRILL TO IMPROVE THIS SKILL
[A single concrete action: read X, practice Y, build Z — specific and achievable]
"""


# ── Prompt cache builders ─────────────────────────────────────────────────────

def _cached_system(template: str, session: SessionContext) -> list[dict]:
    """Wrap a system prompt template with the full syllabus and cache it."""
    full_syllabus = get_full_track_summary(session.track.value)
    text = template.format(full_syllabus=full_syllabus)
    return [{"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}]


# ── Learner context block ─────────────────────────────────────────────────────

def _learner_block(session: SessionContext, topic: str, mode: str) -> str:
    """Rich context injected into every practice call."""
    role_key   = session.track.value
    phase_id   = _WEEK_TO_PHASE.get(session.current_week, "portfolio")
    week_ctx   = format_week_context(role_key, session.current_week)
    lens       = _ROLE_LENS.get(role_key, "")

    # Quiz history for this topic
    best = session.best_score_for(topic)
    history_line = (
        f"Best previous score on '{topic}': {best['score']}/{best['total']} "
        f"({best['pct']}%) [{best['mode']}]"
        if best else f"First time practicing '{topic}'"
    )

    goals_text = (
        "\n".join(f"  • {g}" for g in session.goals)
        if session.goals else "  (not stated)"
    )

    return f"""
════════════════════════════════════════
LEARNER PROFILE
════════════════════════════════════════
Track:       {role_key}
Week:        {session.current_week} / 13
Phase:       {phase_id}
Mode:        {mode}
Topic:       {topic}
{history_line}

Question framing angle:
  {lens}

Learner goals:
{goals_text}

Quizzes taken this session: {len(session.quiz_scores)}
Topics already quizzed: {', '.join(list(session.topics_quizzed)) or 'none yet'}
════════════════════════════════════════

CURRENT WEEK CONTEXT
{week_ctx}
"""


# ── Public interface ──────────────────────────────────────────────────────────

def generate_mcq_quiz(
    client:     anthropic.Anthropic,
    topic:      str,
    session:    SessionContext,
    difficulty: str = "all",
) -> str:
    """
    Generate a 15-question MCQ quiz for a specific topic.

    Args:
        client:     Anthropic client
        topic:      The topic to quiz on (e.g. "RAG", "attention mechanisms")
        session:    Current session context
        difficulty: "all" | "beginner" | "intermediate" | "advanced"
                    Use "all" for the full 15-question set.
                    Use a single level to generate a focused 5-question mini-quiz.

    Returns:
        str: Formatted quiz with questions, options, answers, and explanations
    """
    difficulty_instruction = ""
    if difficulty != "all":
        difficulty_instruction = (
            f"\n⚠️  FOCUSED MODE: Generate only the {difficulty.upper()} questions "
            f"(5 questions). Use Q1–Q5 numbering regardless of level."
        )

    user_content = (
        f"{_learner_block(session, topic, 'MCQ Quiz')}\n"
        f"━━━ QUIZ REQUEST ━━━\n"
        f"Topic: {topic}\n"
        f"Difficulty: {difficulty}\n"
        f"Track framing: {session.track.value.upper()}{difficulty_instruction}\n\n"
        f"Generate the quiz now. Follow the output format precisely."
    )

    response = client.messages.create(
        model=AGENT_MODEL,
        max_tokens=AGENT_MAX_TOKENS,
        system=_cached_system(_MCQ_SYSTEM_PROMPT, session),
        messages=[{"role": "user", "content": user_content}],
    )

    reply = response.content[-1].text if response.content else ""
    session.note_topic(topic)
    session.mark_exercise_done()
    return reply


def generate_interview_questions(
    client:     anthropic.Anthropic,
    topic:      str,
    session:    SessionContext,
    difficulty: str = "all",
) -> str:
    """
    Generate 15 interview questions for a specific topic across 3 levels.

    Args:
        client:     Anthropic client
        topic:      The topic to prep for (e.g. "LLM evaluation", "RAG pipelines")
        session:    Current session context
        difficulty: "all" | "conceptual" | "technical" | "scenario"

    Returns:
        str: Formatted interview question bank with model answers
    """
    difficulty_instruction = ""
    if difficulty != "all":
        level_map = {
            "conceptual": "CONCEPTUAL (Q1–5)",
            "technical":  "TECHNICAL (Q6–10)",
            "scenario":   "SCENARIO / DESIGN (Q11–15)",
        }
        level_label = level_map.get(difficulty, difficulty.upper())
        difficulty_instruction = (
            f"\n⚠️  FOCUSED MODE: Generate only the {level_label} questions "
            f"(5 questions). Use Q1–Q5 numbering."
        )

    user_content = (
        f"{_learner_block(session, topic, 'Interview Prep')}\n"
        f"━━━ INTERVIEW PREP REQUEST ━━━\n"
        f"Topic: {topic}\n"
        f"Level focus: {difficulty}\n"
        f"Track framing: {session.track.value.upper()}{difficulty_instruction}\n\n"
        f"Generate the interview question bank now. Follow the output format precisely."
    )

    response = client.messages.create(
        model=AGENT_MODEL,
        max_tokens=AGENT_MAX_TOKENS,
        system=_cached_system(_INTERVIEW_SYSTEM_PROMPT, session),
        messages=[{"role": "user", "content": user_content}],
    )

    reply = response.content[-1].text if response.content else ""
    session.note_topic(topic)
    session.mark_exercise_done()
    return reply


def evaluate_answer(
    client:   anthropic.Anthropic,
    question: str,
    answer:   str,
    session:  SessionContext,
    topic:    str = "",
) -> str:
    """
    Evaluate a learner's written answer to an interview question.

    Args:
        client:   Anthropic client
        question: The interview question that was asked
        answer:   The learner's written answer
        session:  Current session context
        topic:    Topic label for session tracking (optional)

    Returns:
        str: Scorecard + specific feedback + model answer + one improvement drill
    """
    role_key = session.track.value
    lens     = _ROLE_LENS.get(role_key, "")
    goals    = "; ".join(session.goals[-2:]) if session.goals else "not stated"

    user_content = (
        f"[LEARNER CONTEXT]\n"
        f"Track: {role_key} | Week: {session.current_week} | Goals: {goals}\n"
        f"Question framing angle: {lens}\n\n"
        f"━━━ EVALUATION REQUEST ━━━\n"
        f"QUESTION:\n{question}\n\n"
        f"LEARNER'S ANSWER:\n{answer}\n\n"
        f"Evaluate using the 4-dimension scorecard. Follow the output format precisely."
    )

    response = client.messages.create(
        model=AGENT_MODEL,
        max_tokens=AGENT_MAX_TOKENS,
        system=[{
            "type": "text",
            "text": _EVAL_SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{"role": "user", "content": user_content}],
    )

    reply = response.content[-1].text if response.content else ""
    if topic:
        session.note_topic(topic)
    return reply


def respond(
    client:        anthropic.Anthropic,
    task:          str,
    session:       SessionContext,
    practice_type: str = "quiz",
    topic:         str = "",
    difficulty:    str = "all",
) -> str:
    """
    Main entry point — routes to the correct practice engine.

    Args:
        client:        Anthropic client
        task:          Free-form description of what to practice, OR a learner's
                       answer when practice_type is "evaluate_answer"
        session:       Current session context
        practice_type: "mcq_quiz"        → 15-question MCQ assessment
                       "interview_prep"  → 15 interview questions with model answers
                       "evaluate_answer" → score a learner's answer (pass question
                                          in topic, answer in task)
                       "quiz"            → alias for "mcq_quiz" (backwards compat)
                       "exercise"        → alias for "mcq_quiz"
                       "challenge"       → interview_prep at advanced level
                       "evaluation"      → alias for "evaluate_answer"
        topic:         The specific topic to quiz/prep on. If blank, extracted from task.
        difficulty:    "all" | "beginner" | "intermediate" | "advanced" (for MCQ)
                       "all" | "conceptual" | "technical" | "scenario" (for interview)

    Returns:
        str: The formatted practice content
    """
    # Normalise aliases
    mode_map = {
        "quiz":           "mcq_quiz",
        "exercise":       "mcq_quiz",
        "challenge":      "interview_prep",
        "evaluation":     "evaluate_answer",
    }
    mode = mode_map.get(practice_type, practice_type)

    # Infer topic from task if not explicitly provided
    resolved_topic = topic.strip() if topic.strip() else task.strip()

    if mode == "mcq_quiz":
        return generate_mcq_quiz(
            client=client,
            topic=resolved_topic,
            session=session,
            difficulty=difficulty,
        )

    if mode == "interview_prep":
        # "challenge" alias → advanced-only
        resolved_difficulty = "scenario" if practice_type == "challenge" else difficulty
        return generate_interview_questions(
            client=client,
            topic=resolved_topic,
            session=session,
            difficulty=resolved_difficulty,
        )

    if mode == "evaluate_answer":
        # Expect: topic = the question, task = the learner's answer
        return evaluate_answer(
            client=client,
            question=topic or "Interview question (not specified)",
            answer=task,
            session=session,
            topic=resolved_topic,
        )

    # Fallback: treat as a general MCQ quiz
    return generate_mcq_quiz(
        client=client,
        topic=resolved_topic,
        session=session,
        difficulty=difficulty,
    )
