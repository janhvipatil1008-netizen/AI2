from pathlib import Path


DOC = Path("docs/ai2-dashboard-route-split-audit.md")


def _text() -> str:
    return DOC.read_text(encoding="utf-8")


def test_dashboard_route_split_audit_doc_exists():
    assert DOC.exists()


def test_doc_mentions_dashboard_responsibilities():
    text = _text()
    assert "Dashboard Responsibilities" in text
    assert "GET /dashboard" in text
    assert "renders the learner home page" in text


def test_doc_mentions_dashboard_route_destination():
    assert "routes/dashboard.py" in _text()


def test_doc_mentions_dashboard_template_summary_keys():
    text = _text()
    assert "enrollment_summary" in text
    assert "modular_progress_summary" in text
    assert "position_summary" in text


def test_doc_mentions_db_fallback_behavior_and_route_stability():
    text = _text()
    assert "DB fallback behavior" in text
    assert "route URL stability" in text


def test_doc_recommends_dashboard_route_next_step():
    text = _text()
    assert "Recommended Next Implementation Step" in text
    assert "Move only the dashboard route" in text
