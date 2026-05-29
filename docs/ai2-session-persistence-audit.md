# AI² Session Persistence Audit

## 1. Current Session Responsibilities In app.py

`app.py` still owns the runtime session boundary even though the major route handlers have moved into route modules.

Remaining session/cache/persistence responsibilities:

- `_sessions` in-memory cache for active session runtime objects.
- `SessionContext` JSON serialization and PostgreSQL write-through through `_save_session`.
- Session cache lookup, ownership checks, PostgreSQL fallback restore, and `Orchestrator` reconstruction through `_get_session_data`.
- Recent user session listing through `_get_user_sessions`.
- Permanent chat history reads and writes through `_get_user_history` and `_save_exchange_to_history`.
- Learner profile persistence bridge through `_load_profile_db` and `_save_profile_db`.
- Dormant direct session DB loader `_load_session_from_db`.
- Startup schema initialization through `_startup_db`.
- TEST_MODE session behavior, including no-op persistence, auth bypass coordination, in-memory-only sessions, mock model responses, and high rate-limit ceilings.
- Dependency wiring into `routes.deps` for split route modules.

## 2. Helper Inventory

| helper name | current location | responsibility | callers/routes depending on it | DB dependency | risk level | recommended destination |
|---|---|---|---|---|---|---|
| `_sessions` | `app.py` | Holds active session runtime dicts containing `session`, `orch`, `client`, and `profile`. | `app.py::_get_session_data`; `routes/chat.py` writes through `deps.session_cache`; `routes/dashboard.py` reads it in TEST_MODE. | None directly, but cache misses fall back to DB through `_get_session_data`. | High | Keep app-owned until an eviction policy is planned; later consider `services/session_persistence.py` or a cache-specific wrapper. |
| `_get_session_data` | `app.py` | Loads a session from `_sessions` or PostgreSQL, enforces ownership, rebuilds client/profile/orchestrator on DB restore. | `routes/onboarding.py`, `routes/dashboard.py`, `routes/chat.py`, `routes/syllabus.py`, `routes/topics.py`, `routes/submissions.py`, `routes/jobs.py`, `routes/todos.py`, `routes/debug.py`. | Reads `sessions`; calls `_load_profile_db`; creates Anthropic client outside TEST_MODE. | High | `services/session_persistence.py` after caller audit and ownership tests. |
| `_save_session` | `app.py` | Best-effort write-through of `SessionContext.to_dict()` to `sessions`. | `routes/onboarding.py`, `routes/chat.py`, `routes/syllabus.py`, `routes/topics.py`, `routes/submissions.py`, `routes/todos.py`. | Writes `sessions`; no-op in TEST_MODE. | High | `services/session_persistence.py` after `_get_session_data` contract is frozen. |
| `_get_user_sessions` | `app.py` | Lists recent sessions for a user for dashboard display. | `routes/dashboard.py`. | Reads `sessions`; returns empty list on TEST_MODE or DB failure. | Medium | `services/session_persistence.py`. |
| `_get_user_history` | `app.py` | Reads permanent conversation history for `/history`. | `routes/chat.py::history_page`. | Reads `conversation_history`; returns empty list on TEST_MODE or DB failure. | Low | `services/session_persistence.py`. |
| `_save_exchange_to_history` | `app.py` | Best-effort append of chat exchange to permanent history. | `routes/chat.py::chat`. | Writes `conversation_history`; no-op in TEST_MODE or missing user. | Medium | `services/session_persistence.py`. |
| `_load_profile_db` | `app.py` | Loads `LearnerProfile` for dashboard/start session/DB session restore. | `routes/chat.py`, `routes/dashboard.py`, `app.py::_get_session_data`. | Reads learner profile storage through `load_profile`; no-op in TEST_MODE or missing user. | Medium | `services/session_persistence.py` or a later profile persistence service. |
| `_save_profile_db` | `app.py` | Best-effort learner profile save after chat exchanges. | `routes/chat.py::chat`. | Writes learner profile storage through `save_profile`; no-op in TEST_MODE. | Medium | `services/session_persistence.py` initially; may later move to profile-specific service. |
| `_load_session_from_db` | `app.py` | Directly loads one serialized session by ID. | No current route caller found; overlaps with `_get_session_data` DB restore. | Reads `sessions`. | Low | Either remove in a later refactor if still unused or move with session DB helpers. |
| `_startup_db` | `app.py` | Runs `database/schema.sql` on first deploy when core tables are missing. | Called by `app.py` during import. | Reads information schema; may execute schema SQL outside TEST_MODE. | High | Keep in `app.py` or move to a startup/bootstrap module, not session persistence. |
| `_mock_orchestrator_response` and `_MOCK_RESPONSES` | `app.py` | Provide TEST_MODE chat/practice responses without live model calls. | `routes/chat.py` through `routes.deps`. | None. | Medium | Keep with test/runtime dependency wiring until chat test-mode ownership is separated. |
| `_session_progress` | `app.py` | Builds route response progress summary from `SessionContext`. | `routes/chat.py`, `routes/syllabus.py`, `routes/topics.py`, `routes/todos.py`, and templates through route context. | None. | Medium | Possible `services/session_persistence.py` only if grouped as session runtime helpers; otherwise a small session presentation helper module. |
| `_make_client` | `app.py` | Creates Anthropic client for session and content generation flows. | `app.py::_get_session_data`, `routes/chat.py`, `routes/topics.py`, `routes/submissions.py`. | None. | Medium | Keep outside persistence; possible future AI client factory. |
| `_run_blocking` and `_executor` | `app.py` | Runs blocking agent/service calls in a thread pool. | `routes/chat.py`, `routes/topics.py`, `routes/submissions.py`, `routes/jobs.py`. | None. | Low | Keep outside persistence; possible future runtime utility. |
| `_track_from_str` | `app.py` | Validates track strings for session creation. | `routes/chat.py::start_session`. | None. | Low | Session runtime utility, not persistence-critical. |
| `routes.deps` wiring | `app.py` and `routes/deps.py` | Exposes app-owned callables and state to split route modules. | All split routes that import `routes.deps`. | Mixed, depending on callable. | High | Continue exposing callables to route modules after moving implementations. |

## 3. Recommended Target Structure

- Create `services/session_persistence.py` for session DB/cache/history helpers.
- Keep `app.py` limited to app construction, startup, middleware, dependency wiring, and router includes.
- Continue using `routes.deps` to expose callables to route modules so route URLs and handler signatures do not change.
- Keep non-persistence runtime helpers out of `services/session_persistence.py` unless they are needed to preserve the existing callable contract during migration.

## 4. Migration Order

Recommended small migration slices:

1. Move pure/read-only helper wrappers if any, after confirming they have no startup or cache side effects.
2. Move history helpers: `_get_user_history` and `_save_exchange_to_history`.
3. Move `_get_user_sessions` and `_load_profile_db`.
4. Move `_get_session_data` and `_save_session` only after ownership, DB fallback, TEST_MODE, and route dependency tests are in place.
5. Move `_sessions` cache only with an eviction policy plan.

## 5. Risk Areas

- Session ownership: `_get_session_data` currently distinguishes cache hits, matching DB rows, missing sessions, and wrong-user access.
- Cross-user data leakage: the cache stores live `SessionContext` objects, so preserving user ownership checks is the critical safety requirement.
- TEST_MODE behavior: persistence helpers currently return no-op or empty values in TEST_MODE, while chat/session routes use in-memory cache and mock responses.
- Cookie/session_id/user_id behavior: middleware sets `request.state.user_id`, routes pass `session_id`, and helpers combine both for ownership checks.
- DB fallback behavior: cache miss restore from PostgreSQL, empty-list fallbacks, and non-fatal write failures are user-visible stability choices.
- Render smoke stability: startup DB behavior, health/login redirects, and protected route access must remain stable after any helper move.
- In-memory `_sessions` scaling risk: cache entries have no TTL, LRU cap, or multi-worker sharing, so memory growth and per-process consistency remain open risks.

## 6. Session Eviction Recommendation

After moving persistence helpers, add TTL or LRU eviction for `_sessions`.

Do not move `_sessions` blindly. First decide the eviction policy, whether entries expire by inactivity or count, and how that interacts with DB restore after process restarts or multi-worker deployments.

## 7. Test Plan

Run focused coverage around every caller before and after any implementation move:

- login/signup
- onboarding save
- dashboard load
- chat route
- topic progress
- syllabus task toggle
- session ownership tests
- DB unavailable fallback tests

Suggested existing targets to include:

- `tests/test_auth_routes_split.py`
- `tests/test_onboarding_routes_split.py`
- `tests/test_dashboard_routes_split.py`
- `tests/test_chat_routes_split.py`
- `tests/test_topics_routes.py`
- `tests/test_syllabus_routes_split.py`
- `tests/test_session_ownership.py`
- DB fallback-focused tests for learner state, curriculum, generated learning, usage events, todos, and progress where applicable.

## 8. Recommended Next Implementation Step

Move low-risk history helpers first, or create `services/session_persistence.py` with no behavior change and re-export the same callables through `routes.deps`.

The safer first implementation slice is `_get_user_history` plus `_save_exchange_to_history`, because their route surface is narrow and they already fail closed to empty/no-op behavior in TEST_MODE or DB failure.
