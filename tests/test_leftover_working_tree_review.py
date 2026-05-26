from pathlib import Path


DOC = Path("docs/ai2-leftover-working-tree-review.md")


def _text() -> str:
    return DOC.read_text(encoding="utf-8")


def test_leftover_working_tree_review_doc_exists():
    assert DOC.exists()


def test_doc_mentions_app_py():
    assert "app.py" in _text()


def test_doc_mentions_routes_jobs_py():
    assert "routes/jobs.py" in _text()


def test_doc_mentions_jobs_routes_split_test():
    assert "tests/test_jobs_routes_split.py" in _text()


def test_doc_recommends_commit_or_revert():
    text = _text().lower()
    assert "commit jobs split" in text or "revert leftover changes" in text


def test_doc_says_chat_session_split_should_wait_until_clean():
    text = _text().lower()
    assert "chat/session route split should wait" in text
    assert "working tree is clean" in text
