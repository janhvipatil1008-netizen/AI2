"""Tests for modular curriculum reads behind the topics listing flag."""

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


def _static_topic():
    return get_topics_for_week("aipm", 1)[0]


def _fake_course_result(*, source: str = "db", title: str = "Modular Topic"):
    topic = _static_topic()
    return {
        "source": source,
        "course_structure": {
            "course": {
                "course_key": "aipm-foundations",
                "title": "AI PM Foundations",
            },
            "modules": [
                {
                    "module_key": "module-01",
                    "title": "Modular Module",
                    "description": "Modular module description",
                    "sequence_order": 0,
                    "topics": [
                        {
                            "legacy_topic_id": topic.topic_id,
                            "topic_key": "modular-topic",
                            "title": title,
                            "description": "Modular topic description",
                            "sequence_order": 0,
                        }
                    ],
                }
            ],
            "unassigned_topics": [],
        },
        "error": None,
    }


def _clear_related_flags(monkeypatch):
    monkeypatch.delenv(FLAG, raising=False)
    monkeypatch.delenv("AI2_PROGRESS_DB_READS_ENABLED", raising=False)
    monkeypatch.delenv("AI2_DB_WRITE_THROUGH_ENABLED", raising=False)


def test_flag_false_uses_old_static_path(monkeypatch):
    _clear_related_flags(monkeypatch)
    session_id = _start_session()
    topic = _static_topic()

    with patch(
        "routes.topics._modular_topics_for_listing",
        side_effect=AssertionError("modular path must not run"),
    ) as modular:
        response = client.get(f"/topics/{session_id}")

    assert response.status_code == 200
    assert topic.topic_title in response.text
    modular.assert_not_called()


def test_flag_false_opens_no_db_connection(monkeypatch):
    _clear_related_flags(monkeypatch)
    session_id = _start_session()

    with patch("database.pool.get_conn", side_effect=AssertionError("DB must not open")) as get_conn:
        response = client.get(f"/topics/{session_id}")

    assert response.status_code == 200
    get_conn.assert_not_called()


def test_flag_true_calls_modular_fallback_service(monkeypatch):
    _clear_related_flags(monkeypatch)
    monkeypatch.setenv(FLAG, "1")
    session_id = _start_session()
    fallback = MagicMock(return_value=_fake_course_result())

    with patch("database.pool.get_conn", return_value=_conn_context()), patch(
        "services.modular_curriculum_fallback_service.get_course_structure_with_fallback",
        fallback,
    ):
        response = client.get(f"/topics/{session_id}")

    assert response.status_code == 200
    fallback.assert_called_once()
    assert fallback.call_args.kwargs["course_key"] == "aipm-foundations"
    assert fallback.call_args.kwargs["fallback_track_key"] == "aipm"


def test_flag_true_db_source_renders_topics_page(monkeypatch):
    _clear_related_flags(monkeypatch)
    monkeypatch.setenv(FLAG, "true")
    session_id = _start_session()

    with patch("database.pool.get_conn", return_value=_conn_context()), patch(
        "services.modular_curriculum_fallback_service.get_course_structure_with_fallback",
        return_value=_fake_course_result(source="db", title="DB Modular Topic"),
    ):
        response = client.get(f"/topics/{session_id}")

    assert response.status_code == 200
    assert "DB Modular Topic" in response.text
    assert "Modular Module" in response.text


def test_flag_true_fallback_source_renders_topics_page(monkeypatch):
    _clear_related_flags(monkeypatch)
    monkeypatch.setenv(FLAG, "on")
    session_id = _start_session()

    with patch("database.pool.get_conn", return_value=_conn_context()), patch(
        "services.modular_curriculum_fallback_service.get_course_structure_with_fallback",
        return_value=_fake_course_result(source="fallback", title="Fallback Modular Topic"),
    ):
        response = client.get(f"/topics/{session_id}")

    assert response.status_code == 200
    assert "Fallback Modular Topic" in response.text


def test_db_connection_failure_renders_static_fallback(monkeypatch):
    _clear_related_flags(monkeypatch)
    monkeypatch.setenv(FLAG, "yes")
    session_id = _start_session()
    static_topic = _static_topic()

    with patch("database.pool.get_conn", side_effect=RuntimeError("cannot connect")) as get_conn:
        response = client.get(f"/topics/{session_id}")

    assert response.status_code == 200
    assert static_topic.topic_title in response.text
    get_conn.assert_called_once()


def test_legacy_topic_id_is_preserved_for_existing_urls(monkeypatch):
    _clear_related_flags(monkeypatch)
    monkeypatch.setenv(FLAG, "1")
    session_id = _start_session()
    static_topic = _static_topic()

    with patch("database.pool.get_conn", return_value=_conn_context()), patch(
        "services.modular_curriculum_fallback_service.get_course_structure_with_fallback",
        return_value=_fake_course_result(source="db", title="Legacy Preserved Topic"),
    ):
        response = client.get(f"/topics/{session_id}")

    assert response.status_code == 200
    assert f"/topic/{session_id}/{static_topic.topic_id}" in response.text


def test_progress_works_with_existing_session_context_keys(monkeypatch):
    _clear_related_flags(monkeypatch)
    monkeypatch.setenv(FLAG, "1")
    session_id = _start_session()
    static_topic = _static_topic()

    progress_response = client.post("/topic/progress", json={
        "session_id": session_id,
        "topic_id": static_topic.topic_id,
        "step": "learn",
        "status": "done",
    })
    assert progress_response.status_code == 200

    with patch("database.pool.get_conn", return_value=_conn_context()), patch(
        "services.modular_curriculum_fallback_service.get_course_structure_with_fallback",
        return_value=_fake_course_result(source="db", title="Progress Modular Topic"),
    ):
        response = client.get(f"/topics/{session_id}")

    assert response.status_code == 200
    assert "20%" in response.text
    assert "Continue Quiz" in response.text


def test_no_claude_call_is_made(monkeypatch):
    _clear_related_flags(monkeypatch)
    monkeypatch.setenv(FLAG, "1")
    session_id = _start_session()

    with patch("database.pool.get_conn", return_value=_conn_context()), patch(
        "services.modular_curriculum_fallback_service.get_course_structure_with_fallback",
        return_value=_fake_course_result(),
    ), patch(
        "routes.topics.deps.make_client",
        side_effect=AssertionError("Claude must not be called"),
    ) as make_client:
        response = client.get(f"/topics/{session_id}")

    assert response.status_code == 200
    make_client.assert_not_called()


def test_no_seed_script_is_called(monkeypatch):
    _clear_related_flags(monkeypatch)
    monkeypatch.setenv(FLAG, "1")
    session_id = _start_session()

    with patch("database.pool.get_conn", return_value=_conn_context()), patch(
        "services.modular_curriculum_fallback_service.get_course_structure_with_fallback",
        return_value=_fake_course_result(),
    ), patch(
        "scripts.seed_modular_curriculum.run_seed",
        side_effect=AssertionError("seed script must not run"),
    ) as run_seed:
        response = client.get(f"/topics/{session_id}")

    assert response.status_code == 200
    run_seed.assert_not_called()


def test_no_weeks_or_role_tracks_mutation(monkeypatch):
    _clear_related_flags(monkeypatch)
    monkeypatch.setenv(FLAG, "1")
    session_id = _start_session()
    weeks_before = deepcopy(WEEKS)
    role_tracks_before = deepcopy(ROLE_TRACKS)

    with patch("database.pool.get_conn", return_value=_conn_context()), patch(
        "services.modular_curriculum_fallback_service.get_course_structure_with_fallback",
        return_value=_fake_course_result(),
    ):
        response = client.get(f"/topics/{session_id}")

    assert response.status_code == 200
    assert WEEKS == weeks_before
    assert ROLE_TRACKS == role_tracks_before


def test_topic_detail_route_behavior_remains_unchanged(monkeypatch):
    _clear_related_flags(monkeypatch)
    monkeypatch.setenv(FLAG, "1")
    session_id = _start_session()
    static_topic = _static_topic()

    with patch(
        "services.modular_curriculum_fallback_service.get_course_structure_with_fallback",
        side_effect=AssertionError("topic detail must not use modular listing read"),
    ):
        response = client.get(f"/topic/{session_id}/{static_topic.topic_id}")

    assert response.status_code == 200
    assert static_topic.topic_title in response.text


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
