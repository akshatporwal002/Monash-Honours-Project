# Architecture notes

QuantumLearn starts as two independently runnable applications:

- `frontend`: the React user interface.
- `backend`: the FastAPI application programming interface (API).

Feature-specific folders will be added only when those features are implemented. SQLite is the intended MVP data store. Secrets must be supplied through environment variables and must not be committed.

## Persistence foundation

The backend uses synchronous SQLAlchemy 2.x sessions and Alembic migrations. SQLite foreign-key
enforcement is enabled for application and migration connections. Application startup does not
create tables automatically; local and deployed databases must run `alembic upgrade head`.

Person 4 owns the `workflow_runs`, `feedback_records`, `judge_evaluations`, `learning_events`,
`research_evaluations`, `terminal_integration_outbox`, `continuation_jobs`, and singleton
`worker_heartbeats` tables. These records use UUIDv4 strings and UTC timestamps. Relationships
inside this group use restrictive foreign keys so evaluation evidence and pending continuation
work are not cascade-deleted.

Task, Submission, User, and Course tables are not yet available. Their identifiers are stored as
opaque external references rather than duplicating another feature team's models. A coordinated
future migration may add foreign keys after the canonical shared tables and deletion rules exist.

Learning events contain only pseudonymous user references and allow-listed metadata. They must not
store raw submitted answers, direct identities, prompts, credentials, provider keys, or tokens.

## Feedback service boundary

The feedback pipeline is an async in-process application service. It depends on protocols for
submission lookup, context collection, feedback generation, feedback judging, and persistence.
This keeps external LLM, retrieval, simulation, and shared-domain implementations replaceable.

The terminal workflow stores up to two generated attempts, one evaluation per successful
generation, and an optional safe fallback in one transaction. Infrastructure and context failures
leave no partial workflow. Duplicate requests first return the existing aggregate, while database
uniqueness protects against concurrent duplicate saves. Rejected feedback is retained as internal
evidence but is never returned as validated student feedback.

Block 5 exposes the pipeline through authorized feedback routes. A durable workflow claim returns a
processing state before an in-process executor opens a fresh database session and runs the pipeline.
Duplicate requests share the same claim, failed work is retryable, and an expired five-minute lease
allows work interrupted by a process restart to be reclaimed. A distributed worker can replace the
executor without changing the route contract.

## Feedback agent

The feedback agent builds a versioned `feedback-v2` request and depends on a structured LLM
client protocol rather than a provider SDK. Model output is validated against a strict schema before
it can enter the feedback pipeline. Incorrect feedback must identify the error and include an
improvement action, while citations are limited to retrieved source IDs and the supplied simulation
ID. The application injects the AI-generated notice; the model cannot author or replace it.

Prompts omit direct student, submission, course, workflow, retrieval-request, document, and chunk
identifiers. Student answers and retrieved text are explicitly treated as untrusted data. Client and
validation failures are converted to sanitized errors without logging prompt or output content.

Feedback records preserve provider, model, prompt version, simulation references, token usage, and
estimated cost. This keeps initial results and idempotent replays consistent and prepares the data
boundary needed by later research work. A concrete network-backed client remains a future adapter.

## Quality judge and safe fallback

The Block 4 quality judge uses the same provider-neutral structured client with a versioned
`quality-judge-v1` prompt. A reported pass is effective only when correctness, relevance,
grounding, and actionability are each at least 80, no unsupported claims are present, and the
safety score is 100. All other valid results become failures, with deterministic guidance added
when the judge supplies none. Malformed output and provider errors become sanitized technical
evaluations; raw provider output is never included in regeneration prompts or persisted errors.

The pipeline releases a first-pass success immediately. Otherwise, it performs one guided
regeneration and judges that result once. A generation failure, a rejected second attempt, or a
second technical judge failure releases fixed non-assessing fallback content. Feedback and judge
usage are aggregated across every completed call. The accepted attempt or fallback, full evaluation
history, usage, cost, and outcome are reconstructed exactly during idempotent replay.

## Feedback API and student display

The student API uses injected identity and submission-access contracts and fails closed while the
team authentication integration is absent. Inaccessible and missing feedback use the same not-found
response. Student responses contain only processing state, released feedback, or the fixed safe
fallback; judge evaluations, rejected attempts, prompts, provider identity, token usage, and costs
remain internal.

Cited retrieval IDs are mapped to source labels before persistence. Existing legacy records without
labels display their source ID. Students can report released feedback using an allow-listed category
and optional length-limited note. Reports retain only the pseudonymous actor reference and are
idempotent per actor and feedback.

The React feedback feature is reusable and accepts a submission ID plus an injectable API client. It
polls processing workflows, renders Markdown without raw HTML, preserves code blocks, distinguishes
fallback content, and provides accessible retry and reporting controls. The feature remains unmounted
until the canonical task page is delivered.

## Learning events, research, analytics, and audit

Learning events are validated by event type and written through independent transactions. The
browser may submit only task-view and draft-save events; actor, course, task scope, and occurrence
time are server-derived. HMAC pseudonym namespaces prevent an actor pseudonym from being reused as
a submission or audit identifier.

An explicit consent/course eligibility adapter gates research. A bounded metadata-only planning
step writes privacy-safe research and continuation intents atomically with terminal feedback. The
serial worker reconciles that outbox idempotently, creating an agentic measurement plus one pending
same-model baseline measurement only after feedback is durable. The baseline is isolated from
retrieval, simulation, prior feedback, and judge guidance and cannot influence the student-facing
workflow. SQLite is operated with one serial worker that scans feedback recovery, terminal
integration reconciliation, baseline, and continuation queues. A durable singleton ownership
lease rejects a second live worker. Feedback, outbox, research, and continuation claims use leased
execution tokens so stale executors cannot overwrite newer work.

Analytics services consume normalized records and return aggregate contracts with denominators,
sample sizes, units, and missingness. Research exports use the same normalized terminal rows and
must persist their initial audit event before sending bytes. Export serializers accept only typed
opaque input references, typed source metadata, bounded privacy-validated structured output, and
exact pseudonyms; a corrupt legacy row is excluded identically during counting and streaming.

Audit events are append-only, typed, pseudonymous, and keyed for idempotency. Student-path audit
failures are best effort where they cannot share the action transaction; export auditing is strict
and fail-closed. The production database worker always attaches an independent database-backed
best-effort audit mapper to recovered feedback pipelines; a team adapter may override it but cannot
leave worker lifecycle auditing unwired. Request middleware validates correlation UUIDs, emits
security headers, logs route templates, and recursively redacts sensitive structured values.

After terminal feedback is durable, the outbox reconciler creates one continuation job keyed by
workflow UUID. The observer remains a low-latency best-effort path, not the durability guarantee.
The single SQLite worker checkpoints the idempotent progress callback before requesting an opaque
next-task reference from the injected team recommender. Retry and completion mutations are fenced
by execution token and attempt count; expired leases are reclaimable, while stale executors cannot
replace the winner. The row stores no answer, feedback, prompt, or recommendation rationale.

## Integration and deployment boundary

Identity, authorization, submission/task lookup, retrieval, simulation, LLM, research eligibility,
roster, progress, and next-task recommendation remain injected ports. Production readiness fails
closed when a required port, migration, secret, durable worker heartbeat, or database connection is
absent; it never probes an LLM. A singleton database heartbeat allows an API process to observe the
separate SQLite worker without invoking any provider. The runnable worker entrypoint requires an
explicit adapter factory and fails before claiming work if any adapter is unavailable. Liveness
stays independent at
`/api/v1/health`.

The feedback and analytics React modules remain unmounted until the team router and authorization
shell own their routes. The committed OpenAPI document is generated from FastAPI and checked for
drift in CI. See the worker operations and schema documents for the durable contracts.
