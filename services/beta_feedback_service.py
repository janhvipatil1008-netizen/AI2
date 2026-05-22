"""Pure validation helpers for private beta feedback."""

from __future__ import annotations

ALLOWED_FEEDBACK_CONTEXTS = {
    "quiz_feedback",
    "portfolio_feedback",
    "interview_feedback",
    "topic_lesson",
    "general",
}


def validate_score(score) -> int | None:
    """Return an integer score from 1 to 5, or None for blank/missing."""
    if score is None:
        return None
    if isinstance(score, str):
        score = score.strip()
        if not score:
            return None
    try:
        value = int(score)
    except (TypeError, ValueError) as exc:
        raise ValueError("score must be between 1 and 5") from exc
    if 1 <= value <= 5:
        return value
    raise ValueError("score must be between 1 and 5")


def normalize_feedback_context(context: str) -> str:
    """Normalize feedback context to the allowlist, falling back to general."""
    normalized = (context or "").strip().lower()
    if normalized in ALLOWED_FEEDBACK_CONTEXTS:
        return normalized
    return "general"


def sanitize_feedback_text(text: str | None, max_length: int = 1000) -> str | None:
    """Trim feedback text and cap length; blank text becomes None."""
    if text is None:
        return None
    cleaned = str(text).replace("\x00", "").strip()
    if not cleaned:
        return None
    return cleaned[:max_length]
