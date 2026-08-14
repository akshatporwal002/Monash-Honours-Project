# LearnLens Person A / Person B assessment handoff contract

Status: `BLOCKED` pending Person A A1 contract freeze and approval

Recorded: 2026-08-14

Person B branch: `codex/person-b-platform`

Controlling handoff: `docs/05-two-person-implementation-split.md`, Handoff 1

## Purpose

This document is the durable handoff record between the assessment workstream owned by Person A
and the evidence/platform workstream owned by Person B. It records the contract facts that are
already fixed by the controlling specifications, the exact information that A1 must still publish,
and the gate that prevents Person B from inventing assessment types while the handoff is absent.

It is not an assessment DTO specification. Unavailable names, fields, enum members, import paths,
and compatibility rules remain explicitly unavailable rather than being guessed here.

## Current gate evidence

The handoff is not frozen in the current repository state:

- `origin/main` resolves to `52d45828f0a6e528a9a5736c4cc2a0cdc0009f6a`.
- The published remote heads observed on 2026-08-14 are `main`, `Akshat`, `Arv`, `Mahissh`, and
  `Raveen`; none contains A1.
- `src-main/backend/app/schemas/assessment.py` does not exist on `origin/main` or the Person B head.
- No checked-in Person A DTO defines the versioned assessment/evidence-reference boundary.
- No checked-in compatibility policy maps legacy Quality Judge values to the required operational
  `APPROVED` / `REJECTED` namespace.

Consequently, `src-main/backend/app/services/evidence/assessment_port.py` and its contract tests
must not be created yet. Any implementation would necessarily invent Person A-owned types or make
an unapproved compatibility decision.

## Facts fixed by the controlling specifications

These rules do not depend on missing A1 design choices and are frozen for both workstreams:

| Boundary rule | Required behaviour |
| --- | --- |
| Formal learner result | Only `PASS` or `INCOMPLETE`; Person B never constructs, calculates, changes, or confirms it. |
| Missing result | Absence of a result is distinct from `INCOMPLETE`. |
| Human control | An authorised assessor controls a formal confirmed result. |
| Quality Judge | Operational decision namespace is `APPROVED` / `REJECTED`, separate from learner results. |
| Workflow failures | Execution success/failure and retry state are separate from learner results. |
| Progress and learner model | Evidence, inference, uncertainty, and progress projections cannot become or predict a formal result. |
| Research | Condition, consent, allocation, withdrawal, and research measures cannot affect learning access, adaptation, or result. |
| Access support | May change how evidence is supplied but cannot lower the target, criteria, or pass rule. |
| Version integrity | A decision must remain tied to the exact approved task, response, source, Bloom, criterion, and rule versions used. |
| Stale references | A stale or mismatched response/task/source/rule reference is a conflict or reference-invalid outcome, never an inferred result. |

## Required A1 handoff values

Person A must replace every `UNAVAILABLE` entry with the exact checked-in symbol or policy and
provide tests proving it. Person B will then import those types read-only.

| Contract item | Required evidence | Current value |
| --- | --- | --- |
| Backend DTO import path | Importable module outside Person A ORM models | `UNAVAILABLE` |
| Learner-result enum | Exact Python symbol and wire values; invalid values rejected before service code | `UNAVAILABLE` |
| Result lifecycle enum | Exact Python symbol and wire values, including how a missing result is represented | `UNAVAILABLE` |
| Assessment definition identifier | Exact field name, type, validation, and version relationship | `UNAVAILABLE` |
| Assessment definition version | Exact field name, type, and stale-version rule | `UNAVAILABLE` |
| Approved outcome identifier/version | Exact fields and course-scope validation | `UNAVAILABLE` |
| Bloom target identifier/version | Exact fields and compatibility validation | `UNAVAILABLE` |
| Criterion/pass-rule identifier/version | Exact fields and stale-rule behaviour | `UNAVAILABLE` |
| Task identifier and task-form version | Exact fields, types, and approved-version validation | `UNAVAILABLE` |
| Attempt/submission identifier | Exact opaque reference field and scope validation | `UNAVAILABLE` |
| Response-version identifier | Exact immutable version reference and mismatch behaviour | `UNAVAILABLE` |
| Evidence-reference DTO | Exact symbol, fields, immutability contract, and schema version | `UNAVAILABLE` |
| Evidence-reference resolution result | Exact success, missing, stale, conflict, and access-denied shapes | `UNAVAILABLE` |
| Formal-result summary DTO | Exact read-only projection fields and missing-result representation | `UNAVAILABLE` |
| Quality Judge compatibility | Exact legacy read/migration policy and new `APPROVED` / `REJECTED` symbols | `UNAVAILABLE` |
| Frontend/generated contract | Exact generated symbols and drift checks | `UNAVAILABLE` |

## Forbidden formal-result inputs

The assessment port and every Person A formal-result implementation must reject or ignore these as
formal pass-rule inputs. Their presence in evidence or operational records does not authorise their
use in a result:

- Research condition, allocation, consent, withdrawal, or participation state.
- Demographic or protected-characteristic data.
- Learner, evaluator, model, or Quality Judge confidence.
- Time spent, response latency, pace, breaks, or time of day.
- Retry, attempt-count, regeneration, or failure-count data except the exact valid attempt identity
  required by an approved assessment rule.
- Hints, scaffolds, feedback exposure, formative help, or practice history.
- Gamification points, badges, levels, streaks, or rankings.
- Access-support use or accommodation status.
- Learner-model estimates, inferred strengths/gaps, misconception hypotheses, or uncertainty.
- Progress state, completion percentage, activity count, or engagement state.
- Research, provider-cost, token, latency, availability, or technical-quality measures.
- Legacy numeric score, percentage, weighted total, grade band, GPA, or threshold conversion.

## Person B port obligations after A1 is available

The eventual `assessment_port.py` must:

1. Import only Person A's frozen schema/DTO module, never `app.models.lms`, an assessment ORM
   module, `app.services.lms`, or a formal-result mutation service.
2. Accept only the exact opaque identifiers and version references frozen by A1.
3. Return an immutable, versioned evidence-reference value defined by the frozen contract.
4. Resolve references using a narrow injected provider protocol rather than an ORM session or LMS
   service dependency.
5. Expose a separate read-only formal-result summary provider solely for progress projection.
6. Prevent adaptation, learner-model, research, feedback-generation, and gamification modules from
   importing that formal-result summary provider.
7. Return typed missing, stale/conflict, access-denied, and invalid-reference outcomes without
   manufacturing `INCOMPLETE` or any other learner result.
8. Preserve the assessment/version reference even when simulation, feedback, model, or research
   processing fails.

## Required dependency tests after A1 is available

`src-main/backend/tests/test_assessment_evidence_port.py` must prove at least:

- The frozen Person A DTOs can be imported without importing an LMS or assessment ORM model.
- Evidence-reference creation and resolution preserve every required opaque ID and version.
- Returned evidence references are immutable and serialize deterministically.
- Missing is distinct from `INCOMPLETE`.
- Stale response, task, source, Bloom, criterion, or rule versions produce a typed conflict or
  reference-invalid result.
- Cross-course and unauthorised reference resolution is denied.
- Legacy Quality Judge compatibility values never deserialize as learner results.
- Person B packages do not import Person A ORM modules or formal-result mutation services.
- Only the progress projection package may import the read-only formal-result summary provider.
- Forbidden formal-result input fields cannot cross the port.

## Approval record

| Workstream | Required approval | Status |
| --- | --- | --- |
| Person A | Confirms exact DTO paths/symbols, enum values, reference/version fields, error shapes, and compatibility policy in code and tests | `PENDING` |
| Person B | Confirms the port imports only the approved DTOs and cannot construct or mutate a formal result | `PENDING A1` |

Chat agreement alone does not satisfy this record. Both approvals must refer to a checked-in commit,
and the named contract/dependency tests must pass on the integrated head.

## Unblock procedure

1. Person A publishes the A1 commit or branch and identifies its commit SHA.
2. Recheck that A1 meets the acceptance criteria in document 05 and does not expose ORM models as
   the Person B boundary.
3. Replace all `UNAVAILABLE` entries above with exact checked-in paths, symbols, fields, values,
   validation rules, and error semantics.
4. Record both workstream approvals against the same contract commit.
5. Update the implementation plan before source changes if A1 differs from the anticipated files
   or dependency direction.
6. Implement `assessment_port.py` and `test_assessment_evidence_port.py`, run targeted Ruff and
   pytest checks, and prove the Step 4 acceptance line.
7. Only then mark Step 4 complete and begin Step 5.
