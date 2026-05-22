"""Usage limit enforcement service.

Decides whether an expensive AI generation/evaluation action is permitted
for the current session, gated behind AI2_USAGE_LIMITS_ENABLED.

Design constraints
------------------
- Never opens a DB connection.
- Never makes Claude/provider calls.
- Never exposes internal policy details in user-facing messages.
- is_expensive_ai_action_allowed: never mutates SessionContext.
- enforce_ai_action_limit: records a limit_blocked event then raises.
"""

from __future__ import annotations

DAILY_AI_ACTION_LIMIT = 20

LIMIT_MESSAGE = (
    "You've reached today's free AI practice limit. "
    "You can still review saved lessons and continue your progress."
)

_EXPENSIVE_SOURCES = frozenset({"claude"})


class AIActionLimitError(Exception):
    """Raised when an AI action is blocked by the usage limit."""

    def __init__(self, message: str = LIMIT_MESSAGE) -> None:
        super().__init__(message)
        self.user_message = message


def count_expensive_ai_actions(session) -> int:
    """Return the number of expensive (Claude-billed) events in the session.

    Counts only events with source='claude'.
    cache, shared_cache, test_mode, limit_blocked, and manual are excluded.
    """
    return sum(1 for e in session.usage_events if e.get("source") in _EXPENSIVE_SOURCES)


def is_expensive_ai_action_allowed(session) -> dict:
    """Return a decision dict without mutating session.

    When AI2_USAGE_LIMITS_ENABLED is off, always returns allowed=True.
    When on, evaluates session-level expensive AI action count against
    DAILY_AI_ACTION_LIMIT.
    """
    from services.storage_flags import is_usage_limits_enabled

    if not is_usage_limits_enabled():
        return {
            "allowed":          True,
            "reason":           "limits_disabled",
            "ai_action_count":  0,
            "daily_limit":      DAILY_AI_ACTION_LIMIT,
            "message":          None,
        }

    count = count_expensive_ai_actions(session)
    if count >= DAILY_AI_ACTION_LIMIT:
        return {
            "allowed":          False,
            "reason":           "daily_limit_reached",
            "ai_action_count":  count,
            "daily_limit":      DAILY_AI_ACTION_LIMIT,
            "message":          LIMIT_MESSAGE,
        }

    return {
        "allowed":          True,
        "reason":           "allowed",
        "ai_action_count":  count,
        "daily_limit":      DAILY_AI_ACTION_LIMIT,
        "message":          None,
    }


def enforce_ai_action_limit(session) -> None:
    """Raise AIActionLimitError if the session has exceeded the AI action limit.

    When over the limit, records a limit_blocked usage event for auditing,
    then raises AIActionLimitError with the user-facing message.
    No-op (returns None) when AI2_USAGE_LIMITS_ENABLED is off or under limit.
    """
    decision = is_expensive_ai_action_allowed(session)
    if not decision["allowed"]:
        session.record_usage_event(
            event_type="ai_action_limit_blocked",
            model="",
            source="limit_blocked",
            status="success",
            metadata={
                "reason":           decision["reason"],
                "ai_action_count":  decision["ai_action_count"],
                "daily_limit":      decision["daily_limit"],
            },
        )
        raise AIActionLimitError(decision.get("message") or LIMIT_MESSAGE)
