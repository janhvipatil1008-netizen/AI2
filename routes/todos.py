"""Todo-related routes: /todos/{session_id}, /todos/create, /todos/status."""

import os

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional

from curriculum.topics import get_topic
from services.todo_context_service import build_todo_learning_context

import routes.deps as deps

router = APIRouter()


def _compute_todo_counts(todos: list) -> dict:
    """Mirror of SessionContext.todo_counts() for a plain list."""
    counts: dict = {"total": 0, "todo": 0, "in_progress": 0, "done": 0}
    for t in todos:
        counts["total"] += 1
        status = t.get("status", "todo")
        counts[status] = counts.get(status, 0) + 1
    return counts

TEST_MODE = os.getenv("AI2_TEST_MODE") == "1"


# ── Pydantic models ───────────────────────────────────────────────────────────

class TodoCreateRequest(BaseModel):
    session_id:      str
    title:           str
    todo_type:       str = "daily"
    linked_topic_id: Optional[str] = None
    due_label:       Optional[str] = None


class TodoStatusRequest(BaseModel):
    session_id: str
    todo_id:    str
    status:     str


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/todos/{session_id}", response_class=HTMLResponse)
async def todos_page(request: Request, session_id: str):
    data    = deps.get_session_data(session_id, request.state.user_id or "")
    session = data["session"]
    todos   = deps.read_todos_with_fallback(
        session,
        session_id=session_id,
        user_id=request.state.user_id,
    )
    modular_progress = deps.read_modular_progress_summary_safely(
        session,
        user_id=request.state.user_id,
        session_id=session_id,
    )
    todo_learning_context = build_todo_learning_context(
        modular_progress_summary=modular_progress,
        session=session,
    )
    return deps.templates.TemplateResponse(
        request=request,
        name="todos.html",
        context={
            "session_id":              session_id,
            "daily_todos":             [t for t in todos if t.get("todo_type") == "daily"],
            "weekly_todos":            [t for t in todos if t.get("todo_type") == "weekly"],
            "todo_counts":             _compute_todo_counts(todos),
            "progress":                deps.session_progress(session),
            "todo_learning_context":   todo_learning_context,
            "test_mode":               bool(TEST_MODE),
        },
    )


@router.post("/todos/create")
async def create_todo(request: Request, body: TodoCreateRequest):
    if not body.title.strip():
        raise HTTPException(status_code=422, detail="title cannot be empty")

    data    = deps.get_session_data(body.session_id, request.state.user_id or "")
    session = data["session"]

    if body.linked_topic_id:
        if get_topic(session.track.value, body.linked_topic_id) is None:
            raise HTTPException(status_code=404, detail="linked_topic_id not found")

    try:
        todo = session.add_todo(
            title=body.title,
            todo_type=body.todo_type,
            linked_topic_id=body.linked_topic_id,
            created_by="learner",
            due_label=body.due_label,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    deps.save_session(body.session_id, session)
    deps.write_through_todos(
        session,
        session_id=body.session_id,
        user_id=request.state.user_id or None,
    )
    return {"todo": todo, "todo_counts": session.todo_counts()}


@router.post("/todos/status")
async def update_todo_status_endpoint(request: Request, body: TodoStatusRequest):
    data    = deps.get_session_data(body.session_id, request.state.user_id or "")
    session = data["session"]

    try:
        todo = session.update_todo_status(body.todo_id, body.status)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    if todo is None:
        raise HTTPException(status_code=404, detail=f"Todo '{body.todo_id}' not found")

    deps.save_session(body.session_id, session)
    deps.write_through_todos(
        session,
        session_id=body.session_id,
        user_id=request.state.user_id or None,
    )
    return {"todo": todo, "todo_counts": session.todo_counts()}
