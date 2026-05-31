from __future__ import annotations

import importlib
import inspect
from unittest.mock import MagicMock, patch

import pytest

import database.pool as pool


TEST_DATABASE_URL = "postgresql://test_user:test_pass@db.example.com:6543/appdb"


@pytest.fixture(autouse=True)
def reset_pool_state(monkeypatch):
    monkeypatch.setattr(pool, "DATABASE_URL", TEST_DATABASE_URL)
    pool._pool = None
    yield
    pool._pool = None


def _mock_pool():
    fake_pool = MagicMock()
    fake_conn = MagicMock()
    fake_pool.getconn.return_value = fake_conn
    return fake_pool, fake_conn


def test_pool_module_imports_without_opening_connection(monkeypatch):
    with patch.object(pool.psycopg2, "connect", side_effect=AssertionError("connect called")) as connect:
        with patch.object(
            pool.psycopg2.pool,
            "ThreadedConnectionPool",
            side_effect=AssertionError("pool initialized"),
        ) as threaded_pool:
            reloaded_pool = importlib.reload(pool)

    assert reloaded_pool._pool is None
    connect.assert_not_called()
    threaded_pool.assert_not_called()


def test_get_conn_initializes_pool_lazily(monkeypatch):
    monkeypatch.setattr(pool, "DATABASE_URL", TEST_DATABASE_URL)
    fake_pool, fake_conn = _mock_pool()

    with patch.object(pool.psycopg2.pool, "ThreadedConnectionPool", return_value=fake_pool) as constructor:
        assert pool._pool is None

        with pool.get_conn() as conn:
            assert conn is fake_conn

    assert pool._pool is fake_pool
    constructor.assert_called_once()
    args, kwargs = constructor.call_args
    assert args == (pool.DB_POOL_MINCONN, pool.DB_POOL_MAXCONN)
    assert kwargs["host"] == "db.example.com"
    assert kwargs["port"] == 6543
    assert kwargs["dbname"] == "appdb"
    assert kwargs["user"] == "test_user"
    assert kwargs["password"] == "test_pass"
    assert kwargs["connect_timeout"] == 10
    assert kwargs["sslmode"] == "require"


def test_get_conn_commits_on_success(monkeypatch):
    monkeypatch.setattr(pool, "DATABASE_URL", TEST_DATABASE_URL)
    fake_pool, fake_conn = _mock_pool()

    with patch.object(pool.psycopg2.pool, "ThreadedConnectionPool", return_value=fake_pool):
        with pool.get_conn() as conn:
            assert conn is fake_conn

    fake_conn.commit.assert_called_once_with()
    fake_conn.rollback.assert_not_called()


def test_get_conn_rolls_back_on_exception(monkeypatch):
    monkeypatch.setattr(pool, "DATABASE_URL", TEST_DATABASE_URL)
    fake_pool, fake_conn = _mock_pool()

    with patch.object(pool.psycopg2.pool, "ThreadedConnectionPool", return_value=fake_pool):
        with pytest.raises(ValueError):
            with pool.get_conn():
                raise ValueError("boom")

    fake_conn.rollback.assert_called_once_with()
    fake_conn.commit.assert_not_called()


def test_get_conn_returns_connection_to_pool_with_putconn(monkeypatch):
    monkeypatch.setattr(pool, "DATABASE_URL", TEST_DATABASE_URL)
    fake_pool, fake_conn = _mock_pool()

    with patch.object(pool.psycopg2.pool, "ThreadedConnectionPool", return_value=fake_pool):
        with pool.get_conn():
            pass

    fake_pool.putconn.assert_called_once_with(fake_conn)
    fake_conn.close.assert_not_called()


def test_get_conn_putconn_runs_after_exception(monkeypatch):
    monkeypatch.setattr(pool, "DATABASE_URL", TEST_DATABASE_URL)
    fake_pool, fake_conn = _mock_pool()

    with patch.object(pool.psycopg2.pool, "ThreadedConnectionPool", return_value=fake_pool):
        with pytest.raises(RuntimeError):
            with pool.get_conn():
                raise RuntimeError("boom")

    fake_pool.putconn.assert_called_once_with(fake_conn)


def test_get_conn_preserves_exception_propagation(monkeypatch):
    monkeypatch.setattr(pool, "DATABASE_URL", TEST_DATABASE_URL)
    fake_pool, _fake_conn = _mock_pool()
    expected = RuntimeError("original error")

    with patch.object(pool.psycopg2.pool, "ThreadedConnectionPool", return_value=fake_pool):
        with pytest.raises(RuntimeError) as excinfo:
            with pool.get_conn():
                raise expected

    assert excinfo.value is expected


def test_close_all_connections_closes_pool_and_resets_it():
    fake_pool = MagicMock()
    pool._pool = fake_pool

    pool.close_all_connections()

    fake_pool.closeall.assert_called_once_with()
    assert pool._pool is None


def test_get_conn_public_api_remains_contextmanager_compatible():
    assert list(inspect.signature(pool.get_conn).parameters) == []

    conn_context = pool.get_conn()

    assert hasattr(conn_context, "__enter__")
    assert hasattr(conn_context, "__exit__")
