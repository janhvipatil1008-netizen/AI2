# AI² Production Deployment Readiness Checkpoint

## 1. Current Deployment Readiness Status

AI² appears safe to deploy for a controlled Render/Azure smoke test with conservative feature flags, assuming the production environment variables are set correctly and `database/schema.sql` is applied before any DB-backed features are enabled.

The safest first deployment posture is still SessionContext-first: keep modular curriculum reads and DB-primary todo/progress reads off, validate signup/login/onboarding/dashboard/topics, then enable DB mirrors and reads in small steps. Existing learner-facing behavior is designed to fall back safely when DB/enrollment/progress reads fail.

This checkpoint is an audit snapshot, not a release approval. The worktree is heavily dirty/untracked and needs human review before a production commit/deploy.

## 2. Required Production Environment Variables

- `AI2_ENV=production`
- `TEST_MODE=0`; in this app, do not set `AI2_TEST_MODE=1`
- `AUTH_SECRET`
- `AI2_DEBUG_TOKEN`
- `ANTHROPIC_API_KEY`
- `SUPABASE_DATABASE_URL`; this is the current DB env var read by `database/pool.py`. `DATABASE_URL` is mentioned in some docs/log redaction paths, but the current pool helper reads `SUPABASE_DATABASE_URL`.
- `AI2_DB_WRITE_THROUGH_ENABLED`
- `AI2_TODOS_DB_READS_ENABLED`
- `AI2_PROGRESS_DB_READS_ENABLED`
- `AI2_USAGE_LIMITS_ENABLED`
- `AI2_MODULAR_CURRICULUM_READS_ENABLED`

## 3. Recommended Flag Values for First Render/Azure Smoke Test

Recommended conservative values:

- `AI2_MODULAR_CURRICULUM_READS_ENABLED=false` initially
- Exact smoke-test recommendation: `AI2_MODULAR_CURRICULUM_READS_ENABLED=false initially`
- `AI2_DB_WRITE_THROUGH_ENABLED=false` until `database/schema.sql` is applied; then `true` for DB mirror smoke tests
- `AI2_TODOS_DB_READS_ENABLED=false` initially
- `AI2_PROGRESS_DB_READS_ENABLED=false` initially
- `AI2_USAGE_LIMITS_ENABLED=true`

After the first smoke test passes, enable DB-backed todo/progress reads only if the write-through and fallback behavior has already been verified against production data.

## 4. Database Schema Requirements

`database/schema.sql` must be applied before enabling DB-backed features.

Recently added or migration-relevant tables include:

- Modular curriculum tables: `courses`, `course_modules`, `skills`, `course_topics`, `topic_skills`, `topic_activities`
- `learner_course_enrollments`
- `learner_module_progress`
- `learner_topic_progress`
- `content_cache`
- `usage_events`
- `learning_outcomes`
- `beta_feedback`

Do not enable write-through, modular reads, progress reads, todo reads, usage limits backed by usage state, or debug validation until the target database has the expected schema.

## 5. Manual Seed Requirements

`scripts/seed_modular_curriculum.py` is manual only.

Run it only after `database/schema.sql` has been applied to the target database and `SUPABASE_DATABASE_URL` points at the intended production/staging database. The script is required before enabling `AI2_MODULAR_CURRICULUM_READS_ENABLED=true` in production because modular reads need seeded courses/modules/topics/activities.

Do not run seed scripts automatically during app startup or deployment.

## 6. Render Deployment Check

Before Render smoke testing:

- Confirm the latest Git commit is pushed to the Render-connected branch.
- Check Render build logs for successful `pip install -r requirements.txt`.
- Confirm Render starts `uvicorn app:app --host 0.0.0.0 --port $PORT`.
- Verify required environment variables in the Render dashboard.
- Verify `SUPABASE_DATABASE_URL` connectivity from runtime logs.
- Check Render runtime logs for startup errors, auth-secret errors, test-mode production blocks, and DB connection failures.
- Smoke test `/health`, `/login`, `/signup`, onboarding, `/dashboard`, `/topics/{session_id}`, and topic detail.

Current Render files found:

- `render.yaml`
- `Procfile`
- `runtime.txt`
- `requirements.txt`

## 7. Azure Deployment Check

Azure path for the first beta:

- Azure App Service for the FastAPI app.
- Azure Database for PostgreSQL for production storage.
- Application Insights for logs/metrics/traces.
- App Service environment variables for `AI2_ENV`, `AUTH_SECRET`, `AI2_DEBUG_TOKEN`, `ANTHROPIC_API_KEY`, `SUPABASE_DATABASE_URL`, and feature flags.
- Azure Key Vault later; useful, but not required for the first private beta smoke test.
- No Azure AI Foundry migration yet. Keep the existing Claude/Anthropic integration.

## 8. Smoke Test Checklist

Run with conservative flags first:

- Signup/login
- Onboarding
- Dashboard
- Topics listing
- Topic detail
- Lesson generation
- Practice generation
- Quiz feedback
- Portfolio feedback
- Interview feedback
- Todos
- Learning outcomes
- Beta feedback
- Privacy/terms
- `/debug/modular-curriculum` with `X-AI2-Debug-Token` in production
- `/admin/beta-metrics` with `X-AI2-Debug-Token` in production

Debug token protection matters: in production, protected debug/admin surfaces should require `AI2_DEBUG_TOKEN` and should not expose secrets, DB URLs, raw submissions, generated content, or private feedback.

## 9. Known Compatibility Notes

- `current_week` remains compatibility-only.
- Exact compatibility note: current_week remains compatibility-only.
- `WEEKS` and `ROLE_TRACKS` remain fallback/seed source.
- `legacy_topic_id` is still required to bridge old SessionContext state, content cache, submissions, notes, usage events, and modular topic rows.
- Modular progress is mirrored to DB, but `SessionContext` remains the runtime source of truth.
- Do not remove week compatibility before production smoke tests.
- Do not enable modular reads in production before schema, manual seed, and debug verification pass.

## 10. Dirty/Untracked Worktree Review

Observed `git status --short` includes:

Modified tracked files:

- `.env.example`
- `app.py`
- `auth.py`
- `config.py`
- `context/session.py`
- `curriculum/syllabus.py`
- `database/schema.sql`
- `static/style.css`
- `templates/base.html`
- `templates/chat.html`
- `templates/dashboard.html`
- `templates/index.html`
- `templates/login.html`
- `templates/signup.html`
- `templates/syllabus.html`

Untracked directories/files:

- `.pytest_tmp/`
- `README.md`
- `core/`
- `curriculum/freshness.py`
- `curriculum/modular_seed_export.py`
- `curriculum/seed_export.py`
- `curriculum/topics.py`
- `docs/`
- `harness/`
- `manual_tmp/`
- `repositories/`
- `routes/`
- `scripts/`
- `services/`
- `static/topic_detail.js`
- `templates/beta_metrics.html`
- `templates/onboarding.html`
- `templates/privacy.html`
- `templates/storage_health.html`
- `templates/terms.html`
- `templates/todos.html`
- `templates/topic_detail.html`
- `templates/topics.html`
- many `tests/test_*.py` files

Likely related to modular/storage/private-beta migration:

- `app.py`
- `config.py`
- `context/session.py`
- `curriculum/syllabus.py`
- `curriculum/topics.py`
- `curriculum/modular_seed_export.py`
- `database/schema.sql`
- `core/`
- `repositories/`
- `routes/`
- `scripts/`
- `services/`
- `templates/dashboard.html`
- `templates/todos.html`
- `templates/topic_detail.html`
- `templates/topics.html`
- `templates/onboarding.html`
- `templates/storage_health.html`
- modular/storage/onboarding/dashboard/todos/topics tests
- `docs/ai2-current-week-removal-checklist.md`
- `docs/ai2-advance-week-deprecation-plan.md`

Likely production/private-beta related and needs human review:

- `.env.example`
- `README.md`
- `auth.py`
- `templates/base.html`
- `templates/index.html`
- `templates/login.html`
- `templates/signup.html`
- `templates/privacy.html`
- `templates/terms.html`
- `templates/beta_metrics.html`
- `docs/ai2-production-env-notes.md`
- `docs/ai2-private-beta-launch-plan.md`
- production/auth/debug/beta/privacy tests

Likely unrelated or local-only cleanup candidates needing human review before commit:

- `.pytest_tmp/`
- `manual_tmp/`
- local SQLite files present in the workspace but not shown in `git status`
- `static/style.css` unless tied to current UI migration
- any broad template style changes not directly tied to deployment readiness

Do not delete anything from this list automatically. Review and stage intentionally.

## 11. What Not To Enable Yet

- Azure AI Foundry migration
- Payments
- Removing `current_week`
- Deleting `WEEKS` or `ROLE_TRACKS`
- Enabling modular reads in production before schema + manual seed + `/debug/modular-curriculum` verification
- DB-primary todo/progress reads before write-through/fallback smoke tests

## 12. Recommended Next Step

Run a local full regression test, review and stage the dirty worktree intentionally, then do a controlled Render smoke deployment with conservative flags.

Suggested order:

1. Apply `database/schema.sql` to the target staging/production database.
2. Deploy with modular reads and DB-primary reads disabled.
3. Verify `/health`, auth, onboarding, dashboard, topics, todos, and AI feedback flows.
4. Enable `AI2_DB_WRITE_THROUGH_ENABLED=true` and verify mirrors/debug views.
5. Run `scripts/seed_modular_curriculum.py` manually against the verified database.
6. Verify `/debug/modular-curriculum` with `AI2_DEBUG_TOKEN`.
7. Enable `AI2_MODULAR_CURRICULUM_READS_ENABLED=true` only after seed/debug verification passes.
