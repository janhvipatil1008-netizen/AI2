"""
Verifies that the public routes split was done correctly:
- routes/public.py exists and defines an APIRouter
- the four moved routes are no longer defined directly in app.py
- app.py includes the public router
- runtime behavior of /health, /privacy, /terms, / is preserved

Documentation-style static checks — no HTTP calls, no server startup.
Runtime behavior tested via the existing test_navigation.py and
test_privacy_terms_pages.py suites.
"""

import ast
import os
import re

APP_PATH     = os.path.join(os.path.dirname(__file__), "..", "app.py")
PUBLIC_PATH  = os.path.join(os.path.dirname(__file__), "..", "routes", "public.py")


def _app() -> str:
    with open(APP_PATH, encoding="utf-8") as f:
        return f.read()


def _pub() -> str:
    with open(PUBLIC_PATH, encoding="utf-8") as f:
        return f.read()


# ── routes/public.py exists and is valid ─────────────────────────────────────

def test_public_routes_file_exists():
    """routes/public.py exists."""
    assert os.path.isfile(PUBLIC_PATH), f"Not found: {PUBLIC_PATH}"


def test_public_routes_defines_api_router():
    """routes/public.py creates an APIRouter instance named router."""
    src = _pub()
    assert "APIRouter" in src
    assert "router = APIRouter()" in src


def test_public_routes_imports_deps():
    """routes/public.py imports routes.deps for TEST_MODE and templates."""
    assert "import routes.deps as deps" in _pub()


def test_public_routes_has_no_db_imports():
    """routes/public.py does not import database or session helpers."""
    src = _pub()
    assert "get_conn" not in src
    assert "_get_session_data" not in src
    assert "_save_session" not in src
    assert "SessionContext" not in src


def test_public_routes_has_no_orchestrator_imports():
    """routes/public.py does not import orchestrator or agents."""
    src = _pub()
    assert "Orchestrator" not in src
    assert "import agents" not in src
    assert "anthropic" not in src


# ── Route definitions in routes/public.py ────────────────────────────────────

def test_public_py_defines_health():
    """routes/public.py defines GET /health."""
    src = _pub()
    assert '@router.get("/health")' in src
    assert "async def health()" in src


def test_public_py_health_returns_test_mode():
    """routes/public.py /health returns deps.TEST_MODE."""
    src = _pub()
    assert "deps.TEST_MODE" in src


def test_public_py_defines_privacy():
    """routes/public.py defines GET /privacy."""
    assert '@router.get("/privacy"' in _pub()
    assert "async def privacy_page" in _pub()


def test_public_py_defines_terms():
    """routes/public.py defines GET /terms."""
    assert '@router.get("/terms"' in _pub()
    assert "async def terms_page" in _pub()


def test_public_py_defines_index():
    """routes/public.py defines GET /."""
    assert '@router.get("/"' in _pub()
    assert "async def index" in _pub()


def test_public_py_privacy_uses_deps_templates():
    """routes/public.py privacy_page uses deps.templates.TemplateResponse."""
    src = _pub()
    assert "deps.templates.TemplateResponse" in src
    assert "privacy.html" in src


def test_public_py_terms_uses_deps_templates():
    """routes/public.py terms_page uses deps.templates.TemplateResponse."""
    src = _pub()
    assert "deps.templates.TemplateResponse" in src
    assert "terms.html" in src


def test_public_py_index_redirects_to_dashboard_or_login():
    """routes/public.py index redirects to /dashboard or /login."""
    src = _pub()
    assert "/dashboard" in src
    assert "/login" in src
    assert "RedirectResponse" in src


# ── app.py no longer defines the moved routes ────────────────────────────────

def test_app_py_no_longer_defines_health_route():
    """app.py does not contain @app.get('/health')."""
    assert '@app.get("/health")' not in _app()


def test_app_py_no_longer_defines_privacy_route():
    """app.py does not contain @app.get('/privacy')."""
    assert '@app.get("/privacy"' not in _app()


def test_app_py_no_longer_defines_terms_route():
    """app.py does not contain @app.get('/terms')."""
    assert '@app.get("/terms"' not in _app()


def test_app_py_no_longer_defines_index_route():
    """app.py does not contain @app.get('/') (the index handler)."""
    assert '@app.get("/")' not in _app()


# ── app.py includes the public router ────────────────────────────────────────

def test_app_py_imports_public_router():
    """app.py imports public_router from routes.public."""
    src = _app()
    assert "from routes.public import" in src
    assert "public_router" in src


def test_app_py_includes_public_router():
    """app.py calls app.include_router(public_router)."""
    assert "app.include_router(public_router)" in _app()


def test_app_py_public_router_included_after_deps_wiring():
    """public_router is included after _rdeps.TEST_MODE is set (so deps.TEST_MODE is correct)."""
    src = _app()
    deps_pos   = src.find("_rdeps.TEST_MODE")
    public_pos = src.find("from routes.public import")
    assert deps_pos < public_pos, (
        "routes/public.py is imported before _rdeps.TEST_MODE is set — "
        "deps.TEST_MODE will be False at import time but that is fine; "
        "however the import should come after the wiring block for clarity."
    )


# ── No other routes accidentally moved ───────────────────────────────────────

def test_app_py_includes_dashboard_router():
    """app.py includes dashboard router after dashboard route split."""
    src = _app()
    assert '@app.get("/dashboard"' not in src
    assert "from routes.dashboard import router as dashboard_router" in src
    assert "app.include_router(dashboard_router)" in src


def test_app_py_still_has_debug_route():
    """app.py still defines /debug/storage-status — debug routes not moved."""
    assert '@app.get("/debug/storage-status")' in _app()


def test_app_py_includes_onboarding_router():
    """app.py includes onboarding router after onboarding route split."""
    src = _app()
    assert '@app.get("/onboarding/' not in src
    assert "from routes.onboarding import router as onboarding_router" in src
    assert "app.include_router(onboarding_router)" in src


def test_app_py_includes_chat_router():
    """app.py includes chat router after chat route split."""
    src = _app()
    assert '@app.post("/chat")' not in src
    assert "from routes.chat import router as chat_router" in src
    assert "app.include_router(chat_router)" in src


# ── Route URLs not changed ────────────────────────────────────────────────────

def test_public_health_url_unchanged():
    """/health URL is preserved exactly."""
    assert '"/health"' in _pub()


def test_public_privacy_url_unchanged():
    """/privacy URL is preserved exactly."""
    assert '"/privacy"' in _pub()


def test_public_terms_url_unchanged():
    """/terms URL is preserved exactly."""
    assert '"/terms"' in _pub()


def test_public_index_url_unchanged():
    """/ URL is preserved exactly."""
    assert '"/"' in _pub()


# ── _PUBLIC_PATHS allowlist unchanged ────────────────────────────────────────

def test_public_paths_allowlist_still_in_app_py():
    """_PUBLIC_PATHS is still defined in app.py (auth middleware allowlist)."""
    src = _app()
    assert "_PUBLIC_PATHS" in src
    assert "/health" in src
    assert "/privacy" in src
    assert "/terms" in src
