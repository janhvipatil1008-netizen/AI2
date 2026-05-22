from pathlib import Path


DOC_PATH = Path("docs/ai2-remaining-unstaged-files-review.md")


def read_doc() -> str:
    return DOC_PATH.read_text(encoding="utf-8")


def test_remaining_unstaged_files_review_doc_exists():
    assert DOC_PATH.exists()
    assert read_doc().startswith("# AI² Remaining Unstaged Files Review")


def test_doc_mentions_sensitive_remaining_files():
    text = read_doc()
    assert "auth.py" in text
    assert "config.py" in text
    assert ".env.example" in text
    assert "static/style.css" in text


def test_doc_marks_temp_dirs_do_not_commit():
    text = read_doc()
    assert ".pytest_tmp/" in text
    assert "manual_tmp/" in text
    assert "Do Not Commit" in text


def test_doc_mentions_second_commit_recommendation_and_no_push_yet():
    text = read_doc()
    assert "create a second small commit before pushing" in text
    assert "No push yet" in text
    assert "Do not push" in text


def test_doc_mentions_runtime_dependency_risk():
    text = read_doc()
    assert "core/security_config.py" in text
    assert "services/beta_metrics_service.py" in text
    assert "repositories/beta_feedback_repository.py" in text
    assert "clean Render deploy" in text
