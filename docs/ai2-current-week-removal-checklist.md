# AI² current_week Removal Checklist

## 1. Current Status

Learner-facing wording has mostly moved from a fixed week-based syllabus to module/path language. The topics page and topic detail page now say "Module" or "Learning path" in the UI while preserving existing route URLs and legacy topic IDs.

Step 128 marked week-based internals as compatibility-only. New implementation should use modular course/module/topic state, including `sequence_order`, learner enrollment, and modular progress. Removal is still pending until the compatibility migration is complete.

The modular curriculum foundation exists:

- Modular schema tables exist in `database/schema.sql`.
- Modular repository, seed/export adapter, manual seed script, read service, and fallback service exist.
- `/debug/modular-curriculum` exists for protected validation.
- `AI2_MODULAR_CURRICULUM_READS_ENABLED` gates modular reads.
- `/topics/{session_id}` can read modular curriculum behind the flag.
- `/topic/{session_id}/{topic_id}` can enrich the detail page with modular metadata behind the flag.

`current_week` still exists internally for compatibility. `WEEKS` and `ROLE_TRACKS` still exist as the static fallback and seed/export source. They should not be removed until runtime has a stable replacement for enrollment, module position, and topic progress.

## 2. Why current_week Cannot Be Deleted Yet

`current_week` is deeply embedded. It is not only old UI wording.

Major dependencies:

- Session serialization: `SessionContext.to_dict()` and `SessionContext.from_dict()` persist and restore `current_week`.
- Dashboard progress: dashboard summaries call `get_topics_for_week(track, current_week)`.
- Topic listing fallback: `/topics/{session_id}` still falls back to static topics by current week when modular reads are disabled or unavailable.
- Todo planning: todos are still grouped internally as `daily` and `weekly`, even though labels now say module-plan.
- Chat/agent context: prompt context still includes week-based position text.
- Tests: many focused tests start sessions with `{"week": 1}` and assert `current_week` compatibility.
- Static curriculum fallback: `curriculum.syllabus.WEEKS`, `ROLE_TRACKS`, `MAX_WEEKS`, and week-derived topic IDs still power fallback behavior and static seed generation.

Deleting `current_week` now would break old sessions, static fallback, topic routes, dashboard summaries, prompt context, and a large portion of the test harness.

## 3. All current_week / week-based Dependencies Found

| File path | Symbol/text found | Runtime importance | Replacement direction |
|---|---|---|---|
| `context/session.py` | `current_week: int = 1` | Core runtime state stored in every session | Add enrollment/module state alongside it first; keep backward-compatible load |
| `context/session.py` | `advance_week()` | Old imperative advancement helper | Remove only after module progress derives position |
| `context/session.py` | `TOTAL_WEEKS` import | Bounds `advance_week` and prompt/progress strings | Replace with dynamic course/module count |
| `context/session.py` | `progress_summary()` uses `Current week: ... / TOTAL_WEEKS` | Fed to app/agent-facing context | Replace with course/module/topic progress summary |
| `context/session.py` | `to_dict()` / `from_dict()` include `current_week` | Session persistence compatibility | Keep reader support; write new module fields in parallel |
| `context/session.py` | `as_prompt_context()` uses `Week: ... of TOTAL_WEEKS` | Claude prompt context | Replace with module/path position after runtime module state exists |
| `app.py` | `TOTAL_WEEKS` import | Session start clamping and progress response | Replace with course/module count or remove from API once compatible |
| `app.py` | `_sessions` metadata includes `current_week` | In-memory/test session listing | Add module/course fields; keep current_week for old sessions |
| `app.py` | `build_dashboard_learning_summary()` uses `session.current_week` and `get_topics_for_week` | Dashboard summary | Use module/topic progress from enrollment or modular course |
| `app.py` | `_session_progress()` returns `current_week` and `total_weeks` | Chat/templates/API progress payload | Add module fields; later deprecate week fields |
| `app.py` | start-session request body has `week: int = 1` | Existing API contract | Keep route shape for now; map to initial module internally later |
| `app.py` | `/syllabus/{session_id}` iterates `WEEKS` and uses `ROLE_TRACKS` | Syllabus tracker page | Replace with modular course/module rows |
| `routes/topics.py` | `current_week = session.current_week` | Topics listing fallback | Use enrollment/current module key when modular runtime becomes primary |
| `routes/topics.py` | `_topics_for_listing(track, current_week)` | Flagged modular listing fallback | Replace fallback signature with module/course context |
| `routes/topics.py` | `get_topics_for_week(track, current_week)` | Static fallback when flag off or DB fails | Keep until DB primary and fallback migration are proven |
| `routes/todos.py` | `weekly_todos` grouping | Planner still has weekly internal type | Rename only after data compatibility or add module-plan type migration |
| `curriculum/topics.py` | Imports `ROLE_TRACKS`, `WEEKS`, `get_task_key` | Static topic catalog source | Replace with repository-backed topic listing after DB primary |
| `curriculum/topics.py` | `TopicCard.week_num` | Template-compatible topic object still carries sequence as week field | Add module order/key fields or adapter object before removing |
| `curriculum/topics.py` | `get_topics_for_week(track, week_num)` | Static fallback topic filter | Replace with `get_topics_for_module` or DB service |
| `curriculum/topics.py` | Topic IDs like `{track}-week-{week_num}-{slug}` | Legacy IDs used by sessions, DB mirrors, content cache, submissions | Keep `legacy_topic_id` bridge indefinitely |
| `curriculum/syllabus.py` | `MAX_WEEKS = 5` | Static curriculum bounds | Replace with dynamic module count |
| `curriculum/syllabus.py` | `ROLE_TRACKS` | Static track metadata | Move display metadata to `learning_tracks`/course rows |
| `curriculum/syllabus.py` | `WEEKS` | Static curriculum content source | Keep as fallback/seed source until modular DB is trusted |
| `curriculum/syllabus.py` | `get_current_week()` | Computes active week from syllabus progress | Replace with derived module/topic position |
| `curriculum/syllabus.py` | `get_week_by_num()`, `get_week()` | Backward-compatible week lookup | Replace with module lookup service |
| `curriculum/syllabus.py` | `format_week_context()` and `get_full_track_summary()` | Agent/context curriculum text | Rewrite from modular course structure later |
| `curriculum/syllabus.py` | `_WEEK_TO_PHASE`, `PHASES = WEEKS` | Syllabus route compatibility | Replace with modular phases/modules |
| `curriculum/seed_export.py` | `module_type="week"`, `week-{n}` module keys | Older seed/export path | Prefer modular seed export, then retire |
| `curriculum/modular_seed_export.py` | Reads `ROLE_TRACKS` and static topics | Current modular seed source | Keep until source curriculum content lives in DB/admin tooling |
| `services/modular_curriculum_fallback_service.py` | Static fallback converts WEEKS topics to modular-like dicts | Critical DB-failure fallback | Keep while migration is behind flag |
| `services/curriculum_fallback_service.py` | Uses `ROLE_TRACKS` | Older curriculum fallback | Replace with modular fallback once read migration completes |
| `templates/dashboard.html` | `s.current_week`, `/ 5` progress calculation | Visual dashboard progress still derived from current week | Replace with module/topic completion once available |
| `templates/chat.html` | `progress.current_week` | Displays module number from old field | Point to module position field later |
| `templates/topics.html` | `current_week`, `topic.week_num`, week CSS class names | Visible copy is module-based, internals still week-shaped | Add module-order context; rename CSS only in cleanup step |
| `templates/topic_detail.html` | `topic.week_num` | Displays module number from old field | Replace with module order/key in topic adapter |
| `templates/syllabus.html` | `overall.by_week`, `week-*` JS IDs | Syllabus tracker still week-shaped | Replace with module IDs/sequence |
| `database/schema.sql` | Comments mention WEEKS, `week_number`, legacy topic ID format | Schema documents the bridge state | Keep comments accurate until bridge retired |
| `tests/*` | Many tests call `/session/start` with `week` and use `get_topics_for_week` | Regression harness for old runtime behavior | Add new module/enrollment tests first; then update old tests gradually |
| `docs/*` | Older docs mention fixed week curriculum | Documentation drift | Update as cleanup; not a runtime blocker |

## 4. Replacement Model

Target model:

- `course_key`: stable identifier for a learning path, such as `aipm-foundations`.
- `module_key`: stable identifier for a module inside a course, such as `module-01`.
- `module_id`: DB primary key for the module.
- `topic_id`: DB primary key for a modular topic.
- `legacy_topic_id`: bridge to existing SessionContext, content cache, progress, submissions, and write-through rows.
- `sequence_order`: ordering source for courses, modules, topics, and activities.
- `learner_course_enrollment`: learner/session/course state, including selected course, enrollment status, current position if needed, and timestamps.
- Learner module/topic progress: progress should be derived from topic/activity completion rather than incrementing a week counter.

The important migration principle is to keep `legacy_topic_id` as the bridge until all existing generated content, progress, notes, submissions, usage events, and tests can resolve both old and new IDs.

## 5. Required Schema/State Changes Before Removal

Before removing `current_week`, AI² needs:

- Learner course enrollment state tied to `user_id`, `session_id`, and `course_key`.
- A current module/topic pointer if the product needs an explicit "resume here" location.
- Or a deterministic derivation of current module/topic from topic/activity progress.
- Module progress derived from topic/activity completion.
- A migration path from `current_week` to module `sequence_order`.
- Compatibility for old serialized sessions that contain only `current_week`.
- A fallback strategy for DB failures while modular runtime reads are still maturing.
- Tests proving old sessions and flag-off behavior still load.

## 6. Runtime Migration Steps

Recommended order:

1. Add learner course enrollment state behind schema/repository/service layer.
2. Add `current_module_key` / `current_topic_key`, or derive current position from progress.
3. Update dashboard to use module/topic progress instead of `current_week`.
4. Update todos to use module/topic context instead of weekly planning language and `weekly` internals.
5. Update chat prompt learner context from week position to module/path position.
6. Update static fallback to expose module/order data consistently.
7. Update tests to cover both old session compatibility and modular primary behavior.
8. Remove `advance_week` and `TOTAL_WEEKS` after no runtime path depends on them.
9. Remove `current_week` only after compatibility migration passes and old session load is proven.

## 7. What Can Be Removed Soon

Low-risk cleanup candidates after the next compatibility layer exists:

- Remaining visible week wording in older docs and non-runtime comments.
- Old test names/comments that say week while asserting module behavior.
- `advance_week()` if no route or product flow uses it and replacement module progress exists.
- `TOTAL_WEEKS` after dashboard/session progress no longer needs fixed counts.
- Week-shaped CSS class names only after tests and templates no longer depend on them.

These are still cleanup tasks, not prerequisites for private beta.

## 8. What Must Stay For Now

Keep these until the modular runtime is fully proven:

- `SessionContext.current_week`
- `get_topics_for_week`
- `WEEKS`
- `ROLE_TRACKS`
- `legacy_topic_id`
- Static fallback service
- Existing `/session/start` request shape with `week`
- Existing route URLs

## 9. Testing Requirements Before Removal

Before removing `current_week`, tests must prove:

- Old serialized sessions still load.
- Modular flag false still works.
- Modular flag true works with seeded DB.
- Modular flag true works with DB failure fallback.
- Dashboard renders.
- Topics listing renders.
- Topic detail renders.
- Todos work.
- Content generation works.
- Quiz, portfolio, and interview submissions work.
- No DB connection opens when modular flag is false.
- Existing legacy topic IDs still resolve content, progress, submissions, notes, and usage events.
- `WEEKS` / `ROLE_TRACKS` are not mutated during fallback reads.

## 10. Recommended Next Step

Add learner course enrollment state behind a schema/repository/service layer, without removing `current_week` yet.

That step should be additive:

- Store enrollment by `user_id`, `session_id`, and `course_key`.
- Track selected course and optional current module/topic pointer.
- Keep SessionContext as runtime source of truth while DB primary reads are still gated.
- Add safe read/fallback services and debug checks.
- Do not change learner-facing routes until the enrollment layer is tested.
