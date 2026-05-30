"""Structural tests for docs/ai2-langsmith-observability-plan.md.

Verifies the plan document exists and covers all required topics.
Does not execute any application code and does not change runtime behaviour.
"""

from __future__ import annotations

from pathlib import Path

DOC = Path("docs/ai2-langsmith-observability-plan.md")


def _doc() -> str:
    return DOC.read_text(encoding="utf-8")


# ── Document exists ───────────────────────────────────────────────────────────

def test_plan_doc_exists():
    assert DOC.exists(), f"{DOC} not found"


def test_plan_doc_is_not_empty():
    assert len(_doc()) > 500


# ── LangSmith mentioned ───────────────────────────────────────────────────────

def test_doc_mentions_langsmith():
    assert "LangSmith" in _doc()


def test_doc_mentions_tracing():
    assert "tracing" in _doc().lower() or "Tracing" in _doc()


# ── AI paths covered ──────────────────────────────────────────────────────────

def test_doc_mentions_structured_topic_learning_path():
    doc = _doc().lower()
    assert "structured" in doc


def test_doc_mentions_chat_orchestrator_path():
    doc = _doc().lower()
    assert "chat" in doc and "orchestrator" in doc


# ── Env var: off by default ───────────────────────────────────────────────────

def test_doc_mentions_langsmith_tracing_false():
    assert "LANGSMITH_TRACING=false" in _doc()


def test_doc_says_keep_off_by_default():
    doc = _doc().lower()
    assert "off by default" in doc or "default" in doc


# ── Safe metadata policy ──────────────────────────────────────────────────────

def test_doc_mentions_safe_metadata():
    doc = _doc().lower()
    assert "safe metadata" in doc or "allowed" in doc


def test_doc_mentions_disallowed_metadata():
    doc = _doc().lower()
    assert "disallowed" in doc or "never" in doc


def test_doc_says_no_api_keys_in_metadata():
    doc = _doc().lower()
    assert "api key" in doc or "anthropic_api_key" in doc


def test_doc_says_no_db_urls_in_metadata():
    doc = _doc().lower()
    assert "database_url" in doc or "db url" in doc or "database url" in doc


def test_doc_says_no_submission_text_in_metadata():
    doc = _doc().lower()
    assert "submission" in doc


# ── Structured calls first ────────────────────────────────────────────────────

def test_doc_recommends_structured_calls_first():
    doc = _doc().lower()
    assert "first" in doc and "structured" in doc


def test_doc_mentions_generate_lesson():
    doc = _doc().lower()
    assert "generate lesson" in doc or "generate_learning_content" in doc


def test_doc_mentions_quiz_feedback():
    doc = _doc().lower()
    assert "quiz" in doc and "feedback" in doc


def test_doc_mentions_portfolio_feedback():
    doc = _doc().lower()
    assert "portfolio" in doc and "feedback" in doc


def test_doc_mentions_interview_feedback():
    doc = _doc().lower()
    assert "interview" in doc and "feedback" in doc


# ── No network call when disabled ────────────────────────────────────────────

def test_doc_mentions_no_network_call_when_disabled():
    doc = _doc().lower()
    assert "no network" in doc or "network call" in doc


# ── Implementation plan ───────────────────────────────────────────────────────

def test_doc_mentions_noop_wrapper():
    doc = _doc().lower()
    assert "no-op" in doc or "noop" in doc or "wrapper" in doc


def test_doc_mentions_llm_observability_module():
    assert "llm_observability" in _doc()


# ── Env vars present ─────────────────────────────────────────────────────────

def test_doc_mentions_langsmith_api_key_var():
    assert "LANGSMITH_API_KEY" in _doc()


def test_doc_mentions_langsmith_project_var():
    assert "LANGSMITH_PROJECT" in _doc()
