# AI² Final Architecture Overview

## 1. Product Summary

AI² is an AI-powered learning platform that helps learners move through a structured AI learning journey. It supports topic learning content, practice generation, quiz evaluation, portfolio feedback, interview practice, reflections, todos, and progress tracking.

The product goal is to give learners a guided path while still adapting to their current track, topic, and work history. The current implementation is a portfolio-ready architecture foundation, not a claim of a fully hardened production system.

## 2. High-Level Architecture

The app is organized into practical layers:

- **FastAPI routes:** Browser pages, learner actions, submissions, debug endpoints, and health checks.
- **Services:** Focused business logic for generated content, submissions, storage reads, fallback behavior, mismatch comparison, usage tracking, and safe summaries.
- **Harness layer:** Prompt templates, context building, rubrics, run records, usage policy, and output validation support.
- **Claude/Anthropic provider:** The existing Anthropic integration remains the AI generation and evaluation provider.
- **SessionContext runtime state:** The active learner state object used by runtime learner-facing flows.
- **Optional DB mirror layer:** PostgreSQL schema, repositories, write-through services, read services, fallback services, and mismatch checks.
- **Debug/observability endpoints:** Safe endpoints for storage status, DB mirror checks, mismatch checks, and storage health summaries.

## 3. Source of Truth Strategy

SessionContext remains the runtime source of truth for learner-facing behavior.

The database layer is currently used as an optional mirror. When `AI2_DB_WRITE_THROUGH_ENABLED` is enabled, selected runtime state can be written through to DB tables, but learner-facing routes still read from SessionContext.

DB primary reads are not enabled yet for learner-facing flows. This reduces migration risk because DB mirrors can be validated, compared, and observed before they are trusted as the primary runtime source.

## 4. Harness Engineering Layer

The harness layer makes the AI behavior more product-engineered and testable:

- **prompt_templates:** Centralizes prompt wording and structure so prompts are easier to review, version, and improve.
- **context_builder:** Builds the learner/topic context passed into AI calls, keeping prompt inputs more consistent.
- **rubrics:** Defines scoring expectations for quiz, portfolio, and interview feedback.
- **usage_policy:** Captures usage-policy decisions without enforcing hard limits yet.
- **run_records:** Provides structured records for AI runs and usage events.
- **guardrails/output_validators:** Supports safer output handling by checking format and expected fields before storing or displaying results.

For AI Product Manager interviews, this is the layer that shows the product is not just “calling an LLM.” It has prompt design, context management, evaluation structure, and observability around model behavior.

## 5. Evaluation and Rubric System

AI² uses separate rubrics for different learning tasks:

- **Quiz rubric:** Evaluates learner answers against the topic and expected understanding.
- **Portfolio rubric:** Reviews applied work and gives structured feedback for improvement.
- **Interview rubric:** Assesses interview-style answers for clarity, correctness, and communication quality.

Scores and feedback are parsed into structured submission records and stored in SessionContext. Optional DB mirrors can persist those records through write-through services.

What is still missing for a full automated model-eval suite:

- Curated eval datasets with expected answer ranges.
- Regression tests across multiple model versions.
- Human review calibration for rubric scores.
- Drift monitoring for feedback quality over time.

## 6. Storage and DB Migration Design

The storage migration is designed as a staged, low-risk path:

- **Schema tables:** Learning tracks, topics, topic progress, todos, generated topic content, generated practice, quiz submissions, portfolio submissions, interview submissions, topic notes, and usage events.
- **Repositories:** Small DB access modules that accept injected connections and do not own runtime behavior.
- **Write-through services:** Optional mirror writes behind `AI2_DB_WRITE_THROUGH_ENABLED`.
- **Read services:** Safe DB read helpers that normalize rows without changing learner-facing flows.
- **Fallback services:** Services that can fall back to SessionContext or temporary seed data when DB reads are disabled or unavailable.
- **Mismatch services:** Compare SessionContext state against DB mirror state for learner state, generated learning, and usage events.
- **Storage health endpoint/view:** `/debug/storage-health` and `/debug/storage-health-view` summarize flags, mirror readiness, and safe counts/booleans.

This gives the app a production-style migration foundation while keeping runtime behavior stable.

## 7. Observability and Usage Tracking

AI² tracks lightweight usage events in SessionContext:

- `usage_events` records generation/evaluation events.
- `usage_summary()` aggregates counts by source, status, and event type.
- The `usage_events` DB table can mirror usage events when write-through is enabled.

Observability is intentionally privacy-aware:

- Safe logging utilities redact sensitive error details.
- Mismatch logging summarizes comparison outcomes without raw values.
- Debug responses and logs avoid prompt text, generated content, submissions, notes, usage metadata payloads, DB URLs, env values, and API keys.

## 8. Safety and Privacy Design

Debug and health surfaces are designed to be safe for demos and internal validation:

- No full generated learning content is shown in storage health views.
- No quiz, portfolio, or interview submission text is shown.
- No topic note text is shown.
- No full SessionContext JSON or session_data payload is shown.
- No full usage event metadata is shown.
- Safe error handling avoids exposing DB URLs, API keys, raw environment values, and stack traces.
- Debug endpoints return counts, booleans, summary statuses, and sanitized comparison output.

## 9. Current Feature Flags

Current storage-related flags:

- `AI2_DB_WRITE_THROUGH_ENABLED`
- `AI2_CURRICULUM_DB_READS_ENABLED`
- `AI2_PROGRESS_DB_READS_ENABLED`
- `AI2_TODOS_DB_READS_ENABLED`

Default behavior:

- Write-through is off by default.
- DB reads are off by default.
- SessionContext remains the runtime source of truth.

## 10. Debug Endpoints

Important storage and mirror validation endpoints:

- `/debug/storage-status`
- `/debug/storage-health`
- `/debug/storage-health-view`
- `/debug/curriculum-db-check`
- `/debug/learner-state-db-check`
- `/debug/learner-state-mismatch-check`
- `/debug/generated-learning-db-check`
- `/debug/generated-learning-mismatch-check`
- `/debug/usage-events-db-check`
- `/debug/usage-events-mismatch-check`

These endpoints are for validation and observability. They are not learner-facing product flows.

## 11. What Is Production-Ready vs What Is Still Planned

Production-style foundations completed:

- Harness layer for prompts, context, rubrics, run records, and validation support.
- Rubric-backed quiz, portfolio, and interview feedback flows.
- DB schema for learning state, generated learning, submissions, notes, and usage events.
- Repository layer with injected DB connections.
- Optional write-through mirrors.
- DB read and fallback services.
- Mismatch checks for DB mirror validation.
- Safe storage health JSON endpoint and visual debug view.
- Usage observability and mismatch logging summaries.

Still planned:

- DB-primary reads after mirror confidence is high.
- Stronger automated eval datasets.
- Usage-limit enforcement.
- Admin analytics dashboard.
- Deployment hardening.
- Portfolio export/artifact feature.

## 12. Interview Talking Points

- I kept SessionContext as the runtime source of truth while adding DB mirrors, which reduces migration risk.
- I separated learner-facing behavior from storage validation so the product can evolve without breaking current users.
- I added rubrics and structured evaluation flows instead of treating the LLM as a black box.
- I built observability around usage and DB mirror quality before enabling enforcement or DB-primary reads.
- I designed debug endpoints to show safe counts, booleans, and summaries without leaking private learner content.
- I used feature flags so storage changes can be tested gradually.
- I added mismatch services to compare runtime state against DB mirrors before trusting the database.
- The current system is a portfolio-ready architecture foundation with a clear path toward production hardening.
