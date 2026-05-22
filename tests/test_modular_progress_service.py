"""Tests for services/modular_progress_service.py."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import services.modular_progress_service as svc


SERVICE_PATH = Path("services/modular_progress_service.py")


def _src() -> str:
    return SERVICE_PATH.read_text(encoding="utf-8")


def _activities() -> list[dict]:
    return [
        {"activity_type": "lesson", "is_required": True},
        {"activity_type": "practice_task", "is_required": True},
        {"activity_type": "quiz", "is_required": True},
        {"activity_type": "portfolio_task", "is_required": True},
        {"activity_type": "interview_practice", "is_required": True},
        {"activity_type": "reflection", "is_required": False},
    ]


def _topic(
    key: str,
    legacy_id: str,
    *,
    module_key: str | None = None,
    activities: list[dict] | None = None,
) -> dict:
    topic = {
        "topic_key": key,
        "legacy_topic_id": legacy_id,
        "activities": _activities() if activities is None else activities,
        "metadata": {"private": "nope"},
    }
    if module_key is not None:
        topic["module_key"] = module_key
    return topic


def _course_structure() -> dict:
    return {
        "course": {
            "course_key": "aipm-foundations",
            "metadata": {"private": "do-not-return"},
        },
        "modules": [
            {
                "module_key": "module-01",
                "sequence_order": 0,
                "topics": [
                    _topic("topic-1", "legacy-1"),
                    _topic("topic-2", "legacy-2"),
                ],
            },
            {
                "module_key": "module-02",
                "sequence_order": 1,
                "topics": [
                    _topic("topic-3", "legacy-3"),
                ],
            },
        ],
        "unassigned_topics": [
            _topic("topic-4", "legacy-4", module_key=None),
        ],
    }


def test_module_imports_safely():
    assert svc is not None


def test_expected_functions_exist():
    for name in (
        "clamp_percent",
        "normalize_activity_type",
        "infer_completed_activity_types",
        "calculate_topic_progress",
        "calculate_module_progress",
        "calculate_course_progress",
        "pick_current_position_from_progress",
    ):
        assert callable(getattr(svc, name, None)), f"missing {name}"


def test_clamp_percent_works():
    assert svc.clamp_percent(None) == 0
    assert svc.clamp_percent(-10) == 0
    assert svc.clamp_percent(101) == 100
    assert svc.clamp_percent(42.4) == 42
    assert svc.clamp_percent(42.6) == 43


def test_normalize_activity_type_works():
    assert svc.normalize_activity_type("lesson") == "lesson"
    assert svc.normalize_activity_type("learning_content") == "lesson"
    assert svc.normalize_activity_type("content") == "lesson"
    assert svc.normalize_activity_type("practice") == "practice"
    assert svc.normalize_activity_type("practice_task") == "practice"
    assert svc.normalize_activity_type("quiz") == "quiz"
    assert svc.normalize_activity_type("portfolio") == "portfolio"
    assert svc.normalize_activity_type("portfolio_task") == "portfolio"
    assert svc.normalize_activity_type("interview") == "interview"
    assert svc.normalize_activity_type("interview_practice") == "interview"
    assert svc.normalize_activity_type("reflection") == "reflection"
    assert svc.normalize_activity_type(None) == "unknown"
    assert svc.normalize_activity_type("") == "unknown"
    assert svc.normalize_activity_type("not-real") == "unknown"


def test_infer_completed_activity_types_reads_existing_session_progress_safely():
    session_progress = {
        "legacy-1": {
            "learn": "done",
            "practice_task": "done",
            "quiz": "in_progress",
            "portfolio_task": "not_started",
            "reflection": "done",
        }
    }

    result = svc.infer_completed_activity_types(
        legacy_topic_id="legacy-1",
        session_progress=session_progress,
    )

    assert result == {"lesson", "practice", "reflection"}


def test_infer_completed_activity_types_reads_quiz_portfolio_interview_feedback_safely():
    result = svc.infer_completed_activity_types(
        legacy_topic_id="legacy-1",
        quiz_submissions={"legacy-1": {"answers": "private", "evaluation": "good"}},
        portfolio_submissions={"legacy-1": {"submission": "private", "feedback": "ok"}},
        interview_submissions={"legacy-1": {"answer": "private", "score": 7}},
    )

    assert result == {"quiz", "portfolio", "interview"}


def test_generated_content_alone_does_not_complete_lesson():
    result = svc.infer_completed_activity_types(
        legacy_topic_id="legacy-1",
        generated_content={"legacy-1": {"content": "generated lesson text"}},
    )

    assert "lesson" not in result


def test_calculate_topic_progress_handles_required_activities():
    result = svc.calculate_topic_progress(
        topic=_topic("topic-1", "legacy-1"),
        completed_activity_types={"lesson", "practice", "quiz"},
    )

    assert result["topic_key"] == "topic-1"
    assert result["legacy_topic_id"] == "legacy-1"
    assert result["required_activities_total"] == 5
    assert result["required_activities_completed"] == 3
    assert result["completion_percent"] == 60
    assert result["status"] == "in_progress"


def test_calculate_topic_progress_handles_no_activities_safely():
    result = svc.calculate_topic_progress(
        topic=_topic("topic-empty", "legacy-empty", activities=[]),
        completed_activity_types={"lesson"},
    )

    assert result["required_activities_total"] == 0
    assert result["required_activities_completed"] == 0
    assert result["completion_percent"] == 0
    assert result["status"] == "not_started"


def test_calculate_module_progress_calculates_topic_completion():
    module = {
        "module_key": "module-01",
        "sequence_order": 0,
        "topics": [
            {
                "topic_key": "topic-1",
                "legacy_topic_id": "legacy-1",
                "module_key": "module-01",
                "status": "completed",
                "completion_percent": 100,
            },
            {
                "topic_key": "topic-2",
                "legacy_topic_id": "legacy-2",
                "module_key": "module-01",
                "status": "in_progress",
                "completion_percent": 20,
            },
        ],
    }

    result = svc.calculate_module_progress(module=module)

    assert result["module_key"] == "module-01"
    assert result["sequence_order"] == 0
    assert result["total_topics"] == 2
    assert result["completed_topics"] == 1
    assert result["progress_percent"] == 60
    assert result["status"] == "in_progress"


def test_calculate_course_progress_calculates_full_nested_course_progress():
    result = svc.calculate_course_progress(
        course_structure=_course_structure(),
        session_progress={
            "legacy-1": {
                "learn": "done",
                "practice_task": "done",
                "quiz": "done",
                "portfolio_task": "done",
                "interview_practice": "done",
            },
            "legacy-2": {"learn": "done"},
        },
    )

    assert result["course_key"] == "aipm-foundations"
    assert result["total_topics"] == 4
    assert result["completed_topics"] == 1
    assert result["progress_percent"] == 30
    assert result["status"] == "in_progress"
    assert len(result["modules"]) == 2
    assert result["modules"][0]["completed_topics"] == 1
    assert len(result["topic_progress"]) == 4


def test_calculate_course_progress_uses_legacy_topic_id_bridge():
    result = svc.calculate_course_progress(
        course_structure=_course_structure(),
        session_progress={"legacy-2": {"quiz": "done"}},
    )
    topic_2 = next(t for t in result["topic_progress"] if t["topic_key"] == "topic-2")

    assert topic_2["legacy_topic_id"] == "legacy-2"
    assert topic_2["required_activities_completed"] == 1
    assert topic_2["completion_percent"] == 20


def test_calculate_course_progress_excludes_private_submission_and_generated_text():
    result = svc.calculate_course_progress(
        course_structure=_course_structure(),
        generated_content={"legacy-1": {"content": "PRIVATE GENERATED LESSON"}},
        quiz_submissions={"legacy-1": {"answers": "PRIVATE ANSWERS", "evaluation": "PRIVATE EVAL"}},
        portfolio_submissions={"legacy-1": {"submission": "PRIVATE SUBMISSION", "feedback": "PRIVATE FEEDBACK"}},
        interview_submissions={"legacy-1": {"answer": "PRIVATE ANSWER", "feedback": "PRIVATE INTERVIEW"}},
    )

    rendered = repr(result)
    assert "PRIVATE GENERATED LESSON" not in rendered
    assert "PRIVATE ANSWERS" not in rendered
    assert "PRIVATE SUBMISSION" not in rendered
    assert "PRIVATE ANSWER" not in rendered
    assert "metadata" not in rendered


def test_pick_current_position_from_progress_picks_in_progress_first():
    progress = {
        "topic_progress": [
            {"module_key": "m1", "topic_key": "t1", "legacy_topic_id": "l1", "status": "not_started"},
            {"module_key": "m1", "topic_key": "t2", "legacy_topic_id": "l2", "status": "in_progress"},
        ]
    }

    assert svc.pick_current_position_from_progress(progress) == {
        "current_module_key": "m1",
        "current_topic_key": "t2",
        "current_legacy_topic_id": "l2",
    }


def test_pick_current_position_from_progress_picks_not_started_next():
    progress = {
        "topic_progress": [
            {"module_key": "m1", "topic_key": "t1", "legacy_topic_id": "l1", "status": "completed"},
            {"module_key": "m2", "topic_key": "t2", "legacy_topic_id": "l2", "status": "not_started"},
        ]
    }

    assert svc.pick_current_position_from_progress(progress)["current_topic_key"] == "t2"


def test_pick_current_position_from_progress_handles_all_completed():
    progress = {
        "topic_progress": [
            {"module_key": "m1", "topic_key": "t1", "legacy_topic_id": "l1", "status": "completed"},
            {"module_key": "m2", "topic_key": "t2", "legacy_topic_id": "l2", "status": "completed"},
        ]
    }

    assert svc.pick_current_position_from_progress(progress) == {
        "current_module_key": "m2",
        "current_topic_key": "t2",
        "current_legacy_topic_id": "l2",
    }


def test_inputs_are_not_mutated():
    course_structure = _course_structure()
    session_progress = {"legacy-1": {"learn": "done"}}
    generated_content = {"legacy-1": {"content": "generated"}}
    quiz_submissions = {"legacy-1": {"evaluation": "ok"}}
    originals = deepcopy((course_structure, session_progress, generated_content, quiz_submissions))

    svc.calculate_course_progress(
        course_structure=course_structure,
        session_progress=session_progress,
        generated_content=generated_content,
        quiz_submissions=quiz_submissions,
    )

    assert (course_structure, session_progress, generated_content, quiz_submissions) == originals


def test_no_db_connection_creation():
    src = _src()
    assert "psycopg2.connect" not in src
    assert "database.pool" not in src
    assert "get_conn(" not in src
    assert "_connect(" not in src


def test_no_env_reads():
    src = _src()
    assert "import os" not in src
    assert "os.environ" not in src
    assert "os.getenv" not in src
    assert "getenv(" not in src


def test_no_app_or_routes_imports():
    src = _src()
    assert "from app" not in src
    assert "import app" not in src
    assert "from routes" not in src
    assert "import routes" not in src


def test_no_commit_or_rollback():
    src = _src()
    assert ".commit()" not in src
    assert ".rollback()" not in src


def test_no_claude_or_provider_calls():
    src = _src().lower()
    assert "anthropic" not in src
    assert "claude" not in src
    assert "openai" not in src
    assert "boto3" not in src
