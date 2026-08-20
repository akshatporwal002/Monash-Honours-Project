 plan # 005: Remaining feature roadmap

Status: current roadmap, not an implementation-completion claim

Current delivery state: Step 1 decision register created; Step 2 is `BLOCKED` pending approved
values for D-01 provisional-result visibility and D-06 reassessment policy.

Owner: unassigned

Created: 2026-08-19

Target branch: `arv-person-a-assessment` at `dfcb30c`

## Outcome

Provide one current, feature-focused view of the LearnLens work that remains after
the assessment-definition, assessor-review, evidence, and learner-model foundation
work merged through PR 3. This roadmap does not implement product behaviour, change
data, or promote any release or pilot gate to passed.

## Source evidence

| Claim or rule | Evidence | Requirement |
| --- | --- | --- |
| The merged assessment slice implements work through assessor review only; learner result, reassessment, numeric-score removal, Person B integration, and pilot proof remain outside that slice. | `docs/plans/002-person-a-assessment-implementation.md:13-16` | A1-A6, AC19, AT18-AT24 |
| The immediate remaining assessment work is learner result/review, reassessment, removal of score writes and score UI, Person B handoff, and complete journey proof. | `docs/plans/004-remaining-work-and-merge-readiness.md:60-100` | FR12, FR19, FR21, FR22, FR25, FR39, AT18, AT19, AT21, AT24 |
| Person B completed the baseline, handoff, evidence, capture, and learner-model foundation through Step 9; learner annotation and projection work begins at Step 10. | `docs/plans/001-person-b-platform-implementation.md:225-668` | FR19, FR29, FR30, PD3, BP4, NFR27, NFR31 |
| The remaining Person B scope covers learner correction, task and simulation contracts, feedback safety, adaptation, research, analytics, and release evidence. | `docs/plans/001-person-b-platform-implementation.md:670-1651` | FR9, FR14-FR25, FR31-FR39, PD1-PD12, BP7-BP15, NFR4-NFR31 |
| Formal learner results remain `PASS` or `INCOMPLETE`; numeric marks and public `FAIL` are out of scope. | `docs/01-implementation-requirements.md:17-32`; `docs/02-pass-incomplete-bloom-assessment-spec.md:11-24` | AC19, AT1-AT3, AT19-AT20 |

## Current-state trace

1. The merged foundation provides versioned assessment definitions, immutable response versions,
   deterministic criterion and pass-rule evaluation, provisional decisions, and assessor review.
2. It also provides append-only learning evidence, trusted capture adapters, and versioned,
   non-diagnostic learner-model snapshots.
3. The learner cannot yet view an accessible formal result explanation or submit a formal review
   request. Reassessment policy and result visibility are not approved.
4. Shared LMS paths still retain score-oriented writes and projections. Existing percentages,
   averages, mastery, passing-score settings, and leaderboard behaviour must not represent formal
   assessment after migration.
5. Person B's remaining isolated modules are not yet ready for Handoff 2. They must be integrated
   through stable read-only ports and a verified migration graph, not through direct formal-result
   mutation.
6. Browser, accessibility, hosted, load, cost, evaluator-validation, and pilot evidence remain
   distinct release work. A passing automated test does not prove those broader claims.

## Delivery roadmap

### Step 1: Record the product decisions that gate learner-facing assessment

Files:

- `docs/learnlens/known-limits-and-deferred-decisions.md`
- `docs/plans/002-person-a-assessment-implementation.md`
- `docs/plans/004-remaining-work-and-merge-readiness.md`

Changes:

- [x] Create a decision register with the unresolved decision, named owner, required approval,
  dependent feature, and blocking effect.
- [ ] Name the owner and policy for provisional-result visibility.
- [ ] Approve reassessment eligibility, current-result selection, task-form equivalence, and review
  triggers.
- [ ] Approve assessor assignment rules, real outcome criteria, permitted tools, instructional
  support, access conditions, and transfer rules.
- [ ] Record evaluator release thresholds, retention periods, and escalation ownership without
  implementing them as hidden defaults.

Edge and failure cases:

- Missing policy blocks the dependent feature rather than silently selecting a default.
- Research consent or condition must not influence an assessment result or learning access.

**Acceptance:** Each policy has a named owner, source, effective version, and stated blocking
effect before its dependent feature is implemented.

### Step 2: Close the learner formal-result loop

Current gate: `BLOCKED`. D-01 and D-06 in
`docs/learnlens/known-limits-and-deferred-decisions.md` remain `PENDING`. Do not expose a
provisional result value or activate reassessment until the owners record approved, versioned
policy values. An unset visibility policy must continue to show an under-review state without the
result value.

Files:

- Learner result, review-request, reassessment, and accessibility paths named in
  `docs/plans/002-person-a-assessment-implementation.md:1116-1200`
- Corresponding backend, frontend, migration, API-contract, and browser tests

Changes:

- [ ] Show the learner `PASS` or `INCOMPLETE`, result lifecycle, assessed Bloom target, met and
  missing evidence, and a non-colour-only next action.
- [ ] Add a learner-owned review-request path with course and self-scope protection.
- [ ] Add policy-bound reassessment using a fresh approved form under the same standard.
- [ ] Preserve every earlier attempt, decision, and reason; never average attempts or infer a
  formal result from completion.

Edge and failure cases:

- A task or evaluator fault creates no `INCOMPLETE` result and keeps accepted work available.
- A changed rule or form version creates a reviewable conflict, not a silent re-evaluation.

**Acceptance:** AT18, AT19, AT21, and AT24 have current API, browser, keyboard, and accessibility
proof on the integrated head.

### Step 3: Retire the formal numeric-score model

Files:

- Shared backend and frontend projections named in
  `docs/plans/002-person-a-assessment-implementation.md:1201-1296`
- Legacy migration and compatibility documentation

Changes:

- [ ] Stop new numeric assessment-score writes and score-driven completion logic.
- [ ] Keep protected legacy reads until the approved compatibility window closes.
- [ ] Remove numeric score, percentage, average, mastery, `passing_score`, and public-ranking
  presentation from formal assessment paths.
- [ ] Separate activity, learning evidence, learner-model inference, technical quality metrics,
  research metrics, optional points, and formal results in every replacement contract and view.

Edge and failure cases:

- Old cached or legacy payloads cannot restore a numeric assessment view.
- Optional points and simulation probabilities remain clearly non-grade data.

**Acceptance:** AT1-AT3, AT19, and AT20 have database, API, export, UI, and regression-search
proof; no new formal result accepts or displays a numeric grade.

### Step 4: Complete learner evidence, task, and simulation capabilities

Files:

- Person B Steps 10-18 in `docs/plans/001-person-b-platform-implementation.md:670-935`
- Isolated evidence, learner-model, task-contract, Qiskit, frontend-feature, and test modules

Changes:

- [ ] Add learner annotation and educator correction while preserving immutable originals.
- [ ] Provide authorised evidence timelines and learner-model projections that distinguish
  observation, inference, uncertainty, correction, and provenance.
- [ ] Add versioned prediction, explanation, reasoning, reflection, transfer, matching, and
  sequencing task contracts without returning a formal result from Person B code.
- [ ] Add bounded Qiskit execution, durable run provenance, prediction-before-reveal behaviour,
  equivalent text results, accessible UI, and accepted-work recovery after simulation faults.

Edge and failure cases:

- A single wrong answer remains an uncertain observation, not a diagnosis or fixed learner label.
- Missing inference displays as insufficient evidence, not zero progress.

**Acceptance:** FR9, FR14, FR19, FR29, FR30, FR35-FR37, PD3-PD5, and NFR27 have isolated access,
storage, fault, and accessibility tests before shared integration begins.

### Step 5: Complete safe feedback, adaptation, progress, and learner control

Files:

- Person B Steps 19-30 in `docs/plans/001-person-b-platform-implementation.md:936-1286`
- Feedback, continuation, learner-model, progress, gamification, reminder, and frontend modules

Changes:

- [ ] Add versioned feedback context, Quality Policy v2, safety corpus, fallback provenance, and
  human escalation.
- [ ] Show feedback source/evidence context, safe support, reporting, and typed fallback or
  escalation states.
- [ ] Add learner preferences, non-formal diagnostics, evidence-based adaptation, learner and
  educator overrides, and misconception hypothesis/probe/revision/transfer flows.
- [ ] Build score-free progress projections, optional non-ranking gamification, and time-zone,
  extension, access-plan, completion, and preference-aware reminders.

Edge and failure cases:

- Adaptation cannot alter a Bloom target, evidence rule, pass rule, research condition, or formal
  result.
- Gamification, confidence, hints, access support, retries, and time never lower a formal result.

**Acceptance:** FR15-FR18, FR21-FR25, FR31-FR34, PD1, PD6-PD8, PD10-PD12, BP7, and BP13 have
deterministic, scoped, accessible, and one-way-boundary proof.

### Step 6: Complete research governance, exports, and analytics

Files:

- Person B Steps 31-36 in `docs/plans/001-person-b-platform-implementation.md:1287-1462`
- Research governance, export, analytics, privacy, and frontend modules

Changes:

- [ ] Add separately scoped consent, withdrawal, approved-field, experimental-condition, and
  missing-data records.
- [ ] Publish a pseudonymous, fail-closed research export v2 with a documented compatibility path.
- [ ] Separate educational evidence/activity measures, formal-result summaries, and technical AI
  metrics without averaging binary results.
- [ ] Prove research data has no path into evidence, adaptation, or formal-result decisions.
- [ ] Provide accessible research and analytics views with privacy-safe aggregation and honest
  missing-data states.

Edge and failure cases:

- Withdrawal affects research processing according to the approved policy, never operational
  learning access or formal results.
- No export exposes direct learner identifiers, full answers, secrets, or formula-injection data.

**Acceptance:** FR20, FR22, FR39, BP12-BP14, NFR16, NFR25, NFR30, AC18, and AT23 have governance,
export, privacy, and permutation-test proof.

### Step 7: Complete Handoff 2, full-loop integration, and release evidence

Files:

- `docs/learnlens/person-b-integration-manifest.md` (new)
- Shared integration points and tests named in
  `docs/plans/002-person-a-assessment-implementation.md:1297-1410`
- Person B Steps 37-43 in `docs/plans/001-person-b-platform-implementation.md:1463-1651`

Changes:

- [ ] Require the approved Person B manifest and isolated proof before modifying shared routers,
  models, contracts, application shell, or migrations.
- [ ] Integrate only read-only evidence, progress, and result-summary ports. Person B code must
  never create, alter, or confirm a formal result.
- [ ] Reconcile Alembic heads through a named merge revision when required and regenerate API
  contracts from the repository generators.
- [ ] Prove the complete learner journey from assessor setup through result, review request,
  reassessment, evidence update, and next recommendation.
- [ ] Run and record release, recovery, concurrency, backup, load, cost, security, privacy,
  browser, manual accessibility, traceability, and known-limit evidence.

Edge and failure cases:

- A missing or changed manifest, contract mismatch, or migration conflict stops integration for
  coordination; it does not rewrite another owner's work.
- Unavailable hosted, native-browser, screen-reader, evaluator, or load evidence remains
  `NOT RUN` or `UNVERIFIED`.

**Acceptance:** One integrated migration head, current full-loop tests, all three local reviewer
verdicts, current GitHub checks, and an evidence-backed release record exist before a pilot-ready
claim.

## Recommended dependency order

1. Record the Step 1 policy decisions.
2. Deliver Steps 2 and 3 together so learner assessment cannot reintroduce score semantics.
3. Complete Step 4 before mounting learner evidence and model views.
4. Complete Step 5 before adopting model-driven learner recommendations or progress replacements.
5. Complete Step 6 before enabling live research participation or exports.
6. Complete Step 7 only after both Person A and Person B isolated workstreams have their required
   tests and handoff evidence.

## Full verification

This document introduces no executable code, migration, API, or runtime behaviour. Validate it by:

```zsh
git diff --check
rg -n '^### Step [1-7]:' docs/plans/005-remaining-feature-roadmap.md
```

Each later implementation slice must run its targeted tests first, then the applicable commands
from `.github/workflows/quality.yml`. Browser, screen-reader, native Safari, load, hosted,
evaluator-validation, cost, and usability claims require their own saved evidence.

## Migration and rollback

Not applicable to this documentation-only change. Later feature work must use forward migrations,
fixture-backed legacy compatibility, record-count and foreign-key checks, and a documented
recovery path.

## Risks and controls

| Risk | Impact | Control and proof |
| --- | --- | --- |
| Numeric score paths survive beside binary assessment | Invalid learner assessment and misleading UI | Deliver Steps 2-3 together; prove AT1-AT3 and AT19-AT20 across database, API, export, and UI. |
| Integration bypasses the formal-result boundary | Evidence, research, or model code could change a result | Require Handoff 2 manifest, import-boundary tests, and read-only ports in Step 7. |
| Missing policy becomes a hidden default | Unauthorised learner visibility, reassessment, retention, or escalation behaviour | Record the named owner and block the dependent feature in Step 1. |
| Automated checks are mistaken for pilot evidence | Unsupported accessibility, scale, cost, or evaluator-validity claim | Keep manual, hosted, and governance evidence separately marked until run. |

## Missing-data report

| Missing decision or evidence | Owner | Blocking effect |
| --- | --- | --- |
| Provisional-result visibility and reassessment current-result rule | Product owner and assessors | Blocks learner result wording and reassessment activation. |
| Real outcome criteria, tools, support, access, and transfer conditions | Assigned assessors | Blocks publication of real assessed task forms. |
| Assessor and separate research-permission assignment policy | Product owner and research governance | Blocks production role assignment. |
| Retention, withdrawal, missing-data, and approved research-field policy | Privacy and research governance | Blocks live research governance and destructive lifecycle actions. |
| Evaluator accuracy/fairness thresholds and dataset | Assessment governance | Blocks automated evaluator release. |
| Person B integration manifest and isolated proof | Person B | Blocks Handoff 2 and shared integration. |
| Native Safari, screen-reader, hosted, load, cost, and usability evidence | Accessibility, operations, and product owners | Blocks full NFR and pilot-readiness claims. |

## PR mapping

This is a documentation-only roadmap. Any future implementation PR must reference the relevant
roadmap step and mirror its checklist, acceptance line, verification results, risks, and open
items. No roadmap item is complete merely because this document is committed.
