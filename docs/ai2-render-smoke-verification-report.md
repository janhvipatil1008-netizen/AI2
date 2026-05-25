# AI² Render Smoke Verification Report

**Date:** 2026-05-25
**Environment:** Production — Render
**App URL:** https://ai2-platform.onrender.com
**Purpose:** Structured smoke verification before any UI or curriculum changes

---

## 1. Current Render Status

- App is **live on Render** and responding to requests
- **Dashboard** (`/dashboard`) loads correctly and appears styled
- **Syllabus** (`/syllabus/<session_id>`) loads correctly and appears styled
- **Topics page** loads (UI appears raw — see Section 4)
- **Todos page** loads (UI appears raw — see Section 4)
- No HTTP 500 errors observed on any of the above pages from screenshots
- Auth, session creation, and navigation all appear functional

---

## 2. Smoke Checks Still Required

The following checks have not yet been verified and must be confirmed before proceeding to any UI or curriculum changes:

- [ ] `/health` — endpoint reachable and returns healthy status
- [ ] Topic detail page — individual topic page loads without error
- [ ] **Generate Lesson** — Claude API call completes and returns lesson content
- [ ] **Generate Practice** — Claude API call completes and returns practice content
- [ ] `/debug/storage-health` without token — should return 404 in production (not expose internals)
- [ ] `/debug/modular-curriculum` without token — should return 404 in production
- [ ] `/admin/beta-metrics` without token — should return 404 in production
- [ ] Render deploy status page — confirm latest deploy used the latest pushed commit
- [ ] Render runtime logs — confirm no import errors, no missing env var warnings, no AUTH_SECRET random-generation warnings

---

## 3. Expected Results

| Check | Expected |
|---|---|
| `/health` | HTTP 200, `{"status": "ok"}` or equivalent healthy response |
| Topic detail page | Loads with topic title, description, and action buttons visible |
| Generate Lesson | Returns lesson content from Claude without API error |
| Generate Practice | Returns practice/quiz content from Claude without API error |
| `/debug/storage-health` without token | HTTP 404 — not exposed in production |
| `/debug/modular-curriculum` without token | HTTP 404 — not exposed in production |
| `/admin/beta-metrics` without token | HTTP 404 — not exposed in production |
| Render latest deploy | Shows latest pushed commit SHA, deploy status green |
| Runtime logs | No `ImportError`, no `ModuleNotFoundError`, no `AUTH_SECRET` random-generation warning, no missing `SUPABASE_DATABASE_URL` error |

---

## 4. Observed UI Issues

- **Dashboard** — looks correctly styled, consistent design system
- **Syllabus** — looks correctly styled, consistent design system
- **Topics page** — appears raw/unstyled compared to dashboard; markup renders but without polish
- **Todos page** — appears raw/unstyled compared to dashboard; markup renders but without polish

**Likely causes:**
- Topics/todos templates are not using the same base layout or design system as dashboard and syllabus
- Broad CSS from `static/style.css` or a shared base template may not be included in these page templates
- Page-specific markup needs visual polish to match the rest of the product

**Status:** This is **not a backend blocker**. Pages load and function correctly. UI polish is a frontend-only task and should be addressed as Step 136 after smoke verification passes.

---

## 5. Current Curriculum Status

- The **old/static syllabus** is still active and visible in the deployed app
- Content referencing **AI Evals**, **Agri-Saathi**, and the original 13-week structure still exists in the UI
- This is **expected and correct** — `AI2_MODULAR_CURRICULUM_READS_ENABLED` should remain `false` during the first smoke verification pass
- The modular curriculum database tables may exist but reads are intentionally gated
- **Curriculum cleanup and migration is required before beta launch** but must not be triggered until smoke verification is complete and flags are deliberately enabled

---

## 6. Do Not Enable Yet

The following flags, scripts, and deployments must **not** be enabled until smoke verification fully passes and each item is explicitly approved:

| Item | Reason to hold |
|---|---|
| `AI2_MODULAR_CURRICULUM_READS_ENABLED=true` | Would activate new curriculum reads before content is verified |
| `AI2_DB_WRITE_THROUGH_ENABLED=true` | Would begin writing learner progress to DB before reads are confirmed stable |
| `AI2_TODOS_DB_READS_ENABLED=true` | Would switch todos from in-memory to DB before DB state is confirmed |
| `AI2_PROGRESS_DB_READS_ENABLED=true` | Would switch progress reads to DB before data integrity is confirmed |
| Seed scripts | Must not run against production DB before schema and flag state are confirmed |
| Azure deployment | Not scheduled — Render is the active deployment target |
| Azure AI Foundry | Not in scope for current smoke verification or beta launch |

---

## 7. Recommended Next Manual Screenshots

Please provide screenshots or curl output for the following to complete smoke verification:

1. **`/health` response** — full JSON body visible
2. **Render deploy status page** — showing latest deploy SHA and green status
3. **Topic detail page** — one topic opened, full page visible
4. **Generate Lesson result** — click Generate Lesson on a topic, show the returned lesson content
5. **Generate Practice result** — click Generate Practice on a topic, show the returned practice content
6. **`/debug/storage-health` without token** — confirm 404 response in browser or curl

---

## 8. Next Development Step After Smoke Passes

**Step 136 — Fix topics/todos UI consistency before beta**

Once all smoke checks in Section 2 pass and screenshots confirm Section 3 expected results:

- Audit topics and todos templates against dashboard/syllabus templates
- Identify which base layout, CSS classes, and static includes are missing
- Apply consistent styling without changing any route logic, schema, or backend behavior
- Re-verify after UI fix that all smoke checks still pass
- Do not enable any feature flags from Section 6 until explicitly scheduled

---

*This report is documentation only. No runtime behavior, routes, templates, static files, schema, or data were modified to produce it.*
