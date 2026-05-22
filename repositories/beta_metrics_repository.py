"""Aggregate-only repository for internal private beta metrics."""

from __future__ import annotations


def collect_beta_metrics(conn) -> dict:
    """Return safe aggregate beta metrics using an existing DB connection."""
    return {
        "session_user_summary": _session_user_summary(conn),
        "usage_summary": _usage_summary(conn),
        "learning_outcomes_summary": _learning_outcomes_summary(conn),
        "beta_feedback_summary": _beta_feedback_summary(conn),
        "cache_summary": _cache_summary(conn),
    }


def _session_user_summary(conn) -> dict:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS total_sessions FROM sessions")
        sessions_row = cur.fetchone()
        cur.execute("SELECT COUNT(*) AS total_users FROM users")
        users_row = cur.fetchone()
    return {
        "total_sessions": _value(sessions_row, "total_sessions", 0),
        "total_users": _value(users_row, "total_users", 0),
    }


def _usage_summary(conn) -> dict:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                COUNT(*) AS total_usage_events,
                COUNT(*) FILTER (
                    WHERE source = 'claude'
                       OR COALESCE(model, '') ILIKE '%claude%'
                       OR event_type ILIKE '%claude%'
                ) AS claude_events,
                COUNT(*) FILTER (
                    WHERE source IN ('cache', 'shared_cache')
                       OR event_type ILIKE '%cache%'
                ) AS cache_events,
                COUNT(*) FILTER (
                    WHERE status = 'limit_blocked'
                       OR event_type = 'limit_blocked'
                ) AS limit_blocked_events
            FROM usage_events
            """
        )
        row = cur.fetchone()
    return {
        "total_usage_events": _value(row, "total_usage_events", 0),
        "claude_events": _value(row, "claude_events", 1),
        "cache_events": _value(row, "cache_events", 2),
        "limit_blocked_events": _value(row, "limit_blocked_events", 3),
    }


def _learning_outcomes_summary(conn) -> dict:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                COUNT(*) AS total_outcomes,
                COUNT(*) FILTER (
                    WHERE baseline_score IS NOT NULL
                       OR baseline_answer IS NOT NULL
                       OR baseline_prompt IS NOT NULL
                       OR status = 'baseline_completed'
                ) AS baseline_completed_count,
                COUNT(*) FILTER (
                    WHERE post_score IS NOT NULL
                       OR post_answer IS NOT NULL
                       OR post_prompt IS NOT NULL
                ) AS post_completed_count,
                COUNT(*) FILTER (WHERE status = 'improved') AS improved_count,
                AVG(improvement_delta) FILTER (
                    WHERE improvement_delta IS NOT NULL
                ) AS average_improvement_delta
            FROM learning_outcomes
            """
        )
        row = cur.fetchone()
    return {
        "total_outcomes": _value(row, "total_outcomes", 0),
        "baseline_completed_count": _value(row, "baseline_completed_count", 1),
        "post_completed_count": _value(row, "post_completed_count", 2),
        "improved_count": _value(row, "improved_count", 3),
        "average_improvement_delta": _rounded(_value(row, "average_improvement_delta", 4)),
    }


def _beta_feedback_summary(conn) -> dict:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                COUNT(*) AS total_feedback_submissions,
                AVG(usefulness_score) FILTER (
                    WHERE usefulness_score IS NOT NULL
                ) AS average_usefulness_score,
                AVG(clarity_score) FILTER (
                    WHERE clarity_score IS NOT NULL
                ) AS average_clarity_score
            FROM beta_feedback
            """
        )
        summary_row = cur.fetchone()
        cur.execute(
            """
            SELECT
                CASE
                    WHEN willingness_to_pay IS NULL OR btrim(willingness_to_pay) = ''
                    THEN 'not_specified'
                    WHEN lower(willingness_to_pay) LIKE '%yes%'
                    THEN 'yes'
                    WHEN lower(willingness_to_pay) LIKE '%no%'
                    THEN 'no'
                    WHEN lower(willingness_to_pay) LIKE '%maybe%'
                      OR lower(willingness_to_pay) LIKE '%not sure%'
                    THEN 'maybe'
                    ELSE 'other'
                END AS willingness_category,
                COUNT(*) AS count
            FROM beta_feedback
            GROUP BY willingness_category
            ORDER BY count DESC, willingness_category ASC
            """
        )
        count_rows = cur.fetchall()
    return {
        "total_feedback_submissions": _value(summary_row, "total_feedback_submissions", 0),
        "average_usefulness_score": _rounded(_value(summary_row, "average_usefulness_score", 1)),
        "average_clarity_score": _rounded(_value(summary_row, "average_clarity_score", 2)),
        "willingness_to_pay_counts": {
            str(_value(row, "willingness_category", 0)): _value(row, "count", 1)
            for row in count_rows
        },
    }


def _cache_summary(conn) -> dict:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                COUNT(*) AS total_rows,
                COUNT(*) FILTER (WHERE status = 'active') AS active_rows,
                COUNT(*) FILTER (WHERE status = 'stale') AS stale_rows
            FROM content_cache
            """
        )
        row = cur.fetchone()
    return {
        "total_rows": _value(row, "total_rows", 0),
        "active_rows": _value(row, "active_rows", 1),
        "stale_rows": _value(row, "stale_rows", 2),
    }


def _value(row, key: str, index: int):
    if row is None:
        return None
    if isinstance(row, dict):
        return row.get(key)
    return row[index]


def _rounded(value):
    if value is None:
        return None
    return round(float(value), 2)
