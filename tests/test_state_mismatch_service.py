"""Tests for services/state_mismatch_service.py.

All tests use real SessionContext instances — no DB connection required.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from config import CareerTrack
from context.session import SessionContext
from services.state_mismatch_service import (
    compare_learner_state,
    compare_todos,
    compare_topic_progress,
)


# ── Session factory ───────────────────────────────────────────────────────────

def _session() -> SessionContext:
    return SessionContext(track=CareerTrack.AI_PM)


# ── compare_topic_progress: match ─────────────────────────────────────────────

def test_topic_progress_matches_when_all_fields_equal():
    session = _session()
    # All steps default to "not_started", completion_percent = 0
    db_progress = {
        "learn":               "not_started",
        "quiz":                "not_started",
        "portfolio_task":      "not_started",
        "interview_practice":  "not_started",
        "reflection":          "not_started",
        "completion_percent":  0,
        "legacy_topic_id":     "rag-basics",
    }

    result = compare_topic_progress(
        session=session,
        legacy_topic_id="rag-basics",
        db_progress=db_progress,
    )

    assert result["matches"] is True
    assert result["mismatches"] == []
    assert result["db_missing"] is False
    assert result["type"] == "topic_progress"
    assert result["legacy_topic_id"] == "rag-basics"


def test_topic_progress_matches_with_some_steps_done():
    session = _session()
    session.mark_topic_step("rag-basics", "learn", "done")
    session.mark_topic_step("rag-basics", "quiz", "done")

    db_progress = {
        "learn":               "done",
        "quiz":                "done",
        "portfolio_task":      "not_started",
        "interview_practice":  "not_started",
        "reflection":          "not_started",
        "completion_percent":  40,
    }

    result = compare_topic_progress(
        session=session,
        legacy_topic_id="rag-basics",
        db_progress=db_progress,
    )

    assert result["matches"] is True
    assert result["mismatches"] == []


# ── compare_topic_progress: mismatches ───────────────────────────────────────

def test_topic_progress_mismatch_for_one_status():
    session = _session()
    session.mark_topic_step("rag-basics", "learn", "done")

    db_progress = {
        "learn":               "not_started",   # differs
        "quiz":                "not_started",
        "portfolio_task":      "not_started",
        "interview_practice":  "not_started",
        "reflection":          "not_started",
        "completion_percent":  0,
    }

    result = compare_topic_progress(
        session=session,
        legacy_topic_id="rag-basics",
        db_progress=db_progress,
    )

    assert result["matches"] is False
    assert len(result["mismatches"]) >= 1
    mismatch_fields = [m["field"] for m in result["mismatches"]]
    assert "learn" in mismatch_fields

    learn_m = next(m for m in result["mismatches"] if m["field"] == "learn")
    assert learn_m["session_value"] == "done"
    assert learn_m["db_value"] == "not_started"


def test_topic_progress_mismatch_for_completion_percent():
    session = _session()
    session.mark_topic_step("rag-basics", "learn", "done")
    session.mark_topic_step("rag-basics", "quiz", "done")
    # session completion = 40%

    db_progress = {
        "learn":               "done",
        "quiz":                "done",
        "portfolio_task":      "not_started",
        "interview_practice":  "not_started",
        "reflection":          "not_started",
        "completion_percent":  20,   # stale — should be 40
    }

    result = compare_topic_progress(
        session=session,
        legacy_topic_id="rag-basics",
        db_progress=db_progress,
    )

    assert result["matches"] is False
    pct_m = next((m for m in result["mismatches"] if m["field"] == "completion_percent"), None)
    assert pct_m is not None
    assert pct_m["session_value"] == 40
    assert pct_m["db_value"] == 20


def test_topic_progress_session_snapshot_reflects_actual_session():
    session = _session()
    session.mark_topic_step("rag-basics", "learn", "in_progress")

    db_progress = {
        "learn":              "not_started",
        "completion_percent": 0,
    }

    result = compare_topic_progress(
        session=session,
        legacy_topic_id="rag-basics",
        db_progress=db_progress,
    )

    assert result["session_snapshot"]["learn"] == "in_progress"
    assert result["session_snapshot"]["completion_percent"] == 0


# ── compare_topic_progress: db_missing ───────────────────────────────────────

def test_topic_progress_db_missing_true_when_db_progress_none():
    result = compare_topic_progress(
        session=_session(),
        legacy_topic_id="rag-basics",
        db_progress=None,
    )

    assert result["db_missing"] is True
    assert result["matches"] is False
    assert result["db_snapshot"] is None
    assert result["session_snapshot"] is not None


# ── compare_todos: match ──────────────────────────────────────────────────────

def test_todos_match_when_same_ids_and_statuses():
    session = _session()
    todo = session.add_todo("Read the RAG paper", todo_type="daily")
    todo_id = todo["todo_id"]

    db_todos = [
        {
            "todo_id":         todo_id,
            "title":           "Read the RAG paper",
            "todo_type":       "daily",
            "status":          "todo",
            "linked_topic_id": "",
        }
    ]

    result = compare_todos(session=session, db_todos=db_todos)

    assert result["matches"] is True
    assert result["mismatches"] == []
    assert result["db_missing"] is False
    assert result["session_count"] == 1
    assert result["db_count"] == 1


def test_todos_match_with_empty_session_and_empty_db():
    result = compare_todos(session=_session(), db_todos=[])

    assert result["matches"] is True
    assert result["mismatches"] == []
    assert result["session_count"] == 0
    assert result["db_count"] == 0


# ── compare_todos: mismatches ─────────────────────────────────────────────────

def test_todos_mismatch_when_count_differs():
    session = _session()
    session.add_todo("Read paper", todo_type="daily")
    session.add_todo("Build demo", todo_type="weekly")

    db_todos = [
        {"todo_id": session.todos[0]["todo_id"], "title": "Read paper",
         "todo_type": "daily", "status": "todo", "linked_topic_id": ""}
    ]

    result = compare_todos(session=session, db_todos=db_todos)

    assert result["matches"] is False
    count_m = next((m for m in result["mismatches"] if m["field"] == "count"), None)
    assert count_m is not None
    assert count_m["session_value"] == 2
    assert count_m["db_value"] == 1


def test_todos_mismatch_when_missing_todo_id_in_db():
    session = _session()
    todo = session.add_todo("Read paper", todo_type="daily")

    db_todos = []  # DB has nothing

    result = compare_todos(session=session, db_todos=db_todos)

    assert result["matches"] is False
    presence_m = next(
        (m for m in result["mismatches"]
         if m["field"] == "todo_id_presence" and m.get("todo_id") == todo["todo_id"]),
        None,
    )
    assert presence_m is not None
    assert presence_m["session_value"] == "present"
    assert presence_m["db_value"] == "missing"


def test_todos_mismatch_when_status_differs():
    session = _session()
    todo = session.add_todo("Read paper", todo_type="daily")
    todo_id = todo["todo_id"]

    db_todos = [
        {
            "todo_id":         todo_id,
            "title":           "Read paper",
            "todo_type":       "daily",
            "status":          "done",   # session has "todo"
            "linked_topic_id": "",
        }
    ]

    result = compare_todos(session=session, db_todos=db_todos)

    assert result["matches"] is False
    status_m = next(
        (m for m in result["mismatches"]
         if m["field"] == "status" and m.get("todo_id") == todo_id),
        None,
    )
    assert status_m is not None
    assert status_m["session_value"] == "todo"
    assert status_m["db_value"] == "done"


def test_todos_mismatch_when_db_has_extra_todo_not_in_session():
    session = _session()

    db_todos = [
        {
            "todo_id":         "ghost-todo-99",
            "title":           "Orphan todo",
            "todo_type":       "daily",
            "status":          "todo",
            "linked_topic_id": "",
        }
    ]

    result = compare_todos(session=session, db_todos=db_todos)

    assert result["matches"] is False
    presence_m = next(
        (m for m in result["mismatches"]
         if m["field"] == "todo_id_presence" and m.get("todo_id") == "ghost-todo-99"),
        None,
    )
    assert presence_m is not None
    assert presence_m["session_value"] == "missing"
    assert presence_m["db_value"] == "present"


# ── compare_todos: db_missing ─────────────────────────────────────────────────

def test_todos_db_missing_true_when_db_todos_none():
    session = _session()
    session.add_todo("Read paper", todo_type="daily")

    result = compare_todos(session=session, db_todos=None)

    assert result["db_missing"] is True
    assert result["matches"] is False
    assert result["db_count"] is None
    assert result["session_count"] == 1
    assert result["type"] == "todos"


# ── compare_learner_state ─────────────────────────────────────────────────────

def test_compare_learner_state_combines_progress_and_todos():
    session = _session()
    session.mark_topic_step("rag-basics", "learn", "done")
    todo = session.add_todo("Read paper", todo_type="daily")

    db_progress = {
        "learn":               "done",
        "quiz":                "not_started",
        "portfolio_task":      "not_started",
        "interview_practice":  "not_started",
        "reflection":          "not_started",
        "completion_percent":  20,
    }
    db_todos = [
        {
            "todo_id":         todo["todo_id"],
            "title":           "Read paper",
            "todo_type":       "daily",
            "status":          "todo",
            "linked_topic_id": "",
        }
    ]

    result = compare_learner_state(
        session=session,
        legacy_topic_id="rag-basics",
        db_progress=db_progress,
        db_todos=db_todos,
    )

    types = [c["type"] for c in result["comparisons"]]
    assert "topic_progress" in types
    assert "todos" in types
    assert len(result["comparisons"]) == 2


def test_compare_learner_state_without_legacy_topic_id_only_compares_todos():
    session = _session()
    session.add_todo("Build demo", todo_type="weekly")

    db_todos = [
        {
            "todo_id":         session.todos[0]["todo_id"],
            "title":           "Build demo",
            "todo_type":       "weekly",
            "status":          "todo",
            "linked_topic_id": "",
        }
    ]

    result = compare_learner_state(
        session=session,
        legacy_topic_id=None,
        db_progress=None,
        db_todos=db_todos,
    )

    types = [c["type"] for c in result["comparisons"]]
    assert types == ["todos"]
    assert len(result["comparisons"]) == 1


def test_compare_learner_state_matches_true_when_all_match():
    session = _session()
    todo = session.add_todo("Read paper", todo_type="daily")

    db_todos = [
        {
            "todo_id":         todo["todo_id"],
            "title":           "Read paper",
            "todo_type":       "daily",
            "status":          "todo",
            "linked_topic_id": "",
        }
    ]

    result = compare_learner_state(
        session=session,
        db_todos=db_todos,
    )

    assert result["matches"] is True


def test_compare_learner_state_matches_false_when_any_mismatch():
    session = _session()

    # DB has no todos but session has one
    session.add_todo("Read paper", todo_type="daily")

    result = compare_learner_state(
        session=session,
        db_todos=[],
    )

    assert result["matches"] is False


# ── Security / source constraints ─────────────────────────────────────────────

def test_service_does_not_import_database_pool():
    source = Path("services/state_mismatch_service.py").read_text(encoding="utf-8")

    assert "database.pool" not in source
    assert "from database" not in source
    assert "import database" not in source


def test_service_does_not_read_os_environ():
    source = Path("services/state_mismatch_service.py").read_text(encoding="utf-8")

    assert "import os" not in source
    assert "os.environ" not in source
    assert "os.getenv" not in source
