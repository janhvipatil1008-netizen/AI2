"""
Tests that the app.py refactor audit document exists and contains
all required sections and content markers.

Documentation-only tests — no HTTP calls, no server, no API.
"""

import os

AUDIT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "docs", "ai2-app-py-refactor-audit.md"
)


def _text() -> str:
    with open(AUDIT_PATH, encoding="utf-8") as f:
        return f.read()


# ── Existence ─────────────────────────────────────────────────────────────────

def test_audit_doc_exists():
    """The refactor audit doc exists in docs/."""
    assert os.path.isfile(AUDIT_PATH), f"Audit doc not found at {AUDIT_PATH}"


def test_audit_doc_not_empty():
    assert len(_text()) > 1000


def test_audit_doc_title_correct():
    assert "# AI² app.py Refactor Audit" in _text()


# ── app.py responsibilities ───────────────────────────────────────────────────

def test_doc_mentions_app_py_responsibilities():
    """Doc has a section covering what app.py currently does."""
    assert "## 1. Current app.py Responsibilities" in _text()


def test_doc_mentions_auth_middleware():
    """Doc mentions the auth middleware as an app.py responsibility."""
    assert "auth_middleware" in _text() or "Authentication middleware" in _text()


def test_doc_mentions_session_cache():
    """Doc mentions the in-memory session cache."""
    text = _text().lower()
    assert "session" in text and ("cache" in text or "_sessions" in text)


def test_doc_mentions_session_persistence():
    """Doc mentions session persistence functions."""
    assert "_save_session" in _text() or "session persistence" in _text().lower()


# ── Target modules ────────────────────────────────────────────────────────────

def test_doc_mentions_routes_public_py():
    """Doc recommends routes/public.py as destination for public routes."""
    assert "routes/public.py" in _text()


def test_doc_mentions_routes_debug_py():
    """Doc recommends routes/debug.py as destination for debug routes."""
    assert "routes/debug.py" in _text()


def test_doc_mentions_routes_dashboard_py():
    """Doc recommends routes/dashboard.py as destination for dashboard route."""
    assert "routes/dashboard.py" in _text()


def test_doc_mentions_routes_auth_py():
    """Doc recommends routes/auth.py as destination for auth routes."""
    assert "routes/auth.py" in _text()


def test_doc_mentions_routes_chat_py():
    """Doc recommends routes/chat.py as destination for chat routes."""
    assert "routes/chat.py" in _text()


def test_doc_mentions_routes_syllabus_py():
    """Doc recommends routes/syllabus.py as destination for syllabus routes."""
    assert "routes/syllabus.py" in _text()


def test_doc_mentions_services_session_persistence():
    """Doc recommends services/session_persistence.py for session helper functions."""
    assert "services/session_persistence.py" in _text()


def test_doc_mentions_services_debug_response_utils():
    """Doc recommends services/debug_response_utils.py for debug helper functions."""
    assert "services/debug_response_utils.py" in _text()


# ── Risk areas ────────────────────────────────────────────────────────────────

def test_doc_mentions_auth_middleware_risk():
    """Doc calls out auth middleware / _PUBLIC_PATHS as a high-risk area."""
    text = _text()
    assert "_PUBLIC_PATHS" in text or "auth middleware" in text.lower()
    assert "risk" in text.lower() or "High" in text


def test_doc_mentions_get_session_data_risk():
    """Doc calls out _get_session_data as high risk due to ownership check."""
    assert "_get_session_data" in _text()


def test_doc_mentions_debug_token_protection():
    """Doc calls out debug token protection as a risk area."""
    text = _text().lower()
    assert "debug" in text and ("token" in text or "protection" in text or "_debug_access" in _text())


def test_doc_mentions_route_url_stability():
    """Doc explicitly lists route URL stability as a risk."""
    text = _text().lower()
    assert "route" in text and ("url" in text or "stability" in text)


def test_doc_mentions_template_context_variables():
    """Doc mentions template context variables as a risk area."""
    text = _text().lower()
    assert "template" in text and ("context" in text or "variable" in text)


# ── Split order ───────────────────────────────────────────────────────────────

def test_doc_has_split_order_section():
    assert "## 4. Split Order" in _text()


def test_doc_recommends_public_routes_as_first_split():
    """Doc recommends public routes (/, /health, /privacy, /terms) as first split."""
    text = _text()
    assert "/health" in text
    assert "/privacy" in text
    assert "/terms" in text
    # Should appear early in the split order section
    split_section = text[text.find("## 4. Split Order"):]
    assert "/health" in split_section or "public" in split_section.lower()


def test_doc_mentions_chat_routes_as_high_risk_split():
    """Doc identifies chat routes as high risk to move."""
    text = _text()
    assert "/chat" in text
    assert "High" in text


# ── Next implementation step ──────────────────────────────────────────────────

def test_doc_has_next_implementation_step():
    assert "## 7. Next Implementation Step" in _text()


def test_doc_next_step_is_public_routes():
    """Next implementation step targets /, /health, /privacy, /terms."""
    next_section = _text()[_text().find("## 7. Next Implementation Step"):]
    assert "/health" in next_section
    assert "/privacy" in next_section
    assert "/terms" in next_section


def test_doc_next_step_explains_why_safe():
    """Next step section explains why public routes are the safest first slice."""
    next_section = _text()[_text().find("## 7. Next Implementation Step"):].lower()
    assert "safe" in next_section or "low" in next_section or "no session" in next_section


# ── Section structure ─────────────────────────────────────────────────────────

def test_doc_has_all_required_sections():
    """All 7 required sections are present."""
    text = _text()
    sections = [
        "## 1. Current app.py Responsibilities",
        "## 2. Functions and Routes Found",
        "## 3. Recommended Target Structure",
        "## 4. Split Order",
        "## 5. Highest-Risk Areas",
        "## 6. Test Strategy",
        "## 7. Next Implementation Step",
    ]
    for section in sections:
        assert section in text, f"Missing section: {section}"
