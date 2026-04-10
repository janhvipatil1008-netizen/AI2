"""
AI² Platform — Idea Generator Sub-Agent
Brainstorms projects, creative applications, and career-building directions.
Specializes in translating theory into tangible, portfolio-worthy work.
"""

import anthropic
from context.session import SessionContext
from curriculum.syllabus import get_full_track_summary, format_week_context
from config import AGENT_MODEL, AGENT_MAX_TOKENS

_SYSTEM_PROMPT_TEMPLATE = """\
You are the Idea Generator for AI², an adaptive AI education platform.
Your mission: spark creativity and help learners build real things that demonstrate mastery.

IDEA GENERATION PHILOSOPHY
• Every idea must be buildable within the student's current week skill set
• Mix breadth (many quick ideas) with depth (one fully fleshed-out idea)
• Ground ideas in the student's career track — PM ideas differ from Evals ideas
• Connect project ideas to portfolio value: "This would signal X to a hiring manager"
• Range from weekend hacks to 2-week portfolio pieces to capstone contenders
• Include the "so what" — why this project matters in the field

IDEA STRUCTURE (for each substantive idea)
1. Project name + one-line pitch
2. What you'll build (3 bullet points)
3. Key skills demonstrated
4. What to show in your portfolio
5. Stretch goals (if they want to go deeper)

CREATIVE STIMULUS TECHNIQUES
• Cross-pollinate: combine AI capabilities with an unexpected domain
• Pain-first: start with a real frustration, apply AI as the solution
• Constraint-driven: "what if you could only use 3 API calls?"
• Persona-swap: "what would an AI PM at Netflix build with this?"
• The 10x version: "what if this worked 10x better than today?"

CAREER AWARENESS
• Flag ideas that are especially strong for portfolio/job signal
• Note what company types value which kinds of projects
• Connect ideas to real products, startups, and open roles when relevant

FULL CURRICULUM FOR CONTEXT
{full_syllabus}
"""


def _build_system_prompt(session: SessionContext) -> list[dict]:
    full_syllabus = get_full_track_summary(session.track.value)
    static_text = _SYSTEM_PROMPT_TEMPLATE.format(full_syllabus=full_syllabus)

    return [
        {
            "type": "text",
            "text": static_text,
            "cache_control": {"type": "ephemeral"},
        }
    ]


def respond(
    client:   anthropic.Anthropic,
    theme:    str,
    session:  SessionContext,
    context:  str = "",
) -> str:
    """
    Idea Generator response to a creative brainstorm request.

    Args:
        client:   Anthropic client
        theme:    The theme or topic to generate ideas around
        session:  Current session context
        context:  Optional additional context (goals, constraints, interests)

    Returns:
        str: Creative project ideas and inspiration
    """
    week_context = format_week_context(session.track.value, session.current_week)
    recent_history = session.format_history_for_prompt(n=4)

    additional = f"\nAdditional context: {context}" if context else ""

    user_content = (
        f"{session.as_prompt_context()}\n\n"
        f"CURRENT WEEK CONTENT\n{week_context}\n\n"
        f"RECENT CONVERSATION\n{recent_history}\n\n"
        f"--- IDEA REQUEST ---\n"
        f"Theme/Topic: {theme}{additional}"
    )

    response = client.messages.create(
        model=AGENT_MODEL,
        max_tokens=AGENT_MAX_TOKENS,
        system=_build_system_prompt(session),
        messages=[{"role": "user", "content": user_content}],
    )

    session.note_topic(theme[:60])

    return response.content[0].text
