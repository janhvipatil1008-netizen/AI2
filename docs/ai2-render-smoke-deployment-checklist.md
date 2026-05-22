# AI² Render Smoke Deployment Checklist

## 1. Pre-Deploy Requirements

- Review `git status --short`.
- Stage only intended files.
- Commit the modular migration foundation clearly.
- Do not include temp/cache/local DB files.
- Do not deploy from a messy worktree.
- Confirm no secrets are staged.
- Confirm broad safe regression passes, or document any local-only blockers.

## 2. Required Render Environment Variables

Set these in the Render dashboard:

- `AI2_ENV=production`
- `TEST_MODE=0` or unset; in this app, do not set `AI2_TEST_MODE=1`
- `AUTH_SECRET`
- `AI2_DEBUG_TOKEN`
- `ANTHROPIC_API_KEY`
- `SUPABASE_DATABASE_URL`; this is the project’s active DB env var read by `database/pool.py`. If your Render setup uses `DATABASE_URL`, map or copy it into `SUPABASE_DATABASE_URL`.
- `AI2_MODULAR_CURRICULUM_READS_ENABLED=false`
- `AI2_DB_WRITE_THROUGH_ENABLED=false` initially
- Exact first-smoke value: `AI2_DB_WRITE_THROUGH_ENABLED=false initially`
- `AI2_TODOS_DB_READS_ENABLED=false`
- `AI2_PROGRESS_DB_READS_ENABLED=false`
- `AI2_USAGE_LIMITS_ENABLED=true`

## 3. First Smoke Deploy Flag Strategy

- Keep modular reads false first: `AI2_MODULAR_CURRICULUM_READS_ENABLED=false`.
- Keep DB write-through false until `database/schema.sql` is confirmed applied.
- Keep SessionContext-first behavior for the first smoke deployment.
- Keep todo/progress DB reads false until write-through and fallback checks are verified.
- Enable DB flags gradually after smoke testing.

Recommended first deploy flags:

```env
AI2_MODULAR_CURRICULUM_READS_ENABLED=false
AI2_DB_WRITE_THROUGH_ENABLED=false
AI2_TODOS_DB_READS_ENABLED=false
AI2_PROGRESS_DB_READS_ENABLED=false
AI2_USAGE_LIMITS_ENABLED=true
```

## 4. Render Dashboard Checks

- Confirm the latest commit hash matches the intended deployment commit.
- Check Render build logs for dependency install failures.
- Check Render runtime logs for startup failures.
- Confirm start command is `uvicorn app:app --host 0.0.0.0 --port $PORT`.
- Verify `/health` returns OK.
- Verify required environment variables are present.
- Verify DB connection status after schema is applied and DB features are enabled.
- Check logs for production config errors, missing `AUTH_SECRET`, accidental test mode, or failed DB connections.

## 5. Smoke Test Flow

Run the normal learner path:

- Open app.
- Signup.
- Login.
- Onboarding.
- Dashboard.
- Topics page.
- Topic detail.
- Generate lesson.
- Generate practice.
- Quiz evaluation.
- Portfolio feedback.
- Interview feedback.
- Todos.
- Learning outcome form.
- Beta feedback.
- Privacy page.
- Terms page.

## 6. Protected Admin/Debug Checks

In production:

- `/debug/storage-health` requires `X-AI2-Debug-Token`.
- `/debug/modular-curriculum` requires `X-AI2-Debug-Token`.
- `/admin/beta-metrics` requires `X-AI2-Debug-Token`.
- Wrong or missing token returns `404`.
- Debug/admin responses must not expose DB URLs, API keys, submissions, generated content, feedback text, or raw environment values.

## 7. Database Schema Steps

- Apply `database/schema.sql` before enabling DB write-through.
- Run `scripts/seed_modular_curriculum.py` manually only after schema is applied.
- Keep `AI2_MODULAR_CURRICULUM_READS_ENABLED=false` until seed and `/debug/modular-curriculum` are verified.
- Keep `AI2_DB_WRITE_THROUGH_ENABLED=false` until schema is confirmed.
- Enable `AI2_DB_WRITE_THROUGH_ENABLED=true` only for a controlled DB mirror smoke test.

## 8. Rollback Plan

- Set `AI2_MODULAR_CURRICULUM_READS_ENABLED=false`.
- Set DB write-through/read flags false:
  - `AI2_DB_WRITE_THROUGH_ENABLED=false`
  - `AI2_TODOS_DB_READS_ENABLED=false`
  - `AI2_PROGRESS_DB_READS_ENABLED=false`
- Redeploy the previous commit if needed.
- Check Render runtime logs after rollback.
- Preserve logs and failing request details for diagnosis.

## 9. What Not To Test Yet

- Azure migration.
- Azure AI Foundry.
- Payments.
- Removing `current_week`.
- Deleting `WEEKS` or `ROLE_TRACKS`.
- Replacing Claude/Anthropic.

## 10. Pass/Fail Criteria

Pass criteria:

- App loads.
- Auth works.
- Onboarding works.
- Dashboard, topics, and topic detail work.
- At least one Claude generation works.
- No 500s in normal learner flow.
- Admin/debug routes are protected.

Fail criteria:

- App cannot boot.
- Auth is broken.
- Dashboard or topics are broken.
- Claude generation is broken.
- Env/config production errors appear.
- Private debug endpoints are exposed.
