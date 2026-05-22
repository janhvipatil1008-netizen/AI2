"""Tests for curriculum/modular_seed_export.py.

No DB connection required.  All assertions operate on the in-memory export
built from the existing static WEEKS / ROLE_TRACKS data.
"""

from __future__ import annotations

import inspect
import json
import pathlib
import tempfile

import curriculum.modular_seed_export as mod


# ── Import / API surface ──────────────────────────────────────────────────────

def test_module_imports_safely():
    assert mod is not None


def test_expected_dataclasses_exist():
    for name in (
        "ModularCourseSeed",
        "ModularModuleSeed",
        "ModularSkillSeed",
        "ModularActivitySeed",
        "ModularTopicSeed",
        "ModularCurriculumSeedExport",
    ):
        assert hasattr(mod, name), f"Missing dataclass: {name}"


def test_expected_functions_exist():
    for fn in (
        "slugify_key",
        "infer_skills_for_topic",
        "default_activities_for_topic",
        "build_modular_curriculum_seed_export",
        "modular_seed_export_to_dict",
        "export_modular_curriculum_seed_json",
    ):
        assert hasattr(mod, fn), f"Missing function: {fn}"


# ── Isolation guards ──────────────────────────────────────────────────────────

def _src() -> str:
    return inspect.getsource(mod)


def test_no_db_calls():
    src = _src()
    assert "database.pool" not in src or "import database.pool" not in src
    import re
    assert not re.search(r"^\s*(import|from)\s+database\.pool", src, re.MULTILINE)
    assert "psycopg2.connect" not in src
    assert ".commit()" not in src
    assert ".rollback()" not in src


def test_no_env_reads():
    src = _src()
    assert "os.environ" not in src
    assert "os.getenv" not in src


def test_no_app_routes_services_imports():
    src = _src()
    for bad in ("from app", "from routes", "from services", "import app"):
        assert bad not in src, f"Forbidden import pattern found: {bad}"


def test_no_mutation_of_weeks_or_role_tracks():
    # Confirm WEEKS and ROLE_TRACKS are unchanged after running the export
    from curriculum.syllabus import ROLE_TRACKS, WEEKS
    original_tracks = list(ROLE_TRACKS.keys())
    original_weeks  = len(WEEKS)

    mod.build_modular_curriculum_seed_export()

    assert list(ROLE_TRACKS.keys()) == original_tracks
    assert len(WEEKS) == original_weeks


# ── slugify_key ───────────────────────────────────────────────────────────────

def test_slugify_key_lowercases():
    assert mod.slugify_key("Hello World") == "hello-world"


def test_slugify_key_replaces_spaces_with_hyphen():
    assert mod.slugify_key("ai ml dl") == "ai-ml-dl"


def test_slugify_key_collapses_repeated_non_alphanum():
    assert mod.slugify_key("AI / ML & DL") == "ai-ml-dl"


def test_slugify_key_strips_leading_trailing_hyphens():
    result = mod.slugify_key(" AI ")
    assert not result.startswith("-")
    assert not result.endswith("-")


def test_slugify_key_returns_untitled_for_empty():
    assert mod.slugify_key("") == "untitled"


def test_slugify_key_returns_untitled_for_whitespace_only():
    assert mod.slugify_key("   ") == "untitled"


def test_slugify_key_preserves_numbers():
    assert "3" in mod.slugify_key("GPT-3 models")


# ── infer_skills_for_topic ────────────────────────────────────────────────────

def test_infer_skills_returns_list():
    result = mod.infer_skills_for_topic("AI Foundations")
    assert isinstance(result, list)
    assert len(result) >= 1


def test_infer_skills_default_when_no_keywords():
    result = mod.infer_skills_for_topic("Something completely general")
    keys = [s.skill_key for s in result]
    assert "ai_foundations" in keys


def test_infer_skills_prompt_engineering():
    result = mod.infer_skills_for_topic("Prompt design and chaining")
    keys = [s.skill_key for s in result]
    assert "prompt_engineering" in keys


def test_infer_skills_rag():
    result = mod.infer_skills_for_topic("RAG and retrieval systems")
    keys = [s.skill_key for s in result]
    assert "rag" in keys


def test_infer_skills_ai_evaluation():
    result = mod.infer_skills_for_topic("Evaluation rubric for LLMs")
    keys = [s.skill_key for s in result]
    assert "ai_evaluation" in keys


def test_infer_skills_portfolio():
    result = mod.infer_skills_for_topic("Build a portfolio project")
    keys = [s.skill_key for s in result]
    assert "portfolio_building" in keys


def test_infer_skills_interview():
    result = mod.infer_skills_for_topic("Interview practice questions")
    keys = [s.skill_key for s in result]
    assert "interview_readiness" in keys


def test_infer_skills_product_management():
    result = mod.infer_skills_for_topic("Writing a product roadmap")
    keys = [s.skill_key for s in result]
    assert "product_management" in keys


def test_infer_skills_agents():
    result = mod.infer_skills_for_topic("Agent orchestration patterns")
    keys = [s.skill_key for s in result]
    assert "agents" in keys


def test_infer_skills_context_engineering():
    result = mod.infer_skills_for_topic("Context window management")
    keys = [s.skill_key for s in result]
    assert "context_engineering" in keys


def test_infer_skills_description_used_as_fallback():
    # title has no keyword; description has one
    result = mod.infer_skills_for_topic("Some topic", description="prompt design matters")
    keys = [s.skill_key for s in result]
    assert "prompt_engineering" in keys


def test_infer_skills_multiple_matches():
    result = mod.infer_skills_for_topic("Prompt-based evaluation rubric")
    keys = [s.skill_key for s in result]
    assert "prompt_engineering" in keys
    assert "ai_evaluation" in keys


def test_infer_skills_returns_skill_seeds():
    result = mod.infer_skills_for_topic("Some topic")
    for skill in result:
        assert isinstance(skill, mod.ModularSkillSeed)
        assert skill.skill_key
        assert skill.title


# ── default_activities_for_topic ──────────────────────────────────────────────

def test_default_activities_returns_list():
    result = mod.default_activities_for_topic("some-topic")
    assert isinstance(result, list)


def test_default_activities_has_six_items():
    result = mod.default_activities_for_topic("some-topic")
    assert len(result) == 6


def test_default_activities_has_lesson():
    types = [a.activity_type for a in mod.default_activities_for_topic("t")]
    assert "lesson" in types


def test_default_activities_has_practice_task():
    types = [a.activity_type for a in mod.default_activities_for_topic("t")]
    assert "practice_task" in types


def test_default_activities_has_quiz():
    types = [a.activity_type for a in mod.default_activities_for_topic("t")]
    assert "quiz" in types


def test_default_activities_has_portfolio_task():
    types = [a.activity_type for a in mod.default_activities_for_topic("t")]
    assert "portfolio_task" in types


def test_default_activities_has_interview_practice():
    types = [a.activity_type for a in mod.default_activities_for_topic("t")]
    assert "interview_practice" in types


def test_default_activities_has_reflection():
    types = [a.activity_type for a in mod.default_activities_for_topic("t")]
    assert "reflection" in types


def test_default_activities_keys_are_expected():
    keys = [a.activity_key for a in mod.default_activities_for_topic("t")]
    assert "lesson"     in keys
    assert "practice"   in keys
    assert "quiz"       in keys
    assert "portfolio"  in keys
    assert "interview"  in keys
    assert "reflection" in keys


def test_default_activities_ordered_by_sequence_order():
    acts = mod.default_activities_for_topic("t")
    orders = [a.sequence_order for a in acts]
    assert orders == sorted(orders)


def test_default_activities_are_activity_seeds():
    for act in mod.default_activities_for_topic("t"):
        assert isinstance(act, mod.ModularActivitySeed)


# ── build_modular_curriculum_seed_export ──────────────────────────────────────

def _export():
    return mod.build_modular_curriculum_seed_export()


def test_export_returns_modular_curriculum_seed_export():
    assert isinstance(_export(), mod.ModularCurriculumSeedExport)


def test_export_has_at_least_one_course():
    assert len(_export().courses) >= 1


def test_export_includes_aipm_foundations_course():
    keys = [c.course_key for c in _export().courses]
    assert "aipm-foundations" in keys


def test_export_course_has_required_fields():
    course = next(c for c in _export().courses if c.course_key == "aipm-foundations")
    assert course.title
    assert course.status
    assert course.version
    assert isinstance(course.sequence_order, int)


def test_export_modules_exist():
    assert len(_export().modules) >= 1


def test_modules_use_sequence_order_not_week_number():
    for module in _export().modules:
        assert hasattr(module, "sequence_order")
        assert isinstance(module.sequence_order, int)
        # week_number must not be a field on ModularModuleSeed
        assert not hasattr(module, "week_number")


def test_module_keys_do_not_contain_week_prefix():
    # module_key should use "module-XX" format, not "week-X"
    for module in _export().modules:
        assert not module.module_key.startswith("week-"), (
            f"module_key '{module.module_key}' still uses 'week-' prefix"
        )


def test_module_keys_use_module_prefix():
    keys = [m.module_key for m in _export().modules]
    assert any(k.startswith("module-") for k in keys)


def test_export_topics_exist():
    assert len(_export().topics) >= 1


def test_topics_preserve_legacy_topic_id():
    for topic in _export().topics:
        assert topic.legacy_topic_id, (
            f"topic '{topic.topic_key}' has empty legacy_topic_id"
        )


def test_topics_have_topic_key():
    for topic in _export().topics:
        assert topic.topic_key, f"topic missing topic_key (legacy={topic.legacy_topic_id})"


def test_topic_keys_mostly_avoid_week_language():
    topics = _export().topics
    week_keys = [t for t in topics if "-week-" in t.topic_key]
    # At most 2% of topic_keys should contain "-week-"
    assert len(week_keys) / len(topics) < 0.02, (
        f"{len(week_keys)}/{len(topics)} topic_keys still contain '-week-': "
        f"{[t.topic_key for t in week_keys[:5]]}"
    )


def test_topics_have_skills():
    for topic in _export().topics:
        assert len(topic.skills) >= 1, (
            f"topic '{topic.topic_key}' has no inferred skills"
        )


def test_topics_have_activities():
    for topic in _export().topics:
        assert len(topic.activities) == 6, (
            f"topic '{topic.topic_key}' has {len(topic.activities)} activities, expected 6"
        )


def test_topics_belong_to_a_course():
    course_keys = {c.course_key for c in _export().courses}
    for topic in _export().topics:
        assert topic.course_key in course_keys


def test_topics_belong_to_a_module():
    module_keys = {m.module_key for m in _export().modules}
    for topic in _export().topics:
        assert topic.module_key in module_keys


def test_legacy_topic_ids_match_curriculum_topics():
    from curriculum.topics import get_topics_for_track
    from curriculum.syllabus import ROLE_TRACKS
    all_ids = {t.topic_id for track in ROLE_TRACKS for t in get_topics_for_track(track)}
    for topic in _export().topics:
        assert topic.legacy_topic_id in all_ids, (
            f"legacy_topic_id '{topic.legacy_topic_id}' not in curriculum"
        )


# ── modular_seed_export_to_dict ───────────────────────────────────────────────

def _dict_export() -> dict:
    return mod.modular_seed_export_to_dict(_export())


def test_dict_export_has_expected_top_level_keys():
    d = _dict_export()
    for key in ("courses", "modules", "topics", "skills", "topic_skills", "activities"):
        assert key in d, f"Missing key: {key}"


def test_dict_export_is_json_serializable():
    d = _dict_export()
    serialized = json.dumps(d)
    assert len(serialized) > 0


def test_dict_export_courses_are_dicts():
    for c in _dict_export()["courses"]:
        assert isinstance(c, dict)


def test_dict_export_modules_are_dicts():
    for m in _dict_export()["modules"]:
        assert isinstance(m, dict)


def test_dict_export_topics_are_dicts():
    for t in _dict_export()["topics"]:
        assert isinstance(t, dict)


def test_dict_export_skills_are_deduped():
    skills = _dict_export()["skills"]
    keys = [s["skill_key"] for s in skills]
    assert len(keys) == len(set(keys)), "Duplicate skill_keys found in export"


def test_dict_export_topic_skills_link_topics_and_skills():
    d = _dict_export()
    skill_keys  = {s["skill_key"]  for s in d["skills"]}
    topic_keys  = {t["topic_key"]  for t in d["topics"]}
    for ts in d["topic_skills"]:
        assert ts["skill_key"]  in skill_keys,  f"Unknown skill_key: {ts['skill_key']}"
        assert ts["topic_key"]  in topic_keys,  f"Unknown topic_key: {ts['topic_key']}"


def test_dict_export_activities_include_all_types():
    activities = _dict_export()["activities"]
    types = {a["activity_type"] for a in activities}
    for expected in ("lesson", "practice_task", "quiz",
                     "portfolio_task", "interview_practice", "reflection"):
        assert expected in types, f"Missing activity_type: {expected}"


def test_dict_export_topics_do_not_contain_inline_skills():
    for t in _dict_export()["topics"]:
        assert "skills" not in t


def test_dict_export_topics_do_not_contain_inline_activities():
    for t in _dict_export()["topics"]:
        assert "activities" not in t


def test_dict_export_activities_have_topic_key():
    for a in _dict_export()["activities"]:
        assert "topic_key" in a


# ── export_modular_curriculum_seed_json ───────────────────────────────────────

def test_json_export_writes_file():
    with tempfile.TemporaryDirectory() as tmp:
        out = pathlib.Path(tmp) / "modular_seed.json"
        result = mod.export_modular_curriculum_seed_json(out)
        assert result == out
        assert out.exists()
        assert out.stat().st_size > 0


def test_json_export_writes_valid_json():
    with tempfile.TemporaryDirectory() as tmp:
        out = pathlib.Path(tmp) / "modular_seed.json"
        mod.export_modular_curriculum_seed_json(out)
        data = json.loads(out.read_text(encoding="utf-8"))
        assert "courses" in data
        assert "topics" in data


def test_json_export_is_pretty_printed():
    with tempfile.TemporaryDirectory() as tmp:
        out = pathlib.Path(tmp) / "modular_seed.json"
        mod.export_modular_curriculum_seed_json(out)
        raw = out.read_text(encoding="utf-8")
        assert "\n" in raw  # pretty-printed has newlines
