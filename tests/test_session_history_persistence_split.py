from pathlib import Path
import asyncio

import pytest


APP = Path("app.py")
SERVICE = Path("services/session_persistence.py")
DEPS = Path("routes/deps.py")
CHAT = Path("routes/chat.py")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_session_persistence_service_exists_with_history_helpers():
    source = _read(SERVICE)
    assert SERVICE.exists()
    assert "def get_user_history(" in source
    assert "def save_exchange_to_history(" in source


def test_app_no_longer_directly_defines_history_helpers():
    source = _read(APP)
    assert "def _get_user_history(" not in source
    assert "def _save_exchange_to_history(" not in source
    assert "from services.session_persistence import" in source


def test_core_session_helpers_remain_in_app():
    source = _read(APP)
    assert "_sessions: dict[str, dict] = {}" in source
    assert "def _get_session_data(" in source
    assert "def _save_session(" in source


def test_routes_deps_preserves_chat_dependency_names():
    deps_source = _read(DEPS)
    app_source = _read(APP)
    chat_source = _read(CHAT)

    assert "get_user_history: Callable = None" in deps_source
    assert "save_exchange_to_history: Callable = None" in deps_source
    assert "_rdeps.get_user_history = _get_user_history" in app_source
    assert "_rdeps.save_exchange_to_history = _save_exchange_to_history" in app_source
    assert "deps.get_user_history(user_id, limit=200)" in chat_source
    assert "deps.save_exchange_to_history(" in chat_source


def test_get_user_history_return_shape_and_order_are_preserved(monkeypatch):
    from services import session_persistence

    rows = [
        ("s2", "newer user", "newer assistant", "learning_coach", "2026-01-02"),
        ("s1", "older user", "older assistant", "orchestrator", "2026-01-01"),
    ]
    executed = []

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, query, params):
            executed.append((query, params))

        def fetchall(self):
            return rows

    class Conn:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def cursor(self):
            return Cursor()

    monkeypatch.setattr(session_persistence, "get_conn", lambda: Conn())

    history = session_persistence.get_user_history("user-1", limit=2, test_mode=False)

    assert history == [
        {
            "session_id": "s2",
            "user_message": "newer user",
            "assistant_reply": "newer assistant",
            "agent_used": "learning_coach",
            "timestamp": "2026-01-02",
        },
        {
            "session_id": "s1",
            "user_message": "older user",
            "assistant_reply": "older assistant",
            "agent_used": "orchestrator",
            "timestamp": "2026-01-01",
        },
    ]
    assert "ORDER BY timestamp DESC LIMIT %s" in executed[0][0]
    assert executed[0][1] == ("user-1", 2)


def test_save_exchange_to_history_uses_same_insert_shape(monkeypatch):
    from services import session_persistence

    executed = []

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, query, params):
            executed.append((query, params))

    class Conn:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def cursor(self):
            return Cursor()

    monkeypatch.setattr(session_persistence, "get_conn", lambda: Conn())

    session_persistence.save_exchange_to_history(
        "user-1",
        "session-1",
        "hello",
        "hi",
        "learning_coach",
        test_mode=False,
    )

    query, params = executed[0]
    assert "INSERT INTO conversation_history" in query
    assert "(user_id, session_id, user_message, assistant_reply, agent_used, timestamp)" in query
    assert params[:5] == ("user-1", "session-1", "hello", "hi", "learning_coach")
    assert isinstance(params[5], str)


def test_db_unavailable_fallback_behavior_is_preserved(monkeypatch):
    from services import session_persistence

    def raise_db_error():
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(session_persistence, "get_conn", raise_db_error)

    assert session_persistence.get_user_history("user-1", test_mode=False) == []
    session_persistence.save_exchange_to_history(
        "user-1",
        "session-1",
        "hello",
        "hi",
        "learning_coach",
        test_mode=False,
    )


def test_test_mode_behavior_is_preserved(monkeypatch):
    from services import session_persistence

    def fail_if_called():
        raise AssertionError("get_conn should not be called in TEST_MODE")

    monkeypatch.setattr(session_persistence, "get_conn", fail_if_called)

    assert session_persistence.get_user_history("user-1", test_mode=True) == []
    assert session_persistence.get_user_history("", test_mode=False) == []
    session_persistence.save_exchange_to_history(
        "user-1",
        "session-1",
        "hello",
        "hi",
        "learning_coach",
        test_mode=True,
    )
    session_persistence.save_exchange_to_history(
        "",
        "session-1",
        "hello",
        "hi",
        "learning_coach",
        test_mode=False,
    )


def test_chat_history_route_uses_same_dependency_contract(monkeypatch):
    monkeypatch.setenv("AI2_TEST_MODE", "1")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    import app  # noqa: F401
    import routes.deps as deps
    import routes.chat as chat_routes

    calls = []

    def fake_get_user_history(user_id: str, limit: int = 200):
        calls.append((user_id, limit))
        return [
            {
                "session_id": "session-1",
                "user_message": "hello",
                "assistant_reply": "hi",
                "agent_used": "learning_coach",
                "timestamp": "2026-01-01",
            }
        ]

    class State:
        user_id = "user-1"

    class Request:
        state = State()

    class Templates:
        def TemplateResponse(self, *, request, name, context):
            return {"request": request, "name": name, "context": context}

    monkeypatch.setattr(deps, "get_user_history", fake_get_user_history)
    monkeypatch.setattr(deps, "templates", Templates())
    monkeypatch.setattr(deps, "TEST_MODE", False)

    response = asyncio.run(chat_routes.history_page(Request()))

    assert calls == [("user-1", 200)]
    assert response["name"] == "history.html"
    assert response["context"]["entries"][0]["session_id"] == "session-1"
