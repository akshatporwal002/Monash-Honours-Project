# Person 4 implementation map

> Historical reconnaissance snapshot only. This is not an active implementation plan and its
> future-tense statements are not authoritative. The single canonical plan and current status are
> in [person4-implementation-plan.md](person4-implementation-plan.md).

## Repository snapshot

QuantumLearn currently provides a minimal FastAPI and React scaffold. The backend uses an
application factory, an `/api/v1` router, Pydantic settings and schemas, and a single health
route. SQLAlchemy is declared as a dependency and SQLite is the configured MVP database, but
there is no database engine, session management, declarative base, migration environment, or
domain persistence yet. The frontend is a Vite/React placeholder and is not changed by Blocks 0
or 1.

The repository conventions that Person 4 can reuse are:

- FastAPI routes composed through `app.api.router`.
- Configuration loaded from environment variables with `pydantic-settings`.
- Pydantic response models under `app.schemas`.
- Pytest and Ruff for backend verification.
- TypeScript, ESLint, and Vite for later frontend work.

The README references environment example files that were not present at reconnaissance time.
The IDE context mentioned `quantumlearn_codex_context.md`, but that file was not present in the
workspace. Any team-wide conventions supplied by that document must be reconciled before they
replace the decisions recorded here.

## Person 4 components

Person 4 owns persistence and later services for feedback generation and judging, workflow
tracking, learning events, research comparisons, metrics, exports, and audit events. The initial
persistence slice adds:

- `app.db` for the SQLAlchemy base, engine, sessions, and FastAPI session dependency.
- `app.models` for workflow, feedback, judge, learning-event, and research records.
- `app.schemas.persistence` for validated persistence input/output contracts.
- Alembic revisions for database evolution.
- Backend tests for models, constraints, serialization, and migrations.

Later blocks should place feedback orchestration behind provider-independent services, research
and analytics calculations in separate service modules, and HTTP routes under the existing API
router. Later frontend work should use feature folders for feedback and analytics rather than
expanding the placeholder `App` component directly.

## Required team interfaces

Canonical Task, Submission, User, and Course models do not yet exist. Person 4 will not create
competing placeholder tables. Until team-owned models land, persistence records use non-empty,
opaque string references for `task_id`, `submission_id`, `pseudonymous_user_id`, and `course_id`.
A later coordinated migration may replace or augment these references with foreign keys.

The following adapters are required from other workstreams before the corresponding later block
can use production integrations:

- A task/submission context provider supplying the contracts in the Person 4 brief.
- An identity and authorization provider for ownership and role checks.
- A retrieval provider returning source-labelled chunks and relevance scores.
- A simulation provider returning circuit summaries, results, and controlled failures.
- A progress integration notified only after the feedback workflow reaches a terminal outcome.
- A provider-independent LLM client plus a background execution mechanism for baseline research.
- A project-wide API error envelope and audit actor convention.

## Persistence and privacy decisions

Person 4-owned rows use application-generated UUIDv4 strings, UTC timestamps, SQLAlchemy 2.x,
SQLite-compatible JSON fields, and Alembic migrations. Internal Person 4 relationships use
restrictive foreign keys so feedback and research evidence cannot be silently cascade-deleted.
One workflow is authoritative for each submission, and a research case groups the agentic and
single-step conditions.

Learning events store only a pseudonymous user reference. They have no raw-answer, name, email,
credential, or access-token fields. Operational logs must not contain raw answers, prompts,
direct identities, provider keys, or tokens. JSON metadata is validated against a small allow-list
before persistence. Generated feedback and approved research output may be stored in their
purpose-specific records, but not copied into learning-event metadata or operational logs.

## Risks and coordination points

- Shared model identifiers and deletion rules may differ when other workstreams deliver their
  schemas; resolve these through additive migrations rather than parallel tables.
- Authentication and course scoping are absent, so no student or research endpoints should be
  exposed until the project authorization pattern exists.
- Provider output, retrieval, and simulation contracts remain unavailable; later services must
  depend on adapters and deterministic fakes.
- SQLite does not enforce foreign keys unless enabled for every connection.
- Workflow idempotency depends on the unique submission reference and must be preserved by the
  Block 2 orchestrator.
- Research baseline work needs a background mechanism so it does not delay student feedback.
- Token and cost accounting requires provider-normalized usage metadata and versioned prices.

## Block 1 readiness and boundaries

Block 1 may proceed with external shared-domain references, Alembic, UUID string identifiers, and
the privacy rules above. It must add only persistence infrastructure, models, schemas, migrations,
tests, and supporting documentation. It must not add feedback APIs, repositories, orchestration,
LLM calls, retrieval, simulation, authentication, analytics calculations, exports, or frontend
components.

Block 1 maps to FR15, FR17, FR18, FR20, NFR17, and NFR25 by establishing durable feedback,
evaluation, workflow, learning-event, and research record structures with validation and migration
coverage. Block 2 remains responsible for mocked orchestration and idempotent workflow behavior.

## Block 2 implementation

Block 2 adds an in-process feedback pipeline under `app.services.feedback`. Provider-independent
protocols define submission, task, retrieval, simulation, feedback-generation, judging, and
persistence boundaries. Deterministic in-memory providers and configurable generator/judge fakes
support automated tests without external calls.

The pipeline loads an existing result before doing work. A repeated request returns the stored
workflow and feedback identifiers without invoking the context, generator, or judge providers
again. New work receives a UUID correlation identifier, collects validated in-memory context,
generates and judges feedback, and stores the workflow, feedback, and evaluation in one database
transaction. A uniqueness race rolls back the losing transaction and returns the winning result.

A judge pass stores accepted feedback and a first-pass completed workflow. A judge rejection is
retained for later regeneration work, marks the Block 2 workflow failed, and is never exposed as
validated feedback. Missing context and technical provider failures occur before persistence and
therefore leave no partial records. No API route or background worker is introduced; those remain
later integration work.

Block 2 maps to FR15, FR28, and NFR9. Block 3 replaces the deterministic-only generation boundary
with a structured provider-neutral agent, and Block 4 will extend rejected workflows with the single
permitted regeneration attempt.

## Block 3 implementation

Block 3 adds a versioned, provider-neutral feedback agent behind the existing generator protocol.
It builds prompts from only the available task, submission, retrieval, and simulation fields and
uses a structured LLM client contract with a recording fake for automated tests. No concrete network
provider is configured in this block.

Model output must satisfy the strict feedback-agent schema. Incorrect responses require an identified
error and an improvement action, citations are restricted to supplied retrieval and simulation IDs,
and a fixed AI-generated notice is injected by the application. Provider and validation errors are
sanitized before the pipeline handles them.

Feedback records now retain provider, prompt version, simulation references, token usage, and cost.
The additive migration backfills Block 2 data with explicit legacy metadata, and repository replay
restores the original generation measurements. Block 3 maps to FR15, FR16, NFR12, NFR13, and NFR21.
Block 4 remains responsible for the production quality judge, one regeneration attempt, and safe
fallback behavior.

## Block 4 implementation

Block 4 adds the provider-neutral `quality-judge-v1` agent, strict judge output and evaluation
contracts, deterministic safety gates, and sanitized malformed/provider-error outcomes. A reported
pass is released only when correctness, relevance, grounding, and actionability are each at least
80, it contains no unsupported claims, and its safety score is 100. Failed valid evaluations
receive deterministic regeneration guidance when the judge supplies none.

The feedback prompt advances to `feedback-v2` and can receive a rejected attempt plus its judge
guidance. Technical judge failures use fixed conservative guidance and never place malformed raw
output into the next request. The terminal pipeline performs at most two generations: it releases a
judge-approved first or second attempt, otherwise it releases fixed non-assessing fallback content.
Rejected generated feedback remains stored but unreleasable.

The complete aggregate is persisted atomically, including all successful generation attempts,
their evaluations, optional fallback, provider/model/prompt metadata, and aggregate token/cost
measurements. Replay reconstructs the same released content and internal evaluation history. The
additive migration backfills legacy judge metadata and converts legacy terminal rejections into
completed safe-fallback workflows. Block 4 maps to FR17, FR18, NFR14, and NFR23. Block 5 remains
responsible for HTTP processing states, authorization, display/reporting APIs, and frontend work.

## Block 5 implementation

Block 5 adds durable workflow claims with processing stages, a five-minute recovery lease, sanitized
retryable infrastructure failures, and an in-process executor behind a replaceable interface. The
authorized HTTP layer returns only processing state, judge-approved feedback, or the safe fallback;
authentication and ownership remain injected contracts that fail closed until team integrations
arrive.

Feedback records now retain source labels alongside cited IDs, and released feedback can be reported
once per pseudonymous actor using an allow-listed category and optional length-limited note. The
isolated React feedback module handles polling, retry, safe Markdown and code rendering, source
labels, reporting, keyboard operation, and accessible status announcements. It is not mounted in the
placeholder application because the team-owned student task page is still absent. Block 6 remains
responsible for learning-event collection.
