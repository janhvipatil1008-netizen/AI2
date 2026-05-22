# AI² Render Smoke Commit File List

## 1. Purpose

This file prepares one clean, reviewable commit for the Render smoke deployment. It turns the current dirty/untracked worktree into an explicit staging plan so the deployment commit can be built without staging temp files, local database files, secrets, or unrelated artifacts.

This is a planning document only. Do not stage, commit, push, delete, or run seed scripts from this file without a final human review.

## 2. Recommended Commit Strategy

Recommended strategy: one commit.

Commit message:

```bash
git commit -m "Add modular curriculum migration foundation"
```

The modular curriculum foundation, learner enrollment, modular progress mirroring, dashboard/todos context, compatibility markers, production docs, and focused tests are interdependent. One commit is safer for this Render smoke deploy because splitting the work now would make it easier to deploy a partial state where routes, services, templates, schema, or tests no longer line up.

## 3. Files Recommended To Stage

These files appear related to the modular migration foundation and should be staged only after reviewing their diffs.

### Core runtime changes

- `app.py`
- `context/session.py`
- `curriculum/syllabus.py`
- `database/schema.sql`

### Modular curriculum and learner enrollment

- `curriculum/freshness.py`
- `curriculum/modular_seed_export.py`
- `curriculum/seed_export.py`
- `curriculum/topics.py`
- `repositories/__init__.py`
- `repositories/content_cache_repository.py`
- `repositories/curriculum_repository.py`
- `repositories/generated_content_repository.py`
- `repositories/learner_course_enrollment_repository.py`
- `repositories/learning_outcomes_repository.py`
- `repositories/modular_curriculum_repository.py`
- `repositories/progress_repository.py`
- `repositories/submissions_repository.py`
- `repositories/todos_repository.py`
- `repositories/topic_notes_repository.py`
- `repositories/usage_events_repository.py`
- `routes/__init__.py`
- `routes/deps.py`
- `routes/submissions.py`
- `routes/todos.py`
- `routes/topics.py`
- `services/__init__.py`
- `services/content_cache_service.py`
- `services/content_service.py`
- `services/curriculum_fallback_service.py`
- `services/curriculum_read_service.py`
- `services/generated_learning_mismatch_service.py`
- `services/generated_learning_read_service.py`
- `services/learner_course_enrollment_service.py`
- `services/learner_state_fallback_service.py`
- `services/learner_state_read_service.py`
- `services/learning_outcome_service.py`
- `services/mismatch_logging_service.py`
- `services/modular_curriculum_fallback_service.py`
- `services/modular_curriculum_read_service.py`
- `services/modular_topic_adapter.py`
- `services/state_mismatch_service.py`
- `services/storage_flags.py`
- `services/submission_service.py`
- `services/usage_events_mismatch_service.py`
- `services/usage_limit_service.py`
- `services/write_through_generated_learning_service.py`
- `services/write_through_service.py`
- `services/write_through_usage_events_service.py`

### Modular progress and position services

- `services/dashboard_modular_progress_service.py`
- `services/modular_position_service.py`
- `services/modular_progress_service.py`
- `services/modular_progress_snapshot_service.py`
- `services/modular_progress_write_through_service.py`
- `services/todo_context_service.py`

### Templates/UI wording

- `static/topic_detail.js`
- `templates/beta_metrics.html`
- `templates/dashboard.html`
- `templates/onboarding.html`
- `templates/privacy.html`
- `templates/storage_health.html`
- `templates/terms.html`
- `templates/todos.html`
- `templates/topic_detail.html`
- `templates/topics.html`

### Scripts

- `scripts/seed_curriculum.py`
- `scripts/seed_modular_curriculum.py`

Seed scripts are stageable as code artifacts, but they must remain manual only. Do not run them automatically during deployment.

### Documentation

- `docs/ai2-advance-week-deprecation-plan.md`
- `docs/ai2-auth-user-ownership-review.md`
- `docs/ai2-current-week-removal-checklist.md`
- `docs/ai2-curriculum-dependency-audit.md`
- `docs/ai2-db-read-migration-plan.md`
- `docs/ai2-final-architecture-overview.md`
- `docs/ai2-final-cleanup-checklist.md`
- `docs/ai2-git-staging-plan.md`
- `docs/ai2-harness-engineering-plan.md`
- `docs/ai2-local-regression-cleanup-review.md`
- `docs/ai2-private-beta-launch-plan.md`
- `docs/ai2-production-db-schema-plan.md`
- `docs/ai2-production-deployment-readiness-checkpoint.md`
- `docs/ai2-production-env-notes.md`
- `docs/ai2-production-readiness-audit.md`
- `docs/ai2-render-smoke-commit-file-list.md`
- `docs/ai2-render-smoke-deployment-checklist.md`
- `docs/ai2-topic-journey-architecture.md`

### Tests

- `tests/test_advance_week_deprecation_plan.py`
- `tests/test_beta_feedback.py`
- `tests/test_beta_metrics_view.py`
- `tests/test_chat_context_module_wording.py`
- `tests/test_content_cache_repository.py`
- `tests/test_content_cache_runtime.py`
- `tests/test_content_service.py`
- `tests/test_curriculum_db_check_endpoint.py`
- `tests/test_curriculum_fallback_endpoint.py`
- `tests/test_curriculum_fallback_service.py`
- `tests/test_curriculum_read_service.py`
- `tests/test_curriculum_seed_export.py`
- `tests/test_dashboard_enrollment_summary.py`
- `tests/test_dashboard_modular_progress_summary.py`
- `tests/test_dashboard_summary.py`
- `tests/test_debug_endpoint_protection.py`
- `tests/test_freshness.py`
- `tests/test_generated_learning_db_check_endpoint.py`
- `tests/test_generated_learning_mismatch_endpoint.py`
- `tests/test_generated_learning_mismatch_service.py`
- `tests/test_generated_learning_read_service.py`
- `tests/test_generated_learning_repositories.py`
- `tests/test_git_staging_plan_doc.py`
- `tests/test_harness_foundation.py`
- `tests/test_interview_submission.py`
- `tests/test_learner_course_enrollment_repository.py`
- `tests/test_learner_course_enrollment_service.py`
- `tests/test_learner_state_db_check_endpoint.py`
- `tests/test_learner_state_fallback_endpoint.py`
- `tests/test_learner_state_fallback_service.py`
- `tests/test_learner_state_mismatch_endpoint.py`
- `tests/test_learner_state_read_service.py`
- `tests/test_learning_outcome_routes.py`
- `tests/test_learning_outcome_service.py`
- `tests/test_learning_outcome_ui.py`
- `tests/test_learning_outcomes_repository.py`
- `tests/test_local_regression_cleanup_review.py`
- `tests/test_logging_utils.py`
- `tests/test_mark_done_controls.py`
- `tests/test_mismatch_logging_service.py`
- `tests/test_modular_curriculum_debug_endpoint.py`
- `tests/test_modular_curriculum_fallback_service.py`
- `tests/test_modular_curriculum_read_service.py`
- `tests/test_modular_curriculum_repository.py`
- `tests/test_modular_curriculum_seed_export.py`
- `tests/test_modular_position_runtime_display.py`
- `tests/test_modular_position_service.py`
- `tests/test_modular_progress_service.py`
- `tests/test_modular_progress_snapshot_runtime.py`
- `tests/test_modular_progress_write_through_service.py`
- `tests/test_navigation.py`
- `tests/test_onboarding_course_enrollment.py`
- `tests/test_onboarding_flow.py`
- `tests/test_portfolio.py`
- `tests/test_privacy_terms_pages.py`
- `tests/test_production_auth_config.py`
- `tests/test_production_deployment_readiness_checkpoint.py`
- `tests/test_progress_db_first_routes.py`
- `tests/test_quiz_submission.py`
- `tests/test_render_smoke_commit_file_list.py`
- `tests/test_render_smoke_deployment_checklist.py`
- `tests/test_repositories_structure.py`
- `tests/test_repository_reads.py`
- `tests/test_schema_content_cache.py`
- `tests/test_schema_generated_learning_tables.py`
- `tests/test_schema_learner_course_enrollments.py`
- `tests/test_schema_learning_outcomes.py`
- `tests/test_schema_learning_tables.py`
- `tests/test_schema_modular_curriculum.py`
- `tests/test_schema_usage_events.py`
- `tests/test_seed_curriculum_script.py`
- `tests/test_seed_modular_curriculum_script.py`
- `tests/test_state_mismatch_service.py`
- `tests/test_storage_flags.py`
- `tests/test_storage_health_endpoint.py`
- `tests/test_storage_health_view.py`
- `tests/test_storage_status_endpoint.py`
- `tests/test_submission_service.py`
- `tests/test_todo_routes.py`
- `tests/test_todos.py`
- `tests/test_todos_db_first_routes.py`
- `tests/test_todos_modular_context.py`
- `tests/test_topic_content.py`
- `tests/test_topic_detail_modular_curriculum_flag.py`
- `tests/test_topic_notes.py`
- `tests/test_topic_practice.py`
- `tests/test_topics.py`
- `tests/test_topics_modular_curriculum_flag.py`
- `tests/test_topics_routes.py`
- `tests/test_usage_events_db_check_endpoint.py`
- `tests/test_usage_events_mismatch_endpoint.py`
- `tests/test_usage_events_mismatch_service.py`
- `tests/test_usage_events_repository.py`
- `tests/test_usage_limit_enforcement.py`
- `tests/test_usage_policy.py`
- `tests/test_usage_tracking.py`
- `tests/test_week_compatibility_markers.py`
- `tests/test_week_wording_removed_from_ui.py`
- `tests/test_write_through_generated_learning_routes.py`
- `tests/test_write_through_generated_learning_service.py`
- `tests/test_write_through_routes.py`
- `tests/test_write_through_service.py`
- `tests/test_write_through_usage_events_routes.py`
- `tests/test_write_through_usage_events_service.py`

## 4. Files Needing Final Manual Review Before Staging

These files appear in `git status` and may belong in the Render smoke commit, but they are broad, security-sensitive, environment-sensitive, or shared UI changes. Review their diffs before staging.

- `.env.example`
- `README.md`
- `auth.py`
- `config.py`
- `core/__init__.py`
- `core/logging.py`
- `core/security_config.py`
- `static/style.css`
- `templates/base.html`
- `templates/chat.html`
- `templates/index.html`
- `templates/login.html`
- `templates/signup.html`
- `templates/syllabus.html`
- production/security docs:
  - `docs/ai2-private-beta-launch-plan.md`
  - `docs/ai2-production-deployment-readiness-checkpoint.md`
  - `docs/ai2-production-env-notes.md`
  - `docs/ai2-production-readiness-audit.md`
  - `docs/ai2-render-smoke-deployment-checklist.md`
- production/security tests:
  - `tests/test_debug_endpoint_protection.py`
  - `tests/test_production_auth_config.py`
  - `tests/test_privacy_terms_pages.py`
  - `tests/test_storage_health_endpoint.py`
  - `tests/test_storage_health_view.py`
  - `tests/test_storage_status_endpoint.py`

## 5. Files Not To Stage

Do not stage local, temporary, cache, database, log, export, or secret files. Do not delete them automatically.

- `.pytest_tmp/`
- all `.pytest_tmp/*` entries
- `.pytest_cache/`
- `__pycache__/`
- `manual_tmp/`
- `manual_tmp/x.txt`
- `jobs.db`
- `sessions.db`
- `sessions.db-shm`
- `sessions.db-wal`
- logs
- local exports
- `.env`
- any file containing real API keys, auth secrets, DB URLs, debug tokens, cookies, session data, learner submissions, or private exports

## 6. Exact Git Add Command

Do not use `git add .`.

Use explicit paths only after reviewing the diffs. These grouped commands are reviewable and avoid temp/cache/local DB/secret files.

Core migration files:

```bash
git add app.py context/session.py curriculum/syllabus.py database/schema.sql curriculum/freshness.py curriculum/modular_seed_export.py curriculum/seed_export.py curriculum/topics.py
```

Repositories, routes, services, scripts, and harness:

```bash
git add repositories/__init__.py repositories/content_cache_repository.py repositories/curriculum_repository.py repositories/generated_content_repository.py repositories/learner_course_enrollment_repository.py repositories/learning_outcomes_repository.py repositories/modular_curriculum_repository.py repositories/progress_repository.py repositories/submissions_repository.py repositories/todos_repository.py repositories/topic_notes_repository.py repositories/usage_events_repository.py routes/__init__.py routes/deps.py routes/submissions.py routes/todos.py routes/topics.py services/__init__.py services/content_cache_service.py services/content_service.py services/curriculum_fallback_service.py services/curriculum_read_service.py services/dashboard_modular_progress_service.py services/generated_learning_mismatch_service.py services/generated_learning_read_service.py services/learner_course_enrollment_service.py services/learner_state_fallback_service.py services/learner_state_read_service.py services/learning_outcome_service.py services/mismatch_logging_service.py services/modular_curriculum_fallback_service.py services/modular_curriculum_read_service.py services/modular_position_service.py services/modular_progress_service.py services/modular_progress_snapshot_service.py services/modular_progress_write_through_service.py services/modular_topic_adapter.py services/state_mismatch_service.py services/storage_flags.py services/submission_service.py services/todo_context_service.py services/usage_events_mismatch_service.py services/usage_limit_service.py services/write_through_generated_learning_service.py services/write_through_service.py services/write_through_usage_events_service.py scripts/seed_curriculum.py scripts/seed_modular_curriculum.py harness/__init__.py harness/context_builder.py harness/guardrails.py harness/output_validators.py harness/prompt_templates.py harness/rubrics.py harness/run_records.py harness/usage_policy.py
```

Templates, safe static assets, documentation, and tests:

```bash
git add static/topic_detail.js templates/beta_metrics.html templates/dashboard.html templates/onboarding.html templates/privacy.html templates/storage_health.html templates/terms.html templates/todos.html templates/topic_detail.html templates/topics.html docs/ai2-advance-week-deprecation-plan.md docs/ai2-auth-user-ownership-review.md docs/ai2-current-week-removal-checklist.md docs/ai2-curriculum-dependency-audit.md docs/ai2-db-read-migration-plan.md docs/ai2-final-architecture-overview.md docs/ai2-final-cleanup-checklist.md docs/ai2-git-staging-plan.md docs/ai2-harness-engineering-plan.md docs/ai2-local-regression-cleanup-review.md docs/ai2-private-beta-launch-plan.md docs/ai2-production-db-schema-plan.md docs/ai2-production-deployment-readiness-checkpoint.md docs/ai2-production-env-notes.md docs/ai2-production-readiness-audit.md docs/ai2-render-smoke-commit-file-list.md docs/ai2-render-smoke-deployment-checklist.md docs/ai2-topic-journey-architecture.md tests/test_advance_week_deprecation_plan.py tests/test_beta_feedback.py tests/test_beta_metrics_view.py tests/test_chat_context_module_wording.py tests/test_content_cache_repository.py tests/test_content_cache_runtime.py tests/test_content_service.py tests/test_curriculum_db_check_endpoint.py tests/test_curriculum_fallback_endpoint.py tests/test_curriculum_fallback_service.py tests/test_curriculum_read_service.py tests/test_curriculum_seed_export.py tests/test_dashboard_enrollment_summary.py tests/test_dashboard_modular_progress_summary.py tests/test_dashboard_summary.py tests/test_debug_endpoint_protection.py tests/test_freshness.py tests/test_generated_learning_db_check_endpoint.py tests/test_generated_learning_mismatch_endpoint.py tests/test_generated_learning_mismatch_service.py tests/test_generated_learning_read_service.py tests/test_generated_learning_repositories.py tests/test_git_staging_plan_doc.py tests/test_harness_foundation.py tests/test_interview_submission.py tests/test_learner_course_enrollment_repository.py tests/test_learner_course_enrollment_service.py tests/test_learner_state_db_check_endpoint.py tests/test_learner_state_fallback_endpoint.py tests/test_learner_state_fallback_service.py tests/test_learner_state_mismatch_endpoint.py tests/test_learner_state_read_service.py tests/test_learning_outcome_routes.py tests/test_learning_outcome_service.py tests/test_learning_outcome_ui.py tests/test_learning_outcomes_repository.py tests/test_local_regression_cleanup_review.py tests/test_logging_utils.py tests/test_mark_done_controls.py tests/test_mismatch_logging_service.py tests/test_modular_curriculum_debug_endpoint.py tests/test_modular_curriculum_fallback_service.py tests/test_modular_curriculum_read_service.py tests/test_modular_curriculum_repository.py tests/test_modular_curriculum_seed_export.py tests/test_modular_position_runtime_display.py tests/test_modular_position_service.py tests/test_modular_progress_service.py tests/test_modular_progress_snapshot_runtime.py tests/test_modular_progress_write_through_service.py tests/test_navigation.py tests/test_onboarding_course_enrollment.py tests/test_onboarding_flow.py tests/test_portfolio.py tests/test_privacy_terms_pages.py tests/test_production_auth_config.py tests/test_production_deployment_readiness_checkpoint.py tests/test_progress_db_first_routes.py tests/test_quiz_submission.py tests/test_render_smoke_commit_file_list.py tests/test_render_smoke_deployment_checklist.py tests/test_repositories_structure.py tests/test_repository_reads.py tests/test_schema_content_cache.py tests/test_schema_generated_learning_tables.py tests/test_schema_learner_course_enrollments.py tests/test_schema_learning_outcomes.py tests/test_schema_learning_tables.py tests/test_schema_modular_curriculum.py tests/test_schema_usage_events.py tests/test_seed_curriculum_script.py tests/test_seed_modular_curriculum_script.py tests/test_state_mismatch_service.py tests/test_storage_flags.py tests/test_storage_health_endpoint.py tests/test_storage_health_view.py tests/test_storage_status_endpoint.py tests/test_submission_service.py tests/test_todo_routes.py tests/test_todos.py tests/test_todos_db_first_routes.py tests/test_todos_modular_context.py tests/test_topic_content.py tests/test_topic_detail_modular_curriculum_flag.py tests/test_topic_notes.py tests/test_topic_practice.py tests/test_topics.py tests/test_topics_modular_curriculum_flag.py tests/test_topics_routes.py tests/test_usage_events_db_check_endpoint.py tests/test_usage_events_mismatch_endpoint.py tests/test_usage_events_mismatch_service.py tests/test_usage_events_repository.py tests/test_usage_limit_enforcement.py tests/test_usage_policy.py tests/test_usage_tracking.py tests/test_week_compatibility_markers.py tests/test_week_wording_removed_from_ui.py tests/test_write_through_generated_learning_routes.py tests/test_write_through_generated_learning_service.py tests/test_write_through_routes.py tests/test_write_through_service.py tests/test_write_through_usage_events_routes.py tests/test_write_through_usage_events_service.py
```

Manual-review files to stage only after final inspection:

```bash
git add .env.example README.md auth.py config.py core/__init__.py core/logging.py core/security_config.py static/style.css templates/base.html templates/chat.html templates/index.html templates/login.html templates/signup.html templates/syllabus.html
```

Before committing, verify the staged diff:

```bash
git diff --cached --stat
git diff --cached --name-only
```

## 7. Exact Commit Command

```bash
git commit -m "Add modular curriculum migration foundation"
```

Do not push until the commit contents and Render smoke flags are confirmed.

## 8. Pre-Commit Test Command

Run this before committing:

```bash
python -m pytest tests/test_topics_routes.py tests/test_dashboard_summary.py tests/test_todo_routes.py tests/test_onboarding_flow.py tests/test_modular_progress_service.py tests/test_modular_position_service.py tests/test_production_auth_config.py tests/test_debug_endpoint_protection.py tests/test_render_smoke_deployment_checklist.py
```

## 9. Final Safety Checklist

- Confirm no `.env` file is staged.
- Confirm no local DB files are staged: `jobs.db`, `sessions.db`, `sessions.db-shm`, or `sessions.db-wal`.
- Confirm no cache/temp files are staged: `.pytest_tmp/`, `.pytest_cache/`, `__pycache__/`, or `manual_tmp/`.
- Confirm Render environment variables are set separately in the Render dashboard, not committed.
- Confirm conservative Render flags are used first:
  - `AI2_MODULAR_CURRICULUM_READS_ENABLED=false`
  - `AI2_DB_WRITE_THROUGH_ENABLED=false`
  - `AI2_TODOS_DB_READS_ENABLED=false`
  - `AI2_PROGRESS_DB_READS_ENABLED=false`
  - `AI2_USAGE_LIMITS_ENABLED=true`
- Confirm no seed script is run automatically.
- Confirm `scripts/seed_modular_curriculum.py` remains manual only.
- Confirm `current_week`, `WEEKS`, and `ROLE_TRACKS` are not removed in this commit.
