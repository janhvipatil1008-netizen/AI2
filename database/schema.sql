-- AI² unified schema for PostgreSQL (Supabase)
-- Executed at startup if the users table does not yet exist.

CREATE TABLE IF NOT EXISTS users (
    user_id       TEXT PRIMARY KEY,
    email         TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    display_name  TEXT,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id   TEXT PRIMARY KEY,
    session_data TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    user_id      TEXT REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS conversation_history (
    id              BIGSERIAL PRIMARY KEY,
    user_id         TEXT NOT NULL REFERENCES users(user_id),
    session_id      TEXT NOT NULL,
    user_message    TEXT NOT NULL,
    assistant_reply TEXT NOT NULL,
    agent_used      TEXT NOT NULL,
    timestamp       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS learner_profiles (
    user_id      TEXT PRIMARY KEY REFERENCES users(user_id),
    profile_data TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS jobs (
    id            TEXT PRIMARY KEY,
    external_id   TEXT UNIQUE NOT NULL,
    source        TEXT NOT NULL,
    title         TEXT NOT NULL,
    company       TEXT,
    location      TEXT,
    salary        TEXT,
    description   TEXT,
    date_posted   TEXT,
    job_url       TEXT NOT NULL,
    role_category TEXT,
    enriched      INTEGER DEFAULT 0,
    enriched_at   TEXT,
    created_at    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_jobs_role     ON jobs(role_category);
CREATE INDEX IF NOT EXISTS idx_jobs_enriched ON jobs(enriched);
CREATE INDEX IF NOT EXISTS idx_jobs_created  ON jobs(created_at);

CREATE TABLE IF NOT EXISTS job_enrichments (
    id                 TEXT PRIMARY KEY,
    job_id             TEXT NOT NULL UNIQUE REFERENCES jobs(id),
    summary            TEXT,
    skills_needed      TEXT,
    possible_questions TEXT,
    learning_guide     TEXT,
    quiz               TEXT,
    match_score        INTEGER,
    match_reasoning    TEXT,
    created_at         TEXT NOT NULL
);

-- ─────────────────────────────────────────────────────────────────────────────
-- Learning curriculum tables
-- Added as additive schema preparation. SessionContext remains the runtime
-- source of truth until migration is complete. No app logic reads these yet.
-- ─────────────────────────────────────────────────────────────────────────────

-- Stores flexible learning tracks (e.g. AI PM, AI Evals, Agent Engineering).
-- track_key is a stable slug used to look up a track by code.
CREATE TABLE IF NOT EXISTS learning_tracks (
    id          SERIAL PRIMARY KEY,
    track_key   TEXT NOT NULL UNIQUE,
    title       TEXT NOT NULL,
    description TEXT,
    status      TEXT NOT NULL DEFAULT 'active',
    version     TEXT NOT NULL DEFAULT 'v1',
    metadata    JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_learning_tracks_status   ON learning_tracks(status);

-- Stores modules/weeks/sections within a track.
-- sequence_order controls display ordering within the parent track.
CREATE TABLE IF NOT EXISTS learning_modules (
    id             SERIAL PRIMARY KEY,
    track_id       INTEGER NOT NULL REFERENCES learning_tracks(id) ON DELETE CASCADE,
    module_key     TEXT NOT NULL,
    title          TEXT NOT NULL,
    description    TEXT,
    sequence_order INTEGER NOT NULL DEFAULT 0,
    module_type    TEXT NOT NULL DEFAULT 'module',
    metadata       JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(track_id, module_key)
);

CREATE INDEX IF NOT EXISTS idx_learning_modules_track_id    ON learning_modules(track_id);
CREATE INDEX IF NOT EXISTS idx_learning_modules_track_order ON learning_modules(track_id, sequence_order);

-- Stores individual topics inside a module.
-- freshness_label mirrors the harness freshness classification for AI prompt tuning.
CREATE TABLE IF NOT EXISTS learning_topics (
    id                SERIAL PRIMARY KEY,
    module_id         INTEGER NOT NULL REFERENCES learning_modules(id) ON DELETE CASCADE,
    topic_key         TEXT NOT NULL,
    title             TEXT NOT NULL,
    description       TEXT,
    sequence_order    INTEGER NOT NULL DEFAULT 0,
    difficulty        TEXT,
    freshness_label   TEXT,
    estimated_minutes INTEGER,
    metadata          JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(module_id, topic_key)
);

CREATE INDEX IF NOT EXISTS idx_learning_topics_module_id    ON learning_topics(module_id);
CREATE INDEX IF NOT EXISTS idx_learning_topics_module_order ON learning_topics(module_id, sequence_order);
CREATE INDEX IF NOT EXISTS idx_learning_topics_freshness    ON learning_topics(freshness_label);

-- Stores per-user/session topic step progress.
-- Foreign keys to users and sessions use TEXT to match the existing schema.
-- topic_id references the new learning_topics table; legacy_topic_id holds the
-- current SessionContext string ID for backward compatibility during transition.
CREATE TABLE IF NOT EXISTS topic_progress (
    id                        SERIAL PRIMARY KEY,
    user_id                   TEXT REFERENCES users(user_id) ON DELETE CASCADE,
    session_id                TEXT REFERENCES sessions(session_id) ON DELETE CASCADE,
    topic_id                  INTEGER REFERENCES learning_topics(id) ON DELETE CASCADE,
    legacy_topic_id           TEXT,
    learn_status              TEXT NOT NULL DEFAULT 'not_started',
    quiz_status               TEXT NOT NULL DEFAULT 'not_started',
    portfolio_task_status     TEXT NOT NULL DEFAULT 'not_started',
    interview_practice_status TEXT NOT NULL DEFAULT 'not_started',
    reflection_status         TEXT NOT NULL DEFAULT 'not_started',
    completion_percent        INTEGER NOT NULL DEFAULT 0,
    last_activity_at          TIMESTAMPTZ,
    metadata                  JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at                TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_topic_progress_user_id        ON topic_progress(user_id);
CREATE INDEX IF NOT EXISTS idx_topic_progress_session_id     ON topic_progress(session_id);
CREATE INDEX IF NOT EXISTS idx_topic_progress_topic_id       ON topic_progress(topic_id);
CREATE INDEX IF NOT EXISTS idx_topic_progress_legacy_topic   ON topic_progress(legacy_topic_id);
CREATE INDEX IF NOT EXISTS idx_topic_progress_session_legacy ON topic_progress(session_id, legacy_topic_id);

-- Stores learner daily/weekly planner todos.
-- Foreign keys to users/sessions use TEXT to match the existing schema.
-- linked_topic_id references the new learning_topics table; legacy_linked_topic_id
-- holds the current SessionContext string topic ID for transition compatibility.
CREATE TABLE IF NOT EXISTS todos (
    id                     SERIAL PRIMARY KEY,
    user_id                TEXT REFERENCES users(user_id) ON DELETE CASCADE,
    session_id             TEXT REFERENCES sessions(session_id) ON DELETE CASCADE,
    todo_key               TEXT,
    title                  TEXT NOT NULL,
    todo_type              TEXT NOT NULL DEFAULT 'daily',
    status                 TEXT NOT NULL DEFAULT 'todo',
    linked_topic_id        INTEGER REFERENCES learning_topics(id) ON DELETE SET NULL,
    legacy_linked_topic_id TEXT,
    created_by             TEXT NOT NULL DEFAULT 'learner',
    due_label              TEXT,
    due_date               DATE,
    completed_at           TIMESTAMPTZ,
    metadata               JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_todos_user_id                ON todos(user_id);
CREATE INDEX IF NOT EXISTS idx_todos_session_id             ON todos(session_id);
CREATE INDEX IF NOT EXISTS idx_todos_todo_type              ON todos(todo_type);
CREATE INDEX IF NOT EXISTS idx_todos_status                 ON todos(status);
CREATE INDEX IF NOT EXISTS idx_todos_legacy_linked_topic_id ON todos(legacy_linked_topic_id);
CREATE INDEX IF NOT EXISTS idx_todos_due_date               ON todos(due_date);

-- ─────────────────────────────────────────────────────────────────────────────
-- Generated content and submission tables
-- Schema-only additions for AI-generated learning content, practice problems,
-- quiz/portfolio/interview submissions, and per-topic learner notes.
-- No runtime code reads or writes these tables yet.
-- ─────────────────────────────────────────────────────────────────────────────

-- Stores AI-generated explanations/summaries for individual topics.
-- version and source allow tracking content provenance and prompt changes.
CREATE TABLE IF NOT EXISTS generated_topic_content (
    id               SERIAL PRIMARY KEY,
    user_id          TEXT REFERENCES users(user_id) ON DELETE CASCADE,
    session_id       TEXT REFERENCES sessions(session_id) ON DELETE CASCADE,
    topic_id         INTEGER REFERENCES learning_topics(id) ON DELETE SET NULL,
    legacy_topic_id  TEXT,
    content          TEXT NOT NULL,
    model            TEXT,
    version          TEXT NOT NULL DEFAULT 'v1',
    freshness_label  TEXT,
    source           TEXT NOT NULL DEFAULT 'claude',
    metadata         JSONB NOT NULL DEFAULT '{}'::jsonb,
    generated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_generated_topic_content_session_id     ON generated_topic_content(session_id);
CREATE INDEX IF NOT EXISTS idx_generated_topic_content_legacy_topic   ON generated_topic_content(legacy_topic_id);
CREATE INDEX IF NOT EXISTS idx_generated_topic_content_topic_id       ON generated_topic_content(topic_id);
CREATE INDEX IF NOT EXISTS idx_generated_topic_content_generated_at   ON generated_topic_content(generated_at);
CREATE INDEX IF NOT EXISTS idx_generated_topic_content_session_legacy ON generated_topic_content(session_id, legacy_topic_id);

-- Stores AI-generated practice problems for individual topics.
-- practice_type distinguishes quiz questions, coding exercises, case studies, etc.
CREATE TABLE IF NOT EXISTS generated_topic_practice (
    id               SERIAL PRIMARY KEY,
    user_id          TEXT REFERENCES users(user_id) ON DELETE CASCADE,
    session_id       TEXT REFERENCES sessions(session_id) ON DELETE CASCADE,
    topic_id         INTEGER REFERENCES learning_topics(id) ON DELETE SET NULL,
    legacy_topic_id  TEXT,
    practice_type    TEXT NOT NULL,
    content          TEXT NOT NULL,
    model            TEXT,
    version          TEXT NOT NULL DEFAULT 'v1',
    freshness_label  TEXT,
    source           TEXT NOT NULL DEFAULT 'claude',
    metadata         JSONB NOT NULL DEFAULT '{}'::jsonb,
    generated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_generated_topic_practice_session_id         ON generated_topic_practice(session_id);
CREATE INDEX IF NOT EXISTS idx_generated_topic_practice_legacy_topic        ON generated_topic_practice(legacy_topic_id);
CREATE INDEX IF NOT EXISTS idx_generated_topic_practice_practice_type       ON generated_topic_practice(practice_type);
CREATE INDEX IF NOT EXISTS idx_generated_topic_practice_topic_id            ON generated_topic_practice(topic_id);
CREATE INDEX IF NOT EXISTS idx_generated_topic_practice_session_legacy_type ON generated_topic_practice(session_id, legacy_topic_id, practice_type);

-- Stores learner quiz attempt submissions and AI evaluations.
CREATE TABLE IF NOT EXISTS quiz_submissions (
    id               SERIAL PRIMARY KEY,
    user_id          TEXT REFERENCES users(user_id) ON DELETE CASCADE,
    session_id       TEXT REFERENCES sessions(session_id) ON DELETE CASCADE,
    topic_id         INTEGER REFERENCES learning_topics(id) ON DELETE SET NULL,
    legacy_topic_id  TEXT,
    answers          TEXT NOT NULL,
    evaluation       TEXT,
    score            INTEGER,
    model            TEXT,
    metadata         JSONB NOT NULL DEFAULT '{}'::jsonb,
    submitted_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    evaluated_at     TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_quiz_submissions_session_id     ON quiz_submissions(session_id);
CREATE INDEX IF NOT EXISTS idx_quiz_submissions_legacy_topic   ON quiz_submissions(legacy_topic_id);
CREATE INDEX IF NOT EXISTS idx_quiz_submissions_score          ON quiz_submissions(score);
CREATE INDEX IF NOT EXISTS idx_quiz_submissions_submitted_at   ON quiz_submissions(submitted_at);
CREATE INDEX IF NOT EXISTS idx_quiz_submissions_session_legacy ON quiz_submissions(session_id, legacy_topic_id);

-- Stores learner portfolio task submissions and AI feedback.
CREATE TABLE IF NOT EXISTS portfolio_submissions (
    id               SERIAL PRIMARY KEY,
    user_id          TEXT REFERENCES users(user_id) ON DELETE CASCADE,
    session_id       TEXT REFERENCES sessions(session_id) ON DELETE CASCADE,
    topic_id         INTEGER REFERENCES learning_topics(id) ON DELETE SET NULL,
    legacy_topic_id  TEXT,
    submission       TEXT NOT NULL,
    feedback         TEXT,
    score            INTEGER,
    model            TEXT,
    metadata         JSONB NOT NULL DEFAULT '{}'::jsonb,
    submitted_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_at      TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_portfolio_submissions_session_id     ON portfolio_submissions(session_id);
CREATE INDEX IF NOT EXISTS idx_portfolio_submissions_legacy_topic   ON portfolio_submissions(legacy_topic_id);
CREATE INDEX IF NOT EXISTS idx_portfolio_submissions_score          ON portfolio_submissions(score);
CREATE INDEX IF NOT EXISTS idx_portfolio_submissions_submitted_at   ON portfolio_submissions(submitted_at);
CREATE INDEX IF NOT EXISTS idx_portfolio_submissions_session_legacy ON portfolio_submissions(session_id, legacy_topic_id);

-- Stores learner interview practice submissions and AI feedback.
CREATE TABLE IF NOT EXISTS interview_submissions (
    id               SERIAL PRIMARY KEY,
    user_id          TEXT REFERENCES users(user_id) ON DELETE CASCADE,
    session_id       TEXT REFERENCES sessions(session_id) ON DELETE CASCADE,
    topic_id         INTEGER REFERENCES learning_topics(id) ON DELETE SET NULL,
    legacy_topic_id  TEXT,
    answer           TEXT NOT NULL,
    feedback         TEXT,
    score            INTEGER,
    model            TEXT,
    metadata         JSONB NOT NULL DEFAULT '{}'::jsonb,
    submitted_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_at      TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_interview_submissions_session_id     ON interview_submissions(session_id);
CREATE INDEX IF NOT EXISTS idx_interview_submissions_legacy_topic   ON interview_submissions(legacy_topic_id);
CREATE INDEX IF NOT EXISTS idx_interview_submissions_score          ON interview_submissions(score);
CREATE INDEX IF NOT EXISTS idx_interview_submissions_submitted_at   ON interview_submissions(submitted_at);
CREATE INDEX IF NOT EXISTS idx_interview_submissions_session_legacy ON interview_submissions(session_id, legacy_topic_id);

-- Stores learner reflection notes per topic: confusions, insights, and application ideas.
CREATE TABLE IF NOT EXISTS topic_notes (
    id               SERIAL PRIMARY KEY,
    user_id          TEXT REFERENCES users(user_id) ON DELETE CASCADE,
    session_id       TEXT REFERENCES sessions(session_id) ON DELETE CASCADE,
    topic_id         INTEGER REFERENCES learning_topics(id) ON DELETE SET NULL,
    legacy_topic_id  TEXT,
    reflection       TEXT,
    confusions       TEXT,
    application_idea TEXT,
    metadata         JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_topic_notes_session_id     ON topic_notes(session_id);
CREATE INDEX IF NOT EXISTS idx_topic_notes_legacy_topic   ON topic_notes(legacy_topic_id);
CREATE INDEX IF NOT EXISTS idx_topic_notes_topic_id       ON topic_notes(topic_id);
CREATE INDEX IF NOT EXISTS idx_topic_notes_updated_at     ON topic_notes(updated_at);
CREATE INDEX IF NOT EXISTS idx_topic_notes_session_legacy ON topic_notes(session_id, legacy_topic_id);

-- ---------------------------------------------------------------------------
-- Learning outcome validation tables
-- learning_outcomes tracks baseline and post-topic learning improvement for
-- a learner/session/topic. It is used to validate whether learners are improving.
-- This is a lightweight foundation, not a full automated model-eval suite yet.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS learning_outcomes (
    id                SERIAL PRIMARY KEY,
    user_id           TEXT REFERENCES users(user_id) ON DELETE CASCADE,
    session_id        TEXT REFERENCES sessions(session_id) ON DELETE CASCADE,
    legacy_topic_id   TEXT NOT NULL,
    topic_id          INTEGER REFERENCES learning_topics(id) ON DELETE SET NULL,
    baseline_prompt   TEXT,
    baseline_answer   TEXT,
    baseline_score    INTEGER,
    post_prompt       TEXT,
    post_answer       TEXT,
    post_score        INTEGER,
    improvement_delta INTEGER,
    status            TEXT NOT NULL DEFAULT 'started',
    metadata          JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(session_id, legacy_topic_id)
);

CREATE INDEX IF NOT EXISTS idx_learning_outcomes_user_id         ON learning_outcomes(user_id);
CREATE INDEX IF NOT EXISTS idx_learning_outcomes_session_id      ON learning_outcomes(session_id);
CREATE INDEX IF NOT EXISTS idx_learning_outcomes_legacy_topic    ON learning_outcomes(legacy_topic_id);
CREATE INDEX IF NOT EXISTS idx_learning_outcomes_topic_id        ON learning_outcomes(topic_id);
CREATE INDEX IF NOT EXISTS idx_learning_outcomes_status          ON learning_outcomes(status);
CREATE INDEX IF NOT EXISTS idx_learning_outcomes_created_at      ON learning_outcomes(created_at);
CREATE INDEX IF NOT EXISTS idx_learning_outcomes_updated_at      ON learning_outcomes(updated_at);
CREATE INDEX IF NOT EXISTS idx_learning_outcomes_session_legacy  ON learning_outcomes(session_id, legacy_topic_id);

-- ---------------------------------------------------------------------------
-- Private beta product feedback
-- beta_feedback stores lightweight learner feedback about AI² experiences.
-- It is for product validation, not AI training, and should not be used as
-- prompt input.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS beta_feedback (
    id                     SERIAL PRIMARY KEY,
    user_id                TEXT REFERENCES users(user_id) ON DELETE CASCADE,
    session_id             TEXT REFERENCES sessions(session_id) ON DELETE CASCADE,
    legacy_topic_id        TEXT,
    feedback_context       TEXT NOT NULL,
    usefulness_score       INTEGER,
    clarity_score          INTEGER,
    confusion              TEXT,
    improvement_suggestion TEXT,
    willingness_to_pay     TEXT,
    metadata               JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_beta_feedback_user_id          ON beta_feedback(user_id);
CREATE INDEX IF NOT EXISTS idx_beta_feedback_session_id       ON beta_feedback(session_id);
CREATE INDEX IF NOT EXISTS idx_beta_feedback_legacy_topic     ON beta_feedback(legacy_topic_id);
CREATE INDEX IF NOT EXISTS idx_beta_feedback_context          ON beta_feedback(feedback_context);
CREATE INDEX IF NOT EXISTS idx_beta_feedback_created_at       ON beta_feedback(created_at);

-- ---------------------------------------------------------------------------
-- Usage event tables
-- usage_events stores AI/harness usage events emitted by SessionContext and
-- HarnessRunRecord-compatible flows.
-- SessionContext remains the runtime source of truth for now.
-- DB write-through will be added later; sessions.session_data is unchanged.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS usage_events (
    id              SERIAL PRIMARY KEY,
    event_id        TEXT NOT NULL,
    user_id         TEXT REFERENCES users(user_id) ON DELETE CASCADE,
    session_id      TEXT REFERENCES sessions(session_id) ON DELETE CASCADE,
    legacy_topic_id TEXT,
    event_type      TEXT NOT NULL,
    model           TEXT,
    source          TEXT NOT NULL,
    status          TEXT NOT NULL,
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_usage_events_event_id       ON usage_events(event_id);
CREATE INDEX IF NOT EXISTS idx_usage_events_user_id               ON usage_events(user_id);
CREATE INDEX IF NOT EXISTS idx_usage_events_session_id            ON usage_events(session_id);
CREATE INDEX IF NOT EXISTS idx_usage_events_legacy_topic          ON usage_events(legacy_topic_id);
CREATE INDEX IF NOT EXISTS idx_usage_events_event_type            ON usage_events(event_type);
CREATE INDEX IF NOT EXISTS idx_usage_events_source                ON usage_events(source);
CREATE INDEX IF NOT EXISTS idx_usage_events_status                ON usage_events(status);
CREATE INDEX IF NOT EXISTS idx_usage_events_created_at            ON usage_events(created_at);
CREATE INDEX IF NOT EXISTS idx_usage_events_session_legacy_topic  ON usage_events(session_id, legacy_topic_id);
CREATE INDEX IF NOT EXISTS idx_usage_events_session_event_type    ON usage_events(session_id, event_type);

-- ─────────────────────────────────────────────────────────────────────────────
-- Shared AI-generated content cache
-- content_cache stores reusable canonical AI-generated learning content
-- (base lessons, practice task instructions, quiz templates, interview question
-- sets) that can be shared across learner sessions to reduce repeated Claude calls.
-- Personalised feedback and submission-specific responses must NOT be stored here;
-- only shared canonical content belongs in this table.
-- Runtime caching logic will be wired in a later step; this is schema-only.
-- ─────────────────────────────────────────────────────────────────────────────

-- cache_key is a stable, deterministic identifier for a content variant, used as
-- the primary lookup key. track_key and legacy_topic_id allow fast single-table
-- lookups without joining learning_topics during the dual-ID transition period.
-- difficulty_level, language, and version are first-class cache dimensions so the
-- same topic can yield different cached content for different learner contexts.
CREATE TABLE IF NOT EXISTS content_cache (
    id               SERIAL PRIMARY KEY,
    cache_key        TEXT NOT NULL,
    track_key        TEXT,
    legacy_topic_id  TEXT,
    topic_id         INTEGER REFERENCES learning_topics(id) ON DELETE SET NULL,
    content_type     TEXT NOT NULL,
    difficulty_level TEXT NOT NULL DEFAULT 'beginner',
    language         TEXT NOT NULL DEFAULT 'en',
    version          TEXT NOT NULL DEFAULT 'v1',
    provider         TEXT,
    model            TEXT,
    content          TEXT NOT NULL,
    metadata         JSONB NOT NULL DEFAULT '{}'::jsonb,
    status           TEXT NOT NULL DEFAULT 'active',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_content_cache_cache_key        ON content_cache(cache_key);
CREATE INDEX IF NOT EXISTS idx_content_cache_track_key               ON content_cache(track_key);
CREATE INDEX IF NOT EXISTS idx_content_cache_legacy_topic_id         ON content_cache(legacy_topic_id);
CREATE INDEX IF NOT EXISTS idx_content_cache_topic_id                ON content_cache(topic_id);
CREATE INDEX IF NOT EXISTS idx_content_cache_content_type            ON content_cache(content_type);
CREATE INDEX IF NOT EXISTS idx_content_cache_difficulty_level        ON content_cache(difficulty_level);
CREATE INDEX IF NOT EXISTS idx_content_cache_language                ON content_cache(language);
CREATE INDEX IF NOT EXISTS idx_content_cache_version                 ON content_cache(version);
CREATE INDEX IF NOT EXISTS idx_content_cache_status                  ON content_cache(status);
CREATE INDEX IF NOT EXISTS idx_content_cache_created_at              ON content_cache(created_at);
CREATE INDEX IF NOT EXISTS idx_content_cache_updated_at              ON content_cache(updated_at);
CREATE INDEX IF NOT EXISTS idx_content_cache_lookup                  ON content_cache(track_key, legacy_topic_id, content_type, difficulty_level, language, version, status);

-- ─────────────────────────────────────────────────────────────────────────────
-- Modular curriculum schema
-- Replaces the fixed week-based dependency (WEEKS / week_number) over time.
-- The target model is: Course → Module → Topic → Activity, with Skills as
-- cross-cutting tags that span modules and topics.
--
-- The old tables (learning_tracks, learning_modules, learning_topics) remain
-- in place and continue to be used as the seed/fallback source during
-- migration.  WEEKS and ROLE_TRACKS in curriculum/syllabus.py are still the
-- runtime source of truth; these tables will become primary in a later step.
--
-- Runtime reads will be migrated behind a feature flag
-- (AI2_MODULAR_CURRICULUM_ENABLED) in a subsequent step.
-- ─────────────────────────────────────────────────────────────────────────────

-- Top-level learning programme container.
-- A course groups modules into a coherent learning journey for a target audience.
CREATE TABLE IF NOT EXISTS courses (
    course_id       SERIAL PRIMARY KEY,
    course_key      TEXT NOT NULL UNIQUE,
    title           TEXT NOT NULL,
    description     TEXT,
    target_audience TEXT,
    level           TEXT NOT NULL DEFAULT 'beginner',
    status          TEXT NOT NULL DEFAULT 'draft',
    version         TEXT NOT NULL DEFAULT 'v1',
    sequence_order  INTEGER NOT NULL DEFAULT 0,
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_courses_course_key      ON courses(course_key);
CREATE INDEX IF NOT EXISTS idx_courses_status          ON courses(status);
CREATE INDEX IF NOT EXISTS idx_courses_level           ON courses(level);
CREATE INDEX IF NOT EXISTS idx_courses_sequence_order  ON courses(sequence_order);

-- Ordered sections within a course.
-- Replaces the fixed week concept; sequence_order drives display ordering.
-- module_key is a stable slug unique within its parent course.
CREATE TABLE IF NOT EXISTS course_modules (
    module_id      SERIAL PRIMARY KEY,
    course_id      INTEGER NOT NULL REFERENCES courses(course_id) ON DELETE CASCADE,
    module_key     TEXT NOT NULL,
    title          TEXT NOT NULL,
    description    TEXT,
    sequence_order INTEGER NOT NULL DEFAULT 0,
    estimated_minutes INTEGER,
    status         TEXT NOT NULL DEFAULT 'active',
    metadata       JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(course_id, module_key)
);

CREATE INDEX IF NOT EXISTS idx_course_modules_course_id             ON course_modules(course_id);
CREATE INDEX IF NOT EXISTS idx_course_modules_module_key            ON course_modules(module_key);
CREATE INDEX IF NOT EXISTS idx_course_modules_status                ON course_modules(status);
CREATE INDEX IF NOT EXISTS idx_course_modules_sequence_order        ON course_modules(sequence_order);
CREATE INDEX IF NOT EXISTS idx_course_modules_course_sequence       ON course_modules(course_id, sequence_order);

-- Named capability tags that can span modules and courses.
-- Skills are cross-cutting: one topic can develop multiple skills;
-- one skill can appear across many topics.
CREATE TABLE IF NOT EXISTS skills (
    skill_id    SERIAL PRIMARY KEY,
    skill_key   TEXT NOT NULL UNIQUE,
    title       TEXT NOT NULL,
    description TEXT,
    category    TEXT,
    level       TEXT,
    metadata    JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_skills_skill_key  ON skills(skill_key);
CREATE INDEX IF NOT EXISTS idx_skills_category   ON skills(category);
CREATE INDEX IF NOT EXISTS idx_skills_level      ON skills(level);

-- Individual learning topics within a course module.
-- legacy_topic_id bridges the current SessionContext string topic ID
-- (format: {track}-week-{n}-{slug}) so that existing learner progress rows
-- can be linked during the transition period.
CREATE TABLE IF NOT EXISTS course_topics (
    topic_id          SERIAL PRIMARY KEY,
    course_id         INTEGER NOT NULL REFERENCES courses(course_id) ON DELETE CASCADE,
    module_id         INTEGER REFERENCES course_modules(module_id) ON DELETE SET NULL,
    legacy_topic_id   TEXT,
    topic_key         TEXT NOT NULL,
    title             TEXT NOT NULL,
    description       TEXT,
    difficulty_level  TEXT NOT NULL DEFAULT 'beginner',
    sequence_order    INTEGER NOT NULL DEFAULT 0,
    estimated_minutes INTEGER,
    status            TEXT NOT NULL DEFAULT 'active',
    metadata          JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(course_id, topic_key)
);

CREATE INDEX IF NOT EXISTS idx_course_topics_course_id            ON course_topics(course_id);
CREATE INDEX IF NOT EXISTS idx_course_topics_module_id            ON course_topics(module_id);
CREATE INDEX IF NOT EXISTS idx_course_topics_legacy_topic_id      ON course_topics(legacy_topic_id);
CREATE INDEX IF NOT EXISTS idx_course_topics_topic_key            ON course_topics(topic_key);
CREATE INDEX IF NOT EXISTS idx_course_topics_difficulty_level     ON course_topics(difficulty_level);
CREATE INDEX IF NOT EXISTS idx_course_topics_status               ON course_topics(status);
CREATE INDEX IF NOT EXISTS idx_course_topics_sequence_order       ON course_topics(sequence_order);
CREATE INDEX IF NOT EXISTS idx_course_topics_course_sequence      ON course_topics(course_id, sequence_order);
CREATE INDEX IF NOT EXISTS idx_course_topics_module_sequence      ON course_topics(module_id, sequence_order);

-- Many-to-many join between topics and skills.
-- importance distinguishes core skills from supplementary ones.
CREATE TABLE IF NOT EXISTS topic_skills (
    topic_id   INTEGER NOT NULL REFERENCES course_topics(topic_id) ON DELETE CASCADE,
    skill_id   INTEGER NOT NULL REFERENCES skills(skill_id) ON DELETE CASCADE,
    importance TEXT NOT NULL DEFAULT 'core',
    PRIMARY KEY (topic_id, skill_id)
);

CREATE INDEX IF NOT EXISTS idx_topic_skills_skill_id    ON topic_skills(skill_id);
CREATE INDEX IF NOT EXISTS idx_topic_skills_importance  ON topic_skills(importance);

-- Ordered activity sequence per topic.
-- activity_type maps to the existing journey steps: learn, quiz, portfolio_task,
-- interview_practice, reflection.  rubric_key links to the harness rubric used
-- to evaluate the activity.  Replaces the hardcoded RECOMMENDED_ACTIONS list.
CREATE TABLE IF NOT EXISTS topic_activities (
    activity_id    SERIAL PRIMARY KEY,
    topic_id       INTEGER NOT NULL REFERENCES course_topics(topic_id) ON DELETE CASCADE,
    activity_key   TEXT NOT NULL,
    activity_type  TEXT NOT NULL,
    title          TEXT,
    instructions   TEXT,
    rubric_key     TEXT,
    sequence_order INTEGER NOT NULL DEFAULT 0,
    is_required    BOOLEAN NOT NULL DEFAULT true,
    metadata       JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(topic_id, activity_key)
);

CREATE INDEX IF NOT EXISTS idx_topic_activities_topic_id         ON topic_activities(topic_id);
CREATE INDEX IF NOT EXISTS idx_topic_activities_activity_type    ON topic_activities(activity_type);
CREATE INDEX IF NOT EXISTS idx_topic_activities_sequence_order   ON topic_activities(sequence_order);
CREATE INDEX IF NOT EXISTS idx_topic_activities_is_required      ON topic_activities(is_required);
CREATE INDEX IF NOT EXISTS idx_topic_activities_topic_sequence   ON topic_activities(topic_id, sequence_order);

-- ─────────────────────────────────────────────────────────────────────────────
-- Learner course enrollment state
-- This supports modular curriculum progress and will eventually replace
-- current_week.  current_week remains temporarily in SessionContext for
-- compatibility with existing serialized sessions and static fallback paths.
--
-- legacy_topic_id/current_legacy_topic_id are preserved because old progress,
-- generated content, submissions, notes, content cache rows, and usage events
-- still use legacy string topic IDs during the migration.
--
-- Module/topic progress should be derived from completed topic activities over
-- time.  These tables are additive schema only; runtime source of truth remains
-- SessionContext until a later flagged migration step.
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS learner_course_enrollments (
    enrollment_id           SERIAL PRIMARY KEY,
    user_id                 TEXT REFERENCES users(user_id) ON DELETE CASCADE,
    session_id              TEXT NOT NULL,
    course_id               INTEGER REFERENCES courses(course_id) ON DELETE SET NULL,
    course_key              TEXT NOT NULL,
    status                  TEXT NOT NULL DEFAULT 'active',
    started_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at            TIMESTAMPTZ,
    current_module_id       INTEGER REFERENCES course_modules(module_id) ON DELETE SET NULL,
    current_module_key      TEXT,
    current_topic_id        INTEGER REFERENCES course_topics(topic_id) ON DELETE SET NULL,
    current_topic_key       TEXT,
    current_legacy_topic_id TEXT,
    progress_percent        INTEGER NOT NULL DEFAULT 0,
    metadata                JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, session_id, course_key)
);

CREATE INDEX IF NOT EXISTS idx_learner_course_enrollments_user_id              ON learner_course_enrollments(user_id);
CREATE INDEX IF NOT EXISTS idx_learner_course_enrollments_session_id           ON learner_course_enrollments(session_id);
CREATE INDEX IF NOT EXISTS idx_learner_course_enrollments_course_key           ON learner_course_enrollments(course_key);
CREATE INDEX IF NOT EXISTS idx_learner_course_enrollments_status               ON learner_course_enrollments(status);
CREATE INDEX IF NOT EXISTS idx_learner_course_enrollments_current_module_key   ON learner_course_enrollments(current_module_key);
CREATE INDEX IF NOT EXISTS idx_learner_course_enrollments_current_topic_key    ON learner_course_enrollments(current_topic_key);
CREATE INDEX IF NOT EXISTS idx_learner_course_enrollments_current_legacy_topic ON learner_course_enrollments(current_legacy_topic_id);
CREATE INDEX IF NOT EXISTS idx_learner_course_enrollments_user_session         ON learner_course_enrollments(user_id, session_id);
CREATE INDEX IF NOT EXISTS idx_learner_course_enrollments_user_course          ON learner_course_enrollments(user_id, course_key);

CREATE TABLE IF NOT EXISTS learner_module_progress (
    module_progress_id SERIAL PRIMARY KEY,
    enrollment_id      INTEGER REFERENCES learner_course_enrollments(enrollment_id) ON DELETE CASCADE,
    module_id          INTEGER REFERENCES course_modules(module_id) ON DELETE SET NULL,
    module_key         TEXT NOT NULL,
    status             TEXT NOT NULL DEFAULT 'not_started',
    completed_topics   INTEGER NOT NULL DEFAULT 0,
    total_topics       INTEGER NOT NULL DEFAULT 0,
    progress_percent   INTEGER NOT NULL DEFAULT 0,
    started_at         TIMESTAMPTZ,
    completed_at       TIMESTAMPTZ,
    metadata           JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(enrollment_id, module_key)
);

CREATE INDEX IF NOT EXISTS idx_learner_module_progress_enrollment_id    ON learner_module_progress(enrollment_id);
CREATE INDEX IF NOT EXISTS idx_learner_module_progress_module_key       ON learner_module_progress(module_key);
CREATE INDEX IF NOT EXISTS idx_learner_module_progress_status           ON learner_module_progress(status);
CREATE INDEX IF NOT EXISTS idx_learner_module_progress_progress_percent ON learner_module_progress(progress_percent);

CREATE TABLE IF NOT EXISTS learner_topic_progress (
    topic_progress_id            SERIAL PRIMARY KEY,
    enrollment_id                INTEGER REFERENCES learner_course_enrollments(enrollment_id) ON DELETE CASCADE,
    module_key                   TEXT,
    topic_id                     INTEGER REFERENCES course_topics(topic_id) ON DELETE SET NULL,
    topic_key                    TEXT NOT NULL,
    legacy_topic_id              TEXT,
    status                       TEXT NOT NULL DEFAULT 'not_started',
    completion_percent           INTEGER NOT NULL DEFAULT 0,
    required_activities_completed INTEGER NOT NULL DEFAULT 0,
    required_activities_total    INTEGER NOT NULL DEFAULT 0,
    started_at                   TIMESTAMPTZ,
    completed_at                 TIMESTAMPTZ,
    metadata                     JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at                   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(enrollment_id, topic_key)
);

CREATE INDEX IF NOT EXISTS idx_learner_topic_progress_enrollment_id      ON learner_topic_progress(enrollment_id);
CREATE INDEX IF NOT EXISTS idx_learner_topic_progress_module_key         ON learner_topic_progress(module_key);
CREATE INDEX IF NOT EXISTS idx_learner_topic_progress_topic_key          ON learner_topic_progress(topic_key);
CREATE INDEX IF NOT EXISTS idx_learner_topic_progress_legacy_topic_id    ON learner_topic_progress(legacy_topic_id);
CREATE INDEX IF NOT EXISTS idx_learner_topic_progress_status             ON learner_topic_progress(status);
CREATE INDEX IF NOT EXISTS idx_learner_topic_progress_completion_percent ON learner_topic_progress(completion_percent);
