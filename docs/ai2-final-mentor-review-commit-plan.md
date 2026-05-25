# AI² Final Mentor Review Commit Plan

**Date:** 2026-05-25
**Purpose:** Review and classify all remaining uncommitted changes before final push for mentor review.

---

## 1. Current Repo Status

### Modified tracked files (7)
| File | Change summary |
|---|---|
| `auth.py` | Adds `assert_auth_secret_set()` startup guard from `core.security_config` |
| `config.py` | Adds clarifying comment above `TOTAL_WEEKS = 5` (comment-only, no logic change) |
| `static/style.css` | ~360 lines of new CSS: topics page, topic detail, AI content sections, portfolio/quiz/interview submission areas, topic card progress, week progress summary |
| `templates/base.html` | Adds `<footer>` with Privacy and Terms links |
| `templates/chat.html` | Sidebar wording: "Week X / Y" → "Module X"; adds Topics/Planner nav links; adds `?prompt=` auto-send JS for Learn/Quiz quick actions; updates Ideas button copy |
| `templates/index.html` | Landing page copy: "13-week" → "modular adaptive learning path" |
| `templates/syllabus.html` | Adds "Browse Module Topics" and "My Planner" nav links in topbar |

### Untracked files (safe to commit)
| File | Type |
|---|---|
| `README.md` | Project overview for mentor review |
| `docs/ai2-portfolio-interview-redirect-audit.md` | Audit documentation |
| `docs/ai2-render-smoke-completion-report.md` | Smoke completion report |
| `docs/ai2-render-smoke-verification-report.md` | Smoke verification report |
| `tests/test_portfolio_interview_redirect_audit.py` | Tests for audit doc |
| `tests/test_render_smoke_completion_report.py` | Tests for completion report |
| `tests/test_render_smoke_verification_report.py` | Tests for verification report |

### Untracked files (must NOT commit)
| File | Reason |
|---|---|
| `.pytest_tmp/` | Temp pytest artifact directory |
| `manual_tmp/` | Local manual testing scratch directory |

---

## 2. Files Recommended To Commit

All modified tracked files and all untracked docs/tests are safe to commit. Reason for each:

**`auth.py`** — Calls `assert_auth_secret_set()` at startup. This is an intentional, tested production safety guard that prevents the app from booting in production without a stable `AUTH_SECRET`. Tests in `test_production_auth_config.py` cover the full behavior. Safe and valuable for mentor to see.

**`config.py`** — Comment-only change. Clarifies `TOTAL_WEEKS` is a legacy compatibility constant, not a feature driver. No logic changed. Safe.

**`static/style.css`** — All added CSS classes are referenced by the existing topics/topic_detail templates. Classes include: `.topics-page`, `.topic-card`, `.topic-button-row`, `.topic-action-btn`, `.topic-ai-content-section`, `.portfolio-submission-area`, `.interview-submission-area`, `.topic-continue-btn`, `.week-progress-summary`, and related variants. No existing CSS removed or overwritten. Safe.

**`templates/base.html`** — Footer with Privacy and Terms links. Minimal, safe, mentor-appropriate.

**`templates/chat.html`** — Three improvements:
- "Week X / Y" → "Module X" (removes hardcoded total-week reference consistent with `config.py` comment)
- Browse Topics and Planner sidebar links (navigation only)
- `?prompt=` auto-send JS: reads URL query param, sets `input.value`, dispatches input event, calls `sendMessage()`. Does **not** use `innerHTML` — no XSS risk. This is the mechanism that makes Learn and Quiz chat quick-action links actually work.
- Ideas copy: "this week" → "my current module" (consistent with modular framing)

**`templates/index.html`** — One line: landing hero copy updated from "13-week" to "modular". Safe.

**`templates/syllabus.html`** — Two nav links added to topbar. No functional change to syllabus logic. Safe.

**`README.md`** — Well-structured project overview covering architecture, storage strategy, feature flags, debug endpoints, local dev setup, and current status. Contains no secrets, no API keys, no credentials, no real URLs. Mentor-ready.

**`docs/` files** — Audit, smoke verification, and smoke completion reports. Documentation only. Safe.

**`tests/` files** — Test files for the above docs. No server calls, no API calls, no secrets. Safe.

---

## 3. Files Requiring Manual Visual Review

Before committing, visually review these two files to confirm no unintended content slipped in:

**`static/style.css`** — Large diff (~360 lines added). Verify:
- No hardcoded color values that conflict with CSS variables
- No commented-out debug styles left in
- No commented-out old class names that could confuse a mentor

**`templates/chat.html`** — Contains the `initialPrompt` JS block. Verify:
- `input.value = initialPrompt` (input element property — safe)
- No `innerHTML` usage
- `window.history.replaceState` cleans the URL after the prompt is captured (correct)
- `setTimeout(() => sendMessage(), 100)` — the 100ms delay allows the input event to settle before sending

---

## 4. Files Not To Commit

| File/Directory | Reason |
|---|---|
| `.env` | Contains real `ANTHROPIC_API_KEY`, `AUTH_SECRET`, `SUPABASE_DATABASE_URL`. Must never be committed. Already covered by `.gitignore`. |
| `.pytest_tmp/` | Temp pytest artifact directory — local only |
| `manual_tmp/` | Local manual test scratch — local only |
| Any `*.db` local DB files | SQLite local DB files — not used in production, contain local test data |
| `__pycache__/` | Python bytecode cache — already in `.gitignore` |
| Any log files | Runtime logs — local only |

---

## 5. Risk Review

| File | Risk Level | Notes |
|---|---|---|
| `auth.py` | **Low** | Adds startup guard already covered by existing tests. Wires in `core.security_config` which is already committed. |
| `config.py` | **Very Low** | Comment-only change above `TOTAL_WEEKS`. No logic impact. |
| `static/style.css` | **Low** | Large but purely additive. All new classes. No existing rules touched. Render already shows these styles working in production smoke. |
| `templates/base.html` | **Very Low** | Footer addition only. Privacy/Terms routes already exist. |
| `templates/chat.html` | **Low** | `initialPrompt` JS uses `.value` assignment not `innerHTML`. No XSS surface. Sidebar nav links are anchor tags only. |
| `templates/index.html` | **Very Low** | One text change. Landing page hero copy only. |
| `templates/syllabus.html` | **Very Low** | Two anchor links in the topbar. No template logic changed. |
| `README.md` | **Very Low** | No secrets. Well-structured. Mentor-appropriate. |

No file in this list touches orchestrator logic, agents, database schema, route definitions, or any security-critical path in a risky way.

---

## 6. Recommended Commit Strategy

One final commit covering all remaining safe changes:

```
git add auth.py config.py static/style.css templates/base.html templates/chat.html templates/index.html templates/syllabus.html README.md docs/ai2-portfolio-interview-redirect-audit.md docs/ai2-render-smoke-completion-report.md docs/ai2-render-smoke-verification-report.md tests/test_portfolio_interview_redirect_audit.py tests/test_render_smoke_completion_report.py tests/test_render_smoke_verification_report.py

git commit -m "Finalize mentor review polish and docs"
```

Do **not** include `.pytest_tmp/`, `manual_tmp/`, or any local DB or cache files.

---

## 7. Pre-Commit Tests

Run this suite before committing to confirm nothing is broken:

```
python -m pytest tests/test_production_auth_config.py tests/test_debug_endpoint_protection.py tests/test_navigation.py tests/test_privacy_terms_pages.py tests/test_render_smoke_verification_report.py tests/test_portfolio_interview_redirect_audit.py
```

If `test_navigation.py` or `test_privacy_terms_pages.py` do not exist yet, run the full suite:

```
python -m pytest
```

---

## 8. Final Push Checklist

Before `git push`:

- [ ] `.env` is **not** staged — confirm with `git status --short`
- [ ] No local DB files (`.db`, `sessions.db`, `*.sqlite`) are staged
- [ ] No temp/cache folders (`.pytest_tmp/`, `manual_tmp/`, `__pycache__/`) are staged
- [ ] `python -m pytest` passes all tests (or target suite passes)
- [ ] App still boots locally with `uvicorn app:app --reload` (optional, Render smoke already confirmed this)
- [ ] Debug endpoint protection remains active — `/debug/storage-health` returns `{"detail":"Not found."}` without token
- [ ] README contains no real API keys, no real database URLs, no real secrets
- [ ] README is accurate and safe for public mentor review on GitHub

---

*This document is a planning and review artifact only. No runtime behavior, routes, templates, static files, schema, feature flags, or data were modified to produce it.*
