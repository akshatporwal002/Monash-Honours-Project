# QuantumLearn architecture

QuantumLearn is a two-application MVP:

- `frontend` is a React and TypeScript single-page application built with Vite.
- `backend` is a FastAPI application using synchronous SQLAlchemy 2.x, SQLite, and Alembic.

The browser communicates with the versioned `/api/v1` API using an HTTP-only session cookie and a
CSRF token. The frontend uses `/api/v1` by default and reads an override from
`VITE_API_BASE_URL`.

## Frontend

`src/App.tsx` owns session restoration, login/logout, role routing, and the selected task. The
role-specific views are mounted in the shared application shell:

| Role | Mounted views |
| --- | --- |
| Student | Dashboard, module pathway, progress and gamification, recommendations and reminders, interactive task view |
| Educator | Engagement dashboard, four-step course editor, student table and bulk reminders, cohort analytics |
| Administrator | Platform overview, user management, course management, system settings |

`src/app/api.ts` is the application-facing HTTP boundary. It sends credentials, copies the
`ql_csrf` cookie into `X-CSRF-Token` on mutating requests, normalizes the backend's
`administrator` role to the UI's `admin` label, and adapts API response shapes for components.
Feedback and analytics have focused feature modules consumed by the mounted task and analytics
views.

## Backend

The FastAPI application is composed in `app/api/router.py`. Its mounted route groups cover:

- authentication and role-guarded LMS operations;
- courses, modules, outcomes, enrolments, materials, tasks, drafts, and submissions;
- student dashboards, simulation, recommendations, reminders, and achievements;
- educator dashboards, student monitoring, notifications, and analytics;
- administrator users, courses, and system settings;
- grounded retrieval and task generation;
- feedback workflows, learning events, audited research exports, health, and readiness.

Route functions validate transport data and delegate domain decisions to services. The canonical
LMS boundary is `app/services/lms.py`; focused services implement authentication, material
indexing, retrieval, quantum simulation, feedback, judging, gamification, analytics, audit, and
research workflows. Provider-specific behavior is behind protocols or adapters.

## Persistence

Alembic is the only schema creation mechanism; application startup does not create tables. The
current canonical schema includes:

- users and student profiles;
- courses, modules, enrolments, and weekly/topic learning outcomes;
- learning materials and extracted material chunks;
- learning tasks, prerequisite edges, and the six requirement-named task types;
- drafts, immutable numbered submission attempts, progress summaries, recommendations, reminders,
  points, levels, and achievements;
- feedback workflow attempts and judge evaluations;
- pseudonymous learning events, research measurements, exports, and append-only audit events;
- terminal integration, continuation, and singleton worker lease records.

Course and task relationships use database constraints. Accepted submission attempts are
append-only: a resubmission creates the next attempt rather than modifying earlier evidence.
Migrations must be applied with:

```powershell
cd backend
uv run --frozen alembic upgrade head
```

## Authorization and request safety

Authentication uses Argon2id password hashes and signed, expiring session cookies. Server-side
dependencies enforce student, educator, and administrator roles. Service checks further restrict
students to their own enrolments and educators to courses they own; administrator operations use a
separate guard.

Mutating browser requests carry the CSRF token issued at login. Explicit CORS origins, bounded
request bodies, correlation IDs, security headers, route-template logging, and structured-value
redaction are applied centrally. Login/logout and LMS changes write correlated audit records.
Production configuration requires unique session and pseudonym secrets and secure cookies.

Material links must use HTTPS. Uploaded or linked content is returned only after the same
course-access check; uploaded files use safe attachment and content-type headers.

## Canonical learning loop

1. An educator creates a course, modules, and weekly or topic outcomes.
2. The educator uploads PDF, DOCX, or PPTX material or registers an HTTPS resource.
3. Uploaded text is extracted, normalized, heading-aware chunked, and persisted in the offline
   lexical index.
4. The educator generates three to six scaffolded tasks tied to an outcome and source references,
   then publishes the course and enrols students.
5. The student follows prerequisite ordering, saves a draft, optionally runs a circuit, and
   submits an answer.
6. The submission becomes an immutable attempt. Feedback is generated, judged, regenerated once
   when required, and otherwise replaced by the fixed safe fallback.
7. Progress, points, achievements, learning events, reminders, and a persisted next-task
   recommendation update the role dashboards and analytics.

The supported task types are `multiple_choice`, `multiple_answer`, `short_answer`,
`code_explanation`, `code_completion`, and `quantum_circuit`. Legacy enum values remain readable
only for early database rows.

## AI, retrieval, and simulation

The local configuration is intentionally deterministic and offline. When no usable external model
credential/model pair is available, local task-generation, feedback, and judge adapters keep the
MVP runnable without a model download or network call. Runtime provider and model selection reads
administrator-managed settings, falling back to environment configuration.

An external structured-output-compatible service can be selected with `LLM_API_KEY`, `LLM_MODEL`,
`LLM_PROVIDER`, `LLM_API_BASE_URL`, timeouts, and cost rates. The shared client validates
structured responses and stores provider/model, latency, usage, and estimated cost without
exposing them to students.

Grounding uses authorized course chunks and source references. The feedback pipeline combines task
context, retrieved material, and any circuit simulation result; the judge records correctness,
relevance, grounding, actionability, safety, and its pass/fail reason. Rejected output is retained
as internal evidence but is never released as validated feedback.

Quantum-circuit requests are validated and executed by Qiskit Aer using the supported introductory
H, X, and CX gates, bounded qubit/shot counts, and seeded simulation. Invalid circuits become
controlled client errors rather than terminating the session.

## Material storage and indexing

The canonical authoring API accepts PDF, DOCX, and PPTX uploads up to
`RAG_MAX_FILE_BYTES` (20 MB by default) and HTTPS links. Files are stored below
`RAG_UPLOAD_DIR`. Extractors for each accepted format produce normalized blocks, and the
heading-aware chunker persists `MaterialChunk` records marked with `local-lexical-v1`. A failed
extraction leaves the material record in a visible failed state instead of losing the educator's
upload.

The deterministic, course-scoped lexical retriever is the runtime generation and feedback path.
It keeps the MVP offline-capable and avoids a separate model download or vector server. Generic
embedding and vector-store contracts remain independently tested extension boundaries.

## Feedback durability and database worker

A feedback request claims a durable workflow and starts the normal execution path in process.
Leases and uniqueness constraints make duplicate requests idempotent and allow interrupted work to
be reclaimed.

One serial SQLite worker handles feedback recovery, terminal-integration reconciliation, baseline
research jobs, and continuation jobs. It requires `WORKER_ADAPTER_FACTORY` to identify a factory
returning `app.worker.WorkerAdapters` and refuses to start if required adapters are absent. A
durable singleton lease prevents two workers from processing the queues concurrently.

```powershell
cd backend
$env:WORKER_ADAPTER_FACTORY="team_integration.worker:create_worker_adapters"
uv run --frozen quantumlearn-worker
```

See [worker operations](worker-operations.md) for adapter requirements, leases, recovery, and
readiness behavior.

## Research, analytics, and audit

Learning events contain pseudonymous actors and allow-listed metadata; raw answers and direct
identities are excluded. Terminal feedback can create paired agentic-RAG and isolated single-step
baseline measurement intents. Analytics return aggregates with sample sizes and missingness.
Research export is typed, bounded, pseudonymous, and strictly audited before bytes are sent.

Audit records are append-only and correlated to the originating request. Privacy-safe logging and
export validation keep prompts, credentials, direct student identifiers, and submitted answer text
out of operational logs and research datasets.

## Deployment boundary

Configuration comes from environment variables or administrator-managed runtime settings; secrets
remain server-side. Liveness at `/api/v1/health` is independent of integrations. Readiness at
`/api/v1/ready` verifies the database, migration head, worker heartbeat, pseudonym secret, and
production adapter/credential configuration without calling an LLM.

The committed OpenAPI document and generated frontend contracts are checked for drift. Requirement
coverage and any externally measured acceptance evidence are tracked in
[requirements-traceability.md](requirements-traceability.md).
