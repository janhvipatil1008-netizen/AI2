"""Tests for storage feature flag helpers."""

import importlib


def _import():
    import services.storage_flags as flags
    importlib.reload(flags)
    return flags


def test_all_read_flags_default_false(monkeypatch):
    for name in (
        "AI2_CURRICULUM_DB_READS_ENABLED",
        "AI2_MODULAR_CURRICULUM_READS_ENABLED",
        "AI2_PROGRESS_DB_READS_ENABLED",
        "AI2_TODOS_DB_READS_ENABLED",
    ):
        monkeypatch.delenv(name, raising=False)

    flags = _import()

    assert flags.is_curriculum_db_reads_enabled() is False
    assert flags.is_modular_curriculum_reads_enabled() is False
    assert flags.is_progress_db_reads_enabled() is False
    assert flags.is_todos_db_reads_enabled() is False


def test_truthy_values_work_for_each_read_flag(monkeypatch):
    flags = _import()
    helpers = {
        "AI2_CURRICULUM_DB_READS_ENABLED": flags.is_curriculum_db_reads_enabled,
        "AI2_MODULAR_CURRICULUM_READS_ENABLED": flags.is_modular_curriculum_reads_enabled,
        "AI2_PROGRESS_DB_READS_ENABLED": flags.is_progress_db_reads_enabled,
        "AI2_TODOS_DB_READS_ENABLED": flags.is_todos_db_reads_enabled,
    }

    for name, helper in helpers.items():
        for value in ("1", "true", "TRUE", "yes", "on", " On "):
            monkeypatch.setenv(name, value)
            assert helper() is True


def test_falsy_and_unknown_values_return_false(monkeypatch):
    flags = _import()
    helpers = {
        "AI2_CURRICULUM_DB_READS_ENABLED": flags.is_curriculum_db_reads_enabled,
        "AI2_MODULAR_CURRICULUM_READS_ENABLED": flags.is_modular_curriculum_reads_enabled,
        "AI2_PROGRESS_DB_READS_ENABLED": flags.is_progress_db_reads_enabled,
        "AI2_TODOS_DB_READS_ENABLED": flags.is_todos_db_reads_enabled,
    }

    for name, helper in helpers.items():
        for value in ("", "0", "false", "no", "off", "enabled", "2"):
            monkeypatch.setenv(name, value)
            assert helper() is False


def test_is_truthy_env_flag_reads_named_flag(monkeypatch):
    flags = _import()
    monkeypatch.setenv("AI2_CUSTOM_TEST_FLAG", "yes")

    assert flags.is_truthy_env_flag("AI2_CUSTOM_TEST_FLAG") is True
    assert flags.is_truthy_env_flag("AI2_MISSING_TEST_FLAG") is False


def test_write_through_flag_uses_same_truthy_behavior(monkeypatch):
    flags = _import()

    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "on")
    assert flags.is_db_write_through_enabled() is True

    monkeypatch.setenv("AI2_DB_WRITE_THROUGH_ENABLED", "off")
    assert flags.is_db_write_through_enabled() is False


def test_modular_curriculum_flag_specific_values(monkeypatch):
    flags = _import()
    name = "AI2_MODULAR_CURRICULUM_READS_ENABLED"

    monkeypatch.delenv(name, raising=False)
    assert flags.is_modular_curriculum_reads_enabled() is False

    for value in ("true", "1", "yes", "on", " TRUE ", " On "):
        monkeypatch.setenv(name, value)
        assert flags.is_modular_curriculum_reads_enabled() is True

    for value in ("false", "0", "no", "random", "enabled"):
        monkeypatch.setenv(name, value)
        assert flags.is_modular_curriculum_reads_enabled() is False
