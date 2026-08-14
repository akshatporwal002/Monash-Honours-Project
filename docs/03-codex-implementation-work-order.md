# Codex implementation work order

Status: executable work order

Last updated: 2026-08-14

## 1. Objective

Audit the existing LearnLens code and implement every missing or conflicting requirement in this folder. Keep correct features. Repair partial features. Add tests and traceability for every change.

Read these files first:

1. [`01-implementation-requirements.md`](./01-implementation-requirements.md)
2. [`02-pass-incomplete-bloom-assessment-spec.md`](./02-pass-incomplete-bloom-assessment-spec.md)
3. This work order

The source PDFs and blueprint explain the product intent. The two files above control implementation when wording conflicts.

## 2. Product rules Codex must preserve

- Assessment results are only `PASS` and `INCOMPLETE`.
- A negative rule result maps to `INCOMPLETE`, not learner-facing `FAIL`.
- The assessor sets the target Bloom process and approved evidence rules.
- The system checks those rules and creates a provisional binary result.
- Formal results need authorised assessor control.
- No numeric marks, percentages, weights, grade bands, or GPA values are part of formal assessment.
- Learning evidence, model estimates, progress states, research measures, and points stay separate from assessment results.
- A Bloom label alone cannot grade a response.
- The same standard applies across learners. Access support does not lower it.
- Formative help, time, confidence, attempts, breaks, and research choice cannot reduce a result.
- Direct evidence and system inference must be stored and shown separately.
- No learner diagnosis or protected stereotype may be inferred or stored in the learner model.

## 3. Working rules for Codex

### 3.1 Start with evidence

Do not assume a feature exists because a page, route, type, or database table has its name. Prove behaviour with code paths and tests.

For each requirement, record:

- Status: `IMPLEMENTED`, `PARTIAL`, `MISSING`, `CONFLICTING`, or `UNVERIFIED`.
- Frontend file paths.
- Backend file paths.
- Data model and migration paths.
- Test paths and named test cases.
- Runtime or manual proof.
- Gap and planned change.

### 3.2 Preserve user work

- Inspect the worktree before editing.
- Do not discard unrelated changes.
- Use forward database migrations.
- Back up or fixture-test data conversions.
- Keep old records readable until the migration is verified.
- Use feature flags for risky assessment changes.

### 3.3 Make small, verified changes

- Work in dependency order.
- Add or update tests with each feature.
- Run the smallest useful checks after each edit.
- Run the full release checks before handoff.
- Report what was not tested.

### 3.4 Avoid hidden policy

Do not hard-code an unapproved rule for evidence count, reassessment, retention, human review, or learner visibility. Use explicit configuration with safe defaults and a clear owner.

## 4. Phase 0: inspect and map the current code

### 4.1 Repository map

Find and document:

- Package manager and workspace layout.
- Frontend entry point, route system, state management, and design system.
- Backend entry point, routers, services, schemas, and background jobs.
- Authentication and role checks.
- Database engine, models, migration tool, and seed data.
- Agent, LLM, RAG, Qiskit, and Quality Judge code.
- Task, submission, evidence, feedback, progress, and analytics code.
- Existing assessment, rubric, score, grade, pass, or fail code.
- Test tools, fixtures, CI, lint, type, security, and coverage setup.
- Deployment and environment settings.

### 4.2 Required searches

Search code, database models, prompts, tests, fixtures, docs, and exports for:

```text
score
mark
grade
percentage
weight
points
band
gpa
pass
fail
failed
mastery
bloom
rubric
assessment
submission
attempt
result
confidence
hint
scaffold
diagnosis
neurodivergent
disability
demographic
```

Classify each match. Qiskit probabilities, model confidence, quality metrics, research values, and optional game points may remain. Rename any value that could be mistaken for a learner grade.

### 4.3 Required first deliverable

Create `docs/learnlens/implementation-gap-matrix.md` with this table:

| Requirement | Status | Existing proof | Gap | Planned change | Tests |
| --- | --- | --- | --- | --- | --- |
| FR1 |  |  |  |  |  |

Include FR1 to FR39, PD1 to PD12, BP1 to BP15, NFR1 to NFR31, AC1 to AC22, and AT1 to AT24.

Do not begin broad rewrites until this matrix exists. Small diagnostic fixes are allowed when needed to run the project.

## 5. Phase 1: lock the domain language

### 5.1 Add shared enums

Create one source of truth for:

- `AssessmentResult`
- `ResultState`
- `SubmissionState`
- `AssessmentPurpose`
- `BloomProcess`
- `BloomKnowledge`
- `CriterionDecision`
- `QualityReviewDecision`
- `MisconceptionState`

Generate or share types across the frontend and backend when the stack supports it.

### 5.2 Prevent namespace conflicts

The following values are different concepts:

- Learner assessment: `PASS` or `INCOMPLETE`.
- Quality Judge: `APPROVED` or `REJECTED`.
- Request execution: `SUCCEEDED` or `FAILED`.
- Submission state: draft, submitted, under review, and related states.
- Learner model: uncertain progress estimates.

Do not reuse one status field for these areas.

### 5.3 Phase 1 gate

- Invalid enum writes fail at API and database layers.
- The UI uses the same labels.
- `FAIL` cannot be created as a learner result.
- Existing code compiles or type-checks.
- Enum unit tests pass.

## 6. Phase 2: database and migration

### 6.1 Add or extend records

Implement the data groups from Section 7 of the main requirements. Reuse current tables where their meaning is correct.

Prioritise:

- Versioned learning outcomes.
- Bloom targets.
- Criteria and pass rules.
- Task models and forms.
- Submission and response versions.
- Learning evidence.
- Instructional support and access conditions.
- Assessment attempts and decisions.
- Assessor review and override.
- Agent, judge, retrieval, and audit versions.

### 6.2 Required constraints

- Formal result enum check.
- Approved assessment requires Bloom and pass-rule versions.
- Confirmed result requires assessor, action, and time.
- Override requires the old decision and reason.
- Decision references one exact response version.
- Foreign keys enforce course, outcome, task, and attempt links.
- Unique keys prevent duplicate submission and evaluation events.
- Research mapping is separate from operational identity.

### 6.3 Migrate old grade data

Follow Section 19 of the assessment specification.

Do not convert a numeric value to `PASS` without an approved mapping. Convert old public `FAIL` to `INCOMPLETE` and retain the source value in protected migration history.

### 6.4 Migration proof

Test:

- Empty database upgrade.
- Database with old pass/fail records.
- Database with numeric records.
- Duplicate and stale events.
- Rollback or recovery plan.
- Record counts and relationship integrity.
- API reads before and after compatibility changes.

### 6.5 Phase 2 gate

- Migration runs twice without duplicate effects where supported.
- All constraints work.
- No accepted learning record is lost.
- Old and new fixture counts match expected results.
- Backup and restore verification passes.

## 7. Phase 3: roles, scope, and security

### 7.1 Add assessor permission

Use a permission, not a hidden check on the educator role. Define who can:

- Design assessment rules.
- Publish assessed tasks.
- Review evidence.
- Confirm results.
- Override or void decisions.
- Approve reassessment.

### 7.2 Enforce course scope

Apply access checks in the service and query layer, not only in the UI.

Test student self-access, educator course scope, assessor course scope, admin rights, and separate research access.

### 7.3 Security controls

- Hash credentials with the current approved method.
- Keep secrets out of source and logs.
- Validate and limit uploads.
- Validate all typed API input.
- Use HTTPS in hosted use.
- Limit Qiskit circuit size, shots, runtime, and resource use.
- Add rate limits or job limits to costly AI and simulation routes.
- Record safe audit events without full answer text.

### 7.4 Phase 3 gate

- All protected-route tests pass.
- Cross-student and cross-course tests pass.
- No direct identifier leaks in logs.
- No open critical or high security finding remains.

## 8. Phase 4: course, source, outcome, and assessment setup

### 8.1 Course and material flow

Complete create, edit, publish, archive, upload, link, parse, index, and source-status paths. Keep source versions and retrieval ownership.

### 8.2 Outcome blueprint

Build assessor controls for:

- Outcome wording and source.
- Prerequisites and bypass.
- Bloom process and knowledge dimension.
- Claim and evidence rules.
- Mandatory criteria.
- Pass rule.
- Task forms.
- Tool and support rules.
- Access conditions.
- Transfer and evidence-sufficiency rules.
- Version and approval state.

### 8.3 Validation

Block publication when:

- The assessment has no Bloom target.
- The task does not elicit the target process.
- Criteria or pass rule are missing.
- A source or outcome is unapproved.
- An access mode changes the intended construct.
- A task form has no approved version.

### 8.4 Phase 4 gate

- A first-time educator completes the SRS setup trial within 20 minutes.
- An assessed task cannot publish with an incomplete blueprint.
- Version history is visible and tested.
- AT4, AT5, and AT6 pass.

## 9. Phase 5: task engine and Qiskit evidence

### 9.1 Task type contract

Each task type needs:

- Typed prompt and response data.
- UI renderer.
- Draft and submit validation.
- Evidence extractor.
- Evaluator adapter.
- Accessible name, help, and error behaviour.
- Export format.
- Unit and full-path tests.

### 9.2 Qiskit controls

- Create circuits from validated data.
- Keep learner code or circuit input separate from server control code.
- Set circuit, shot, and time limits.
- Store Qiskit and simulator versions.
- Save counts, probabilities, shots, and error details.
- Create visual and text output from one circuit and result object.
- Collect prediction before reveal when required.
- Keep the learner draft after every fault.

### 9.3 Phase 5 gate

- All required task types work through save and submit.
- Code formatting survives storage and display.
- Circuit visual and text forms agree.
- Invalid simulation tests lose no accepted work.
- FR9, FR13, FR14, AC3, and AC17 tests pass.

## 10. Phase 6: evidence, feedback, and learner model

### 10.1 Append-only evidence

Capture every response version and linked interaction. Do not overwrite old evidence.

Each item needs learner, course, outcome, activity, task form, response version, evidence type, source interaction, conditions, and time.

### 10.2 Feedback pipeline

1. Gather approved sources and simulation evidence.
2. Generate feedback from the response and learning context.
3. Check factual and learning quality.
4. Regenerate once after rejection.
5. Use a safe fallback after a second rejection.
6. Keep all calls, reasons, versions, and costs.

### 10.3 Learner model

- Build a new snapshot from linked evidence.
- Keep observation and inference separate.
- Store uncertainty, recency, model version, and prior state.
- Permit learner annotation and educator correction.
- Never store a diagnosis or fixed learning-style label.
- Do not use the model estimate as a formal result.

### 10.4 Phase 6 gate

- A complete AAYL episode is visible in time order.
- Old evidence remains after revision.
- Judge retry and fallback tests pass.
- Inference always links to evidence and uncertainty.
- Safety tests find no banned diagnosis or stereotype.

## 11. Phase 7: Bloom evaluator and binary result engine

### 11.1 Separate evidence evaluation from the pass rule

The evaluator decides whether each criterion is `MET`, `NOT_MET`, or `NOT_EVALUABLE`. The rules engine then applies the stored Boolean pass rule.

Do not let an LLM return only a final grade.

### 11.2 Evaluation input

Use only:

- Exact response version.
- Approved outcome and task versions.
- Bloom target.
- Approved criteria and anchors.
- Allowed source and simulation evidence.
- Declared tool and support conditions.
- Access conditions.

Exclude research condition, demographic data, confidence, time, attempts, and game points from the formal pass rule.

### 11.3 Evaluation output

Store:

- Criterion decisions.
- Evidence links.
- Short reasons.
- Evaluator type and version.
- Evaluator confidence, when used.
- Pass-rule version.
- Provisional `PASS` or `INCOMPLETE`.
- Stable reason code.
- Quality Judge result.

### 11.4 Fault handling

Do not issue `INCOMPLETE` when a system or task fault prevents valid assessment. Keep review state or void the attempt.

### 11.5 Phase 7 gate

- AT1 to AT14, AT20 to AT23 pass.
- Repeated evaluation is deterministic under the same versions.
- Numeric grade fields are absent from result responses.
- An `ANALYSE` target cannot pass on recall-only evidence.
- The system provides useful incomplete reasons without giving away the next answer.

## 12. Phase 8: assessor review and learner result views

### 12.1 Review queue

Build filters for course, outcome, result, result state, flagged reason, and age. Show evidence and versions before action.

Require a reason for override, withholding, or void action. Make duplicate finalisation safe.

### 12.2 Learner result

Show:

- `PASS` or `INCOMPLETE`.
- Provisional or confirmed state.
- Target Bloom process in plain language.
- Criteria met and still needed.
- Evidence used.
- Next allowed action.
- Review request.

Do not use colour alone. Do not show `FAIL` or a numeric mark.

### 12.3 Phase 8 gate

- AT15, AT16, AT17, AT19, and AT24 pass.
- All assessor actions are audited.
- Learner result views pass keyboard, focus, zoom, and screen-reader checks.

## 13. Phase 9: reassessment, adaptation, and misconception flows

### 13.1 Reassessment

Use a new approved form under the same outcome and standard. Keep all earlier decisions. Do not average attempts.

### 13.2 Adaptation

Allow the learning path to change within approved bounds. Keep target Bloom and pass criteria fixed. Store the trigger, reason, uncertainty, versions, and override.

### 13.3 Misconception

Implement hypothesis, confirmatory probe, alternate explanation, revision, transfer, and final hypothesis-state flow. Include contradicting evidence and educator correction.

### 13.4 Phase 9 gate

- AT18 passes.
- Seeded evidence causes the expected adaptation without changing the grade rule.
- A possible misconception is never stored as a certain diagnosis after one wrong answer.
- Learner and educator override tests pass.

## 14. Phase 10: progress, reminders, gamification, and research

### 14.1 Progress views

Show activity, evidence, inference, and formal results in separate areas. Do not make a fake pass average.

### 14.2 Reminders

Use the course time zone, due date, extension, and latest completion. Enforce one reminder per task per 24 hours.

### 14.3 Gamification

Keep it optional and separate from results. Do not rank learners or penalise support and pace choices.

### 14.4 Research

- Use pseudonymous IDs.
- Store condition separately from production decisions.
- Add approved consent and withdrawal state.
- Record missing-data reasons.
- Export only approved fields.
- Include source, model, prompt, judge, simulation, latency, token, and cost versions.
- Keep educational outcome tests separate from technical LLM quality tests.

### 14.5 Phase 10 gate

- The same evidence gets the same result across research conditions.
- Research refusal does not change access, adaptation, or result.
- Export completeness tests pass.
- No direct ID appears in the research file.

## 15. Phase 11: non-functional release gates

### 15.1 Quality checks

Run all configured:

- Formatting checks.
- Lint checks.
- Frontend and backend type checks.
- Static analysis.
- Unit tests.
- Integration tests.
- Full browser tests.
- Security scans.
- Accessibility tests.
- Coverage reports.

Target zero configured errors and at least 80 percent backend service statement coverage.

### 15.2 Load and fault tests

Prove:

- SRS latency targets at 50 users.
- Scale behaviour to 100 users.
- Retry and idempotency behaviour.
- Restart recovery.
- External LLM timeout fallback.
- Qiskit failure recovery.
- Database contention and attempt ordering.
- Backup restore completeness.
- Cost per full learning loop.

### 15.3 Browser and access checks

Test the latest available Chrome, Edge, Firefox, and Safari. Test keyboard, focus, labels, errors, contrast, zoom, reflow, screen readers, and circuit text alternatives.

Automated access tools are not enough. Record manual checks.

### 15.4 Phase 11 gate

Every NFR has saved proof or a named open exception. Build success and an HTTP 200 check are not enough.

## 16. Phase 12: pilot readiness and handoff

### 16.1 Required documents

Update or create:

- Implementation gap matrix.
- Architecture and data-flow note.
- Environment and model configuration guide.
- Database migration and rollback guide.
- Assessor setup guide.
- Student result and review guide.
- Accessibility test record.
- Security and privacy test record.
- Load, recovery, and cost test record.
- Research export data dictionary.
- Requirement traceability report.
- Known limits and deferred policy decisions.

### 16.2 Pilot settings that need approval

Confirm and record:

- Assessor assignment rules.
- Result visibility before confirmation.
- Evidence-sufficiency rules by outcome.
- Reassessment rule.
- Human-review triggers.
- Access and tool conditions.
- Retention and deletion rules.
- Consent, withdrawal, and missing-data rules.
- Evaluator release thresholds.
- Escalation owner and response target.
- Reuse test target for NFR24.

### 16.3 Final gate

The pilot is ready only when:

- All required gap-matrix rows have proof.
- AC1 to AC22 pass.
- AT1 to AT24 pass.
- PD1 to PD12 and BP1 to BP15 have implementation proof.
- Applicable NFR targets pass.
- No open critical access, security, privacy, data-loss, or grade-validity fault remains.
- Formal assessment is disabled or human-confirmed until the AI evaluator release gate passes.

## 17. Test structure Codex should create

Adapt names to the current stack.

### 17.1 Unit tests

- Enum and schema validation.
- Bloom and task alignment rules.
- Criterion evaluation adapters.
- Boolean pass rules.
- Incomplete reason selection.
- Result lifecycle transitions.
- Reassessment current-result rule.
- Reminder timing.
- Pseudonym and export-field filters.

### 17.2 Integration tests

- Role and course scope.
- Course and outcome setup.
- Material intake and retrieval.
- Submission idempotency.
- Qiskit execution and fault handling.
- Feedback judge retry and fallback.
- Evidence append and model snapshot.
- Provisional evaluation and assessor confirmation.
- Override and audit history.
- Research export and withdrawal.

### 17.3 Browser tests

- Student full AAYL loop.
- Assessor creates and publishes a Bloom-based assessment.
- Student gets `PASS`.
- Student gets `INCOMPLETE` and starts reassessment.
- Assessor confirms and overrides results.
- Learner requests review.
- Keyboard-only circuit and result paths.
- Screen-reader labels and live status.
- Cross-role navigation denial.

### 17.4 Safety and evaluator tests

- Unsupported diagnosis or fixed-ability claims.
- Bias and stereotype prompts.
- Answer leakage.
- Ungrounded quantum claims.
- Incorrect Qiskit API advice.
- Recall-only response for a higher-process target.
- Unusual but valid reasoning.
- Short correct response.
- Alternate accessible response.
- Prompt injection inside uploaded material or learner text.

## 18. Completion report format

Codex must finish each work batch with:

```markdown
## Outcome

What now works.

## Requirements completed

- FR or AT ID, with file and test evidence.

## Existing behaviour preserved

- Feature and proof.

## Data changes

- Migration, backfill, compatibility, and rollback notes.

## Verification

- Check name and result.
- Manual checks and result.

## Open items

- Requirement, reason, owner, and next action.

## Limits

- What was not tested or cannot yet be claimed.
```

Do not say a feature is complete when only a component test passed. State the exact scope of proof.

## 19. Copy-ready kickoff prompt for Codex

```text
Read docs/learnlens/01-implementation-requirements.md,
docs/learnlens/02-pass-incomplete-bloom-assessment-spec.md, and
docs/learnlens/03-codex-implementation-work-order.md in full.

This is an existing LearnLens codebase. First inspect the repository and create
docs/learnlens/implementation-gap-matrix.md. Map FR1-FR39, PD1-PD12,
BP1-BP15, NFR1-NFR31, AC1-AC22, and AT1-AT24 to exact code and tests.
Mark each item implemented,
partial, missing, conflicting, or unverified.

Do not begin a broad rewrite. Preserve working features and unrelated changes.
Then implement the first incomplete dependency group in the work order. Add tests
with each change and run the checks that prove the behaviour.

The controlling assessment rule is binary. Only PASS and INCOMPLETE may be
stored or shown as learner assessment results. The assessor sets the Bloom
target and approved evidence rules. The system applies those rules and creates a
provisional result. Formal results require authorised assessor control. Do not
add numeric marks, percentages, grade bands, or GPA fields.

At the end, update the gap matrix and report exact files, migrations, tests,
manual checks, open items, and limits.
```
