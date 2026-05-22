"""Tests for scripts/seed_curriculum.py.

All tests run without a real database connection.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure the scripts directory is importable
SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "seed_curriculum.py"


def _import_script():
    """Import seed_curriculum as a module (adds scripts/ to sys.path temporarily)."""
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    # Force fresh import each time to avoid caching issues
    if "seed_curriculum" in sys.modules:
        del sys.modules["seed_curriculum"]
    import seed_curriculum
    return seed_curriculum


# ── File existence ────────────────────────────────────────────────────────────

def test_script_file_exists():
    assert SCRIPT_PATH.exists(), f"seed_curriculum.py not found at {SCRIPT_PATH}"


# ── Import without DB connection ──────────────────────────────────────────────

def test_script_imports_without_db_connection():
    """Importing the script must not connect to any database."""
    mod = _import_script()
    assert mod is not None


def test_script_does_not_call_main_at_import():
    """main() must not execute during import."""
    # If main() ran at import, it would raise RuntimeError (no DB URL in test env)
    # or sys.exit(1). The fact that import succeeds proves it did not run.
    mod = _import_script()
    assert callable(mod.main)


# ── Structure checks ──────────────────────────────────────────────────────────

def test_script_has_main_function():
    mod = _import_script()
    assert hasattr(mod, "main")
    assert callable(mod.main)


def test_script_has_run_seed_function():
    mod = _import_script()
    assert hasattr(mod, "run_seed")
    assert callable(mod.run_seed)


def test_script_source_contains_if_name_main_guard():
    src = SCRIPT_PATH.read_text(encoding="utf-8")
    assert 'if __name__ == "__main__"' in src


def test_script_source_references_build_curriculum_seed_export():
    src = SCRIPT_PATH.read_text(encoding="utf-8")
    assert "build_curriculum_seed_export" in src


def test_script_source_references_seed_curriculum_export():
    src = SCRIPT_PATH.read_text(encoding="utf-8")
    assert "seed_curriculum_export" in src


def test_script_source_does_not_read_env_at_module_level():
    """os.environ / os.getenv must only be accessed inside functions."""
    src = SCRIPT_PATH.read_text(encoding="utf-8")
    # The script delegates env reading to database.pool._connect which
    # is only called inside _get_connection() — itself called inside main().
    # Verify no top-level os.environ or os.getenv call in the script itself.
    assert "os.environ" not in src
    assert "os.getenv" not in src


def test_script_source_does_not_call_psycopg2_connect_at_module_level():
    src = SCRIPT_PATH.read_text(encoding="utf-8")
    # psycopg2.connect must not appear as a bare module-level call
    assert "psycopg2.connect(" not in src


# ── run_seed with fake connection ─────────────────────────────────────────────

class FakeCursor:
    def __init__(self):
        self.executed = []

    def execute(self, sql, params=()):
        self.executed.append((sql.strip(), params))

    def fetchone(self):
        return None

    def fetchall(self):
        return []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class FakeConn:
    def __init__(self):
        self.cursor_obj = FakeCursor()
        self.committed = False
        self.rolled_back = False

    def cursor(self, **kwargs):
        return self.cursor_obj

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        pass


def test_run_seed_accepts_fake_connection():
    """run_seed(conn) must not raise when given a fake connection."""
    mod = _import_script()
    conn = FakeConn()
    result = mod.run_seed(conn)
    assert isinstance(result, dict)


def test_run_seed_returns_counts_dict():
    mod = _import_script()
    conn = FakeConn()
    result = mod.run_seed(conn)
    assert "tracks" in result
    assert "modules" in result
    assert "topics" in result


def test_run_seed_counts_are_non_negative():
    mod = _import_script()
    conn = FakeConn()
    result = mod.run_seed(conn)
    assert result["tracks"] >= 0
    assert result["modules"] >= 0
    assert result["topics"] >= 0


def test_run_seed_executes_sql_against_connection():
    """Verify run_seed actually drives DB calls through the connection."""
    mod = _import_script()
    conn = FakeConn()
    mod.run_seed(conn)
    # At minimum the SELECT for track lookup should have been executed
    assert len(conn.cursor_obj.executed) > 0


# ── main() with monkeypatched connection ─────────────────────────────────────

def test_main_commits_on_success(capsys):
    mod = _import_script()
    fake_conn = FakeConn()

    with patch.object(mod, "_get_connection", return_value=fake_conn):
        mod.main()

    assert fake_conn.committed
    captured = capsys.readouterr()
    assert "Tracks" in captured.out
    assert "Modules" in captured.out
    assert "Topics" in captured.out
    assert "Done" in captured.out


def test_main_rolls_back_on_error(capsys):
    mod = _import_script()
    fake_conn = FakeConn()

    def _failing_run_seed(conn):
        raise RuntimeError("simulated DB failure")

    with patch.object(mod, "_get_connection", return_value=fake_conn):
        with patch.object(mod, "run_seed", side_effect=_failing_run_seed):
            try:
                mod.main()
            except SystemExit as exc:
                assert exc.code == 1

    assert fake_conn.rolled_back


def test_main_exits_nonzero_when_no_db(monkeypatch):
    mod = _import_script()

    def _fail_connect():
        raise RuntimeError("SUPABASE_DATABASE_URL env var is not set")

    with patch.object(mod, "_get_connection", side_effect=_fail_connect):
        try:
            mod.main()
            assert False, "main() should have called sys.exit(1)"
        except SystemExit as exc:
            assert exc.code == 1
