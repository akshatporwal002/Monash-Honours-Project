# 003: Repair assessment branch merge blockers

Status: bounded integration slice approved by all local reviewers; GitHub actions not authorised

Owner: Person A

Created: 2026-08-19

Target branch: `arv-person-a-assessment` at `9a42050315a589e731b10a284071e11ee9ab3210`

## Outcome

Make the implemented assessment slice safe to integrate into `main`. Restore the failing release
checks, align public contracts with the controlling assessment specification, prevent destructive
downgrades, and close the current correctness and maintainability review findings.

This plan does not implement Steps 15 to 20 from
`docs/plans/002-person-a-assessment-implementation.md`. Learner result, review request,
reassessment, score removal, final Person B integration, and pilot-readiness work remain a later
delivery slice. Formal publication remains fail-closed without an injected policy, so this repair
does not claim pilot readiness.

No GitHub action is included. The user authorised local fixes, not staging, committing, pushing,
PR creation, review requests, or merge.

## Source evidence

| Claim or rule | Evidence | Requirement |
| --- | --- | --- |
| Assessment results and lifecycle are separate. A `VOID` decision has no active result. | `docs/01-implementation-requirements.md:41-67`; `src-main/backend/app/models/assessment.py:705-706`; `src-main/backend/app/services/assessment/review.py:450-454` | FR19, AC19, AC22 |
| Stable learner-safe reason codes are fixed by the controlling specification. | `docs/02-pass-incomplete-bloom-assessment-spec.md:347-385`; `src-main/backend/app/services/assessment/pass_rules.py:215-226` | FR17, AC20, AT8-AT10 |
| The setup UI sends an invalid pass-rule shape, list access conditions, and no elicited Bloom process. | `src-main/frontend/src/features/assessment/AssessorSetup.tsx:91-120`; `src-main/backend/app/services/assessment/definitions.py:432-451`; `src-main/backend/app/services/assessment/alignment.py:76-108` | FR6, FR8, AC3, AT4-AT6 |
| Definition creation persists successfully but response serialization uses the review criterion schema and returns HTTP 500. | `src-main/backend/app/api/routes/assessment.py:427-459`; `src-main/backend/app/schemas/lms.py:240-285`; `tests/test_assessment_definition_api.py` | FR6, NFR23, AC3 |
| Current form selection orders by timestamps, so a higher approved form version can be ignored. | `src-main/backend/app/services/assessment/submissions.py:50-78`; `tests/test_assessment_submissions.py::test_changed_task_form_blocks_finalisation` | BP11, BP15, AT21 |
| Runtime readiness pins revision `20260816_0020`, while Alembic head is `20260816_0021`. | `src-main/backend/app/core/readiness.py:19`; `src-main/backend/migrations/versions/20260816_0021_assessor_review_actions.py:13-16` | NFR5, NFR17, AC9 |
| Alembic logging can disable application loggers in a full-suite process. Focused learning-event tests pass, while the full suite loses the expected safe warning records. | `src-main/backend/migrations/env.py:14`; `src-main/backend/app/core/request_context.py:32-35`; `tests/test_learning_events.py:256-276,392-412` | NFR16, NFR20, NFR23 |
| Published migrations 0015 to 0017 drop populated assessment records without local downgrade guards. | `src-main/backend/migrations/versions/20260815_0015_role_assignments.py:110-115`; `20260815_0016_assessment_definitions.py:710-754`; `20260815_0017_assessment_attempts.py:409-455` | FR26, BP8, NFR5, NFR17 |
| Learner-model replay compares only a snapshot ID, not the full immutable payload. | `src-main/backend/app/services/learner_model/repository.py:119-140`; `tests/test_learner_model.py:246-269` | FR29, FR30, NFR5, NFR17 |
| Review queue filtering builds each detail in Python and runs repeated queries per decision. | `src-main/backend/app/services/assessment/review.py:133-188,266-370` | NFR7, NFR9, NFR10 |
| One flush listener mixes eight validation concerns. | `src-main/backend/app/models/assessment.py:1150-1383` | NFR9, NFR10 |
| Assessor screens mix state, network calls, focus logic, and rendering in single components. | `src-main/frontend/src/features/assessment/AssessorSetup.tsx`; `AssessorReviewQueue.tsx` | NFR4, NFR9, NFR10 |
| Browser setup imports private helpers from unit-test modules. | `src-main/backend/tests/browser_e2e_server.py:14-16,257-263` | NFR9, NFR10 |
| Current release evidence is 569 backend passes and 12 failures, 75 frontend passes, and 18 browser passes with six Firefox page-creation failures. | Fresh Test Judge run on 2026-08-19 at head `9a42050` | AC9, NFR10, NFR18 |

## Current-state trace

### Assessment definition setup

1. The educator submits a typed `AssessmentDefinitionDraftCreate` payload.
2. The route versions the source outcome, then `AssessmentDefinitionService` stores the draft.
3. Response mapping constructs the wrong criterion read model and raises a Pydantic error.
4. `RequestContextMiddleware` returns a safe HTTP 500, so every definition API test stops.
5. The frontend mock accepts a payload the backend alignment rules reject.

This path is `CONFLICTING` for FR6, FR8, AC3, and AT4 to AT6.

### Frozen attempt and result contracts

1. An assessed response stores one frozen task-form version.
2. Finalisation asks for the current approved form, but timestamp ordering can select an older
   version.
3. The pass-rule engine emits undocumented reason strings that are persisted on the decision.
4. A valid void action clears the result, while `FormalResultSummary` rejects that state.

These paths are `CONFLICTING` for BP11, BP15, AC19, AC20, AC22, AT8 to AT10, and AT21.

### Data integrity and operational checks

1. Learner-model idempotency returns success for the same snapshot ID without checking estimates
   or evidence links.
2. Early assessment downgrade functions can delete populated role, definition, and attempt data.
3. Readiness reports an older migration head.
4. Alembic logging changes can suppress later best-effort analytics warnings in the same process.

These paths are `CONFLICTING` for FR26, FR29, FR30, NFR5, NFR16, NFR17, and NFR23.

### Review queue and test harness

The review queue is functionally covered but has decision-count-dependent queries. Model and React
modules concentrate unrelated responsibilities. Browser seeding depends on private test helpers.
The Windows default Firefox run fails inside Playwright page creation, while the prior headed run
passed. These areas are `PARTIAL` for NFR4, NFR9, NFR10, and NFR18.

## Proposed design

Keep the existing versioned assessment model and public routes. Repair boundaries instead of
adding policy:

- Use one canonical typed `AssessmentReasonCode` enum in domain, schemas, evaluation, and tests.
- Treat `VOID` as a reviewed decision with identifiers and times, but no active result or learner
  reason code.
- Make the frontend payload match the generated backend contract and alignment rules exactly.
- Compare full persisted learner-model snapshot content for an idempotent replay.
- Reject destructive downgrades before any trigger or table changes.
- Load queue records with SQL filters and bounded batch queries.
- Split validators, React state, and test seeds into named modules without changing behaviour.
- Keep CI Firefox headless. Use the proven headed Firefox mode only for Windows local runs where
  Playwright's headless page creation fails before a test begins.

## Step 1: Restore failing backend release paths

Files:

- `src-main/backend/app/api/routes/assessment.py`
- `src-main/backend/app/services/assessment/submissions.py`
- `src-main/backend/app/core/readiness.py`
- `src-main/backend/migrations/env.py`
- `src-main/backend/tests/test_assessment_definition_api.py`
- `src-main/backend/tests/test_assessment_submissions.py`
- `src-main/backend/tests/test_deployment_runtime.py`
- `src-main/backend/tests/test_learning_events.py`

Changes:

- [x] Map definition criteria through `AssessmentTaskCriterionRead`.
- [x] Select the highest approved task-form version deterministically.
- [x] Pin readiness to the actual migration head.
- [x] Preserve existing application loggers when Alembic configures logging.
- [x] Add regression proof for serialization, higher-version selection, readiness, and safe logs
  after migration work.

Edge and failure cases:

- Definition validation still returns 422, not 500.
- A stale form returns a conflict even when timestamps are out of order.
- Best-effort analytics still omits actor, answer, task, and exception content.

**Acceptance:** The 12 previously failing backend tests pass together. The definition API returns
201 for a valid draft and 422 for an invalid draft.

## Step 2: Align public assessment contracts and setup payloads

Files:

- `src-main/backend/app/domain/assessment.py`
- `src-main/backend/app/schemas/assessment.py`
- `src-main/backend/app/services/assessment/pass_rules.py`
- `src-main/backend/app/services/assessment/evaluation.py`
- `src-main/backend/app/models/assessment.py`
- `src-main/backend/migrations/versions/20260815_0017_assessment_attempts.py`
- `src-main/backend/app/schemas/lms.py`
- `src-main/backend/app/api/routes/assessment.py`
- `src-main/backend/app/services/lms.py`
- `src-main/backend/tests/test_assessment_contracts.py`
- `src-main/backend/tests/test_assessment_attempt_models.py`
- `src-main/backend/tests/test_assessment_definition_api.py`
- `src-main/backend/tests/test_pass_rule_engine.py`
- `src-main/backend/tests/test_assessment_evaluation_api.py`
- `src-main/frontend/src/features/assessment/AssessorSetup.tsx`
- `src-main/frontend/src/features/assessment/AssessorSetup.test.tsx`
- `src-main/contracts/openapi.json`
- `src-main/frontend/src/api/generated.ts`
- `docs/learnlens/person-a-person-b-contract.md`

Changes:

- [x] Add the exact stable reason-code enum from the controlling specification.
- [x] Return and persist only canonical reason codes.
- [x] Constrain persisted reasons at the database boundary and reject unknown public mappings.
- [x] Require a reason code for every active assessed result contract.
- [x] Allow a reviewed `VOID` summary with decision and review times but no result or result reason.
- [x] Correct the Person A to Person B lifecycle rule.
- [x] Build setup access modes, pass-rule operators, and elicited Bloom constraints in backend-valid
  shapes.
- [x] Test the real outgoing payload, not only a mocked success response.
- [x] Require explicit Bloom elicitation and construct-preservation checks before draft creation.
- [x] Save edited setup values through an optimistic, versioned update route before publication.
- [x] Keep edits made during an in-flight save dirty against the returned server version.
- [x] Clear Bloom and access verification when their target inputs change.
- [x] Keep source outcome versioning and definition writes in one transaction.
- [x] Regenerate OpenAPI and TypeScript contracts.

Edge and failure cases:

- Missing, conflicting, not-evaluable, and ordinary unmet evidence map to the specified codes.
- `NOT_ASSESSED` remains empty. Active assessed states still require result, decision, and time.
- Invalid access modes and recall-only forms stay blocked by backend approval checks.

**Acceptance:** Contract, pass-rule, definition, and evaluation tests pass. A frontend setup test
captures a payload accepted by `AssessmentDefinitionDraftCreate` and alignment validation.

## Step 3: Protect immutable data and exact replays

Files:

- `src-main/backend/migrations/versions/20260815_0015_role_assignments.py`
- `src-main/backend/migrations/versions/20260815_0016_assessment_definitions.py`
- `src-main/backend/migrations/versions/20260815_0017_assessment_attempts.py`
- `src-main/backend/migrations/versions/20260816_0021_assessor_review_actions.py`
- `src-main/backend/app/services/learner_model/repository.py`
- `src-main/backend/tests/test_migrations.py`
- `src-main/backend/tests/test_learner_model.py`

Changes:

- [x] Refuse each destructive downgrade when its owned tables contain records.
- [x] Keep empty-database downgrade and re-upgrade proof.
- [x] Expand the current-head guard to cover every assessment, role, evidence, and learner-model
  table that later downgrade steps could discard.
- [x] Compare every snapshot field, estimate, and evidence relation before declaring a replay.
- [x] Reject same-ID payload changes with `LearnerModelConflictError`.

Edge and failure cases:

- Numeric-only legacy history, role-only data, definition-only data, and attempt-only data each
  block destructive downgrade before schema changes.
- Exact replay is order-stable. Changed uncertainty, relation, reason, or evidence ID conflicts.

**Acceptance:** Migration rollback/recovery tests and learner-model idempotency tests pass. Failed
downgrades leave the database manifest unchanged.

## Step 4: Bound review-queue queries and split model validation

Files:

- `src-main/backend/app/services/assessment/review.py`
- `src-main/backend/app/models/assessment.py`
- `src-main/backend/tests/test_assessor_review_api.py`
- `src-main/backend/tests/test_assessment_models.py`
- `src-main/backend/tests/test_assessment_attempt_models.py`

Changes:

- [x] Apply course, outcome, result, state, age, and quality filters in SQL.
- [x] Batch-load attempts, responses, version records, evaluations, criteria, reviews, and quality
  events for the selected decision set.
- [x] Add a multi-record bounded-query test.
- [x] Split the flush listener into named validators for rules, review revisions, attempts,
  evaluations, decisions, reassessments, and appeals.
- [x] Preserve all database and ORM invariant tests.

Edge and failure cases:

- Empty queues use bounded queries and disclose no cross-course record.
- Missing linked immutable records still fail closed.
- Review revisions remain ordered within a decision.

**Acceptance:** Review service and model tests pass. Query count stays constant when the queue grows
from one to several decisions. Configured Ruff checks report no complexity error.

## Step 5: Split assessor screens without changing access behaviour

Files:

- `src-main/frontend/src/features/assessment/AssessorSetup.tsx`
- New `src-main/frontend/src/features/assessment/assessmentDraft.ts`
- New `src-main/frontend/src/features/assessment/useAssessorSetup.ts`
- New `src-main/frontend/src/features/assessment/AssessorSetupPanels.tsx`
- `src-main/frontend/src/features/assessment/AssessorReviewQueue.tsx`
- New `src-main/frontend/src/features/assessment/useAssessorReviewQueue.ts`
- New `src-main/frontend/src/features/assessment/useReviewQueueData.ts`
- New `src-main/frontend/src/features/assessment/useReviewDialogFocus.ts`
- New `src-main/frontend/src/features/assessment/AssessorReviewPanels.tsx`
- `src-main/frontend/src/features/assessment/AssessorSetup.test.tsx`
- `src-main/frontend/src/features/assessment/AssessorReviewQueue.test.tsx`
- `src-main/frontend/src/App.tsx`
- `src-main/frontend/src/test/App.test.tsx`

Changes:

- [x] Move setup draft construction into a helper. Split setup, queue data, action, and dialog
  state into focused hooks.
- [x] Move form, evidence, history, and action-dialog rendering into small components.
- [x] Preserve access revocation, stale conflict recovery, typed reasons, focus trapping, focus
  return, and live status.
- [x] Keep long JSX structures readable and directly testable.
- [x] Refresh access for the selected course, clear its cached selection after revocation, and
  leave the workspace even when another course assignment remains active.

Edge and failure cases:

- Revoked access removes action controls before a write.
- A stale review reloads server state without losing the typed reason.
- Escape, Tab, Shift+Tab, and post-action focus remain correct.

**Acceptance:** Frontend unit and Axe tests pass. Strict TypeScript and ESLint pass. Focused
complexity checks no longer report the original component findings.

## Step 6: Stabilise browser seeds and Windows Firefox execution

Files:

- New `src-main/backend/tests/support/__init__.py`
- New `src-main/backend/tests/support/assessment.py`
- New `src-main/backend/tests/support/person4.py`
- `src-main/backend/tests/browser_e2e_server.py`
- `src-main/frontend/playwright.config.ts`

Changes:

- [x] Move browser assessment and Person 4 seed helpers into stable support modules.
- [x] Remove browser-server imports from unit-test modules.
- [x] Keep Linux CI Firefox headless.
- [x] Run Windows local Firefox headed by default, with an explicit environment override for
  diagnostic headless runs.

Edge and failure cases:

- Test discovery does not collect the support module as tests.
- Seed data uses no direct learner identity outside the protected fixture database.
- Chrome, Edge, Firefox, and WebKit projects still run from one command.

**Acceptance:** Backend seed consumers pass. `npm.cmd run test:e2e` passes all available browser
projects on Windows, and the CI configuration remains headless on Linux.

## Step 7: Record the bounded delivery scope and rerun all gates

Files:

- `docs/plans/002-person-a-assessment-implementation.md`
- `docs/plans/003-merge-blocker-repairs.md`
- All files changed by Steps 1 to 6

Changes:

- [x] Record that the current integration slice ends after assessor review and does not satisfy
  Steps 15 to 20 or pilot readiness.
- [x] Run targeted checks after each repair.
- [x] Run the backend and frontend release commands from `.github/workflows/quality.yml`.
- [x] Run current browser and automated accessibility checks.
- [x] Obtain fresh independent Test Judge, Code Reviewer, and Code Quality Reviewer verdicts on
  the final working tree.
- [x] Record unavailable manual screen-reader or native Safari proof as `NOT RUN`; do not convert
  it into a pass or pilot-readiness claim.

Edge and failure cases:

- Any code change after a verdict invalidates that verdict.
- A failing or unavailable release command remains a blocker or named exception according to its
  acceptance scope.

**Acceptance:** All available release checks pass, all three local verdicts approve the same final
working tree, and the plan states the exact remaining product and manual-accessibility limits.

## Full verification

Run from `src-main/backend`:

```powershell
uv lock --check
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pytest tests/test_assessment_definition_api.py tests/test_assessment_submissions.py tests/test_deployment_runtime.py tests/test_learning_events.py
uv run --frozen pytest tests/test_assessment_contracts.py tests/test_pass_rule_engine.py tests/test_assessment_evaluation_api.py
uv run --frozen pytest tests/test_learner_model.py tests/test_assessor_review_api.py tests/test_assessment_models.py tests/test_assessment_attempt_models.py
uv run --frozen pytest tests/test_migrations.py
uv run --frozen python scripts/export_openapi.py --check
uv run --frozen python scripts/generate_frontend_contracts.py --check
uv run --frozen pytest --cov=app.services --cov-report=term-missing --cov-fail-under=80
```

Run from `src-main/frontend`:

```powershell
npm.cmd run lint
npm.cmd test
npm.cmd run build
npm.cmd run test:e2e
npm.cmd audit --audit-level=high
npm.cmd audit --omit=dev --audit-level=high
```

CI also runs the Python dependency audit and Gitleaks. Network-backed audits are `NOT RUN` unless
the environment and current task authority permit them.

Manual proof:

- Keyboard and focus paths for setup and review.
- 200 and 400 percent zoom and 640px and 320px reflow.
- Approved screen-reader output when a controllable environment is available.
- Native Safari remains external evidence; Playwright WebKit proves only its own project.

## Verification evidence

Recorded on 2026-08-19 against the current unstaged working tree:

| Gate | Result |
| --- | --- |
| `uv lock --check` | Passed |
| Configured Ruff lint and format checks | Passed, 300 Python files formatted |
| Full backend suite with the CI coverage threshold | Passed, 592 tests and 84.97% service coverage |
| Migration downgrade, recovery, and manifest tests | Passed separately, 26 tests |
| OpenAPI and generated TypeScript contract drift | Passed |
| Frontend ESLint and production build | Passed |
| Frontend unit and automated Axe checks | Passed, 81 tests |
| Playwright browser matrix | Passed in one final run, 24 tests across Chrome, Edge, Firefox, and WebKit. Firefox used the configured headed Windows run outside the sandbox. |
| Independent local reviews | Passed, Test Judge, Code Reviewer, and Code Quality Reviewer approved the final implementation tree |
| Python dependency audit | Passed, no known vulnerabilities |
| Full and production npm dependency audits | Passed, no vulnerabilities |
| Gitleaks | `NOT RUN`, the local binary is unavailable; GitHub CI owns this check |
| Approved screen reader and native Safari | `NOT RUN`, no approved local environment is available |
| Manual 200% and 400% zoom inspection | `NOT RUN`; automated 640px and 320px overflow checks passed |

## Migration and rollback

No new migration revision is planned. The unreleased assessment migration now constrains stored
reason codes. The repair also changes downgrade safety and the runtime head pin. Each destructive
downgrade must check its owned tables before removing triggers, columns, or tables. Empty databases
may still downgrade and re-upgrade. Populated databases must use the verified backup restore path
in `app/services/assessment/backup.py`.

Tests compare database manifests before and after a rejected downgrade. Existing records, links,
and digests must remain unchanged.

## Risks and controls

| Risk | Impact | Control and proof |
| --- | --- | --- |
| Payload repair weakens approval validation | Misaligned tasks could publish | Use the existing backend validator and capture the real frontend payload in tests |
| Reason-code rename breaks stored draft data | Old unmerged fixtures may not deserialize | Branch is not in `main`; update all code, tests, OpenAPI, and docs together |
| Queue batching changes ordering | Assessor sees inconsistent evidence | Preserve explicit order for decisions, criteria, and review revisions |
| Replay comparison depends on row order | Exact retry could conflict | Compare normalised field-keyed immutable structures |
| Downgrade guard runs too late | Data may be lost before refusal | Check before any trigger, table, or batch operation |
| Windows-only Firefox setting leaks into CI | CI browser coverage changes | Gate on `process.platform` and keep CI Linux headless |
| Scope split is mistaken for feature completion | Incomplete learner flows could be treated as ready | Keep publication fail-closed and label Steps 15 to 20 and pilot proof as missing |

## Missing-data report

| Missing decision or evidence | Owner | Blocking effect |
| --- | --- | --- |
| Product policies listed in Plan 002 remain unresolved | Product and assessment owners | Blocks pilot configuration, not repair of the current fail-closed slice |
| Approved screen-reader environment and reviewer | Accessibility owner | Screen-reader proof remains `NOT RUN` if the environment cannot verify spoken output |
| Native Safari environment | Accessibility owner | Native Safari claim remains `NOT RUN`; WebKit is reported separately |
| GitHub CI for the repaired head | GitHub workflow owner | No remote readiness claim until a later authorised push runs CI |

## PR mapping

A later implementation PR must mirror all seven steps, the exact verification results, the
scope split from Plan 002, data-safety proof, reviewer verdicts, and every `NOT RUN` item. It must
not claim that learner result, reassessment, score removal, or pilot-readiness work is complete.
