# AI² Six-Course Syllabus UI Audit

## 1. Product Direction

The next syllabus UI should present the curriculum as six course cards:

- AI Foundations
- AI Engineering & Building
- AI Evaluation & Quality
- AI Product & Strategy
- AI Data & Analytics
- AI Experience & Growth

AI Foundations should be labeled “Start here” because it is the shared prerequisite
for the catalog. The other five cards should be labeled “Specialization paths” so
learners understand they can move into them after, or in some cases alongside, the
shared Foundations course.

The product model should shift the learner-facing language from legacy role tracks
to courses. The existing track values can remain as a compatibility bridge during
implementation, but the UI should make the six-course catalog the primary choice.

## 2. Current Course/Track Selection Flow

The current learner-facing selection flow is still built around three career tracks:
`aipm`, `evals`, and `context`.

`routes/public.py` sends authenticated users and test-mode users from `/` to
`/dashboard`; unauthenticated users go to `/login`. `templates/index.html` still
contains a legacy three-card track chooser, but the current root route no longer
renders it directly.

`routes/dashboard.py` builds the active selectable cards from `config.CareerTrack`,
`TRACK_DISPLAY_NAMES`, and `TRACK_TAGLINES`. `templates/dashboard.html` renders
these as track cards under "Start New Track". Clicking a card posts `{track}` to
`/session/start` and redirects to `/chat/{session_id}`.

`routes/chat.py` owns `/session/start`. It validates the posted track through
`routes.deps.track_from_str`, which is wired in `app.py` to `_track_from_str`.
That validator only accepts the `CareerTrack` enum values currently defined in
`config.py`: `aipm`, `evals`, and `context`. The new `SessionContext` stores the
selected value as `session.track` and initializes `current_week` to the requested
week, clamped to `TOTAL_WEEKS`.

`routes/onboarding.py` is not a full course selector today. Its form asks for goal,
level, and weekly time. `SessionContext.save_onboarding_profile()` maps onboarding
goals to a `recommended_track`; `ai_builder` currently maps to `context`, and
`interview_prep` maps to `aipm`. After saving, onboarding calls
`ensure_course_enrollment()` best-effort with that recommended track, then redirects
to `/topics/{session_id}`.

`routes/syllabus.py` renders `/syllabus/{session_id}` from the legacy static
syllabus. It reads `session.track.value`, iterates `curriculum.syllabus.WEEKS`,
and shows shared `all_tracks` tasks plus tasks for the selected role track. The
syllabus page does not currently read a selected `course_key` from the session.

`routes/topics.py` renders `/topics/{session_id}` from the selected session track
and current module. Topic detail pages use legacy `topic_id` values derived from
the static topic projection, while optionally enriching with modular metadata when
the modular curriculum flag is enabled.

## 3. Current Data Flow

The static fallback curriculum is in `curriculum/syllabus.py`. It defines
`ROLE_TRACKS`, `WEEKS`, task keys, role-specific tasks, artifacts, skills, and
helper functions for syllabus progress. `curriculum/topics.py` projects that
static syllabus into `TopicCard` objects with legacy `topic_id`, `track`,
`week_num`, module title/theme, recommended actions, and generated prompts.

This static path is still the default runtime path. `/syllabus/{session_id}` always
uses `WEEKS` and `ROLE_TRACKS`. `/topics/{session_id}` calls
`get_topics_for_week(track, current_week)` unless modular curriculum reads are
enabled and the modular read succeeds.

The modular DB curriculum path exists in parallel. The schema-facing repository is
`repositories/modular_curriculum_repository.py`, with `courses`, `course_modules`,
`course_topics`, `skills`, `topic_skills`, and `topic_activities` helpers. The read
service in `services/modular_curriculum_read_service.py` loads course trees by
`course_key` and topic structures by `legacy_topic_id`.

`services/modular_curriculum_fallback_service.py` bridges DB reads back to the
static fallback. It can return a course structure for a `course_key`, list courses,
or look up a topic by legacy ID. Today its fallback catalog is derived from
`ROLE_TRACKS`, so it returns three track-derived "Foundations" courses rather than
the new six-course catalog.

Feature flags live in `services/storage_flags.py`. The relevant read flag is
`AI2_MODULAR_CURRICULUM_READS_ENABLED`, exposed as
`is_modular_curriculum_reads_enabled()`. When the flag is off, `routes/topics.py`
does not open the modular DB path. When the flag is on, topic listing calls
`get_course_structure_with_fallback()` and then adapts course/module/topic records
to `TopicCard` objects. Topic detail pages similarly call modular topic lookup only
when the flag is on.

Course key mapping is currently a compatibility layer:

- `services/learner_course_enrollment_service.py` maps `aipm` to
  `aipm-foundations`, `evals` to `evals-foundations`, and `context` to
  `context-engineering-foundations`.
- `routes/topics.py` has a local `_course_key_for_track()` map with those same
  three keys, plus provisional `ai_builder` and `ai_job_ready` entries.
- Dashboard enrollment summaries normalize from `session.track` to `course_key`.
- Modular topic detail lookups still use legacy `legacy_topic_id` as the stable
  bridge into `course_topics`.

`scripts/seed_modular_curriculum.py` is manual only. It imports the modular seed
export, upserts courses/modules/topics/skills/activities, commits on success, and
rolls back on failure. It must not be run during this UI audit or before pure-data
and route tests pass.

## 4. UI Placement Recommendation

The six course cards should appear on the dashboard first, replacing or superseding
the current "Start New Track" section. That is the active authenticated learner
entry point today, and it already has card styling, JavaScript click handling, and
the surrounding "Continue Learning" context.

Onboarding can later become a guided recommendation layer, but it should not be
the only place the catalog appears. The dashboard should always expose the full
catalog so learners can see the Foundations prerequisite and all specialization
paths.

Recommended card labels:

- AI Foundations: “Start here”
- AI Engineering & Building: “Specialization paths”
- AI Evaluation & Quality: “Specialization paths”
- AI Product & Strategy: “Specialization paths”
- AI Data & Analytics: “Specialization paths”
- AI Experience & Growth: “Specialization paths”

Each card should carry a stable `course_key` from the catalog. In the first
implementation slice, card selection can be wired through the existing session
start/course enrollment path by translating a selected course to whatever legacy
`session.track` value is still required. The implementation should keep
AI Foundations as the shared prerequisite in the copy and metadata, without
blocking the UI behind database state.

## 5. Implementation Plan

1. Add or update a pure-data curriculum catalog file, likely
   `curriculum/curriculum_catalog.py`, containing the six courses, stable
   `course_key` values, labels, descriptions, prerequisite metadata, modules,
   topics, and prompt text. Do not seed the DB in this slice.
2. Add catalog summary tests that assert there are exactly 6 courses, every course
   has modules, topics, and prompts, AI Foundations is marked “Start here”, and
   the other five are marked “Specialization paths”.
3. Add course-card UI copy and labels to the dashboard catalog section, with tests
   verifying that all six course names render and that the prerequisite/specialty
   language is visible.
4. Connect card selection to the existing session/course flow. Keep the current
   `SessionContext.track` API working until runtime routes are migrated to
   `course_key`; use a small compatibility map rather than changing every caller.
5. Run focused route and UI tests for dashboard, onboarding, syllabus, topics,
   topic detail, modular curriculum flags, enrollment summaries, and session
   persistence.
6. Seed DB only after code tests pass and the pure-data catalog has been reviewed.
   The seed step should be a separate, explicit operation.

Files likely to change in the implementation step:

- `curriculum/curriculum_catalog.py` or the existing modular seed export data
- `curriculum/modular_seed_export.py`
- `services/modular_curriculum_fallback_service.py`
- `services/learner_course_enrollment_service.py`
- `routes/dashboard.py`
- `routes/chat.py` if `/session/start` accepts `course_key`
- `routes/onboarding.py` if onboarding recommendations become course-based
- `routes/topics.py` if topic listing moves from `track/current_week` to
  `course_key/module_key/topic_key`
- `templates/dashboard.html`
- possibly `templates/onboarding.html`
- `static/style.css`
- focused tests under `tests/`

## 6. Risk Areas

- Breaking existing session flow: `SessionContext` currently requires a
  `CareerTrack`, and many routes read `session.track.value`.
- Mismatched `course_key`, `module_key`, and `topic_key`: modular DB reads use
  these keys, while legacy topic pages still route by `legacy_topic_id`.
- Feature flags: `AI2_MODULAR_CURRICULUM_READS_ENABLED` changes whether topic
  lists and topic details attempt modular DB reads.
- DB vs fallback mismatch: the fallback currently exposes three track-derived
  courses, while the new product direction requires six course cards.
- Route URLs: current UI starts sessions through `/session/start` with `{track}`;
  a course-card UI needs either a compatible `track` bridge or a deliberate
  `course_key` API extension.
- Existing topic detail actions: Learn, Quiz, Portfolio Task, Interview Practice,
  reflections, submissions, learning outcomes, planner actions, and write-through
  progress all assume stable legacy topic IDs.
- Onboarding semantics: current onboarding recommends a legacy track, not a course.
- Syllabus page semantics: `/syllabus/{session_id}` still renders static
  role-track tasks and does not render a modular course tree.
- Seeding too early: running `scripts/seed_modular_curriculum.py` before tests pass
  could write an incomplete or mismatched catalog to the database.

## 7. Recommended Next Step

Add the updated `curriculum_catalog.py` as pure data first, with summary tests only.
That should establish the six course names, stable course keys, Start here vs
Specialization paths labels, prerequisite metadata, module/topic structure, and
prompt coverage without touching routes, templates, schema, or the database.

Do not seed DB until tests pass.
