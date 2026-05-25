"""Syllabus and task routes."""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

import routes.deps as deps
from curriculum.syllabus import (
    ROLE_TRACKS,
    WEEKS,
    get_progress as syllabus_get_progress,
    get_task_key,
)

router = APIRouter()


class TaskToggleRequest(BaseModel):
    session_id: str
    task_key: str
    status: str = "done"  # "done" | "in_progress" | "todo"


@router.get("/syllabus/{session_id}", response_class=HTMLResponse)
async def syllabus_page(request: Request, session_id: str):
    data = deps.get_session_data(session_id, request.state.user_id or "")
    session = data["session"]
    role = session.track.value

    phases_data = []
    for week in WEEKS:
        wn = week["num"]
        all_tasks = []
        role_done = role_total = 0
        for day in week["days"]:
            for ti, task_text in enumerate(day["all_tracks"]):
                key = get_task_key(wn, day["day_idx"], "all", ti)
                status = session.syllabus_progress.get(key, "todo")
                all_tasks.append({
                    "key": key,
                    "text": task_text,
                    "track_name": "All Tracks",
                    "status": status,
                    "roles": list(ROLE_TRACKS.keys()),
                    "is_my_role": True,
                })
                role_total += 1
                if status == "done":
                    role_done += 1
            role_tasks = day["tracks"].get(role, [])
            task_list = role_tasks if isinstance(role_tasks, list) else [role_tasks]
            for ti, task_text in enumerate(task_list):
                if not task_text:
                    continue
                key = get_task_key(wn, day["day_idx"], role, ti)
                status = session.syllabus_progress.get(key, "todo")
                all_tasks.append({
                    "key": key,
                    "text": task_text,
                    "track_name": ROLE_TRACKS[role]["label"],
                    "status": status,
                    "roles": [role],
                    "is_my_role": True,
                })
                role_total += 1
                if status == "done":
                    role_done += 1
        if all_tasks:
            phases_data.append({
                "id": f"week-{wn}",
                "icon": "📅",
                "phase": f"Module {wn}",
                "weeks": week["week_hours"],
                "title": week["title"],
                "description": week["theme"],
                "tasks": all_tasks,
                "done": role_done,
                "total": role_total,
                "pct": round(role_done / role_total * 100) if role_total > 0 else 0,
            })

    overall = syllabus_get_progress(session.syllabus_progress, [role])

    return deps.templates.TemplateResponse(
        request=request,
        name="syllabus.html",
        context={
            "session_id": session_id,
            "progress": deps.session_progress(session),
            "phases": phases_data,
            "overall": overall,
            "test_mode": bool(deps.TEST_MODE),
            "user_role": role,
            "role_tracks": ROLE_TRACKS,
        },
    )


@router.post("/task/toggle")
async def task_toggle(request: Request, body: TaskToggleRequest):
    valid_statuses = {"done", "in_progress", "todo"}
    if body.status not in valid_statuses:
        raise HTTPException(status_code=422, detail=f"status must be one of {valid_statuses}")

    data = deps.get_session_data(body.session_id, request.state.user_id or "")
    session = data["session"]
    session.mark_task(body.task_key, body.status)
    deps.save_session(body.session_id, session)

    role = session.track.value
    overall = syllabus_get_progress(session.syllabus_progress, [role])
    return {
        "task_key": body.task_key,
        "status": body.status,
        "overall": overall,
        "tasks_done": session.tasks_done_count(),
    }
