"""Tests for content_cache_service.

All tests run without a real database. Repository calls are patched with
lightweight fakes so no DB connection is opened.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

SERVICE_FILE = Path(__file__).parent.parent / "services" / "content_cache_service.py"


def _src() -> str:
    return SERVICE_FILE.read_text(encoding="utf-8")


# ── Fake DB helpers ───────────────────────────────────────────────────────────

class FakeCursor:
    def __init__(self, *, fetchone_row=None, rowcount: int = 0):
        self.executed: list[tuple[str, tuple]] = []
        self._fetchone_row = fetchone_row
        self.rowcount = rowcount

    def execute(self, sql: str, params=None) -> None:
        self.executed.append((sql.strip(), params))

    def fetchone(self):
        return self._fetchone_row

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class FakeConn:
    def __init__(self, *, fetchone_row=None, rowcount: int = 0):
        self.cursor_obj = FakeCursor(fetchone_row=fetchone_row, rowcount=rowcount)
        self.commit_count = 0
        self.rollback_count = 0

    def cursor(self, **kwargs):
        return self.cursor_obj

    def commit(self):
        self.commit_count += 1

    def rollback(self):
        self.rollback_count += 1


# ── normalize_content_type ────────────────────────────────────────────────────

class TestNormalizeContentType:
    def test_lesson_maps_to_base_lesson(self):
        from services.content_cache_service import normalize_content_type
        assert normalize_content_type("lesson") == "base_lesson"

    def test_learning_content_maps_to_base_lesson(self):
        from services.content_cache_service import normalize_content_type
        assert normalize_content_type("learning_content") == "base_lesson"

    def test_content_maps_to_base_lesson(self):
        from services.content_cache_service import normalize_content_type
        assert normalize_content_type("content") == "base_lesson"

    def test_practice_maps_to_practice_task(self):
        from services.content_cache_service import normalize_content_type
        assert normalize_content_type("practice") == "practice_task"

    def test_practice_content_maps_to_practice_task(self):
        from services.content_cache_service import normalize_content_type
        assert normalize_content_type("practice_content") == "practice_task"

    def test_base_lesson_unchanged(self):
        from services.content_cache_service import normalize_content_type
        assert normalize_content_type("base_lesson") == "base_lesson"

    def test_practice_task_unchanged(self):
        from services.content_cache_service import normalize_content_type
        assert normalize_content_type("practice_task") == "practice_task"

    def test_quiz_template_unchanged(self):
        from services.content_cache_service import normalize_content_type
        assert normalize_content_type("quiz_template") == "quiz_template"

    def test_interview_questions_unchanged(self):
        from services.content_cache_service import normalize_content_type
        assert normalize_content_type("interview_questions") == "interview_questions"

    def test_strips_whitespace(self):
        from services.content_cache_service import normalize_content_type
        assert normalize_content_type("  lesson  ") == "base_lesson"

    def test_lowercases(self):
        from services.content_cache_service import normalize_content_type
        assert normalize_content_type("LESSON") == "base_lesson"

    def test_unknown_type_returned_lowercased(self):
        from services.content_cache_service import normalize_content_type
        assert normalize_content_type("CustomType") == "customtype"


# ── should_use_shared_cache ───────────────────────────────────────────────────

class TestShouldUseSharedCache:
    def test_true_for_base_lesson(self):
        from services.content_cache_service import should_use_shared_cache
        assert should_use_shared_cache("base_lesson") is True

    def test_true_for_practice_task(self):
        from services.content_cache_service import should_use_shared_cache
        assert should_use_shared_cache("practice_task") is True

    def test_true_for_quiz_template(self):
        from services.content_cache_service import should_use_shared_cache
        assert should_use_shared_cache("quiz_template") is True

    def test_true_for_interview_questions(self):
        from services.content_cache_service import should_use_shared_cache
        assert should_use_shared_cache("interview_questions") is True

    def test_true_for_lesson_alias(self):
        from services.content_cache_service import should_use_shared_cache
        assert should_use_shared_cache("lesson") is True

    def test_true_for_practice_alias(self):
        from services.content_cache_service import should_use_shared_cache
        assert should_use_shared_cache("practice") is True

    def test_false_for_quiz_feedback(self):
        from services.content_cache_service import should_use_shared_cache
        assert should_use_shared_cache("quiz_feedback") is False

    def test_false_for_portfolio_feedback(self):
        from services.content_cache_service import should_use_shared_cache
        assert should_use_shared_cache("portfolio_feedback") is False

    def test_false_for_interview_feedback(self):
        from services.content_cache_service import should_use_shared_cache
        assert should_use_shared_cache("interview_feedback") is False

    def test_false_for_reflection_feedback(self):
        from services.content_cache_service import should_use_shared_cache
        assert should_use_shared_cache("reflection_feedback") is False

    def test_false_for_unknown_type(self):
        from services.content_cache_service import should_use_shared_cache
        assert should_use_shared_cache("some_unknown_type") is False


# ── build_cache_lookup ────────────────────────────────────────────────────────

class TestBuildCacheLookup:
    def test_returns_dict_with_all_keys(self):
        from services.content_cache_service import build_cache_lookup
        result = build_cache_lookup(
            track_key="aipm",
            legacy_topic_id="rag-basics",
            content_type="base_lesson",
        )
        for key in ("cache_key", "track_key", "legacy_topic_id",
                    "content_type", "difficulty_level", "language", "version"):
            assert key in result, f"missing key: {key}"

    def test_normalizes_content_type_in_result(self):
        from services.content_cache_service import build_cache_lookup
        result = build_cache_lookup(
            track_key="aipm",
            legacy_topic_id="rag-basics",
            content_type="lesson",
        )
        assert result["content_type"] == "base_lesson"

    def test_cache_key_is_a_non_empty_string(self):
        from services.content_cache_service import build_cache_lookup
        result = build_cache_lookup(
            track_key="aipm",
            legacy_topic_id="rag-basics",
            content_type="base_lesson",
        )
        assert isinstance(result["cache_key"], str)
        assert result["cache_key"] != ""

    def test_cache_key_encodes_all_dimensions(self):
        from services.content_cache_service import build_cache_lookup
        result = build_cache_lookup(
            track_key="aipm",
            legacy_topic_id="rag-basics",
            content_type="base_lesson",
            difficulty_level="advanced",
            language="fr",
            version="v2",
        )
        key = result["cache_key"]
        assert "aipm" in key
        assert "rag-basics" in key
        assert "base_lesson" in key
        assert "advanced" in key
        assert "fr" in key
        assert "v2" in key

    def test_uses_defaults_for_optional_dimensions(self):
        from services.content_cache_service import (
            DEFAULT_CACHE_LANGUAGE,
            DEFAULT_CACHE_LEVEL,
            DEFAULT_CACHE_VERSION,
            build_cache_lookup,
        )
        result = build_cache_lookup(
            track_key="aipm",
            legacy_topic_id="rag-basics",
            content_type="base_lesson",
        )
        assert result["difficulty_level"] == DEFAULT_CACHE_LEVEL
        assert result["language"] == DEFAULT_CACHE_LANGUAGE
        assert result["version"] == DEFAULT_CACHE_VERSION

    def test_preserves_track_key_in_result(self):
        from services.content_cache_service import build_cache_lookup
        result = build_cache_lookup(
            track_key="aipm",
            legacy_topic_id="t1",
            content_type="quiz_template",
        )
        assert result["track_key"] == "aipm"

    def test_none_track_key_preserved_in_result(self):
        from services.content_cache_service import build_cache_lookup
        result = build_cache_lookup(
            track_key=None,
            legacy_topic_id="t1",
            content_type="base_lesson",
        )
        assert result["track_key"] is None

    def test_deterministic_for_same_inputs(self):
        from services.content_cache_service import build_cache_lookup
        r1 = build_cache_lookup(track_key="aipm", legacy_topic_id="t1", content_type="lesson")
        r2 = build_cache_lookup(track_key="aipm", legacy_topic_id="t1", content_type="lesson")
        assert r1["cache_key"] == r2["cache_key"]


# ── get_shared_cached_content ─────────────────────────────────────────────────

class TestGetSharedCachedContent:
    def test_returns_none_for_non_cacheable_feedback_type(self):
        from services.content_cache_service import get_shared_cached_content
        conn = FakeConn()
        result = get_shared_cached_content(
            conn,
            track_key="aipm",
            legacy_topic_id="t1",
            content_type="quiz_feedback",
        )
        assert result is None

    def test_no_db_call_for_non_cacheable_type(self):
        from services.content_cache_service import get_shared_cached_content
        conn = FakeConn()
        with patch("repositories.content_cache_repository.get_cached_content") as mock_get:
            get_shared_cached_content(
                conn,
                track_key="aipm",
                legacy_topic_id="t1",
                content_type="portfolio_feedback",
            )
            mock_get.assert_not_called()

    def test_calls_repository_for_cacheable_type(self):
        from services.content_cache_service import get_shared_cached_content
        cached_row = {"cache_key": "k1", "content": "Lesson text.", "status": "active"}
        with patch(
            "repositories.content_cache_repository.get_cached_content",
            return_value=cached_row,
        ) as mock_get:
            conn = FakeConn()
            result = get_shared_cached_content(
                conn,
                track_key="aipm",
                legacy_topic_id="rag-basics",
                content_type="base_lesson",
            )
            mock_get.assert_called_once()
        assert result == cached_row

    def test_returns_none_when_repository_returns_none(self):
        from services.content_cache_service import get_shared_cached_content
        with patch(
            "repositories.content_cache_repository.get_cached_content",
            return_value=None,
        ):
            conn = FakeConn()
            result = get_shared_cached_content(
                conn,
                track_key="aipm",
                legacy_topic_id="t1",
                content_type="practice_task",
            )
        assert result is None

    def test_alias_type_also_hits_repository(self):
        from services.content_cache_service import get_shared_cached_content
        with patch(
            "repositories.content_cache_repository.get_cached_content",
            return_value=None,
        ) as mock_get:
            conn = FakeConn()
            get_shared_cached_content(
                conn,
                track_key="aipm",
                legacy_topic_id="t1",
                content_type="lesson",
            )
            mock_get.assert_called_once()

    def test_does_not_commit(self):
        from services.content_cache_service import get_shared_cached_content
        with patch("repositories.content_cache_repository.get_cached_content", return_value=None):
            conn = FakeConn()
            get_shared_cached_content(
                conn, track_key="aipm", legacy_topic_id="t1", content_type="base_lesson"
            )
        assert conn.commit_count == 0

    def test_repository_exception_propagates(self):
        from services.content_cache_service import get_shared_cached_content
        with patch(
            "repositories.content_cache_repository.get_cached_content",
            side_effect=RuntimeError("DB exploded"),
        ):
            conn = FakeConn()
            with pytest.raises(RuntimeError, match="DB exploded"):
                get_shared_cached_content(
                    conn, track_key="aipm", legacy_topic_id="t1", content_type="base_lesson"
                )


# ── save_shared_cached_content ────────────────────────────────────────────────

class TestSaveSharedCachedContent:
    def test_skips_non_cacheable_feedback_type(self):
        from services.content_cache_service import save_shared_cached_content
        with patch("repositories.content_cache_repository.upsert_cached_content") as mock_upsert:
            conn = FakeConn()
            result = save_shared_cached_content(
                conn,
                track_key="aipm",
                legacy_topic_id="t1",
                content_type="quiz_feedback",
                content="Some feedback.",
            )
            mock_upsert.assert_not_called()
        assert result == ""

    def test_skips_blank_content(self):
        from services.content_cache_service import save_shared_cached_content
        with patch("repositories.content_cache_repository.upsert_cached_content") as mock_upsert:
            conn = FakeConn()
            for blank in ("", "   ", "\n\t"):
                result = save_shared_cached_content(
                    conn,
                    track_key="aipm",
                    legacy_topic_id="t1",
                    content_type="base_lesson",
                    content=blank,
                )
                assert result == "", f"expected '' for blank content {blank!r}"
            mock_upsert.assert_not_called()

    def test_calls_repository_for_cacheable_content(self):
        from services.content_cache_service import save_shared_cached_content
        with patch("repositories.content_cache_repository.upsert_cached_content") as mock_upsert:
            conn = FakeConn()
            result = save_shared_cached_content(
                conn,
                track_key="aipm",
                legacy_topic_id="rag-basics",
                content_type="base_lesson",
                content="Full lesson text here.",
            )
            mock_upsert.assert_called_once()
        assert result != ""
        assert "aipm" in result or "rag" in result or "base_lesson" in result

    def test_returns_cache_key_string(self):
        from services.content_cache_service import save_shared_cached_content
        with patch("repositories.content_cache_repository.upsert_cached_content"):
            conn = FakeConn()
            result = save_shared_cached_content(
                conn,
                track_key="aipm",
                legacy_topic_id="rag-basics",
                content_type="base_lesson",
                content="Lesson text.",
            )
        assert isinstance(result, str)
        assert result != ""

    def test_passes_provider_model_to_repository(self):
        from services.content_cache_service import save_shared_cached_content
        with patch("repositories.content_cache_repository.upsert_cached_content") as mock_upsert:
            conn = FakeConn()
            save_shared_cached_content(
                conn,
                track_key="aipm",
                legacy_topic_id="t1",
                content_type="practice_task",
                content="Practice instructions.",
                provider="anthropic",
                model="claude-sonnet-4-6",
            )
        _, kwargs = mock_upsert.call_args
        assert kwargs.get("provider") == "anthropic"
        assert kwargs.get("model") == "claude-sonnet-4-6"

    def test_passes_metadata_to_repository(self):
        from services.content_cache_service import save_shared_cached_content
        meta = {"tokens": 256}
        with patch("repositories.content_cache_repository.upsert_cached_content") as mock_upsert:
            conn = FakeConn()
            save_shared_cached_content(
                conn,
                track_key="aipm",
                legacy_topic_id="t1",
                content_type="base_lesson",
                content="Lesson text.",
                metadata=meta,
            )
        _, kwargs = mock_upsert.call_args
        assert kwargs.get("metadata") == meta

    def test_normalizes_alias_type_before_writing(self):
        from services.content_cache_service import save_shared_cached_content
        with patch("repositories.content_cache_repository.upsert_cached_content") as mock_upsert:
            conn = FakeConn()
            save_shared_cached_content(
                conn,
                track_key="aipm",
                legacy_topic_id="t1",
                content_type="lesson",
                content="Lesson text.",
            )
        _, kwargs = mock_upsert.call_args
        assert kwargs["content_type"] == "base_lesson"

    def test_does_not_commit(self):
        from services.content_cache_service import save_shared_cached_content
        with patch("repositories.content_cache_repository.upsert_cached_content"):
            conn = FakeConn()
            save_shared_cached_content(
                conn,
                track_key="aipm",
                legacy_topic_id="t1",
                content_type="base_lesson",
                content="Lesson text.",
            )
        assert conn.commit_count == 0

    def test_repository_exception_propagates(self):
        from services.content_cache_service import save_shared_cached_content
        with patch(
            "repositories.content_cache_repository.upsert_cached_content",
            side_effect=RuntimeError("write failed"),
        ):
            conn = FakeConn()
            with pytest.raises(RuntimeError, match="write failed"):
                save_shared_cached_content(
                    conn,
                    track_key="aipm",
                    legacy_topic_id="t1",
                    content_type="base_lesson",
                    content="Lesson text.",
                )


# ── get_or_none_from_cache ────────────────────────────────────────────────────

class TestGetOrNoneFromCache:
    def test_returns_tuple_of_two_elements(self):
        from services.content_cache_service import get_or_none_from_cache
        with patch("repositories.content_cache_repository.get_cached_content", return_value=None):
            conn = FakeConn()
            result = get_or_none_from_cache(
                conn, track_key="aipm", legacy_topic_id="t1", content_type="base_lesson"
            )
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_second_element_is_lookup_dict(self):
        from services.content_cache_service import get_or_none_from_cache
        with patch("repositories.content_cache_repository.get_cached_content", return_value=None):
            conn = FakeConn()
            _, lookup = get_or_none_from_cache(
                conn, track_key="aipm", legacy_topic_id="t1", content_type="base_lesson"
            )
        assert "cache_key" in lookup
        assert "content_type" in lookup

    def test_first_element_is_none_for_non_cacheable_type(self):
        from services.content_cache_service import get_or_none_from_cache
        conn = FakeConn()
        cached, _ = get_or_none_from_cache(
            conn, track_key="aipm", legacy_topic_id="t1", content_type="quiz_feedback"
        )
        assert cached is None

    def test_no_db_call_for_non_cacheable_type(self):
        from services.content_cache_service import get_or_none_from_cache
        with patch("repositories.content_cache_repository.get_cached_content") as mock_get:
            conn = FakeConn()
            get_or_none_from_cache(
                conn, track_key="aipm", legacy_topic_id="t1", content_type="portfolio_feedback"
            )
            mock_get.assert_not_called()

    def test_first_element_is_cached_row_when_hit(self):
        from services.content_cache_service import get_or_none_from_cache
        row = {"cache_key": "k1", "content": "Lesson text.", "status": "active"}
        with patch(
            "repositories.content_cache_repository.get_cached_content",
            return_value=row,
        ):
            conn = FakeConn()
            cached, lookup = get_or_none_from_cache(
                conn, track_key="aipm", legacy_topic_id="t1", content_type="base_lesson"
            )
        assert cached == row
        assert "cache_key" in lookup

    def test_first_element_is_none_when_cache_miss(self):
        from services.content_cache_service import get_or_none_from_cache
        with patch("repositories.content_cache_repository.get_cached_content", return_value=None):
            conn = FakeConn()
            cached, _ = get_or_none_from_cache(
                conn, track_key="aipm", legacy_topic_id="t1", content_type="base_lesson"
            )
        assert cached is None

    def test_lookup_contains_normalized_content_type(self):
        from services.content_cache_service import get_or_none_from_cache
        with patch("repositories.content_cache_repository.get_cached_content", return_value=None):
            conn = FakeConn()
            _, lookup = get_or_none_from_cache(
                conn, track_key="aipm", legacy_topic_id="t1", content_type="lesson"
            )
        assert lookup["content_type"] == "base_lesson"

    def test_does_not_commit(self):
        from services.content_cache_service import get_or_none_from_cache
        with patch("repositories.content_cache_repository.get_cached_content", return_value=None):
            conn = FakeConn()
            get_or_none_from_cache(
                conn, track_key="aipm", legacy_topic_id="t1", content_type="base_lesson"
            )
        assert conn.commit_count == 0

    def test_repository_exception_propagates(self):
        from services.content_cache_service import get_or_none_from_cache
        with patch(
            "repositories.content_cache_repository.get_cached_content",
            side_effect=RuntimeError("DB down"),
        ):
            conn = FakeConn()
            with pytest.raises(RuntimeError, match="DB down"):
                get_or_none_from_cache(
                    conn, track_key="aipm", legacy_topic_id="t1", content_type="base_lesson"
                )


# ── Source-code safety checks ─────────────────────────────────────────────────

class TestServiceSafetyConstraints:
    def test_no_os_environ_reads(self):
        src = _src()
        assert "os.environ" not in src
        assert "os.getenv" not in src

    def test_no_database_pool_import(self):
        src = _src()
        assert "database.pool" not in src
        assert "from database" not in src

    def test_no_psycopg2_connect(self):
        src = _src()
        assert "psycopg2.connect(" not in src

    def test_no_routes_or_app_imports(self):
        src = _src()
        assert "from routes" not in src
        assert "import routes" not in src
        assert "from app" not in src
        assert "import app" not in src

    def test_no_claude_api_calls(self):
        src = _src()
        assert "client.messages" not in src
        assert "make_client" not in src
        assert "anthropic.Anthropic(" not in src

    def test_no_session_context_mutation(self):
        src = _src()
        assert "session.add_todo" not in src
        assert "session.mark_topic_step" not in src
        assert "session.save_topic_notes" not in src

    def test_module_imports_safely(self):
        import services.content_cache_service  # noqa: F401

    def test_constants_exist(self):
        from services.content_cache_service import (
            DEFAULT_CACHE_LANGUAGE,
            DEFAULT_CACHE_LEVEL,
            DEFAULT_CACHE_VERSION,
        )
        assert DEFAULT_CACHE_LANGUAGE == "en"
        assert DEFAULT_CACHE_LEVEL == "beginner"
        assert DEFAULT_CACHE_VERSION == "v1"
