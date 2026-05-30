"""Tests for moving core session persistence helpers into the service layer."""

from __future__ import annotations

import ast
import json
import os
from pathlib import Path

import pytest
from fastapi import HTTPException

os.environ["AI2_TEST_MODE"] = "1"
os.environ["ANTHROPIC_API_KEY"] = "test-key"

import app as app_module
import routes.deps as deps
from config import CareerTrack
from context.session import SessionContext
from services import session_persistence


APP = Path("app.py")
SERVICE = Path("services/session_persistence.py")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_source(path: Path, function_name: str) -> str:
    source = _read(path)
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            return ast.get_source_segment(source, node) or ""
    raise AssertionError(f"{function_name} not found in {path}")


def test_service_contains_core_session_helpers():
    source = _read(SERVICE)

    assert "def get_session_data(" in source
    assert "def save_session(" in source


def test_app_keeps_sessions_cache_and_thin_wrappers_only():
    app_source = _read(APP)
    get_wrapper = _function_source(APP, "_get_session_data")
    save_wrapper = _function_source(APP, "_save_session")

    assert "_sessions: dict[str, dict] = {}" in app_source
    assert "return get_session_data(" in get_wrapper
    assert "session_cache=_sessions" in get_wrapper
    assert "orchestrator_cls=Orchestrator" in get_wrapper
    assert "SELECT session_data FROM sessions" not in get_wrapper
    assert "Access denied." not in get_wrapper

    assert "return save_session(" in save_wrapper
    assert "INSERT INTO sessions" not in save_wrapper
    assert "_save_session failed" not in save_wrapper


def test_routes_deps_exposes_expected_session_callables():
    assert deps.get_session_data is app_module._get_session_data
    assert deps.save_session is app_module._save_session
    assert callable(deps.get_session_data)
    assert callable(deps.save_session)


def test_session_ownership_behavior_is_preserved_for_cache_hits():
    session = SessionContext(track=CareerTrack.AI_PM, user_id="user-a")
    cache = {"session-1": {"session": session, "orch": object(), "client": object(), "profile": None}}

    same_owner = session_persistence.get_session_data(
        "session-1",
        "user-a",
        session_cache=cache,
        test_mode=False,
    )
    assert same_owner is cache["session-1"]

    with pytest.raises(HTTPException) as exc_info:
        session_persistence.get_session_data(
            "session-1",
            "user-b",
            session_cache=cache,
            test_mode=False,
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Access denied."


def test_test_mode_preserves_cache_hit_ownership_bypass():
    session = SessionContext(track=CareerTrack.AI_PM, user_id="user-a")
    cache = {"session-1": {"session": session, "orch": object(), "client": object(), "profile": None}}

    data = session_persistence.get_session_data(
        "session-1",
        "user-b",
        session_cache=cache,
        test_mode=True,
    )

    assert data is cache["session-1"]


def test_db_unavailable_falls_back_to_session_not_found(monkeypatch):
    def broken_get_conn():
        raise RuntimeError("db unavailable")

    monkeypatch.setattr(session_persistence, "get_conn", broken_get_conn)

    with pytest.raises(HTTPException) as exc_info:
        session_persistence.get_session_data(
            "missing-session",
            "user-a",
            session_cache={},
            test_mode=False,
            make_client=lambda: object(),
            load_profile_db=lambda _user_id: None,
            orchestrator_cls=lambda **_kwargs: object(),
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Session 'missing-session' not found"


def test_db_restore_populates_cache_with_same_return_shape(monkeypatch):
    session = SessionContext(track=CareerTrack.AI_PM, user_id="user-a")
    row = (json.dumps(session.to_dict()),)
    executed = []

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, query, params):
            executed.append((query, params))

        def fetchone(self):
            return row

    class Conn:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def cursor(self):
            return Cursor()

    class FakeOrchestrator:
        def __init__(self, *, client, session, profile):
            self.client = client
            self.session = session
            self.profile = profile

    cache = {}
    client = object()
    profile = object()

    monkeypatch.setattr(session_persistence, "get_conn", lambda: Conn())

    data = session_persistence.get_session_data(
        "session-1",
        "user-a",
        session_cache=cache,
        test_mode=False,
        make_client=lambda: client,
        load_profile_db=lambda _user_id: profile,
        orchestrator_cls=FakeOrchestrator,
    )

    assert executed[0][1] == ("session-1", "user-a")
    assert data is cache["session-1"]
    assert data["session"].user_id == "user-a"
    assert data["client"] is client
    assert data["profile"] is profile
    assert isinstance(data["orch"], FakeOrchestrator)


def test_save_session_test_mode_does_not_touch_db(monkeypatch):
    def fail_get_conn():
        raise AssertionError("TEST_MODE save_session must not open DB connection")

    monkeypatch.setattr(session_persistence, "get_conn", fail_get_conn)

    session_persistence.save_session(
        "session-1",
        SessionContext(track=CareerTrack.AI_PM, user_id="user-a"),
        test_mode=True,
    )


def test_route_modules_still_use_dependency_wiring_for_session_helpers():
    route_sources = {
        "routes/onboarding.py": _read(Path("routes/onboarding.py")),
        "routes/dashboard.py": _read(Path("routes/dashboard.py")),
        "routes/chat.py": _read(Path("routes/chat.py")),
        "routes/syllabus.py": _read(Path("routes/syllabus.py")),
        "routes/topics.py": _read(Path("routes/topics.py")),
        "routes/todos.py": _read(Path("routes/todos.py")),
        "routes/submissions.py": _read(Path("routes/submissions.py")),
    }

    for path, source in route_sources.items():
        assert "deps.get_session_data" in source, path

    for path in (
        "routes/onboarding.py",
        "routes/chat.py",
        "routes/syllabus.py",
        "routes/topics.py",
        "routes/todos.py",
        "routes/submissions.py",
    ):
        assert "deps.save_session" in route_sources[path], path


def test_learner_route_urls_remain_registered():
    routes = {
        (route.path, ",".join(sorted(getattr(route, "methods", set()) or [])))
        for route in app_module.app.routes
        if hasattr(route, "methods")
    }

    expected = {
        ("/dashboard", "GET"),
        ("/session/start", "POST"),
        ("/chat", "POST"),
        ("/chat/{session_id}", "GET"),
        ("/onboarding/{session_id}", "GET"),
        ("/onboarding/save", "POST"),
        ("/syllabus/{session_id}", "GET"),
        ("/task/toggle", "POST"),
        ("/topics/{session_id}", "GET"),
        ("/topic/{session_id}/{topic_id}", "GET"),
        ("/topic/progress", "POST"),
        ("/todos/{session_id}", "GET"),
        ("/todos/create", "POST"),
        ("/todos/status", "POST"),
        ("/portfolio/submit", "POST"),
        ("/quiz/submit", "POST"),
        ("/interview/submit", "POST"),
    }

    assert expected <= routes
