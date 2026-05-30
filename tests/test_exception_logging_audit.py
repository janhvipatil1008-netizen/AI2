"""Structural tests for the exception logging audit document.

These tests verify that docs/ai2-exception-logging-audit.md exists and
covers the required topics.  They do not execute any application code
and do not change runtime behaviour.
"""

from __future__ import annotations

from pathlib import Path

import pytest

DOC = Path("docs/ai2-exception-logging-audit.md")


def _doc() -> str:
    return DOC.read_text(encoding="utf-8")


# ── Document exists ───────────────────────────────────────────────────────────

def test_audit_doc_exists():
    assert DOC.exists(), f"{DOC} not found"


def test_audit_doc_is_not_empty():
    assert len(_doc()) > 500


# ── Required section headings ─────────────────────────────────────────────────

def test_doc_has_purpose_section():
    assert "## 1. Purpose" in _doc() or "# AI² Exception Logging Audit" in _doc()


def test_doc_has_findings_summary_section():
    assert "Findings Summary" in _doc()


def test_doc_has_high_priority_areas_section():
    assert "High-Priority Areas" in _doc()


def test_doc_has_recommended_logging_rules_section():
    assert "Recommended Logging Rules" in _doc()


def test_doc_has_first_implementation_slice_section():
    assert "First Implementation Slice" in _doc()


def test_doc_has_test_plan_section():
    assert "Test Plan" in _doc()


# ── Broad except blocks are addressed ────────────────────────────────────────

def test_doc_mentions_broad_except_blocks():
    doc = _doc()
    assert "except Exception" in doc or "broad" in doc.lower() or "silent" in doc.lower()


def test_doc_acknowledges_pass_in_except():
    assert "pass" in _doc()


def test_doc_references_silent_swallows():
    doc = _doc()
    assert "silent" in doc.lower() or "swallow" in doc.lower()


# ── High-priority areas covered ──────────────────────────────────────────────

def test_doc_mentions_db_write_through_failures():
    doc = _doc().lower()
    assert "write-through" in doc or "write_through" in doc


def test_doc_mentions_content_cache_failures():
    doc = _doc().lower()
    assert "content_cache" in doc or "content cache" in doc


def test_doc_mentions_content_cache_write_failure():
    doc = _doc().lower()
    assert "cache write" in doc or "content_cache write" in doc or "shared_cache_write" in doc


def test_doc_mentions_modular_progress_snapshot_failures():
    doc = _doc().lower()
    assert "modular progress" in doc or "modular_progress_snapshot" in doc


def test_doc_mentions_onboarding_enrollment_failures():
    doc = _doc().lower()
    assert "onboarding" in doc and ("enrollment" in doc or "enrolment" in doc)


def test_doc_mentions_job_failures():
    doc = _doc().lower()
    assert "job" in doc


def test_doc_mentions_claude_ai_failures():
    doc = _doc().lower()
    assert "claude" in doc or "ai provider" in doc


# ── Safety and logging rules ─────────────────────────────────────────────────

def test_doc_says_no_secrets_in_logs():
    doc = _doc().lower()
    assert "secret" in doc or "api key" in doc or "db url" in doc or "database_url" in doc


def test_doc_mentions_safe_error_metadata():
    assert "safe_error_metadata" in _doc()


def test_doc_says_learner_facing_behavior_unchanged():
    doc = _doc().lower()
    assert "learner-facing" in doc or "learner facing" in doc or "behavior" in doc


def test_doc_distinguishes_warning_vs_exception_severity():
    doc = _doc().lower()
    assert "logger.warning" in doc and ("logger.exception" in doc or "logger.error" in doc)


def test_doc_forbids_print_based_logging():
    doc = _doc().lower()
    assert "print" not in doc.split("## 4")[1].lower().split("##")[0] or \
           "never" in doc.split("## 4")[1].lower().split("##")[0]


# ── First implementation slice is specified ───────────────────────────────────

def test_doc_recommends_first_implementation_slice():
    doc = _doc()
    assert "First Implementation Slice" in doc or "first" in doc.lower()


def test_doc_names_content_cache_write_as_first_slice():
    doc = _doc().lower()
    # The recommended first slice should be in the content_service/content_cache area
    assert "content_service" in doc or "shared content_cache" in doc or "cache write" in doc


def test_doc_explains_why_first_slice_was_chosen():
    doc = _doc()
    # Should explain rationale (zero behavior change, already has logger, etc.)
    section = doc.split("## 5")[1] if "## 5" in doc else doc
    assert "behavior" in section.lower() or "zero" in section.lower() or "logger" in section.lower()


# ── Test plan requirements ────────────────────────────────────────────────────

def test_doc_test_plan_mentions_behavior_unchanged():
    doc = _doc()
    if "## 6" in doc:
        section = doc.split("## 6")[1]
    else:
        section = doc
    assert "behavior" in section.lower() or "unchanged" in section.lower()


def test_doc_test_plan_mentions_no_secrets_in_logs():
    doc = _doc()
    if "## 6" in doc:
        section = doc.split("## 6")[1]
    else:
        section = doc
    assert "secret" in section.lower() or "api key" in section.lower() or "db url" in section.lower()


def test_doc_test_plan_mentions_caplog():
    doc = _doc()
    assert "caplog" in doc


def test_doc_test_plan_mentions_existing_route_tests():
    doc = _doc().lower()
    assert "route" in doc and "test" in doc
