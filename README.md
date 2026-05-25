# AI² — AI-Powered Learning Platform

## Product Summary

AI² helps learners move through AI, product, and technical topics using AI-generated learning content, quizzes, portfolio tasks, interview practice, reflections, todos, and progress tracking.

The project is designed as a portfolio-ready architecture foundation for an adaptive learning platform. It demonstrates how an AI product can combine guided curriculum, learner state, evaluation rubrics, usage observability, and safe storage migration patterns.

## Key Features

- Topic-based learning flow
- AI-generated learning content
- Practice content generation
- Quiz evaluation
- Portfolio feedback
- Interview feedback
- Reflections and topic notes
- Daily and weekly todos
- Progress tracking
- Usage tracking
- Debug and storage health views

## Architecture Highlights

- **FastAPI routes:** Web pages, learner actions, submissions, health checks, and debug endpoints.
- **Service layer:** Focused logic for content generation, submissions, storage reads, fallback behavior, mismatch comparison, usage tracking, and safe summaries.
- **Harness layer:** Prompt templates, context building, rubrics, run records, usage policy, and output validation support.
- **Claude/Anthropic integration:** Existing Anthropic API integration powers AI content, evaluation, and feedback.
- **SessionContext runtime source of truth:** Learner-facing runtime behavior continues to use SessionContext.
- **Optional DB write-through mirrors:** Selected state can be mirrored to DB tables behind feature flags.
- **Repository layer:** DB access is isolated behind repository modules that accept injected connections.
- **Mismatch validation:** Debug services compare SessionContext state against DB mirrors before DB reads are trusted.
- **Safe observability/debug endpoints:** Storage and mismatch endpoints expose safe counts, booleans, and summaries without private content.

## Storage Strategy

SessionContext remains the runtime source of truth.

The database layer is currently an optional mirror. When enabled, write-through services can copy learner state, generated learning artifacts, submissions, notes, todos, progress, and usage events into DB tables.

DB primary reads are not enabled yet for learner-facing flows. This is intentional: mirror quality can be validated with debug checks and mismatch services before changing runtime read behavior. That reduces migration risk and keeps existing learner-facing behavior stable.

## Feature Flags

Storage-related feature flags:

- `AI2_DB_WRITE_THROUGH_ENABLED`
- `AI2_CURRICULUM_DB_READS_ENABLED`
- `AI2_PROGRESS_DB_READS_ENABLED`
- `AI2_TODOS_DB_READS_ENABLED`

Default behavior:

- Write-through is off by default.
- DB reads are off by default.
- SessionContext remains the runtime source of truth.

## Debug/Health Endpoints

Primary storage health endpoints:

- `/debug/storage-status`
- `/debug/storage-health`
- `/debug/storage-health-view`

Deeper debug endpoints also exist for curriculum, learner-state, generated-learning, and usage-events DB mirror checks and mismatch checks.

Debug endpoints are intended for internal validation and demos. They should not expose generated content, submissions, notes, usage metadata, session JSON, DB URLs, environment values, API keys, or stack traces.

## Local Development

Create and activate a virtual environment:

```bash
python -m venv .venv
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Set environment variables with placeholders only:

```bash
ANTHROPIC_API_KEY=your_anthropic_api_key_here
DATABASE_URL=your_database_url_here
AI2_DB_WRITE_THROUGH_ENABLED=0
AI2_CURRICULUM_DB_READS_ENABLED=0
AI2_PROGRESS_DB_READS_ENABLED=0
AI2_TODOS_DB_READS_ENABLED=0
```

Run the FastAPI app:

```bash
uvicorn app:app --reload --port 8000
```

Run tests:

```bash
python -m pytest
```

For test mode, set:

```bash
AI2_TEST_MODE=1
```

## Testing

The project includes a focused pytest suite covering learner flows, harness behavior, usage tracking, schema expectations, repositories, write-through services, read/fallback services, mismatch services, and debug endpoints.

Example focused test command:

```bash
python -m pytest tests/test_storage_health_endpoint.py tests/test_mismatch_logging_service.py
```

On Windows, if pytest hits temp directory permission issues for `tmp_path`, rerun from a terminal/session with proper temp-write permissions.

## Current Status

This is a portfolio-ready architecture foundation, not a fully hardened production deployment.

Completed foundations include the harness layer, rubric-backed evaluation flows, usage tracking, DB mirror schema, repository layer, optional write-through, read/fallback services, mismatch validation, safe logging, and storage health views.

## Planned Improvements

- DB-primary reads after mirror confidence is high
- Stronger automated eval datasets
- Usage-limit enforcement
- Admin analytics dashboard
- Deployment hardening
- Portfolio/export artifact feature
