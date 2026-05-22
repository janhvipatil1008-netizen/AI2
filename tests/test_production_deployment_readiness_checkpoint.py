"""Tests for the production deployment readiness checkpoint doc."""

from __future__ import annotations

from pathlib import Path


DOC_PATH = Path("docs/ai2-production-deployment-readiness-checkpoint.md")


def _doc() -> str:
    return DOC_PATH.read_text(encoding="utf-8")


def test_checkpoint_doc_exists():
    assert DOC_PATH.exists()
    assert _doc().startswith("# AI² Production Deployment Readiness Checkpoint")


def test_doc_mentions_render_and_azure():
    text = _doc()

    assert "Render" in text
    assert "Azure" in text
    assert "Azure App Service" in text
    assert "Azure Database for PostgreSQL" in text


def test_doc_recommends_modular_reads_false_initially():
    text = _doc()

    assert "AI2_MODULAR_CURRICULUM_READS_ENABLED=false initially" in text


def test_doc_mentions_modular_seed_is_manual_only():
    text = _doc()

    assert "scripts/seed_modular_curriculum.py" in text
    assert "manual only" in text
    assert "Do not run seed scripts automatically" in text


def test_doc_mentions_week_compatibility_fallbacks():
    text = _doc()

    assert "current_week remains compatibility-only" in text
    assert "WEEKS" in text
    assert "ROLE_TRACKS" in text
    assert "fallback/seed source" in text


def test_doc_mentions_smoke_tests_and_debug_token_protection():
    text = _doc()

    assert "Smoke Test Checklist" in text
    assert "/debug/modular-curriculum" in text
    assert "/admin/beta-metrics" in text
    assert "AI2_DEBUG_TOKEN" in text
    assert "Debug token protection" in text
