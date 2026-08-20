# LearnLens known limits and deferred decisions

Status: pending owner decisions

Last reviewed: 2026-08-19

## Purpose

This register records policy and evidence decisions that cannot be inferred from code, prompts,
fixtures, or defaults. It supports Step 1 of
[`005-remaining-feature-roadmap.md`](../plans/005-remaining-feature-roadmap.md).

It does not approve a policy, enable a feature, or make a pilot-readiness claim. A `PENDING` entry
blocks the dependent behaviour wherever the controlling requirements require an explicit decision.

## Fixed controlling rules

The following are already decided and must not be reopened through this register:

- Formal learner results are only `PASS` or `INCOMPLETE`.
- Numeric marks, percentages, grade bands, GPA, and public `FAIL` are not learner assessment
  results.
- Assessors approve the Bloom target, evidence criteria, and pass rule before an assessed attempt.
- A system result is provisional until an authorised assessor confirms, overrides, withholds, or
  voids it.
- Research condition, consent, demographics, confidence, time, retries, hints, access support,
  points, progress, and learner-model inference cannot change a formal assessment result.
- Operational identity, learning evidence, learner-model inference, formal assessment, and
  research data remain separately scoped.

Sources: `docs/01-implementation-requirements.md:17-32`,
`docs/02-pass-incomplete-bloom-assessment-spec.md:11-24`, and
`docs/learnlens/person-a-person-b-contract.md:40-112`.

## Decision register

| ID | Decision | Status | Required owner | Evidence or approval required | Dependent work blocked |
| --- | --- | --- | --- | --- | --- |
| D-01 | Whether learners can see a provisional formal result before assessor action | `PENDING` | Product owner and assessors | Named policy, learner wording, effective version, and approval date | Learner result visibility and final wording in Plan 005 Step 2; AT19 and AT24 completion |
| D-02 | Which users may receive course-scoped assessor permission | `PENDING` | Product owner | Role-assignment policy, approver, course-scope rule, and effective version | Production assessor assignment and pilot-ready role claim; FR1, FR38, AT17 |
| D-03 | Which users may receive separately approved research permission | `PENDING` | Product owner and research governance | Research-access policy, authorised roles, scope, and effective version | Production research assignment; FR20 and research-governance activation |
| D-04 | Outcome-specific mandatory criteria and evidence-sufficiency rules | `PENDING` | Assigned assessors | Approved outcome, criteria, pass rule, evidence-sufficiency rule, and version | Publication of real assessed outcomes and task forms; FR6, FR8, BP2-BP3, AT4-AT9 |
| D-05 | Permitted tools, instructional support, access conditions, and transfer rules for each assessed task | `PENDING` | Assigned assessors | Approved task-form conditions and construct-equivalence rationale | Publication of real assessed task forms; BP5-BP6, AT11-AT14 |
| D-06 | Reassessment eligibility, equivalent-form rule, review triggers, and current-result selection | `PENDING` | Product owner and assessors | Versioned reassessment policy and approval date | Reassessment activation; AT18 and AT21 |
| D-07 | AI evaluator dataset, agreement statistic, fairness review, and release thresholds | `PENDING` | Assessment governance | Approved evaluation protocol, dataset definition, statistic, threshold, and release decision | Automated evaluator release; BP10-BP11 and NFR12-NFR14 |
| D-08 | Assessment, audit, and research retention, withdrawal, deletion, and missing-data rules | `PENDING` | Privacy owner and research governance | Approved data plan, consent version, retention schedule, withdrawal handling, and effective version | Destructive lifecycle actions, live participant enrolment, and final privacy/pilot claim; BP12-BP14, NFR16, NFR25, NFR30 |
| D-09 | Human escalation owner, severity mapping, and response/service target | `PENDING` | Product owner and operations | Approved escalation policy, assignment queue, target, and effective version | Escalation service-level claim; PD7 and NFR20 |
| D-10 | Legacy numeric-score compatibility window and client-version shutdown plan | `PENDING` | Product owner and technical owner | Approved compatibility period, affected clients, migration notice, and retirement date | Final legacy-column removal and old-client shutdown; Plan 005 Step 3 and AT1-AT3 |
| D-11 | Approved NFR24 reuse target | `PENDING` | Product owner | Approved second-subject reuse measure and threshold | NFR24 completion claim |
| D-12 | Approved environments and reviewers for native Safari, screen-reader, manual zoom, hosted availability, load, cost, and usability evidence | `PENDING` | Accessibility, operations, and product owners | Named environment, reviewer, schedule, and evidence location | NFR1-NFR8, NFR18, NFR22, AC17, AC18, and pilot-ready claim |

## Recording an approval

Before an entry changes from `PENDING`, add an approval record with:

1. Decision ID and exact policy value.
2. Named decision owner and approver.
3. Source artefact or meeting record.
4. Effective version and date.
5. Affected courses, outcomes, task forms, roles, or studies.
6. Required implementation plan, acceptance tests, migration or compatibility effect, and audit
   record.

Do not record learner identities, full responses, credentials, or sensitive research data in this
document.

## Implementation guardrails

- An unset decision remains visible and blocks only the feature that depends on it.
- Test fixtures may exercise policy machinery using explicit test values, but they do not approve
  production policy.
- A code default must fail closed where a decision controls formal assessment, research access,
  retention/deletion, or pilot release.
- Any future implementation must link the selected policy version to the relevant audit and
  evidence records.

## Current limits

- Learner result visibility and reassessment are not ready to implement as active course features
  until D-01 and D-06 are approved.
- Real assessed outcomes and forms cannot publish until D-04 and D-05 are approved.
- Automated evaluation remains advisory until D-07 is approved and validated.
- Destructive retention, deletion, and live research-governance actions remain disabled or blocked
  until D-08 is approved.
- Full pilot readiness remains unverified until D-02, D-03, D-07, D-08, D-09, and D-12 have
  evidence-backed resolution.

## Source references

- `docs/plans/004-remaining-work-and-merge-readiness.md:102-132`
- `docs/plans/002-person-a-assessment-implementation.md:1516-1534`
- `docs/plans/001-person-b-platform-implementation.md:1775-1792`
- `docs/01-implementation-requirements.md:17-32`
- `docs/02-pass-incomplete-bloom-assessment-spec.md:11-24`
