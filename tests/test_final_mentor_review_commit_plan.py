"""
Tests that the final mentor review commit plan doc exists and contains
all required sections and content markers.

Documentation-only tests — no HTTP calls, no server, no API.
"""

import os

PLAN_PATH = os.path.join(
    os.path.dirname(__file__), "..", "docs", "ai2-final-mentor-review-commit-plan.md"
)


def _text() -> str:
    with open(PLAN_PATH, encoding="utf-8") as f:
        return f.read()


# ── Existence ─────────────────────────────────────────────────────────────────

def test_plan_exists():
    """The commit plan doc exists in docs/."""
    assert os.path.isfile(PLAN_PATH), f"Plan not found at {PLAN_PATH}"


def test_plan_not_empty():
    assert len(_text()) > 500


def test_plan_title_correct():
    assert "# AI² Final Mentor Review Commit Plan" in _text()


# ── Mentor review ─────────────────────────────────────────────────────────────

def test_plan_mentions_mentor_review():
    """Doc references mentor review as the purpose."""
    assert "mentor" in _text().lower()


def test_plan_mentions_github():
    """Doc implies GitHub as the destination for mentor review."""
    text = _text().lower()
    assert "github" in text or "push" in text


# ── Files recommended to commit ───────────────────────────────────────────────

def test_plan_mentions_files_recommended_to_commit():
    """Doc has a section listing files recommended for commit."""
    assert "## 2. Files Recommended To Commit" in _text()


def test_plan_mentions_auth_py():
    assert "auth.py" in _text()


def test_plan_mentions_style_css():
    assert "style.css" in _text()


def test_plan_mentions_readme():
    assert "README" in _text()


def test_plan_mentions_docs_files():
    text = _text()
    assert "docs/" in text or "audit" in text.lower()


def test_plan_mentions_test_files():
    text = _text()
    assert "tests/" in text or "test_" in text


# ── Files not to commit ───────────────────────────────────────────────────────

def test_plan_mentions_files_not_to_commit():
    """Doc has a section listing files that must not be committed."""
    assert "## 4. Files Not To Commit" in _text()


def test_plan_mentions_env_must_not_be_staged():
    """Doc explicitly states .env must not be committed."""
    assert ".env" in _text()


def test_plan_mentions_local_db_files_must_not_be_staged():
    """Doc explicitly states local DB files must not be committed."""
    text = _text().lower()
    assert "db" in text or "sqlite" in text or "local db" in text


def test_plan_mentions_temp_dirs_not_to_commit():
    """Doc lists temp/cache directories that must not be staged."""
    text = _text()
    assert ".pytest_tmp" in text or "manual_tmp" in text


# ── Pre-commit tests ──────────────────────────────────────────────────────────

def test_plan_mentions_pre_commit_tests():
    """Doc includes a pre-commit test command."""
    assert "## 7. Pre-Commit Tests" in _text()


def test_plan_mentions_pytest_command():
    """Doc includes a pytest command."""
    assert "pytest" in _text()


def test_plan_mentions_auth_config_test():
    """Pre-commit tests include production auth config tests."""
    assert "test_production_auth_config" in _text()


def test_plan_mentions_debug_protection_test():
    """Pre-commit tests include debug endpoint protection tests."""
    assert "test_debug_endpoint_protection" in _text()


# ── Final push checklist ──────────────────────────────────────────────────────

def test_plan_mentions_final_push_checklist():
    """Doc contains a final push checklist section."""
    assert "## 8. Final Push Checklist" in _text()


def test_checklist_mentions_env_not_staged():
    """Checklist confirms .env must not be staged."""
    text = _text()
    assert ".env" in text
    assert "not" in text.lower() or "never" in text.lower()


def test_checklist_mentions_debug_protection():
    """Checklist confirms debug endpoint protection must remain active."""
    text = _text().lower()
    assert "debug" in text
    assert "not found" in text or "protection" in text


def test_checklist_mentions_readme_safe_for_public():
    """Checklist confirms README is safe for public mentor review."""
    text = _text().lower()
    assert "readme" in text
    assert "safe" in text or "public" in text or "mentor" in text


# ── Risk review ───────────────────────────────────────────────────────────────

def test_plan_has_risk_review_section():
    assert "## 5. Risk Review" in _text()


def test_risk_review_covers_all_modified_files():
    text = _text()
    for f in ["auth.py", "config.py", "style.css", "base.html", "chat.html", "index.html", "syllabus.html"]:
        assert f in text, f"Risk review missing file: {f}"


# ── Commit strategy ───────────────────────────────────────────────────────────

def test_plan_has_recommended_commit_strategy():
    assert "## 6. Recommended Commit Strategy" in _text()


def test_plan_commit_message_present():
    assert "Finalize mentor review polish and docs" in _text()


# ── Section structure ─────────────────────────────────────────────────────────

def test_plan_has_all_required_sections():
    """All 8 required sections present."""
    text = _text()
    sections = [
        "## 1. Current Repo Status",
        "## 2. Files Recommended To Commit",
        "## 3. Files Requiring Manual Visual Review",
        "## 4. Files Not To Commit",
        "## 5. Risk Review",
        "## 6. Recommended Commit Strategy",
        "## 7. Pre-Commit Tests",
        "## 8. Final Push Checklist",
    ]
    for section in sections:
        assert section in text, f"Missing section: {section}"
