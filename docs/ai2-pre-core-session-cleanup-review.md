# AI² Pre-Core Session Cleanup Review

## 1. Current Status

`git status --short` was clean before this review started.

Route splitting is complete, and the debug/admin split is complete. `services/session_persistence.py` now owns the lower-risk persistence helpers:

- `get_user_history`
- `save_exchange_to_history`
- `get_user_sessions`
- `load_profile_db`
- `save_profile_db`

`app.py` still owns the high-risk core session helpers that control in-memory session state and persistence boundaries.

## 2. Tests Run

Focused regression command:

```bash
python -m pytest tests/test_session_history_persistence_split.py tests/test_session_profile_listing_persistence_split.py tests/test_chat_routes_split.py tests/test_dashboard_routes_split.py tests/test_auth_routes_split.py tests/test_onboarding_routes_split.py tests/test_syllabus_routes_split.py tests/test_topics_routes.py tests/test_todo_routes.py tests/test_session_ownership.py
```

Focused regression result:

- `158 passed`
- `2 failed`
- `5 warnings`
- Runtime: `52.92s`

Failures:

- `tests/test_onboarding_routes_split.py::test_app_py_still_has_debug_route`
- `tests/test_syllabus_routes_split.py::test_non_syllabus_routes_not_moved_in_this_step`

Both failures assert that `@app.get("/debug/storage-status")` still appears directly in `app.py`. That expectation is stale because debug/admin route splitting is already complete.

## 3. Remaining Core Session Helpers

The remaining core session helpers in `app.py` are:

- `_sessions`
- `_get_session_data`
- `_save_session`

These helpers should be treated as high risk because they sit on the boundary between request ownership, cached session state, and persistent session storage.

## 4. Risk Review

Session ownership remains the primary risk. Any movement of `_get_session_data` or `_save_session` must preserve the current checks that prevent one authenticated user from reading, mutating, or saving another user's session.

Cross-user leakage risk is tightly coupled to the `_sessions` cache. The cache currently lives in `app.py`, and moving it without an explicit eviction and ownership model could make leaks harder to reason about.

DB fallback behavior must remain unchanged. The current code paths must continue to tolerate unavailable database state and preserve existing fallback semantics for local/test usage.

`TEST_MODE` behavior must remain stable. Session creation, loading, saving, and fallback paths often behave differently under test flags, so extraction must not change how tests isolate users or storage.

Onboarding, dashboard, chat, topics, and todos depend on these helpers directly or indirectly. A core session extraction can regress enrollment state, dashboard summaries, chat history, topic progress, or todo persistence even when route URLs remain unchanged.

Render stability depends on conservative movement. The next implementation must avoid changing route URLs, environment handling, startup behavior, or production database fallback behavior.

## 5. Cleanup Findings

No pre-existing untracked files, temp files, or local artifacts were reported by `git status --short` before this review.

This review intentionally adds only:

- `docs/ai2-pre-core-session-cleanup-review.md`
- `tests/test_pre_core_session_cleanup_review.py`

No files were deleted, moved, staged, committed, or pushed.

## 6. Recommendation

Move `_get_session_data` and `_save_session` only after this checkpoint is reviewed and the focused regression is either passing or the stale split-guard expectations are intentionally updated.

Keep `_sessions` cache in `app.py` until an eviction policy is designed. The cache needs an explicit ownership, lifetime, and invalidation model before it is moved into a service boundary.
