"""Content cache service for shared canonical AI-generated learning content.

Wraps content_cache_repository helpers with content-type normalisation and
eligibility checks.  Personalised feedback (quiz/portfolio/interview/reflection)
is never stored in the shared cache.

Design constraints
------------------
- Never opens a DB connection — callers pass one in.
- Never commits or rolls back — that is the caller's responsibility.
- Never mutates SessionContext.
- Never reads environment variables.
- Never makes Claude/provider calls.
- Not yet wired into routes or content generation services.
"""

from __future__ import annotations

DEFAULT_CACHE_LANGUAGE = "en"
DEFAULT_CACHE_LEVEL    = "beginner"
DEFAULT_CACHE_VERSION  = "v1"

# Content types that produce shared canonical content (safe to cache globally).
_SHARED_CACHE_TYPES = frozenset({
    "base_lesson",
    "practice_task",
    "quiz_template",
    "interview_questions",
})

# Content types that are personalised feedback (must NOT be cached globally).
_PERSONALISED_TYPES = frozenset({
    "quiz_feedback",
    "portfolio_feedback",
    "interview_feedback",
    "reflection_feedback",
})

# Aliases that callers may use and their canonical equivalents.
_CONTENT_TYPE_ALIASES: dict[str, str] = {
    "lesson":            "base_lesson",
    "learning_content":  "base_lesson",
    "content":           "base_lesson",
    "practice":          "practice_task",
    "practice_content":  "practice_task",
}


def normalize_content_type(content_type: str) -> str:
    """Return the canonical content_type string.

    Lowercases, strips whitespace, and maps legacy aliases to their canonical
    equivalents.  Unknown values are returned lowercased and stripped.
    """
    normalised = content_type.strip().lower()
    return _CONTENT_TYPE_ALIASES.get(normalised, normalised)


def should_use_shared_cache(content_type: str) -> bool:
    """Return True when content_type is eligible for the shared canonical cache.

    Personalised feedback types always return False.  Only reusable base
    content types (base_lesson, practice_task, quiz_template,
    interview_questions) return True.
    """
    return normalize_content_type(content_type) in _SHARED_CACHE_TYPES


def build_cache_lookup(
    *,
    track_key: str | None,
    legacy_topic_id: str,
    content_type: str,
    difficulty_level: str = DEFAULT_CACHE_LEVEL,
    language: str = DEFAULT_CACHE_LANGUAGE,
    version: str = DEFAULT_CACHE_VERSION,
) -> dict:
    """Return a dict of all normalised cache dimensions including the cache_key.

    The returned dict has the shape::

        {
            "cache_key":        "track:aipm|topic:rag-basics|...",
            "track_key":        "aipm",
            "legacy_topic_id":  "rag-basics",
            "content_type":     "base_lesson",
            "difficulty_level": "beginner",
            "language":         "en",
            "version":          "v1",
        }
    """
    from repositories.content_cache_repository import build_content_cache_key

    norm_type = normalize_content_type(content_type)
    cache_key = build_content_cache_key(
        track_key        = track_key,
        legacy_topic_id  = legacy_topic_id,
        content_type     = norm_type,
        difficulty_level = difficulty_level,
        language         = language,
        version          = version,
    )
    return {
        "cache_key":        cache_key,
        "track_key":        track_key,
        "legacy_topic_id":  legacy_topic_id,
        "content_type":     norm_type,
        "difficulty_level": difficulty_level,
        "language":         language,
        "version":          version,
    }


def get_shared_cached_content(
    conn,
    *,
    track_key: str | None,
    legacy_topic_id: str,
    content_type: str,
    difficulty_level: str = DEFAULT_CACHE_LEVEL,
    language: str = DEFAULT_CACHE_LANGUAGE,
    version: str = DEFAULT_CACHE_VERSION,
) -> dict | None:
    """Return the cached content row for the given dimensions, or None.

    Returns None immediately (without touching the DB) when the content type
    is not eligible for the shared cache.

    Repository exceptions propagate to the caller.
    """
    if not should_use_shared_cache(content_type):
        return None

    from repositories.content_cache_repository import get_cached_content

    lookup = build_cache_lookup(
        track_key        = track_key,
        legacy_topic_id  = legacy_topic_id,
        content_type     = content_type,
        difficulty_level = difficulty_level,
        language         = language,
        version          = version,
    )
    return get_cached_content(conn, cache_key=lookup["cache_key"])


def save_shared_cached_content(
    conn,
    *,
    track_key: str | None,
    legacy_topic_id: str,
    content_type: str,
    content: str,
    difficulty_level: str = DEFAULT_CACHE_LEVEL,
    language: str = DEFAULT_CACHE_LANGUAGE,
    version: str = DEFAULT_CACHE_VERSION,
    provider: str | None = None,
    model: str | None = None,
    metadata: dict | None = None,
) -> str:
    """Upsert a shared canonical content row and return the cache_key.

    Returns "" immediately (without touching the DB) when:
    - the content type is not eligible for the shared cache, or
    - content is empty or whitespace-only.

    Repository exceptions propagate to the caller.
    """
    if not should_use_shared_cache(content_type):
        return ""
    if not content or not content.strip():
        return ""

    from repositories.content_cache_repository import upsert_cached_content

    lookup = build_cache_lookup(
        track_key        = track_key,
        legacy_topic_id  = legacy_topic_id,
        content_type     = content_type,
        difficulty_level = difficulty_level,
        language         = language,
        version          = version,
    )
    upsert_cached_content(
        conn,
        cache_key        = lookup["cache_key"],
        track_key        = track_key,
        legacy_topic_id  = legacy_topic_id,
        content_type     = lookup["content_type"],
        content          = content,
        difficulty_level = difficulty_level,
        language         = language,
        version          = version,
        provider         = provider,
        model            = model,
        metadata         = metadata,
    )
    return lookup["cache_key"]


def get_or_none_from_cache(
    conn,
    *,
    track_key: str | None,
    legacy_topic_id: str,
    content_type: str,
    difficulty_level: str = DEFAULT_CACHE_LEVEL,
    language: str = DEFAULT_CACHE_LANGUAGE,
    version: str = DEFAULT_CACHE_VERSION,
) -> tuple[dict | None, dict]:
    """Return (cached_row_or_None, lookup_dict).

    Convenience helper for callers that need both the cached value and the
    fully resolved lookup dimensions in a single call.  Designed for use in
    routes once caching is wired in.

    If the content type is not cache-eligible, the first element is always
    None.  Repository exceptions propagate to the caller.
    """
    lookup = build_cache_lookup(
        track_key        = track_key,
        legacy_topic_id  = legacy_topic_id,
        content_type     = content_type,
        difficulty_level = difficulty_level,
        language         = language,
        version          = version,
    )
    if not should_use_shared_cache(lookup["content_type"]):
        return (None, lookup)

    from repositories.content_cache_repository import get_cached_content

    cached = get_cached_content(conn, cache_key=lookup["cache_key"])
    return (cached, lookup)
