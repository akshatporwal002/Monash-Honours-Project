# 007: Diagnose and repair the assessed feedback pipeline

Status: approved for sequential implementation

Owner: Codex implementation agent; policy owners remain listed below

Created: 2026-08-21

Target branch: `arv-person-a-assessment`

Evidence snapshot: commit `7ef9082`

## Outcome

Restore feedback for assessed submissions without reintroducing numeric marks.
Feedback must use the frozen response, approved assessment context, and authorised evidence.
It must remain separate from the formal learner result.

The repaired flow must:

- Preserve the accepted response when any provider or worker fails.
- Keep system faults out of the learner `PASS` and `INCOMPLETE` namespace.
- Produce learning feedback from criteria evidence, not percentage bands.
- Review generated feedback under the separate `APPROVED` or `REJECTED` namespace.
- Regenerate once, then release a safe fallback after another rejection.
- Store complete response, source, prompt, model, rule, and judge lineage.
- Show pending, available, fallback, and failed states truthfully in the UI.
- Continue safely after an API restart through the worker.

This plan does not approve unresolved assessment or release policy. It does not infer formal
results from legacy scores. The user authorised sequential implementation on 2026-08-21. Commits,
pushes, and pull-request actions still need separate instruction.

## Source evidence

| Claim or rule | Evidence | Requirement |
| --- | --- | --- |
| Assessed submissions intentionally store a null score. | `src-main/backend/app/services/lms.py:672-700`, `LmsService.submit` | AT1, AT2, AC19 |
| The feedback adapter casts that null score to `float`. | `src-main/backend/app/services/feedback/runtime.py:69-77`, `LmsSubmissionProvider.get_submission` | FR15, FR18 |
| The feedback contract already permits a null score. | `src-main/backend/app/schemas/feedback.py:123-131`, `SubmissionContext` | FR15 |
| The local generator still classifies responses from score bands. | `src-main/backend/app/services/local_ai.py:29-64`, `LocalFeedbackGenerator.generate` | FR16, AT19 |
| Unknown feedback exceptions are marked as retryable infrastructure faults. | `src-main/backend/app/services/feedback/application.py:196-208`, `InProcessFeedbackExecutor._failure` | FR18, NFR20 |
| A failed feedback workflow can execute three times. | `src-main/backend/app/services/feedback/repository.py:48`, `:314-405`, `:579-634` | FR18, NFR20 |
| The production evaluation route injects unavailable evaluator ports. | `src-main/backend/app/api/routes/assessment_evaluation.py:40-49` | BP7, AT20 |
| The criterion evaluation port always raises a configuration error. | `src-main/backend/app/services/assessment/evaluation.py:91-102` | BP7, NFR20 |
| No frontend source calls the assessment evaluation endpoint. | Current `rg` scan for `assessment/attempts` and evaluation calls under `src-main/frontend/src` | FR28, BP7 |
| Feedback starts after LMS submission through a background task. | `src-main/backend/app/api/routes/lms.py:481-519` | FR15, FR18 |
| The UI says feedback is ready before the job reaches a terminal state. | `src-main/frontend/src/components/TaskView.tsx:261-278` | FR15, NFR4 |
| The UI renders the feedback panel next to the saved assessment response. | `src-main/frontend/src/components/TaskView.tsx:542-555` | FR12, FR15 |
| The old Quality Judge enum still uses `PASS` and `FAIL`. | `src-main/backend/app/models/enums.py:52-54` | FR17, AT20 |
| The current quality policy is a score threshold named `quality-policy-v1`. | `src-main/backend/app/schemas/feedback.py:54-55` | FR17, NFR14, NFR28 |
| Feedback must link response, source, agent, and judge records. | `docs/01-implementation-requirements.md:311-340` | FR15 to FR18 |
| Quality Judge decisions must be separate from learner results. | `docs/03-codex-implementation-work-order.md:155-158` | FR17, AT20 |
| The required feedback flow includes one regeneration and a safe fallback. | `docs/03-codex-implementation-work-order.md:339-354` | FR18 |
| Feedback for an incomplete result must use `INCOMPLETE`, not `FAIL`. | `docs/02-pass-incomplete-bloom-assessment-spec.md:875-881` | AT19, AT20 |
| Evidence capture and learner-model services exist but lack live production callers. | Current usage scan for `EvidenceService`, `TrustedEvidenceCaptureAdapter`, and `LearnerModelBuildService` | FR19, FR29, FR30 |
| Only six requirement-named task types are registered. | `src-main/backend/app/models/enums.py:77-89`, `src-main/backend/app/services/task_types.py:304-320` | FR9, PD4 |
| Prediction, reflection, and transfer tasks are required. | `docs/01-implementation-requirements.md:268-283` | FR9 |
| Local startup launches only backend and frontend processes. | `start-quantumlearn.ps1:80-90`, `:112-138` | NFR10, NFR20 |
| The local launcher checks `/health`, not `/ready`. | `start-quantumlearn.ps1:115-137` | NFR10, NFR20 |
| The gap matrix uses an old August 14 baseline. | `docs/learnlens/implementation-gap-matrix.md:7-11` | Phase 0 gate |
| Several product and release decisions remain pending. | `docs/learnlens/known-limits-and-deferred-decisions.md:37-48`, `:78-86` | D-01, D-04 to D-10 |

## Current-state trace

1. The learner submits through `TaskView.save(true)`.
2. The LMS route saves the response before starting feedback.
3. An assessed task freezes assessment version references.
4. That path stores `SubmissionAttempt.score = None` by design.
5. The route starts the feedback application in a background task.
6. `LmsSubmissionProvider` loads the accepted attempt.
7. The provider executes `float(attempt.score)`.
8. Python raises a `TypeError` before retrieval, simulation, generation, or judging.
9. The executor records `unexpected_infrastructure_error` as retryable.
10. The same deterministic code path can fail three times.
11. The learner sees retry or failed feedback state after the earlier ready message.

The formal assessment path is separate but incomplete:

1. Submission creates the frozen assessment attempt and response data.
2. Submission does not start formal assessment evaluation.
3. The frontend does not call the evaluation endpoint.
4. A direct endpoint call reaches an unavailable criterion evaluator.
5. No criterion outcome or provisional result reaches feedback generation.

### Reproduced failure

The production adapter was called with an assessed attempt whose score was null.
It failed with:

```text
TypeError: float() argument must be a string or a real number, not 'NoneType'
```

The traceback ended at `app/services/feedback/runtime.py:76`.

### Why existing tests missed it

The focused feedback, LMS, and assessment suites all passed. The full backend suite also passed.
No test crosses this complete production path:

```text
assessed submit
  -> null score
  -> production LmsSubmissionProvider
  -> feedback executor
  -> terminal feedback response
  -> learner UI
```

The browser tests use demo or test-backed data. They do not prove this production adapter path.

## Confirmed diagnosis

### Critical runtime defect

`LmsSubmissionProvider.get_submission` violates its own nullable schema. The model permits
`SubmissionContext.score` to be null, but the adapter forces it into a float.

### Architectural mismatch

The existing feedback pipeline belongs to the older numeric-score flow. The new assessment flow
deliberately removes that score. Feedback still depends on it for response classification.

Changing `float(attempt.score)` to `float(attempt.score or 0)` is not a valid repair. It would call
every assessed response incorrect. It could also turn a missing evaluator result into learner blame.

### Missing upstream result context

The feedback system cannot use formal assessment evidence because production evaluation is not
configured or orchestrated. The feedback contract also lacks the frozen assessment fields required
for safe criteria-based feedback.

## Repository-wide finding inventory

| Priority | Status | Finding | Effect |
| --- | --- | --- | --- |
| Critical | CONFIRMED | Null assessed score crashes the production feedback adapter. | No assessed feedback reaches retrieval or generation. |
| Critical | MISSING | Production criterion evaluation and quality review providers are unavailable. | Formal assessed evaluation returns a service fault. |
| Critical | MISSING | Submission does not orchestrate durable assessment evaluation. | Feedback has no criteria outcome or provisional context. |
| High | CONFLICTING | Feedback generation still uses percentage bands. | It cannot describe binary criteria evidence safely. |
| High | CONFLICTING | Quality Judge still uses `PASS` and `FAIL`. | Judge results can be confused with learner results. |
| High | PARTIAL | Quality checks cover a narrower score policy. | Bloom, evidence, leakage, access, bias, and reflection checks remain incomplete. |
| High | PARTIAL | Feedback provenance lacks frozen assessment and evidence lineage. | Auditors cannot reconstruct the exact decision context. |
| High | MISSING | Human escalation has no owned queue and lifecycle. | Repeated rejection or unsafe output has no managed resolution path. |
| High | PARTIAL | Evidence and learner-model foundations are isolated from the live flow. | Submission, revision, feedback use, and inference history remain disconnected. |
| High | CONFLICTING | Numeric score fields remain across LMS, analytics, dashboards, and gamification. | The old and new assessment models remain visible together. |
| High | MISSING | Learner result, review request, and reassessment are incomplete. | The full formal result lifecycle is unavailable. |
| Medium | PARTIAL | Qiskit runs are not stored as versioned simulation evidence. | Feedback cannot prove engine, input, output, and prediction lineage. |
| Medium | MISSING | Prediction, reflection, and transfer task types are absent. | FR9 and the full Assess As You Learn cycle remain incomplete. |
| Medium | MISSING | Adaptation and misconception flows are not wired to production evidence. | Next-step choices lack live evidence and correction history. |
| Medium | MISSING | Research consent, withdrawal, field approval, and missing-data rules are incomplete. | Live research use remains blocked. |
| Medium | CONFIRMED | The UI declares feedback ready before completion. | Learners receive a false success message. |
| Medium | CONFIRMED | Local startup omits the durable worker and readiness probe. | Restart recovery is unavailable and startup can be overstated. |
| Low | STALE | The implementation gap matrix predates current assessment foundations. | Planning status cannot be treated as current proof. |
| Low | PARTIAL | Legacy student routes and score services remain unmounted or unused. | They create maintenance and accidental reuse risk. |
| Low | CONFIRMED | The production frontend chunk is 643.27 kB. | Vite reports a chunk-size warning above 500 kB. |
| Release | UNVERIFIED | Native Safari, screen reader, load, cost, evaluator, hosted, and usability proof is missing. | Pilot and release claims remain blocked. |

## Proposed design

### Separate feedback from formal assessment authority

Feedback may read an immutable assessment summary. It must not create, confirm, override, or
display a formal result. Only the assessment service may create a provisional decision. Only an
authorised assessor may perform the configured formal action.

System faults must produce `UNDER_REVIEW`, safe fallback, or retry state. They must never produce
learner `INCOMPLETE`.

### Add a versioned assessed-feedback input

Create a strict input contract containing:

- Course, learner, task, attempt, and response-version references.
- Task-form and assessment-definition version references.
- Target Bloom process and knowledge dimension.
- Mandatory criteria, pass rule, and evidence-sufficiency rule versions.
- Permitted tools and instructional support.
- Access conditions and equivalent-format proof.
- Approved source and retrieval references with versions.
- Simulation evidence references with engine and input versions.
- Criterion outcomes with supporting and missing evidence references.
- Provisional result summary when policy permits its use.
- Stable reason code, evaluator version, prompt version, and quality-policy version.

Protected learner content must remain in authorised response or evidence storage. General logs,
analytics, audit payloads, and research records must keep references and safe metadata only.

### Use durable orchestration

Accepted work must be committed before evaluation begins. A durable job should then:

1. Resolve the frozen response and task context.
2. Gather authorised source and simulation evidence.
3. Run criterion evaluation when configured.
4. Keep evaluation advisory or under review while D-07 is pending.
5. Generate learning feedback from criteria evidence.
6. Run Quality Policy v2.
7. Regenerate once after rejection.
8. Release a safe fallback after another rejection or technical fault.
9. Record provenance, costs, audit events, and escalation state.
10. Trigger evidence capture and learner-model work through narrow ports.

Every stage must be idempotent and fenced. Duplicate API calls or worker restarts must not create
duplicate results, feedback, evidence, or escalation records.

## Step 1: Lock the regression into integration tests

Files:

- `src-main/backend/tests/test_assessed_feedback_integration.py`
- `src-main/backend/app/services/feedback/runtime.py`

Changes:

- [x] Add a production-adapter test with an assessed attempt whose score is null.
- [x] Preserve the valid null score in `SubmissionContext` without assigning learner meaning.
- [x] Prove the response remains stored when feedback fails.
- [x] Prove the production submission adapter can reach a terminal feedback response.

Edge and failure cases:

- Null legacy score, missing attempt, missing task, stale version, duplicate start, expired lease,
  worker restart, provider timeout, and cross-course access.

**Acceptance:** The new backend test reproduces the current `float(None)` failure before repair,
then passes through the production submission adapter to a terminal feedback response.

Implementation verification (2026-08-21): `PASS`. The new tests first reproduced two failures at
`app/services/feedback/runtime.py:76`. After the nullable adapter repair, all three regression tests
passed. The affected feedback, LMS, and assessment selection reported 68 passed in 24.68 seconds.
Targeted Ruff check and format check passed. The first local test attempt was `NOT RUN` against the
code because the global pytest temp folder denied access. The recorded rerun used a repository-local
`--basetemp` and reached the intended code path.

## Step 2: Replace score-based feedback input with frozen assessment context

Files:

- `src-main/backend/app/schemas/feedback.py`
- `src-main/backend/app/services/feedback/contracts.py`
- `src-main/backend/app/services/feedback/runtime.py`
- `src-main/backend/app/services/feedback/context.py`
- `src-main/backend/app/services/feedback/prompt.py`
- `src-main/backend/app/services/feedback/agent.py`
- `src-main/backend/app/services/feedback/errors.py`
- `src-main/backend/app/services/feedback/__init__.py`
- New `src-main/backend/app/services/assessment/feedback_context.py`
- New `src-main/backend/tests/test_assessment_feedback_context.py`

Changes:

- [x] Remove the runtime requirement for a numeric score.
- [x] Add a versioned assessed-feedback input without importing assessment ORM models.
- [x] Resolve immutable response, task-form, criteria, source, and evidence references.
- [x] Reject missing, stale, cross-course, or mismatched references before generation.
- [x] Keep formal result mutation outside all feedback modules.
- [x] Release only safe fallback for assessed context until Step 4 replaces legacy classification.
- [x] Check OpenAPI and frontend contracts for drift. No public generated file changed.

Edge and failure cases:

- A null score is valid. Missing assessment context is a safe review state. It is not an incorrect
  learner response. Version conflicts fail closed and preserve the accepted response. The temporary
  generation gate must never classify the response or call the legacy generator.

**Acceptance:** An assessed submission reaches context collection without a score. Contract and
dependency tests prove that feedback cannot write a formal result.

Implementation verification (2026-08-21): `PASS`. The versioned input resolves the accepted
response, approved task form, assessment versions, criteria, source lineage, and criterion evidence.
It fails closed for missing, stale, cross-course, and mismatched references. The feedback package
has no assessment ORM, evaluation, review, or formal-result writer imports. Assessed input reaches
context collection with a null score, then returns the safe fallback without calling the legacy
score classifier. The focused gate reported 9 passed in 3.82 seconds. The affected feedback, LMS,
and assessment suite reported 134 passed in 27.90 seconds. The full backend suite reported 601
passed in 128.94 seconds. Targeted Ruff check and format check passed. OpenAPI and generated
frontend contract drift checks passed. Criteria-based assessed generation remains blocked until
Step 4, as planned.

## Step 3: Configure evaluation and durable post-submit orchestration

Files:

- `src-main/backend/app/models/assessment.py`
- `src-main/backend/app/models/__init__.py`
- `src-main/backend/app/core/readiness.py`
- New `src-main/backend/migrations/versions/20260821_0022_assessment_evaluation_jobs.py`
- `src-main/backend/app/api/assessment_dependencies.py`
- `src-main/backend/app/api/routes/assessment_evaluation.py`
- `src-main/backend/app/services/assessment/evaluation.py`
- `src-main/backend/app/services/assessment/submissions.py`
- New `src-main/backend/app/services/assessment/runtime.py`
- New `src-main/backend/app/services/assessment/jobs.py`
- `src-main/backend/app/api/routes/lms.py`
- `src-main/backend/app/worker.py`
- `src-main/backend/tests/test_assessment_submissions.py`
- `src-main/backend/tests/test_migrations.py`
- New `src-main/backend/tests/test_assessment_evaluation_jobs.py`

Validation-only coverage:

- `src-main/backend/tests/test_criterion_evaluation.py`
- `src-main/backend/tests/test_assessment_evaluation_api.py`
- `src-main/backend/tests/test_database_worker.py`
- `src-main/backend/tests/test_lms_core_api.py`
- `src-main/backend/tests/test_person4_e2e.py`
- `src-main/backend/tests/test_deployment_runtime.py`
- `src-main/backend/tests/test_worker_health.py`

Changes:

- [x] Replace unavailable ports with a configured frozen-response rules adapter.
- [x] Start evaluation through durable work after the accepted response commits.
- [x] Keep repeated execution deterministic under frozen versions.
- [x] Keep D-07 evaluation advisory until release evidence and approval exist.
- [x] Record safe failure and human-review states without changing learner results.
- [x] Prevent duplicate work across API background tasks and worker recovery.

Edge and failure cases:

- Provider unavailable, malformed response, low confidence, version conflict, lease loss, duplicate
  request, partial commit, and worker restart.

**Acceptance:** A stored assessed response creates one durable evaluation job. A configured test
adapter produces one provisional record. An unavailable adapter leaves the response under review.

Grounding update (2026-08-21): `AssessmentAttempt.PENDING` has no claim token, lease, retry time,
or processing count. It cannot prevent an API background task and worker recovery from evaluating
the same response at once. Existing continuation jobs are tied to terminal feedback workflows and
cannot safely represent assessment work. Step 3 therefore needs its own assessment evaluation job,
forward migration, fenced repository, and worker pass. This is required by the existing acceptance
line and AT22. It does not change assessment policy or expose provisional results to learners.

Implementation verification (2026-08-21): `PASS`. Assessed submission now stores one pending
evaluation job in the same commit as its frozen attempt. API background work and worker recovery
claim that job through a compare-and-swap token and lease. Expired final claims move to
`review_required`. Unsupported human, mixed, or validated-AI criteria also move to human review and
create no learner result. Only approved deterministic rule criteria use the production adapter.
Advisory evaluator output cannot create a provisional decision while D-07 remains pending. The
focused orchestration gate reported 10 passed, then 7 passed after lease and advisory cases were
added. The final affected selection reported 96 passed in 55.80 seconds. The complete migration
suite reported 27 passed in 25.79 seconds, including pending-job backfill, repeat safety, and
manifest-preserving downgrade refusal. The first full backend run reported 607 passed and two
readiness-pin failures. Updating the deployment migration pin fixed both, and the focused rerun
reported 15 passed. The final full backend run reported 609 passed in 174.72 seconds. Repository-wide
Ruff check passed, all 299 Python files passed the format check, Alembic reports one head at
`20260821_0022`, and both generated-contract drift checks passed. D-01 learner visibility, D-07 AI
release approval, and Step 10 local worker launch remain unchanged and pending.

## Step 4: Generate criteria-based feedback and truthful UI states

Files:

- `src-main/backend/app/services/local_ai.py`
- `src-main/backend/app/services/llm.py`
- `src-main/backend/app/services/feedback/prompt.py`
- `src-main/backend/app/services/feedback/pipeline.py`
- `src-main/frontend/src/components/TaskView.tsx`
- `src-main/frontend/src/features/feedback/`
- `src-main/frontend/e2e/assessed-feedback.e2e.ts`
- Related backend and frontend tests

Changes:

- [ ] Replace score bands with criterion evidence and missing-evidence reasoning.
- [ ] Give the least revealing useful support and a clear next action.
- [ ] Use `PASS` or `INCOMPLETE` only when an authorised result context permits it.
- [ ] Use learning-only wording while the formal result remains under review.
- [ ] Show preparing, available, safe fallback, retryable failure, and terminal failure states.
- [ ] Add a browser test that submits a real assessed response and waits for terminal feedback.
- [ ] Prove the UI never claims ready while the workflow is pending.
- [ ] Keep keyboard, focus, zoom, and screen-reader behaviour covered.

Edge and failure cases:

- No approved source, no simulation evidence, conflicting evidence, unsafe prompt content, long
  answers, code answers, circuit answers, and a withheld formal result.

**Acceptance:** Tests prove that a null score never selects the incorrect branch. The learner UI
does not show ready until approved feedback or the safe fallback is available.

## Step 5: Migrate Quality Judge policy and namespace

Files:

- `src-main/backend/app/models/enums.py`
- `src-main/backend/app/domain/assessment.py`
- `src-main/backend/app/schemas/feedback.py`
- `src-main/backend/app/services/feedback/judge.py`
- New `src-main/backend/app/services/feedback/quality_policy.py`
- New versioned safety fixtures under `src-main/backend/tests/fixtures`
- New forward migration under `src-main/backend/migrations/versions`
- `src-main/frontend/src/api/generated.ts`

Changes:

- [ ] Use `APPROVED` and `REJECTED` for new Quality Judge records.
- [ ] Keep old `pass` and `fail` records readable during the approved compatibility window.
- [ ] Never translate an old judge value into a learner assessment result.
- [ ] Check factual grounding, Bloom alignment, criteria use, evidence sufficiency, answer leakage,
  access, bias, unsupported diagnosis, reflection, and independent work.
- [ ] Store policy, prompt, model, retrieval, and source versions.
- [ ] Add adversarial and safety regression cases.

Edge and failure cases:

- Existing rows, mixed client versions, unknown old values, rejected first generation, rejected
  regeneration, malformed judge output, and unavailable judge provider.

**Acceptance:** Migration round-trip tests pass. New records use only `APPROVED` or `REJECTED`.
AT20 proves judge values cannot enter the learner-result namespace.

## Step 6: Complete provenance, fallback, and human escalation

Files:

- `src-main/backend/app/models/persistence.py`
- `src-main/backend/app/services/feedback/repository.py`
- `src-main/backend/app/services/feedback/application.py`
- New escalation models, schemas, services, and routes
- New forward migration under `src-main/backend/migrations/versions`
- Related audit, API, and repository tests

Changes:

- [ ] Store response, source, retrieval, simulation, prompt, model, rule, cost, and judge references.
- [ ] Keep both rejected generations and the released fallback.
- [ ] Distinguish transient provider faults from deterministic programming faults.
- [ ] Prove deterministic programming faults are not retried as transient faults.
- [ ] Add escalation state, owner, severity, due target, reason, resolution, and audit history.
- [ ] Keep escalation content course-scoped and privacy-minimal.
- [ ] Hold service-target claims until D-09 is approved.

Edge and failure cases:

- Concurrent escalation, duplicate fallback, resolver mismatch, closed-course access, removed owner,
  missing due target, and redacted learner content.

**Acceptance:** Repository tests reconstruct one feedback decision from immutable references. A
second rejection creates one fallback and one auditable escalation record.

## Step 7: Connect evidence and learner-model foundations to the live flow

Files:

- `src-main/backend/app/services/evidence/`
- `src-main/backend/app/services/learner_model/`
- `src-main/backend/app/services/continuation/`
- New narrow dependency wiring and routes
- Related evidence, privacy, learner-model, and continuation tests

Changes:

- [ ] Capture accepted response, revision, feedback view, reflection, and transfer evidence.
- [ ] Preserve old evidence after every revision.
- [ ] Build learner-model snapshots only from linked evidence.
- [ ] Store uncertainty, model version, prior state, and supporting and contradicting references.
- [ ] Keep evidence, inference, research, progress, and formal assessment separate.
- [ ] Permit learner annotation and educator correction through authorised paths.

Edge and failure cases:

- Duplicate events, late events, stale snapshots, denied access, missing artefacts, contradictory
  evidence, correction history, and builder failure.

**Acceptance:** One live assessed-feedback episode is visible in order. Old response evidence
remains. Each inference links to evidence and uncertainty and cannot change the formal result.

## Step 8: Complete task and simulation evidence support

Files:

- `src-main/backend/app/services/task_types.py`
- `src-main/backend/app/models/enums.py`
- New task contracts for prediction, reflection, and transfer
- `src-main/backend/app/services/quantum.py`
- New simulation models, services, schemas, and migration
- Related frontend task controls and tests

Changes:

- [ ] Add typed prediction, reflection, and transfer task handlers.
- [ ] Add accessible frontend controls and validation for each type.
- [ ] Store simulation input, output, engine version, seed, shots, timing, and failure state.
- [ ] Link prediction evidence before revealing simulation results.
- [ ] Keep accessible text evidence equivalent to the visual circuit result.
- [ ] Enforce resource and execution-time bounds.

Edge and failure cases:

- Unsupported gates, oversized circuits, timeouts, missing engine, invalid prediction ordering,
  keyboard-only use, and non-visual output.

**Acceptance:** FR9 tests cover all required task types. Simulation tests reconstruct a run from
stored versions and prove prediction capture occurred before result reveal.

## Step 9: Retire legacy score projections and complete result lifecycle

Files:

- `src-main/backend/app/services/lms.py`
- `src-main/backend/app/schemas/lms.py`
- `src-main/backend/app/services/analytics/`
- `src-main/backend/app/services/gamification.py`
- Student, educator, analytics, and assessment frontend views
- Forward compatibility migrations and contract updates

Changes:

- [ ] Remove numeric marks from new assessment API responses and UI projections.
- [ ] Exclude legacy score fields from new progress, analytics, learner-model, and gamification logic.
- [ ] Keep legacy records readable until D-10 sets the retirement window.
- [ ] Complete learner result, review request, correction, and reassessment flows after approval.
- [ ] Keep result visibility behind D-01 and reassessment behind D-06.
- [ ] Preserve assessor actions and all earlier decisions.

Edge and failure cases:

- Mixed old and new attempts, old clients, hidden provisional results, overridden results, voided
  results, equivalent reassessment forms, and current-result selection.

**Acceptance:** New assessed API payloads contain no numeric marks. AT1 to AT3 and AT15 to AT19
pass. Legacy records remain readable without inferring `PASS`.

## Step 10: Repair local worker startup and readiness checks

Files:

- `start-quantumlearn.ps1`
- `README.md`
- Local operations documentation and startup checks

Changes:

- [ ] Start `quantumlearn-worker` with backend and frontend processes.
- [ ] Track and report all three process IDs.
- [ ] Check `/api/v1/ready` and the frontend before reporting ready.
- [ ] Fail clearly when the worker or a required dependency is unavailable.
- [ ] Document safe shutdown and port verification.

Edge and failure cases:

- Worker exits early, backend health passes while readiness fails, occupied ports, repeated launch,
  missing dependencies, and partial shutdown.

**Acceptance:** The launcher reports ready only while frontend, API readiness, and worker are live.
Stopping the launcher leaves no tracked service running.

## Step 11: Refresh the gap matrix and complete release evidence

Files:

- `docs/learnlens/implementation-gap-matrix.md`
- `docs/learnlens/known-limits-and-deferred-decisions.md`
- `src-main/docs/requirements-traceability.md`
- Release evidence under `src-main/docs/release`

Changes:

- [ ] Re-audit every matrix row against the implementation head.
- [ ] Cite current files, tests, commands, and remaining gaps.
- [ ] Keep missing checks labelled `NOT RUN`, `UNVERIFIED`, or `BLOCKED`.
- [ ] Record evaluator validation, load, cost, hosted, browser, and access evidence separately.
- [ ] Do not claim native Safari from Playwright WebKit.
- [ ] Do not claim screen-reader support from Axe alone.

Edge and failure cases:

- Stale evidence, code changes after verdicts, partial browser coverage, unavailable external systems,
  and unresolved product policy.

**Acceptance:** The matrix names the current commit and evidence date. Its validator passes. Every
release claim links to current proof or a named blocker.

## Current verification baseline

Evidence captured on 2026-08-21 at commit `7ef9082`:

| Check | Result | Limit |
| --- | --- | --- |
| Direct production feedback-adapter reproduction | FAIL with `float(None)` `TypeError` | Confirms the assessed feedback defect. |
| Focused feedback, LMS, and assessment tests | 65 passed in 26.43 seconds | Missing production assessed-feedback integration case. |
| Full backend test suite | 592 passed in 200.19 seconds | Coverage threshold was not measured in this run. |
| Ruff lint | PASS | Local current-head check. |
| Ruff format check | PASS, 292 files | Local current-head check. |
| OpenAPI drift | PASS | Export is current. |
| Generated frontend contract drift | PASS | Generated TypeScript is current. |
| Frontend unit and access tests | 173 passed across 51 files | JSDOM printed non-failing canvas warnings. |
| Frontend lint | PASS | Local current-head check. |
| Frontend production build | PASS | Vite warned about a 643.27 kB main chunk. |
| Browser E2E | 33 passed, 11 failed in 6.6 minutes | All failures occurred during Firefox setup. |
| Chrome, Edge, and WebKit browser projects | PASS | Does not prove native Safari. |
| Firefox browser project | 11 setup failures | GPU and tab subprocess creation failed before test bodies ran. |
| Git worktree after diagnosis | Clean | No implementation files changed. |

The following release checks were `NOT RUN`:

- The CI backend coverage command with `--cov-fail-under=80`.
- The standalone Alembic clean, legacy, and round-trip job.
- Python and npm dependency audits.
- Gitleaks.
- Production load, latency, availability, and cost tests.
- External evaluator agreement and fairness validation.
- Native Safari verification.
- Manual screen-reader verification.
- Hosted TLS and deployment verification.
- Learner, educator, and assessor usability studies.

## Full verification

Run targeted tests with the step that introduces each behaviour. Then run the repository release
gate from `.github/workflows/quality.yml`.

Backend commands from `src-main/backend`:

```powershell
$env:APP_ENV = 'test'
$env:DATABASE_URL = 'sqlite:///./ci-tests.db'
$env:LEARNING_EVENT_PSEUDONYM_SECRET = 'ci-only-pseudonym-secret-32-bytes-minimum'
uv lock --check
uv sync --frozen --all-extras
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pytest --cov=app.services --cov-report=term-missing --cov-fail-under=80
uv run --frozen pytest tests/test_migrations.py
uv run --frozen python scripts/export_openapi.py --check
uv run --frozen python scripts/generate_frontend_contracts.py --check
uv run --frozen --with pip-audit==2.9.0 pip-audit --skip-editable
```

Frontend commands from `src-main/frontend`:

```powershell
npm ci
npm run lint
npm test
npm run build
npx playwright install --with-deps chrome msedge firefox webkit
npm run test:e2e
npm audit --audit-level=high
npm audit --omit=dev --audit-level=high
```

Security and external proof:

- Run the configured Gitleaks action with full Git history.
- Run load, cost, availability, and recovery checks against the release candidate.
- Run native Safari separately from WebKit automation.
- Complete keyboard, focus, zoom, contrast, and named screen-reader checks.
- Validate evaluator agreement and fairness against the approved dataset and thresholds.

Every code change invalidates earlier local-review verdicts. Obtain fresh Test Judge, Code Reviewer,
and Code Quality Reviewer results after the final diff and full test evidence exist.

## Migration and rollback

Use forward migrations only.

- Preserve old Quality Judge values as legacy data.
- Never map old judge values or numeric scores into learner `PASS`.
- Add new provenance, escalation, and simulation records without overwriting old workflow rows.
- Count old, migrated, new, orphaned, and rejected records before and after each migration.
- Keep generated clients compatible for the D-10 window.
- Roll back behaviour through versioned adapters or feature controls, not destructive data removal.
- Keep accepted learner responses readable throughout deployment and recovery.

The exact legacy shutdown date is `BLOCKED` by D-10. Reassessment activation is `BLOCKED` by D-06.

## Risks and controls

| Risk | Impact | Control and proof |
| --- | --- | --- |
| Null or missing assessment context is treated as learner error. | False `INCOMPLETE` or harmful feedback. | Use under-review state and explicit system-fault tests. |
| Judge and learner result namespaces mix. | A quality rejection becomes a learner result. | Separate enums, dependency tests, migration checks, and AT20. |
| A quick null-coalescing fix labels every assessed answer wrong. | Incorrect feedback at scale. | Remove score-based assessed classification and test null input. |
| Duplicate API and worker execution creates duplicate records. | Conflicting feedback or assessor work. | Idempotency keys, fenced claims, unique constraints, and restart tests. |
| Newer rules are applied to old responses. | Results cannot be reconstructed. | Resolve frozen versions and reject mismatches. |
| Full learner answers enter logs or research data. | Privacy breach. | Store protected content once and emit references or safe metadata. |
| Source or course scope is bypassed. | Cross-course disclosure. | Course-scoped resolution and denied-access tests. |
| Fallback hides repeated unsafe generation. | Educators cannot correct the issue. | Preserve both rejects, release fallback, and create escalation. |
| Old clients break during enum migration. | Feedback API outage. | Versioned compatibility window under D-10. |
| Passing unit tests hide the real production path. | Regression reaches users. | Add production-adapter integration and browser tests. |
| Browser automation is overstated. | False access or Safari claim. | Record Firefox setup failure and test native Safari separately. |

## Missing-data report

| Decision | Owner | Blocking effect |
| --- | --- | --- |
| D-01, provisional result visibility | Product owner and assessors | Blocks learner result wording and visibility. |
| D-04, mandatory criteria and evidence sufficiency | Assigned assessors | Blocks publication of real assessed outcomes and forms. |
| D-05, tools, support, access, and transfer rules | Assigned assessors | Blocks publication of real assessed task forms. |
| D-06, review and reassessment policy | Product owner and assessors | Blocks active reassessment and current-result selection. |
| D-07, evaluator validation and release thresholds | Assessment governance | Blocks automated evaluator release beyond advisory use. |
| D-08, retention, withdrawal, and missing-data rules | Privacy and research governance | Blocks destructive lifecycle and live research claims. |
| D-09, escalation owner and service target | Product owner and operations | Blocks escalation ownership and response-time claims. |
| D-10, legacy score compatibility window | Product and technical owners | Blocks final legacy field removal and old-client shutdown. |

These decisions do not block the null-score regression test, score-free feedback contract, truthful
pending UI, safe fault handling, or local worker readiness repair.

## PR mapping

Each implementation PR must map to one or more numbered steps in this plan. Its body must repeat
the relevant checklist, acceptance line, tests, migration effect, risks, and open policy items.

Do not request human review while any required test or local agent verdict is missing, stale,
failing, `NOT RUN`, `UNVERIFIED`, or `BLOCKED`.
