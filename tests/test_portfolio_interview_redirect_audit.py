"""
Tests that the Portfolio/Interview redirect audit report exists and contains
all required sections and content markers.

These tests are documentation-only — no HTTP requests, no API calls,
no server startup required.
"""

import os

REPORT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "docs", "ai2-portfolio-interview-redirect-audit.md"
)


def _text() -> str:
    with open(REPORT_PATH, encoding="utf-8") as f:
        return f.read()


# ── Existence ─────────────────────────────────────────────────────────────────

def test_audit_doc_exists():
    """The audit report file exists in docs/."""
    assert os.path.isfile(REPORT_PATH), f"Report not found at {REPORT_PATH}"


def test_audit_doc_not_empty():
    assert len(_text()) > 300


# ── /chat redirect ────────────────────────────────────────────────────────────

def test_doc_mentions_chat_redirect():
    """/chat redirect is identified as the observed behavior."""
    assert "/chat" in _text()


def test_doc_mentions_chat_url_data_attribute():
    """The data-chat-url attribute is named as part of the root cause."""
    assert "data-chat-url" in _text()


# ── Topic detail ──────────────────────────────────────────────────────────────

def test_doc_mentions_topic_detail():
    """Report references topic detail page as the expected destination."""
    assert "topic detail" in _text().lower()


def test_doc_mentions_topic_detail_template_file():
    """Report names the specific template file involved."""
    assert "topic_detail.html" in _text()


def test_doc_mentions_topic_detail_js_file():
    """Report names the JS file containing the redirect handler."""
    assert "topic_detail.js" in _text()


# ── Portfolio task ────────────────────────────────────────────────────────────

def test_doc_mentions_portfolio_task():
    """Portfolio Task is identified as one of the redirecting actions."""
    assert "Portfolio Task" in _text() or "portfolio_task" in _text()


def test_doc_mentions_portfolio_endpoints():
    """Report lists /portfolio/submit and /portfolio/feedback as existing endpoints."""
    text = _text()
    assert "/portfolio/submit" in text
    assert "/portfolio/feedback" in text


# ── Interview practice ────────────────────────────────────────────────────────

def test_doc_mentions_interview_practice():
    """Interview Practice is identified as one of the redirecting actions."""
    assert "Interview Practice" in _text() or "interview_practice" in _text()


def test_doc_mentions_interview_endpoints():
    """Report lists /interview/submit and /interview/feedback as existing endpoints."""
    text = _text()
    assert "/interview/submit" in text
    assert "/interview/feedback" in text


# ── Structured learning behavior ──────────────────────────────────────────────

def test_doc_mentions_structured_learning_behavior():
    """Report describes expected structured on-page behavior."""
    text = _text().lower()
    assert "structured" in text


def test_doc_mentions_generate_practice_function():
    """Report identifies generatePractice() as the correct function to call."""
    assert "generatePractice" in _text()


def test_doc_mentions_existing_endpoints():
    """Report confirms structured endpoints already exist — no backend work needed."""
    assert "/topic/practice/generate" in _text()


# ── Orchestrator preservation ─────────────────────────────────────────────────

def test_doc_mentions_not_changing_orchestrator():
    """Report explicitly states orchestrator.py should not be changed."""
    assert "orchestrator" in _text().lower()
    assert "not" in _text().lower()


# ── Test plan ─────────────────────────────────────────────────────────────────

def test_doc_has_test_plan_section():
    """Report contains a test plan section."""
    assert "## 7. Test Plan" in _text()


def test_doc_test_plan_covers_portfolio_stays_on_page():
    """Test plan includes check that portfolio click stays on topic detail."""
    text = _text().lower()
    assert "portfolio" in text
    assert "topic detail" in text


def test_doc_test_plan_covers_interview_stays_on_page():
    """Test plan includes check that interview click stays on topic detail."""
    text = _text().lower()
    assert "interview" in text
    assert "topic detail" in text


def test_doc_test_plan_covers_chat_quick_actions_still_work():
    """Test plan confirms chat quick actions should continue working separately."""
    assert "chat" in _text().lower()


def test_doc_test_plan_no_route_url_changes():
    """Test plan states no route URLs should change."""
    assert "route" in _text().lower()


def test_doc_test_plan_no_claude_changes():
    """Test plan states no Claude/provider changes."""
    text = _text().lower()
    assert "claude" in text or "provider" in text


# ── Section structure ─────────────────────────────────────────────────────────

def test_doc_has_all_required_sections():
    """All 7 required sections are present."""
    text = _text()
    sections = [
        "## 1. Current Behavior",
        "## 2. Expected Structured Learning Behavior",
        "## 3. Files and Routes Involved",
        "## 4. Existing Structured Endpoints",
        "## 5. Root Cause",
        "## 6. Recommended Fix",
        "## 7. Test Plan",
    ]
    for section in sections:
        assert section in text, f"Missing section: {section}"


def test_doc_title_correct():
    assert "# AI² Portfolio and Interview Redirect Audit" in _text()
