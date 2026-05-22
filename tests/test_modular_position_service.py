"""Tests for services/modular_position_service.py."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import services.modular_position_service as svc


SERVICE_PATH = Path("services/modular_position_service.py")


def _src() -> str:
    return SERVICE_PATH.read_text(encoding="utf-8")


def _topic(
    topic_key: str,
    legacy_topic_id: str,
    *,
    module_key: str | None = None,
    status: str = "not_started",
    completion_percent: int = 0,
    sequence_order: int | None = None,
) -> dict:
    topic = {
        "topic_key": topic_key,
        "legacy_topic_id": legacy_topic_id,
        "status": status,
        "completion_percent": completion_percent,
        "metadata": {"private": "do-not-copy"},
        "feedback": "private",
    }
    if module_key is not None:
        topic["module_key"] = module_key
    if sequence_order is not None:
        topic["sequence_order"] = sequence_order
    return topic


def _course_progress() -> dict:
    return {
        "course_key": "aipm-foundations",
        "progress_percent": 35,
        "status": "in_progress",
        "modules": [
            {
                "module_key": "module-01",
                "sequence_order": 1,
                "topics": [
                    _topic(
                        "topic-01",
                        "legacy-01",
                        status="completed",
                        completion_percent=100,
                        sequence_order=1,
                    ),
                    _topic(
                        "topic-02",
                        "legacy-02",
                        status="in_progress",
                        completion_percent=40,
                        sequence_order=2,
                    ),
                ],
            },
            {
                "module_key": "module-02",
                "sequence_order": 2,
                "topics": [
                    _topic(
                        "topic-03",
                        "legacy-03",
                        status="not_started",
                        completion_percent=0,
                        sequence_order=1,
                    ),
                ],
            },
        ],
        "unassigned_topics": [
            _topic(
                "topic-04",
                "legacy-04",
                status="not_started",
                completion_percent=0,
                sequence_order=99,
            )
        ],
        "topic_progress": [],
    }


class FakeSession:
    current_week = 4


def test_module_imports_safely():
    assert svc is not None


def test_expected_functions_exist():
    for name in (
        "flatten_course_topics",
        "is_topic_completed",
        "is_topic_in_progress",
        "pick_current_topic",
        "pick_next_topic",
        "build_position_summary",
        "build_legacy_position_fallback",
    ):
        assert callable(getattr(svc, name, None)), f"missing {name}"


def test_flatten_course_topics_preserves_order():
    result = svc.flatten_course_topics(_course_progress())

    assert [topic["topic_key"] for topic in result] == [
        "topic-01",
        "topic-02",
        "topic-03",
        "topic-04",
    ]
    assert result[0]["module_key"] == "module-01"
    assert result[1]["sequence_order"] == 2
    assert result[2]["module_key"] == "module-02"


def test_flatten_course_topics_includes_unassigned_topics():
    result = svc.flatten_course_topics(_course_progress())

    assert result[-1] == {
        "module_key": None,
        "topic_key": "topic-04",
        "legacy_topic_id": "legacy-04",
        "status": "not_started",
        "completion_percent": 0,
        "sequence_order": 99,
    }


def test_flatten_course_topics_does_not_mutate_input():
    progress = _course_progress()
    original = deepcopy(progress)

    result = svc.flatten_course_topics(progress)
    result[0]["status"] = "changed"

    assert progress == original


def test_flatten_course_topics_handles_invalid_input():
    assert svc.flatten_course_topics(None) == []
    assert svc.flatten_course_topics([]) == []
    assert svc.flatten_course_topics({"modules": [None], "unassigned_topics": ["bad"]}) == []


def test_is_topic_completed_works():
    assert svc.is_topic_completed({"status": "completed", "completion_percent": 0})
    assert svc.is_topic_completed({"status": "in_progress", "completion_percent": 100})
    assert not svc.is_topic_completed({"status": "in_progress", "completion_percent": 99})
    assert not svc.is_topic_completed({})


def test_is_topic_in_progress_works():
    assert svc.is_topic_in_progress({"status": "in_progress", "completion_percent": 0})
    assert svc.is_topic_in_progress({"status": "not_started", "completion_percent": 30})
    assert not svc.is_topic_in_progress({"status": "completed", "completion_percent": 20})
    assert not svc.is_topic_in_progress({"status": "completed", "completion_percent": 100})
    assert not svc.is_topic_in_progress({"status": "not_started", "completion_percent": 0})


def test_pick_current_topic_prefers_in_progress():
    result = svc.pick_current_topic(_course_progress())

    assert result == {
        "module_key": "module-01",
        "topic_key": "topic-02",
        "legacy_topic_id": "legacy-02",
        "status": "in_progress",
        "completion_percent": 40,
        "source": "in_progress",
    }


def test_pick_current_topic_picks_first_not_started_when_none_in_progress():
    progress = _course_progress()
    progress["modules"][0]["topics"][1]["status"] = "completed"
    progress["modules"][0]["topics"][1]["completion_percent"] = 100

    result = svc.pick_current_topic(progress)

    assert result["topic_key"] == "topic-03"
    assert result["module_key"] == "module-02"
    assert result["source"] == "next_not_started"


def test_pick_current_topic_falls_back_to_last_completed_when_all_completed():
    progress = _course_progress()
    for topic in progress["modules"][0]["topics"]:
        topic["status"] = "completed"
        topic["completion_percent"] = 100
    progress["modules"][1]["topics"][0]["status"] = "completed"
    progress["modules"][1]["topics"][0]["completion_percent"] = 100
    progress["unassigned_topics"][0]["status"] = "completed"
    progress["unassigned_topics"][0]["completion_percent"] = 100

    result = svc.pick_current_topic(progress)

    assert result["topic_key"] == "topic-04"
    assert result["legacy_topic_id"] == "legacy-04"
    assert result["source"] == "completed_fallback"


def test_pick_current_topic_handles_empty_input():
    assert svc.pick_current_topic(None) == {
        "module_key": None,
        "topic_key": None,
        "legacy_topic_id": None,
        "status": None,
        "completion_percent": 0,
        "source": "empty",
    }


def test_pick_next_topic_picks_first_incomplete_topic():
    result = svc.pick_next_topic(_course_progress())

    assert result["topic_key"] == "topic-02"
    assert result["source"] == "next_not_started"


def test_pick_next_topic_handles_all_completed():
    progress = {
        "modules": [
            {
                "module_key": "module-01",
                "topics": [
                    _topic("topic-01", "legacy-01", status="completed", completion_percent=100)
                ],
            }
        ],
        "unassigned_topics": [],
    }

    assert svc.pick_next_topic(progress) == {
        "module_key": None,
        "topic_key": None,
        "legacy_topic_id": None,
        "status": None,
        "completion_percent": 0,
        "source": "completed",
    }


def test_build_position_summary_returns_current_and_next():
    result = svc.build_position_summary(_course_progress())

    assert result["current"]["topic_key"] == "topic-02"
    assert result["next"]["topic_key"] == "topic-02"
    assert result["has_next"] is True
    assert result["course_progress_percent"] == 35
    assert result["course_status"] == "in_progress"


def test_build_legacy_position_fallback_uses_module_wording_not_week_wording():
    result = svc.build_legacy_position_fallback(FakeSession())

    assert result == {
        "current_module_label": "Module 4",
        "source": "session_fallback",
    }
    assert "Week" not in repr(result)
    assert svc.build_legacy_position_fallback(None) == {
        "current_module_label": None,
        "source": "disabled",
    }


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
