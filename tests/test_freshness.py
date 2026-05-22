import os

os.environ["AI2_TEST_MODE"] = "1"
os.environ["ANTHROPIC_API_KEY"] = "test-key"

import pytest
from fastapi.testclient import TestClient

from app import app
from curriculum.freshness import (
    FRESHNESS_LATEST_RECOMMENDED,
    FRESHNESS_PERIODIC,
    FRESHNESS_STABLE,
    FRESHNESS_TOOL_SPECIFIC,
    classify_topic_freshness,
    freshness_guidance,
)
from curriculum.topics import get_topics_for_week

client = TestClient(app)


# ── classify_topic_freshness: label priority ──────────────────────────────────

def test_pricing_keyword_returns_latest():
    assert classify_topic_freshness("AI Pricing Overview") == FRESHNESS_LATEST_RECOMMENDED


def test_cloud_cost_returns_latest():
    assert classify_topic_freshness("Cloud Cost Analysis") == FRESHNESS_LATEST_RECOMMENDED


def test_latest_keyword_in_description_returns_latest():
    assert classify_topic_freshness("Model Overview", "Compare the latest models") == FRESHNESS_LATEST_RECOMMENDED


def test_langchain_returns_tool_specific():
    assert classify_topic_freshness("Building with LangChain") == FRESHNESS_TOOL_SPECIFIC


def test_mcp_returns_tool_specific():
    assert classify_topic_freshness("MCP Integration") == FRESHNESS_TOOL_SPECIFIC


def test_fastapi_returns_tool_specific():
    assert classify_topic_freshness("FastAPI Deployment") == FRESHNESS_TOOL_SPECIFIC


def test_openai_returns_tool_specific():
    assert classify_topic_freshness("OpenAI API Basics") == FRESHNESS_TOOL_SPECIFIC


def test_rag_returns_periodic():
    assert classify_topic_freshness("Introduction to RAG") == FRESHNESS_PERIODIC


def test_agents_returns_periodic():
    assert classify_topic_freshness("Building AI Agents") == FRESHNESS_PERIODIC


def test_evaluation_returns_periodic():
    assert classify_topic_freshness("Model Evaluation Techniques") == FRESHNESS_PERIODIC


def test_evals_returns_periodic():
    assert classify_topic_freshness("Running Evals on LLM Outputs") == FRESHNESS_PERIODIC


def test_prompt_engineering_returns_periodic():
    assert classify_topic_freshness("Prompt Engineering Fundamentals") == FRESHNESS_PERIODIC


def test_stable_topic_returns_stable():
    assert classify_topic_freshness("Binary Search Trees") == FRESHNESS_STABLE


def test_basic_concept_returns_stable():
    assert classify_topic_freshness("Introduction to Python Classes") == FRESHNESS_STABLE


def test_description_checked_for_tool_keywords():
    assert classify_topic_freshness("Deployment Guide", "We will use Docker to containerise the service") == FRESHNESS_TOOL_SPECIFIC


def test_description_checked_for_periodic_keywords():
    assert classify_topic_freshness("Best Practices", "covers mlops workflows") == FRESHNESS_PERIODIC


# ── Priority: latest beats tool-specific ─────────────────────────────────────

def test_latest_beats_tool_specific():
    # "claude" is tool-specific, "pricing" is latest — latest should win
    result = classify_topic_freshness("Claude Pricing")
    assert result == FRESHNESS_LATEST_RECOMMENDED


def test_latest_beats_periodic():
    # "rag" is periodic, "current" is latest — latest should win
    result = classify_topic_freshness("Current RAG Patterns")
    assert result == FRESHNESS_LATEST_RECOMMENDED


# ── freshness_guidance ────────────────────────────────────────────────────────

def test_guidance_stable_non_empty():
    assert freshness_guidance(FRESHNESS_STABLE) != ""


def test_guidance_periodic_non_empty():
    assert freshness_guidance(FRESHNESS_PERIODIC) != ""


def test_guidance_tool_specific_non_empty():
    assert freshness_guidance(FRESHNESS_TOOL_SPECIFIC) != ""


def test_guidance_latest_recommended_non_empty():
    assert freshness_guidance(FRESHNESS_LATEST_RECOMMENDED) != ""


def test_guidance_unknown_label_returns_empty():
    assert freshness_guidance("Not A Real Label") == ""


# ── Template: freshness chip visible on topic detail page ─────────────────────

def _start_session(track: str = "aipm", week: int = 1) -> str:
    r = client.post("/session/start", json={"track": track, "week": week})
    assert r.status_code == 200, r.text
    return r.json()["session_id"]


def _first_topic():
    return get_topics_for_week("aipm", 1)[0]


def test_freshness_label_present_in_topic_detail_page():
    session_id = _start_session()
    topic = _first_topic()
    r = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert r.status_code == 200
    assert "Freshness:" in r.text


def test_freshness_chip_class_present_in_topic_detail_page():
    session_id = _start_session()
    topic = _first_topic()
    r = client.get(f"/topic/{session_id}/{topic.topic_id}")
    assert "topic-freshness-chip" in r.text


def test_freshness_guidance_text_present_in_topic_detail_page():
    session_id = _start_session()
    topic = _first_topic()
    r = client.get(f"/topic/{session_id}/{topic.topic_id}")
    # Guidance text should be one of the known strings
    known_guidance_fragments = [
        "foundational concept",
        "evolves over time",
        "tools and frameworks update",
        "become outdated quickly",
    ]
    assert any(frag in r.text for frag in known_guidance_fragments)


# ── Generated content saves the classified label (not "AI-generated") ─────────

def test_generated_content_saves_classified_freshness_label():
    session_id = _start_session()
    topic = _first_topic()
    r = client.post("/topic/content/generate", json={
        "session_id": session_id, "topic_id": topic.topic_id,
    })
    assert r.status_code == 200
    data = r.json()
    label = data["generated_topic_content"]["freshness_label"]
    valid_labels = {
        FRESHNESS_STABLE, FRESHNESS_PERIODIC,
        FRESHNESS_TOOL_SPECIFIC, FRESHNESS_LATEST_RECOMMENDED,
    }
    assert label in valid_labels, f"Unexpected freshness_label: {label!r}"
    assert label != "AI-generated"


def test_generated_practice_saves_classified_freshness_label():
    session_id = _start_session()
    topic = _first_topic()
    r = client.post("/topic/practice/generate", json={
        "session_id": session_id, "topic_id": topic.topic_id,
        "practice_type": "quiz",
    })
    assert r.status_code == 200
    data = r.json()
    label = data["generated_practice"]["freshness_label"]
    valid_labels = {
        FRESHNESS_STABLE, FRESHNESS_PERIODIC,
        FRESHNESS_TOOL_SPECIFIC, FRESHNESS_LATEST_RECOMMENDED,
    }
    assert label in valid_labels, f"Unexpected freshness_label: {label!r}"
    assert label != "AI-generated"
