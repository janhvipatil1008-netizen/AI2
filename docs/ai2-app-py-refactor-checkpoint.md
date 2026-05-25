# AI² app.py Refactor Checkpoint

## 1. Routes Already Split

The current checkpoint confirms these route groups have been moved out of `app.py`:

| split area | file | routes/helpers now owned there |
|---|---|---|
| public routes split | `routes/public.py` | `GET /`, `GET /health`, `GET /privacy`, `GET /terms` |
| onboarding routes split | `routes/onboarding.py` | `GET /onboarding/{session_id}`, `POST /onboarding/save`, `_onboarding_template_context`, `_ensure_onboarding_course_enrollment` |
| dashboard route split | `routes/dashboard.py` | `GET /dashboard`, `build_dashboard_learning_summary`, `_dashboard_enrollment_summary`, `_disabled_dashboard_enrollment_summary`, `_disabled_dashboard_modular_progress_summary`, `_dashboard_db_summaries` |

`routes/deps.py` is the current bridge for split route modules. It holds app-populated references such as `templates`, `get_session_data`, `get_user_sessions`, `load_profile_db`, `save_session`, `session_progress`, `make_client`, `run_blocking`, `session_cache`, and `TEST_MODE`. It also owns shared route helpers for write-through behavior, DB-first/fallback reads, content cache access, usage limits, and modular progress summary reads.

## 2. What Still Remains In app.py

### App startup and middleware

- `FastAPI` app construction, static mount, `Jinja2Templates`, rate limiter setup, `_CHAT_RATE_LIMIT`, `_PRACTICE_RATE_LIMIT`.
- `TEST_MODE` detection and `assert_test_mode_off()`.
- `_startup_db`, which applies `database/schema.sql` when tables are missing outside test mode.
- `_PUBLIC_PATHS` and `auth_middleware`, including the auth allowlist and `/static` bypass behavior.

### Session persistence helpers

- `_sessions` in-memory session cache and `_executor`.
- `_save_session`, `_save_exchange_to_history`, `_save_profile_db`, `_load_profile_db`, `_load_session_from_db`.
- `_get_user_sessions` and `_get_user_history`.
- `_get_session_data`, including cache lookup, DB restore, and ownership checks.
- `_session_progress`, `_track_from_str`, `_make_client`, and `_run_blocking`.

### Pydantic request models

- `StartSessionRequest`
- `ChatRequest`
- `QuizRequest`
- `InterviewRequest`
- `EvaluateRequest`
- `TaskToggleRequest`

### TEST_MODE mock block

- `_MOCK_RESPONSES`
- `_mock_orchestrator_response`

These remain coupled to chat/practice runtime behavior and should not move until the chat/session route boundary is planned.

### Auth routes

- `GET /login`
- `POST /login`
- `GET /signup`
- `POST /signup`
- `GET /logout`

These still use auth cookies, password hashing/verification, `users` DB reads/writes, redirects to `/dashboard`, and `get_cookie_secure()`.

### Debug endpoints

Remaining debug routes include:

- `GET /debug/storage-status`
- `GET /debug/storage-health`
- `GET /debug/storage-health-view`
- `GET /debug/curriculum-db-check`
- `GET /debug/curriculum-fallback-check`
- `GET /debug/learner-state-db-check`
- `GET /debug/generated-learning-db-check`
- `GET /debug/usage-events-db-check`
- `GET /debug/usage-events-mismatch-check`
- `GET /debug/generated-learning-mismatch-check`
- `GET /debug/learner-state-mismatch-check`
- `GET /debug/learner-state-fallback-check`
- `GET /debug/modular-curriculum`

Related helpers also remain in `app.py`, including `_debug_access`, `_build_storage_health_payload`, `_storage_health_overall_status`, `_storage_health_session_status`, `_storage_health_completed_topics_count`, `_storage_health_topic_status`, `_empty_generated_learning_state_found`, `_generated_learning_state_found`, `_safe_debug_error_message`, `_safe_debug_limit`, and `_flatten_generated_learning_found`.

### Admin/beta metrics

- `GET /admin/beta-metrics`

This remains in `app.py` and depends on `_debug_access`, beta metrics services, templates, and `TEST_MODE` context.

### Chat and practice routes

- `POST /session/start`
- `POST /chat`
- `GET /progress/{session_id}`
- `POST /quiz`
- `POST /interview`
- `POST /evaluate`
- `GET /chat/{session_id}`

These remain strongly coupled to `_get_session_data`, `_save_session`, `_save_exchange_to_history`, `_save_profile_db`, `_make_client`, `_run_blocking`, `Orchestrator`, `practice_arena`, `SessionContext`, `LearnerProfile`, rate limits, and TEST_MODE mocks.

### Syllabus routes

- `GET /syllabus/{session_id}`
- `POST /task/toggle`

These remain coupled to session loading/saving, `WEEKS`, `ROLE_TRACKS`, `get_task_key`, `syllabus_get_progress`, and `_session_progress`.

### Jobs routes

- `GET /jobs`
- `GET /jobs/{job_id}`
- `GET /api/jobs/health`
- `POST /api/jobs/enrich/{job_id}`
- `POST /api/jobs/refresh`

These remain in `app.py` and depend on job repository helpers imported earlier in the file, templates, request user/session context, background task scheduling, and `_run_blocking`.

### Router includes and dependency wiring

The bottom of `app.py` still populates `routes.deps` and includes routers:

- `routes.public`
- `routes.onboarding`
- `routes.dashboard`
- `routes.topics`
- `routes.todos`
- `routes.submissions`

The dependency wiring block is still the central handoff point for shared route state.

## 3. Recommended Next Split

Recommended next split: move auth routes into `routes/auth.py` if the auth middleware allowlist is updated deliberately and covered by focused tests.

Why this is the safest next candidate:

- The auth route group is compact: login page, login submit, signup page, signup submit, and logout.
- The templates and route URLs are stable and easy to assert.
- The DB behavior is narrow: `users` lookup/insert plus duplicate email handling.
- Runtime dependencies can be passed through `routes.deps` or imported directly with limited surface area.

If auth feels too sensitive because of cookie/security behavior, the next safest alternative is a syllabus split into `routes/syllabus.py`, covering `GET /syllabus/{session_id}` and `POST /task/toggle`. Syllabus is more session-coupled but has less security surface.

Do not move debug routes next unless a dependency plan is clear. The debug area is large, token-protected, and has many specialized DB/service helpers.

## 4. Risk Notes

- Auth middleware allowlist risk: moving auth routes requires keeping `/login`, `/signup`, `/logout`, `/privacy`, `/terms`, `/health`, `/`, and `/static` access semantics intact. A route move must not accidentally block login/signup or expose protected routes.
- Debug token protection risk: debug and admin endpoints depend on `_debug_access` and `is_debug_access_allowed`. Moving them without preserving dependency behavior could expose internal state or break production-safe 404 behavior.
- Session persistence coupling: `_get_session_data`, `_save_session`, `_sessions`, profile loading, and ownership checks are shared by chat, dashboard, onboarding, topics, todos, submissions, syllabus, and jobs enrichment. These should remain centralized until a clear session dependency module exists.
- DB helpers coupling: `get_conn`, `_startup_db`, profile/session persistence, auth user DB reads/writes, dashboard enrollment reads, debug DB checks, and jobs repositories currently cross route boundaries.
- route URL stability: every split must preserve exact paths, HTTP methods, response classes, redirects, and template context variables.

## 5. Test Plan For Next Split

For an auth split, run focused tests:

- `tests/test_production_auth_config.py`
- `tests/test_session_ownership.py`
- `tests/test_privacy_terms_pages.py`
- `tests/test_smoke.py`
- `tests/test_onboarding_flow.py`
- a new `tests/test_auth_routes_split.py`

For a syllabus split alternative, run:

- `tests/test_onboarding_flow.py`
- `tests/test_navigation.py`
- `tests/test_session.py`
- `tests/test_week_compatibility_markers.py`
- a new `tests/test_syllabus_routes_split.py`

For any future debug split, run the relevant debug-focused files:

- `tests/test_debug_endpoint_protection.py`
- `tests/test_storage_status_endpoint.py`
- `tests/test_storage_health_endpoint.py`
- `tests/test_storage_health_view.py`
- `tests/test_curriculum_db_check_endpoint.py`
- `tests/test_curriculum_fallback_endpoint.py`
- `tests/test_learner_state_db_check_endpoint.py`
- `tests/test_learner_state_fallback_endpoint.py`
- `tests/test_learner_state_mismatch_endpoint.py`
- `tests/test_generated_learning_db_check_endpoint.py`
- `tests/test_generated_learning_mismatch_endpoint.py`
- `tests/test_usage_events_db_check_endpoint.py`
- `tests/test_usage_events_mismatch_endpoint.py`
