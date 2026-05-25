"""
Verifies that the onboarding routes split was done correctly:
- routes/onboarding.py exists and defines an APIRouter
- the moved routes/helpers are no longer defined directly in app.py
- app.py includes the onboarding router
- route URLs are unchanged
- enrollment best-effort behavior is preserved in the new module
- no other routes were accidentally moved

Documentation-style static checks — no HTTP calls, no server startup.
Runtime behavior tested by test_onboarding_flow.py and test_onboarding_course_enrollment.py.
"""

import os

APP_PATH        = os.path.join(os.path.dirname(__file__), "..", "app.py")
ONBOARDING_PATH = os.path.join(os.path.dirname(__file__), "..", "routes", "onboarding.py")


def _app() -> str:
    with open(APP_PATH, encoding="utf-8") as f:
        return f.read()


def _onb() -> str:
    with open(ONBOARDING_PATH, encoding="utf-8") as f:
        return f.read()


# ── routes/onboarding.py exists and is valid ─────────────────────────────────

def test_onboarding_routes_file_exists():
    """routes/onboarding.py exists."""
    assert os.path.isfile(ONBOARDING_PATH), f"Not found: {ONBOARDING_PATH}"


def test_onboarding_routes_defines_api_router():
    """routes/onboarding.py creates an APIRouter instance named router."""
    src = _onb()
    assert "APIRouter" in src
    assert "router = APIRouter()" in src


def test_onboarding_routes_imports_deps():
    """routes/onboarding.py imports routes.deps for shared helpers."""
    assert "import routes.deps as deps" in _onb()


def test_onboarding_routes_has_no_orchestrator_imports():
    """routes/onboarding.py does not import orchestrator or agents."""
    src = _onb()
    assert "Orchestrator" not in src
    assert "import agents" not in src
    assert "import anthropic" not in src


# ── Route definitions in routes/onboarding.py ────────────────────────────────

def test_onboarding_py_defines_onboarding_page():
    """routes/onboarding.py defines GET /onboarding/{session_id}."""
    src = _onb()
    assert '@router.get("/onboarding/{session_id}"' in src
    assert "async def onboarding_page" in src


def test_onboarding_py_defines_onboarding_save():
    """routes/onboarding.py defines POST /onboarding/save."""
    src = _onb()
    assert '@router.post("/onboarding/save")' in src
    assert "async def onboarding_save" in src


def test_onboarding_py_uses_deps_get_session_data():
    """routes/onboarding.py uses deps.get_session_data (not a direct _get_session_data call)."""
    src = _onb()
    assert "deps.get_session_data" in src
    assert "_get_session_data" not in src


def test_onboarding_py_uses_deps_save_session():
    """routes/onboarding.py uses deps.save_session (not a direct _save_session call)."""
    src = _onb()
    assert "deps.save_session" in src
    assert "_save_session" not in src


def test_onboarding_py_uses_deps_templates():
    """routes/onboarding.py uses deps.templates.TemplateResponse."""
    assert "deps.templates.TemplateResponse" in _onb()


def test_onboarding_py_renders_onboarding_html():
    """routes/onboarding.py renders onboarding.html template."""
    assert "onboarding.html" in _onb()


def test_onboarding_py_redirects_to_topics_after_save():
    """routes/onboarding.py redirects to /topics/{session_id} after successful save."""
    src = _onb()
    assert "/topics/" in src
    assert "RedirectResponse" in src


def test_onboarding_py_handles_value_error_with_422():
    """routes/onboarding.py re-renders form with 422 on ValueError."""
    src = _onb()
    assert "ValueError" in src
    assert "422" in src


# ── Onboarding-specific helpers moved ────────────────────────────────────────

def test_onboarding_py_has_template_context_helper():
    """routes/onboarding.py includes _onboarding_template_context helper."""
    assert "_onboarding_template_context" in _onb()


def test_onboarding_py_template_context_uses_deps_test_mode():
    """_onboarding_template_context uses deps.TEST_MODE (not a bare TEST_MODE reference)."""
    src = _onb()
    assert "deps.TEST_MODE" in src
    assert '"test_mode": bool(deps.TEST_MODE)' in src or "bool(deps.TEST_MODE)" in src


def test_onboarding_py_has_enrollment_helper():
    """routes/onboarding.py includes _ensure_onboarding_course_enrollment helper."""
    assert "_ensure_onboarding_course_enrollment" in _onb()


def test_onboarding_py_enrollment_is_best_effort():
    """_ensure_onboarding_course_enrollment swallows exceptions (best-effort)."""
    src = _onb()
    assert "except Exception" in src
    assert "logger.warning" in src


def test_onboarding_py_enrollment_uses_get_conn():
    """_ensure_onboarding_course_enrollment uses get_conn from database.pool."""
    src = _onb()
    assert "get_conn" in src
    assert "from database.pool import get_conn" in src


def test_onboarding_py_enrollment_uses_ensure_course_enrollment():
    """_ensure_onboarding_course_enrollment calls ensure_course_enrollment service."""
    src = _onb()
    assert "ensure_course_enrollment" in src
    assert "from services.learner_course_enrollment_service import ensure_course_enrollment" in src


# ── app.py no longer defines the moved routes ────────────────────────────────

def test_app_py_no_longer_defines_onboarding_page():
    """app.py does not contain @app.get('/onboarding/{session_id}')."""
    assert '@app.get("/onboarding/{session_id}"' not in _app()


def test_app_py_no_longer_defines_onboarding_save():
    """app.py does not contain @app.post('/onboarding/save')."""
    assert '@app.post("/onboarding/save")' not in _app()


def test_app_py_no_longer_has_onboarding_template_context():
    """app.py no longer defines _onboarding_template_context."""
    assert "def _onboarding_template_context(" not in _app()


def test_app_py_no_longer_has_ensure_onboarding_enrollment():
    """app.py no longer defines _ensure_onboarding_course_enrollment."""
    assert "def _ensure_onboarding_course_enrollment(" not in _app()


# ── app.py includes the onboarding router ────────────────────────────────────

def test_app_py_imports_onboarding_router():
    """app.py imports onboarding_router from routes.onboarding."""
    src = _app()
    assert "from routes.onboarding import" in src
    assert "onboarding_router" in src


def test_app_py_includes_onboarding_router():
    """app.py calls app.include_router(onboarding_router)."""
    assert "app.include_router(onboarding_router)" in _app()


# ── Route URLs unchanged ──────────────────────────────────────────────────────

def test_onboarding_page_url_unchanged():
    """/onboarding/{session_id} URL is preserved exactly."""
    assert '"/onboarding/{session_id}"' in _onb()


def test_onboarding_save_url_unchanged():
    """/onboarding/save URL is preserved exactly."""
    assert '"/onboarding/save"' in _onb()


# ── No other routes accidentally moved ───────────────────────────────────────

def test_app_py_still_has_dashboard_route():
    """app.py still defines /dashboard — was not accidentally moved."""
    assert '@app.get("/dashboard"' in _app()


def test_app_py_still_has_history_route():
    """app.py still defines /history — was not accidentally moved."""
    assert '@app.get("/history"' in _app()


def test_app_py_still_has_debug_route():
    """app.py still defines debug routes — debug routes not moved."""
    assert '@app.get("/debug/storage-status")' in _app()


def test_app_py_still_has_chat_route():
    """app.py still defines POST /chat — chat route not moved."""
    assert '@app.post("/chat")' in _app()


def test_app_py_still_has_syllabus_route():
    """app.py still defines /syllabus — syllabus route not moved."""
    assert '@app.get("/syllabus/{session_id}"' in _app()
