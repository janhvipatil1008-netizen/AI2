# AI² Remaining Unstaged Files Review

## 1. Purpose

Review what remains after commit `d4772b7` before pushing to Render.

Commit `d4772b7` added the modular curriculum migration foundation, but the worktree still contains production/security, global UI, documentation, and beta-support files. This review classifies those leftovers so the next action is intentional.

No push yet. Do not push `d4772b7` alone until the dependency risk below is resolved.

## 2. Safe To Include In Second Commit

These files should be included in a second small commit before pushing because the committed code already references them or they directly support committed learner/admin flows:

- `core/__init__.py`
- `core/logging.py`
- `core/security_config.py`
- `repositories/beta_feedback_repository.py`
- `repositories/beta_metrics_repository.py`
- `services/beta_feedback_service.py`
- `services/beta_metrics_service.py`

Reason: committed runtime code imports these modules:

- `app.py` imports `core.security_config` and `core.logging`.
- `routes/deps.py`, `routes/topics.py`, and `services/submission_service.py` import `core.logging`.
- `routes/submissions.py` imports beta feedback repository/service helpers.
- `app.py` imports beta metrics repository/service helpers for the admin beta metrics view.

If these files are not committed before push, a clean Render deploy of `d4772b7` can fail at import time or fail when beta feedback/metrics routes are used.

Also reasonable to include in the second commit after reviewing diffs:

- `README.md`
- `.env.example`
- `auth.py`
- `config.py`
- `static/style.css`
- `templates/base.html`
- `templates/chat.html`
- `templates/index.html`
- `templates/login.html`
- `templates/signup.html`
- `templates/syllabus.html`

These are related to production hardening, privacy/terms navigation, module wording, and UI support for committed templates.

## 3. Needs Manual Review

Review these before staging because they can affect auth, config, global UI, styling, or public docs:

- `.env.example`
  - Adds `AI2_ENV`, `AI2_DEBUG_TOKEN`, and `AI2_MODULAR_CURRICULUM_READS_ENABLED`.
  - Confirm no real secrets are present.
  - Confirm DB env var guidance matches the active production DB helper.

- `auth.py`
  - Imports `core.security_config.assert_auth_secret_set`.
  - Enforces `AUTH_SECRET` in production before falling back to a generated local secret.
  - Production-sensitive and should be reviewed with `core/security_config.py`.

- `config.py`
  - Adds compatibility-only comments around `TOTAL_WEEKS`.
  - Low behavior risk, but it touches shared configuration.

- `static/style.css`
  - Adds broad topic, topic detail, AI content, quiz, portfolio, interview, and progress styling.
  - It likely supports committed topic/detail templates, but it is a large global stylesheet change.
  - It still contains CSS class names with `week-` prefixes; these are internal selectors, not visible learner copy, but should be reviewed before staging.

- `templates/base.html`
  - Adds global Privacy/Terms footer links.

- `templates/chat.html`
  - Changes visible wording from week to module.
  - Adds topics/todos navigation and initial prompt handling.

- `templates/index.html`
  - Changes landing copy from fixed week language to modular path language.

- `templates/login.html`
  - Adds Privacy/Terms links.

- `templates/signup.html`
  - Adds Privacy/Terms links.

- `templates/syllabus.html`
  - Adds topics and planner navigation.

- `README.md`
  - New broad project overview.
  - It mentions storage flags and local environment guidance; review for stale env names before publishing.

- `core/`
  - Production/security/logging helpers.
  - Needed by committed runtime imports, but still security-sensitive.

## 4. Do Not Commit

Do not commit local temp/cache folders:

- `.pytest_tmp/`
- `manual_tmp/`

Also keep excluding:

- `.pytest_cache/`
- `__pycache__/`
- local DB files such as `jobs.db`, `sessions.db`, `sessions.db-shm`, and `sessions.db-wal`
- logs
- local exports
- `.env`
- any file containing real secrets, tokens, DB URLs, cookies, session data, learner submissions, or private exports

Do not delete these automatically. Clean them later only after a separate review.

## 5. Risk Summary

The highest risk is not cosmetic: `d4772b7` references uncommitted modules. Pushing only `d4772b7` can produce a broken Render deployment because a clean checkout will not contain `core/`, `services/beta_metrics_service.py`, `services/beta_feedback_service.py`, `repositories/beta_metrics_repository.py`, or `repositories/beta_feedback_repository.py`.

Auth/config changes are production-sensitive. `auth.py` and `core/security_config.py` intentionally harden production behavior by requiring `AUTH_SECRET`, blocking test mode in production, and protecting debug/admin routes with `AI2_DEBUG_TOKEN`. Review them before staging, but they fit the Render smoke deployment work.

Template/style changes affect global learner-facing UI. The Privacy/Terms links, module wording, topics/todos navigation, and stylesheet additions appear aligned with the modular migration, but they should be reviewed because broad templates and global CSS can affect many pages.

The README is useful but broad. Review env var names before committing so it does not conflict with `.env.example` or Render docs.

## 6. Recommended Action Before Push

Recommendation: create a second small commit before pushing.

Suggested second commit scope:

- `core/`
- `repositories/beta_feedback_repository.py`
- `repositories/beta_metrics_repository.py`
- `services/beta_feedback_service.py`
- `services/beta_metrics_service.py`
- `.env.example`
- `auth.py`
- `config.py`
- `README.md`
- `static/style.css`
- `templates/base.html`
- `templates/chat.html`
- `templates/index.html`
- `templates/login.html`
- `templates/signup.html`
- `templates/syllabus.html`
- this review doc and its test

Suggested commit message:

```bash
git commit -m "Add production safety and beta support leftovers"
```

Leave `.pytest_tmp/` and `manual_tmp/` unstaged. Clean temp folders later in a separate cleanup step if needed.

Do not push yet until:

- the second commit is reviewed and created,
- the staged diff contains no `.env`, temp/cache, local DB, or secret files,
- the focused regression batch still passes,
- Render conservative flags are confirmed in the dashboard.
