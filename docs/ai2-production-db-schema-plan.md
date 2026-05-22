# AI² Production DB Schema Plan

## 1. Goal

AI² currently stores most topic journey state inside `sessions.session_data` as serialized `SessionContext` JSON. That is useful for rapid iteration, but it limits production reliability once learners, topics, generated content, submissions, and observability data grow.

The goal of this schema plan is to move topic journey data into normalized database tables while keeping `sessions.session_data` as a backward-compatible fallback during migration. Normalized tables will make it easier to query learner progress, version AI-generated content, support multiple tracks and modules, build analytics, inspect usage, and evolve the curriculum without rewriting session JSON.

This plan is design documentation only. It does not change `database/schema.sql` yet and does not create a migration.

## 2. Design Principles

- The current syllabus is seed data, not the final curriculum.
- Support multiple learning tracks such as AI PM, Evals, and Context Engineering.
- Support modules/weeks without hard-coding the curriculum shape.
- Support flexible topics that can change independently of the temporary syllabus.
- Support AI-generated content versioning for learning content, practice content, feedback, and future regeneration flows.
- Support learner progress tracking at the topic and step level.
- Support analytics later without forcing analytics concerns into the first migration.
- Preserve backward compatibility during migration by keeping `SessionContext.from_dict()` and existing `sessions.session_data`.
- Prefer stable IDs and explicit foreign keys where possible.
- Avoid storing large prompts or sensitive learner text in observability tables.

## 3. Proposed Tables

### Curriculum Tables

#### `learning_tracks`

Purpose: Stores top-level learning tracks.

Suggested columns:

```sql
id UUID PRIMARY KEY,
track_key TEXT NOT NULL UNIQUE,
display_name TEXT NOT NULL,
description TEXT,
status TEXT NOT NULL DEFAULT 'active',
sort_order INTEGER NOT NULL DEFAULT 0,
created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
```

Important indexes:

```sql
CREATE UNIQUE INDEX idx_learning_tracks_track_key ON learning_tracks(track_key);
CREATE INDEX idx_learning_tracks_status_sort ON learning_tracks(status, sort_order);
```

Relationship to `user_id` / `session_id` / `topic_id`: Tracks are global curriculum records. Sessions and learner progress reference tracks indirectly through modules/topics.

Create now or later: Create now in the first migration.

#### `learning_modules`

Purpose: Stores track-specific curriculum groupings such as weeks, modules, units, or phases.

Suggested columns:

```sql
id UUID PRIMARY KEY,
track_id UUID NOT NULL REFERENCES learning_tracks(id),
module_key TEXT NOT NULL,
title TEXT NOT NULL,
description TEXT,
module_number INTEGER,
theme TEXT,
status TEXT NOT NULL DEFAULT 'active',
sort_order INTEGER NOT NULL DEFAULT 0,
created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
UNIQUE(track_id, module_key)
```

Important indexes:

```sql
CREATE INDEX idx_learning_modules_track_sort ON learning_modules(track_id, sort_order);
CREATE INDEX idx_learning_modules_status ON learning_modules(status);
```

Relationship to `user_id` / `session_id` / `topic_id`: Modules are global curriculum records under a track. Topics reference modules.

Create now or later: Create now in the first migration.

#### `learning_topics`

Purpose: Stores flexible topic cards independent of the temporary syllabus source.

Suggested columns:

```sql
id UUID PRIMARY KEY,
module_id UUID NOT NULL REFERENCES learning_modules(id),
topic_key TEXT NOT NULL,
title TEXT NOT NULL,
description TEXT,
learn_prompt TEXT,
quiz_prompt TEXT,
portfolio_prompt TEXT,
interview_prompt TEXT,
source_ref TEXT,
status TEXT NOT NULL DEFAULT 'active',
sort_order INTEGER NOT NULL DEFAULT 0,
created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
UNIQUE(module_id, topic_key)
```

Important indexes:

```sql
CREATE INDEX idx_learning_topics_module_sort ON learning_topics(module_id, sort_order);
CREATE INDEX idx_learning_topics_status ON learning_topics(status);
CREATE INDEX idx_learning_topics_topic_key ON learning_topics(topic_key);
```

Relationship to `user_id` / `session_id` / `topic_id`: Topics are global curriculum records. Learner-owned tables reference `learning_topics.id` as `topic_id`.

Create now or later: Create now in the first migration.

#### `topic_blueprints` or `topic_steps`

Purpose: Optional table for defining the available journey steps per topic or track. This keeps the system flexible if future tracks use different steps than `learn`, `quiz`, `portfolio_task`, `interview_practice`, and `reflection`.

Suggested columns:

```sql
id UUID PRIMARY KEY,
topic_id UUID REFERENCES learning_topics(id),
track_id UUID REFERENCES learning_tracks(id),
step_key TEXT NOT NULL,
display_name TEXT NOT NULL,
step_type TEXT NOT NULL,
required BOOLEAN NOT NULL DEFAULT true,
sort_order INTEGER NOT NULL DEFAULT 0,
created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
```

Important indexes:

```sql
CREATE INDEX idx_topic_steps_topic_sort ON topic_steps(topic_id, sort_order);
CREATE INDEX idx_topic_steps_track_sort ON topic_steps(track_id, sort_order);
CREATE UNIQUE INDEX idx_topic_steps_unique_topic_step ON topic_steps(topic_id, step_key);
```

Relationship to `user_id` / `session_id` / `topic_id`: Blueprint records are curriculum metadata. `topic_progress.step_key` can reference these logical step keys.

Create now or later: Later unless the first migration needs configurable step definitions immediately. The first migration can keep step keys as validated text.

### Learner Progress Tables

#### `topic_progress`

Purpose: Stores learner progress for each topic step.

Suggested columns:

```sql
id UUID PRIMARY KEY,
user_id UUID REFERENCES users(id),
session_id TEXT REFERENCES sessions(session_id),
topic_id UUID NOT NULL REFERENCES learning_topics(id),
step_key TEXT NOT NULL,
status TEXT NOT NULL,
started_at TIMESTAMPTZ,
completed_at TIMESTAMPTZ,
created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
UNIQUE(session_id, topic_id, step_key)
```

Important indexes:

```sql
CREATE INDEX idx_topic_progress_user_topic ON topic_progress(user_id, topic_id);
CREATE INDEX idx_topic_progress_session_topic ON topic_progress(session_id, topic_id);
CREATE INDEX idx_topic_progress_status ON topic_progress(status);
```

Relationship to `user_id` / `session_id` / `topic_id`: Should include `session_id` during migration because existing state is session-scoped. `user_id` enables future cross-session progress.

Create now or later: Create now in the first migration.

#### `todos`

Purpose: Stores learner todos currently held in `SessionContext.todos`.

Suggested columns:

```sql
id UUID PRIMARY KEY,
todo_id TEXT UNIQUE,
user_id UUID REFERENCES users(id),
session_id TEXT REFERENCES sessions(session_id),
linked_topic_id UUID REFERENCES learning_topics(id),
title TEXT NOT NULL,
todo_type TEXT NOT NULL,
status TEXT NOT NULL DEFAULT 'todo',
created_by TEXT NOT NULL DEFAULT 'learner',
due_label TEXT,
created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
completed_at TIMESTAMPTZ
```

Important indexes:

```sql
CREATE INDEX idx_todos_user_status ON todos(user_id, status);
CREATE INDEX idx_todos_session_status ON todos(session_id, status);
CREATE INDEX idx_todos_linked_topic ON todos(linked_topic_id);
CREATE INDEX idx_todos_type_status ON todos(todo_type, status);
```

Relationship to `user_id` / `session_id` / `topic_id`: During migration, keep `session_id`. Longer term, decide whether todos should be user-scoped across sessions.

Create now or later: Create now in the first migration.

#### `topic_notes`

Purpose: Stores learner reflection notes and application ideas per topic.

Suggested columns:

```sql
id UUID PRIMARY KEY,
user_id UUID REFERENCES users(id),
session_id TEXT REFERENCES sessions(session_id),
topic_id UUID NOT NULL REFERENCES learning_topics(id),
reflection TEXT,
confusions TEXT,
application_idea TEXT,
created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
UNIQUE(session_id, topic_id)
```

Important indexes:

```sql
CREATE INDEX idx_topic_notes_user_topic ON topic_notes(user_id, topic_id);
CREATE INDEX idx_topic_notes_session_topic ON topic_notes(session_id, topic_id);
```

Relationship to `user_id` / `session_id` / `topic_id`: Notes are learner-owned and topic-specific. Include both `user_id` and `session_id` during migration.

Create now or later: Phase 3.

### Generated Content Tables

#### `generated_topic_content`

Purpose: Stores AI-generated learning content per topic, learner/session, and version.

Suggested columns:

```sql
id UUID PRIMARY KEY,
user_id UUID REFERENCES users(id),
session_id TEXT REFERENCES sessions(session_id),
topic_id UUID NOT NULL REFERENCES learning_topics(id),
content TEXT NOT NULL,
model TEXT NOT NULL,
version INTEGER NOT NULL DEFAULT 1,
freshness_label TEXT,
generation_source TEXT NOT NULL DEFAULT 'claude',
created_at TIMESTAMPTZ NOT NULL DEFAULT now()
```

Important indexes:

```sql
CREATE INDEX idx_generated_topic_content_session_topic ON generated_topic_content(session_id, topic_id);
CREATE INDEX idx_generated_topic_content_user_topic ON generated_topic_content(user_id, topic_id);
CREATE UNIQUE INDEX idx_generated_topic_content_version ON generated_topic_content(session_id, topic_id, version);
```

Relationship to `user_id` / `session_id` / `topic_id`: Current behavior is session-specific generated content. Future design may allow reusable global content by adding a nullable `user_id`/`session_id` policy or a separate canonical content table.

Create now or later: Phase 2.

#### `generated_topic_practice`

Purpose: Stores AI-generated practice material per topic, practice type, learner/session, and version.

Suggested columns:

```sql
id UUID PRIMARY KEY,
user_id UUID REFERENCES users(id),
session_id TEXT REFERENCES sessions(session_id),
topic_id UUID NOT NULL REFERENCES learning_topics(id),
practice_type TEXT NOT NULL,
content TEXT NOT NULL,
model TEXT NOT NULL,
version INTEGER NOT NULL DEFAULT 1,
freshness_label TEXT,
generation_source TEXT NOT NULL DEFAULT 'claude',
created_at TIMESTAMPTZ NOT NULL DEFAULT now()
```

Important indexes:

```sql
CREATE INDEX idx_generated_practice_session_topic_type ON generated_topic_practice(session_id, topic_id, practice_type);
CREATE INDEX idx_generated_practice_user_topic_type ON generated_topic_practice(user_id, topic_id, practice_type);
CREATE UNIQUE INDEX idx_generated_practice_version ON generated_topic_practice(session_id, topic_id, practice_type, version);
```

Relationship to `user_id` / `session_id` / `topic_id`: Current behavior is session-specific. Practice content references a topic and a `practice_type` such as `quiz`, `portfolio_task`, or `interview_practice`.

Create now or later: Phase 2.

### Submission Tables

#### `quiz_submissions`

Purpose: Stores learner quiz answers and AI evaluation results.

Suggested columns:

```sql
id UUID PRIMARY KEY,
user_id UUID REFERENCES users(id),
session_id TEXT REFERENCES sessions(session_id),
topic_id UUID NOT NULL REFERENCES learning_topics(id),
answers TEXT NOT NULL,
evaluation TEXT,
score INTEGER,
model TEXT,
submitted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
evaluated_at TIMESTAMPTZ,
created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
```

Important indexes:

```sql
CREATE INDEX idx_quiz_submissions_session_topic ON quiz_submissions(session_id, topic_id);
CREATE INDEX idx_quiz_submissions_user_topic ON quiz_submissions(user_id, topic_id);
CREATE INDEX idx_quiz_submissions_score ON quiz_submissions(score);
```

Relationship to `user_id` / `session_id` / `topic_id`: Learner-owned, topic-specific, currently session-scoped.

Create now or later: Phase 3.

#### `portfolio_submissions`

Purpose: Stores learner portfolio task submissions and AI feedback.

Suggested columns:

```sql
id UUID PRIMARY KEY,
user_id UUID REFERENCES users(id),
session_id TEXT REFERENCES sessions(session_id),
topic_id UUID NOT NULL REFERENCES learning_topics(id),
submission TEXT NOT NULL,
feedback TEXT,
score INTEGER,
model TEXT,
submitted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
reviewed_at TIMESTAMPTZ,
created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
```

Important indexes:

```sql
CREATE INDEX idx_portfolio_submissions_session_topic ON portfolio_submissions(session_id, topic_id);
CREATE INDEX idx_portfolio_submissions_user_topic ON portfolio_submissions(user_id, topic_id);
CREATE INDEX idx_portfolio_submissions_score ON portfolio_submissions(score);
```

Relationship to `user_id` / `session_id` / `topic_id`: Learner-owned, topic-specific, currently session-scoped.

Create now or later: Phase 3.

#### `interview_submissions`

Purpose: Stores learner interview practice answers and AI feedback.

Suggested columns:

```sql
id UUID PRIMARY KEY,
user_id UUID REFERENCES users(id),
session_id TEXT REFERENCES sessions(session_id),
topic_id UUID NOT NULL REFERENCES learning_topics(id),
answer TEXT NOT NULL,
feedback TEXT,
score INTEGER,
model TEXT,
submitted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
reviewed_at TIMESTAMPTZ,
created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
```

Important indexes:

```sql
CREATE INDEX idx_interview_submissions_session_topic ON interview_submissions(session_id, topic_id);
CREATE INDEX idx_interview_submissions_user_topic ON interview_submissions(user_id, topic_id);
CREATE INDEX idx_interview_submissions_score ON interview_submissions(score);
```

Relationship to `user_id` / `session_id` / `topic_id`: Learner-owned, topic-specific, currently session-scoped.

Create now or later: Phase 3.

### Usage and Observability Tables

#### `usage_events`

Purpose: Stores lightweight AI usage and backend observability events currently held in `SessionContext.usage_events`.

Suggested columns:

```sql
id UUID PRIMARY KEY,
event_id TEXT UNIQUE,
user_id UUID REFERENCES users(id),
session_id TEXT REFERENCES sessions(session_id),
topic_id UUID REFERENCES learning_topics(id),
event_type TEXT NOT NULL,
model TEXT,
source TEXT NOT NULL,
status TEXT NOT NULL,
metadata JSONB NOT NULL DEFAULT '{}',
created_at TIMESTAMPTZ NOT NULL DEFAULT now()
```

Important indexes:

```sql
CREATE INDEX idx_usage_events_session_created ON usage_events(session_id, created_at DESC);
CREATE INDEX idx_usage_events_user_created ON usage_events(user_id, created_at DESC);
CREATE INDEX idx_usage_events_type_source ON usage_events(event_type, source);
CREATE INDEX idx_usage_events_status ON usage_events(status);
CREATE INDEX idx_usage_events_topic ON usage_events(topic_id);
```

Relationship to `user_id` / `session_id` / `topic_id`: Usage events may be session-specific, user-specific, topic-specific, or global backend events. Keep nullable `topic_id` for non-topic events.

Create now or later: Phase 4.

## 4. Migration Strategy

### Phase 1: Curriculum, Progress, and Todos

- Add `learning_tracks`.
- Add `learning_modules`.
- Add `learning_topics`.
- Add `topic_progress`.
- Add `todos`.
- Seed curriculum tables from the current syllabus projection.
- Keep `SessionContext` JSON as the fallback source of truth.
- Begin optional write-through for topic progress and todos after route/service behavior is stable.

### Phase 2: Generated Content and Practice

- Add `generated_topic_content`.
- Add `generated_topic_practice`.
- Store versions instead of overwriting prior generated content.
- Keep current `SessionContext.generated_topic_content` and `SessionContext.generated_topic_practice` during write-through.
- Preserve cache behavior by reading the latest version for a topic/session/practice type.

### Phase 3: Submissions and Notes

- Add `quiz_submissions`.
- Add `portfolio_submissions`.
- Add `interview_submissions`.
- Add `topic_notes`.
- Preserve current semantics for clearing feedback when learner text changes.
- Keep JSON copies during write-through until the migration is stable.

### Phase 4: Usage Events

- Add `usage_events`.
- Write `SessionContext.usage_events` to the DB.
- Keep metadata small and safe.
- Do not store full prompts, full learner submissions, or full generated content in usage metadata.

### Phase 5: DB-First Reads With JSON Fallback

- Gradually read from normalized DB tables first.
- Fall back to `sessions.session_data` when normalized rows are absent.
- Compare DB-derived state with JSON state in logs or internal diagnostics during migration.
- Remove JSON dependency only after production stability and backfill verification.

## 5. Backward Compatibility Strategy

- Do not delete `sessions.session_data`.
- Continue supporting `SessionContext.from_dict()` for old sessions.
- Use a write-through period where mutations write to both `SessionContext` and normalized DB tables.
- Later, read from DB first and fall back to `SessionContext` JSON.
- Keep route URLs and response payloads unchanged during migration.
- Avoid changing frontend templates during the database migration unless a later UI task explicitly requires it.
- Only remove the JSON dependency after stable migration, backfill validation, and rollback planning.

## 6. Open Decisions

- Should topics be global curriculum records, user-customized records, or a hybrid with user overrides?
- Should AI-generated content be per-user/session, reusable per topic, or both?
- Should todos be session-scoped or user-scoped across sessions?
- Should usage events be stored permanently, summarized into aggregates, or retained with a time-based policy?
- How should syllabus versioning work when the temporary seed syllabus changes?
- Should topic IDs remain derived slugs, become UUID-only, or preserve both?
- Should generated content versions support explicit parent/refresh relationships?
- Should progress be tracked per session, per user, or both with reconciliation rules?

## 7. Recommended First Migration

The first actual migration should create only the foundational tables needed for flexible curriculum and learner progress:

- `learning_tracks`
- `learning_modules`
- `learning_topics`
- `topic_progress`
- `todos`

This keeps the first migration small and reversible while establishing stable topic IDs and the core learner progress model. Generated content, submissions, notes, and usage events can follow once curriculum and progress reads/writes are proven stable.
