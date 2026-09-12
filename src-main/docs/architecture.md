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
| Educator | Engagement dashboard, course editor, student monitoring, cohort analytics; Assessment setup and Assessment review with a current course assessor grant |
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
- immutable teaching-task/source revisions and approvals, prerequisite edges, typed tasks and
  frozen assessment work starts;
- drafts, immutable numbered submission attempts, progress summaries, recommendations, reminders,
  points, levels, and achievements;
- feedback workflow attempts and judge evaluations;
- pseudonymous learning events, research measurements, exports, and append-only audit events;
- terminal integration, continuation, and singleton worker lease records;
- versioned assessment definitions, criterion decisions, human confirmation, moderation and
  correction histories;
- evidence-linked learner-model snapshots, preferences, study consent/grants, instruments,
  operational snapshots and disposal receipts.

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
students to their own enrolments and educators to their authorised courses; administrator operations
use a separate guard. Teaching eligibility and a separate administrator-issued course assessor grant control
formal assessment access. Owning a course or having an administrator account does not itself supply
that assessor authority.

Mutating browser requests carry the CSRF token issued at login. Explicit CORS origins, bounded
request bodies, correlation IDs, security headers, route-template logging, and structured-value
redaction are applied centrally. Login/logout and LMS changes write correlated audit records.
Production configuration requires unique session and pseudonym secrets and secure cookies.

Material links must use HTTPS. Uploaded or linked content is returned only after the same
course-access check and applicable clean-scan/current-material gates; uploaded files use safe
attachment and content-type headers. Historic frozen source passages retain their scoped history.

## Canonical learning loop

1. An educator creates course outcomes and supplies authorised material. Intake records quarantine,
   scanning, extraction and immutable source revisions; a source approval is an explicit action.
2. Generated tasks and representations are saved as drafts bound to their source passages. The
   educator reviews the exact saved revision, including required content-quality dimensions, before
   teaching-task approval. Saving or generating does not publish a reviewed task.
3. A course-authorised assessor defines the claim, Bloom target, criteria, pass rule, task forms,
   tools, support/access conditions, feedback and adaptation plan. Assessment-definition approval
   is separate from teaching-task approval. Course/pathway publication retains its own gates.
4. The learner opens an available task. **Start assessed task** freezes the reviewed version and
   conditions before assessed work; ordinary practice does not acquire a formal result merely
   because it uses the same content type.
5. Drafts, predictions, simulation evidence, supported revisions/reflection and fresh application
   are recorded through typed interfaces. Transfer suppresses instructional help while preserving
   the approved access conditions. A submitted response is an immutable attempt.
6. Feedback passes its own quality gate or produces a safe fallback. It does not confirm an
   assessment result. Durable continuation records evidence-linked model updates and suggestions.
7. Authorised assessors inspect frozen evidence, record criterion decisions and apply the frozen
   pass rule. Configured independent moderation gates selected attempts. Only released human
   decisions expose PASS or INCOMPLETE; pending verdicts remain hidden.
8. Learners can inspect the result, missing evidence, next action and review history, and request
   assessor review where permitted. Corrections and fresh reassessment preserve earlier evidence.

Runtime types include single/multiple choice, short answer, code explanation/completion, quantum
circuit, matching/sequencing, and typed prediction/reasoning/explanation/revision/reflection/transfer
episodes. Five standalone PD4 types remain documented extensions, not delivered runtime types; see
[task-type contracts](task-type-extension.md). Legacy quiz/code/circuit aliases remain readable.

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
context, retrieved material, and any circuit simulation result; the judge retains quality findings
and their reasons/evidence. Externally generated feedback requires a current version-bound
category-quality receipt across all ten required dimensions. Exact local templates and frozen
approved assessment selections use separately bound structural or inherited-content receipts;
those receipts do not claim a fresh semantic quality review.
Historical compatible receipts retain their own versioned rules. Quality approval/rejection is
separate from PASS/INCOMPLETE assessment decisions. Rejected content is never released as validated
feedback; deterministic structure checks do not establish factual or educational validity.

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

The default `RAG_RETRIEVAL_BACKEND=local_vector` uses deterministic 2,048-dimensional signed
word-frequency vectors and a disposable SQLite vector cache. It needs no model download or external
vector server and makes no trained semantic-quality claim. Candidate text and scope come from the
main database; current source approval, revision, retirement and scan gates remain authoritative.
The optional `lexical` adapter retains the same access and safety gates. Chunk extraction metadata
such as `local-lexical-v1` does not select the runtime retrieval backend. See the
[local vector delivery](../../docs/learnlens/local-vector-retrieval.md).

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
out of operational logs and the minimal technical export. Separately authorised study-operational
exports can include selected response/code/episode or AI text only with exact purpose/field/consent
grants, source-bound redaction approval and revalidation. Coded instrument exports exclude raw
instrument text. See [the versioned export dictionary](research-export-schema.md).

Research activation requires deployment opt-in plus a current exact study release, approved plans
and instruments, consent and grants. Synthetic forms or a successful CI run do not activate a study.
Restricted instrument-text disposal has an explicit inventory/authority/hold-checked workflow; other
record classes remain subject to an approved retention plan and may need class-specific work.

## Deployment boundary

Configuration comes from environment variables or administrator-managed runtime settings; secrets
remain server-side. Liveness at `/api/v1/health` is independent of integrations. Readiness at
`/api/v1/ready` verifies the database, migration head, worker heartbeat, pseudonym secret, and
production adapter/credential configuration without calling an LLM.

The committed OpenAPI document and generated frontend contracts are checked for drift. Requirement
coverage and any externally measured acceptance evidence are tracked in
[the current requirement matrix](../../docs/learnlens/implementation-gap-matrix.md);
[requirements-traceability.md](requirements-traceability.md) retains its earlier scope.
