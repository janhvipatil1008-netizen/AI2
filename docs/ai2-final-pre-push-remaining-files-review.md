# AI² Final Pre-Push Remaining Files Review

## 1. Purpose

Review remaining unstaged files before Render smoke push.

Current ready commits:

- `6fbaad3` Add missing production safety and beta support modules
- `d4772b7` Add modular curriculum migration foundation

No push yet. This review covers only the remaining unstaged production-sensitive files and excludes temp folders.

## 2. File-by-File Diff Summary

### `.env.example`

- What changed: Adds placeholder deployment variables for `AI2_ENV`, `AI2_DEBUG_TOKEN`, and `AI2_MODULAR_CURRICULUM_READS_ENABLED`.
- Needed for Render smoke deployment: Useful but not required at runtime because Render env vars are set in the dashboard.
- Risk level: medium.
- Recommendation: commit now after confirming placeholder-only values and adding any missing conservative flags in a later docs/env cleanup.

### `auth.py`

- What changed: Imports `assert_auth_secret_set` from `core.security_config` and calls it before falling back to a generated local secret.
- Needed for Render smoke deployment: Recommended. It hardens production auth by preventing production boot without `AUTH_SECRET`.
- Risk level: medium.
- Recommendation: commit now if production Render has `AUTH_SECRET` configured. Leave unstaged only if the first Render smoke intentionally needs to validate environment setup before enforcing production boot.

### `config.py`

- What changed: Adds compatibility-only comments above `TOTAL_WEEKS`; no symbol rename or behavior change.
- Needed for Render smoke deployment: Not required, but consistent with week-compatibility documentation.
- Risk level: low.
- Recommendation: commit now.

### `static/style.css`

- What changed: Adds broad styling for topics, topic detail, AI content sections, quiz/portfolio/interview submission areas, syllabus navigation, topic card progress, and progress summary classes.
- Needed for Render smoke deployment: Recommended if the committed topic/topic-detail templates are deployed; otherwise those pages may render with incomplete styling.
- Risk level: high because it is a large global stylesheet change.
- Recommendation: needs human visual review before commit. It is probably part of the same modular UI work, but broad CSS should be checked on login, dashboard, topics, topic detail, todos, and mobile widths.

### `templates/base.html`

- What changed: Adds global Privacy and Terms footer links.
- Needed for Render smoke deployment: Useful for beta readiness and public pages.
- Risk level: medium because it affects every page using the base template.
- Recommendation: commit now after quick visual review.

### `templates/chat.html`

- What changed: Rewords the sidebar from `Week` to `Module`, adds Topics and Planner navigation, changes the Ideas quick prompt to module wording, and adds initial `prompt` query-param handling.
- Needed for Render smoke deployment: Useful for modular wording and navigation.
- Risk level: medium.
- Recommendation: commit now after confirming the query-param auto-send behavior is intended.

### `templates/index.html`

- What changed: Replaces fixed `13-week` landing copy with modular learning path copy.
- Needed for Render smoke deployment: Useful for current product positioning.
- Risk level: low.
- Recommendation: commit now.

### `templates/login.html`

- What changed: Adds Privacy and Terms links below the login form.
- Needed for Render smoke deployment: Useful for beta readiness.
- Risk level: low after Step 134; the mojibake separator was replaced with plain `|`.
- Recommendation: commit now.

### `templates/signup.html`

- What changed: Adds Privacy and Terms links below the signup form.
- Needed for Render smoke deployment: Useful for beta readiness.
- Risk level: low after Step 134; the mojibake separator was replaced with plain `|`.
- Recommendation: commit now.

### `templates/syllabus.html`

- What changed: Adds Browse Module Topics and My Planner navigation links.
- Needed for Render smoke deployment: Useful for modular navigation.
- Risk level: low.
- Recommendation: commit now.

### `README.md`

- What changed: Adds a new project overview covering product summary, key features, architecture, storage strategy, feature flags, debug endpoints, local development, testing, current status, and planned improvements.
- Needed for Render smoke deployment: Not required at runtime, but useful for repository readiness.
- Risk level: medium because it is broad and mentions env vars such as `DATABASE_URL`/`AI2_TEST_MODE` that should be checked against the current production docs and active DB helper naming.
- Recommendation: needs human review before commit, or leave unstaged until after Render smoke.

## 3. Production Safety Findings

- `auth.py` production auth behavior: good hardening direction. In production, missing `AUTH_SECRET` should fail fast instead of silently generating a transient secret. Risk is operational: Render must have `AUTH_SECRET` configured before this is deployed.
- `config.py` production flags/constants: only comments were added around `TOTAL_WEEKS`; no behavior change found.
- `.env.example` placeholder-only values: no real secrets found. `AI2_DEBUG_TOKEN=replace-with-long-random-token` is a placeholder. `SUPABASE_DATABASE_URL` remains a placeholder. Step 134 added conservative Render smoke flags.
- `static/style.css` broad UI risk: high review surface. It supports modular topics/detail/submission views but can affect global layout due shared class names and broad selectors.
- `templates/login.html`, `templates/signup.html`, and `templates/base.html` global impact: privacy/terms links are appropriate. Step 134 fixed the login/signup separator mojibake.

## 4. Recommendation

Recommendation: hold push until manual visual review.

Reason: the two ready commits are stronger with a third small production-safety/UI polish commit, but the remaining files include broad CSS and visible auth/login/signup/base changes. A quick browser check should happen before staging them.

After visual review, create a third small commit for:

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
- optionally `README.md` if env names are verified
- `docs/ai2-final-pre-push-remaining-files-review.md`
- `tests/test_final_pre_push_remaining_files_review.py`

Files to leave unstaged until later if review time is short:

- `README.md`

Do not push yet until either these files are intentionally committed or intentionally left out after confirming the two ready commits deploy cleanly without them.

## 6. Step 134 Review Result

- Mojibake review: fixed the login/signup `Â·` separator by replacing it with plain `|`. No additional scoped learner-facing mojibake was found in the reviewed templates.
- Auth/config reviewed: `auth.py` uses `core.security_config.assert_auth_secret_set()` before local random-secret fallback, so production auth is not weakened. `config.py` only adds compatibility-only comments around `TOTAL_WEEKS`; no production-breaking config or secrets were found.
- `.env.example` reviewed: values are placeholders only. Step 134 added conservative Render smoke defaults for `AI2_DB_WRITE_THROUGH_ENABLED=false`, `AI2_TODOS_DB_READS_ENABLED=false`, `AI2_PROGRESS_DB_READS_ENABLED=false`, `AI2_USAGE_LIMITS_ENABLED=true`, `AI2_TEST_MODE=0`, and `TEST_MODE=0`.
- CSS reviewed: no obvious broken CSS syntax or hidden/disabled login, signup, or dashboard areas were found in the scoped diff. The stylesheet remains broad and should be visually checked, but it supports the committed topics/topic-detail/submission UI.
- Template review: base/login/signup/index/chat/syllabus changes use normal learner-facing text, do not expose debug/private information, and do not change route URLs.
- Recommendation for third small commit: commit the scoped production-safety/UI/env files after the focused tests pass. Keep `README.md`, `.pytest_tmp/`, and `manual_tmp/` unstaged in this step.

## 5. Do Not Stage

Do not stage:

- `.pytest_tmp/`
- `manual_tmp/`

Also continue excluding `.pytest_cache/`, `__pycache__/`, local DB files, logs, local exports, `.env`, and any secret files.
