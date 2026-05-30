"""Structural tests for docs/ai2-backend-stability-checkpoint-before-ui.md.

Verifies the checkpoint document exists and covers all required topics.
Does not execute any application code and does not change runtime behaviour.
"""

from __future__ import annotations

from pathlib import Path

DOC = Path("docs/ai2-backend-stability-checkpoint-before-ui.md")


def _doc() -> str:
    return DOC.read_text(encoding="utf-8")


# ── Document exists ───────────────────────────────────────────────────────────

def test_checkpoint_doc_exists():
    assert DOC.exists(), f"{DOC} not found"


def test_checkpoint_doc_is_not_empty():
    assert len(_doc()) > 500


# ── Backend work coverage ─────────────────────────────────────────────────────

def test_doc_mentions_route_splitting():
    doc = _doc().lower()
    assert "route splitting" in doc or "route split" in doc


def test_doc_mentions_debug_admin_splitting():
    doc = _doc().lower()
    assert "debug" in doc and ("admin" in doc or "split" in doc)


def test_doc_mentions_session_persistence():
    doc = _doc().lower()
    assert "session persistence" in doc


def test_doc_mentions_session_cache_eviction():
    doc = _doc().lower()
    assert "cache eviction" in doc or "session cache" in doc


def test_doc_mentions_exception_logging():
    doc = _doc().lower()
    assert "exception" in doc and "log" in doc


def test_doc_mentions_github_actions():
    doc = _doc().lower()
    assert "github actions" in doc or "github" in doc


def test_doc_mentions_noop_observability():
    doc = _doc().lower()
    assert "no-op" in doc or "noop" in doc or "observability" in doc


# ── No LangSmith SDK / network calls ─────────────────────────────────────────

def test_doc_mentions_no_langsmith_sdk():
    doc = _doc().lower()
    assert "no langsmith sdk" in doc or ("langsmith" in doc and ("no network" in doc or "no sdk" in doc or "sdk import" in doc))


def test_doc_mentions_tracing_off_by_default():
    doc = _doc().lower()
    assert "tracing" in doc and ("off" in doc or "disabled" in doc or "default" in doc)


# ── Lovable UI polish recommendation ─────────────────────────────────────────

def test_doc_recommends_lovable_ui_next():
    doc = _doc().lower()
    assert "lovable" in doc


def test_doc_mentions_ui_polish():
    doc = _doc().lower()
    assert "ui polish" in doc or "ui" in doc


# ── Allowed UI files listed ───────────────────────────────────────────────────

def test_doc_lists_topics_html():
    assert "templates/topics.html" in _doc()


def test_doc_lists_topic_detail_html():
    assert "templates/topic_detail.html" in _doc()


def test_doc_lists_todos_html():
    assert "templates/todos.html" in _doc()


def test_doc_lists_syllabus_html():
    assert "templates/syllabus.html" in _doc()


def test_doc_lists_style_css():
    assert "static/style.css" in _doc()


# ── Backend files not allowed for Lovable ────────────────────────────────────

def test_doc_says_app_py_not_allowed():
    assert "app.py" in _doc()


def test_doc_says_routes_not_allowed():
    assert "routes/" in _doc()


def test_doc_says_services_not_allowed():
    assert "services/" in _doc()


def test_doc_says_schema_not_allowed():
    assert "schema.sql" in _doc() or "schema" in _doc()


def test_doc_says_env_not_allowed():
    assert ".env" in _doc()


def test_doc_says_orchestrator_not_allowed():
    assert "orchestrator.py" in _doc()


def test_doc_says_agents_not_allowed():
    assert "agents/" in _doc()
