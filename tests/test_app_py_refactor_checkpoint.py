from pathlib import Path


DOC = Path("docs/ai2-app-py-refactor-checkpoint.md")


def _text() -> str:
    return DOC.read_text(encoding="utf-8")


def test_checkpoint_doc_exists():
    assert DOC.exists()


def test_doc_mentions_completed_route_splits():
    text = _text()
    assert "public routes split" in text
    assert "onboarding routes split" in text
    assert "dashboard route split" in text


def test_doc_mentions_remaining_debug_and_auth_routes():
    text = _text()
    assert "remaining debug routes" in text.lower()
    assert "Auth routes" in text
    assert "GET /login" in text


def test_doc_mentions_session_persistence_helpers():
    text = _text()
    assert "Session persistence helpers" in text
    assert "_save_session" in text
    assert "_get_session_data" in text


def test_doc_recommends_next_split():
    text = _text()
    assert "Recommended next split" in text
    assert "routes/auth.py" in text or "routes/syllabus.py" in text


def test_doc_mentions_route_url_stability():
    assert "route URL stability" in _text()
