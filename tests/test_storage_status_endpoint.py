"""Tests for GET /debug/storage-status.

Verifies that the endpoint:
- exists and returns 200
- returns correct boolean flags for the current feature-flag state
- changes storage_mode based on AI2_DB_WRITE_THROUGH_ENABLED
- never exposes env var values, secrets, or DB URLs
- never opens a DB connection
- does not require a live browser
"""

from __future__ import annotations

import os

os.environ["AI2_TEST_MODE"] = "1"
os.environ["ANTHROPIC_API_KEY"] = "test-key"

from unittest.mock import patch

from fastapi.testclient import TestClient

from app import app

client = TestClient(app)

URL = "/debug/storage-status"


# ── Endpoint existence ────────────────────────────────────────────────────────

def test_endpoint_exists_returns_200():
    r = client.get(URL)
    assert r.status_code == 200


def test_endpoint_returns_json():
    r = client.get(URL)
    assert r.headers["content-type"].startswith("application/json")


# ── Stable fields always present ──────────────────────────────────────────────

def test_response_has_all_expected_keys():
    r = client.get(URL)
    data = r.json()
    expected = {
        "session_context_source_of_truth",
        "db_write_through_enabled",
        "db_reads_enabled",
        "curriculum_db_reads_enabled",
        "progress_db_reads_enabled",
        "todos_db_reads_enabled",
        "storage_mode",
        "notes",
    }
    assert expected.issubset(data.keys()), f"Missing keys: {expected - data.keys()}"


def test_session_context_source_of_truth_is_true():
    r = client.get(URL)
    assert r.json()["session_context_source_of_truth"] is True


def test_db_reads_enabled_is_false():
    r = client.get(URL)
    assert r.json()["db_reads_enabled"] is False


def test_curriculum_db_reads_enabled_is_false():
    r = client.get(URL)
    assert r.json()["curriculum_db_reads_enabled"] is False


def test_progress_db_reads_enabled_is_false():
    r = client.get(URL)
    assert r.json()["progress_db_reads_enabled"] is False


def test_todos_db_reads_enabled_is_false():
    r = client.get(URL)
    assert r.json()["todos_db_reads_enabled"] is False


def test_db_reads_enabled_true_if_curriculum_read_flag_true(monkeypatch):
    monkeypatch.setenv("AI2_CURRICULUM_DB_READS_ENABLED", "1")
    monkeypatch.delenv("AI2_PROGRESS_DB_READS_ENABLED", raising=False)
    monkeypatch.delenv("AI2_TODOS_DB_READS_ENABLED", raising=False)

    data = client.get(URL).json()

    assert data["curriculum_db_reads_enabled"] is True
    assert data["progress_db_reads_enabled"] is False
    assert data["todos_db_reads_enabled"] is False
    assert data["db_reads_enabled"] is True


def test_db_reads_enabled_true_if_progress_read_flag_true(monkeypatch):
    monkeypatch.delenv("AI2_CURRICULUM_DB_READS_ENABLED", raising=False)
    monkeypatch.setenv("AI2_PROGRESS_DB_READS_ENABLED", "true")
    monkeypatch.delenv("AI2_TODOS_DB_READS_ENABLED", raising=False)

    data = client.get(URL).json()

    assert data["curriculum_db_reads_enabled"] is False
    assert data["progress_db_reads_enabled"] is True
    assert data["todos_db_reads_enabled"] is False
    assert data["db_reads_enabled"] is True


def test_db_reads_enabled_true_if_todos_read_flag_true(monkeypatch):
    monkeypatch.delenv("AI2_CURRICULUM_DB_READS_ENABLED", raising=False)
    monkeypatch.delenv("AI2_PROGRESS_DB_READS_ENABLED", raising=False)
    monkeypatch.setenv("AI2_TODOS_DB_READS_ENABLED", "yes")

    data = client.get(URL).json()

    assert data["curriculum_db_reads_enabled"] is False
    assert data["progress_db_reads_enabled"] is False
    assert data["todos_db_reads_enabled"] is True
    assert data["db_reads_enabled"] is True


def test_db_reads_enabled_false_when_all_read_flags_false(monkeypatch):
    monkeypatch.setenv("AI2_CURRICULUM_DB_READS_ENABLED", "off")
    monkeypatch.setenv("AI2_PROGRESS_DB_READS_ENABLED", "0")
    monkeypatch.setenv("AI2_TODOS_DB_READS_ENABLED", "enabled")

    data = client.get(URL).json()

    assert data["curriculum_db_reads_enabled"] is False
    assert data["progress_db_reads_enabled"] is False
    assert data["todos_db_reads_enabled"] is False
    assert data["db_reads_enabled"] is False


def test_read_flags_enabled_storage_mode_and_note(monkeypatch):
    monkeypatch.setenv("AI2_CURRICULUM_DB_READS_ENABLED", "on")

    data = client.get(URL).json()

    assert data["storage_mode"] == "session_context_with_db_read_flags_enabled"
    assert any("runtime routes have not been migrated" in note for note in data["notes"])


def test_notes_is_a_list():
    r = client.get(URL)
    assert isinstance(r.json()["notes"], list)


def test_notes_contains_source_of_truth_message():
    r = client.get(URL)
    notes = r.json()["notes"]
    assert any("source of truth" in n.lower() for n in notes)


def test_notes_contains_no_db_reads_message():
    r = client.get(URL)
    notes = r.json()["notes"]
    assert any("not read" in n.lower() or "no" in n.lower() for n in notes)


# ── Flag OFF (default) ────────────────────────────────────────────────────────

def test_flag_off_db_write_through_enabled_is_false(monkeypatch):
    monkeypatch.delenv("AI2_DB_WRITE_THROUGH_ENABLED", raising=False)
    r = client.get(URL)
    assert r.json()["db_write_through_enabled"] is False


def test_flag_off_storage_mode_is_session_context_only(monkeypatch):
    monkeypatch.delenv("AI2_DB_WRITE_THROUGH_ENABLED", raising=False)
    r = client.get(URL)
    assert r.json()["storage_mode"] == "session_context_only"


def test_flag_off_notes_mention_disabled(monkeypatch):
    monkeypatch.delenv("AI2_DB_WRITE_THROUGH_ENABLED", raising=False)
    r = client.get(URL)
    notes = r.json()["notes"]
    assert any("disabled" in n.lower() for n in notes)


def test_flag_off_notes_do_not_mention_enabled_write_through(monkeypatch):
    monkeypatch.delenv("AI2_DB_WRITE_THROUGH_ENABLED", raising=False)
    r = client.get(URL)
    notes = r.json()["notes"]
    assert not any("enabled for progress" in n.lower() for n in notes)


# ── Flag ON ───────────────────────────────────────────────────────────────────

def test_flag_on_db_write_through_enabled_is_true(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    r = client.get(URL)
    assert r.json()["db_write_through_enabled"] is True


def test_flag_on_storage_mode_is_with_db_write_through(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    r = client.get(URL)
    assert r.json()["storage_mode"] == "session_context_with_db_write_through"


def test_flag_on_notes_mention_enabled(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    r = client.get(URL)
    notes = r.json()["notes"]
    assert any("enabled" in n.lower() and "progress" in n.lower() for n in notes)


def test_flag_on_notes_do_not_mention_disabled(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    r = client.get(URL)
    notes = r.json()["notes"]
    # The "disabled" message should not appear when the flag is on
    assert not any(n.strip().lower() == "db write-through is disabled." for n in notes)


def test_flag_on_db_reads_still_false(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    r = client.get(URL)
    data = r.json()
    assert data["db_reads_enabled"] is False
    assert data["curriculum_db_reads_enabled"] is False
    assert data["progress_db_reads_enabled"] is False
    assert data["todos_db_reads_enabled"] is False


def test_flag_true_string_also_sets_enabled(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "true")
    r = client.get(URL)
    assert r.json()["db_write_through_enabled"] is True


# ── Security: no secrets in response ─────────────────────────────────────────

def test_response_does_not_contain_database_url(monkeypatch):
    monkeypatch.setenv("SUPABASE_DATABASE_URL", "postgresql://user:secret@host/db")
    r = client.get(URL)
    body = r.text
    assert "postgresql://" not in body
    assert "user:secret" not in body
    assert "SUPABASE_DATABASE_URL" not in body


def test_response_does_not_contain_api_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-super-secret")
    r = client.get(URL)
    body = r.text
    assert "sk-ant-test-super-secret" not in body
    assert "ANTHROPIC_API_KEY" not in body


def test_response_does_not_contain_raw_env_var_names():
    r = client.get(URL)
    body = r.text
    # Should not leak env var names as values
    assert "AI2_DB_WRITE_THROUGH_ENABLED" not in body
    assert "SUPABASE_DATABASE_URL" not in body
    assert "ANTHROPIC_API_KEY" not in body


def test_response_does_not_contain_user_data():
    r = client.get(URL)
    data = r.json()
    # No session IDs, user IDs, or session counts
    assert "session_id" not in data
    assert "user_id" not in data
    assert "sessions" not in data


# ── No DB connection attempted ────────────────────────────────────────────────

def test_endpoint_does_not_open_db_connection_flag_off(monkeypatch):
    monkeypatch.delenv("AI2_DB_WRITE_THROUGH_ENABLED", raising=False)
    with patch("database.pool._connect", side_effect=AssertionError("_connect must not be called")) as mock_c:
        r = client.get(URL)
    assert r.status_code == 200
    mock_c.assert_not_called()


def test_endpoint_does_not_open_db_connection_flag_on(monkeypatch):
    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "1")
    with patch("database.pool._connect", side_effect=AssertionError("_connect must not be called")) as mock_c:
        r = client.get(URL)
    assert r.status_code == 200
    mock_c.assert_not_called()


def test_endpoint_does_not_open_db_connection_when_read_flags_on(monkeypatch):
    monkeypatch.setenv("AI2_CURRICULUM_DB_READS_ENABLED", "1")
    monkeypatch.setenv("AI2_PROGRESS_DB_READS_ENABLED", "1")
    monkeypatch.setenv("AI2_TODOS_DB_READS_ENABLED", "1")
    with patch("database.pool._connect", side_effect=AssertionError("_connect must not be called")) as mock_c:
        r = client.get(URL)
    assert r.status_code == 200
    assert r.json()["db_reads_enabled"] is True
    mock_c.assert_not_called()


def test_endpoint_does_not_call_runtime_db_read_functions(monkeypatch):
    monkeypatch.setenv("AI2_CURRICULUM_DB_READS_ENABLED", "1")
    monkeypatch.setenv("AI2_PROGRESS_DB_READS_ENABLED", "1")
    monkeypatch.setenv("AI2_TODOS_DB_READS_ENABLED", "1")

    with patch(
        "repositories.curriculum_repository.get_learning_track_by_key",
        side_effect=AssertionError("curriculum read must not be called"),
    ) as track_read:
        with patch(
            "repositories.curriculum_repository.get_learning_topic_by_legacy_id",
            side_effect=AssertionError("topic read must not be called"),
        ) as topic_read:
            with patch(
                "repositories.progress_repository.get_topic_progress_by_legacy_id",
                side_effect=AssertionError("progress read must not be called"),
            ) as progress_read:
                with patch(
                    "repositories.todos_repository.list_todos_for_session",
                    side_effect=AssertionError("todos read must not be called"),
                ) as todos_read:
                    r = client.get(URL)

    assert r.status_code == 200
    track_read.assert_not_called()
    topic_read.assert_not_called()
    progress_read.assert_not_called()
    todos_read.assert_not_called()


# ── No stack traces or internal errors ────────────────────────────────────────

def test_response_does_not_contain_traceback():
    r = client.get(URL)
    body = r.text
    assert "Traceback" not in body
    assert "traceback" not in body


def test_response_does_not_contain_exception_strings():
    r = client.get(URL)
    body = r.text
    assert "Exception" not in body
    assert "RuntimeError" not in body
