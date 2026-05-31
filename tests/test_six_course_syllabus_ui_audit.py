"""Structural tests for docs/ai2-six-course-syllabus-ui-audit.md."""

from __future__ import annotations

from pathlib import Path


DOC = Path("docs/ai2-six-course-syllabus-ui-audit.md")

COURSE_NAMES = [
    "AI Foundations",
    "AI Engineering & Building",
    "AI Evaluation & Quality",
    "AI Product & Strategy",
    "AI Data & Analytics",
    "AI Experience & Growth",
]


def _doc() -> str:
    return DOC.read_text(encoding="utf-8")


def test_doc_exists():
    assert DOC.exists()


def test_doc_mentions_all_six_course_names():
    text = _doc()
    for course_name in COURSE_NAMES:
        assert course_name in text


def test_doc_says_ai_foundations_is_start_here():
    text = _doc()
    assert "AI Foundations" in text
    assert "Start here" in text


def test_doc_says_other_five_are_specialization_paths():
    text = _doc()
    for course_name in COURSE_NAMES[1:]:
        assert course_name in text
    assert "Specialization paths" in text


def test_doc_mentions_current_course_track_selection_flow():
    text = _doc().lower()
    assert "current course/track selection flow" in text
    assert "track" in text
    assert "/session/start" in text


def test_doc_mentions_modular_db_reads_and_feature_flags():
    text = _doc()
    assert "modular DB" in text or "modular db" in text.lower()
    assert "feature flags" in text.lower()
    assert "AI2_MODULAR_CURRICULUM_READS_ENABLED" in text


def test_doc_recommends_curriculum_catalog_as_pure_data_first():
    text = _doc().lower()
    assert "curriculum_catalog.py" in text
    assert "pure data first" in text


def test_doc_warns_not_to_seed_db_until_tests_pass():
    text = _doc().lower()
    assert "do not seed db until tests pass" in text
    assert "scripts/seed_modular_curriculum.py" in _doc()
