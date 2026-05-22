# AI² Git Staging Plan Before Render Smoke Deploy

## 1. Current Worktree Summary

`git status --short` shows a large dirty/untracked worktree. Nothing has been staged, committed, pushed, or deleted by this review.

Tracked modified files:

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

Untracked project directories/files include:

- `README.md`
- `core/`
- `curriculum/freshness.py`
- `curriculum/modular_seed_export.py`
- `curriculum/seed_export.py`
- `curriculum/topics.py`
- `docs/`
- `harness/`
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
- many focused `tests/test_*.py` files

Tracked `git diff --stat` reports 15 modified files with about 3378 insertions and 24 deletions. The largest tracked changes are in `app.py`, `database/schema.sql`, `context/session.py`, `static/style.css`, and `templates/dashboard.html`.

## 2. Safe To Stage

Safe to stage for modular migration after human review confirms the diff content:

- `database/schema.sql`
- `repositories/`
- `services/`
- `routes/`
- `curriculum/topics.py`
- `curriculum/modular_seed_export.py`
- `curriculum/seed_export.py`
- `curriculum/freshness.py`
- `scripts/seed_modular_curriculum.py`
- modular curriculum/enrollment/progress-related docs under `docs/`
- modular curriculum/enrollment/progress-related tests under `tests/`
- templates related to modular learner flows:
  - `templates/dashboard.html`
  - `templates/onboarding.html`
  - `templates/todos.html`
  - `templates/topic_detail.html`
  - `templates/topics.html`
  - `templates/storage_health.html`
  - `templates/beta_metrics.html`
- `static/topic_detail.js`

These files appear related to the modular curriculum foundation, learner enrollment, modular progress, dashboard/todos context, storage/debug views, and private beta readiness.

## 3. Needs Manual Review

Review carefully before staging:

- `auth.py`: production/security-sensitive.
- `config.py`: production constants and model/env-adjacent behavior.
- `.env.example`: must not contain real secrets and should match current production flags.
- `README.md`: deployment and feature-flag guidance should be checked for stale instructions.
- `static/style.css`: broad UI styling; confirm it is intentional and not unrelated churn.
- `templates/base.html`
- `templates/chat.html`
- `templates/index.html`
- `templates/login.html`
- `templates/signup.html`
- `templates/syllabus.html`
- `core/`: security/logging/config helpers; review for production implications.
- production/security docs and tests:
  - `docs/ai2-production-env-notes.md`
  - `docs/ai2-production-deployment-readiness-checkpoint.md`
  - `docs/ai2-render-smoke-deployment-checklist.md`
  - `tests/test_production_auth_config.py`
  - `tests/test_debug_endpoint_protection.py`

Also review any file that contains environment variable names, auth behavior, debug/admin access, production deployment instructions, or secret-handling logic.

## 4. Do Not Stage

Do not stage local/temp/secret artifacts:

- `.pytest_tmp/`
- `.pytest_cache/`
- `__pycache__/`
- `manual_tmp/`
- local database files:
  - `jobs.db`
  - `sessions.db`
  - `sessions.db-shm`
  - `sessions.db-wal`
- logs
- local exports
- `.env`
- any secret files
- any generated artifact that is not explicitly part of the app or tests

Do not delete these automatically. Review first, then clean intentionally if needed.

## 5. Suggested Commit Groups

Suggested commits:

1. **Modular curriculum foundation**
   - `database/schema.sql`
   - `curriculum/topics.py`
   - `curriculum/modular_seed_export.py`
   - `curriculum/seed_export.py`
   - modular curriculum repositories/services/tests
   - `scripts/seed_modular_curriculum.py`

2. **Learner enrollment and modular progress**
   - learner course enrollment repository/service/tests
   - modular progress service/write-through/snapshot/position services/tests
   - route hooks for best-effort enrollment/progress mirroring

3. **UI wording and dashboard/todos modular context**
   - dashboard enrollment/modular progress summary
   - todos modular context
   - topics/topic detail modular read flag behavior
   - related templates/static assets/tests

4. **Production readiness and deployment docs**
   - production env notes
   - production deployment readiness checkpoint
   - local regression cleanup review
   - Render smoke deployment checklist
   - advance-week/current-week deprecation docs

5. **Tests**
   - If the test set is too large to review with each feature commit, make one final test commit grouping all focused regression tests.

Because the changes are interdependent and many files are currently untracked, one single commit may be safer if the goal is a quick Render smoke deploy. If using one commit, use a clear message such as:

```text
Prepare modular curriculum migration foundation for Render smoke deploy
```

## 6. Pre-Commit Test Command

Run this broad safe batch before staging/committing:

```bash
python -m pytest tests/test_topics_routes.py tests/test_dashboard_summary.py tests/test_todo_routes.py tests/test_onboarding_flow.py tests/test_modular_progress_service.py tests/test_modular_position_service.py tests/test_production_auth_config.py tests/test_debug_endpoint_protection.py tests/test_render_smoke_deployment_checklist.py
```

Full `python -m pytest` should also be retried in a clean local environment, but the latest local full run had Windows temp/Playwright/live-server environment blockers.

## 7. Recommended Next Action

Manually review before staging.

Recommended workflow:

1. Inspect `git diff` for tracked files.
2. Inspect untracked directories with targeted `git diff --no-index` or file review.
3. Exclude `.pytest_tmp/`, `.pytest_cache/`, `__pycache__/`, `manual_tmp/`, local DB files, logs, local exports, `.env`, and any secret files.
4. Stage files by commit group using explicit paths.
5. Run the pre-commit test command.
6. Commit only after the staged diff has been reviewed.
7. Do not push until the commit history and Render smoke deploy flags are confirmed.

No automatic commit or push should happen from this plan.
