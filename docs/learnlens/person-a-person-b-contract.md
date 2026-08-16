# LearnLens Person A / Person B assessment handoff contract

Status: `PERSON A APPROVED; PERSON B APPROVED`

Recorded: 2026-08-15

Person A branch: `arv-person-a-assessment`

Person B branch: `codex/person-b-platform`

Controlling handoff: `docs/05-two-person-implementation-split.md`, Handoff 1

## Purpose

This file records the assessment contract between Person A and Person B. Person A owns the
assessment language and frozen DTOs. Person B may import those DTOs as a read-only boundary.

The contract does not give Person B access to assessment ORM models or result mutation services.
It also does not let Person B infer a formal result from missing or invalid evidence.

## Current gate evidence

The A1 contract is implemented on the local Person A branch:

- Canonical enums live in `app.domain.assessment`. This module has no ORM or service imports.
- Frozen DTOs and the legacy adapter live in `app.schemas.assessment`.
- `app.schemas` uses lazy exports. Importing assessment DTOs does not load ORM modules.
- OpenAPI exports the route-independent assessment schemas as named components.
- Frontend types are generated from `src-main/contracts/openapi.json`.
- Backend contract tests pass: `9 passed` in `tests/test_assessment_contracts.py`.
- The frontend contract test, production build, and lint checks pass.

The Test Judge, Code Reviewer, and Code Quality Reviewer approved the local implementation on
2026-08-15. Person A approved contract commit `fe7c168af1397e65176ccccdb63343c0c8691bf2`.
Person B reviewed that frozen contract after integrating the Person A branch and approved its
read-only dependency direction on 2026-08-16. The current-head contract test run reported
`9 passed`; the Person B port and its dependency tests remain the next required implementation
work before Handoff 1 can be marked complete.

## Facts fixed by the controlling specifications

These rules are frozen for both workstreams:

| Boundary rule | Required behaviour |
| --- | --- |
| Formal learner result | Only `PASS` or `INCOMPLETE`; Person B never constructs, calculates, changes, or confirms it. |
| Missing result | Absence of a result is distinct from `INCOMPLETE`. |
| Human control | An authorised assessor controls a formal confirmed result. |
| Quality Judge | Operational decisions use `APPROVED` or `REJECTED`, separate from learner results. |
| Workflow failures | Execution success, failure, and retry state stay separate from learner results. |
| Progress and learner model | Evidence, uncertainty, and progress projections cannot become or predict a formal result. |
| Research | Condition, consent, allocation, withdrawal, and measures cannot affect learning access, adaptation, or result. |
| Access support | Support may change how evidence is supplied, but not the target, criteria, or pass rule. |
| Version integrity | A decision stays tied to the exact task, response, source, Bloom, criterion, and rule versions used. |
| Stale references | A stale or mismatched reference returns a typed resolution failure, never an inferred result. |

## Frozen A1 handoff values

Person B must use these exact symbols and wire values.

| Contract item | Frozen value |
| --- | --- |
| Backend DTO import path | `app.schemas.assessment` |
| ORM-free enum import path | `app.domain.assessment` |
| Learner-result enum | `AssessmentResult`: `PASS`, `INCOMPLETE` |
| Result lifecycle enum | `ResultState`: `NOT_ASSESSED`, `PROVISIONAL`, `CONFIRMED`, `OVERRIDDEN`, `VOID` |
| Submission lifecycle enum | `SubmissionState`: `NOT_STARTED`, `DRAFT`, `SUBMITTED`, `UNDER_REVIEW`, `RETURNED`, `COMPLETED` |
| Assessment purpose enum | `AssessmentPurpose`: `DIAGNOSTIC`, `FORMATIVE`, `AS_LEARNING`, `SUMMATIVE`, `RESEARCH` |
| Bloom process enum | `BloomProcess`: `REMEMBER`, `UNDERSTAND`, `APPLY`, `ANALYSE`, `EVALUATE`, `CREATE` |
| Bloom knowledge enum | `BloomKnowledge`: `FACTUAL`, `CONCEPTUAL`, `PROCEDURAL`, `METACOGNITIVE` |
| Criterion decision enum | `CriterionDecision`: `MET`, `NOT_MET`, `NOT_EVALUABLE` |
| Quality Judge enum | `QualityReviewDecision`: `APPROVED`, `REJECTED` |
| Misconception hypothesis enum | `MisconceptionState`: `PERSISTED`, `WEAKENED`, `CORRECTED`, `UNCERTAIN` |
| Assessment definition | `AssessmentVersionReference.assessment_definition_id` and `assessment_definition_version` |
| Approved outcome | `outcome_id` and `outcome_version` |
| Bloom target | `bloom_target_id` and `bloom_target_version` |
| Criteria and pass rule | `criterion_set_id`, `criterion_set_version`, `pass_rule_id`, `pass_rule_version` |
| Task and task form | `task_id` and `task_form_version` |
| Attempt and response | `assessment_attempt_id` and `response_version_id` |
| Version rules | Integer versions range from 1 through 2,147,483,647. Resolver scope checks remain Person B's duty. |
| Evidence-reference DTO | Frozen `EvidenceReference`, contract `learnlens.assessment-evidence.v1` |
| Evidence integrity | `schema_version`, `record_version`, SHA-256 `content_digest`, source record ID/version, and timezone-aware `occurred_at` |
| Resolution result | `EvidenceReferenceResolution`: `RESOLVED`, `MISSING`, `STALE`, `CONFLICT`, `ACCESS_DENIED`, `INVALID` |
| Resolution envelope | Frozen `EvidenceReferenceResolutionEnvelope` with discriminated `resolution` |
| Formal-result summary | Frozen `FormalResultSummary`; `result=None` is allowed only with `NOT_ASSESSED` |
| Quality Judge compatibility | `legacy_judge_decision_to_quality_review` maps stored `pass` to `APPROVED` and `fail` to `REJECTED` |
| Frontend generated contract | `ApiSchemas` entries with feature aliases in `features/assessment/types.ts` |
| Drift checks | `scripts/export_openapi.py --check` and `scripts/generate_frontend_contracts.py --check` |

All DTOs reject unknown fields. Evidence references and result summaries are immutable. Timestamps
must include a timezone. Opaque IDs are non-empty and use the approved safe character set.

## Forbidden formal-result inputs

The assessment port and every Person A result implementation must reject these as formal pass-rule
inputs:

- Research condition, allocation, consent, withdrawal, or participation state.
- Demographic or protected-characteristic data.
- Learner, evaluator, model, or Quality Judge confidence.
- Time spent, response latency, pace, breaks, or time of day.
- Retry, regeneration, or failure counts, except the exact valid attempt identity.
- Hints, scaffolds, feedback exposure, formative help, or practice history.
- Gamification points, badges, levels, streaks, or rankings.
- Access-support use or accommodation status.
- Learner-model estimates, inferred gaps, hypotheses, or uncertainty.
- Progress state, completion percentage, activity count, or engagement state.
- Research, provider-cost, token, latency, availability, or quality measures.
- Numeric scores, percentages, weighted totals, grade bands, GPA, or threshold conversion.

## Person B port obligations

The future `assessment_port.py` must:

1. Import `app.schemas.assessment`, never assessment ORM models or result mutation services.
2. Accept only the opaque IDs and version references in `AssessmentVersionReference`.
3. Return the frozen, versioned `EvidenceReference` value.
4. Resolve references through a narrow injected provider protocol, not an ORM session.
5. Expose a separate read-only formal-result summary provider for progress projection only.
6. Block adaptation, learner-model, research, feedback, and gamification packages from that provider.
7. Return typed missing, stale, conflict, denied, and invalid outcomes.
8. Never manufacture `INCOMPLETE` from a resolution failure.
9. Preserve the reference when simulation, feedback, model, or research processing fails.

## Required dependency tests

`src-main/backend/tests/test_assessment_evidence_port.py` must prove:

- Person A DTO imports do not import ORM models or LMS services.
- Reference creation and resolution preserve every required ID and version.
- Returned references are immutable and serialize in a stable form.
- Missing is distinct from `INCOMPLETE`.
- Stale versions produce `STALE`, `CONFLICT`, or `INVALID`, never a learner result.
- Cross-course and unauthorised resolution is denied.
- Legacy Quality Judge values never deserialize as learner results.
- Person B packages do not import result mutation services.
- Only progress projection imports the read-only result summary provider.
- Forbidden formal-result fields cannot cross the port.

## Approval record

| Workstream | Required approval | Status |
| --- | --- | --- |
| Person A | Confirms DTO paths, enums, version fields, error shapes, and compatibility policy | `APPROVED: fe7c168af1397e65176ccccdb63343c0c8691bf2` |
| Person B | Confirms the port can only import the read-only DTO contract | `APPROVED: fe7c168af1397e65176ccccdb63343c0c8691bf2 reviewed after integration on 2026-08-16` |

Chat agreement does not satisfy this record. Both approvals must name one checked-in contract
commit. The contract and dependency tests must pass on the integrated head.

## Unblock procedure

1. Person A completed Step 1 checks and the three required local agent reviews.
2. Person A checked in A1 as `fe7c168af1397e65176ccccdb63343c0c8691bf2`.
3. Have Person B review that exact contract commit and record approval here.
4. Update the implementation plan if the port differs from this dependency direction.
5. Implement `assessment_port.py` and `test_assessment_evidence_port.py`.
6. Run Ruff, pytest, OpenAPI drift, frontend drift, and dependency checks.
7. Mark Person B plan Step 4 complete only after every named check passes.
