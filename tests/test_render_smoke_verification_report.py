"""
Tests that the Render smoke verification report exists and contains
all required sections and content markers.

These tests are documentation-only verification — they make no HTTP
requests, no API calls, and do not start the server.
"""

import os

REPORT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "docs", "ai2-render-smoke-verification-report.md"
)


def _report_text() -> str:
    with open(REPORT_PATH, encoding="utf-8") as f:
        return f.read()


# ── Existence ─────────────────────────────────────────────────────────────────

def test_report_exists():
    """The smoke verification report file exists in docs/."""
    assert os.path.isfile(REPORT_PATH), (
        f"Report not found at {REPORT_PATH}"
    )


def test_report_is_not_empty():
    assert len(_report_text()) > 200


# ── Health endpoint ────────────────────────────────────────────────────────────

def test_report_mentions_health_endpoint():
    """/health check is listed as a required smoke check."""
    assert "/health" in _report_text()


# ── Generate Lesson / Practice ────────────────────────────────────────────────

def test_report_mentions_generate_lesson():
    """Generate Lesson is listed as a smoke check."""
    assert "Generate Lesson" in _report_text()


def test_report_mentions_generate_practice():
    """Generate Practice is listed as a smoke check."""
    assert "Generate Practice" in _report_text()


# ── Debug/admin endpoints ─────────────────────────────────────────────────────

def test_report_mentions_debug_endpoints_return_404():
    """Report states debug/admin endpoints should return 404 without token."""
    text = _report_text()
    assert "404" in text
    assert "debug" in text.lower()


def test_report_mentions_storage_health_endpoint():
    assert "/debug/storage-health" in _report_text()


def test_report_mentions_admin_endpoint():
    assert "/admin/beta-metrics" in _report_text()


# ── UI issues ─────────────────────────────────────────────────────────────────

def test_report_mentions_topics_todos_ui_raw():
    """Report acknowledges topics/todos pages appear raw/unstyled."""
    text = _report_text()
    assert "raw" in text.lower()
    assert "topics" in text.lower()
    assert "todos" in text.lower() or "todo" in text.lower()


# ── Modular curriculum flag ───────────────────────────────────────────────────

def test_report_mentions_modular_curriculum_reads_should_remain_false():
    """Report states modular curriculum reads should remain false during smoke."""
    text = _report_text()
    assert "AI2_MODULAR_CURRICULUM_READS_ENABLED" in text
    assert "false" in text.lower()


# ── Azure hold ────────────────────────────────────────────────────────────────

def test_report_mentions_azure_should_wait():
    """Report explicitly lists Azure deployment as do-not-enable."""
    text = _report_text()
    assert "Azure" in text


# ── Section structure ─────────────────────────────────────────────────────────

def test_report_has_all_required_sections():
    """All 8 required sections are present in the report."""
    text = _report_text()
    required_sections = [
        "## 1. Current Render Status",
        "## 2. Smoke Checks Still Required",
        "## 3. Expected Results",
        "## 4. Observed UI Issues",
        "## 5. Current Curriculum Status",
        "## 6. Do Not Enable Yet",
        "## 7. Recommended Next Manual Screenshots",
        "## 8. Next Development Step After Smoke Passes",
    ]
    for section in required_sections:
        assert section in text, f"Missing section: {section}"


def test_report_title_correct():
    assert "# AI² Render Smoke Verification Report" in _report_text()
