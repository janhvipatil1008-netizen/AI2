"""Tests for curriculum/seed_export.py.

All tests run without a database connection — this module is pure data mapping.
"""

import json

from curriculum.seed_export import (
    CurriculumSeedExport,
    ModuleSeedRecord,
    TopicSeedRecord,
    TrackSeedRecord,
    build_curriculum_seed_export,
    curriculum_seed_export_to_dict,
    export_curriculum_seed_json,
    slugify_key,
)


# ── slugify_key ───────────────────────────────────────────────────────────────

def test_slugify_key_lowercases():
    assert slugify_key("HELLO") == "hello"


def test_slugify_key_replaces_spaces_with_dash():
    assert slugify_key("hello world") == "hello-world"


def test_slugify_key_removes_special_characters():
    result = slugify_key("AI vs ML vs DL!")
    assert " " not in result
    assert "!" not in result


def test_slugify_key_collapses_multiple_non_alphanum():
    assert slugify_key("a  --  b") == "a-b"


def test_slugify_key_strips_leading_trailing_dashes():
    assert slugify_key("--hello--") == "hello"


def test_slugify_key_returns_item_for_empty_string():
    assert slugify_key("") == "item"


def test_slugify_key_returns_item_for_only_special_chars():
    assert slugify_key("!@#$") == "item"


def test_slugify_key_handles_existing_slug():
    assert slugify_key("aipm-week-1-ai-vs-ml") == "aipm-week-1-ai-vs-ml"


# ── build_curriculum_seed_export ──────────────────────────────────────────────

def test_export_returns_curriculum_seed_export():
    export = build_curriculum_seed_export()
    assert isinstance(export, CurriculumSeedExport)


def test_export_contains_at_least_one_track():
    export = build_curriculum_seed_export()
    assert len(export.tracks) >= 1


def test_export_tracks_are_track_seed_records():
    export = build_curriculum_seed_export()
    for track in export.tracks:
        assert isinstance(track, TrackSeedRecord)


def test_export_contains_modules():
    export = build_curriculum_seed_export()
    assert len(export.modules) >= 1


def test_export_modules_are_module_seed_records():
    export = build_curriculum_seed_export()
    for module in export.modules:
        assert isinstance(module, ModuleSeedRecord)


def test_export_contains_topics():
    export = build_curriculum_seed_export()
    assert len(export.topics) >= 1


def test_export_topics_are_topic_seed_records():
    export = build_curriculum_seed_export()
    for topic in export.topics:
        assert isinstance(topic, TopicSeedRecord)


# ── Track record fields ───────────────────────────────────────────────────────

def test_track_keys_are_non_empty():
    export = build_curriculum_seed_export()
    for track in export.tracks:
        assert track.track_key, f"empty track_key on track: {track}"


def test_track_titles_are_non_empty():
    export = build_curriculum_seed_export()
    for track in export.tracks:
        assert track.title, f"empty title on track: {track.track_key}"


def test_known_tracks_are_present():
    export = build_curriculum_seed_export()
    keys = {t.track_key for t in export.tracks}
    assert "aipm" in keys


# ── Module record fields ──────────────────────────────────────────────────────

def test_module_keys_are_non_empty():
    export = build_curriculum_seed_export()
    for module in export.modules:
        assert module.module_key, f"empty module_key: {module}"


def test_module_sequence_orders_are_ints():
    export = build_curriculum_seed_export()
    for module in export.modules:
        assert isinstance(module.sequence_order, int), (
            f"sequence_order is not int for module {module.module_key}"
        )


def test_module_track_keys_match_known_tracks():
    export = build_curriculum_seed_export()
    track_keys = {t.track_key for t in export.tracks}
    for module in export.modules:
        assert module.track_key in track_keys, (
            f"module.track_key '{module.track_key}' not in track keys"
        )


def test_modules_have_titles():
    export = build_curriculum_seed_export()
    for module in export.modules:
        assert module.title, f"empty title on module {module.module_key}"


# ── Topic record fields ───────────────────────────────────────────────────────

def test_topic_keys_are_non_empty():
    export = build_curriculum_seed_export()
    for topic in export.topics:
        assert topic.topic_key, f"empty topic_key: {topic.title}"


def test_topic_keys_are_valid_slugs():
    export = build_curriculum_seed_export()
    import re
    for topic in export.topics:
        assert re.match(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$", topic.topic_key), (
            f"invalid topic_key slug: '{topic.topic_key}'"
        )


def test_topic_legacy_topic_ids_are_non_empty():
    export = build_curriculum_seed_export()
    for topic in export.topics:
        assert topic.legacy_topic_id, f"empty legacy_topic_id for topic: {topic.title}"


def test_topic_key_matches_slugified_legacy_topic_id():
    export = build_curriculum_seed_export()
    for topic in export.topics:
        assert topic.topic_key == slugify_key(topic.legacy_topic_id), (
            f"topic_key '{topic.topic_key}' != slugify('{topic.legacy_topic_id}')"
        )


def test_topic_sequence_orders_are_ints():
    export = build_curriculum_seed_export()
    for topic in export.topics:
        assert isinstance(topic.sequence_order, int)


def test_topic_freshness_labels_are_non_empty():
    export = build_curriculum_seed_export()
    for topic in export.topics:
        assert topic.freshness_label, f"empty freshness_label for topic: {topic.title}"


def test_topic_module_keys_match_module_records():
    export = build_curriculum_seed_export()
    module_keys = {(m.track_key, m.module_key) for m in export.modules}
    for topic in export.topics:
        assert (topic.track_key, topic.module_key) in module_keys, (
            f"topic references unknown module: ({topic.track_key}, {topic.module_key})"
        )


def test_topic_titles_are_non_empty():
    export = build_curriculum_seed_export()
    for topic in export.topics:
        assert topic.title, "topic has empty title"


# ── JSON serialization ────────────────────────────────────────────────────────

def test_curriculum_seed_export_to_dict_is_json_serializable():
    export = build_curriculum_seed_export()
    data = curriculum_seed_export_to_dict(export)
    # Must not raise
    json_str = json.dumps(data)
    assert json_str


def test_curriculum_seed_export_to_dict_has_expected_keys():
    data = curriculum_seed_export_to_dict(build_curriculum_seed_export())
    assert set(data.keys()) == {"tracks", "modules", "topics"}


def test_curriculum_seed_export_to_dict_counts_match():
    export = build_curriculum_seed_export()
    data = curriculum_seed_export_to_dict(export)
    assert len(data["tracks"]) == len(export.tracks)
    assert len(data["modules"]) == len(export.modules)
    assert len(data["topics"]) == len(export.topics)


# ── export_curriculum_seed_json ───────────────────────────────────────────────

def test_export_curriculum_seed_json_writes_file(tmp_path):
    out = tmp_path / "curriculum_seed.json"
    result = export_curriculum_seed_json(out)
    assert result == out
    assert out.exists()


def test_export_curriculum_seed_json_writes_valid_json(tmp_path):
    out = tmp_path / "curriculum_seed.json"
    export_curriculum_seed_json(out)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert "tracks" in data
    assert "modules" in data
    assert "topics" in data


def test_export_curriculum_seed_json_is_pretty_printed(tmp_path):
    out = tmp_path / "curriculum_seed.json"
    export_curriculum_seed_json(out)
    content = out.read_text(encoding="utf-8")
    # Pretty-printed JSON has newlines and indentation
    assert "\n" in content
    assert "  " in content


# ── No database connection required ──────────────────────────────────────────

def test_seed_export_module_has_no_db_imports():
    """Verify seed_export.py source does not import any DB libraries."""
    from pathlib import Path
    source = (Path(__file__).parent.parent / "curriculum" / "seed_export.py").read_text()
    for db_lib in ("psycopg2", "asyncpg", "sqlalchemy", "database.connection", "pg8000"):
        assert db_lib not in source, f"seed_export.py must not import '{db_lib}'"
