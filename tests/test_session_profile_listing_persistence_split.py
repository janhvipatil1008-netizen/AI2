from pathlib import Path
import asyncio
import os

os.environ["AI2_TEST_MODE"] = "1"
os.environ["ANTHROPIC_API_KEY"] = "test-key"

import app as app_module
import routes.deps as deps
import routes.dashboard as dashboard_routes
from config import CareerTrack
from context.learner_profile import LearnerProfile
from context.session import SessionContext


APP = Path("app.py")
SERVICE = Path("services/session_persistence.py")
DEPS = Path("routes/deps.py")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_session_persistence_service_contains_profile_and_listing_helpers():
    source = _read(SERVICE)

    assert "def get_user_sessions(" in source
    assert "def load_profile_db(" in source
    assert "def save_profile_db(" in source


def test_app_no_longer_directly_defines_profile_and_listing_helpers():
    source = _read(APP)

    assert "def _get_user_sessions(" not in source
    assert "def _load_profile_db(" not in source
    assert "def _save_profile_db(" not in source
    assert "from services.session_persistence import" in source


def test_core_session_helpers_remain_in_app():
    source = _read(APP)

    assert "_sessions: dict[str, dict] = {}" in source
    assert "def _get_session_data(" in source
    assert "def _save_session(" in source


def test_routes_deps_preserves_expected_dependency_callables():
    deps_source = _read(DEPS)
    app_source = _read(APP)

    assert "get_user_sessions: Callable = None" in deps_source
    assert "load_profile_db:  Callable = None" in deps_source
    assert "save_profile_db: Callable = None" in deps_source
    assert "_rdeps.get_user_sessions = _get_user_sessions" in app_source
    assert "_rdeps.load_profile_db  = _load_profile_db" in app_source
    assert "_rdeps.save_profile_db = _save_profile_db" in app_source

    assert callable(deps.get_user_sessions)
    assert callable(deps.load_profile_db)
    assert callable(deps.save_profile_db)


def test_get_user_sessions_return_shape_order_and_bad_row_fallback(monkeypatch):
    from services import session_persistence

    rows = [
        ("session-new", '{"track": "aipm", "current_week": 3}', "2026-01-03"),
        ("session-bad", "{bad-json", "2026-01-02"),
        ("session-old", '{"track": "evals"}', "2026-01-01"),
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

    sessions = session_persistence.get_user_sessions("user-1", limit=2, test_mode=False)

    assert sessions == [
        {
            "session_id": "session-new",
            "track": "aipm",
            "current_week": 3,
            "updated_at": "2026-01-03",
        },
        {
            "session_id": "session-old",
            "track": "evals",
            "current_week": 1,
            "updated_at": "2026-01-01",
        },
    ]
    assert "WHERE user_id = %s ORDER BY updated_at DESC LIMIT %s" in executed[0][0]
    assert executed[0][1] == ("user-1", 2)


def test_profile_load_save_fallback_behavior_is_preserved(monkeypatch):
    from services import session_persistence

    profile = LearnerProfile.new_for_user("user-1", CareerTrack.AI_PM)
    calls = []

    class Conn:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(session_persistence, "get_conn", lambda: Conn())
    monkeypatch.setattr(
        session_persistence,
        "load_profile",
        lambda user_id, conn: calls.append(("load", user_id, conn)) or profile,
    )
    monkeypatch.setattr(
        session_persistence,
        "save_profile",
        lambda saved_profile, conn: calls.append(("save", saved_profile.user_id, conn)),
    )

    assert session_persistence.load_profile_db("user-1", test_mode=False) is profile
    session_persistence.save_profile_db(profile, test_mode=False)
    assert [call[:2] for call in calls] == [("load", "user-1"), ("save", "user-1")]

    def raise_db_error():
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(session_persistence, "get_conn", raise_db_error)
    assert session_persistence.load_profile_db("user-1", test_mode=False) is None
    session_persistence.save_profile_db(profile, test_mode=False)


def test_test_mode_behavior_is_preserved(monkeypatch):
    from services import session_persistence

    def fail_if_called():
        raise AssertionError("get_conn should not be called in TEST_MODE")

    monkeypatch.setattr(session_persistence, "get_conn", fail_if_called)
    profile = LearnerProfile.new_for_user("user-1", CareerTrack.AI_PM)

    assert session_persistence.get_user_sessions("user-1", test_mode=True) == []
    assert session_persistence.get_user_sessions("", test_mode=False) == []
    assert session_persistence.load_profile_db("user-1", test_mode=True) is None
    assert session_persistence.load_profile_db("", test_mode=False) is None
    session_persistence.save_profile_db(profile, test_mode=True)


def test_dashboard_session_listing_and_profile_dependency_behavior_is_unchanged(monkeypatch):
    session = SessionContext(
        track=CareerTrack.AI_PM,
        user_id="user-1",
        current_week=3,
    )
    profile = LearnerProfile.new_for_user("user-1", CareerTrack.AI_PM)
    profile.session_count = 4
    profile.total_quizzes = 5
    profile.topics_mastered = {"rag"}
    profile.total_exchanges = 6

    calls = []

    def fake_get_user_sessions(user_id: str, limit: int = 10):
        calls.append(("get_user_sessions", user_id, limit))
        return [
            {
                "session_id": "session-new",
                "track": "aipm",
                "current_week": 3,
                "updated_at": "2026-01-03",
            }
        ]

    def fake_load_profile_db(user_id: str):
        calls.append(("load_profile_db", user_id))
        return profile

    def fake_get_session_data(session_id: str, user_id: str = ""):
        calls.append(("get_session_data", session_id, user_id))
        return {"session": session, "orch": None, "client": None, "profile": profile}

    class State:
        user_id = "user-1"

    class Request:
        state = State()

    class Templates:
        def TemplateResponse(self, *, request, name, context):
            return {"request": request, "name": name, "context": context}

    monkeypatch.setattr(deps, "get_user_sessions", fake_get_user_sessions)
    monkeypatch.setattr(deps, "load_profile_db", fake_load_profile_db)
    monkeypatch.setattr(deps, "get_session_data", fake_get_session_data)
    monkeypatch.setattr(deps, "templates", Templates())
    monkeypatch.setattr(deps, "TEST_MODE", True)
    monkeypatch.setattr(
        dashboard_routes,
        "_dashboard_db_summaries",
        lambda **kwargs: (
            {
                "source": "disabled",
                "course_key": "aipm-foundations",
                "status": "active",
                "progress_percent": 0,
                "current_module_key": None,
                "current_topic_key": None,
                "current_legacy_topic_id": None,
                "error": None,
            },
            {
                "source": "disabled",
                "available": False,
                "progress_percent": 0,
                "modules": [],
                "topics": [],
                "error": None,
            },
        ),
    )

    response = asyncio.run(dashboard_routes.dashboard(Request()))
    context = response["context"]

    assert calls == [
        ("get_user_sessions", "user-1", 5),
        ("load_profile_db", "user-1"),
        ("get_session_data", "session-new", "user-1"),
    ]
    assert context["recent_sessions"][0]["session_id"] == "session-new"
    assert context["recent_session_id"] == "session-new"
    assert context["stats"] == {
        "session_count": 4,
        "total_quizzes": 5,
        "topics_mastered": 1,
        "total_exchanges": 6,
    }


def test_app_dependency_wiring_uses_service_functions_without_moving_core_helpers():
    from services import session_persistence

    assert app_module._get_user_sessions.func is session_persistence.get_user_sessions
    assert app_module._load_profile_db.func is session_persistence.load_profile_db
    assert app_module._save_profile_db.func is session_persistence.save_profile_db
    assert hasattr(app_module, "_get_session_data")
    assert hasattr(app_module, "_save_session")
    assert hasattr(app_module, "_sessions")
