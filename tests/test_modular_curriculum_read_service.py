"""Tests for services/modular_curriculum_read_service.py.

No real DB connection required.  Repository functions are patched at source.
"""

from __future__ import annotations

import inspect
import re
from unittest.mock import MagicMock, patch

import pytest

import services.modular_curriculum_read_service as svc


# ── Import / API surface ──────────────────────────────────────────────────────

def test_module_imports_safely():
    assert svc is not None


def test_expected_normalizers_exist():
    for fn in (
        "normalize_course",
        "normalize_module",
        "normalize_topic",
        "normalize_skill",
        "normalize_activity",
    ):
        assert hasattr(svc, fn), f"Missing normalizer: {fn}"


def test_expected_read_functions_exist():
    for fn in (
        "get_course_structure",
        "list_available_courses",
        "get_topic_structure_by_legacy_id",
    ):
        assert hasattr(svc, fn), f"Missing function: {fn}"


# ── Isolation guards ──────────────────────────────────────────────────────────

def _src() -> str:
    return inspect.getsource(svc)


def test_no_db_connection_creation():
    src = _src()
    assert "psycopg2.connect" not in src
    assert "database.pool" not in src or not re.search(
        r"^\s*(import|from)\s+database\.pool", src, re.MULTILINE
    )


def test_no_env_reads():
    src = _src()
    assert "os.environ" not in src
    assert "os.getenv" not in src


def test_no_app_routes_imports():
    src = _src()
    for bad in ("from app", "import app", "from routes", "import routes"):
        assert bad not in src, f"Forbidden import: {bad}"


def test_no_commit_or_rollback():
    src = _src()
    assert ".commit()" not in src
    assert ".rollback()" not in src


def test_no_claude_or_anthropic_calls():
    src = _src()
    # Only catch actual import/call patterns, not references in comments/docstrings
    for bad in (
        r"^\s*(import|from)\s+anthropic",
        r"anthropic\.Anthropic\(",
        r"boto3.*bedrock",
        r"openai\.",
    ):
        assert not re.search(bad, src, re.MULTILINE | re.IGNORECASE), (
            f"Unexpected provider reference pattern: {bad}"
        )


# ── normalize_course ──────────────────────────────────────────────────────────

def test_normalize_course_returns_none_for_none():
    assert svc.normalize_course(None) is None


def test_normalize_course_preserves_all_expected_keys():
    row = {
        "course_id": 1, "course_key": "aipm-foundations",
        "title": "AI PM", "description": "desc", "target_audience": "PMs",
        "level": "beginner", "status": "active", "version": "v1",
        "sequence_order": 0, "metadata": {"x": 1},
    }
    result = svc.normalize_course(row)
    for key in ("course_id", "course_key", "title", "description",
                "target_audience", "level", "status", "version",
                "sequence_order", "metadata"):
        assert key in result, f"normalize_course missing key: {key}"


def test_normalize_course_does_not_mutate_input():
    row = {"course_id": 1, "course_key": "k"}
    original = dict(row)
    svc.normalize_course(row)
    assert row == original


def test_normalize_course_uses_defaults_for_missing_keys():
    result = svc.normalize_course({"course_id": 5})
    assert result["course_key"] == ""
    assert result["level"] == "beginner"
    assert result["status"] == "draft"
    assert result["version"] == "v1"
    assert result["sequence_order"] == 0
    assert result["metadata"] == {}


def test_normalize_course_metadata_none_becomes_empty_dict():
    result = svc.normalize_course({"course_id": 1, "metadata": None})
    assert result["metadata"] == {}


# ── normalize_module ──────────────────────────────────────────────────────────

def test_normalize_module_returns_none_for_none():
    assert svc.normalize_module(None) is None


def test_normalize_module_preserves_all_expected_keys():
    row = {
        "module_id": 10, "course_id": 1, "module_key": "module-01",
        "title": "Mod 1", "description": "d", "sequence_order": 0,
        "estimated_minutes": 90, "status": "active", "metadata": {},
    }
    result = svc.normalize_module(row)
    for key in ("module_id", "course_id", "module_key", "title", "description",
                "sequence_order", "estimated_minutes", "status", "metadata"):
        assert key in result, f"normalize_module missing key: {key}"


def test_normalize_module_does_not_mutate_input():
    row = {"module_id": 10, "module_key": "m"}
    original = dict(row)
    svc.normalize_module(row)
    assert row == original


def test_normalize_module_defaults():
    result = svc.normalize_module({"module_id": 7})
    assert result["module_key"] == ""
    assert result["status"] == "active"
    assert result["sequence_order"] == 0
    assert result["metadata"] == {}
    assert result["estimated_minutes"] is None


# ── normalize_topic ───────────────────────────────────────────────────────────

def test_normalize_topic_returns_none_for_none():
    assert svc.normalize_topic(None) is None


def test_normalize_topic_preserves_all_expected_keys():
    row = {
        "topic_id": 20, "course_id": 1, "module_id": 10,
        "legacy_topic_id": "aipm-week-1-transformers",
        "topic_key": "transformers", "title": "Transformers",
        "description": "d", "difficulty_level": "beginner",
        "sequence_order": 0, "estimated_minutes": 45,
        "status": "active", "metadata": {},
    }
    result = svc.normalize_topic(row)
    for key in ("topic_id", "course_id", "module_id", "legacy_topic_id",
                "topic_key", "title", "description", "difficulty_level",
                "sequence_order", "estimated_minutes", "status", "metadata"):
        assert key in result, f"normalize_topic missing key: {key}"


def test_normalize_topic_does_not_mutate_input():
    row = {"topic_id": 20, "topic_key": "t"}
    original = dict(row)
    svc.normalize_topic(row)
    assert row == original


def test_normalize_topic_defaults():
    result = svc.normalize_topic({"topic_id": 3})
    assert result["difficulty_level"] == "beginner"
    assert result["status"] == "active"
    assert result["legacy_topic_id"] == ""
    assert result["metadata"] == {}


# ── normalize_skill ───────────────────────────────────────────────────────────

def test_normalize_skill_returns_none_for_none():
    assert svc.normalize_skill(None) is None


def test_normalize_skill_preserves_all_expected_keys():
    row = {
        "skill_id": 1, "skill_key": "prompt_engineering", "title": "Prompting",
        "description": "d", "category": "prompting", "level": "beginner",
        "importance": "core",
    }
    result = svc.normalize_skill(row)
    for key in ("skill_id", "skill_key", "title", "description",
                "category", "level", "importance"):
        assert key in result, f"normalize_skill missing key: {key}"


def test_normalize_skill_includes_importance_with_default():
    result = svc.normalize_skill({"skill_id": 1, "skill_key": "rag"})
    assert result["importance"] == "core"


def test_normalize_skill_does_not_mutate_input():
    row = {"skill_id": 1, "skill_key": "rag"}
    original = dict(row)
    svc.normalize_skill(row)
    assert row == original


# ── normalize_activity ────────────────────────────────────────────────────────

def test_normalize_activity_returns_none_for_none():
    assert svc.normalize_activity(None) is None


def test_normalize_activity_preserves_all_expected_keys():
    row = {
        "activity_id": 5, "topic_id": 20, "activity_key": "lesson",
        "activity_type": "lesson", "title": "Read & Learn",
        "instructions": "inst", "rubric_key": "", "sequence_order": 1,
        "is_required": True, "metadata": {},
    }
    result = svc.normalize_activity(row)
    for key in ("activity_id", "topic_id", "activity_key", "activity_type",
                "title", "instructions", "rubric_key", "sequence_order",
                "is_required", "metadata"):
        assert key in result, f"normalize_activity missing key: {key}"


def test_normalize_activity_defaults():
    result = svc.normalize_activity({"activity_id": 5})
    assert result["activity_key"] == ""
    assert result["activity_type"] == ""
    assert result["sequence_order"] == 0
    assert result["is_required"] is True
    assert result["metadata"] == {}


def test_normalize_activity_does_not_mutate_input():
    row = {"activity_id": 5, "activity_key": "quiz"}
    original = dict(row)
    svc.normalize_activity(row)
    assert row == original


# ── Fake data helpers ─────────────────────────────────────────────────────────

def _fake_conn():
    return MagicMock()


def _course_row():
    return {
        "course_id": 1, "course_key": "aipm-foundations",
        "title": "AI PM", "description": "desc", "target_audience": "PMs",
        "level": "beginner", "status": "active", "version": "v1",
        "sequence_order": 0, "metadata": {},
    }


def _module_row(module_id=10, course_id=1):
    return {
        "module_id": module_id, "course_id": course_id,
        "module_key": f"module-{module_id:02d}", "title": f"Module {module_id}",
        "description": "", "sequence_order": 0, "estimated_minutes": None,
        "status": "active", "metadata": {},
    }


def _topic_row(topic_id=20, module_id=10, course_id=1):
    return {
        "topic_id": topic_id, "course_id": course_id, "module_id": module_id,
        "legacy_topic_id": f"aipm-week-1-topic-{topic_id}",
        "topic_key": f"topic-{topic_id}", "title": f"Topic {topic_id}",
        "description": "", "difficulty_level": "beginner",
        "sequence_order": 0, "estimated_minutes": None,
        "status": "active", "metadata": {},
    }


def _skill_row(skill_id=1):
    return {
        "skill_id": skill_id, "skill_key": "prompt_engineering",
        "title": "Prompt Engineering", "description": "",
        "category": "prompting", "level": "", "importance": "core",
    }


def _activity_row(activity_id=100, topic_id=20, act_key="lesson"):
    return {
        "activity_id": activity_id, "topic_id": topic_id,
        "activity_key": act_key, "activity_type": "lesson",
        "title": "Read & Learn", "instructions": "",
        "rubric_key": "", "sequence_order": 1,
        "is_required": True, "metadata": {},
    }


# ── get_course_structure ──────────────────────────────────────────────────────

_REPO = "repositories.modular_curriculum_repository"


def test_get_course_structure_returns_none_when_course_not_found():
    conn = _fake_conn()
    with patch(f"{_REPO}.get_course_by_key", return_value=None):
        result = svc.get_course_structure(conn, course_key="missing")
    assert result is None


def test_get_course_structure_returns_dict_with_expected_keys():
    conn = _fake_conn()
    with (
        patch(f"{_REPO}.get_course_by_key",       return_value=_course_row()),
        patch(f"{_REPO}.list_modules_for_course",  return_value=[_module_row()]),
        patch(f"{_REPO}.list_topics_for_course",   return_value=[_topic_row()]),
        patch(f"{_REPO}.list_skills_for_topic",    return_value=[_skill_row()]),
        patch(f"{_REPO}.list_activities_for_topic",return_value=[_activity_row()]),
    ):
        result = svc.get_course_structure(conn, course_key="aipm-foundations")

    assert result is not None
    assert "course"            in result
    assert "modules"           in result
    assert "unassigned_topics" in result


def test_get_course_structure_course_is_normalized():
    conn = _fake_conn()
    with (
        patch(f"{_REPO}.get_course_by_key",       return_value=_course_row()),
        patch(f"{_REPO}.list_modules_for_course",  return_value=[]),
        patch(f"{_REPO}.list_topics_for_course",   return_value=[]),
        patch(f"{_REPO}.list_skills_for_topic",    return_value=[]),
        patch(f"{_REPO}.list_activities_for_topic",return_value=[]),
    ):
        result = svc.get_course_structure(conn, course_key="aipm-foundations")

    course = result["course"]
    assert course["course_key"] == "aipm-foundations"
    assert "course_id" in course


def test_get_course_structure_modules_are_normalized():
    conn = _fake_conn()
    with (
        patch(f"{_REPO}.get_course_by_key",       return_value=_course_row()),
        patch(f"{_REPO}.list_modules_for_course",  return_value=[_module_row()]),
        patch(f"{_REPO}.list_topics_for_course",   return_value=[]),
        patch(f"{_REPO}.list_skills_for_topic",    return_value=[]),
        patch(f"{_REPO}.list_activities_for_topic",return_value=[]),
    ):
        result = svc.get_course_structure(conn, course_key="aipm-foundations")

    assert len(result["modules"]) == 1
    mod = result["modules"][0]
    assert "module_id"  in mod
    assert "module_key" in mod
    assert "topics"     in mod


def test_get_course_structure_topics_nested_in_module():
    conn = _fake_conn()
    with (
        patch(f"{_REPO}.get_course_by_key",       return_value=_course_row()),
        patch(f"{_REPO}.list_modules_for_course",  return_value=[_module_row(module_id=10)]),
        patch(f"{_REPO}.list_topics_for_course",   return_value=[_topic_row(topic_id=20, module_id=10)]),
        patch(f"{_REPO}.list_skills_for_topic",    return_value=[_skill_row()]),
        patch(f"{_REPO}.list_activities_for_topic",return_value=[_activity_row()]),
    ):
        result = svc.get_course_structure(conn, course_key="aipm-foundations")

    mod = result["modules"][0]
    assert len(mod["topics"]) == 1
    topic = mod["topics"][0]
    assert "skills"     in topic
    assert "activities" in topic


def test_get_course_structure_skills_attached_to_topic():
    conn = _fake_conn()
    with (
        patch(f"{_REPO}.get_course_by_key",       return_value=_course_row()),
        patch(f"{_REPO}.list_modules_for_course",  return_value=[_module_row()]),
        patch(f"{_REPO}.list_topics_for_course",   return_value=[_topic_row()]),
        patch(f"{_REPO}.list_skills_for_topic",    return_value=[_skill_row()]),
        patch(f"{_REPO}.list_activities_for_topic",return_value=[]),
    ):
        result = svc.get_course_structure(conn, course_key="aipm-foundations")

    topic = result["modules"][0]["topics"][0]
    assert len(topic["skills"]) == 1
    assert topic["skills"][0]["skill_key"] == "prompt_engineering"


def test_get_course_structure_activities_attached_to_topic():
    conn = _fake_conn()
    with (
        patch(f"{_REPO}.get_course_by_key",       return_value=_course_row()),
        patch(f"{_REPO}.list_modules_for_course",  return_value=[_module_row()]),
        patch(f"{_REPO}.list_topics_for_course",   return_value=[_topic_row()]),
        patch(f"{_REPO}.list_skills_for_topic",    return_value=[]),
        patch(f"{_REPO}.list_activities_for_topic",return_value=[_activity_row()]),
    ):
        result = svc.get_course_structure(conn, course_key="aipm-foundations")

    topic = result["modules"][0]["topics"][0]
    assert len(topic["activities"]) == 1
    assert topic["activities"][0]["activity_key"] == "lesson"


def test_get_course_structure_unassigned_topics_when_module_id_none():
    conn = _fake_conn()
    topic_no_module = _topic_row(topic_id=99, module_id=None)
    topic_no_module["module_id"] = None

    with (
        patch(f"{_REPO}.get_course_by_key",       return_value=_course_row()),
        patch(f"{_REPO}.list_modules_for_course",  return_value=[_module_row(module_id=10)]),
        patch(f"{_REPO}.list_topics_for_course",   return_value=[topic_no_module]),
        patch(f"{_REPO}.list_skills_for_topic",    return_value=[]),
        patch(f"{_REPO}.list_activities_for_topic",return_value=[]),
    ):
        result = svc.get_course_structure(conn, course_key="aipm-foundations")

    assert len(result["unassigned_topics"]) == 1
    assert result["modules"][0]["topics"] == []


def test_get_course_structure_unassigned_topics_when_module_id_unknown():
    conn = _fake_conn()
    # module_id=999 is not in modules returned by list_modules_for_course
    orphan_topic = _topic_row(topic_id=55, module_id=999)

    with (
        patch(f"{_REPO}.get_course_by_key",       return_value=_course_row()),
        patch(f"{_REPO}.list_modules_for_course",  return_value=[_module_row(module_id=10)]),
        patch(f"{_REPO}.list_topics_for_course",   return_value=[orphan_topic]),
        patch(f"{_REPO}.list_skills_for_topic",    return_value=[]),
        patch(f"{_REPO}.list_activities_for_topic",return_value=[]),
    ):
        result = svc.get_course_structure(conn, course_key="aipm-foundations")

    assert len(result["unassigned_topics"]) == 1
    assert result["modules"][0]["topics"] == []


def test_get_course_structure_preserves_repository_topic_order():
    conn = _fake_conn()
    topic_a = _topic_row(topic_id=1, module_id=10)
    topic_b = _topic_row(topic_id=2, module_id=10)
    topic_c = _topic_row(topic_id=3, module_id=10)

    with (
        patch(f"{_REPO}.get_course_by_key",       return_value=_course_row()),
        patch(f"{_REPO}.list_modules_for_course",  return_value=[_module_row(module_id=10)]),
        patch(f"{_REPO}.list_topics_for_course",   return_value=[topic_a, topic_b, topic_c]),
        patch(f"{_REPO}.list_skills_for_topic",    return_value=[]),
        patch(f"{_REPO}.list_activities_for_topic",return_value=[]),
    ):
        result = svc.get_course_structure(conn, course_key="aipm-foundations")

    ids = [t["topic_id"] for t in result["modules"][0]["topics"]]
    assert ids == [1, 2, 3]


def test_get_course_structure_multiple_modules():
    conn = _fake_conn()
    with (
        patch(f"{_REPO}.get_course_by_key",       return_value=_course_row()),
        patch(f"{_REPO}.list_modules_for_course",  return_value=[
            _module_row(module_id=10), _module_row(module_id=11)
        ]),
        patch(f"{_REPO}.list_topics_for_course",   return_value=[
            _topic_row(topic_id=1, module_id=10),
            _topic_row(topic_id=2, module_id=11),
        ]),
        patch(f"{_REPO}.list_skills_for_topic",    return_value=[]),
        patch(f"{_REPO}.list_activities_for_topic",return_value=[]),
    ):
        result = svc.get_course_structure(conn, course_key="aipm-foundations")

    assert len(result["modules"]) == 2
    assert len(result["modules"][0]["topics"]) == 1
    assert len(result["modules"][1]["topics"]) == 1


def test_get_course_structure_empty_course():
    conn = _fake_conn()
    with (
        patch(f"{_REPO}.get_course_by_key",       return_value=_course_row()),
        patch(f"{_REPO}.list_modules_for_course",  return_value=[]),
        patch(f"{_REPO}.list_topics_for_course",   return_value=[]),
        patch(f"{_REPO}.list_skills_for_topic",    return_value=[]),
        patch(f"{_REPO}.list_activities_for_topic",return_value=[]),
    ):
        result = svc.get_course_structure(conn, course_key="aipm-foundations")

    assert result["modules"] == []
    assert result["unassigned_topics"] == []


def test_get_course_structure_does_not_call_skills_when_topic_id_none():
    """Topics with no topic_id should not trigger list_skills_for_topic."""
    conn = _fake_conn()
    topic_no_id = _topic_row(topic_id=None)
    topic_no_id["topic_id"] = None
    topic_no_id["module_id"] = None

    with (
        patch(f"{_REPO}.get_course_by_key",       return_value=_course_row()),
        patch(f"{_REPO}.list_modules_for_course",  return_value=[]),
        patch(f"{_REPO}.list_topics_for_course",   return_value=[topic_no_id]),
        patch(f"{_REPO}.list_skills_for_topic",    return_value=[]) as mock_skills,
        patch(f"{_REPO}.list_activities_for_topic",return_value=[]) as mock_acts,
    ):
        result = svc.get_course_structure(conn, course_key="aipm-foundations")

    mock_skills.assert_not_called()
    mock_acts.assert_not_called()
    assert len(result["unassigned_topics"]) == 1
    assert result["unassigned_topics"][0]["skills"]     == []
    assert result["unassigned_topics"][0]["activities"] == []


# ── list_available_courses ────────────────────────────────────────────────────

def test_list_available_courses_returns_list():
    conn = _fake_conn()
    with patch(f"{_REPO}.list_courses", return_value=[_course_row()]):
        result = svc.list_available_courses(conn)
    assert isinstance(result, list)
    assert len(result) == 1


def test_list_available_courses_returns_normalized_dicts():
    conn = _fake_conn()
    with patch(f"{_REPO}.list_courses", return_value=[_course_row()]):
        result = svc.list_available_courses(conn)
    course = result[0]
    assert "course_id"   in course
    assert "course_key"  in course
    assert "title"       in course


def test_list_available_courses_passes_status_filter():
    conn = _fake_conn()
    with patch(f"{_REPO}.list_courses", return_value=[]) as mock_lc:
        svc.list_available_courses(conn, status="draft")
    mock_lc.assert_called_once_with(conn, status="draft")


def test_list_available_courses_default_status_is_active():
    conn = _fake_conn()
    with patch(f"{_REPO}.list_courses", return_value=[]) as mock_lc:
        svc.list_available_courses(conn)
    mock_lc.assert_called_once_with(conn, status="active")


def test_list_available_courses_passes_none_status():
    conn = _fake_conn()
    with patch(f"{_REPO}.list_courses", return_value=[]) as mock_lc:
        svc.list_available_courses(conn, status=None)
    mock_lc.assert_called_once_with(conn, status=None)


def test_list_available_courses_returns_empty_for_no_rows():
    conn = _fake_conn()
    with patch(f"{_REPO}.list_courses", return_value=[]):
        result = svc.list_available_courses(conn)
    assert result == []


def test_list_available_courses_filters_out_none_rows():
    """normalize_course returns None for None rows; those should be excluded."""
    conn = _fake_conn()
    with patch(f"{_REPO}.list_courses", return_value=[None, _course_row()]):
        result = svc.list_available_courses(conn)
    assert len(result) == 1


def test_list_available_courses_multiple_courses():
    conn = _fake_conn()
    row2 = dict(_course_row())
    row2["course_id"] = 2
    row2["course_key"] = "evals-foundations"
    with patch(f"{_REPO}.list_courses", return_value=[_course_row(), row2]):
        result = svc.list_available_courses(conn)
    assert len(result) == 2
    keys = [c["course_key"] for c in result]
    assert "aipm-foundations"  in keys
    assert "evals-foundations" in keys


# ── get_topic_structure_by_legacy_id ─────────────────────────────────────────

def test_get_topic_structure_by_legacy_id_returns_none_when_not_found():
    conn = _fake_conn()
    with patch(f"{_REPO}.get_topic_by_legacy_id", return_value=None):
        result = svc.get_topic_structure_by_legacy_id(
            conn, legacy_topic_id="aipm-week-1-transformers"
        )
    assert result is None


def test_get_topic_structure_by_legacy_id_returns_normalized_topic():
    conn = _fake_conn()
    with (
        patch(f"{_REPO}.get_topic_by_legacy_id",   return_value=_topic_row()),
        patch(f"{_REPO}.list_skills_for_topic",    return_value=[_skill_row()]),
        patch(f"{_REPO}.list_activities_for_topic",return_value=[_activity_row()]),
    ):
        result = svc.get_topic_structure_by_legacy_id(
            conn, legacy_topic_id="aipm-week-1-topic-20"
        )

    assert result is not None
    assert "topic_id"    in result
    assert "topic_key"   in result
    assert "skills"      in result
    assert "activities"  in result


def test_get_topic_structure_by_legacy_id_attaches_skills():
    conn = _fake_conn()
    with (
        patch(f"{_REPO}.get_topic_by_legacy_id",   return_value=_topic_row()),
        patch(f"{_REPO}.list_skills_for_topic",    return_value=[_skill_row()]),
        patch(f"{_REPO}.list_activities_for_topic",return_value=[]),
    ):
        result = svc.get_topic_structure_by_legacy_id(
            conn, legacy_topic_id="aipm-week-1-topic-20"
        )

    assert len(result["skills"]) == 1
    assert result["skills"][0]["skill_key"] == "prompt_engineering"


def test_get_topic_structure_by_legacy_id_attaches_activities():
    conn = _fake_conn()
    with (
        patch(f"{_REPO}.get_topic_by_legacy_id",   return_value=_topic_row()),
        patch(f"{_REPO}.list_skills_for_topic",    return_value=[]),
        patch(f"{_REPO}.list_activities_for_topic",return_value=[_activity_row()]),
    ):
        result = svc.get_topic_structure_by_legacy_id(
            conn, legacy_topic_id="aipm-week-1-topic-20"
        )

    assert len(result["activities"]) == 1
    assert result["activities"][0]["activity_key"] == "lesson"


def test_get_topic_structure_by_legacy_id_passes_correct_legacy_id():
    conn = _fake_conn()
    with patch(f"{_REPO}.get_topic_by_legacy_id", return_value=None) as mock_fn:
        svc.get_topic_structure_by_legacy_id(
            conn, legacy_topic_id="aipm-week-3-rag"
        )
    mock_fn.assert_called_once_with(conn, legacy_topic_id="aipm-week-3-rag")


def test_get_topic_structure_by_legacy_id_uses_topic_id_for_children():
    conn = _fake_conn()
    with (
        patch(f"{_REPO}.get_topic_by_legacy_id",   return_value=_topic_row(topic_id=42)),
        patch(f"{_REPO}.list_skills_for_topic",    return_value=[]) as mock_skills,
        patch(f"{_REPO}.list_activities_for_topic",return_value=[]) as mock_acts,
    ):
        svc.get_topic_structure_by_legacy_id(
            conn, legacy_topic_id="aipm-week-1-topic-42"
        )

    mock_skills.assert_called_once_with(conn, topic_id=42)
    mock_acts.assert_called_once_with(conn, topic_id=42)


def test_get_topic_structure_by_legacy_id_no_topic_id_returns_empty_children():
    """If topic row has no topic_id, skills/activities must be [] without DB calls."""
    conn = _fake_conn()
    row_no_id = _topic_row(topic_id=None)
    row_no_id["topic_id"] = None

    with (
        patch(f"{_REPO}.get_topic_by_legacy_id",   return_value=row_no_id),
        patch(f"{_REPO}.list_skills_for_topic",    return_value=[]) as mock_s,
        patch(f"{_REPO}.list_activities_for_topic",return_value=[]) as mock_a,
    ):
        result = svc.get_topic_structure_by_legacy_id(
            conn, legacy_topic_id="aipm-week-1-no-id"
        )

    assert result is not None
    assert result["skills"]     == []
    assert result["activities"] == []
    mock_s.assert_not_called()
    mock_a.assert_not_called()


def test_get_topic_structure_by_legacy_id_multiple_skills():
    conn = _fake_conn()
    skill2 = dict(_skill_row())
    skill2["skill_id"]  = 2
    skill2["skill_key"] = "rag"
    skill2["title"]     = "RAG & Retrieval"

    with (
        patch(f"{_REPO}.get_topic_by_legacy_id",   return_value=_topic_row()),
        patch(f"{_REPO}.list_skills_for_topic",    return_value=[_skill_row(), skill2]),
        patch(f"{_REPO}.list_activities_for_topic",return_value=[]),
    ):
        result = svc.get_topic_structure_by_legacy_id(
            conn, legacy_topic_id="aipm-week-1-topic-20"
        )

    assert len(result["skills"]) == 2
    skill_keys = [s["skill_key"] for s in result["skills"]]
    assert "prompt_engineering" in skill_keys
    assert "rag" in skill_keys
