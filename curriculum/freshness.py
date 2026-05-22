"""
AI² Platform — Topic Content Freshness Classification

Deterministic keyword-based classifier that assigns a freshness label
to a topic, guiding learners on when to regenerate AI content.
"""

FRESHNESS_STABLE             = "Stable concept"
FRESHNESS_PERIODIC           = "Needs periodic refresh"
FRESHNESS_TOOL_SPECIFIC      = "Tool/framework specific"
FRESHNESS_LATEST_RECOMMENDED = "Latest knowledge recommended"

# Checked in priority order: latest → tool-specific → periodic → stable

_LATEST_KEYWORDS = frozenset({
    "pricing", "latest", "current", "new model", "model comparison",
    "aws service", "cloud cost", "deployment pricing",
})

_TOOL_KEYWORDS = frozenset({
    "langchain", "langgraph", "mcp", "anthropic", "claude", "openai",
    "groq", "vector database", "pinecone", "qdrant", "supabase",
    "render", "vercel", "fastapi", "next.js", "docker", "opentofu",
    "terraform", "github actions",
})

_PERIODIC_KEYWORDS = frozenset({
    "rag", "agents", "agentic", "evaluation", "evals",
    "prompt engineering", "context engineering", "llm app",
    "ai product", "cloud architecture", "mlops",
})

_GUIDANCE: dict[str, str] = {
    FRESHNESS_STABLE: (
        "This is a foundational concept and usually does not change often."
    ),
    FRESHNESS_PERIODIC: (
        "This topic evolves over time. Refresh when you want a newer explanation."
    ),
    FRESHNESS_TOOL_SPECIFIC: (
        "This topic may change as tools and frameworks update. "
        "Refresh before using it in a real project."
    ),
    FRESHNESS_LATEST_RECOMMENDED: (
        "This topic can become outdated quickly. "
        "Refresh before relying on it for decisions."
    ),
}


def classify_topic_freshness(topic_title: str, description: str = "") -> str:
    """Return a freshness label for a topic based on keyword matching."""
    text = (topic_title + " " + description).lower()
    for kw in _LATEST_KEYWORDS:
        if kw in text:
            return FRESHNESS_LATEST_RECOMMENDED
    for kw in _TOOL_KEYWORDS:
        if kw in text:
            return FRESHNESS_TOOL_SPECIFIC
    for kw in _PERIODIC_KEYWORDS:
        if kw in text:
            return FRESHNESS_PERIODIC
    return FRESHNESS_STABLE


def freshness_guidance(label: str) -> str:
    """Return a human-readable guidance string for a freshness label."""
    return _GUIDANCE.get(label, "")
