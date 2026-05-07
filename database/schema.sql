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
)
