# AI² advance_week Deprecation Plan

## 1. Current Usage

The audit found that `advance_week`, `TOTAL_WEEKS`, and `current_week` are still compatibility scaffolding. They should be treated as deprecated runtime internals, not deleted yet.

Step 128 marked week-based internals as compatibility-only. New implementation should use modular course/module/topic state, including `sequence_order`, learner enrollment, and modular progress. Removal is still pending until the compatibility migration is complete.

| File | Function/template/test usage | Status |
|---|---|---|
| `context/session.py` | Imports `TOTAL_WEEKS`; stores `SessionContext.current_week`; defines `SessionContext.advance_week()`; serializes/deserializes `current_week`; uses `current_week` as module position in `progress_summary()` and `as_prompt_context()` | Core compatibility dependency |
| `app.py` | Imports `TOTAL_WEEKS`; clamps `/session/start` `week` into `current_week`; `_session_progress()` returns `current_week` and `total_weeks`; dashboard/session listing still includes `current_week`; dashboard fallback summary calls `get_topics_for_week(track, current_week)` | Runtime fallback and API compatibility |
| `routes/topics.py` | Reads `session.current_week`; passes `current_week` to `templates/topics.html`; uses `_topics_for_listing(track, current_week)` and `get_topics_for_week()` when modular reads are disabled or fail | Static topic fallback |
| `routes/todos.py` | Does not advance modules, but todo display context can fall back to `SessionContext.current_week` as `Module N` | Planner compatibility fallback |
| `templates/dashboard.html` | Uses `s.current_week` for legacy session-list progress and module labels; uses `learning_summary.current_week` as a module label | Visible wording is module-based, but data source is still legacy |
| `templates/topics.html` | Uses `current_week` and `week_progress_summary` variable/CSS names while visible wording says module | Template compatibility names |
| `templates/todos.html` | Uses `progress.current_week` only as a module fallback label | Template compatibility fallback |
| `templates/chat.html` | Uses `progress.current_week` in a `week-badge` class while visible wording says module | Template compatibility name |
| `curriculum/topics.py` | Static fallback topic catalog still exposes `TopicCard.week_num` and `get_topics_for_week(track, week_num)` | Legacy topic filtering fallback |
| `curriculum/syllabus.py` | Still defines static `WEEKS`, `ROLE_TRACKS`, `MAX_WEEKS`, `get_current_week()`, `get_week_by_num()`, and week-derived context helpers | Static syllabus fallback and seed source |
| `services/todo_context_service.py` | Falls back from missing modular/enrollment context to `SessionContext.current_week`, displayed as `Module N` | Safe fallback only |
| `docs/ai2-current-week-removal-checklist.md` | Documents broader `current_week` removal dependencies | Related migration checklist |
| `tests/test_chat_context_module_wording.py` | Verifies prompt wording is module-based while `current_week` and `advance_week` still exist | Compatibility regression |
| `tests/test_dashboard_enrollment_summary.py` | Verifies dashboard fallback still supports `current_week` | Compatibility regression |
| `tests/test_dashboard_modular_progress_summary.py` | Verifies dashboard modular progress fallback still supports `current_week` | Compatibility regression |
| `tests/test_modular_progress_snapshot_runtime.py` | Verifies progress snapshot runtime does not mutate `current_week` | Compatibility regression |
| `tests/test_onboarding_course_enrollment.py` | Verifies onboarding enrollment does not mutate `current_week` | Compatibility regression |
| `tests/test_orchestrator.py` | Verifies existing progress payload still includes `current_week` / `total_weeks` | API compatibility regression |
| `tests/test_schema_learner_course_enrollments.py` | Verifies additive schema comments for future `current_week` replacement | Migration regression |
| `tests/test_todos_modular_context.py` | Verifies todos can fall back to `current_week` as module context | Compatibility regression |
| `tests/test_week_wording_removed_from_ui.py` | Verifies visible UI wording moved from week to module while internals remain | Wording regression |

No active route/button was found that calls `advance_week()` directly. The method remains as an internal compatibility helper.

## 2. Why It Must Stay Temporarily

`advance_week`, `TOTAL_WEEKS`, and especially `current_week` must stay temporarily because they still protect old and fallback flows:

- Old serialized sessions contain `current_week`, and `SessionContext.from_dict()` expects to restore it.
- Static fallback still uses `get_topics_for_week(track, current_week)` when modular curriculum reads are disabled or unavailable.
- Topic filtering fallback still depends on legacy week numbers to find the correct static topic set.
- Tests still assert the old `/session/start` request shape and progress payload compatibility.
- Legacy topic IDs include week-shaped strings, and those IDs bridge existing progress, notes, content cache, submissions, usage events, and modular topic rows.
- `WEEKS` and `ROLE_TRACKS` remain the static fallback and seed/export source until modular DB reads are fully primary.

Deleting these now would break compatibility without improving learner-facing behavior.

## 3. Replacement Behavior

The future runtime should not advance a fixed week counter. It should derive position from modular progress:

- Pick the next incomplete topic from modular course progress.
- Derive the current module from the first in-progress topic, then the first not-started topic, then the last completed topic.
- Persist the current position on learner course enrollment using `current_module_key`, `current_topic_key`, and `current_legacy_topic_id`.
- Use course/module/topic sequence order and completion state, with no fixed total week count.
- Treat `legacy_topic_id` as the bridge until all existing content, progress, notes, submissions, and tests can resolve modular topic keys directly.

## 4. Safe Removal Order

1. Add a next-topic/current-position helper.
2. Use modular progress to derive current position.
3. Update dashboard/topics/todos to stop relying on `current_week` for display.
4. Keep `current_week` only as compatibility fallback.
5. Remove or hide any advance-week route/button if one is introduced or found unused.
6. Remove `TOTAL_WEEKS` after no runtime path needs fixed counts.
7. Migrate old sessions from `current_week` to module/topic position.
8. Remove `current_week` only after compatibility migration and old-session loading are proven.

## 5. What Can Be Changed Soon

Low-risk follow-up changes:

- Hide or remove advance-week UI if any stale UI appears, while keeping route compatibility if a route exists.
- Replace fixed total module count in dashboard/chat progress payloads.
- Prefer modular progress summary wherever it is already available.
- Keep legacy route URLs and request shapes while adding modular fields alongside them.
- Rename CSS/test variable names such as `week-progress-*` only after behavior is stable.

## 6. What Must Not Be Deleted Yet

Do not delete these yet:

- `SessionContext.current_week`
- `SessionContext.advance_week`
- `TOTAL_WEEKS`
- `get_topics_for_week`
- `WEEKS`
- `ROLE_TRACKS`

## 7. Recommended Next Implementation Step

Add a modular next-topic/current-position helper service.

The helper should accept calculated course progress and return:

- `current_module_key`
- `current_topic_key`
- `current_legacy_topic_id`
- a reason/source such as `in_progress`, `not_started`, or `completed`

That service should be pure, safe, and independent of DB connections so dashboard, topics, todos, and enrollment write-through can adopt it gradually.
