"""Tests for scripts/seed_modular_curriculum.py.

No real DB connection required.  All tests use fakes / monkeypatching.
"""

from __future__ import annotations

import inspect
import sys
from unittest.mock import MagicMock, call, patch

import scripts.seed_modular_curriculum as script


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_skill(key: str, title: str = ""):
    from curriculum.modular_seed_export import ModularSkillSeed
    return ModularSkillSeed(skill_key=key, title=title or key.replace("_", " ").title())


def _make_activity(key: str, act_type: str, seq: int = 1):
    from curriculum.modular_seed_export import ModularActivitySeed
    return ModularActivitySeed(
        activity_key=key, activity_type=act_type, sequence_order=seq, is_required=True
    )


def _make_minimal_export():
    """Two topics sharing one skill, one topic with two skills.

    Designed to surface deduplication and ID-threading behaviour.
    """
    from curriculum.modular_seed_export import (
        ModularActivitySeed,
        ModularCourseSeed,
        ModularCurriculumSeedExport,
        ModularModuleSeed,
        ModularSkillSeed,
        ModularTopicSeed,
    )

    skill_found  = _make_skill("ai_foundations")
    skill_prompt = _make_skill("prompt_engineering")

    acts = [
        _make_activity("lesson",    "lesson",             1),
        _make_activity("quiz",      "quiz",               2),
        _make_activity("portfolio", "portfolio_task",     3),
    ]

    topic1 = ModularTopicSeed(
        course_key="aipm-foundations",
        module_key="module-01",
        topic_key="transformers",
        title="Transformers",
        description="LLM basics",
        legacy_topic_id="aipm-week-1-transformers",
        skills=[skill_found],
        activities=acts[:],
    )
    # topic2 shares ai_foundations with topic1 → dedup test
    topic2 = ModularTopicSeed(
        course_key="aipm-foundations",
        module_key="module-01",
        topic_key="prompt-design",
        title="Prompt Design",
        description="Effective prompts",
        legacy_topic_id="aipm-week-1-prompt-design",
        skills=[skill_found, skill_prompt],
        activities=acts[:],
    )

    return ModularCurriculumSeedExport(
        courses=[ModularCourseSeed(course_key="aipm-foundations", title="AI PM Foundations")],
        modules=[ModularModuleSeed(
            course_key="aipm-foundations", module_key="module-01", title="Module 1"
        )],
        topics=[topic1, topic2],
    )


# Patch targets
_BUILD   = "curriculum.modular_seed_export.build_modular_curriculum_seed_export"
_REPO    = "repositories.modular_curriculum_repository"
_COURSE  = f"{_REPO}.upsert_course"
_MODULE  = f"{_REPO}.upsert_course_module"
_SKILL   = f"{_REPO}.upsert_skill"
_TOPIC   = f"{_REPO}.upsert_course_topic"
_LINK    = f"{_REPO}.link_topic_skill"
_ACTIV   = f"{_REPO}.upsert_topic_activity"


def _all_repo_patches(
    *,
    course_id: int = 1,
    module_id: int = 10,
    skill_id:  int = 100,
    topic_id:  int = 1000,
    act_id:    int = 9999,
):
    """Return context-manager patches for all six repo functions."""
    return [
        patch(_COURSE, return_value=course_id),
        patch(_MODULE, return_value=module_id),
        patch(_SKILL,  return_value=skill_id),
        patch(_TOPIC,  return_value=topic_id),
        patch(_LINK,   return_value=None),
        patch(_ACTIV,  return_value=act_id),
    ]


# ── Import / API surface ──────────────────────────────────────────────────────

def test_module_imports_safely_without_db():
    assert script is not None


def test_has_run_seed():
    assert callable(script.run_seed)


def test_has_main():
    assert callable(script.main)


def test_main_guard_present():
    src = inspect.getsource(script)
    assert 'if __name__ == "__main__"' in src


# ── Isolation guards (source inspection) ─────────────────────────────────────

def _src() -> str:
    return inspect.getsource(script)


def test_no_routes_or_app_imports():
    src = _src()
    for bad in ("from app", "from routes", "import app ", "from services"):
        assert bad not in src, f"Forbidden import: {bad!r}"


def test_no_env_reads_at_module_level():
    # os.environ / os.getenv must not appear outside a function body
    # (they appear only inside _get_connection which is called lazily)
    src = _src()
    # The only acceptable occurrence is inside _get_connection or referenced
    # via database.pool — direct os.environ usage is forbidden
    assert "os.environ" not in src
    assert "os.getenv"  not in src


def test_no_commit_inside_run_seed():
    # Grab just the run_seed function source
    src = inspect.getsource(script.run_seed)
    assert ".commit()" not in src


def test_no_rollback_inside_run_seed():
    src = inspect.getsource(script.run_seed)
    assert ".rollback()" not in src


def test_no_conn_close_inside_run_seed():
    src = inspect.getsource(script.run_seed)
    assert ".close()" not in src


def test_no_secrets_printed():
    src = _src()
    for word in ("DATABASE_URL", "password", "secret", "SUPABASE_KEY"):
        # These must not appear in print() calls
        import re
        matches = re.findall(rf'print\([^)]*{word}', src)
        assert not matches, f"Secret '{word}' found in a print() call"


# ── run_seed: basic call flow ─────────────────────────────────────────────────

def test_run_seed_calls_build_export():
    export = _make_minimal_export()
    conn   = MagicMock()
    patches = _all_repo_patches()
    with patch(_BUILD, return_value=export) as mock_build, \
         patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
        script.run_seed(conn)
    mock_build.assert_called_once()


def test_run_seed_calls_upsert_course():
    export = _make_minimal_export()
    conn   = MagicMock()
    patches = _all_repo_patches()
    with patch(_BUILD, return_value=export), \
         patch(_COURSE) as mock_course, \
         patches[1], patches[2], patches[3], patches[4], patches[5]:
        mock_course.return_value = 42
        script.run_seed(conn)
    assert mock_course.called
    _, kwargs = mock_course.call_args
    assert kwargs["course_key"] == "aipm-foundations"


def test_run_seed_calls_upsert_module():
    export = _make_minimal_export()
    conn   = MagicMock()
    patches = _all_repo_patches()
    with patch(_BUILD, return_value=export), \
         patches[0], \
         patch(_MODULE) as mock_mod, \
         patches[2], patches[3], patches[4], patches[5]:
        mock_mod.return_value = 10
        script.run_seed(conn)
    assert mock_mod.called
    _, kwargs = mock_mod.call_args
    assert kwargs["module_key"] == "module-01"


def test_run_seed_calls_upsert_topic():
    export = _make_minimal_export()
    conn   = MagicMock()
    with patch(_BUILD, return_value=export), \
         patch(_COURSE, return_value=1), \
         patch(_MODULE, return_value=10), \
         patch(_SKILL,  return_value=100), \
         patch(_TOPIC)  as mock_topic, \
         patch(_LINK,   return_value=None), \
         patch(_ACTIV,  return_value=1):
        mock_topic.return_value = 999
        script.run_seed(conn)
    assert mock_topic.call_count == 2  # two topics in export


def test_run_seed_preserves_legacy_topic_id():
    export = _make_minimal_export()
    conn   = MagicMock()
    topic_calls: list[dict] = []

    def capture_topic(*args, **kwargs):
        topic_calls.append(kwargs)
        return 50

    with patch(_BUILD, return_value=export), \
         patch(_COURSE, return_value=1), \
         patch(_MODULE, return_value=10), \
         patch(_SKILL,  return_value=100), \
         patch(_TOPIC,  side_effect=capture_topic), \
         patch(_LINK,   return_value=None), \
         patch(_ACTIV,  return_value=1):
        script.run_seed(conn)

    legacy_ids = [c["legacy_topic_id"] for c in topic_calls]
    assert "aipm-week-1-transformers" in legacy_ids
    assert "aipm-week-1-prompt-design" in legacy_ids


def test_run_seed_activities_receive_topic_id():
    export = _make_minimal_export()
    conn   = MagicMock()
    received_topic_ids: list[int] = []

    def fake_activity(*args, **kwargs):
        received_topic_ids.append(kwargs["topic_id"])
        return 1

    with patch(_BUILD, return_value=export), \
         patch(_COURSE, return_value=1), \
         patch(_MODULE, return_value=10), \
         patch(_SKILL,  return_value=100), \
         patch(_TOPIC,  return_value=777), \
         patch(_LINK,   return_value=None), \
         patch(_ACTIV,  side_effect=fake_activity):
        script.run_seed(conn)

    # Every activity call must reference the topic_id returned by upsert_course_topic
    assert all(tid == 777 for tid in received_topic_ids), (
        f"Some activities used wrong topic_id: {received_topic_ids}"
    )


def test_run_seed_links_skills_with_topic_id():
    export = _make_minimal_export()
    conn   = MagicMock()
    linked_topic_ids: list[int] = []

    def fake_link(*args, **kwargs):
        linked_topic_ids.append(kwargs["topic_id"])

    with patch(_BUILD, return_value=export), \
         patch(_COURSE, return_value=1), \
         patch(_MODULE, return_value=10), \
         patch(_SKILL,  return_value=100), \
         patch(_TOPIC,  return_value=888), \
         patch(_LINK,   side_effect=fake_link), \
         patch(_ACTIV,  return_value=1):
        script.run_seed(conn)

    assert all(tid == 888 for tid in linked_topic_ids)


# ── run_seed: skill deduplication ─────────────────────────────────────────────

def test_run_seed_deduplicates_skills():
    """ai_foundations appears in both topics — upsert_skill must be called once for it."""
    export = _make_minimal_export()
    conn   = MagicMock()
    skill_keys_seen: list[str] = []

    def fake_upsert_skill(*args, **kwargs):
        skill_keys_seen.append(kwargs["skill_key"])
        return 100

    with patch(_BUILD, return_value=export), \
         patch(_COURSE, return_value=1), \
         patch(_MODULE, return_value=10), \
         patch(_SKILL,  side_effect=fake_upsert_skill), \
         patch(_TOPIC,  return_value=1), \
         patch(_LINK,   return_value=None), \
         patch(_ACTIV,  return_value=1):
        script.run_seed(conn)

    assert skill_keys_seen.count("ai_foundations") == 1, (
        f"ai_foundations upserted {skill_keys_seen.count('ai_foundations')} times, expected 1"
    )
    # prompt_engineering should appear exactly once too
    assert skill_keys_seen.count("prompt_engineering") == 1


def test_run_seed_total_skills_count_reflects_unique_skills():
    export = _make_minimal_export()  # 2 unique skills: ai_foundations, prompt_engineering
    conn   = MagicMock()
    with patch(_BUILD, return_value=export), \
         patch(_COURSE, return_value=1), \
         patch(_MODULE, return_value=10), \
         patch(_SKILL,  return_value=100), \
         patch(_TOPIC,  return_value=1), \
         patch(_LINK,   return_value=None), \
         patch(_ACTIV,  return_value=1):
        counts = script.run_seed(conn)

    assert counts["skills"] == 2  # ai_foundations + prompt_engineering (not 3)


# ── run_seed: return counts ───────────────────────────────────────────────────

def test_run_seed_returns_dict_with_expected_keys():
    export = _make_minimal_export()
    conn   = MagicMock()
    patches = _all_repo_patches()
    with patch(_BUILD, return_value=export), \
         patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
        counts = script.run_seed(conn)
    for key in ("courses", "modules", "topics", "skills", "topic_skills", "activities"):
        assert key in counts, f"Missing count key: {key}"


def test_run_seed_counts_courses():
    export = _make_minimal_export()  # 1 course
    conn   = MagicMock()
    patches = _all_repo_patches(course_id=42)
    with patch(_BUILD, return_value=export), \
         patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
        counts = script.run_seed(conn)
    assert counts["courses"] == 1


def test_run_seed_counts_modules():
    export = _make_minimal_export()  # 1 module
    conn   = MagicMock()
    patches = _all_repo_patches()
    with patch(_BUILD, return_value=export), \
         patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
        counts = script.run_seed(conn)
    assert counts["modules"] == 1


def test_run_seed_counts_topics():
    export = _make_minimal_export()  # 2 topics
    conn   = MagicMock()
    patches = _all_repo_patches()
    with patch(_BUILD, return_value=export), \
         patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
        counts = script.run_seed(conn)
    assert counts["topics"] == 2


def test_run_seed_counts_activities():
    export = _make_minimal_export()  # 2 topics × 3 activities each
    conn   = MagicMock()
    patches = _all_repo_patches()
    with patch(_BUILD, return_value=export), \
         patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
        counts = script.run_seed(conn)
    assert counts["activities"] == 6


def test_run_seed_skips_topic_when_course_missing():
    """If upsert_course returns None, topics must be skipped."""
    export = _make_minimal_export()
    conn   = MagicMock()
    with patch(_BUILD, return_value=export), \
         patch(_COURSE, return_value=None), \
         patch(_MODULE, return_value=None), \
         patch(_SKILL,  return_value=100), \
         patch(_TOPIC)  as mock_topic, \
         patch(_LINK,   return_value=None), \
         patch(_ACTIV,  return_value=1):
        counts = script.run_seed(conn)

    mock_topic.assert_not_called()
    assert counts["courses"]    == 0
    assert counts["topics"]     == 0
    assert counts["activities"] == 0


def test_run_seed_skips_activities_when_topic_returns_none():
    """If upsert_course_topic returns None, activities must be skipped."""
    export = _make_minimal_export()
    conn   = MagicMock()
    with patch(_BUILD, return_value=export), \
         patch(_COURSE, return_value=1), \
         patch(_MODULE, return_value=10), \
         patch(_SKILL,  return_value=100), \
         patch(_TOPIC,  return_value=None), \
         patch(_LINK,   return_value=None), \
         patch(_ACTIV)  as mock_act:
        counts = script.run_seed(conn)

    mock_act.assert_not_called()
    assert counts["activities"]  == 0
    assert counts["topic_skills"] == 0


# ── run_seed: no commit/rollback called on conn ───────────────────────────────

def test_run_seed_does_not_commit():
    export = _make_minimal_export()
    conn   = MagicMock()
    patches = _all_repo_patches()
    with patch(_BUILD, return_value=export), \
         patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
        script.run_seed(conn)
    conn.commit.assert_not_called()


def test_run_seed_does_not_rollback():
    export = _make_minimal_export()
    conn   = MagicMock()
    patches = _all_repo_patches()
    with patch(_BUILD, return_value=export), \
         patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
        script.run_seed(conn)
    conn.rollback.assert_not_called()


def test_run_seed_does_not_close_conn():
    export = _make_minimal_export()
    conn   = MagicMock()
    patches = _all_repo_patches()
    with patch(_BUILD, return_value=export), \
         patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
        script.run_seed(conn)
    conn.close.assert_not_called()


# ── main(): success path ───────────────────────────────────────────────────────

def test_main_commits_on_success(capsys):
    mock_conn  = MagicMock()
    good_counts = {
        "courses": 3, "modules": 15, "topics": 100,
        "skills": 8,  "topic_skills": 200, "activities": 600,
    }
    with patch("scripts.seed_modular_curriculum._get_connection",
               return_value=mock_conn), \
         patch("scripts.seed_modular_curriculum.run_seed",
               return_value=good_counts):
        script.main()

    mock_conn.commit.assert_called_once()


def test_main_closes_conn_on_success(capsys):
    mock_conn = MagicMock()
    with patch("scripts.seed_modular_curriculum._get_connection",
               return_value=mock_conn), \
         patch("scripts.seed_modular_curriculum.run_seed",
               return_value={k: 0 for k in
                             ("courses","modules","topics","skills","topic_skills","activities")}):
        script.main()
    mock_conn.close.assert_called_once()


def test_main_prints_counts(capsys):
    mock_conn  = MagicMock()
    good_counts = {
        "courses": 3, "modules": 15, "topics": 100,
        "skills": 8,  "topic_skills": 200, "activities": 600,
    }
    with patch("scripts.seed_modular_curriculum._get_connection",
               return_value=mock_conn), \
         patch("scripts.seed_modular_curriculum.run_seed",
               return_value=good_counts):
        script.main()

    out = capsys.readouterr().out
    assert "3"   in out   # courses
    assert "15"  in out   # modules
    assert "100" in out   # topics


# ── main(): error path ────────────────────────────────────────────────────────

def test_main_rolls_back_on_error():
    mock_conn = MagicMock()
    with patch("scripts.seed_modular_curriculum._get_connection",
               return_value=mock_conn), \
         patch("scripts.seed_modular_curriculum.run_seed",
               side_effect=RuntimeError("DB exploded")):
        try:
            script.main()
        except SystemExit:
            pass

    mock_conn.rollback.assert_called_once()


def test_main_closes_conn_on_error():
    mock_conn = MagicMock()
    with patch("scripts.seed_modular_curriculum._get_connection",
               return_value=mock_conn), \
         patch("scripts.seed_modular_curriculum.run_seed",
               side_effect=RuntimeError("failure")):
        try:
            script.main()
        except SystemExit:
            pass

    mock_conn.close.assert_called_once()


def test_main_does_not_commit_on_error():
    mock_conn = MagicMock()
    with patch("scripts.seed_modular_curriculum._get_connection",
               return_value=mock_conn), \
         patch("scripts.seed_modular_curriculum.run_seed",
               side_effect=RuntimeError("failure")):
        try:
            script.main()
        except SystemExit:
            pass

    mock_conn.commit.assert_not_called()


def test_main_exits_with_nonzero_on_error():
    mock_conn = MagicMock()
    with patch("scripts.seed_modular_curriculum._get_connection",
               return_value=mock_conn), \
         patch("scripts.seed_modular_curriculum.run_seed",
               side_effect=RuntimeError("failure")):
        try:
            script.main()
            raised = False
        except SystemExit as exc:
            raised = True
            assert exc.code != 0

    assert raised, "main() should have called sys.exit on error"


def test_main_exits_if_no_db_url():
    with patch("scripts.seed_modular_curriculum._get_connection",
               side_effect=RuntimeError("Set SUPABASE_DATABASE_URL")):
        try:
            script.main()
            raised = False
        except SystemExit as exc:
            raised = True
            assert exc.code != 0

    assert raised


def test_main_does_not_print_db_url(capsys):
    mock_conn = MagicMock()
    with patch("scripts.seed_modular_curriculum._get_connection",
               return_value=mock_conn), \
         patch("scripts.seed_modular_curriculum.run_seed",
               return_value={k: 0 for k in
                             ("courses","modules","topics","skills","topic_skills","activities")}):
        script.main()

    out = capsys.readouterr().out + capsys.readouterr().err
    assert "DATABASE_URL" not in out
    assert "password"     not in out.lower()
