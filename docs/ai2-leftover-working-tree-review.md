# AI² Leftover Working Tree Review

## 1. Current Status

`git status --short` shows:

```text
 M app.py
 M tests/test_auth_routes_split.py
 M tests/test_syllabus_routes_split.py
?? routes/jobs.py
?? tests/test_jobs_routes_split.py
```

## 2. File-by-File Findings

### app.py

Changed from defining jobs routes directly to including a jobs router:

- Removed the top-level jobs database helper import block for `_get_jobs`, `_get_job_detail`, and `_get_jobs_stats`.
- Removed direct route handlers for:
  - `GET /jobs`
  - `GET /jobs/{job_id}`
  - `GET /api/jobs/health`
  - `POST /api/jobs/enrich/{job_id}`
  - `POST /api/jobs/refresh`
- Added:
  - `from routes.jobs import router as jobs_router`
  - `app.include_router(jobs_router)`

Finding: this appears to be a valid completed jobs route split, not accidental duplicate work. The route URLs appear preserved through the router include.

Recommended action: commit with the jobs split after running the jobs route tests.

### tests/test_auth_routes_split.py

Changed one assertion in `test_non_auth_routes_not_moved_into_auth_routes`:

- Previously expected `@app.get("/jobs"` to remain directly in `app.py`.
- Now expects `from routes.jobs import router as jobs_router` in `app.py`.

Finding: this is consistent with jobs routes having moved out of `app.py`. It updates the auth split guard so it still verifies jobs routes were not moved into auth routes.

Recommended action: commit with the jobs split.

### tests/test_syllabus_routes_split.py

Changed one assertion in `test_non_syllabus_routes_not_moved_in_this_step`:

- Previously expected `@app.get("/jobs"` to remain directly in `app.py`.
- Now expects `from routes.jobs import router as jobs_router` in `app.py`.

Finding: this is consistent with jobs routes having moved out of `app.py`. It updates the syllabus split guard so it still verifies jobs routes were not moved into syllabus routes.

Recommended action: commit with the jobs split.

### routes/jobs.py

New router module for job search routes.

It defines:

- `router = APIRouter()`
- `GET /jobs`
- `GET /jobs/{job_id}`
- `GET /api/jobs/health`
- `POST /api/jobs/enrich/{job_id}`
- `POST /api/jobs/refresh`

It moves the jobs DB helper imports into the module and uses `routes.deps` for shared runtime dependencies:

- `deps.templates`
- `deps.TEST_MODE`
- `deps.get_session_data`
- `deps.run_blocking`

Finding: this is the expected destination for a completed jobs route split. It does not appear to duplicate already-committed work because `routes/jobs.py` is untracked and `app.py` still has the corresponding removal diff.

Recommended action: commit with the jobs split after verification.

### tests/test_jobs_routes_split.py

New focused test file for the jobs route split.

It verifies:

- `routes/jobs.py` exists and defines the expected router routes.
- `app.py` includes `jobs_router`.
- Job route URLs remain registered.
- `/jobs` still loads when DB helpers fail.
- `/jobs` renders jobs and stats.
- `/jobs/{job_id}` preserves 404 behavior.
- `/api/jobs/health` preserves JSON behavior.
- `app.py` no longer defines jobs route handlers directly.
- Non-jobs routes were not moved into `routes/jobs.py`.

Finding: this is a valid regression test for the jobs route split.

Recommended action: commit with the jobs split.

## 3. Recommendation

Recommendation: commit jobs split.

Classification: A. valid completed jobs route split that should be committed.

This does not look like accidental leftover changes that duplicate already-committed work. It also does not look unsafe or mixed with chat/session route changes. The changes are scoped to jobs routing plus tests that account for the new split.

Before committing, run the relevant jobs split test, for example:

```text
python -m pytest tests/test_jobs_routes_split.py
```

## 4. Safety Notes

The chat/session route split should wait until the working tree is clean.

Starting the chat/session split while these jobs changes remain uncommitted would mix two route-split efforts in the same working tree, making review, rollback, and regression triage harder. Commit or otherwise resolve the jobs split first, then begin the chat/session route split from a clean status.
