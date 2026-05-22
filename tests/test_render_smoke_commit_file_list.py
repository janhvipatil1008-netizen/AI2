from pathlib import Path


DOC_PATH = Path("docs/ai2-render-smoke-commit-file-list.md")


def read_doc() -> str:
    return DOC_PATH.read_text(encoding="utf-8")


def test_render_smoke_commit_file_list_doc_exists():
    assert DOC_PATH.exists()
    assert read_doc().startswith("# AI² Render Smoke Commit File List")


def test_doc_mentions_one_commit_strategy():
    text = read_doc()
    assert "Recommended strategy: one commit" in text
    assert "Add modular curriculum migration foundation" in text


def test_doc_mentions_exact_git_add_command_and_no_git_add_dot():
    text = read_doc()
    assert "## 6. Exact Git Add Command" in text
    assert "git add app.py context/session.py" in text
    assert "Do not use `git add .`" in text


def test_doc_mentions_exact_commit_command():
    text = read_doc()
    assert 'git commit -m "Add modular curriculum migration foundation"' in text


def test_doc_mentions_not_staging_env_or_local_db_files():
    text = read_doc()
    assert "Confirm no `.env` file is staged" in text
    assert "jobs.db" in text
    assert "sessions.db" in text
    assert "sessions.db-shm" in text
    assert "sessions.db-wal" in text


def test_doc_mentions_pre_commit_test_command():
    text = read_doc()
    assert "python -m pytest tests/test_topics_routes.py" in text
    assert "tests/test_render_smoke_deployment_checklist.py" in text


def test_doc_mentions_conservative_render_flags():
    text = read_doc()
    assert "AI2_MODULAR_CURRICULUM_READS_ENABLED=false" in text
    assert "AI2_DB_WRITE_THROUGH_ENABLED=false" in text
    assert "AI2_TODOS_DB_READS_ENABLED=false" in text
    assert "AI2_PROGRESS_DB_READS_ENABLED=false" in text
    assert "AI2_USAGE_LIMITS_ENABLED=true" in text
