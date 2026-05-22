import os

import pytest

os.environ["AI2_TEST_MODE"] = "1"
os.environ["ANTHROPIC_API_KEY"] = "test-key"

from fastapi.testclient import TestClient

from app import app
from config import CareerTrack
from context.session import SessionContext
from curriculum.topics import get_topics_for_week

client = TestClient(app)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _start_session(track: str = "aipm", week: int = 1) -> str:
    response = client.post("/session/start", json={"track": track, "week": week})
    assert response.status_code == 200, response.text
    return response.json()["session_id"]


# ── Unit tests: SessionContext ────────────────────────────────────────────────

def test_session_default_topic_notes_is_empty():
    session = SessionContext(track=CareerTrack.AI_PM)
    assert session.topic_notes == {}


def test_get_topic_notes_returns_empty_default():
    session = SessionContext(track=CareerTrack.AI_PM)
    notes = session.get_topic_notes("some-topic")
    assert notes == {
        "reflection":       "",
        "confusions":       "",
        "application_idea": "",
        "updated_at":       "",
    }


def test_save_topic_notes_strips_whitespace_and_saves():
    session = SessionContext(track=CareerTrack.AI_PM)
    notes = session.save_topic_notes(
        topic_id         = "topic-1",
        reflection       = "  I learned a lot  ",
        confusions       = "  Still unclear on X  ",
        application_idea = "  Build a pipeline  ",
    )
    assert notes["reflection"]       == "I learned a lot"
    assert notes["confusions"]       == "Still unclear on X"
    assert notes["application_idea"] == "Build a pipeline"
    assert notes["updated_at"] != ""
    assert "topic-1" in session.topic_notes


def test_save_topic_notes_sets_updated_at():
    session = SessionContext(track=CareerTrack.AI_PM)
    notes = session.save_topic_notes("topic-1", reflection="test")
    assert notes["updated_at"] != ""


def test_save_topic_notes_overwrites_previous():
    session = SessionContext(track=CareerTrack.AI_PM)
    session.save_topic_notes("topic-1", reflection="First")
    notes = session.save_topic_notes("topic-1", reflection="Second")
    assert notes["reflection"] == "Second"
    assert session.get_topic_notes("topic-1")["reflection"] == "Second"


def test_get_topic_notes_returns_saved_values():
    session = SessionContext(track=CareerTrack.AI_PM)
    session.save_topic_notes("topic-1", reflection="Understood X", confusions="Not sure about Y")
    notes = session.get_topic_notes("topic-1")
    assert notes["reflection"]  == "Understood X"
    assert notes["confusions"]  == "Not sure about Y"
    assert notes["application_idea"] == ""


def test_to_dict_from_dict_preserves_topic_notes():
    session = SessionContext(track=CareerTrack.AI_PM)
    session.save_topic_notes("topic-1", reflection="Key insight", application_idea="Use in project")
    restored = SessionContext.from_dict(session.to_dict())
    notes = restored.get_topic_notes("topic-1")
    assert notes["reflection"]       == "Key insight"
    assert notes["application_idea"] == "Use in project"


def test_from_dict_missing_topic_notes_defaults_to_empty():
    session = SessionContext(track=CareerTrack.AI_PM)
    d = session.to_dict()
    del d["topic_notes"]
    restored = SessionContext.from_dict(d)
    assert restored.topic_notes == {}
    assert restored.get_topic_notes("any-topic")["reflection"] == ""


# ── Route tests ───────────────────────────────────────────────────────────────

def test_topic_notes_endpoint_saves_notes():
    session_id = _start_session()
    topic = get_topics_for_week("aipm", 1)[0]

    response = client.post("/topic/notes", json={
        "session_id":       session_id,
        "topic_id":         topic.topic_id,
        "reflection":       "I understood the concept.",
        "confusions":       "Still unclear on edge cases.",
        "application_idea": "Use this in my RAG project.",
    })

    assert response.status_code == 200
    data = response.json()
    assert data["topic_id"] == topic.topic_id
    assert data["notes"]["reflection"]       == "I understood the concept."
    assert data["notes"]["confusions"]       == "Still unclear on edge cases."
    assert data["notes"]["application_idea"] == "Use this in my RAG project."
    assert data["notes"]["updated_at"] != ""


def test_topic_notes_returns_completion_percent():
    session_id = _start_session()
    topic = get_topics_for_week("aipm", 1)[0]

    response = client.post("/topic/notes", json={
        "session_id": session_id,
        "topic_id":   topic.topic_id,
        "reflection": "Good notes.",
    })

    assert response.status_code == 200
    data = response.json()
    assert "completion_percent" in data
    assert isinstance(data["completion_percent"], int)


def test_topic_notes_marks_reflection_done_when_nonempty():
    session_id = _start_session()
    topic = get_topics_for_week("aipm", 1)[0]

    response = client.post("/topic/notes", json={
        "session_id": session_id,
        "topic_id":   topic.topic_id,
        "reflection": "Something insightful.",
    })

    assert response.status_code == 200
    data = response.json()
    assert data["topic_progress"]["reflection"] == "done"
    # 1 of 5 steps done = 20%
    assert data["completion_percent"] == 20


def test_topic_notes_does_not_mark_done_when_all_empty():
    session_id = _start_session()
    topic = get_topics_for_week("aipm", 1)[0]

    response = client.post("/topic/notes", json={
        "session_id":       session_id,
        "topic_id":         topic.topic_id,
        "reflection":       "",
        "confusions":       "",
        "application_idea": "",
    })

    assert response.status_code == 200
    data = response.json()
    assert data["topic_progress"]["reflection"] != "done"


def test_topic_notes_invalid_topic_returns_404():
    session_id = _start_session()

    response = client.post("/topic/notes", json={
        "session_id": session_id,
        "topic_id":   "nonexistent-topic-xyz",
        "reflection": "Some reflection.",
    })

    assert response.status_code == 404


def test_topic_detail_renders_saved_notes():
    session_id = _start_session()
    topic = get_topics_for_week("aipm", 1)[0]

    # Save a note
    client.post("/topic/notes", json={
        "session_id": session_id,
        "topic_id":   topic.topic_id,
        "reflection": "This is my reflection.",
    })

    # Reload the detail page and check the note appears
    response = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert response.status_code == 200
    assert "This is my reflection." in response.text


def test_topic_detail_contains_reflection_form():
    session_id = _start_session()
    topic = get_topics_for_week("aipm", 1)[0]

    response = client.get(f"/topic/{session_id}/{topic.topic_id}")
    html = response.text

    assert response.status_code == 200
    assert "Save Reflection"          in html
    assert "What did you understand"  in html
    assert "What is still confusing"  in html
    assert "Where can you apply"      in html
    assert "/topic/notes"             in html
