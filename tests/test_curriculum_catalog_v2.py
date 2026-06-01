"""Tests for the market-aligned six-course curriculum catalog v2."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


COURSE_NAMES = {
    "AI Foundations",
    "AI Engineering & Building",
    "AI Evaluation & Quality",
    "AI Product & Strategy",
    "AI Data & Analytics",
    "AI Experience & Growth",
}

PROMPT_KEYS = {"learn", "quiz", "portfolio", "interview"}


@pytest.fixture
def catalog():
    import curriculum.curriculum_catalog as catalog_module

    return catalog_module


def _all_modules(export):
    return [module for course in export.courses for module in course.modules]


def _all_topics(export):
    return [topic for module in _all_modules(export) for topic in module.topics]


def test_build_full_curriculum_export_exists(catalog):
    assert callable(catalog.build_full_curriculum_export)


def test_summary_returns_six_courses(catalog):
    assert catalog.summary()["course_count"] == 6


def test_courses_include_market_aligned_six(catalog):
    export = catalog.build_full_curriculum_export()
    assert {course.title for course in export.courses} == COURSE_NAMES


def test_ai_foundations_metadata_is_prerequisite(catalog):
    export = catalog.build_full_curriculum_export()
    foundations = next(course for course in export.courses if course.title == "AI Foundations")

    assert foundations.metadata["is_prerequisite"] is True
    assert foundations.card_label == "Start here"


def test_other_five_courses_are_specialization_paths(catalog):
    export = catalog.build_full_curriculum_export()
    specializations = [course for course in export.courses if course.title != "AI Foundations"]

    assert len(specializations) == 5
    for course in specializations:
        assert course.metadata["is_specialization_path"] is True
        assert course.metadata["is_prerequisite"] is False
        assert course.card_label == "Specialization paths"
        assert course.path_type == "specialization"


def test_every_course_has_at_least_one_module(catalog):
    export = catalog.build_full_curriculum_export()
    for course in export.courses:
        assert course.modules, course.title


def test_every_module_has_at_least_one_topic(catalog):
    export = catalog.build_full_curriculum_export()
    for module in _all_modules(export):
        assert module.topics, module.module_key


def test_every_topic_has_activities(catalog):
    export = catalog.build_full_curriculum_export()
    for topic in _all_topics(export):
        assert topic.activities, topic.topic_key


def test_every_topic_metadata_has_prompts(catalog):
    export = catalog.build_full_curriculum_export()
    for topic in _all_topics(export):
        assert "prompts" in topic.metadata
        assert set(topic.metadata["prompts"]) == PROMPT_KEYS


def test_prompts_are_non_empty(catalog):
    export = catalog.build_full_curriculum_export()
    for topic in _all_topics(export):
        for key in PROMPT_KEYS:
            assert topic.metadata["prompts"][key].strip(), (topic.topic_key, key)


def test_topics_include_current_2026_market_concepts(catalog):
    export = catalog.build_full_curriculum_export()
    haystack = "\n".join(
        [
            topic.title
            + " "
            + topic.description
            + " "
            + " ".join(topic.metadata.get("market_concepts", []))
            for topic in _all_topics(export)
        ]
    )

    for concept in ("Agents", "MCP", "RAG", "Evals", "Guardrails", "Vector Databases"):
        assert concept in haystack
    assert "GEO" in haystack or "AEO" in haystack


def test_no_db_env_or_network_calls_happen_on_import(monkeypatch):
    sys.modules.pop("curriculum.curriculum_catalog", None)

    with patch("socket.create_connection", side_effect=AssertionError("network call")):
        module = importlib.import_module("curriculum.curriculum_catalog")

    assert module.summary()["course_count"] == 6


def test_catalog_source_does_not_import_db_env_or_network_helpers():
    source = Path("curriculum/curriculum_catalog.py").read_text(encoding="utf-8")
    forbidden = [
        "database.pool",
        "psycopg2",
        "os.environ",
        "getenv",
        "requests",
        "httpx",
        "urllib.request",
        "socket",
    ]
    for token in forbidden:
        assert token not in source
