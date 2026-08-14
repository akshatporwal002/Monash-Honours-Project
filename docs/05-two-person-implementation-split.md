# 001: Two-person LearnLens implementation split

Status: proposed

Owners: Person A and Person B

Created: 2026-08-14

Target branch: `main`

## Outcome

Two people can implement the remaining LearnLens work with limited file overlap.

Person A owns formal assessment and its educator, assessor, and learner interfaces. Person B owns
learning evidence, AI support services, research, analytics, and release proof.

This plan does not assign, repeat, or resolve the policy decisions that block a live pilot. It also
does not authorise implementation before this plan receives human approval.

## Ownership boundary

The split follows code ownership, not alternating phases. Each person should work on a separate
branch or worktree.

| Area | Person A owns | Person B owns |
| --- | --- | --- |
| Domain language | Assessment enums and public assessment contracts | Quality Judge, workflow, research, and operational enums |
| Database | Outcome, criteria, assessment, result, review, and reassessment records | Evidence, learner-model, adaptation, simulation, research, and analytics records |
| Backend | Assessment services and LMS integration | Feedback, Qiskit, evidence, learner model, adaptation, research, and analytics services |
| API | Assessment setup, evaluation, review, result, and reassessment routes | Evidence, simulation, feedback, research, analytics, and progress support routes |
| Frontend | Assessor setup, review queue, learner result, and reassessment screens | Task evidence, progress, adaptation, gamification, analytics, and research screens |
| Testing | Assessment acceptance tests and assessment migration tests | Platform, evidence, research, accessibility, performance, recovery, and release tests |
| Documentation | Assessment schema, migration, assessor, and learner-result guides | Gap matrix, architecture, operations, research, access, security, and release records |

## Shared-file rule

Person A owns these high-conflict files during implementation:

- `src-main/backend/app/models/enums.py`
- `src-main/backend/app/models/lms.py`
- `src-main/backend/app/models/__init__.py`
- `src-main/backend/app/schemas/lms.py`
- `src-main/backend/app/services/lms.py`
- `src-main/backend/app/api/routes/lms.py`
- `src-main/backend/app/api/router.py`
- `src-main/frontend/src/app/types.ts`
- `src-main/frontend/src/app/api.ts`
- `src-main/frontend/src/App.tsx`
- `src-main/contracts/openapi.json`
- `src-main/frontend/src/api/generated.ts`

Person B must not edit these files directly. Person B should add separate modules and tests. Person A
will perform the small integration edits after Person B's module contracts are stable.

This rule prevents both people from repeatedly changing the same LMS service, generated contracts,
router, and frontend type files.

## Source evidence

| Claim or rule | Evidence | Requirement |
| --- | --- | --- |
| Learner results must use only `PASS` or `INCOMPLETE`. | `docs/01-implementation-requirements.md:17` | AC19, AT1 to AT3 |
| The current role enum lacks assessor and research permissions. | `src-main/backend/app/models/user.py:10` | FR1, FR38, AT17 |
| Quality Judge currently uses `PASS` and `FAIL`. | `src-main/backend/app/models/enums.py:42` | FR17, AT20 |
| The current outcome record lacks Bloom and evidence-rule fields. | `src-main/backend/app/models/lms.py:152` | FR6, BP1 to BP6, AT4 to AT6 |
| A submission attempt stores a mandatory numeric score. | `src-main/backend/app/models/lms.py:258`, `src-main/backend/app/models/lms.py:294` | AC19, AT1 to AT3 |
| Completion currently depends on a global numeric passing score. | `src-main/backend/app/services/lms.py:576`, `src-main/backend/app/services/lms.py:603` | FR12, FR19, AT7 to AT9 |
| The required full gap matrix does not exist. | `docs/03-codex-implementation-work-order.md:122` | Phase 0 gate |
| The existing quality workflow defines the current release commands. | `.github/workflows/quality.yml` | NFR10, AC9 |

## Current-state trace

The current learner path is:

1. A student opens an LMS task through the authenticated LMS routes.
2. `LmsService.submit` validates the task-specific response.
3. The task registry calculates a numeric score.
4. `passing_score` changes the attempt status to submitted or completed.
5. The attempt stores the numeric score and starts feedback processing.
6. Student and educator views display scores, averages, mastery, points, and rankings.

This path is `CONFLICTING` with the binary assessment specification.

The current platform also has useful separate services for RAG, Qiskit, feedback judging,
learning events, research export, analytics, audit, and recovery. These areas are suitable for
Person B because most already live outside the central LMS files.

Formal assessment definition, criterion evaluation, result lifecycle, assessor review, learner
review requests, reassessment, and Bloom-based result views are `MISSING`.

Manual browser, load, native Safari, screen-reader, and complete release evidence remain
`UNVERIFIED`.

## Proposed design

The two streams connect through versioned contracts rather than shared service code.

```text
Person A: Assessment domain and interfaces
    assessment definition -> response version -> criterion decisions
    -> provisional result -> assessor action -> learner result
                              |
                              | versioned IDs and DTOs
                              v
Person B: Evidence and platform services
    task evidence -> feedback and simulation -> learner model
    -> adaptation -> research and analytics -> release evidence
```

The integration boundary contains only opaque IDs, enums, timestamps, evidence references, and
version identifiers. Person B must not calculate or change the learner's formal result. Person A
must not place research condition, confidence, time, hints, points, or learner-model estimates in
the pass rule.

## Person A workstream: assessment and user interfaces

### A1: Lock assessment language and contracts

Files:

- `src-main/backend/app/models/enums.py`
- `src-main/backend/app/schemas/lms.py`
- New `src-main/backend/app/schemas/assessment.py`
- `src-main/frontend/src/app/types.ts`
- Contract generation scripts and generated files

Changes:

- [ ] Add the required assessment, lifecycle, purpose, Bloom, and criterion enums.
- [ ] Rename Quality Judge decisions to `APPROVED` and `REJECTED`.
- [ ] Keep workflow failure states separate from learner results.
- [ ] Define versioned assessment and evidence-reference DTOs for Person B.
- [ ] Reject numeric grades and public `FAIL` values in assessment schemas.
- [ ] Add enum, schema, generated-contract, and invalid-value tests.

Edge and failure cases:

- Legacy judge values need compatibility handling during migration.
- A missing result is not the same as `INCOMPLETE`.
- Invalid wire values must fail before reaching service code.

**Acceptance:** Backend and frontend contract checks pass, `FAIL` cannot be created as a learner
result, and Person B can import the frozen assessment DTOs without importing LMS ORM models.

Requirements: FR1, FR6, FR17, FR19, FR26, BP15, AC19, AT1 to AT3, AT20.

### A2: Add the assessment database and forward migration

Files:

- `src-main/backend/app/models/lms.py`
- New `src-main/backend/app/models/assessment.py`
- `src-main/backend/app/models/__init__.py`
- New Alembic migrations under `src-main/backend/migrations/versions`
- Migration and model tests under `src-main/backend/tests`

Changes:

- [ ] Add versioned Bloom targets, claims, criteria, and Boolean pass rules.
- [ ] Add task-form, response-version, assessment-attempt, and criterion-decision records.
- [ ] Add provisional result, result lifecycle, assessor action, and audit references.
- [ ] Enforce exact response, rule, task, source, model, and actor versions.
- [ ] Add course-scope, lifecycle, uniqueness, and idempotency constraints.
- [ ] Preserve legacy scores and statuses in protected migration history.
- [ ] Keep old records readable during the compatibility window.
- [ ] Add clean, legacy, repeated-upgrade, integrity, backup, and recovery tests.

Edge and failure cases:

- Numeric values must not become `PASS` without an approved mapping.
- Legacy public `FAIL` must map to `INCOMPLETE` while retaining its source value.
- A task or system fault must not create a valid assessment result.
- Repeated migrations and duplicate evaluation requests must not duplicate records.

**Acceptance:** Clean and legacy databases reach the new migration head, record counts match the
expected fixtures, invalid lifecycle writes fail, and accepted learner work remains readable.

Requirements: FR6, FR19, FR26, FR38, BP8, BP15, NFR17, NFR20, AT1 to AT3, AT21, AT22.

### A3: Add assessor access and assessment setup

Files:

- `src-main/backend/app/models/user.py`
- `src-main/backend/app/api/dependencies/roles.py`
- New assessment services and routes
- `src-main/backend/app/services/lms.py`
- `src-main/backend/app/api/routes/lms.py`
- New frontend assessment setup components

Changes:

- [ ] Add explicit assessor permission without treating every educator as an assessor.
- [ ] Add a separate research permission without granting it through another role.
- [ ] Enforce course scope in services, queries, and routes.
- [ ] Add versioned outcome, Bloom, criteria, pass-rule, tool, support, access, and form setup.
- [ ] Add educator and assessor approval history.
- [ ] Block assessed-task publication when required fields or approval are missing.
- [ ] Add setup, publication, role-denial, and cross-course tests.

Edge and failure cases:

- UI hiding does not replace backend permission checks.
- Stale versions must return a conflict instead of overwriting an approved definition.
- Access support must not weaken the approved standard.

**Acceptance:** An authorised assessor can create and publish a complete assessment definition.
Student, educator-only, out-of-course, and stale-version requests are denied safely.

Requirements: FR1, FR6, FR8, FR20, FR38, PD9, PD12, BP1 to BP9, AC1, AC2, AC16,
AT4 to AT6, AT17, AT21.

### A4: Implement the criterion evaluator and binary rules engine

Files:

- New `src-main/backend/app/services/assessment` package
- New assessment repositories
- New assessment API routes
- Assessment unit and integration tests

Changes:

- [ ] Evaluate each criterion as `MET`, `NOT_MET`, or `NOT_EVALUABLE`.
- [ ] Link each decision to exact evidence and a short reason.
- [ ] Apply the stored Boolean pass rule deterministically.
- [ ] Produce only provisional `PASS` or `INCOMPLETE` results.
- [ ] Keep formal result calculation separate from AI feedback generation.
- [ ] Exclude research, demographics, confidence, time, retries, hints, points, and access support.
- [ ] Add idempotency, stale-version, invalid-attempt, and replay tests.

Edge and failure cases:

- Missing evidence results in `INCOMPLETE` only when the attempt is otherwise valid.
- System and task faults keep review state or void the attempt.
- Recall-only evidence cannot pass an `ANALYSE` target.

**Acceptance:** AT1 to AT14 and AT20 to AT23 pass with deterministic results under identical
versions. No result response contains a numeric grade.

Requirements: FR17, FR19, FR31, FR38, BP2 to BP6, BP8 to BP11, AC19, AC20, AC22, AT1 to AT14,
AT20 to AT23.

### A5: Build assessor review, learner results, and reassessment

Files:

- New assessor review and reassessment services and routes
- New frontend assessor queue and learner result components
- `src-main/frontend/src/App.tsx`
- Browser, accessibility, and API tests

Changes:

- [ ] Add review filters and full evidence inspection.
- [ ] Add confirm, override, withhold, and void actions with reasons and audit history.
- [ ] Make repeated finalisation idempotent.
- [ ] Show learners the result, lifecycle, Bloom target, evidence, missing criteria, and next action.
- [ ] Add learner review and correction requests.
- [ ] Use a fresh approved task form for reassessment.
- [ ] Keep all prior decisions and never average attempts.
- [ ] Add keyboard, focus, zoom, reflow, colour-independent, and screen-reader checks.

Edge and failure cases:

- An assessor cannot act outside assigned course scope.
- Stale review pages cannot overwrite a newer action.
- Reassessment never deletes or edits the earlier attempt.

**Acceptance:** AT15 to AT19 and AT24 pass. Every assessor action is audited, and the complete
learner result path passes automated and recorded manual access checks.

Requirements: FR12, FR21, FR38, PD7, PD12, BP7 to BP9, AC5, AC16, AC17, AC21, AC22,
AT15 to AT19, AT24.

### A6: Remove score-based learner and educator presentation

Files:

- `src-main/frontend/src/components/TaskView.tsx`
- `src-main/frontend/src/components/StudentDashboard.tsx`
- `src-main/frontend/src/components/StudentsView.tsx`
- Assessment-related sections of `src-main/frontend/src/components/AnalyticsView.tsx`
- `src-main/backend/app/services/lms.py`
- Related frontend and backend tests

Changes:

- [ ] Remove learner-facing scores, averages, percentage grades, and numeric mastery labels.
- [ ] Separate task state, evidence, inference, progress, and formal results.
- [ ] Replace completion logic that depends on `passing_score`.
- [ ] Keep valid research and Quality Judge metrics clearly labelled and separate.
- [ ] Preserve optional game points without presenting them as assessment results.

Edge and failure cases:

- Qiskit probabilities and quality metrics may remain when their labels cannot imply learner grades.
- Legacy attempts need a safe compatibility display without exposing a new numeric grade.

**Acceptance:** Learner and educator assessment views show no numeric grade, public `FAIL`, fake
pass average, or numeric mastery claim. Existing valid research and simulation metrics remain usable.

Requirements: FR19, FR21, FR22, FR25, FR39, BP13, AC6, AC11, AC19, AT2, AT3, AT19.

## Person B workstream: evidence, platform, research, and release proof

### B1: Create the gap matrix and restore the current baseline

Files:

- New `docs/learnlens/implementation-gap-matrix.md`
- `src-main/backend/app/services/analytics`
- `src-main/backend/tests/test_analytics_application.py`
- `src-main/backend/tests/test_person4_e2e.py`

Changes:

- [ ] Map every FR, PD, BP, NFR, AC, and AT item to exact current proof.
- [ ] Mark gaps as implemented, partial, missing, conflicting, or unverified.
- [ ] Repair the two current research-rate test failures from root-cause evidence.
- [ ] Run the existing backend, frontend, contract, lint, format, and build checks.
- [ ] Record honest limits without treating code existence as runtime proof.

Edge and failure cases:

- The analytics repair must preserve half-open date filters and incomplete-pair exclusion.
- Existing unrelated work must remain untouched.

**Acceptance:** The gap matrix contains every required row, both failing tests pass for the correct
reason, and the pre-change quality baseline is recorded.

Requirements: Phase 0 gate, NFR10, AC9.

### B2: Expand append-only learning evidence and learner-model snapshots

Files:

- `src-main/backend/app/services/learning_events`
- New evidence and learner-model modules
- New models and migrations outside Person A's LMS-owned files
- Learning-event, evidence, privacy, and learner-model tests

Changes:

- [ ] Capture predictions, explanations, revisions, confidence, hints, scaffolds, reflections,
  misconception checks, transfer, access conditions, and timestamps.
- [ ] Keep response and evidence history append-only.
- [ ] Separate observations from inferences.
- [ ] Store uncertainty, recency, evidence links, model version, and prior state.
- [ ] Add learner annotation and educator correction contracts.
- [ ] Prevent diagnostic or fixed-ability labels.
- [ ] Expose only versioned evidence references to Person A's assessment services.

Edge and failure cases:

- Full learner answers and direct identifiers stay out of general logs.
- A single wrong response cannot create a certain misconception claim.
- Failed external calls cannot erase accepted evidence.

**Acceptance:** A complete learning episode is visible in time order, old evidence survives
revision, every inference links to evidence and uncertainty, and safety tests reject banned claims.

Requirements: FR19, FR20, FR29 to FR34, FR36, PD3, PD8, NFR16, NFR20, NFR27, NFR31,
AC11 to AC15.

### B3: Complete task contracts and Qiskit evidence

Files:

- `src-main/backend/app/services/task_types.py`
- `src-main/backend/app/services/quantum.py`
- New task handlers and schemas outside shared LMS files
- New frontend task components outside `App.tsx` and shared types
- Task, simulation, browser, and access tests

Changes:

- [ ] Add prediction, reflection, transfer, and broader reasoning task handlers.
- [ ] Add typed draft, submit, evidence extraction, evaluation-adapter, and export contracts.
- [ ] Bound Qiskit circuit size, shots, runtime, and resource use.
- [ ] Store simulator versions, counts, probabilities, shots, and safe errors.
- [ ] Produce matching visual and text circuit evidence.
- [ ] Capture prediction before result reveal when the task requires it.
- [ ] Preserve accepted work after every simulation fault.

Edge and failure cases:

- Invalid circuits return controlled errors without losing drafts.
- Accessible and visual responses must refer to the same circuit and result object.
- Task handlers must not calculate the formal assessment result.

**Acceptance:** Every required task type works through draft and submit, code formatting survives,
visual and text circuit forms agree, and simulation faults lose no accepted learner work.

Requirements: FR9, FR13, FR14, PD4, PD5, NFR4, NFR11, NFR23, AC3, AC17.

### B4: Extend feedback quality and safe learner support

Files:

- `src-main/backend/app/services/feedback`
- `src-main/backend/app/services/rag`
- Feedback schemas and tests
- `src-main/frontend/src/features/feedback`

Changes:

- [ ] Add Bloom, evidence-rule, accessibility, bias, and unsupported-learner-claim checks.
- [ ] Preserve one regeneration and safe fallback after repeated rejection.
- [ ] Store all prompt, source, model, judge, cost, latency, and fallback versions.
- [ ] Provide useful incomplete support without exposing the next answer.
- [ ] Keep feedback classification separate from formal learner results.
- [ ] Add safety cases for prompt injection, answer leakage, unusual reasoning, and short valid answers.

Edge and failure cases:

- Missing retrieval or simulation evidence returns a typed safe state.
- Provider, model, and judge failures preserve the submission and evidence.
- Feedback must not invent an assessment result.

**Acceptance:** Feedback retry and fallback tests pass, banned diagnosis and bias cases are rejected,
and released feedback always has approved grounding and version evidence.

Requirements: FR15 to FR18, PD6, PD7, PD9, PD10, NFR12 to NFR14, NFR21, NFR28, AC4.

### B5: Implement adaptation, misconception, progress, and optional gamification modules

Files:

- New adaptation and misconception services
- `src-main/backend/app/services/gamification.py`
- New progress projection services outside `LmsService`
- `src-main/frontend/src/components/AnalyticsView.tsx`, coordinated with Person A
- New progress, adaptation, and gamification components and tests

Changes:

- [ ] Suggest next tasks or supports from observable evidence and uncertainty.
- [ ] Store triggers, reasons, versions, and override history.
- [ ] Add hypothesis, probe, alternate explanation, revision, transfer, and correction flow.
- [ ] Keep the approved assessment standard outside adaptation services.
- [ ] Separate evidence, inference, progress, and result projections.
- [ ] Make gamification optional and neutral to assessment outcomes.
- [ ] Remove or restrict ranking behaviour that conflicts with product rules.
- [ ] Extend reminders with course time zones, extensions, access plans, and learner preferences.

Edge and failure cases:

- Research condition cannot alter adaptation or formal result.
- Hints, retries, access support, time, pace, and breaks cannot reduce progress or results.
- Learner and educator overrides remain visible and reversible where allowed.

**Acceptance:** Seeded evidence produces the expected adaptation without changing assessment
criteria, possible misconceptions remain uncertain, and disabling gamification changes no result.

Requirements: FR23 to FR25, FR30 to FR37, PD1 to PD3, PD8, PD11, NFR26, NFR27, NFR29,
NFR31, AC5, AC11 to AC15, AT11 to AT14, AT18, AT23.

### B6: Complete research safeguards and analytics separation

Files:

- `src-main/backend/app/services/research`
- `src-main/backend/app/services/research_export.py`
- `src-main/backend/app/services/analytics`
- Research, export, privacy, and analytics schemas and tests
- `src-main/frontend/src/features/analytics`

Changes:

- [ ] Keep operational identity and pseudonymous research identity separate.
- [ ] Add versioned research eligibility and approved-field filtering hooks.
- [ ] Record missing-data states without inventing values.
- [ ] Keep educational outcomes separate from technical AI quality metrics.
- [ ] Remove numeric learner assessment fields from new research exports.
- [ ] Preserve source, model, prompt, judge, simulation, latency, token, and cost versions.
- [ ] Prove research condition has no input to formal assessment or adaptation decisions.

Edge and failure cases:

- Direct identifiers and full learner answers cannot enter approved exports.
- Incomplete research pairs stay excluded from comparative rates.
- Formula injection and nested private values remain blocked.

**Acceptance:** Golden exports contain only approved pseudonymous fields, incomplete pairs are
handled correctly, and identical assessment evidence has identical results across research cases.

Requirements: FR20, FR39, BP12, BP13, NFR16, NFR20, NFR22, NFR25, NFR30, AC6, AC10, AT23.

### B7: Produce non-functional and release proof

Files:

- `.github/workflows/quality.yml`
- New load, recovery, security, access, and cost tests
- Release records under `src-main/docs` and `docs/learnlens`
- Deployment and operations documentation

Changes:

- [ ] Run and record format, lint, type, static, unit, integration, browser, security, and coverage checks.
- [ ] Maintain at least 80 percent backend service statement coverage.
- [ ] Add 50-user latency and 100-user scale evidence.
- [ ] Test restart, retry, idempotency, LLM timeout, Qiskit fault, and database contention paths.
- [ ] Verify backup and restore completeness.
- [ ] Measure cost per complete learning loop.
- [ ] Test Chrome, Edge, Firefox, Safari, keyboard, zoom, reflow, and screen readers.
- [ ] Record manual access checks without treating automated scans as full proof.
- [ ] Prepare architecture, environment, security, privacy, research, traceability, and known-limit records.

Edge and failure cases:

- An unavailable browser or external service is `NOT RUN`, not a pass.
- A build or HTTP 200 result does not prove browser interaction or access compliance.
- No unresolved critical or high security finding may be hidden by a suppression.

**Acceptance:** Every applicable NFR has saved proof or a named open exception, CI commands pass,
and the handoff documents link each claim to current test or runtime evidence.

Requirements: NFR1 to NFR31, AC9, AC17, AC18.

## Coordination points

Only these handoffs are planned:

### Handoff 1: Assessment contract freeze

Person A completes A1 first. Person B then uses the frozen DTOs and evidence-reference rules.
Person B can complete B1 and begin platform-only parts of B2, B3, B4, B6, and B7 before this handoff.

**Acceptance:** Both people agree on enum values, evidence-reference fields, version fields, and
forbidden formal-result inputs. The agreement is stored in code and tests, not chat only.

### Handoff 2: Integration and generated files

Person B supplies stable module entry points and tests. Person A wires them into shared routers,
LMS orchestration, generated API contracts, and the application shell.

**Acceptance:** Integration changes touch only the shared files owned by Person A. Person B's
modules remain independently testable.

## Suggested parallel order

| Work period | Person A | Person B |
| --- | --- | --- |
| Start | A1 contracts | B1 gap matrix and baseline repair |
| Parallel block 1 | A2 database migration | B2 evidence model and B3 task or Qiskit modules |
| Parallel block 2 | A3 setup and access | B4 feedback quality and B6 research separation |
| Parallel block 3 | A4 evaluator | B5 adaptation, progress, and gamification |
| Parallel block 4 | A5 review and reassessment | B7 release tests and records |
| Integration | A6 score removal and shared-file wiring | Support targeted integration tests without editing shared files |

## Full verification

Run targeted tests with each step. Before handoff, run the commands defined by the current
repository and `.github/workflows/quality.yml`.

Backend:

```powershell
cd src-main/backend
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pytest --cov=app.services --cov-report=term-missing --cov-fail-under=80
uv run --frozen pytest tests/test_migrations.py
uv run --frozen python scripts/export_openapi.py --check
uv run --frozen python scripts/generate_frontend_contracts.py --check
```

Frontend:

```powershell
cd src-main/frontend
npm ci
npm run lint
npm test
npm run build
npm run test:e2e
npm audit --audit-level=high
npm audit --omit=dev --audit-level=high
```

Also run and save manual keyboard, zoom, reflow, screen-reader, browser, load, recovery, backup,
security, privacy, and cost checks where automation cannot prove the requirement.

## Migration and rollback

Person A owns the assessment migration sequence. Person B may add separate evidence and research
migrations, but must not edit Person A's migration revisions.

- Use forward migrations only.
- Keep legacy score data readable during the compatibility period.
- Store source values before removing public numeric fields.
- Test clean, legacy, repeated, duplicate, stale, and partially migrated databases.
- Verify table counts, foreign keys, assessment links, and content digests.
- Restore from a verified backup as the recovery path.
- Do not use a guessed numeric-to-result mapping.

## Risks and controls

| Risk | Impact | Control and proof |
| --- | --- | --- |
| Both people edit central LMS files | Repeated merge conflicts and lost work | Person A is the only shared-file owner. Person B adds isolated modules. |
| Assessment and research concepts mix | Research data could affect learner results | Versioned DTO boundary and AT23 tests block research inputs. |
| Numeric grades survive in hidden paths | The UI, API, export, or analytics may violate the product rule | Repository-wide search, schema rejection, migration tests, and AT1 to AT3. |
| Person B's evidence changes break assessment | Evaluations could reference stale or missing evidence | Frozen evidence-reference contract and version-conflict tests. |
| Migration loses historical attempts | Accepted learner work could become unreadable | Forward migration, protected source history, record counts, backup, and restore proof. |
| Accessibility is tested too late | Result and review screens may require redesign | Access tests stay inside A5, B3, and B7, with manual records before handoff. |
| Existing platform behaviour regresses | Working RAG, feedback, simulation, or research flows may break | B1 establishes the baseline before feature work. Full release checks run after integration. |

## Missing-data report

Live-pilot policy decisions are intentionally excluded at the user's request. This plan does not
assign them or invent defaults for them. Work that needs one of those decisions must stop at a
configurable interface and cannot claim pilot readiness.

No additional implementation sample or current-code evidence is required to begin B1 or draft the
detailed A1 implementation plan.

## PR mapping

Use separate implementation PRs for Person A and Person B. Each PR must mirror its owned steps,
checklists, acceptance lines, verification results, risks, and open items.

Do not request human review until implementation, tests, and all required local agent reviews pass.
