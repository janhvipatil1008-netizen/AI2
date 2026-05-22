"""Harness usage policy: structured decision helpers, not yet enforced in routes."""

from dataclasses import dataclass, field

DEFAULT_DAILY_GENERATION_LIMIT = 20
DEFAULT_DAILY_AI_ACTION_LIMIT  = 20
DEFAULT_MONTHLY_AI_ACTION_LIMIT = 200

_EXPENSIVE_AI_SOURCES = frozenset({"claude"})
DEFAULT_REFRESH_LIMIT = 5
DEFAULT_ERROR_LIMIT = 5
DEFAULT_CLAUDE_EVENT_LIMIT = 15
DEFAULT_CACHE_WARNING_THRESHOLD = 0.2


@dataclass
class UsagePolicyDecision:
    allowed: bool
    reason: str
    warnings: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


def safe_int(value, default: int = 0) -> int:
    """Convert value to a non-negative int; return default on failure.

    Routes through float first so numeric strings like "3.7" are accepted.
    """
    try:
        result = int(float(value))
    except (TypeError, ValueError):
        return default
    return max(result, 0)


def cache_hit_ratio(usage_summary: dict) -> float:
    """Return cache_events / total_events, or 0.0 if no events recorded."""
    total = safe_int(usage_summary.get("total_events", 0))
    if total == 0:
        return 0.0
    return safe_int(usage_summary.get("cache_events", 0)) / total


def claude_event_count(usage_summary: dict) -> int:
    """Return the number of Claude-sourced events from a usage summary."""
    return safe_int(usage_summary.get("claude_events", 0))


def error_event_count(usage_summary: dict) -> int:
    """Return the number of error events from a usage summary."""
    return safe_int(usage_summary.get("error_events", 0))


def can_generate(
    usage_summary: dict,
    *,
    limit: int = DEFAULT_DAILY_GENERATION_LIMIT,
) -> bool:
    """Return True if total_events is below the daily generation limit."""
    total_events = safe_int(usage_summary.get("total_events", 0))
    return total_events < limit


def evaluate_usage_policy(
    usage_summary: dict,
    *,
    daily_limit: int = DEFAULT_DAILY_GENERATION_LIMIT,
    claude_limit: int = DEFAULT_CLAUDE_EVENT_LIMIT,
    error_limit: int = DEFAULT_ERROR_LIMIT,
    cache_warning_threshold: float = DEFAULT_CACHE_WARNING_THRESHOLD,
) -> UsagePolicyDecision:
    """Evaluate usage against policy limits and return a structured decision.

    Does not enforce anything — callers decide what to do with the result.
    """
    total  = safe_int(usage_summary.get("total_events", 0))
    claude = claude_event_count(usage_summary)
    errors = error_event_count(usage_summary)
    cache  = safe_int(usage_summary.get("cache_events", 0))
    ratio  = cache_hit_ratio(usage_summary)

    # Hard blocks (first match wins)
    if total >= daily_limit:
        allowed, reason = False, "daily_limit_reached"
    elif claude >= claude_limit:
        allowed, reason = False, "claude_limit_reached"
    elif errors >= error_limit:
        allowed, reason = False, "error_limit_reached"
    else:
        allowed, reason = True, "allowed"

    # Soft warnings (accumulate all that apply)
    warnings: list[str] = []
    if total >= daily_limit * 0.8:
        warnings.append("near_daily_limit")
    if claude >= claude_limit * 0.8:
        warnings.append("near_claude_limit")
    if errors > 0:
        warnings.append("recent_errors")
    if total > 0 and ratio < cache_warning_threshold:
        warnings.append("low_cache_hit_ratio")

    metadata = {
        "total_events":    total,
        "claude_events":   claude,
        "cache_events":    cache,
        "error_events":    errors,
        "cache_hit_ratio": ratio,
        "daily_limit":     daily_limit,
        "claude_limit":    claude_limit,
        "error_limit":     error_limit,
    }

    return UsagePolicyDecision(
        allowed=allowed,
        reason=reason,
        warnings=warnings,
        metadata=metadata,
    )


def evaluate_ai_action_limit(
    usage_summary: dict,
    *,
    daily_limit: int = DEFAULT_DAILY_AI_ACTION_LIMIT,
    monthly_limit: int = DEFAULT_MONTHLY_AI_ACTION_LIMIT,
) -> dict:
    """Evaluate whether an expensive AI generation/evaluation action is allowed.

    Counts only events from expensive sources (claude).  cache, shared_cache,
    and test_mode events are not counted.  Monthly filtering is not yet
    implemented — session-level totals are used as a proxy.

    Returns a plain dict (not a dataclass) for easy JSON serialisation.
    """
    expensive_count = safe_int(usage_summary.get("claude_events", 0))

    if expensive_count >= daily_limit:
        allowed, reason = False, "daily_limit_reached"
    else:
        allowed, reason = True, "allowed"

    return {
        "allowed":            allowed,
        "reason":             reason,
        "daily_limit":        daily_limit,
        "monthly_limit":      monthly_limit,
        "current_ai_actions": expensive_count,
    }
