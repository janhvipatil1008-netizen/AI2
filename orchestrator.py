"""
AI² Platform — Orchestrator Agent
The central coordinator. Analyzes learner intent and delegates to the right
specialist via tool use. After receiving sub-agent results, synthesizes a
contextualized response that connects the answer to the learner's journey.

Architecture:
  User message
      │
      ▼
  Orchestrator (Claude Opus — tool_use loop)
      │  calls one of three tools
      ▼
  ┌──────────────┬──────────────────┬───────────────┐
  │ Learning     │ Practice         │ Idea          │
  │ Coach        │ Arena            │ Generator     │
  │ (Claude)     │ (Claude)         │ (Claude)      │
  └──────────────┴──────────────────┴───────────────┘
      │  tool result returned to orchestrator
      ▼
  Orchestrator synthesizes final response with learner context
      │
      ▼
  Response to user
"""

import json
from typing import Generator
import anthropic

from context.session import SessionContext
from curriculum.syllabus import format_week_context, get_week
from config import (
    ORCHESTRATOR_MODEL,
    ORCHESTRATOR_MAX_TOKENS,
    SYNTHESIS_MAX_TOKENS,
    AGENT_DESCRIPTIONS,
    TRACK_DISPLAY_NAMES,
    NO_SYNTHESIS_AGENTS,
)
import agents.learning_coach  as learning_coach
import agents.practice_arena  as practice_arena
import agents.idea_generator  as idea_generator


# ── Orchestrator Tools ────────────────────────────────────────────────────────
# These tell the orchestrator which specialist to call and with what parameters.

ORCHESTRATOR_TOOLS = [
    {
        "name": "consult_learning_coach",
        "description": AGENT_DESCRIPTIONS["learning_coach"],
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The specific question or concept the learner wants to understand",
                },
                "depth": {
                    "type": "string",
                    "enum": ["introductory", "intermediate", "advanced"],
                    "description": (
                        "The explanation depth needed. "
                        "Use 'introductory' for first-time topics, "
                        "'intermediate' for building on prior knowledge, "
                        "'advanced' for expert-level nuance."
                    ),
                },
                "papers_requested": {
                    "type": "boolean",
                    "description": (
                        "Set to true when the learner explicitly asks for papers, "
                        "reading lists, research, or resources. The coach will "
                        "prioritise a curated paper recommendation in their response."
                    ),
                },
            },
            "required": ["query", "depth"],
        },
    },
    {
        "name": "consult_practice_arena",
        "description": AGENT_DESCRIPTIONS["practice_arena"],
        "input_schema": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": (
                        "For mcq_quiz / interview_prep: the topic to practice "
                        "(e.g. 'RAG pipelines', 'LLM evaluation', 'attention mechanism'). "
                        "For evaluate_answer: the learner's written answer to score."
                    ),
                },
                "practice_type": {
                    "type": "string",
                    "enum": ["mcq_quiz", "interview_prep", "evaluate_answer"],
                    "description": (
                        "'mcq_quiz' — generate 15 MCQ questions (5 beginner, 5 intermediate, "
                        "5 advanced) for a topic. Use after the learner finishes a topic or "
                        "asks to be tested. "
                        "'interview_prep' — generate 15 interview questions (5 conceptual, "
                        "5 technical, 5 scenario/design) with model answers. Use when the "
                        "learner asks for interview practice. "
                        "'evaluate_answer' — score and give feedback on the learner's written "
                        "answer to an interview question. Use when the learner submits an answer."
                    ),
                },
                "topic": {
                    "type": "string",
                    "description": (
                        "The specific topic or concept to focus on. "
                        "For evaluate_answer: the interview question that was asked. "
                        "If the learner didn't specify, infer from context."
                    ),
                },
                "difficulty": {
                    "type": "string",
                    "enum": ["all", "beginner", "intermediate", "advanced",
                             "conceptual", "technical", "scenario"],
                    "description": (
                        "Difficulty level to focus on. Defaults to 'all' (full 15 questions). "
                        "For mcq_quiz: 'beginner' | 'intermediate' | 'advanced'. "
                        "For interview_prep: 'conceptual' | 'technical' | 'scenario'. "
                        "Use a specific level only if the learner explicitly asks for it."
                    ),
                },
            },
            "required": ["task", "practice_type"],
        },
    },
    {
        "name": "consult_idea_generator",
        "description": AGENT_DESCRIPTIONS["idea_generator"],
        "input_schema": {
            "type": "object",
            "properties": {
                "theme": {
                    "type": "string",
                    "description": "The theme, technology, or topic to generate project ideas around",
                },
                "context": {
                    "type": "string",
                    "description": "Optional: learner's goals, constraints, or interests to personalise ideas",
                },
            },
            "required": ["theme"],
        },
    },
]


# ── Orchestrator System Prompt ────────────────────────────────────────────────

def _build_orchestrator_system(session: SessionContext) -> str:
    week_data = get_week(session.track.value, session.current_week)
    track_name = TRACK_DISPLAY_NAMES[session.track]

    return f"""\
You are the AI² Orchestrator — the intelligent coordinator of a personalized AI learning platform.

YOUR ROLE
You are NOT the one who teaches, practices, or generates ideas directly.
Your job is to:
  1. Understand the learner's intent with precision
  2. Route to the single most appropriate specialist agent (via a tool call)
  3. After receiving the specialist's response, add a brief contextual frame (1-3 sentences)
     that connects the answer to the learner's journey and current week

THE LEARNER
Track:        {track_name}
Current Week: {session.current_week} — {week_data['title']}
Exchanges:    {len(session.history)} so far this session
Exercises:    {session.exercises_done} completed

ROUTING DECISION RULES
• ANY question about "what is", "how does", "explain", "I don't understand", "teach me"
  → consult_learning_coach

• ANY request for "papers", "research", "reading list", "resources", "what should I read"
  → consult_learning_coach with papers_requested=true

• ANY request to be tested, quizzed, or assessed on a topic
  → consult_practice_arena with practice_type="mcq_quiz"

• ANY request for interview prep, interview questions, mock interview
  → consult_practice_arena with practice_type="interview_prep"

• ANY time the learner submits a written answer for feedback
  → consult_practice_arena with practice_type="evaluate_answer",
    topic = the question asked, task = the learner's answer

• ANY request for "ideas", "what can I build", "inspire me", "project",
  "what should I work on"
  → consult_idea_generator

• When ambiguous → default to consult_learning_coach

AFTER THE SPECIALIST RESPONDS
Write 1-3 sentences that:
  • Acknowledge where the learner is ("You're in Week {session.current_week}...")
  • Add one connection to the broader curriculum arc (optional)
  • Suggest what to explore next (optional)

Do NOT repeat or summarise the specialist's content. Just add the framing.
Keep your framing brief — the specialist's response is the main value.
"""


# ── Orchestrator Class ────────────────────────────────────────────────────────

class Orchestrator:
    """
    Central coordinator for the AI² learning platform.

    Process flow:
      1. Build context messages (session history + current query)
      2. Run tool-use loop: orchestrator picks a specialist tool
      3. Execute the tool (call the sub-agent)
      4. Orchestrator synthesizes a framing response
      5. Return full response to caller
    """

    def __init__(self, client: anthropic.Anthropic, session: SessionContext):
        self.client  = client
        self.session = session

    def process(self, user_message: str) -> str:
        """
        Process a learner message through the full orchestration pipeline.

        Returns the complete response as a string.
        Streaming can be layered on top of this by the caller.
        """
        messages = self._build_messages(user_message)
        system   = _build_orchestrator_system(self.session)

        # ── Phase 1: Routing + Sub-Agent Execution ─────────────────────────
        # The orchestrator MUST call a tool (tool_choice="any").
        # It picks the right specialist and provides parameters.

        routing_response = self.client.messages.create(
            model       = ORCHESTRATOR_MODEL,
            max_tokens  = ORCHESTRATOR_MAX_TOKENS,
            system      = system,
            tools       = ORCHESTRATOR_TOOLS,
            tool_choice = {"type": "any"},   # force exactly one tool call
            messages    = messages,
            # Note: thinking cannot be used together with tool_choice="any"
        )

        # Append orchestrator routing turn
        messages.append({"role": "assistant", "content": routing_response.content})

        # Execute the tool call(s) — there will be exactly one due to tool_choice="any"
        tool_results = []
        sub_agent_name = "learning_coach"   # default for session tracking

        for block in routing_response.content:
            if block.type != "tool_use":
                continue

            tool_name   = block.name
            tool_input  = block.input
            sub_agent_name = tool_name.replace("consult_", "")

            result = self._execute_tool(tool_name, tool_input)

            tool_results.append({
                "type":        "tool_result",
                "tool_use_id": block.id,
                "content":     result,
            })

        # Feed tool results back
        messages.append({"role": "user", "content": tool_results})

        # ── Phase 2: Synthesis ─────────────────────────────────────────────
        # Orchestrator adds 1-3 sentence framing after the specialist response.
        # Skipped for Practice Arena — its structured MCQ/interview output is
        # already self-contained and doesn't benefit from appended commentary.

        specialist_content = tool_results[0]["content"] if tool_results else ""

        if sub_agent_name in NO_SYNTHESIS_AGENTS:
            full_response = specialist_content
        else:
            synthesis_response = self.client.messages.create(
                model      = ORCHESTRATOR_MODEL,
                max_tokens = SYNTHESIS_MAX_TOKENS,
                system     = system,
                messages   = messages,
            )
            framing = ""
            for block in synthesis_response.content:
                if block.type == "text":
                    framing += block.text

            full_response = specialist_content
            if framing.strip():
                full_response += f"\n\n---\n{framing.strip()}"

        # ── Update Session ─────────────────────────────────────────────────
        self.session.add_exchange(
            user_message    = user_message,
            assistant_reply = full_response[:500],   # truncate for storage
            agent_used      = sub_agent_name,
        )

        return full_response

    # ── Tool Dispatch ─────────────────────────────────────────────────────────

    def _execute_tool(self, tool_name: str, tool_input: dict) -> str:
        """Dispatch a tool call to the appropriate sub-agent."""
        if tool_name == "consult_learning_coach":
            if tool_input.get("papers_requested"):
                return learning_coach.recommend_papers(
                    client  = self.client,
                    topic   = tool_input["query"],
                    session = self.session,
                )
            return learning_coach.respond(
                client  = self.client,
                query   = tool_input["query"],
                session = self.session,
                depth   = tool_input.get("depth", "intermediate"),
            )

        if tool_name == "consult_practice_arena":
            return practice_arena.respond(
                client        = self.client,
                task          = tool_input["task"],
                session       = self.session,
                practice_type = tool_input.get("practice_type", "mcq_quiz"),
                topic         = tool_input.get("topic", ""),
                difficulty    = tool_input.get("difficulty", "all"),
            )

        if tool_name == "consult_idea_generator":
            return idea_generator.respond(
                client  = self.client,
                theme   = tool_input["theme"],
                session = self.session,
                context = tool_input.get("context", ""),
            )

        return f"[Unknown tool: {tool_name}]"

    # ── Context Builder ───────────────────────────────────────────────────────

    def _build_messages(self, user_message: str) -> list[dict]:
        """
        Build the messages array for the orchestrator call.
        Includes recent session history for conversational continuity.
        """
        messages = []

        # Inject recent history as prior turns
        for exchange in self.session.recent_history(n=4):
            messages.append({"role": "user",      "content": exchange.user_message})
            messages.append({"role": "assistant",  "content": exchange.assistant_reply})

        # Current turn
        messages.append({"role": "user", "content": user_message})

        return messages
