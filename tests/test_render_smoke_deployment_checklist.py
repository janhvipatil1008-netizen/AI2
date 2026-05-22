"""Tests for the Render smoke deployment checklist doc."""

from __future__ import annotations

from pathlib import Path


DOC_PATH = Path("docs/ai2-render-smoke-deployment-checklist.md")


def _doc() -> str:
    return DOC_PATH.read_text(encoding="utf-8")


def test_render_smoke_checklist_doc_exists():
    assert DOC_PATH.exists()
    assert _doc().startswith("# AI² Render Smoke Deployment Checklist")


def test_doc_mentions_render_env_vars():
    text = _doc()

    assert "Required Render Environment Variables" in text
    assert "AI2_ENV=production" in text
    assert "AUTH_SECRET" in text
    assert "ANTHROPIC_API_KEY" in text
    assert "SUPABASE_DATABASE_URL" in text


def test_doc_recommends_modular_reads_false_first():
    text = _doc()

    assert "AI2_MODULAR_CURRICULUM_READS_ENABLED=false" in text
    assert "Keep modular reads false first" in text


def test_doc_recommends_db_write_through_false_initially():
    text = _doc()

    assert "AI2_DB_WRITE_THROUGH_ENABLED=false initially" in text
    assert "Keep DB write-through false" in text


def test_doc_mentions_debug_token_protection():
    text = _doc()

    assert "X-AI2-Debug-Token" in text
    assert "Wrong or missing token returns `404`" in text
    assert "/debug/storage-health" in text
    assert "/debug/modular-curriculum" in text
    assert "/admin/beta-metrics" in text


def test_doc_mentions_schema_and_manual_seed():
    text = _doc()

    assert "database/schema.sql" in text
    assert "scripts/seed_modular_curriculum.py" in text
    assert "manually only after schema is applied" in text


def test_doc_mentions_rollback_plan():
    text = _doc()

    assert "Rollback Plan" in text
    assert "Redeploy the previous commit" in text
    assert "Check Render runtime logs after rollback" in text


def test_doc_says_do_not_remove_week_compatibility_yet():
    text = _doc()

    assert "Removing `current_week`" in text
    assert "Deleting `WEEKS` or `ROLE_TRACKS`" in text
