"""
AI² Platform — Configuration
Central constants, model IDs, and agent identities.
"""

from enum import Enum

# ── Models ────────────────────────────────────────────────────────────────────
ORCHESTRATOR_MODEL = "claude-opus-4-6"
AGENT_MODEL = "claude-opus-4-6"

# ── Career Tracks ─────────────────────────────────────────────────────────────
class CareerTrack(str, Enum):
    AI_PM            = "aipm"
    EVALS            = "evals"
    CONTEXT_ENGINEER = "context"

TRACK_DISPLAY_NAMES = {
    CareerTrack.AI_PM:            "AI Product Manager",
    CareerTrack.EVALS:            "AI Evals Specialist",
    CareerTrack.CONTEXT_ENGINEER: "Context Engineer",
}

TRACK_TAGLINES = {
    CareerTrack.AI_PM:            "Build AI products that matter.",
    CareerTrack.EVALS:            "Measure what matters in AI systems.",
    CareerTrack.CONTEXT_ENGINEER: "Master the art of context and memory.",
}

TOTAL_WEEKS = 13

# ── Agent Identities ──────────────────────────────────────────────────────────
AGENT_DESCRIPTIONS = {
    "learning_coach": (
        "The Learning Coach explains concepts, teaches theory, and guides understanding. "
        "Use for: questions, explanations, concept deep-dives, 'what is X', 'how does Y work'."
    ),
    "practice_arena": (
        "The Practice Arena reinforces learning after a topic is completed. "
        "Two modes: (1) MCQ Quiz — 15 multiple-choice questions at beginner / intermediate / "
        "advanced levels for any topic; (2) Interview Prep — 15 real interview questions at "
        "conceptual / technical / scenario levels with model answers and answer evaluation. "
        "Use for: 'quiz me', 'test me', 'interview practice', 'evaluate my answer', "
        "'am I ready for interviews on X'."
    ),
    "idea_generator": (
        "The Idea Generator brainstorms projects, creative applications, and career directions. "
        "Use for: project ideas, inspiration, 'what can I build', 'give me ideas', creative prompts."
    ),
}

# ── Generation Settings ───────────────────────────────────────────────────────
ORCHESTRATOR_MAX_TOKENS       = 512    # Routing call — brief
AGENT_MAX_TOKENS              = 2048   # Learning Coach, Idea Generator
PRACTICE_AGENT_MAX_TOKENS     = 4096   # Practice Arena — 15-question sets are long
SYNTHESIS_MAX_TOKENS          = 256    # Orchestrator framing — concise

# Sub-agents that produce fully self-contained structured output (skip synthesis framing)
NO_SYNTHESIS_AGENTS = {"practice_arena"}
