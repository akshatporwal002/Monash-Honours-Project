# QuantumLearn Person 4 -- canonical implementation plan

This is the single active implementation and release plan for the Person 4 scope. The
implementation map is historical context only; it does not contain a second active plan.

## Status

- Blocks 0-3: committed before this implementation cycle.
- Blocks 4-10 and standalone Block 11: implemented and verified in the working tree.
- Block 12: implemented and verified, including durable terminal handoff and deterministic E2E.
- Release state: implementation complete; the locked CI workflow reproduces the release gates.
- Final local evidence: 272 backend tests, three migration checks, 43 frontend tests, production
  build, two Playwright E2E scenarios, Ruff check/format, lock checks, and contract-drift checks
  all pass. Python/npm dependency audits report no known vulnerabilities; Gitleaks is enforced by
  CI.

## Summary and execution order

Block 11 is an explicit standalone implementation phase. It executes before Blocks 9-10 because
research exports require durable audit logging before any data is released.

Execution order:

**Blocks 4-5 stabilization -> Block 6 -> Block 7 -> Block 8 -> Block 11 -> Block 9 -> Block 10 -> Block 12**

Blocks 0-3 are already committed. Blocks 4-5 began in the working tree and must pass the
stabilization gate before later work is considered released.

## Block 4-5 stabilization -- finish the current working tree

### Repository and release gate

- Preserve and review all current uncommitted work.
- Remove only verified generated artifacts, including any audit-created
  `backend/quantumlearn.db`.
- Expand `.gitignore`; version the implementation map and this canonical plan.
- Lock Python 3.11 and Node 22 dependencies, replace frontend `"latest"` declarations, and make
  the Ruff rules and version explicit.
- Require backend tests, Ruff check/format, migrations, frontend lint/test/build, and API contract
  checks.

### Workflow correctness

- Add `execution_token`, execution-attempt count, retry time, course/task scope, and persisted
  latency to workflows.
- Fence stage changes, lease renewal, terminal saves, and failure updates using workflow ID plus
  execution token.
- Renew the 300-second lease around stages and bound provider calls to 60 seconds.
- Allow three controlled infrastructure attempts; stale workers must stop without overwriting
  newer work.
- Make expired claims recoverable by POST and the single-concurrency SQLite worker.
- Persist monotonic latency so idempotent replay returns the original measurement.
- Validate requested submission ID against the returned submission, and validate
  task/course/retrieval/simulation scope before prompting.
- Introduce typed retrieval and simulation results distinguishing not-configured, completed,
  empty, and failed states.
- Enforce attempt order, regeneration count, judge-pass/released-feedback alignment, exactly one
  released record, and valid workflow stage/outcome combinations.
- Convert corrupted aggregates and database failures into sanitized errors.

### Judge policy

- Add versioned `quality-policy-v1`.
- Require correctness, relevance, grounding, and actionability scores of at least 80.
- Require safety 100, no unsupported claims, and a model-reported pass.
- Persist the policy version with every evaluation.

### API and frontend closeout

- Generate `Location` from configured routes.
- Bound path IDs and add correlation, `Retry-After`, and `Cache-Control: no-store` headers.
- Replace recursive report retry logic with one race-safe requery.
- Add a configurable frontend API base URL, Vite development proxy, frontend environment example,
  request timeout, credentials and CSRF hooks, runtime response validation, and sanitized errors.
- Bound feedback polling, honor `Retry-After`, handle offline/timeout/abort states, use unique DOM
  IDs, and test hostile Markdown and full accessibility.
- Keep the feedback module unmounted until the canonical task page exists.

## Block 6 -- learning analytics events

### Services and privacy

- Implement strict `LearningEventRecorder` and non-blocking `BestEffortLearningEventSink`
  services.
- Use independent transactions so event failures cannot roll back student actions.
- Generate namespace-separated HMAC-SHA256 `v1` pseudonyms server-side using a secret of at least
  32 bytes.
- Never accept pseudonymous actor IDs, course IDs, or timestamps from the browser.
- Deduplicate using pseudonymous actor, event type, and caller event UUID.
- Return the existing event for exact replay and reject conflicting reuse.

### Typed metadata

- `task_view`: optional bounded source slug.
- `draft_save`: optional nonnegative duration; never draft content.
- `submission`: positive attempt number and optional 0-100 score.
- `feedback_view`: validated or fallback status.
- `completion`: completion status and optional 0-100 score.

### Integration and tests

- Expose authenticated ingestion only for UI-originated task views and draft saves.
- Record submission and completion through trusted backend hooks.
- Record one feedback-view event on the first terminal feedback retrieval per actor.
- Add a fire-and-forget frontend event client containing no answers, drafts, identities, or
  credentials.
- Test all types, concurrency, privacy rejection, cross-course denial, deduplication, and database
  failure isolation.

## Block 7 -- research comparison pipeline

### Services and eligibility

- Add `ResearchEligibilityPolicy`, `ResearchCaseFactory`, `BaselineGenerator`,
  `ResearchJobRepository`, and `ResearchJobDispatcher`.
- Keep research disabled until an explicit consent/course eligibility policy is injected.
- Use workflow ID as the shared case ID.
- Reject changed measurements on exact case replay; a workflow UUID cannot be reused with a
  different agentic measurement.
- For every eligible terminal workflow, persist one agentic record and one pending baseline
  record.
- Schedule the baseline only after student feedback is durable.

### Persistence additions

- Task type and measurement schema version.
- Running state, execution token, lease, processing attempts, and failure category.
- Fallback and comparability flags.
- Usage-completeness flag.
- Retrieval request/hit counts.
- First and final judge status/decision.
- Five normalized scores, unsupported-claim count, and quality-policy version.
- Evaluation-only latency, token usage, and cost.
- Indexes for course/date/condition, task type, provider/model, and decision filters.
- Conservative legacy backfill marked `legacy-v1` and measurement-incomplete.

### Research privacy

- Store pseudonymous actor/submission references.
- Store retrieved source IDs, labels, and relevance scores, but no source chunks.
- Store simulation reference/status, but no raw errors.
- Store generated output and structured judge results, but no prompt or raw answer.
- For fallback, retain the last generated candidate for research and mark the condition as
  fallback.

### Baseline rules

- `baseline-v1` may contain only task information, marking criteria/expected answer, and the
  transient student answer.
- It must not contain retrieval, simulation, prior feedback, judge guidance, attempt/score
  metadata, or regeneration context.
- Use and verify the same provider/base model as agentic generation.
- Require empty source and simulation references.
- Judge once for measurement only; never regenerate or affect student feedback.
- Agentic cost/latency covers the full student-facing pipeline.
- Baseline primary cost/latency covers generation only; its evaluation judge usage is stored
  separately.
- Recover stale jobs through fenced claims without ordinary provider retries.

## Block 8 -- metrics services

Use UTC half-open ranges, a 30-day default, 365-day maximum, nearest-rank P95, and `null` with
denominator zero for undefined metrics.

### Research metrics

- Hallucination rate: valid final judged outputs with unsupported claims divided by valid final
  judged outputs.
- First-pass rate: first-attempt agentic passes divided by all eligible agentic cases.
- Regeneration success: final passes among regenerated cases divided by all regenerated cases.
- Overall pass: final effective passes divided by all eligible cases, per condition.
- Average relevance from valid final scores.
- Retrieval hit rate using attempted retrieval requests and a versioned 0.5 relevance threshold.
- Average and P95 primary latency.
- Average complete token usage and cost.
- Fallback rate.
- Paired agentic-minus-baseline differences using comparable completed pairs only.

### Learning metrics

- Event and unique actor-task view/submission counts.
- Completion rate using distinct completed versus submitted actor-task pairs.
- Average numeric score.
- Total and average attempt counts.
- Feedback-view rate over released workflows, linked by workflow UUID rather than course/task
  approximation.
- Chronological view -> draft -> submission -> feedback -> completion funnel.
- Learners inactive for 14 days, including never-active learners, through a roster adapter.
- Keep detailed inactive learners in the bounded paginated endpoint, not the learning summary.

Every metric result includes schema version, filters, units, numerator, denominator, sample size,
generated timestamp, and excluded/incomplete counts.

## Block 11 -- audit logging and privacy hardening

This block is completed before exports or dashboards are exposed.

### Persistence

- Add append-only `AuditEvent` records containing:
  - UUID.
  - Pseudonymous actor or system actor.
  - Typed action.
  - Success/failure outcome.
  - UTC timestamp.
  - Correlation ID.
  - Opaque resource type and resource UUID.
  - Sanitized failure category.
  - Deduplication key.
- Require failure category only for failed outcomes.
- Index correlation/time, action/time, and actor/time.
- Provide strict `AuditRecorder` and best-effort student-path wrapper.

### Required actions

- `feedback_generation_started`
- `feedback_generation_completed`
- `feedback_judged`
- `feedback_regenerated`
- `feedback_fallback_used`
- `feedback_viewed`
- `feedback_reported`
- `research_export_created`
- `workflow_completed`
- `workflow_failed`

### Event mapping

- Winning claim records generation started.
- Every generation and judge call records its outcome.
- The second attempt records regeneration.
- Fallback release records fallback use.
- First terminal retrieval per actor records feedback viewed.
- Report creation or exact replay records feedback reported.
- Terminal persistence records workflow completed.
- Executor, worker recovery, and POST recovery record terminal workflow failure, including
  exhausted third attempts.
- Export authorization/preparation records export creation before streaming.

### Failure behavior

- Student-path auditing is transactional where practical and otherwise best effort; audit failure
  must not lose feedback or submissions.
- The production worker injects the independent database-backed best-effort audit mapper even when
  the team adapter factory does not provide an override.
- Research export auditing is fail-closed. No export bytes may be sent if the initial audit record
  cannot be stored.
- A stream failure appends a sanitized failed export audit event.

### Privacy

Audit and operational logs must never contain:

- Raw answers or drafts.
- Feedback or report text.
- Prompt contents or provider output.
- Retrieved source chunks.
- Names, emails, or direct student IDs.
- API keys, access tokens, cookies, or CSRF tokens.
- Raw exceptions from external providers.

Use workflow, feedback, report, and export UUIDs as resource references instead of submission IDs.
Add recursive key/value redaction and bounded structured metadata.

### Security and observability

- Generate or validate a correlation ID for every request/job and return it in response headers.
- Log route templates rather than sensitive raw URLs.
- Log only bounded correlation, route/status/stage, latency, and sanitized-category fields.
- Restrict CORS origins, methods, and headers.
- Add CSRF-policy and per-actor rate-limit hooks for mutating routes, generation, reports,
  analytics, and exports.
- Add security headers and disable interactive API documentation in production unless explicitly
  enabled.
- Bound prompt, context, output, list, note, and export sizes.
- Preserve `/health` as liveness and add readiness checking database connectivity, migration head,
  worker health, secrets, and required production adapters without invoking an LLM or creating a
  missing SQLite database.

### Block 11 tests

- Every required action and outcome.
- Audit deduplication and concurrency.
- Strict versus best-effort failure behavior.
- Export fail-closed behavior.
- Database, operational-log, API-response, and export privacy sentinels.
- Recursive sensitive-value attacks.
- Correlation propagation.
- CORS, CSRF, rate-limit, security-header, readiness, and size-limit behavior.
- Confirmation that no provider exception or raw content enters logs.

## Block 9 -- CSV and JSON research exports

- Implement `GET /api/v1/research/exports?format=csv|json`.
- Support course, UTC date range, experimental condition, task type, model, and judge-decision
  filters.
- Apply authorization-scoped course intersection and export only terminal rows.
- Use a stable versioned serializer and CSV column order.
- Include the required brief fields plus task type, scores, unsupported-claim count, status,
  failure category, fallback, comparability, usage completeness, and measurement version.
- Export exact `v1_<64 lowercase hex>` pseudonymous references only.
- Encode nested fields as canonical JSON, timestamps as UTC ISO-8601, and costs as fixed Decimal
  strings.
- Neutralize spreadsheet-formula cells, including whitespace/control-prefixed formulas, reject
  unsanitized persisted failure categories, and return safe filenames with
  `Cache-Control: no-store`.
- Use a `quantumlearn.research-export.v1` JSON envelope.
- Stream in batches of 1,000 with a configurable 100,000-row synchronous cap.
- Require the Block 11 export audit record before streaming.
- Test golden files, escaping, formula injection, filters, authorization, row limits, audit
  failures, and forbidden-field absence.

## Block 10 -- analytics APIs and route-ready dashboard

### Backend endpoints

- `GET /api/v1/analytics/learning`
- `GET /api/v1/analytics/research`
- `GET /api/v1/analytics/filter-options`
- `GET /api/v1/analytics/inactive-learners`
- Paginated inactive-learner aggregates with a maximum page size of 100.

### Frontend

- Build route-ready `AnalyticsFilters`, learning/research summary cards, engagement funnel, judge
  results, latency/cost summaries, paired comparison table, inactive learners, and export
  controls.
- Consume aggregate endpoints only.
- Use semantic tables and lightweight CSS/native SVG with text equivalents.
- Show denominators and sample sizes.
- Handle loading, permission, error, no-data, and partial-measurement states.
- Abort stale requests and expose filter-state callbacks for the future router.
- Keep the dashboard unmounted except in the E2E harness.
- Test filtering, null results, pagination, request cancellation, export downloads, responsive
  layout, keyboard use, reduced motion, contrast, and Axe.

## Block 12 -- integration and end-to-end validation

### Adapters

- Identity/authentication.
- Submission ownership and course authorization.
- Task/submission lookup.
- Retrieval and simulation.
- Structured LLM provider with explicit usage-completeness reporting.
- Research eligibility and roster access.
- Progress persistence and next-task recommendation.
- Job dispatch and pseudonymization.

### Continuation and durable terminal handoff

- Notify progress once after terminal feedback, idempotently by workflow ID.
- Request an opaque next-task reference from the team recommender.
- Retry continuation through the worker without withholding released feedback.
- Return continuation through the owning learning-workflow integration without implementing
  recommendation logic here.
- Atomically create privacy-safe terminal-integration outbox work with terminal feedback so a
  post-commit observer failure or process crash cannot permanently lose an eligible research pair
  or continuation.
- Fence outbox claims, retries, completion, and exhausted-lease failure using an execution token.

### E2E harness

- Use built React modules, FastAPI, an Alembic-migrated temporary SQLite database, and
  deterministic adapters.
- Cover all ten brief scenarios, authorization denial, reporting, one feedback-view event,
  research pairing, baseline isolation, dashboards, audited export, worker restart, stale-worker
  fencing, progress idempotency, next-task handoff, and privacy sentinels.
- Never call a real provider during automated tests.

### Release gate

- Generate frontend contracts from OpenAPI and fail on drift.
- Run locked backend tests, Ruff check/format, migration clean/legacy/round-trip checks, frontend
  lint/test/build, Playwright, full and production dependency audits, and secret scanning in CI.
- Update README, architecture, API/event/research/export/audit schemas, methodology, environment
  examples, worker instructions, requirement traceability, and this canonical plan status.

## Locked defaults

- Adapter-complete implementation; missing team systems fail closed.
- Route-ready feedback and analytics modules remain unmounted.
- SQLite with one database-backed worker.
- Research disabled without explicit eligibility/consent.
- HMAC-SHA256 `v1` pseudonyms with a 32-byte minimum secret.
- Quality thresholds of 80/80/80/80, safety 100, and zero unsupported claims.
- 300-second lease, 60-second provider timeout, and three infrastructure attempts.
- UTC half-open ranges, 30-day default, 365-day maximum, 14-day inactivity, 0.5 retrieval
  threshold, and nearest-rank P95.
- One baseline generation and one evaluation-only judge call.
- Paired comparisons use `agentic - baseline`.
- Export cap of 100,000 rows.

## Definition of done

The implementation is complete only when the final tree passes:

1. Locked Python 3.11 dependency and lock checks.
2. Ruff check and format check.
3. The complete backend test suite.
4. Clean, legacy, downgrade/upgrade, and Alembic model-parity migration checks.
5. OpenAPI and generated frontend-contract drift checks.
6. Locked Node 22 installation, frontend lint, unit/accessibility tests, and production build.
7. Real built-React -> FastAPI -> migrated-SQLite Playwright E2E with deterministic adapters.
8. Python and npm full/production dependency audits.
9. Secret scanning in CI and local privacy-sentinel scans.
10. Removal of verified generated artifacts and a final worktree review.
