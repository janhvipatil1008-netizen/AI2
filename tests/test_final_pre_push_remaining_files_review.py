from pathlib import Path


DOC_PATH = Path("docs/ai2-final-pre-push-remaining-files-review.md")


def read_doc() -> str:
    return DOC_PATH.read_text(encoding="utf-8")


def test_final_pre_push_review_doc_exists():
    assert DOC_PATH.exists()
    assert read_doc().startswith("# AI² Final Pre-Push Remaining Files Review")


def test_doc_mentions_sensitive_files():
    text = read_doc()
    assert "auth.py" in text
    assert "config.py" in text
    assert ".env.example" in text
    assert "static/style.css" in text
    assert "templates/login.html" in text


def test_doc_mentions_recommendation_and_no_push_yet():
    text = read_doc()
    assert "Recommendation" in text
    assert "hold push until manual visual review" in text
    assert "No push yet" in text
    assert "Do not push yet" in text


def test_doc_marks_temp_dirs_do_not_stage():
    text = read_doc()
    assert ".pytest_tmp/" in text
    assert "manual_tmp/" in text
    assert "Do not stage" in text


def test_doc_mentions_step_134_review_checks():
    text = read_doc()
    assert "Step 134 Review Result" in text
    assert "Mojibake review" in text
    assert "Auth/config reviewed" in text
    assert ".env.example` reviewed" in text
    assert "CSS reviewed" in text
