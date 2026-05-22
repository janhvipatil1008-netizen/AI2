"""Tests for modular topic detail metadata behind the curriculum flag."""

from __future__ import annotations

import os
from contextlib import contextmanager
from copy import deepcopy
from unittest.mock import MagicMock, patch

os.environ["AI2_TEST_MODE"] = "1"
os.environ["ANTHROPIC_API_KEY"] = "test-key"

from fastapi.testclient import TestClient

from app import app
from curriculum.syllabus import ROLE_TRACKS, WEEKS
from curriculum.topics import get_topics_for_week


client = TestClient(app)
FLAG = "AI2_MODULAR_CURRICULUM_READS_ENABLED"


@contextmanager
def _conn_context():
    yield MagicMock()


def _start_session() -> str:
    response = client.post("/session/start", json={"track": "aipm", "week": 1})
    assert response.status_code == 200, response.text
    return response.json()["session_id"]


def _topic():
    return get_topics_for_week("aipm", 1)[0]


def _clear_related_flags(monkeypatch):
    monkeypatch.delenv(FLAG, raising=False)
    monkeypatch.delenv("AI2_PROGRESS_DB_READS_ENABLED", raising=False)
    monkeypatch.delenv("AI2_DB_WRITE_THROUGH_ENABLED", raising=False)
    monkeypatch.delenv("AI2_USAGE_LIMITS_ENABLED", raising=False)


def _fake_topic_result(*, source: str = "db", title: str = "Modular Detail Topic"):
    topic = _topic()
    return {
        "source": source,
        "topic": {
            "topic_id": 42,
            "legacy_topic_id": topic.topic_id,
            "topic_key": "modular-detail-topic",
            "title": title,
            "description": "Safe modular topic metadata.",
            "difficulty_level": "beginner",
            "estimated_minutes": 30,
            "status": "active",
            "metadata": {"private": "not rendered"},
            "skills": [
                {
                    "skill_key": "prompt_design",
                    "name": "Prompt Design",
                    "metadata": {"private": "not rendered"},
                }
            ],
            "activities": [
                {
                    "activity_key": "lesson",
                    "activity_type": "lesson",
                    "title": "Read & Learn",
                    "is_required": True,
                    "metadata": {"private": "not rendered"},
                }
            ],
        },
        "error": None,
    }


def test_flag_false_uses_old_topic_detail_path(monkeypatch):
    _clear_related_flags(monkeypatch)
    session_id = _start_session()
    topic = _topic()

    with patch(
        "services.modular_curriculum_fallback_service.get_topic_structure_by_legacy_id_with_fallback",
        side_effect=AssertionError("modular topic fallback must not run"),
    ) as fallback:
        response = client.get(f"/topic/{session_id}/{topic.topic_id}")

    assert response.status_code == 200
    assert topic.topic_title in response.text
    fallback.assert_not_called()


def test_flag_false_opens_no_db_connection(monkeypatch):
    _clear_related_flags(monkeypatch)
    session_id = _start_session()
    topic = _topic()

    with patch("database.pool.get_conn", side_effect=AssertionError("DB must not open")) as get_conn:
        response = client.get(f"/topic/{session_id}/{topic.topic_id}")

    assert response.status_code == 200
    get_conn.assert_not_called()


def test_flag_true_calls_modular_topic_fallback_service(monkeypatch):
    _clear_related_flags(monkeypatch)
    monkeypatch.setenv(FLAG, "1")
    session_id = _start_session()
    topic = _topic()
    fallback = MagicMock(return_value=_fake_topic_result())

    with patch("database.pool.get_conn", return_value=_conn_context()), patch(
        "services.modular_curriculum_fallback_service.get_topic_structure_by_legacy_id_with_fallback",
        fallback,
    ):
        response = client.get(f"/topic/{session_id}/{topic.topic_id}")

    assert response.status_code == 200
    fallback.assert_called_once()
    assert fallback.call_args.kwargs["legacy_topic_id"] == topic.topic_id


def test_flag_true_db_source_can_render_topic_detail(monkeypatch):
    _clear_related_flags(monkeypatch)
    monkeypatch.setenv(FLAG, "true")
    session_id = _start_session()
    topic = _topic()

    with patch("database.pool.get_conn", return_value=_conn_context()), patch(
        "services.modular_curriculum_fallback_service.get_topic_structure_by_legacy_id_with_fallback",
        return_value=_fake_topic_result(source="db", title="DB Modular Detail"),
    ):
        response = client.get(f"/topic/{session_id}/{topic.topic_id}")

    assert response.status_code == 200
    assert topic.topic_title in response.text
    assert "Prompt Design" in response.text
    assert "Read &amp; Learn" in response.text
    assert "not rendered" not in response.text


def test_flag_true_fallback_source_can_render_topic_detail(monkeypatch):
    _clear_related_flags(monkeypatch)
    monkeypatch.setenv(FLAG, "on")
    session_id = _start_session()
    topic = _topic()

    with patch("database.pool.get_conn", return_value=_conn_context()), patch(
        "services.modular_curriculum_fallback_service.get_topic_structure_by_legacy_id_with_fallback",
        return_value=_fake_topic_result(source="fallback", title="Fallback Modular Detail"),
    ):
        response = client.get(f"/topic/{session_id}/{topic.topic_id}")

    assert response.status_code == 200
    assert topic.topic_title in response.text
    assert "Prompt Design" in response.text


def test_db_connection_failure_renders_old_topic_detail_safely(monkeypatch):
    _clear_related_flags(monkeypatch)
    monkeypatch.setenv(FLAG, "yes")
    session_id = _start_session()
    topic = _topic()

    with patch("database.pool.get_conn", side_effect=RuntimeError("cannot connect postgres://secret")):
        response = client.get(f"/topic/{session_id}/{topic.topic_id}")

    assert response.status_code == 200
    assert topic.topic_title in response.text
    assert "postgres://secret" not in response.text
    assert "Prompt Design" not in response.text


def test_existing_topic_id_remains_legacy_topic_id(monkeypatch):
    _clear_related_flags(monkeypatch)
    monkeypatch.setenv(FLAG, "1")
    session_id = _start_session()
    topic = _topic()

    with patch("database.pool.get_conn", return_value=_conn_context()), patch(
        "services.modular_curriculum_fallback_service.get_topic_structure_by_legacy_id_with_fallback",
        return_value=_fake_topic_result(source="db"),
    ):
        response = client.get(f"/topic/{session_id}/{topic.topic_id}")

    assert response.status_code == 200
    assert f'data-topic-id="{topic.topic_id}"' in response.text
    assert f'name="topic_id" value="{topic.topic_id}"' in response.text


def test_content_generation_route_behavior_remains_unchanged(monkeypatch):
    _clear_related_flags(monkeypatch)
    monkeypatch.setenv(FLAG, "1")
    session_id = _start_session()
    topic = _topic()

    with patch(
        "services.modular_curriculum_fallback_service.get_topic_structure_by_legacy_id_with_fallback",
        side_effect=AssertionError("generation must not load modular topic metadata"),
    ):
        response = client.post("/topic/content/generate", json={
            "session_id": session_id,
            "topic_id": topic.topic_id,
            "refresh": False,
        })

    assert response.status_code == 200
    assert response.json()["topic_id"] == topic.topic_id


def test_practice_generation_route_behavior_remains_unchanged(monkeypatch):
    _clear_related_flags(monkeypatch)
    monkeypatch.setenv(FLAG, "1")
    session_id = _start_session()
    topic = _topic()

    with patch(
        "services.modular_curriculum_fallback_service.get_topic_structure_by_legacy_id_with_fallback",
        side_effect=AssertionError("practice must not load modular topic metadata"),
    ):
        response = client.post("/topic/practice/generate", json={
            "session_id": session_id,
            "topic_id": topic.topic_id,
            "practice_type": "quiz",
            "refresh": False,
        })

    assert response.status_code == 200
    assert response.json()["topic_id"] == topic.topic_id


def test_quiz_portfolio_interview_submission_routes_remain_unchanged():
    paths = {route.path for route in app.routes}

    assert "/quiz/submit" in paths
    assert "/portfolio/submit" in paths
    assert "/interview/submit" in paths


def test_no_claude_call_is_made_while_loading_topic_detail(monkeypatch):
    _clear_related_flags(monkeypatch)
    monkeypatch.setenv(FLAG, "1")
    session_id = _start_session()
    topic = _topic()

    with patch("database.pool.get_conn", return_value=_conn_context()), patch(
        "services.modular_curriculum_fallback_service.get_topic_structure_by_legacy_id_with_fallback",
        return_value=_fake_topic_result(),
    ), patch(
        "routes.topics.deps.make_client",
        side_effect=AssertionError("Claude must not be called"),
    ) as make_client:
        response = client.get(f"/topic/{session_id}/{topic.topic_id}")

    assert response.status_code == 200
    make_client.assert_not_called()


def test_no_seed_script_is_called(monkeypatch):
    _clear_related_flags(monkeypatch)
    monkeypatch.setenv(FLAG, "1")
    session_id = _start_session()
    topic = _topic()

    with patch("database.pool.get_conn", return_value=_conn_context()), patch(
        "services.modular_curriculum_fallback_service.get_topic_structure_by_legacy_id_with_fallback",
        return_value=_fake_topic_result(),
    ), patch(
        "scripts.seed_modular_curriculum.run_seed",
        side_effect=AssertionError("seed script must not run"),
    ) as run_seed:
        response = client.get(f"/topic/{session_id}/{topic.topic_id}")

    assert response.status_code == 200
    run_seed.assert_not_called()


def test_no_weeks_or_role_tracks_mutation(monkeypatch):
    _clear_related_flags(monkeypatch)
    monkeypatch.setenv(FLAG, "1")
    session_id = _start_session()
    topic = _topic()
    weeks_before = deepcopy(WEEKS)
    role_tracks_before = deepcopy(ROLE_TRACKS)

    with patch("database.pool.get_conn", return_value=_conn_context()), patch(
        "services.modular_curriculum_fallback_service.get_topic_structure_by_legacy_id_with_fallback",
        return_value=_fake_topic_result(),
    ):
        response = client.get(f"/topic/{session_id}/{topic.topic_id}")

    assert response.status_code == 200
    assert WEEKS == weeks_before
    assert ROLE_TRACKS == role_tracks_before


def test_route_urls_remain_unchanged():
    paths = {route.path for route in app.routes}

    assert {
        "/topics/{session_id}",
        "/topic/{session_id}/{topic_id}",
        "/topic/content/generate",
        "/topic/practice/generate",
        "/quiz/submit",
        "/portfolio/submit",
        "/interview/submit",
    }.issubset(paths)
