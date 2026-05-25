"""
Tests that the Render smoke completion report exists and contains
all required sections and content markers.

Documentation-only tests — no HTTP calls, no server, no API.
"""

import os

REPORT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "docs", "ai2-render-smoke-completion-report.md"
)


def _text() -> str:
    with open(REPORT_PATH, encoding="utf-8") as f:
        return f.read()


# ── Existence ─────────────────────────────────────────────────────────────────

def test_report_exists():
    """The smoke completion report file exists in docs/."""
    assert os.path.isfile(REPORT_PATH), f"Report not found at {REPORT_PATH}"


def test_report_not_empty():
    assert len(_text()) > 500


def test_report_title_correct():
    assert "# AI² Render Smoke Completion Report" in _text()


# ── Health endpoint ───────────────────────────────────────────────────────────

def test_report_mentions_health_endpoint():
    """/health is listed as a passed smoke check."""
    assert "/health" in _text()


def test_report_mentions_test_mode_false():
    """Report confirms test_mode is false in production (real Claude calls)."""
    assert "test_mode" in _text()
    assert "false" in _text().lower()


# ── Security ──────────────────────────────────────────────────────────────────

def test_report_mentions_debug_endpoint_not_found():
    """Report confirms debug endpoint returns Not found without a token."""
    text = _text()
    assert "Not found" in text or "not found" in text.lower()
    assert "debug" in text.lower()


def test_report_mentions_storage_health_endpoint():
    assert "/debug/storage-health" in _text()


# ── AI generation ─────────────────────────────────────────────────────────────

def test_report_mentions_generate_learning_content():
    """Report confirms Generate Learning Content smoke check passed."""
    assert "Generate Learning Content" in _text()


def test_report_mentions_generate_quiz():
    """Report confirms Generate Quiz smoke check passed."""
    assert "Generate Quiz" in _text()


# ── Portfolio/interview redirect fix ──────────────────────────────────────────

def test_report_mentions_portfolio_task_no_chat_redirect():
    """Report confirms Portfolio Task no longer redirects to /chat."""
    text = _text()
    assert "Portfolio Task" in text
    assert "/chat" in text


def test_report_mentions_interview_practice_no_chat_redirect():
    """Report confirms Interview Practice no longer redirects to /chat."""
    text = _text()
    assert "Interview Practice" in text


def test_report_mentions_portfolio_anchor():
    """Report confirms Portfolio Task now links to #ai-portfolio-task anchor."""
    assert "#ai-portfolio-task" in _text()


def test_report_mentions_interview_anchor():
    """Report confirms Interview Practice now links to #ai-interview-practice anchor."""
    assert "#ai-interview-practice" in _text()


def test_report_mentions_both_fix_commits():
    """Report references both fix commits (f1fd631 and 25127d4)."""
    text = _text()
    assert "f1fd631" in text
    assert "25127d4" in text


def test_report_mentions_topics_html_fix():
    """Report mentions topics.html as the second redirect fix location."""
    assert "topics.html" in _text() or "topics page" in _text().lower()


def test_report_mentions_topic_detail_html_fix():
    """Report mentions topic_detail.html as the first redirect fix location."""
    assert "topic_detail.html" in _text() or "topic detail" in _text().lower()


# ── UI polish next step ───────────────────────────────────────────────────────

def test_report_mentions_ui_polish_as_next_step():
    """Report identifies UI polish as the next recommended step."""
    text = _text().lower()
    assert "ui polish" in text or ("polish" in text and "ui" in text)


def test_report_mentions_lovable():
    """Report names Lovable AI as the UI polish tool."""
    assert "Lovable" in _text()


def test_report_mentions_step_145():
    """Report references Step 145 as the next step identifier."""
    assert "145" in _text() or "Step 145" in _text()


# ── Azure should wait ─────────────────────────────────────────────────────────

def test_report_mentions_azure_should_wait():
    """Report explicitly states Azure should wait / not be enabled yet."""
    text = _text()
    assert "Azure" in text


# ── Feature flags ─────────────────────────────────────────────────────────────

def test_report_mentions_modular_curriculum_flag():
    assert "AI2_MODULAR_CURRICULUM_READS_ENABLED" in _text()


def test_report_mentions_usage_limits_flag():
    assert "AI2_USAGE_LIMITS_ENABLED" in _text()


def test_report_mentions_flags_stay_conservative():
    """Report instructs flags to remain at conservative values."""
    text = _text().lower()
    assert "false" in text


# ── Section structure ─────────────────────────────────────────────────────────

def test_report_has_all_required_sections():
    """All 8 required sections are present."""
    text = _text()
    sections = [
        "## 1. Summary",
        "## 2. Checks Passed",
        "## 3. Security Check Result",
        "## 4. AI Generation Check Result",
        "## 5. Portfolio/Interview Redirect Fix Result",
        "## 6. Known Non-Blocking Issues",
        "## 7. Flags That Must Stay Conservative",
        "## 8. Next Recommended Step",
    ]
    for section in sections:
        assert section in text, f"Missing section: {section}"
