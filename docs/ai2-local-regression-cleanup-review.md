# AI² Local Regression and Cleanup Review

## 1. Git Worktree Summary

`git status --short` shows a heavily dirty worktree with modified tracked files and many untracked project directories/files. No files were deleted during this review.

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

Untracked directories/files include:

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
- many focused `tests/test_*.py` files

## 2. Files To Keep And Commit

Required project changes likely to keep/commit:

- `app.py`
- `auth.py`
- `config.py`
- `context/session.py`
- `curriculum/syllabus.py`
- `curriculum/topics.py`
- `curriculum/freshness.py`
- `curriculum/modular_seed_export.py`
- `curriculum/seed_export.py`
- `database/schema.sql`
- `core/`
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

Documentation changes likely to keep/commit:

- `README.md`
- `docs/ai2-advance-week-deprecation-plan.md`
- `docs/ai2-auth-user-ownership-review.md`
- `docs/ai2-current-week-removal-checklist.md`
- `docs/ai2-curriculum-dependency-audit.md`
- `docs/ai2-db-read-migration-plan.md`
- `docs/ai2-final-architecture-overview.md`
- `docs/ai2-final-cleanup-checklist.md`
- `docs/ai2-harness-engineering-plan.md`
- `docs/ai2-private-beta-launch-plan.md`
- `docs/ai2-production-db-schema-plan.md`
- `docs/ai2-production-deployment-readiness-checkpoint.md`
- `docs/ai2-production-env-notes.md`
- `docs/ai2-production-readiness-audit.md`
- `docs/ai2-topic-journey-architecture.md`
- `docs/ai2-local-regression-cleanup-review.md`

Tests likely to keep/commit:

- All untracked focused tests covering beta feedback, beta metrics, chat context wording, content cache, curriculum reads/fallbacks, dashboard enrollment/modular progress, debug protection, generated learning, learner state, learning outcomes, modular curriculum, modular position/progress, onboarding enrollment, production auth, production deployment checkpoint, repository/schema checks, storage health, todos, topics, usage, week compatibility, and write-through behavior.

## 3. Files Needing Human Review

Review before staging/deploying:

- `.env.example`: confirm production flag examples are complete and contain no secrets.
- `auth.py`: security-sensitive; review auth/session cookie behavior carefully.
- `static/style.css`: broad UI styling file; verify changes are intentional.
- `templates/base.html`, `templates/chat.html`, `templates/dashboard.html`, `templates/index.html`, `templates/login.html`, `templates/signup.html`, `templates/syllabus.html`: review UI changes for accidental regressions.
- `README.md`: review for deployment accuracy and stale flags.
- `docs/`: review for duplicate/outdated guidance.
- `scripts/`: confirm scripts remain manual and safe.
- `routes/`: review route behavior because the directory is untracked as a whole.
- `services/`: review service boundaries and ensure no unintended runtime wiring.
- `repositories/`: review SQL helpers and transaction ownership.
- `database/schema.sql`: review full schema before applying to production.

## 4. Local Cleanup Candidates

Do not delete anything automatically. Review these local cleanup candidates first:

- `.pytest_tmp/`
- `manual_tmp/`
- `.pytest_cache/`
- `__pycache__/`
- local database artifacts such as `jobs.db`, `sessions.db`, `sessions.db-shm`, `sessions.db-wal`
- generated logs or temporary exports if any are present

## 5. Files Not Safe To Delete Automatically

Not safe to delete automatically:

- Any file under `core/`, `repositories/`, `routes/`, `services/`, `scripts/`, `harness/`, `curriculum/`, `templates/`, `static/`, `tests/`, or `docs/`
- `database/schema.sql`
- `.env.example`
- `README.md`
- Render/deployment files such as `render.yaml`, `Procfile`, `runtime.txt`, and `requirements.txt`
- Local DB files until the owner confirms they are disposable

## 6. Full Regression Result

Full regression command attempted:

```bash
python -m pytest
```

Result:

- `2433 passed`
- `5 failed`
- `17 errors`
- `5 warnings`
- Runtime: about 6 minutes 12 seconds

Observed blockers appear local/environmental:

- Windows temp permission errors for pytest `tmp_path`: `PermissionError: [WinError 5] Access is denied: C:\Users\J\AppData\Local\Temp\pytest-of-J`
- Playwright named-pipe permission errors on Windows.
- Auth live-server ownership tests timed out against localhost.

Broad safe regression command run after the full-suite local blockers:

```bash
python -m pytest tests/test_topics_routes.py tests/test_dashboard_summary.py tests/test_todo_routes.py tests/test_onboarding_flow.py tests/test_modular_progress_service.py tests/test_modular_position_service.py tests/test_production_auth_config.py tests/test_debug_endpoint_protection.py tests/test_privacy_terms_pages.py tests/test_production_deployment_readiness_checkpoint.py
```

Broad safe regression result:

- `207 passed`
- `5 warnings`
- Runtime: about 6 seconds

Doc test for this cleanup review:

```bash
python -m pytest tests/test_local_regression_cleanup_review.py
```

Result:

- `5 passed`

## 7. Deployment Recommendation

Do not deploy directly from this dirty worktree without human review and intentional staging.

Recommended next steps:

1. Review and stage required project changes, docs, and tests intentionally.
2. Do not delete local/temp files until confirmed disposable.
3. Resolve local full-regression blockers if possible by fixing temp permissions and Playwright subprocess permissions.
4. Re-run `python -m pytest` in a clean terminal/environment.
5. If full regression remains blocked locally, use the broad safe batch plus targeted browser/auth tests in a known-good environment.
6. Deploy to Render with conservative flags after a reviewed commit is pushed.
7. Keep `AI2_MODULAR_CURRICULUM_READS_ENABLED=false` for the first smoke test.
8. Apply `database/schema.sql` before enabling DB write-through or DB-backed reads.
9. Run `scripts/seed_modular_curriculum.py` manually only after schema is applied and DB connectivity is verified.

No automatic deletion was performed as part of this review.
