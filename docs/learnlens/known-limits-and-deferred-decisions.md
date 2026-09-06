# LearnLens known limits and deferred decisions

Status: eleven option selections approved; D-10 approved for implementation; detailed activation records remain pending

Last reviewed: 2026-09-07

## Purpose

This register records policy and evidence decisions that cannot be inferred from code, prompts,
fixtures, or defaults. It supports Step 1 of
[`005-remaining-feature-roadmap.md`](../plans/005-remaining-feature-roadmap.md).

This register indexes recorded policy approvals and their remaining limits. It does not itself enable a feature or claim pilot readiness.
A `PENDING` entry blocks dependent behaviour where an explicit decision is required.
`SELECTION_APPROVED` records an accepted option while keeping its remaining activation requirements visible.

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
| D-01 | Whether learners can see a provisional formal result before assessor action | `SELECTION_APPROVED` | Product owner and assessors | [Approved selection](task-08-approved-selections.md#d-01); remaining detail: Named policy, learner wording, effective version, and approval date | Learner result visibility and final wording in Plan 005 Step 2; AT19 and AT24 completion |
| D-02 | Which users may receive course-scoped assessor permission | `SELECTION_APPROVED` | Product owner | [Approved selection](task-08-approved-selections.md#d-02); remaining detail: Role-assignment policy, approver, course-scope rule, and effective version | Production assessor assignment and pilot-ready role claim; FR1, FR38, AT17 |
| D-03 | Which users may receive separately approved research permission | `SELECTION_APPROVED` | Product owner and research governance | [Approved selection](task-08-approved-selections.md#d-03); remaining detail: Research-access policy, authorised roles, scope, and effective version | Production research assignment; FR20 and research-governance activation |
| D-04 | Outcome-specific mandatory criteria and evidence-sufficiency rules | `SELECTION_APPROVED` | Assigned assessors | [Approved selection](task-08-approved-selections.md#d-04); remaining detail: Approved outcome, criteria, pass rule, evidence-sufficiency rule, and version | Publication of real assessed outcomes and task forms; FR6, FR8, BP2-BP3, AT4-AT9 |
| D-05 | Permitted tools, instructional support, access conditions, and transfer rules for each assessed task | `SELECTION_APPROVED` | Assigned assessors | [Approved selection](task-08-approved-selections.md#d-05); remaining detail: Approved task-form conditions and construct-equivalence rationale | Publication of real assessed task forms; BP5-BP6, AT11-AT14 |
| D-06 | Reassessment eligibility, equivalent-form rule, review triggers, and current-result selection | `SELECTION_APPROVED` | Product owner and assessors | [Approved selection](task-08-approved-selections.md#d-06); remaining detail: Versioned reassessment policy and approval date | Reassessment activation; AT18 and AT21 |
| D-07 | AI evaluator dataset, agreement statistic, fairness review, and release thresholds | `SELECTION_APPROVED` | Assessment governance | [Approved selection](task-08-approved-selections.md#d-07); remaining detail: Approved evaluation protocol, dataset definition, statistic, threshold, and release decision | Automated evaluator release; BP10-BP11 and NFR12-NFR14 |
| D-08 | Assessment, audit, and research retention, withdrawal, deletion, and missing-data rules | `SELECTION_APPROVED` | Privacy owner and research governance | [Approved selection](task-08-approved-selections.md#d-08); remaining detail: Approved data plan, consent version, retention schedule, withdrawal handling, and effective version | Destructive lifecycle actions, live participant enrolment, and final privacy/pilot claim; BP12-BP14, NFR16, NFR25, NFR30 |
| D-09 | Human escalation owner, severity mapping, and response/service target | `SELECTION_APPROVED` | Product owner and operations | [Approved selection](task-08-approved-selections.md#d-09); remaining detail: Approved escalation policy, assignment queue, target, and effective version | Escalation service-level claim; PD7 and NFR20 |
| D-10 | Legacy numeric-score compatibility window and client-version shutdown plan | `APPROVED_FOR_IMPLEMENTATION` | Requesting user, through this conversation | [Recorded retirement decision](../../.scratch/learnlens-pilot-readiness/issues/11-legacy-score-retirement.md#answer), including scope, version, effective date, and verification requirements | Policy choice settled; final legacy-column removal and old-client shutdown still require implementation and validation |
| D-11 | Approved NFR24 reuse target | `SELECTION_APPROVED` | Product owner | [Approved selection](task-08-approved-selections.md#d-11); remaining detail: Approved second-subject reuse measure and threshold | NFR24 completion claim |
| D-12 | Approved environments and reviewers for native Safari, screen-reader, manual zoom, hosted availability, load, cost, and usability evidence | `SELECTION_APPROVED` | Accessibility, operations, and product owners | [Approved selection](task-08-approved-selections.md#d-12); remaining detail: Named environment, reviewer, schedule, and evidence location | NFR1-NFR8, NFR18, NFR22, AC17, AC18, and pilot-ready claim |

## Recording an approval

The [approved selections](task-08-approved-selections.md) record the user's explicit choice of D-05 B,
D-07 C, and A for every other offered decision, effective for implementation planning on 2026-09-07.
`SELECTION_APPROVED` means the offered option is settled. It does not mean every scoped activation requirement is satisfied.
The [decision package](task-08-decision-package.md) retains other detailed proposals and outstanding evidence.
Do not ask the user to choose the same options again. No runtime policy is enabled by these documents.

Before an entry receives full activation approval, complete its record with:

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

The [legacy retirement decision](../../.scratch/learnlens-pilot-readiness/issues/11-legacy-score-retirement.md#answer) records the user's explicit implementation approval.
Its full policy and scope live in that ticket. It does not approve deletion of protected history or replace migration evidence.

- An unset decision remains visible and blocks only the feature that depends on it.
- Test fixtures may exercise policy machinery using explicit test values, but they do not approve
  production policy.
- A code default must fail closed where a decision controls formal assessment, research access,
  retention/deletion, or pilot release.
- Any future implementation must link the selected policy version to the relevant audit and
  evidence records.

## Current limits

- D-01 and D-06 option selections are approved; concrete course records and remaining detailed policies are still due.
- Real assessed outcomes and forms need named assessor approval of their exact D-04 and D-05 bundles before publication.
- D-05 permits unrestricted approved conceptual hints in supported assessment and preserves separate unaided transfer.
- D-07 permits AI criterion suggestions after the separate validation gate passes. Humans must still confirm formal results.
- D-08 requires the approved field and retention schedule before participant processing or destructive lifecycle actions.
- D-12 selects an institution-approved host; the actual host, staff, provider budget, and release evidence remain unverified.
- Full Task 8 closure still needs the scoped records listed in the approved selections.

## Source references

- `docs/plans/004-remaining-work-and-merge-readiness.md:102-132`
- `docs/plans/002-person-a-assessment-implementation.md:1516-1534`
- `docs/plans/001-person-b-platform-implementation.md:1775-1792`
- `docs/01-implementation-requirements.md:17-32`
- `docs/02-pass-incomplete-bloom-assessment-spec.md:11-24`
