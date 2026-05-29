from pathlib import Path


DOC = Path("docs/ai2-app-py-post-route-split-checkpoint.md")


def _text() -> str:
    return DOC.read_text(encoding="utf-8")


def test_checkpoint_doc_exists():
    assert DOC.exists()


def test_doc_mentions_moved_route_modules():
    text = _text()
    assert "routes/public.py" in text
    assert "routes/debug.py" in text
    assert "routes/admin.py" in text


def test_doc_mentions_session_persistence_helpers():
    text = _text()
    assert "session persistence helpers" in text.lower()
    assert "_get_session_data" in text
    assert "_save_session" in text
    assert "_save_exchange_to_history" in text


def test_doc_mentions_recommended_session_persistence_service():
    assert "services/session_persistence.py" in _text()


def test_doc_recommends_audit_before_moving():
    text = _text().lower()
    assert "audit session persistence helpers before moving" in text


def test_doc_mentions_route_dependency_wiring():
    assert "route dependency wiring" in _text().lower()
