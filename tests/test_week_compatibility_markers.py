"""Text checks for week-based compatibility-only markers."""

from __future__ import annotations

import os
from pathlib import Path

os.environ["AI2_TEST_MODE"] = "1"
os.environ["ANTHROPIC_API_KEY"] = "test-key"

from config import TOTAL_WEEKS, CareerTrack
from context.session import SessionContext


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_session_context_marks_week_internals_compatibility_only():
    text = _read("context/session.py")

    assert "compatibility-only" in text
    assert "TOTAL_WEEKS bounds old current_week fallback behavior" in text
    assert "current_week:       int = 1" in text
    assert "def advance_week" in text
    assert "Do not use for new modular curriculum features" in text
    assert "course/module/topic sequence_order" in text
    assert "learner enrollment/progress state" in text


def test_config_marks_total_weeks_compatibility_only():
    text = _read("config.py")

    assert "compatibility-only: fixed week count" in text
    assert "TOTAL_WEEKS = 5" in text


def test_curriculum_topics_marks_get_topics_for_week_compatibility_only():
    text = _read("curriculum/topics.py")

    assert "compatibility-only" in text
    assert "def get_topics_for_week" in text
    assert "static fallback topic lookup" in text
    assert "legacy topic IDs" in text


def test_syllabus_marks_static_fallback_structures_compatibility_only():
    text = _read("curriculum/syllabus.py")

    assert "compatibility-only" in text
    assert "ROLE_TRACKS = {" in text
    assert "WEEKS = [" in text
    assert "Do not use WEEKS for new modular curriculum features" in text


def test_docs_mention_compatibility_only_status():
    current_week_doc = _read("docs/ai2-current-week-removal-checklist.md")
    advance_week_doc = _read("docs/ai2-advance-week-deprecation-plan.md")

    for text in (current_week_doc, advance_week_doc):
        assert "Step 128 marked week-based internals as compatibility-only" in text
        assert "modular course/module/topic state" in text
        assert "Removal is still pending until the compatibility migration is complete" in text


def test_current_week_and_advance_week_still_exist():
    session = SessionContext(track=CareerTrack.AI_PM, current_week=1)

    assert hasattr(session, "current_week")
    assert hasattr(session, "advance_week")
    assert session.current_week == 1
    assert isinstance(TOTAL_WEEKS, int)


def test_no_route_url_change_for_marker_step():
    import app as app_module

    routes = {
        (route.path, ",".join(sorted(getattr(route, "methods", set()) or [])))
        for route in app_module.app.routes
        if hasattr(route, "methods")
    }

    assert ("/dashboard", "GET") in routes
    assert ("/topics/{session_id}", "GET") in routes
    assert ("/todos/{session_id}", "GET") in routes
    assert ("/chat/{session_id}", "GET") in routes


def test_runtime_behavior_unchanged_for_advance_week():
    session = SessionContext(track=CareerTrack.AI_PM, current_week=1)

    assert session.advance_week() is True
    assert session.current_week == 2
    session.current_week = TOTAL_WEEKS
    assert session.advance_week() is False
    assert session.current_week == TOTAL_WEEKS
