"""Tests for the advance_week/current_week deprecation plan."""

from __future__ import annotations

from pathlib import Path

from config import TOTAL_WEEKS, CareerTrack
from context.session import SessionContext
from curriculum.syllabus import ROLE_TRACKS, WEEKS


DOC_PATH = Path("docs/ai2-advance-week-deprecation-plan.md")


def _doc() -> str:
    return DOC_PATH.read_text(encoding="utf-8")


def test_deprecation_plan_doc_exists():
    assert DOC_PATH.exists()
    assert _doc().startswith("# AI² advance_week Deprecation Plan")


def test_doc_mentions_core_compatibility_symbols():
    text = _doc()

    assert "advance_week" in text
    assert "TOTAL_WEEKS" in text
    assert "current_week" in text


def test_doc_recommends_modular_next_topic_current_position_replacement():
    text = _doc().lower()

    assert "next-topic/current-position helper" in text
    assert "current_module_key" in text
    assert "current_topic_key" in text
    assert "current_legacy_topic_id" in text
    assert "no fixed total week count" in text


def test_no_runtime_deletion_occurred():
    session = SessionContext(track=CareerTrack.AI_PM, current_week=2)

    assert hasattr(session, "current_week")
    assert hasattr(session, "advance_week")
    assert session.to_dict()["current_week"] == 2
    assert isinstance(TOTAL_WEEKS, int)
    assert WEEKS
    assert ROLE_TRACKS


def test_visible_ui_does_not_introduce_new_week_wording():
    template_text = "\n".join(
        Path(path).read_text(encoding="utf-8")
        for path in (
            "templates/dashboard.html",
            "templates/topics.html",
            "templates/todos.html",
            "templates/chat.html",
        )
    )

    forbidden_visible_phrases = (
        ">Week",
        " Week {{",
        "This Week",
        "this week",
        "Next Week",
        "next week",
        "Advance Week",
        "advance week",
        "Add to This Week",
    )
    for phrase in forbidden_visible_phrases:
        assert phrase not in template_text
