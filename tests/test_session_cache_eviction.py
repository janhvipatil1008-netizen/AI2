"""Tests for _sessions in-memory cache eviction policy.

Covers:
  - structural assertions (dicts and constants present in app.py source)
  - _session_touch behaviour
  - TTL expiry via _evict_expired_sessions
  - LRU cap enforcement via _enforce_session_cache_cap
  - combined sweep via _sweep_session_cache_once
  - _get_session_data and _save_session touch sessions after success
  - TEST_MODE safety (eviction functions remain callable; DB is never touched)
  - no private session content in eviction log lines
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import pytest

import os
os.environ.setdefault("AI2_TEST_MODE", "1")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")

import app as app_module
from config import CareerTrack
from context.session import SessionContext

APP = Path("app.py")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _make_entry(user_id: str = "user-a") -> dict:
    session = SessionContext(track=CareerTrack.AI_PM, user_id=user_id)
    return {"session": session, "orch": object(), "client": object(), "profile": None}


def _clear_caches() -> None:
    app_module._sessions.clear()
    app_module._sessions_last_accessed.clear()


# ── Structural assertions ─────────────────────────────────────────────────────

def test_sessions_dict_still_in_app():
    assert "_sessions: dict[str, dict] = {}" in _read(APP)


def test_sessions_last_accessed_exists_in_app():
    source = _read(APP)
    assert "_sessions_last_accessed: dict[str, float] = {}" in source


def test_eviction_constants_present_in_source():
    source = _read(APP)
    assert "_SESSION_CACHE_TTL_SECONDS" in source
    assert "_SESSION_CACHE_MAX_ENTRIES" in source
    assert "_SESSION_CACHE_SWEEP_INTERVAL_SECONDS" in source


def test_eviction_constants_have_correct_values():
    assert app_module._SESSION_CACHE_TTL_SECONDS == 30 * 60
    assert app_module._SESSION_CACHE_MAX_ENTRIES == 500
    assert app_module._SESSION_CACHE_SWEEP_INTERVAL_SECONDS == 10 * 60


def test_sessions_last_accessed_is_plain_dict():
    assert isinstance(app_module._sessions_last_accessed, dict)


# ── _session_touch ────────────────────────────────────────────────────────────

def test_session_touch_records_timestamp():
    _clear_caches()
    before = time.monotonic()
    app_module._session_touch("sid-1")
    after = time.monotonic()
    ts = app_module._sessions_last_accessed["sid-1"]
    assert before <= ts <= after


def test_session_touch_overwrites_stale_timestamp():
    _clear_caches()
    app_module._sessions_last_accessed["sid-1"] = 0.0
    app_module._session_touch("sid-1")
    assert app_module._sessions_last_accessed["sid-1"] > 1.0


def test_session_touch_works_for_new_and_existing_keys():
    _clear_caches()
    app_module._session_touch("new-sid")
    assert "new-sid" in app_module._sessions_last_accessed
    app_module._session_touch("new-sid")
    assert "new-sid" in app_module._sessions_last_accessed


# ── _evict_expired_sessions ───────────────────────────────────────────────────

def test_expired_session_removed_from_memory():
    _clear_caches()
    app_module._sessions["old"] = _make_entry()
    app_module._sessions_last_accessed["old"] = 0.0  # ancient timestamp

    evicted = app_module._evict_expired_sessions(now=time.monotonic())

    assert evicted == 1
    assert "old" not in app_module._sessions
    assert "old" not in app_module._sessions_last_accessed


def test_fresh_session_is_kept():
    _clear_caches()
    now = time.monotonic()
    app_module._sessions["fresh"] = _make_entry()
    app_module._sessions_last_accessed["fresh"] = now - 60  # 1 min ago — within 30-min TTL

    evicted = app_module._evict_expired_sessions(now=now)

    assert evicted == 0
    assert "fresh" in app_module._sessions


def test_eviction_clears_both_dicts():
    _clear_caches()
    app_module._sessions["stale"] = _make_entry()
    app_module._sessions_last_accessed["stale"] = 0.0

    app_module._evict_expired_sessions(now=time.monotonic())

    assert "stale" not in app_module._sessions
    assert "stale" not in app_module._sessions_last_accessed


def test_eviction_mixes_expired_and_fresh():
    _clear_caches()
    now = time.monotonic()
    app_module._sessions["expired-1"] = _make_entry()
    app_module._sessions_last_accessed["expired-1"] = 0.0
    app_module._sessions["expired-2"] = _make_entry()
    app_module._sessions_last_accessed["expired-2"] = 1.0
    app_module._sessions["alive"] = _make_entry()
    app_module._sessions_last_accessed["alive"] = now - 60

    evicted = app_module._evict_expired_sessions(now=now)

    assert evicted == 2
    assert "expired-1" not in app_module._sessions
    assert "expired-2" not in app_module._sessions
    assert "alive" in app_module._sessions


def test_eviction_does_not_open_db_connection(monkeypatch):
    """Eviction only manipulates in-memory dicts; it must never touch PostgreSQL."""
    _clear_caches()
    db_calls: list = []

    def _fake_get_conn():
        db_calls.append(1)
        raise AssertionError("eviction must not open a DB connection")

    monkeypatch.setattr(app_module, "get_conn", _fake_get_conn)

    app_module._sessions["victim"] = _make_entry()
    app_module._sessions_last_accessed["victim"] = 0.0

    app_module._evict_expired_sessions(now=time.monotonic())

    assert "victim" not in app_module._sessions
    assert db_calls == [], "DB was accessed during eviction"


# ── _enforce_session_cache_cap ────────────────────────────────────────────────

def test_cap_evicts_oldest_entries():
    _clear_caches()
    now = time.monotonic()
    original_max = app_module._SESSION_CACHE_MAX_ENTRIES
    app_module._SESSION_CACHE_MAX_ENTRIES = 3
    try:
        for i in range(5):
            sid = f"cap-session-{i}"
            app_module._sessions[sid] = _make_entry()
            # session-0 is oldest, session-4 is newest
            app_module._sessions_last_accessed[sid] = now - (5 - i) * 100

        evicted = app_module._enforce_session_cache_cap(now=now)

        assert evicted == 2
        assert len(app_module._sessions) == 3
        assert "cap-session-0" not in app_module._sessions
        assert "cap-session-1" not in app_module._sessions
        for i in range(2, 5):
            assert f"cap-session-{i}" in app_module._sessions
    finally:
        app_module._SESSION_CACHE_MAX_ENTRIES = original_max


def test_cap_no_op_when_under_limit():
    _clear_caches()
    app_module._sessions["s1"] = _make_entry()
    app_module._sessions_last_accessed["s1"] = time.monotonic()

    evicted = app_module._enforce_session_cache_cap()

    assert evicted == 0
    assert "s1" in app_module._sessions


def test_cap_eviction_clears_both_dicts():
    _clear_caches()
    original_max = app_module._SESSION_CACHE_MAX_ENTRIES
    app_module._SESSION_CACHE_MAX_ENTRIES = 1
    try:
        now = time.monotonic()
        app_module._sessions["older"] = _make_entry()
        app_module._sessions_last_accessed["older"] = now - 200
        app_module._sessions["newer"] = _make_entry()
        app_module._sessions_last_accessed["newer"] = now - 10

        app_module._enforce_session_cache_cap(now=now)

        assert "older" not in app_module._sessions
        assert "older" not in app_module._sessions_last_accessed
        assert "newer" in app_module._sessions
    finally:
        app_module._SESSION_CACHE_MAX_ENTRIES = original_max


# ── _sweep_session_cache_once ─────────────────────────────────────────────────

def test_sweep_returns_expected_keys():
    _clear_caches()
    result = app_module._sweep_session_cache_once(now=time.monotonic())
    assert "ttl_evicted" in result
    assert "cap_evicted" in result
    assert "remaining" in result


def test_sweep_evicts_expired_leaves_fresh():
    _clear_caches()
    now = time.monotonic()
    app_module._sessions["stale"] = _make_entry()
    app_module._sessions_last_accessed["stale"] = 0.0
    app_module._sessions["fresh"] = _make_entry()
    app_module._sessions_last_accessed["fresh"] = now - 60

    result = app_module._sweep_session_cache_once(now=now)

    assert result["ttl_evicted"] == 1
    assert result["cap_evicted"] == 0
    assert "stale" not in app_module._sessions
    assert "fresh" in app_module._sessions


def test_sweep_remaining_count_is_accurate():
    _clear_caches()
    now = time.monotonic()
    for i in range(3):
        app_module._sessions[f"live-{i}"] = _make_entry()
        app_module._sessions_last_accessed[f"live-{i}"] = now - 60

    result = app_module._sweep_session_cache_once(now=now)

    assert result["remaining"] == 3


# ── _get_session_data touches session on success ──────────────────────────────

def test_get_session_data_touches_on_cache_hit():
    _clear_caches()
    session = SessionContext(track=CareerTrack.AI_PM, user_id="user-a")
    app_module._sessions["hit-sid"] = {
        "session": session, "orch": object(), "client": object(), "profile": None,
    }
    app_module._sessions_last_accessed["hit-sid"] = 0.0  # stale

    app_module._get_session_data("hit-sid", "user-a")

    assert app_module._sessions_last_accessed["hit-sid"] > 1.0


# ── _save_session touches session ─────────────────────────────────────────────

def test_save_session_touches_session():
    _clear_caches()
    session = SessionContext(track=CareerTrack.AI_PM, user_id="user-a")
    app_module._sessions_last_accessed["save-sid"] = 0.0  # stale

    app_module._save_session("save-sid", session)

    assert app_module._sessions_last_accessed["save-sid"] > 1.0


def test_save_session_in_test_mode_still_touches():
    """In TEST_MODE the DB write is a no-op, but the touch must still happen."""
    _clear_caches()
    assert app_module.TEST_MODE is True
    session = SessionContext(track=CareerTrack.AI_PM, user_id="user-a")
    app_module._sessions_last_accessed["tm-sid"] = 0.0

    app_module._save_session("tm-sid", session)

    assert app_module._sessions_last_accessed["tm-sid"] > 1.0


# ── TEST_MODE preservation ────────────────────────────────────────────────────

def test_test_mode_is_active():
    assert app_module.TEST_MODE is True


def test_eviction_functions_callable_in_test_mode():
    """Eviction helpers must be importable and callable regardless of TEST_MODE."""
    _clear_caches()
    assert callable(app_module._session_touch)
    assert callable(app_module._evict_expired_sessions)
    assert callable(app_module._enforce_session_cache_cap)
    assert callable(app_module._sweep_session_cache_once)
    # calling them in TEST_MODE must not raise
    app_module._session_touch("any-sid")
    app_module._evict_expired_sessions(now=time.monotonic())
    app_module._enforce_session_cache_cap()
    app_module._sweep_session_cache_once(now=time.monotonic())


# ── No private session content in logs ───────────────────────────────────────

def test_eviction_log_does_not_contain_session_id(caplog):
    _clear_caches()
    app_module._sessions["secret-sid"] = _make_entry("private-user")
    app_module._sessions_last_accessed["secret-sid"] = 0.0

    with caplog.at_level(logging.INFO, logger="app"):
        app_module._evict_expired_sessions(now=time.monotonic())

    for record in caplog.records:
        msg = record.getMessage()
        assert "secret-sid" not in msg
        assert "private-user" not in msg


def test_cap_eviction_log_does_not_contain_session_id(caplog):
    _clear_caches()
    original_max = app_module._SESSION_CACHE_MAX_ENTRIES
    app_module._SESSION_CACHE_MAX_ENTRIES = 0
    try:
        app_module._sessions["cap-secret"] = _make_entry("cap-user")
        app_module._sessions_last_accessed["cap-secret"] = time.monotonic()

        with caplog.at_level(logging.INFO, logger="app"):
            app_module._enforce_session_cache_cap()

        for record in caplog.records:
            msg = record.getMessage()
            assert "cap-secret" not in msg
            assert "cap-user" not in msg
    finally:
        app_module._SESSION_CACHE_MAX_ENTRIES = original_max
