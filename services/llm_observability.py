"""No-op LLM observability wrapper.

Provides safe metadata helpers and a context manager for future LangSmith
tracing. All functions are safe no-ops when tracing is disabled (the default).

Rules enforced here:
- No LangSmith SDK import.
- No network calls.
- Metadata sanitizer strips secret-like keys and private content fields
  before any value leaves this module.
- Tracing is inactive unless LANGSMITH_TRACING=true AND LANGSMITH_API_KEY
  is non-empty (double gate via observability_flags).
"""

from __future__ import annotations

import contextlib
from typing import Any

from services.observability_flags import is_langsmith_tracing_enabled

# ── Keys that must never appear in trace metadata ─────────────────────────────

_BLOCKED_KEYS = frozenset({
    # credentials / secrets
    "api_key", "anthropic_api_key", "langsmith_api_key", "auth_secret",
    "auth_cookie", "cookie", "token", "debug_token", "password", "secret",
    # DB / infra URLs
    "database_url", "supabase_database_url", "db_url", "connection_string",
    # raw learner content
    "content", "generated_content", "prompt", "system_prompt",
    "answers", "submission", "portfolio_submission", "interview_answer",
    "notes", "private_notes", "learner_notes",
    # personal profile details
    "email", "display_name", "profile", "profile_details",
    # full message history
    "history", "messages", "chat_history",
})

# ── Keys that are explicitly safe to include ──────────────────────────────────

_SAFE_KEYS = frozenset({
    "session_id", "topic_id", "track_key", "activity_type", "route_type",
    "model", "practice_type", "from_cache", "latency_ms", "status",
    "usage_limit_blocked", "error_type", "turn_count", "score",
    "agent_used", "source", "refresh", "version",
})


def sanitize_trace_metadata(metadata: dict) -> dict:
    """Return a copy of metadata with all blocked keys removed.

    Keys not in _SAFE_KEYS are also removed unless they look structurally
    safe (non-string values that are numeric or boolean are kept if the key
    is not blocked). Only the _BLOCKED_KEYS set is guaranteed to be removed.
    Normalises keys to lowercase before checking.
    """
    safe: dict[str, Any] = {}
    for key, value in metadata.items():
        normalised = key.lower().replace("-", "_")
        if normalised in _BLOCKED_KEYS:
            continue
        if normalised in _SAFE_KEYS:
            safe[key] = value
    return safe


def build_safe_trace_metadata(
    *,
    topic_id: str | None = None,
    track_key: str | None = None,
    activity_type: str | None = None,
    model: str | None = None,
    practice_type: str | None = None,
    from_cache: bool | None = None,
    latency_ms: float | int | None = None,
    status: str | None = None,
    agent_used: str | None = None,
    source: str | None = None,
    **extra,
) -> dict:
    """Build a metadata dict from only known-safe keyword arguments.

    Unknown kwargs in **extra are passed through sanitize_trace_metadata so
    any accidentally blocked keys are stripped before the dict is returned.
    """
    base: dict[str, Any] = {}
    if topic_id     is not None: base["topic_id"]     = topic_id
    if track_key    is not None: base["track_key"]    = track_key
    if activity_type is not None: base["activity_type"] = activity_type
    if model        is not None: base["model"]        = model
    if practice_type is not None: base["practice_type"] = practice_type
    if from_cache   is not None: base["from_cache"]   = from_cache
    if latency_ms   is not None: base["latency_ms"]   = latency_ms
    if status       is not None: base["status"]       = status
    if agent_used   is not None: base["agent_used"]   = agent_used
    if source       is not None: base["source"]       = source
    if extra:
        base.update(sanitize_trace_metadata(extra))
    return base


def is_tracing_active() -> bool:
    """True only when LANGSMITH_TRACING=true and LANGSMITH_API_KEY is set."""
    return is_langsmith_tracing_enabled()


@contextlib.contextmanager
def trace_llm_call(name: str, metadata: dict | None = None):
    """Context manager wrapping a single LLM call for future tracing.

    Currently a no-op: yields immediately and does nothing whether tracing
    is enabled or not. When LangSmith SDK integration is added in a later
    slice, this context manager will be the single point of change.
    """
    yield
