"""Safe mismatch logging helpers for DB mirror comparison results.

This module is intentionally pure with respect to application state: it opens
no DB connections, reads no environment variables, imports no routes, and does
not mutate SessionContext. Summaries exclude raw mismatch values and private
payloads.
"""

from __future__ import annotations

from collections.abc import Mapping


_SAFE_CONTEXT_FIELDS = frozenset({
    "session_id",
    "legacy_topic_id",
    "user_id",
    "source",
})


def summarize_mismatch_result(
    *,
    domain: str,
    comparison: dict | None,
) -> dict:
    """Return a compact, private-data-safe summary of a mismatch result."""
    summary = {
        "domain": str(domain or ""),
        "matches": None,
        "comparison_count": 0,
        "mismatch_count": 0,
        "mismatch_types": [],
    }

    if comparison is None:
        return summary

    matches = comparison.get("matches")
    summary["matches"] = matches if isinstance(matches, bool) else None

    comparisons = comparison.get("comparisons")
    if not isinstance(comparisons, list):
        comparisons = []

    summary["comparison_count"] = len(comparisons)

    mismatch_types: list[str] = []
    mismatch_count = 0

    for item in comparisons:
        if not isinstance(item, Mapping):
            continue

        item_matches = item.get("matches")
        if item_matches is not False:
            continue

        mismatch_type = str(item.get("type") or "unknown")
        if mismatch_type not in mismatch_types:
            mismatch_types.append(mismatch_type)

        item_count = _comparison_mismatch_count(item)
        mismatch_count += item_count if item_count > 0 else 1

    summary["mismatch_count"] = mismatch_count
    summary["mismatch_types"] = mismatch_types
    return summary


def log_mismatch_summary(
    *,
    logger,
    domain: str,
    comparison: dict | None,
    context: dict | None = None,
) -> dict:
    """Log and return a safe mismatch summary.

    INFO is used for matches and unknown/None match status. WARNING is used for
    confirmed mismatches. If logger is None, this only returns the summary.
    """
    summary = summarize_mismatch_result(domain=domain, comparison=comparison)
    safe_context = _safe_context(context)
    if safe_context:
        summary["context"] = safe_context

    if logger is None:
        return summary

    log_method = logger.warning if summary["matches"] is False else logger.info
    log_method("mismatch_summary", extra={"mismatch_summary": summary})
    return summary


def _comparison_mismatch_count(comparison: Mapping) -> int:
    count = 0

    mismatches = comparison.get("mismatches")
    if isinstance(mismatches, list):
        count += len(mismatches)

    missing_in_db = comparison.get("missing_in_db")
    if isinstance(missing_in_db, list):
        count += len(missing_in_db)

    extra_in_db = comparison.get("extra_in_db")
    if isinstance(extra_in_db, list):
        count += len(extra_in_db)

    return count


def _safe_context(context: dict | None) -> dict:
    if not isinstance(context, Mapping):
        return {}

    safe = {}
    for field in _SAFE_CONTEXT_FIELDS:
        value = context.get(field)
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            safe[field] = str(value)
    return safe
