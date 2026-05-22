"""Tests for services/learning_outcome_service.py."""

from __future__ import annotations

import inspect

from services import learning_outcome_service as service
from services.learning_outcome_service import (
    calculate_improvement_delta,
    classify_learning_outcome,
    summarize_learning_outcome,
)


PRIVATE_BASELINE = "private baseline answer should not appear"
PRIVATE_POST = "private post answer should not appear"


def test_positive_improvement_delta():
    assert calculate_improvement_delta(40, 75) == 35


def test_zero_improvement_delta():
    assert calculate_improvement_delta(75, 75) == 0


def test_negative_improvement_delta():
    assert calculate_improvement_delta(80, 65) == -15


def test_missing_scores_return_none():
    assert calculate_improvement_delta(None, 65) is None
    assert calculate_improvement_delta(80, None) is None
    assert calculate_improvement_delta(None, None) is None


def test_status_classification():
    assert classify_learning_outcome(10) == "improved"
    assert classify_learning_outcome(0) == "improved"
    assert classify_learning_outcome(-1) == "needs_review"
    assert classify_learning_outcome(None) == "completed"


def test_summary_for_none_outcome():
    assert summarize_learning_outcome(None) == {
        "has_baseline": False,
        "has_post": False,
        "baseline_score": None,
        "post_score": None,
        "improvement_delta": None,
        "status": None,
    }


def test_summary_includes_safe_fields_only():
    summary = summarize_learning_outcome({
        "baseline_prompt": "baseline prompt",
        "baseline_answer": PRIVATE_BASELINE,
        "baseline_score": 45,
        "post_prompt": "post prompt",
        "post_answer": PRIVATE_POST,
        "post_score": 80,
        "improvement_delta": 35,
        "status": "improved",
        "metadata": {"private": "metadata"},
    })

    assert summary == {
        "has_baseline": True,
        "has_post": True,
        "baseline_score": 45,
        "post_score": 80,
        "improvement_delta": 35,
        "status": "improved",
    }


def test_summary_excludes_full_answers():
    summary = summarize_learning_outcome({
        "baseline_answer": PRIVATE_BASELINE,
        "baseline_score": 40,
        "post_answer": PRIVATE_POST,
        "post_score": 70,
        "improvement_delta": 30,
        "status": "improved",
    })

    body = str(summary)
    assert PRIVATE_BASELINE not in body
    assert PRIVATE_POST not in body
    assert "baseline_answer" not in body
    assert "post_answer" not in body


def test_service_does_not_read_env_vars():
    src = inspect.getsource(service)
    assert "os.environ" not in src
    assert "os.getenv" not in src
    assert "getenv(" not in src


def test_service_does_not_create_db_connections():
    src = inspect.getsource(service)
    assert "database.pool" not in src
    assert "get_conn(" not in src
    assert "psycopg2.connect" not in src


def test_service_does_not_import_routes_or_session_context():
    src = inspect.getsource(service)
    assert "import routes" not in src
    assert "from routes" not in src
    assert "SessionContext" not in src
