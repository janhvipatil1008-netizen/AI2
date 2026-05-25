# AI² Dashboard Route Split Audit

## 1. Dashboard Responsibilities

The current `GET /dashboard` handler in `app.py` renders the learner home page without changing learner state. It determines the current user, best-effort loads the user's display name, reads recent sessions, loads the learner profile, selects the most recent session, builds legacy `SessionContext` learning statistics, reads enrollment and modular progress summaries from the DB when enough user/session context exists, derives a current position summary, and renders `templates/dashboard.html`.

The route must stay read-only. Existing tests assert it does not call Claude, does not run seed scripts, does not commit or rollback read-only DB connections, hides DB errors from learners, and keeps the route URL as `GET /dashboard`.

## 2. Dashboard Routes and Helpers Found

| name | current location | responsibility | dependencies | recommended destination | risk level |
|---|---|---|---|---|---|
| `dashboard` | `app.py` | Handles `GET /dashboard`, chooses the most recent session, builds template context, and renders `dashboard.html`. | `Request`, `templates`, `TEST_MODE`, `get_conn`, `_get_user_sessions`, `_load_profile_db`, `_get_session_data`, `build_dashboard_learning_summary`, `_dashboard_db_summaries`, `build_position_summary`, `build_legacy_position_fallback`, `CareerTrack`, `TRACK_DISPLAY_NAMES`, `TRACK_TAGLINES`. | `routes/dashboard.py` as the route entry point. | High |
| `_get_user_sessions` | `app.py` | Lists recent sessions for a user from the `sessions` table and returns safe display fields. | `TEST_MODE`, `get_conn`, `json`, `sessions.session_data`, `current_week`. | Keep in `app.py` or expose through `routes.deps` for now; move later with session persistence. | Medium |
| `_get_user_history` | `app.py` | Lists conversation history for `/history`; adjacent session history helper but not used by dashboard. | `TEST_MODE`, `get_conn`, `conversation_history`. | Leave in `app.py` until history is split. | Low |
| `_get_session_data` | `app.py` | Loads a session from memory or DB and enforces ownership on DB reads. Dashboard uses it to hydrate the most recent session. | `_sessions`, `_load_session_from_db`, `_make_client`, `_load_profile_db`, `SessionContext`, ownership SQL checks. | Keep in `app.py` and continue passing through `routes.deps`. | High |
| `_load_profile_db` | `app.py` | Best-effort loads `LearnerProfile` for dashboard stats. | `TEST_MODE`, `load_profile`, `get_conn`. | Keep in `app.py` or expose through `routes.deps` until profile/session persistence is split. | Medium |
| `build_dashboard_learning_summary` | `app.py` | Builds legacy dashboard cards from `SessionContext`: topic progress, todos, submissions, reflections, usage summary. | `SessionContext`, `get_topics_for_week`, `todo_counts`, `get_todos`, topic progress/submission dictionaries, `usage_summary`. | `routes/dashboard.py` as dashboard-local pure helper. | Medium |
| `_dashboard_enrollment_summary` | `app.py` | Reads active enrollment with fallback and returns safe fields for `enrollment_summary`. | `_open_db_connection`, `get_active_course_enrollment_with_fallback`, `normalize_course_key`, `summarize_enrollment_progress`, `SessionContext`. | `routes/dashboard.py` as dashboard-local DB read helper. | Medium |
| `_disabled_dashboard_enrollment_summary` | `app.py` | Produces safe disabled/fallback `enrollment_summary`. | `SessionContext`, `normalize_course_key`. | `routes/dashboard.py`. | Low |
| `_disabled_dashboard_modular_progress_summary` | `app.py` | Produces safe disabled/fallback `modular_progress_summary`. | None beyond dict shape. | `routes/dashboard.py`. | Low |
| `_dashboard_db_summaries` | `app.py` | Opens one DB connection and coordinates enrollment plus modular progress dashboard reads. Falls back safely on missing context or DB failure. | `_open_db_connection`, `_dashboard_enrollment_summary`, `build_dashboard_modular_progress_summary`, `SessionContext`. | `routes/dashboard.py`, still depending on DB connection provider from `app.py` or `routes.deps`. | High |
| `build_dashboard_modular_progress_summary` | `services/dashboard_modular_progress_service.py` | Service-level safe modular course summary from enrollment/module/topic progress tables. | Enrollment service, enrollment repository progress listing, `clamp_percent`. | Keep in service module. | Low |
| `build_position_summary` / `build_legacy_position_fallback` | `services/modular_position_service.py` | Pure current/next topic selection from modular progress or legacy `current_week` fallback. | `clamp_percent`, modular summary shape, optional `SessionContext.current_week`. | Keep in service module. | Low |
| `read_modular_progress_summary_safely` | `routes/deps.py` | Shared safe modular progress reader used by route modules such as todos. | `get_conn`, `build_dashboard_modular_progress_summary`, safe logging. | Keep in `routes/deps.py`; dashboard currently has its own enrollment plus modular DB summary helper. | Low |

Imports in `app.py` that are dashboard-only today include `get_topics_for_week`, `_open_db_connection`, `get_active_course_enrollment_with_fallback`, `normalize_course_key`, `summarize_enrollment_progress`, `build_dashboard_modular_progress_summary`, `build_position_summary`, and `build_legacy_position_fallback`. `ensure_course_enrollment` is no longer used by `app.py` after onboarding moved to `routes/onboarding.py`; it is not part of the dashboard move plan.

## 3. Template Context Variables

`templates/dashboard.html` receives these top-level variables:

- `display_name`: learner display name, defaulting to `Learner`.
- `recent_sessions`: recent session list. The template uses `recent_sessions[0]` as `s`.
- `tracks`: available track cards with `value`, `label`, and `tagline`.
- `stats`: profile-level stat cards.
- `learning_summary`: legacy `SessionContext` learning summary or `None`.
- `enrollment_summary`: enrollment card data.
- `modular_progress_summary`: modular progress card data.
- `position_summary`: current focus data derived from modular progress or legacy fallback.
- `recent_session_id`: selected session id used for topic and todo links.
- `test_mode`: renders the test badge.

Known `recent_sessions` fields:

- `session_id`
- `track`
- `current_week`
- `updated_at`

The template also derives `s = recent_sessions[0]` and `pct = ((s.current_week / 5) * 100)|int` for the resume card. The visible resume card uses `s.track`, `s.current_week`, and `s.session_id`.

Known `stats` fields:

- `session_count`
- `total_quizzes`
- `topics_mastered`
- `total_exchanges`

Known `learning_summary` counts/cards/progress fields:

- `current_week`
- `total_topics`
- `completed_topics`
- `in_progress_topics`
- `not_started_topics`
- `average_completion_percent`
- `total_todos`
- `daily_todos`
- `weekly_todos`
- `done_todos`
- `in_progress_todos`
- `quiz_evaluations_done`
- `portfolio_reviews_done`
- `interview_feedback_done`
- `reflections_saved`
- `usage_summary`

Known `enrollment_summary` fields:

- `source`
- `course_key`
- `status`
- `progress_percent`
- `current_module_key`
- `current_topic_key`
- `current_legacy_topic_id`
- `error`

Known `modular_progress_summary` fields:

- `source`
- `available`
- `course_key`
- `progress_percent`
- `current_module_key`
- `current_topic_key`
- `current_legacy_topic_id`
- `modules`
- `topics`
- `error`

Known `modular_progress_summary.modules` fields:

- `module_key`
- `status`
- `completed_topics`
- `total_topics`
- `progress_percent`

Known `modular_progress_summary.topics` fields:

- `module_key`
- `topic_key`
- `legacy_topic_id`
- `status`
- `completion_percent`
- `required_activities_completed`
- `required_activities_total`

Known `position_summary` fields:

- `available`
- `current_topic_key`
- `current_module_key`
- `next_topic_key`
- `progress_percent`
- `current_module_label`
- `source`

## 4. DB and Session Dependencies

`SessionContext` supplies the legacy runtime source of truth for the selected active session. Dashboard reads the selected session's `track`, `current_week`, topic progress, todos, quiz submissions, portfolio submissions, interview submissions, topic notes, usage summary, and `user_id`. It must preserve `current_week` compatibility because old serialized sessions and fallback display still depend on it.

DB best-effort reads include:

- `users.display_name` for the greeting.
- `sessions` through `_get_user_sessions` for recent session listing.
- `sessions.session_data` through `_get_session_data` when hydrating the most recent session after listing.
- learner profile data through `_load_profile_db`.
- learner course enrollment through `_dashboard_enrollment_summary`.
- modular module/topic progress through `build_dashboard_modular_progress_summary`.

DB fallback behavior must remain safe. Missing user context, missing session id, no selected session, DB connection errors, query errors, and unreadable enrollment/progress data must return disabled or fallback summary dictionaries and still render the dashboard. DB errors must not leak connection strings, secrets, tokens, or internal exception text into learner-facing HTML.

## 5. Target Structure

Recommended target structure:

- Put the `GET /dashboard` route in `routes/dashboard.py`.
- Move route-local dashboard helpers with it: `build_dashboard_learning_summary`, `_dashboard_enrollment_summary`, `_disabled_dashboard_enrollment_summary`, `_disabled_dashboard_modular_progress_summary`, and `_dashboard_db_summaries`.
- Keep session persistence and ownership-sensitive helpers in `app.py` and `routes.deps` for now, including `_sessions`, `_get_session_data`, `_save_session`, `_load_session_from_db`, `_get_user_sessions`, and `_load_profile_db`.
- Keep modular progress services where they already are: `services/dashboard_modular_progress_service.py`, `services/learner_course_enrollment_service.py`, and `services/modular_position_service.py`.
- Wire dashboard through `APIRouter` after `routes.deps` has been populated, matching the public/onboarding/topics/todos/submissions split pattern.

## 6. Risks

- route URL stability: `GET /dashboard` must remain exactly the same route and response class after the move.
- Template context mismatch: `dashboard.html` depends on many nested fields, especially `recent_sessions`, `stats`, `learning_summary`, `enrollment_summary`, `modular_progress_summary`, and `position_summary`.
- DB fallback behavior: the route currently survives failed display-name, session-list, profile, enrollment, and modular progress reads. The split must preserve disabled/error fallback dictionaries and no learner-facing DB error output.
- `current_week` compatibility: resume card, learning summary, old topic curriculum fallback, and `build_legacy_position_fallback` still use `SessionContext.current_week`.
- Enrollment/modular progress summary behavior: DB source shows learning path/progress cards, fallback source hides those cards while preserving legacy dashboard cards.
- Ownership and session hydration: `_get_session_data` enforces ownership on DB reads and should not be copied casually into a route module.
- Tests patch `app_module._dashboard_db_summaries` today; moving the helper will require a compatibility decision or test update in the route split step.

## 7. Test Strategy

Run these tests after the route move:

- `tests/test_dashboard_routes_split.py`
- `tests/test_dashboard_summary.py`
- `tests/test_dashboard_enrollment_summary.py`
- `tests/test_dashboard_modular_progress_summary.py`
- `tests/test_modular_position_runtime_display.py`
- `tests/test_onboarding_flow.py`

Also keep the existing dashboard invariants in mind: no Claude call, no seed script call, no route URL change, no learner-facing DB error, no commit/rollback for read-only dashboard reads, and no mutation of `WEEKS` or `ROLE_TRACKS`.

## 8. Recommended Next Implementation Step

Move only the dashboard route and dashboard-local helpers into `routes/dashboard.py`. Keep session persistence, session hydration, ownership checks, profile loading, and recent session listing in `app.py` or exposed through `routes.deps` for now. Include the new router after `routes.deps` assignment, then add focused split tests that prove `GET /dashboard` remains stable and `app.py` no longer owns the dashboard route body.
