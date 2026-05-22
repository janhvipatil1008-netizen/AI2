"""Tests for harness/usage_policy.py — structured policy decisions, not yet enforced."""

from harness.usage_policy import (
    DEFAULT_CACHE_WARNING_THRESHOLD,
    DEFAULT_CLAUDE_EVENT_LIMIT,
    DEFAULT_DAILY_GENERATION_LIMIT,
    DEFAULT_ERROR_LIMIT,
    DEFAULT_REFRESH_LIMIT,
    UsagePolicyDecision,
    cache_hit_ratio,
    can_generate,
    claude_event_count,
    error_event_count,
    evaluate_usage_policy,
    safe_int,
)


# ── safe_int ──────────────────────────────────────────────────────────────────

def test_safe_int_handles_plain_int():
    assert safe_int(5) == 5


def test_safe_int_handles_numeric_string():
    assert safe_int("12") == 12


def test_safe_int_handles_float_string():
    assert safe_int("3.7") == 3


def test_safe_int_returns_default_for_none():
    assert safe_int(None) == 0
    assert safe_int(None, default=99) == 99


def test_safe_int_returns_default_for_invalid_string():
    assert safe_int("bad") == 0
    assert safe_int("bad", default=7) == 7


def test_safe_int_clamps_negative_to_zero():
    assert safe_int(-3) == 0
    assert safe_int("-5") == 0


def test_safe_int_zero_stays_zero():
    assert safe_int(0) == 0


# ── cache_hit_ratio ───────────────────────────────────────────────────────────

def test_cache_hit_ratio_zero_for_no_events():
    assert cache_hit_ratio({}) == 0.0
    assert cache_hit_ratio({"total_events": 0}) == 0.0


def test_cache_hit_ratio_all_cache():
    summary = {"total_events": 10, "cache_events": 10}
    assert cache_hit_ratio(summary) == 1.0


def test_cache_hit_ratio_half():
    summary = {"total_events": 10, "cache_events": 5}
    assert cache_hit_ratio(summary) == 0.5


def test_cache_hit_ratio_zero_cache():
    summary = {"total_events": 8, "cache_events": 0}
    assert cache_hit_ratio(summary) == 0.0


def test_cache_hit_ratio_missing_cache_events_treated_as_zero():
    summary = {"total_events": 4}
    assert cache_hit_ratio(summary) == 0.0


# ── claude_event_count / error_event_count ────────────────────────────────────

def test_claude_event_count_returns_value():
    assert claude_event_count({"claude_events": 7}) == 7


def test_claude_event_count_missing_key_returns_zero():
    assert claude_event_count({}) == 0


def test_claude_event_count_handles_none_value():
    assert claude_event_count({"claude_events": None}) == 0


def test_error_event_count_returns_value():
    assert error_event_count({"error_events": 3}) == 3


def test_error_event_count_missing_key_returns_zero():
    assert error_event_count({}) == 0


# ── can_generate (backward-compatible) ────────────────────────────────────────

def test_can_generate_true_when_under_limit():
    assert can_generate({}) is True
    assert can_generate({"total_events": DEFAULT_DAILY_GENERATION_LIMIT - 1}) is True


def test_can_generate_false_at_limit():
    assert can_generate({"total_events": DEFAULT_DAILY_GENERATION_LIMIT}) is False


def test_can_generate_false_over_limit():
    assert can_generate({"total_events": DEFAULT_DAILY_GENERATION_LIMIT + 5}) is False


def test_can_generate_custom_limit():
    assert can_generate({"total_events": 2}, limit=2) is False
    assert can_generate({"total_events": 1}, limit=2) is True


# ── evaluate_usage_policy — allowed ───────────────────────────────────────────

def test_evaluate_usage_policy_allowed_when_all_under_limits():
    decision = evaluate_usage_policy({"total_events": 0})
    assert decision.allowed is True
    assert decision.reason == "allowed"
    assert isinstance(decision.warnings, list)
    assert isinstance(decision.metadata, dict)


def test_evaluate_usage_policy_returns_usage_policy_decision():
    decision = evaluate_usage_policy({})
    assert isinstance(decision, UsagePolicyDecision)


# ── evaluate_usage_policy — hard blocks ───────────────────────────────────────

def test_evaluate_usage_policy_blocks_on_daily_limit():
    summary = {"total_events": DEFAULT_DAILY_GENERATION_LIMIT}
    decision = evaluate_usage_policy(summary)
    assert decision.allowed is False
    assert decision.reason == "daily_limit_reached"


def test_evaluate_usage_policy_blocks_on_daily_limit_exceeded():
    summary = {"total_events": DEFAULT_DAILY_GENERATION_LIMIT + 10}
    decision = evaluate_usage_policy(summary)
    assert decision.allowed is False
    assert decision.reason == "daily_limit_reached"


def test_evaluate_usage_policy_blocks_on_claude_limit():
    summary = {
        "total_events": 5,
        "claude_events": DEFAULT_CLAUDE_EVENT_LIMIT,
    }
    decision = evaluate_usage_policy(summary)
    assert decision.allowed is False
    assert decision.reason == "claude_limit_reached"


def test_evaluate_usage_policy_blocks_on_error_limit():
    summary = {
        "total_events": 5,
        "claude_events": 3,
        "error_events": DEFAULT_ERROR_LIMIT,
    }
    decision = evaluate_usage_policy(summary)
    assert decision.allowed is False
    assert decision.reason == "error_limit_reached"


def test_evaluate_usage_policy_daily_limit_takes_precedence_over_claude_limit():
    summary = {
        "total_events": DEFAULT_DAILY_GENERATION_LIMIT,
        "claude_events": DEFAULT_CLAUDE_EVENT_LIMIT,
    }
    decision = evaluate_usage_policy(summary)
    assert decision.reason == "daily_limit_reached"


# ── evaluate_usage_policy — warnings ──────────────────────────────────────────

def test_evaluate_usage_policy_near_daily_limit_warning():
    threshold = int(DEFAULT_DAILY_GENERATION_LIMIT * 0.8)
    summary = {"total_events": threshold}
    decision = evaluate_usage_policy(summary)
    assert "near_daily_limit" in decision.warnings


def test_evaluate_usage_policy_no_near_daily_limit_warning_when_well_under():
    summary = {"total_events": 1}
    decision = evaluate_usage_policy(summary)
    assert "near_daily_limit" not in decision.warnings


def test_evaluate_usage_policy_near_claude_limit_warning():
    threshold = int(DEFAULT_CLAUDE_EVENT_LIMIT * 0.8)
    summary = {"total_events": 5, "claude_events": threshold}
    decision = evaluate_usage_policy(summary)
    assert "near_claude_limit" in decision.warnings


def test_evaluate_usage_policy_recent_errors_warning():
    summary = {"total_events": 5, "error_events": 1}
    decision = evaluate_usage_policy(summary)
    assert "recent_errors" in decision.warnings


def test_evaluate_usage_policy_no_recent_errors_warning_when_zero():
    summary = {"total_events": 5, "error_events": 0}
    decision = evaluate_usage_policy(summary)
    assert "recent_errors" not in decision.warnings


def test_evaluate_usage_policy_low_cache_hit_ratio_warning():
    # 10 events, 0 cache hits → ratio 0.0 < threshold 0.2
    summary = {"total_events": 10, "cache_events": 0}
    decision = evaluate_usage_policy(summary)
    assert "low_cache_hit_ratio" in decision.warnings


def test_evaluate_usage_policy_no_low_cache_warning_when_above_threshold():
    # 10 events, 5 cache hits → ratio 0.5 > threshold 0.2
    summary = {"total_events": 10, "cache_events": 5}
    decision = evaluate_usage_policy(summary)
    assert "low_cache_hit_ratio" not in decision.warnings


def test_evaluate_usage_policy_no_low_cache_warning_when_no_events():
    decision = evaluate_usage_policy({})
    assert "low_cache_hit_ratio" not in decision.warnings


def test_evaluate_usage_policy_multiple_warnings_can_coexist():
    threshold_daily = int(DEFAULT_DAILY_GENERATION_LIMIT * 0.8)
    summary = {
        "total_events": threshold_daily,
        "cache_events": 0,
        "error_events": 1,
    }
    decision = evaluate_usage_policy(summary)
    assert "near_daily_limit" in decision.warnings
    assert "recent_errors" in decision.warnings
    assert "low_cache_hit_ratio" in decision.warnings


# ── evaluate_usage_policy — metadata ──────────────────────────────────────────

def test_evaluate_usage_policy_metadata_includes_expected_fields():
    summary = {
        "total_events": 10,
        "claude_events": 5,
        "cache_events": 3,
        "error_events": 1,
    }
    decision = evaluate_usage_policy(summary)
    for key in [
        "total_events", "claude_events", "cache_events", "error_events",
        "cache_hit_ratio", "daily_limit", "claude_limit", "error_limit",
    ]:
        assert key in decision.metadata, f"missing metadata key: {key}"


def test_evaluate_usage_policy_metadata_values_are_correct():
    summary = {
        "total_events": 8,
        "claude_events": 4,
        "cache_events": 2,
        "error_events": 1,
    }
    decision = evaluate_usage_policy(summary)
    assert decision.metadata["total_events"] == 8
    assert decision.metadata["claude_events"] == 4
    assert decision.metadata["cache_events"] == 2
    assert decision.metadata["error_events"] == 1
    assert decision.metadata["cache_hit_ratio"] == 0.25
    assert decision.metadata["daily_limit"] == DEFAULT_DAILY_GENERATION_LIMIT
    assert decision.metadata["claude_limit"] == DEFAULT_CLAUDE_EVENT_LIMIT
    assert decision.metadata["error_limit"] == DEFAULT_ERROR_LIMIT


def test_evaluate_usage_policy_custom_limits_reflected_in_metadata():
    decision = evaluate_usage_policy({}, daily_limit=50, claude_limit=30, error_limit=10)
    assert decision.metadata["daily_limit"] == 50
    assert decision.metadata["claude_limit"] == 30
    assert decision.metadata["error_limit"] == 10


# ── constants exist ───────────────────────────────────────────────────────────

def test_constants_are_defined():
    assert DEFAULT_DAILY_GENERATION_LIMIT == 20
    assert DEFAULT_REFRESH_LIMIT == 5
    assert DEFAULT_ERROR_LIMIT == 5
    assert DEFAULT_CLAUDE_EVENT_LIMIT == 15
    assert DEFAULT_CACHE_WARNING_THRESHOLD == 0.2
