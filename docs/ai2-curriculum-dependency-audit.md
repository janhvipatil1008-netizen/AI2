# AI² Curriculum Dependency Audit

**Date:** 2026-05-20  
**Purpose:** Identify every dependency on the fixed 13-week / week-based syllabus model
before migrating to a flexible Course → Module → Skill → Topic → Activity structure.  
**Scope:** Audit only. No runtime files, templates, schema, or tests were modified.

---

## 1. Current Curriculum Model

### How the system represents curriculum today

All curriculum content lives in a single Python file: `curriculum/syllabus.py`. The
structure is a static in-process dictionary called `WEEKS` — a 5-element list where each
element describes one week of the programme. Every learner sees the same weeks in the
same order.

Track identity is held in a parallel dictionary `ROLE_TRACKS` (three entries: `aipm`,
`evals`, `context`), which mirrors the `CareerTrack` enum defined in `config.py`.

`curriculum/topics.py` projects `WEEKS` into `TopicCard` objects at import time. A
`TopicCard` is a frozen dataclass that includes `week_num` as a first-class field. Topic
IDs are generated from the pattern `{track}-week-{week_num}-{slug}`, permanently
embedding the week number into every stable topic identifier in the system.

### Static source of truth

`ROLE_TRACKS` and `WEEKS` in `curriculum/syllabus.py` are the **only** authoritative
source of curriculum content at runtime. Every learner-facing page and every agent prompt
ultimately derives from these two objects.

### DB curriculum tables: present but not yet primary

The schema (`database/schema.sql`) already has three DB-backed curriculum tables:
`learning_tracks`, `learning_modules`, and `learning_topics`. These use `sequence_order`
(an integer) instead of a week number. However:

- No learner-facing route reads from them.
- They are populated by a **manual** seed script (`scripts/seed_curriculum.py`), which
  itself reads from `WEEKS`.
- `services/curriculum_fallback_service.py` and `services/curriculum_read_service.py`
  expose flag-gated DB reads, but the flag (`AI2_CURRICULUM_DB_READS_ENABLED`) is off by
  default and not wired into the main topic-display flow.

In short: the DB tables exist and are structurally sound for migration, but the static
Python dictionaries are what runs the app today.

---

## 2. Fixed 13-Week / Week-Based Dependencies

The curriculum is actually **5 weeks** (not 13 — `TOTAL_WEEKS = 5`, `MAX_WEEKS = 5`).
Some agent strings still say "/ 13", which are pre-existing copy bugs rather than
accurate constants. Every structural dependency listed below uses 5 as the actual limit.

### `config.py`

| Line | Dependency | Why It Matters | Replacement Direction |
|------|-----------|---------------|----------------------|
| 31 | `TOTAL_WEEKS = 5` | Used to clamp `current_week`, drive progress % in `session.py` and `app.py` | Replace with dynamic module count or remove entirely once per-learner sequence is tracked in DB |

### `curriculum/syllabus.py`

| Lines | Dependency | Why It Matters | Replacement Direction |
|-------|-----------|---------------|----------------------|
| 12 | `MAX_WEEKS = 5` | Bounds check for week iteration | Remove after WEEKS is retired |
| 16-20 | `ROLE_TRACKS` dict | Defines the three valid track slugs and their display metadata | Keep slugs; move display metadata to `learning_tracks` DB table |
| 24-556 | `WEEKS` list | **Primary curriculum content source.** All topic text, titles, day breakdowns, role-specific tasks. | Migrate content to `learning_topics` rows; retire this structure after DB seeding is verified |
| 558-561 | `get_task_key(week_num, day_idx, scope, task_idx)` | Generates stable string keys like `w1-d0-all-0` for syllabus_progress tracking | Replace with `topic_id`-based progress tracking; task keys can become `legacy_task_key` column in topics table |
| 564 | `get_week_by_num(week)` | Lookup week dict by number | Remove after WEEKS retired |
| 625 | `get_current_week()` | Returns int week based on session state | Remove |
| 850 | `PHASES = WEEKS` alias | `/syllabus` route iterates this | Remove when syllabus page migrated |

### `curriculum/topics.py`

| Lines | Dependency | Why It Matters | Replacement Direction |
|-------|-----------|---------------|----------------------|
| 15 | `from curriculum.syllabus import ROLE_TRACKS, WEEKS, get_task_key` | Hard import coupling to static data | Replace with DB read once `learning_topics` is primary |
| 22-36 | `TopicCard.week_num: int` | Every topic card carries its week number | Replace with `module_order: int` (already present as `sequence_order` in DB) |
| 54-92 | Loop over `WEEKS` in `get_topics_for_track` | Generates all topic cards by iterating weeks | Rewrite to read from `learning_topics` via repository |
| 95-97 | `get_topics_for_week(track, week_num)` | Filters topics by week | Replace with `get_topics_for_module(track, module_order)` |
| 119-122 | Topic ID generation: `f"{track}-week-{week_num}-{slug}"` | Embeds week in every stable topic identifier | **Most invasive dependency.** Existing IDs stored in sessions, DB progress rows, content cache. Will need a `legacy_topic_id` bridge column (already in schema). |

### `context/session.py`

| Lines | Dependency | Why It Matters | Replacement Direction |
|-------|-----------|---------------|----------------------|
| 11 | `from config import CareerTrack, TOTAL_WEEKS` | Imports week constant | Remove `TOTAL_WEEKS` import once `advance_week` is removed |
| 47 | `current_week: int = 1` | Session field stored in serialized session JSON | Deprecate field; keep in `from_dict` for backward compatibility with existing stored sessions |
| 89-93 | `advance_week()` | Increments `current_week`, checks against `TOTAL_WEEKS` | Remove; week advancement becomes implicit from module completion |
| 584 | `f"Current week: {self.current_week} / {TOTAL_WEEKS}"` | Learner-facing context string fed to agents | Replace with module-based position string |
| 598-637 | `current_week` in `to_dict()` / `from_dict()` | Serialized into every stored session | Must keep during migration for existing sessions; add `module_order` alongside |
| 678-681 | `f"Week: {self.current_week} of {TOTAL_WEEKS}"` in `build_learner_context()` | Injected into every agent prompt | Replace with module/sequence label |

### `app.py`

| Lines | Dependency | Why It Matters | Replacement Direction |
|-------|-----------|---------------|----------------------|
| 44 | `from config import ... TOTAL_WEEKS` | Import | Remove once week progress removed |
| 54 | `from curriculum.topics import get_topics_for_week` | Main import for /topics route | Replace with module-aware read |
| 192 | `"current_week": data.get("current_week", 1)` | Included in session-list API response | Update field name or include both for compatibility |
| 231-233 | `get_topics_for_week(track, current_week)` in dashboard summary | Topics shown on /topics are filtered to current week only | Replace with module-based topic list |
| 260 | `"current_week": current_week` in dashboard summary dict | Passed to template | Replace with module label |
| 589-590 | `SessionStartRequest.week: int = 1` | `/session/start` POST body accepts week number | Replace with `module_order: int = 1` or remove in favor of starting at first module |
| 691-698 | `_session_progress()` — `_WEEK_TO_PHASE` lookup, `current_week`, `total_weeks` | Drives chat sidebar progress display | Replace phase/week with module-based position |
| 1984-1985 | `"current_week": recent_session.current_week` in session list | Serialized to JSON | Update after migration |

### `curriculum/freshness.py`

No direct week-number dependency found. Freshness classification (`evergreen`, `stable`,
`current`, `volatile`) is topic-level and carries forward cleanly.

### `curriculum/seed_export.py`

| Lines | Dependency | Why It Matters | Replacement Direction |
|-------|-----------|---------------|----------------------|
| 18, 85 | `from curriculum.syllabus import ROLE_TRACKS, WEEKS` | Entire export logic iterates WEEKS | When WEEKS is replaced by DB content, this script becomes a one-time migration export only |
| 75-130 | `build_curriculum_seed_export()` | Produces `TrackSeedRecord`, `ModuleSeedRecord`, `TopicSeedRecord` structures from WEEKS | Keep structure; point at new DB data source after migration |

### Agent files (do not modify per constraints)

These are noted for awareness only:

- `agents/learning_coach.py` (line ~485): `"Current week: {session.current_week} / 13"` — hardcoded 13 is a pre-existing copy bug, should be `TOTAL_WEEKS`
- `agents/practice_arena.py` (lines ~294, ~334): Uses `session.current_week` for prompt context
- `agents/idea_generator.py` (line ~81): Calls `format_week_context(session.track.value, session.current_week)`
- These will naturally update once `session.current_week` is replaced or aliased

### `harness/usage_policy.py`, `harness/context_builder.py`, `harness/prompt_templates.py`

No direct week-structure dependency. The harness reads from `session.current_week` via
`SessionContext`, so it will benefit automatically once that field is updated.

---

## 3. Runtime Dependencies

The following learner-facing routes currently depend on week/track static structure:

| Route | File | Week Dependency | Impact |
|-------|------|----------------|--------|
| `GET /topics/{session_id}` | `app.py` | `get_topics_for_week(track, current_week)` — only shows current week's topics | Learner cannot browse other modules without changing weeks |
| `POST /session/start` | `app.py` | Accepts `week: int` — sets `session.current_week` | Session start is week-anchored |
| `GET /syllabus/{session_id}` | `app.py` | Iterates `WEEKS` directly | Entire syllabus page is static week data |
| `GET /topic/{session_id}/{topic_id}` | `routes/topics.py` | Validates topic via `get_topic(track, topic_id)` which reads WEEKS | Works fine but topic set is fixed to static WEEKS |
| `GET /dashboard` | `app.py` | `build_dashboard_learning_summary` uses `get_topics_for_week` | Progress bar / topic count is week-scoped |
| Chat sidebar | `_session_progress()` in `app.py` | `current_week`, `total_weeks` exposed to template | Sidebar shows "Week X / 5" |

Content generation routes (`/topic/content`, `/topic/practice`, `/quiz/*`, `/portfolio/*`,
`/interview/*`) do **not** depend on week structure — they use `topic_id` directly and
read from `SessionContext`. These require no change.

---

## 4. Database Dependencies

### Existing curriculum tables

The three tables added in the earlier DB schema work (`database/schema.sql`, lines 79–132)
already anticipate the modular model:

| Table | Key Fields | Week Coupling | Notes |
|-------|-----------|--------------|-------|
| `learning_tracks` | `track_key`, `title`, `status`, `metadata` | None | Clean; no week concept |
| `learning_modules` | `track_id`, `module_key`, `title`, `sequence_order` | None | `sequence_order` replaces week number; flexible |
| `learning_topics` | `module_id`, `topic_key`, `title`, `sequence_order`, `freshness_label` | Indirect via seed | `sequence_order` is flexible; current topics seeded from WEEKS inherit week-shaped grouping |

**The DB tables are structurally flexible.** They use `sequence_order` rather than
`week_number`. However, because the seed data comes from `WEEKS`, the current
`module_key` values are things like `week-1`, `week-2` — the week concept leaks through
the seed values even though the schema itself is week-agnostic.

### `topic_progress` table

Uses `legacy_topic_id TEXT` to store the current string topic IDs (e.g.
`aipm-week-1-ai-vs-ml-vs-dl`). The `week` string is embedded in these IDs. During
migration this column bridges old and new; it should be preserved until all stored
progress rows are re-keyed or the column is treated as permanent legacy storage.

### Missing tables for target model

The target Course → Module → **Skill** → Topic → **Activity** model requires two tables
not yet in the schema:

| Table | Purpose |
|-------|---------|
| `skills` | Named skill tags (e.g., "prompt engineering", "model evaluation") that span modules |
| `topic_skills` | Many-to-many join: which skills each topic develops |
| `topic_activities` | Ordered activity sequence per topic (learn → quiz → portfolio → interview → reflection) |

`topic_activities` would replace the current hardcoded `RECOMMENDED_ACTIONS` list in
`curriculum/topics.py`.

---

## 5. Template/UI Dependencies

| Template | Line(s) | Week Language | Suggested Replacement |
|----------|---------|--------------|----------------------|
| `templates/chat.html` | 11 | `"Week {{ progress.current_week }} / {{ progress.total_weeks }}"` | `"Module {{ progress.module_order }}"` or `"{{ progress.module_title }}"` |
| `templates/chat.html` | 32 | `"Browse Week Topics"` (button label) | `"Browse Topics"` or `"Browse Module Topics"` |
| `templates/chat.html` | 43 | `"Give me project ideas I can build this week"` (quick-action prompt) | `"Give me project ideas for this module"` |
| `templates/dashboard.html` | 215, 232-235 | Progress bar: `((s.current_week / 5) * 100)` | Drive from completion percent across topics, not week count |
| `templates/topics.html` | 9-10, 21 | `"Week {{ current_week }}"` heading | `"{{ module_title }}"` or `"Module {{ module_order }}"` |
| `templates/syllabus.html` | All | Entire page is a week-by-week static view | Replace with dynamic module listing once DB is primary |
| `templates/topic_detail.html` | 432 | `"View Syllabus"` link | `"View Learning Path"` or keep as-is until syllabus page is redesigned |

No template modification is required in this step.

---

## 6. Tests Depending on Week Structure

43 test files contain week-related references. The most structurally coupled are:

| Test File | Week Dependency | How to Update Later |
|-----------|----------------|---------------------|
| `tests/test_session.py` | `/session/start` with `week: 5`, `week: 8` | Replace `week` param with `module_order` once session start is updated |
| `tests/test_navigation.py` | `get_topics_for_week("aipm", 1)[0]` to get a test topic | Replace with `get_topics_for_track("aipm")[0]` or a fixture topic |
| `tests/test_topics_routes.py` | `get_topics_for_week("aipm", 1)[0]` in every test | Same replacement |
| `tests/test_dashboard_summary.py` | `get_topics_for_week("aipm", 1)` for topic count assertions | Replace with `get_topics_for_track("aipm")[:N]` |
| `tests/test_curriculum_seed_export.py` | Full export from WEEKS; asserts module_keys, week counts | Update assertions to expect `sequence_order`-based keys once seed is module-based |
| `tests/test_topics.py` | Tests `get_topics_for_week` function directly | Add tests for `get_topics_for_module`; keep old tests until function removed |
| `tests/conftest.py` | Creates test sessions with `week` parameter | Update fixture after session start schema changes |

Tests for content generation, submission, usage limits, caching, and write-through DB
have **no structural dependency on week number** — they use `topic_id` strings directly
and will require no changes during curriculum migration.

---

## 7. What Should Be Kept

The following capabilities were built independently of week structure and must be
preserved completely:

- **Structured topic learning flow** (learn → quiz → portfolio → interview → reflection)
  tracked in `session.topic_progress` and `topic_progress` DB table
- **AI content generation** (`services/content_service.py`) — topic-ID keyed, no week logic
- **Practice content generation** (`services/content_service.py`) — same
- **Quiz / portfolio / interview feedback** (`services/submission_service.py`) — same
- **Shared content cache** (`services/content_cache_service.py`, `content_cache` DB table)
  — keyed by `(track, topic_id, content_type, difficulty, language, version)`; topic IDs
  will change format during migration but the caching mechanism itself is sound
- **Usage limit enforcement** (`services/usage_limit_service.py`) — session-event based,
  no week coupling
- **DB write-through** (all `write_through_*` services) — writes to `topic_progress`,
  `generated_content`, `usage_events`; no week dependency
- **DB-first reads with fallback** (`curriculum_fallback_service.py`,
  `learner_state_fallback_service.py`) — flag-gated, no week dependency
- **Todos / learning planner** — `todo_type` is `daily`/`weekly` (user-preference labels,
  not curriculum weeks); no structural change needed
- **Learning outcomes** (`services/learning_outcome_service.py`)
- **Harness / rubrics / context builder** (`harness/`)
- **Beta feedback** (`services/beta_feedback_service.py`)
- **User auth / session ownership** — entirely separate concern

---

## 8. What Should Be Deprecated

| Item | Where | Why |
|------|-------|-----|
| `WEEKS` list in `curriculum/syllabus.py` | `curriculum/syllabus.py:24–556` | Replaced by `learning_topics` DB rows once seeded and verified |
| `MAX_WEEKS = 5` | `curriculum/syllabus.py:12` | Derived constant; irrelevant after WEEKS retired |
| `TOTAL_WEEKS = 5` | `config.py:31` | Replaced by dynamic module count |
| `current_week: int` on `SessionContext` | `context/session.py:47` | Replaced by per-learner module position tracked in DB or derived from progress |
| `advance_week()` method | `context/session.py:89` | Week advancement has no analogue in modular model |
| `get_topics_for_week(track, week_num)` | `curriculum/topics.py:95` | Replaced by module-keyed equivalent |
| `TopicCard.week_num` field | `curriculum/topics.py:25` | Replace with `module_order: int` |
| Topic IDs with `-week-N-` embedded | All stored session data | Must bridge via `legacy_topic_id`; cannot delete immediately |
| `get_task_key()` and `syllabus_progress` dict | `curriculum/syllabus.py:558`, `context/session.py:53` | Task-key-based syllabus tracking replaced by `topic_progress` step tracking (already done) |
| `SessionStartRequest.week` field | `app.py:590` | Remove once module-based start is wired |
| Week-based UI language ("Week X / 5", "Browse Week Topics") | `templates/` | Replace with module / learning path language |
| `ROLE_TRACKS` as **runtime source** | `curriculum/syllabus.py:16` | Move metadata to `learning_tracks` DB table; keep slug constants in `config.py` |

> **Note:** Do not delete these until the replacement path is verified end-to-end. Every
> item above should follow a deprecate-then-remove cycle with the DB fallback flag as
> the safety net.

---

## 9. Target Modular Curriculum Model

### Conceptual hierarchy

```
Course
  └── Module (ordered sequence within a course)
        └── Skill (cross-cutting tag, many-to-many with topics)
        └── Topic (ordered within a module)
              └── Activity (learn / quiz / portfolio / interview / reflection)
```

### Suggested DB entities

| Table | Key Columns | Notes |
|-------|------------|-------|
| `courses` | `course_id`, `course_key`, `title`, `description`, `status` | Top-level learning programme (e.g., "AI Career Accelerator") |
| `course_modules` | `module_id`, `course_id`, `module_key`, `title`, `sequence_order` | Replaces "week"; already exists as `learning_modules` |
| `skills` | `skill_id`, `skill_key`, `title`, `description`, `category` | Named capability tags |
| `course_topics` | `topic_id`, `module_id`, `topic_key`, `title`, `sequence_order`, `freshness_label`, `difficulty` | Already exists as `learning_topics` |
| `topic_skills` | `topic_id`, `skill_id` | Many-to-many join |
| `topic_activities` | `activity_id`, `topic_id`, `activity_type`, `activity_order` | Ordered activity sequence per topic; replaces hardcoded `RECOMMENDED_ACTIONS` |

### Mapping from current to target

| Current | Target |
|---------|--------|
| `WEEKS[i]` | `course_modules` row with `sequence_order = i` |
| `week_num` | `module.sequence_order` |
| `day` within a week | `topic.sequence_order` within a module |
| `RECOMMENDED_ACTIONS` list | `topic_activities` rows |
| `ROLE_TRACKS` dict | `learning_tracks` rows (already in schema) |
| `get_topics_for_week(track, week_num)` | `get_topics_for_module(track_key, module_order)` |
| Topic ID `{track}-week-{n}-{slug}` | `{track}-m{n}-{slug}` or pure DB `topic_id` |

The `learning_tracks`, `learning_modules`, and `learning_topics` tables already in the
schema map directly to `courses`/`course_modules`/`course_topics`. Adding `courses` as a
top-level table and `skills`/`topic_skills`/`topic_activities` completes the model.

---

## 10. Migration Strategy

This is the recommended safe sequence:

### Step 1 — Add modular schema beside current schema *(next step)*
Add `courses`, `skills`, `topic_skills`, `topic_activities` tables to `database/schema.sql`
as additive, non-breaking additions. No existing table is altered. No runtime code changes.

### Step 2 — Update seed/export adapter
Update `curriculum/seed_export.py` to emit `course_key`, `module_key` with
`sequence_order` instead of week-number-derived keys. Seed the new tables alongside the
existing ones. Verify content parity.

### Step 3 — Add DB read service for modular courses
Add `services/modular_curriculum_service.py` with `get_module_topics(track_key, module_order)`
and `get_topic_by_key(track_key, topic_key)`. Gate behind a new flag
`AI2_MODULAR_CURRICULUM_ENABLED`.

### Step 4 — Add fallback to old curriculum
Wire the new service into `curriculum/topics.py` functions using the same flag-gated
fallback pattern already used elsewhere:
- `AI2_MODULAR_CURRICULUM_ENABLED=1` → read from DB
- Flag off → fall back to current `WEEKS` iteration

This gives a zero-risk toggle.

### Step 5 — Update UI wording
Change template strings from "Week" to "Module" / "Learning path" / "Sequence".
This is cosmetic and can be done independently of the data migration.

### Step 6 — Update tests
Replace `get_topics_for_week("aipm", 1)` calls in tests with
`get_topics_for_track("aipm")[:N]` or module-keyed equivalents.
Update `_start_session` fixtures to use `module_order` instead of `week`.

### Step 7 — Remove old fixed curriculum only after replacement works
Once `AI2_MODULAR_CURRICULUM_ENABLED=1` is verified in staging:
1. Remove `WEEKS` from `curriculum/syllabus.py`
2. Remove `TOTAL_WEEKS` from `config.py`
3. Remove `current_week` / `advance_week` from `SessionContext`
4. Remove `get_topics_for_week` from `curriculum/topics.py`
5. Keep `ROLE_TRACKS` slugs in `config.py` as string constants for backward compatibility

**The `legacy_topic_id` column in `topic_progress` and other DB tables must be preserved
indefinitely** to support existing learner progress data.

---

## 11. Immediate Next Implementation Step

**Recommended: Add modular curriculum schema**

Extend `database/schema.sql` with three additive tables:
- `courses` — top-level course container
- `skills` — cross-cutting skill tags
- `topic_skills` — topic-to-skill many-to-many join
- `topic_activities` — ordered activity sequence per topic

No existing table is altered. No runtime code is touched. The current 5-week system
continues to run unchanged. This step establishes the target schema so the seed/export
and service layer can be built against a stable target in the following step.

---

## Summary

### Is the 13-week (5-week) dependency deeply embedded?

**Moderately embedded, not deeply.** The content and logic are well-separated:

- **Deeply embedded:** Topic IDs contain `-week-N-`, stored in DB progress rows and
  cached content. These cannot be renamed without a migration of existing learner data.
- **Moderately embedded:** `current_week` in `SessionContext` serialization; `WEEKS`
  iteration in topic generation; week-language in templates and agent prompts.
- **Shallowly embedded:** The DB curriculum tables already use `sequence_order` and are
  week-agnostic. The service layer, submission flows, caching, and usage limits have no
  week coupling at all.

### What can be safely removed after the replacement works?

In order of safety (easiest first):
1. Week language in templates (cosmetic only)
2. `TOTAL_WEEKS` constant and `advance_week()` method
3. `get_topics_for_week()` function (once callers updated)
4. `WEEKS` list in `curriculum/syllabus.py` (once seed verified)
5. `current_week` field on `SessionContext` (requires session migration plan)
6. `-week-N-` format in topic IDs (requires `legacy_topic_id` bridge and data migration)

### Confirmation

- **Documentation-only step:** Yes. No runtime files were modified.
- **No templates modified:** Yes.
- **No schema modified:** Yes.
- **No tests deleted or modified:** Yes.
- **Runtime behavior unchanged:** Yes. All existing learner-facing flows remain identical.
