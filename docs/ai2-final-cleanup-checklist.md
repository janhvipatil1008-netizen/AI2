# AI² Final Cleanup Checklist

Use this checklist before pushing or sharing the repository for portfolio/interview review.

## 1. Files To Inspect Before Push

- Review `README.md` for accurate setup, testing, and status language.
- Review `docs/ai2-final-architecture-overview.md` for current architecture claims.
- Review recent service/test files for accidental debug prints or temporary comments.
- Review `git status --short` and inspect every modified or untracked file.
- Confirm runtime changes are intentional and covered by tests.

## 2. Generated And Cache Files To Avoid Committing

Avoid committing generated local artifacts unless they are intentionally part of the project:

- `.pytest_cache/`
- `.pytest_tmp/`
- `__pycache__/`
- `*.pyc`
- coverage output such as `.coverage`, `htmlcov/`, or coverage XML
- local virtual environments such as `.venv/`, `venv/`, or `env/`
- local build/dist folders

## 3. Environment And Secrets Check

Before pushing:

- Do not commit `.env` or local environment files.
- Do not commit real `ANTHROPIC_API_KEY` values.
- Do not commit real `DATABASE_URL` or `SUPABASE_DATABASE_URL` values.
- Do not commit API keys, tokens, passwords, session cookies, or auth secrets.
- Search changed files for `sk-`, `postgresql://`, `DATABASE_URL=`, and `ANTHROPIC_API_KEY=`.
- Keep docs and examples on placeholders only.

## 4. Pytest Temp Folders

Windows pytest runs may create temp directories or hit `tmp_path` permission issues.

Before committing:

- Check for `.pytest_tmp/`.
- Check for `.pytest_cache/`.
- Do not commit temp files created by failed or interrupted test runs.
- If pytest fails on Windows temp permissions, rerun from a terminal/session with proper temp-write permissions.

## 5. Python Cache Cleanup

Inspect for:

- `__pycache__/`
- `*.pyc`
- `*.pyo`

These should not be committed.

## 6. Local DB Dumps And Data Exports

Avoid committing:

- local database dumps
- SQL export files with private data
- CSV exports
- JSON session dumps
- generated seed/export output unless explicitly intended and sanitized

If a data file is needed for docs or tests, confirm it contains no private learner data or secrets.

## 7. Screenshots And Debug Exports

Avoid committing incidental demo/debug artifacts:

- screenshots containing user/session data
- debug endpoint response exports
- browser downloads
- Playwright screenshots/videos unless intentionally used as test artifacts
- logs copied from local runs

If screenshots are included for portfolio use, confirm they show no private content, API keys, DB URLs, env values, or raw session JSON.

## 8. Accidental Logs

Search for and avoid committing:

- `*.log`
- traceback dumps
- local server logs
- raw prompt/response logs
- debug exports containing generated content, submissions, notes, usage metadata, or session data

Safe observability should stay at counts, booleans, summaries, and redacted error metadata.

## 9. Large Model Or Vector Artifacts

Avoid committing large artifacts unless intentionally required:

- model weights
- vector indexes
- embedding caches
- local Chroma/FAISS stores
- large generated datasets
- notebook checkpoints

If needed later, document how to regenerate them or store them outside git.

## 10. Documentation Check

Confirm these docs are up to date:

- `README.md`
- `docs/ai2-final-architecture-overview.md`
- `docs/ai2-final-cleanup-checklist.md`
- relevant migration or architecture docs under `docs/`

Make sure docs say "portfolio-ready architecture foundation" or "production-style foundation" where appropriate, not "fully production-ready."

## 11. Test Check

Before final push:

- Run the focused suite relevant to the changed area.
- Run the broader focused suite when runtime behavior changed.
- For documentation-only changes, run the smallest safe smoke tests.
- Confirm no learner-facing route behavior changed unless that was the explicit goal.

Suggested smoke command for the final docs/cleanup step:

```bash
python -m pytest tests/test_storage_health_endpoint.py tests/test_mismatch_logging_service.py
```

## 12. Final Review Questions

- Did I avoid deleting files accidentally?
- Did I avoid committing `.env` or secrets?
- Did I keep SessionContext as the runtime source of truth?
- Did I avoid switching learner-facing routes to DB reads?
- Did I avoid adding private content to debug views, logs, or docs?
- Did I keep test results and architecture claims honest?
