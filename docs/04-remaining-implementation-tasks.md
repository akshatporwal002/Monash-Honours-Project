# LearnLens remaining implementation tasks

Status: codebase and document audit

Last updated: 2026-08-14

## 1. Main finding

The codebase is a strong older MVP, but it does not meet the new LearnLens assessment rules.
The main unfinished work is the move from numeric scores to assessor-controlled `PASS` or
`INCOMPLETE` results.

The existing implementation provides useful foundations. These should be preserved and extended.
They must not be treated as proof that the newer requirements are complete.

## 2. Remaining tasks by priority

| Priority | Task | Main gap |
| --- | --- | --- |
| P0 | Create the implementation gap matrix | The required `docs/learnlens/implementation-gap-matrix.md` does not exist. It must cover FR1 to FR39, PD1 to PD12, BP1 to BP15, NFR1 to NFR31, AC1 to AC22, and AT1 to AT24. |
| P0 | Repair the existing test baseline | Of 383 backend tests, 381 pass and two research analytics tests fail. Both receive `None` for expected rate values. |
| P1 | Replace numeric assessment results | Submissions store a numeric score from 0 to 100. Completion uses a global passing score, and the UI displays percentages. |
| P1 | Introduce the required shared enums | Add `AssessmentResult`, `ResultState`, `SubmissionState`, `AssessmentPurpose`, `BloomProcess`, `BloomKnowledge`, `CriterionDecision`, `QualityReviewDecision`, and `MisconceptionState`. |
| P1 | Separate status namespaces | Learner results, Quality Judge decisions, workflow outcomes, submission states, and learner-model estimates must use separate enums and fields. |
| P1 | Design and migrate the assessment database | Add versioned criteria, pass rules, response versions, evidence links, assessment decisions, assessor confirmation, overrides, voiding, and protected migration history. |
| P1 | Add assessor and research permissions | Current roles only include student, educator, and administrator. Assessor and research access must be explicit and course-scoped. |
| P2 | Build the assessment blueprint workflow | Add Bloom targets, claims, evidence criteria, mandatory rules, tools, supports, access conditions, task forms, approval state, and version history. |
| P2 | Add assessment publication gates | Block assessed tasks without an approved outcome, Bloom target, criteria, pass rule, aligned task form, and assessor approval. |
| P2 | Complete the task-type contract | Add prediction, reflection, transfer, and broader explanation or reasoning contracts. Each needs schemas, validation, UI, evidence extraction, accessible controls, export, and tests. |
| P2 | Complete Qiskit assessment evidence | Preserve drafts after faults, store simulator versions and limits, provide matching visual and text results, and capture predictions before revealing results where required. |
| P2 | Expand the learning evidence model | Add revisions, reasoning, confidence, hints, scaffolds, reflection, transfer, misconception evidence, uncertainty, and learner-model snapshots. |
| P2 | Build the binary Bloom evaluator | Evaluate each criterion as `MET`, `NOT_MET`, or `NOT_EVALUABLE`, then apply the stored Boolean pass rule. An LLM must not return the final result by itself. |
| P2 | Build assessor review and learner result screens | Add evidence inspection, confirmation, override, withholding, void actions, reasons, audit history, review requests, and accessible result presentation. |
| P2 | Add reassessment | Use a fresh approved task form. Preserve earlier decisions, do not average attempts, and define which result becomes current. |
| P2 | Add controlled adaptation and misconception flows | Store evidence, uncertainty, versions, reasons, and learner or educator overrides. One wrong answer must never become a diagnosis. |
| P2 | Repair progress and gamification semantics | Remove learner-facing average scores and concept-mastery percentages. Make gamification optional and independent of assessment results. Review the leaderboard against the no-public-ranking rule. |
| P2 | Complete research safeguards | Add consent, withdrawal, missing-data handling, approved-field controls, identity separation, and proof that research conditions cannot affect results. |
| P3 | Complete non-functional release evidence | Run browser, accessibility, load, recovery, security, privacy, cost, backup, and evaluator validation gates. Save evidence for every NFR. |
| P3 | Prepare pilot documentation | Add or update the required assessor, learner, migration, accessibility, security, research, traceability, and known-limit documents. |

## 3. Existing functionality to preserve

The current implementation already provides:

- Authenticated student, educator, and administrator workspaces.
- Course, module, enrolment, and basic outcome management.
- PDF, DOCX, PPTX, and HTTPS material intake.
- Course-scoped retrieval and grounded task generation.
- Six existing task handlers.
- Qiskit Aer simulation and controlled errors.
- Drafts and immutable submission attempts.
- Feedback generation, quality judging, one retry, and a safe fallback.
- Audit records and pseudonymous research exports.
- Reminders, recommendations, gamification, and administration.
- Alembic migrations, Docker packaging, CI, and generated API contracts.

These features need extension or terminology changes before they satisfy the new specification.

## 4. Immediate implementation conflicts

The following conflicts exist in the current live path:

- `SubmissionAttempt.score` is mandatory and constrained from 0 to 100.
- A configurable `passing_score` determines task completion.
- Student and educator pages show percentages and average scores.
- Concept mastery is calculated from numeric scores.
- Quality Judge decisions use `PASS` and `FAIL`, which conflicts with learner-result terms.
- There is no assessment result lifecycle.
- There is no assessor confirmation or override workflow.
- Learning outcomes do not contain Bloom targets or approved evidence rules.
- There are no acceptance tests for AT1 to AT24.
- Existing traceability covers the older FR1 to FR28 and NFR1 to NFR25 baseline.
- The required full implementation gap matrix does not exist.

## 5. Work packages in dependency order

### 5.1 Restore a known baseline

1. Create `docs/learnlens/implementation-gap-matrix.md`.
2. Map every current requirement to exact code and test evidence.
3. Mark each row as implemented, partial, missing, conflicting, or unverified.
4. Repair the two failing research analytics tests.
5. Run the complete existing quality gate before assessment changes begin.

### 5.2 Lock the domain language

1. Create one source of truth for all required assessment enums.
2. Share or generate matching frontend types.
3. Rename the Quality Judge values to `APPROVED` and `REJECTED`.
4. Keep workflow failure terms separate from learner results.
5. Reject `FAIL`, numbers, percentages, and score bands as learner results.

### 5.3 Add the assessment data model

1. Version learning outcomes, Bloom targets, criteria, and pass rules.
2. Store exact task, prompt, source, rubric, model, and rule versions.
3. Add append-only response versions and evidence records.
4. Add provisional decisions and result lifecycle states.
5. Add assessor confirmation, correction, override, withholding, and void records.
6. Require reasons and actors for consequential changes.
7. Add database constraints for course scope and valid lifecycle transitions.
8. Create a forward migration for existing score and pass/fail records.
9. Preserve source values in protected migration history.
10. Do not convert numeric scores to `PASS` without an approved mapping.

### 5.4 Add roles, permissions, and scope controls

1. Add explicit assessor permission.
2. Add separately approved research access.
3. Define who may design, publish, review, confirm, override, void, or reassign assessments.
4. Enforce student self-access and educator or assessor course scope in queries and services.
5. Add cross-student, cross-course, cross-role, and research-isolation tests.

### 5.5 Complete educator and assessor setup

1. Expand outcomes with learner wording, ownership, approval, sources, and prerequisites.
2. Add Bloom process and knowledge dimensions.
3. Add claims, observable evidence, mandatory criteria, and pass rules.
4. Add supported versus independent evidence settings.
5. Add permitted tools, instructional support, and access conditions.
6. Add parallel task forms and transfer rules.
7. Show version and approval history.
8. Block publication when required fields or approvals are missing.

### 5.6 Complete task and simulation support

1. Add the missing task types and typed response contracts.
2. Provide draft, submit, evidence extraction, evaluation, and export support for each type.
3. Add accessible labels, help text, errors, focus behaviour, and keyboard controls.
4. Keep code formatting across the UI, API, database, feedback, and export.
5. Bound Qiskit circuit size, shots, runtime, and resource use.
6. Store circuit, simulator, count, probability, shot, and error evidence.
7. Generate matching visual and text representations.
8. Preserve accepted learner work after every simulation fault.

### 5.7 Complete evidence, feedback, and learner modelling

1. Capture all response versions and learning interactions without overwriting earlier evidence.
2. Keep observations separate from system inferences.
3. Store uncertainty, recency, model version, prior state, and supporting evidence.
4. Allow learner annotation and educator correction.
5. Prevent diagnosis, fixed ability labels, and unsupported learner claims.
6. Extend feedback checks to Bloom and evidence-rule alignment.
7. Keep all generation, regeneration, judge, fallback, cost, and version records.

### 5.8 Implement formal binary assessment

1. Evaluate each approved criterion against one exact response version.
2. Link every criterion decision to evidence and a reason.
3. Apply the stored pass rule deterministically.
4. Produce only provisional `PASS` or `INCOMPLETE` results.
5. Exclude confidence, time, retries, hints, access support, demographics, and research condition.
6. Do not issue `INCOMPLETE` when a system or task fault prevents valid assessment.
7. Add deterministic replay, idempotency, stale-version, and fault tests.
8. Implement AT1 to AT14 and AT20 to AT23.

### 5.9 Implement human review and reassessment

1. Build an assessor queue with course, outcome, result, state, reason, and age filters.
2. Show the full evidence and versions before an assessor acts.
3. Require reasons for override, withholding, and void actions.
4. Make duplicate finalisation safe.
5. Show learners the result, lifecycle, Bloom target, evidence, gaps, and next action.
6. Add a human review or correction request path.
7. Use a fresh approved form for reassessment.
8. Keep all earlier results and do not average attempts.
9. Implement AT15 to AT19 and AT24.

### 5.10 Complete adaptation, progress, gamification, and research

1. Add evidence-based adaptation with visible reasons and uncertainty.
2. Allow learner and educator overrides of non-essential suggestions.
3. Keep the assessment standard fixed during adaptation.
4. Add the full misconception hypothesis, probe, revision, transfer, and correction flow.
5. Separate observed activity, inference, progress, and formal results in dashboards.
6. Remove fake pass averages and numeric mastery labels.
7. Make gamification optional and neutral to assessment outcomes.
8. Add course time zones, extensions, access plans, and learner preferences to reminders.
9. Add research consent, withdrawal, missing-data, retention, and field-approval controls.
10. Prove that research refusal or condition never changes teaching access or results.

### 5.11 Complete release and pilot evidence

1. Run formatting, lint, type, static, unit, integration, browser, security, and coverage checks.
2. Reach at least 80 percent backend service statement coverage.
3. Run 50-user latency and 100-user scale tests.
4. Test retries, restarts, external LLM timeouts, Qiskit faults, and database contention.
5. Verify backup and restore completeness.
6. Measure cost per complete learning loop.
7. Test Chrome, Edge, Firefox, Safari, keyboard, zoom, reflow, and screen readers.
8. Record manual accessibility results instead of relying only on automated tools.
9. Validate the evaluator against an approved accuracy, fairness, and edge-case dataset.
10. Disable formal automatic assessment or require human confirmation until the release gate passes.

## 6. Pilot decisions still required

The documents require human approval for these policy choices:

1. Which users may hold assessor permission.
2. Whether learners see provisional system results before assessor review.
3. How many independent observations each outcome requires.
4. Which assessment results allow reassessment.
5. Whether the latest valid attempt replaces an earlier result.
6. Which criteria are mandatory for each outcome.
7. Which tools, supports, and access conditions apply to each task.
8. Which actions trigger required human review.
9. How long learning, assessment, audit, and research records are retained.
10. How consent, withdrawal, and missing data work during the pilot.
11. The approved reuse target for NFR24.
12. Assessment evaluator accuracy and fairness release thresholds.
13. The final escalation owner and response time.

These decisions must be recorded as named blockers. They must not be hidden in prompts, constants,
fixtures, or default branches.

## 7. Required pilot documents

The following documents must be created or updated before pilot readiness:

1. Implementation gap matrix.
2. Architecture and data-flow note.
3. Environment and model configuration guide.
4. Database migration and rollback guide.
5. Assessor setup guide.
6. Student result and review guide.
7. Accessibility test record.
8. Security and privacy test record.
9. Load, recovery, and cost test record.
10. Research export data dictionary.
11. Requirement traceability report.
12. Known limits and deferred policy decisions.

## 8. Verification snapshot

The following checks were run during this audit:

| Check | Result |
| --- | --- |
| Backend tests | 381 passed, 2 failed |
| Frontend tests | 59 passed |
| Ruff lint | Passed |
| Ruff formatting | Passed for 229 files |
| Frontend ESLint | Passed |
| TypeScript and production build | Passed |
| Browser end-to-end suite | Not run |
| Coverage release gate | Not run |
| Dependency audits | Not run |
| Load and scale tests | Not run |
| Manual accessibility tests | Not run |

The two backend failures are:

- `tests/test_analytics_application.py::test_sql_analytics_use_half_open_filters_roster_and_terminal_research`
- `tests/test_person4_e2e.py::test_person4_deterministic_end_to_end`

Both failures concern research rate metrics returning `None` instead of the expected value.

## 9. Recommended first implementation batch

The first batch should contain only these steps:

1. Create the complete implementation gap matrix.
2. Repair the two failing research analytics tests.
3. Run the complete existing quality gate.
4. Write an approved implementation plan for the shared assessment enums.
5. Design the numeric-score migration before changing the database or UI.

This order restores a known baseline before changing assessment policy or stored learner records.
