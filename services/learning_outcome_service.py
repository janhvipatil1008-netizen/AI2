"""Pure helpers for learning outcome validation summaries.

These functions do not open DB connections, read environment variables, import
routes, or mutate runtime state. They operate on already-provided values.
"""

from __future__ import annotations


def calculate_improvement_delta(
    baseline_score: int | None,
    post_score: int | None,
) -> int | None:
    """Return post_score - baseline_score when both scores are available."""
    if baseline_score is None or post_score is None:
        return None
    return int(post_score) - int(baseline_score)


def classify_learning_outcome(delta: int | None) -> str:
    """Classify the post-topic outcome status from an improvement delta."""
    if delta is None:
        return "completed"
    if delta < 0:
        return "needs_review"
    return "improved"


def summarize_learning_outcome(outcome: dict | None) -> dict:
    """Return a safe summary that excludes prompts, answers, and metadata."""
    if not outcome:
        return {
            "has_baseline": False,
            "has_post": False,
            "baseline_score": None,
            "post_score": None,
            "improvement_delta": None,
            "status": None,
        }

    baseline_score = outcome.get("baseline_score")
    post_score = outcome.get("post_score")
    return {
        "has_baseline": bool(
            outcome.get("baseline_answer") is not None
            or outcome.get("baseline_prompt") is not None
            or baseline_score is not None
        ),
        "has_post": bool(
            outcome.get("post_answer") is not None
            or outcome.get("post_prompt") is not None
            or post_score is not None
        ),
        "baseline_score": baseline_score,
        "post_score": post_score,
        "improvement_delta": outcome.get("improvement_delta"),
        "status": outcome.get("status"),
    }
