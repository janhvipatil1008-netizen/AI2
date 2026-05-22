import pytest

from config import CareerTrack
from context.session import SessionContext, VALID_TODO_TYPES, VALID_TODO_STATUSES


def test_session_default_todos_is_empty():
    session = SessionContext(track=CareerTrack.AI_PM)
    assert session.todos == []


def test_add_todo_creates_todo_with_required_fields():
    session = SessionContext(track=CareerTrack.AI_PM)
    todo = session.add_todo("Read the paper")
    assert todo["title"]      == "Read the paper"
    assert todo["todo_type"]  == "daily"
    assert todo["status"]     == "todo"
    assert todo["created_by"] == "learner"
    assert "todo_id"    in todo
    assert "created_at" in todo
    assert len(session.todos) == 1


def test_add_todo_weekly_type():
    session = SessionContext(track=CareerTrack.AI_PM)
    todo = session.add_todo("Build RAG pipeline", todo_type="weekly", due_label="Friday")
    assert todo["todo_type"] == "weekly"
    assert todo["due_label"] == "Friday"


def test_add_todo_invalid_type_raises():
    session = SessionContext(track=CareerTrack.AI_PM)
    with pytest.raises(ValueError):
        session.add_todo("Task", todo_type="monthly")


def test_update_todo_status_updates():
    session = SessionContext(track=CareerTrack.AI_PM)
    todo = session.add_todo("Task 1")
    result = session.update_todo_status(todo["todo_id"], "done")
    assert result is not None
    assert result["status"] == "done"
    # In-place: the list entry reflects the change
    assert session.todos[0]["status"] == "done"


def test_update_todo_status_invalid_status_raises():
    session = SessionContext(track=CareerTrack.AI_PM)
    todo = session.add_todo("Task 1")
    with pytest.raises(ValueError):
        session.update_todo_status(todo["todo_id"], "cancelled")


def test_update_todo_status_missing_id_returns_none():
    session = SessionContext(track=CareerTrack.AI_PM)
    result = session.update_todo_status("nonexistent-id", "done")
    assert result is None


def test_get_todos_no_filter_returns_all():
    session = SessionContext(track=CareerTrack.AI_PM)
    session.add_todo("Daily task",  todo_type="daily")
    session.add_todo("Weekly task", todo_type="weekly")
    assert len(session.get_todos()) == 2


def test_get_todos_filters_by_type():
    session = SessionContext(track=CareerTrack.AI_PM)
    session.add_todo("Daily task",  todo_type="daily")
    session.add_todo("Weekly task", todo_type="weekly")
    assert len(session.get_todos("daily"))  == 1
    assert len(session.get_todos("weekly")) == 1
    assert session.get_todos("daily")[0]["title"] == "Daily task"


def test_todo_counts():
    session = SessionContext(track=CareerTrack.AI_PM)
    session.add_todo("Task 1")
    session.add_todo("Task 2")
    t = session.add_todo("Task 3")
    session.update_todo_status(t["todo_id"], "done")
    counts = session.todo_counts()
    assert counts["total"]       == 3
    assert counts["todo"]        == 2
    assert counts["done"]        == 1
    assert counts["in_progress"] == 0


def test_todo_counts_empty_session():
    session = SessionContext(track=CareerTrack.AI_PM)
    counts = session.todo_counts()
    assert counts == {"total": 0, "todo": 0, "in_progress": 0, "done": 0}


def test_to_dict_from_dict_preserves_todos():
    session = SessionContext(track=CareerTrack.AI_PM)
    session.add_todo("My task", todo_type="weekly", due_label="Friday")
    restored = SessionContext.from_dict(session.to_dict())
    assert len(restored.todos) == 1
    assert restored.todos[0]["title"]     == "My task"
    assert restored.todos[0]["todo_type"] == "weekly"
    assert restored.todos[0]["due_label"] == "Friday"
    assert restored.todos[0]["status"]    == "todo"


def test_from_dict_missing_todos_defaults_to_empty():
    session = SessionContext(track=CareerTrack.AI_PM)
    d = session.to_dict()
    del d["todos"]
    restored = SessionContext.from_dict(d)
    assert restored.todos == []


def test_valid_constants_are_correct():
    assert "daily"   in VALID_TODO_TYPES
    assert "weekly"  in VALID_TODO_TYPES
    assert "todo"        in VALID_TODO_STATUSES
    assert "in_progress" in VALID_TODO_STATUSES
    assert "done"        in VALID_TODO_STATUSES
