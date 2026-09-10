# Task 8 feature decisions

Status: selections approved; remaining activation details pending; Task 8 not complete

Prepared: 2026-09-07

Package version: `feature-decisions-v1-draft.2`

Branch: `docs/task-8-feature-decisions`

Base: `aca9476`, local `main` and its stored `origin/main` reference at inspection.
The remote has not been refreshed during this task.

## What this package settles

The approved selections cover all twelve policy areas.
D-10 already has an explicit implementation approval.
The user has now selected D-05 B, D-07 C, and A for the other offered choices.
The [approved selections](task-08-approved-selections.md) record the exact scope, versions, date, and remaining requirements.
Those selections control any conflicting wording in this draft. Other detailed proposals still need their own approval records.

The [register](known-limits-and-deferred-decisions.md) remains the approval index.
New proposals below are not retrospective approvals. Unselected details remain proposals.
The original audit's statement that all twelve decisions remain pending is stale.

Task 8 completes only when each dependent feature has the approval its acceptance check requires.
Recording a proposed policy does not enable production access, publish an assessment, or approve research or release.

## Approval records to supply

For each decision, record the owner's name, approver's name, exact scope, policy version, approval date, and evidence link.
Record any amendments to the proposed value. Do not infer a team member's authority from their Git identity.
Policy changes need a new version. Existing assessed attempts keep their frozen version.

| Decision | Existing direction and source | Proposed version | Approval still needed |
| --- | --- | --- | --- |
| D-01 | [Hide provisional results](task-08-approved-selections.md#d-01) | `learner-visibility-v1` | Product owner and assessor names; approve the state table and course scope |
| D-02 | [Explicit course assessor grants](task-08-approved-selections.md#d-02) | `assessor-access-v1` | Product owner; name eligible staff and grant authorities for each course |
| D-03 | [Separate research grants](task-08-approved-selections.md#d-03) | `research-access-v1` | Product and research owners; name approved staff, courses, studies, and fields |
| D-04 | [Prediction, explanation, fresh application](task-08-approved-selections.md#d-04) | `single-qubit-outcome-v1` | Assigned assessor; approve the outcome, sources, criteria, examples, and sufficiency rule |
| D-05 | [Unlimited approved conceptual hints and unaided transfer](task-08-approved-selections.md#d-05) | `single-qubit-conditions-v1-selection` | Assigned assessor; approve concrete hint content, tools, equivalent forms, and access conditions |
| D-06 | [Fresh equivalent reassessment](task-08-approved-selections.md#d-06) | `reassessment-v1` | Product owner and assessors; approve eligibility, selection, and review rules |
| D-07 | [Validated AI suggestions with human confirmation](task-08-approved-selections.md#d-07) | `ai-assessor-suggestions-v1-selection` | Assessment governance and expert reviewers; approve dataset, measures, error limits, and release process |
| D-08 | [Separate consent and owner-approved lifecycle](task-08-approved-selections.md#d-08) | `data-lifecycle-v1` | Privacy and research owners; supply field schedule, retention periods, and institutional decisions |
| D-09 | [Learning and technical queues](task-08-approved-selections.md#d-09) | `human-escalation-v1` | Product and operations owners; name primary and backup staff, service hours, and targets |
| D-10 | [Immediate retirement](task-08-approved-selections.md#d-10), approved 2026-09-06 by the requesting user | `legacy-retirement-v1`, already effective for implementation | No new policy choice; implementation and migration evidence remain due |
| D-11 | [Programming module within 16 hours](task-08-approved-selections.md#d-11) | `programming-reuse-v1` | Product owner; approve module, effort accounting, and independent verifier |
| D-12 | [One hosted pilot and assigned reviewers](task-08-approved-selections.md#d-12) | `release-evidence-v1` | Product, accessibility, and operations owners; name environments, providers, reviewers, and release authority |

## D-01: learner result visibility

Keep the accepted rule: learners cannot see provisional `PASS` or `INCOMPLETE`.
The following wording and field rules are proposed for every course that adopts this policy version.

| State or action | Learner wording | Fields shown | Next action |
| --- | --- | --- | --- |
| Not started or draft | Not assessed | Declared outcome, Bloom target, criteria, tools, help rules, saved work | Start or resume |
| Submitted, processing, provisional, or human review required | Awaiting assessor review | Submission receipt, learner's evidence, declared criteria, permitted learning feedback | View submission or request review |
| Confirmed | PASS or INCOMPLETE; Confirmed by assessor | Result, met and missing criteria, scoped evidence, assessor reason, decision date, version references | Request review; reassess when eligible |
| Overridden | PASS or INCOMPLETE; Updated by assessor | Current result and reason, permitted earlier decision history, version references | Request review |
| Withheld | Result withheld pending review | Assessor's learner notice, submission, permitted feedback; no current result or provisional criterion judgements | View review status |
| Returned | Returned for further work | Assessor reason and requested evidence; no unconfirmed formal result | Resume permitted work |
| Void | Attempt voided | Learner-safe reason, affected attempt, preserved history, next-step notice; no usable current result | Request review or start an authorised replacement |

Withholding and returning remain actions or submission states. They do not add new formal result values.
Do not reveal evaluator verdicts indirectly through provisional criterion labels, exports, notifications, or result summaries.
Learning feedback may describe work and next steps within the approved help policy.
Assessor-only notes and other learners' evidence remain private.

Acceptance: exercise every state through learner-owned APIs and screens, including stale requests and cross-course access.
Confirm that assessor action changes the visible projection without changing the original submitted evidence.
The policy must apply to dashboard, task, history, review, and export paths.

## D-02 and D-03: scoped authority

The selected assessor assignment route requires course-lead approval of eligible teaching staff for the named course.
An authorised administrator records the grant or revocation, policy version, approving owner, scope, start, optional expiry, and reason.
Administrator or educator status alone grants no assessor powers. Grants cannot create approval authority by themselves.
Revocation, expiry, and account deactivation apply on the next protected request and worker action.
Earlier valid decisions stay readable and retain the authority record used at decision time.

Research grants use a separate permission for named study staff, named courses, approved studies, and permitted fields.
Under selected D-03 A, grants expire when the study's access period ends.
Research processing also requires an approved study, approved fields, current consent, and permitted use under D-08.
Recheck those conditions when jobs execute and when exports are delivered, not only when work is queued.
Ordinary analytics permission, administrator status, a global toggle, or an assessor grant is insufficient.
Withdrawal or revoked research access leaves teaching access and formal results unchanged.

Acceptance: cover absent grants, wrong courses, expiry, deactivation, revocation after enqueue, and denied export delivery.
Record grant and revoke events without including learner responses or secrets in audit summaries.

## D-04: first outcome and evidence

The accepted first topic is introductory superposition with a Hadamard gate and human assessment.
The proposed learner group is students beginning quantum computing who know basic probability and binary notation.
The actual course, cohort, assessor, and source approvals still need names or stable identifiers.

Proposed outcome `Q-SINGLE-01`: explain and predict single-qubit measurement behaviour, then apply that reasoning to a fresh circuit.
Proposed Bloom process: `APPLY`. Knowledge dimensions: `CONCEPTUAL` and `PROCEDURAL`.
The assessed claim covers applying the gate sequence and explaining the resulting measurement, not recalling gate names.

Candidate source: IBM Quantum Learning, [Quantum information](https://quantum.cloud.ibm.com/learning/en/courses/basics-of-quantum-information/single-systems/quantum-information).
An assessor must select and approve the exact passage revision before publication.
A URL and retrieval date do not substitute for Task 9's preserved source record.

Proposed task family uses one qubit, ideal H and X gates, and computational-basis measurement.
One H on an initial zero state gives equal outcome probabilities. Two consecutive H gates restore the initial state.
Finite samples need not divide evenly. These facts follow the candidate [IBM lesson](https://quantum.cloud.ibm.com/learning/en/courses/basics-of-quantum-information/single-systems/quantum-information).

| Mandatory criterion | Evidence needed for MET | Evidence that does not meet it | Evaluator |
| --- | --- | --- | --- |
| C1: prediction | Save the expected distribution and reason before the assessed run reveals results | A copied histogram, outcome without reasoning, or a contradicted prediction | Human |
| C2: explanation | Explain the gate sequence, one-shot outcome, and difference between probability and observed frequency | Claim that every finite run must split evenly, or confuse gate application with measurement | Human |
| C3: fresh application | Give a correct prediction and explanation for an assessor-approved unseen equivalent sequence under transfer conditions | Repeat the practice answer without applying the new sequence, or use an answer revealed for this form | Human |

Proposed pass rule: `ALL_OF(C1, C2, C3)`, with all three mandatory.
One approved multi-part attempt must provide all three. Do not combine partial evidence from unrelated attempts.
Missing, conflicting, or unreadable evidence is `NOT_EVALUABLE` and requires a reason and human review.
Apply the existing conservative binary-result rules; do not treat uncertainty as positive evidence.

Accept plain text, accurate mathematical notation, or an approved equivalent response form.
A valid concise explanation can meet a criterion. Length, grammar style, confidence, time, and hints do not determine the result.
An accurate simulation histogram alone cannot establish conceptual understanding.
An unusual valid method goes to the assessor rather than failing a phrase match.

Practice sequence: predict, explain, save, simulate, read checked feedback, revise, reflect, then receive the next approved activity.
An assessed sequence begins with explicit conditions and a frozen version bundle.
Its fresh form uses a gate sequence not revealed in the learner's practice or help history.
The assessor must approve at least one concrete fresh form and its expected evidence before publication.
No prompt in this draft counts as an approved unseen form for a real learner.

Acceptance: preserve each stage and its source, circuit, simulation, help, rule, and assessment references across restart.
A human records criterion judgements and a reason before confirming the formal result.
Task 25 must prove the complete journey through real application services.

## D-05: tools, help, and access conditions

Proposed practice conditions allow conceptual hints, simulation, checked feedback, and revision.
Assessed prediction must be saved before results become visible.
During the supported assessed stage, allow unrestricted approved conceptual hints, with no instructional hint-count cap.
Hints may restate the concept or ask for reasoning. They cannot give the current form's answer or completed circuit.
Requests outside the approved conceptual-help scope route to practice or human help; they never deduct a mark.
The no-cap rule is approved under D-05 B. The exact hint content and tool conditions below still need form approval.

For fresh transfer, disable instructional hints, worked solutions, external AI answers, and pre-answer simulation results.
Allow the declared task instructions, gate reference, and approved access support.
After submission, release only feedback permitted by the form's policy.
Remote UI controls cannot prove the absence of outside help; retain the declared conditions without claiming supervised evidence.

Proposed equivalent modes include keyboard circuit controls, text circuit entry, assistive reading, and speech-to-text.
They must preserve the same reasoning demand and evidence content.
Record approved modes without inferring a disability or penalising support, breaks, or extra time.
The assessor must approve each alternative and explain why it tests the same claim.

Acceptance: test hint boundaries across reloads, prediction-before-reveal, resumed conditions, and fresh-form selection.
A content or rule change must preserve the started version or return an explicit conflict.

## D-06: reassessment and current results

Propose reassessment after feedback for a confirmed `INCOMPLETE`, or after an authorised void or replacement decision.
Use a fresh equivalent form with the same outcome, mandatory criteria, and declared conditions.
No automatic lifetime attempt limit is proposed. Scheduling and eligibility changes require an explicit policy version.
An unresolved review or withheld attempt stays in review until an assessor decides its next action.

An assessor must approve replacement links. The newest submitted or provisional attempt cannot replace a confirmed result.
The current outcome result is the latest eligible confirmed or overridden decision in the authorised replacement chain.
A voided decision cannot serve as the current result. Preserve and explain the resulting chain selection.
Keep a valid current PASS until an authorised action explicitly supersedes or voids it.
Do not average attempts or accumulate different attempts' partial criteria under the first-outcome sufficiency rule.
No course-level result is proposed for the first loop.

Examples: an incomplete result followed by a pending reassessment remains the current incomplete result.
A confirmed passing replacement becomes current while its earlier decision remains readable.
A review request alone changes neither the current result nor the original evidence.

Acceptance: test simultaneous review and reassessment actions, replay, invalid links, revoked assessors, and outcome scope.

## D-07: evaluator evidence and release

After the separate validation gate passes, show AI criterion suggestions to assessors before they decide.
Humans still confirm formal results. Until that gate passes, use human assessment and keep operational AI assessment suggestions disabled.
This is the selected D-07 C workflow. The validation design below remains a proposal where not already required by the specification.
Propose at least 100 distinct expert-reviewed quantum cases, covering supported task types and every critical criterion.
Include correct, incorrect, uncertain, conflicting, unusual-valid, brief, long, and approved alternate-mode responses.
Two trained reviewers judge independently before adjudication. Keep initial labels to measure human agreement.

Proposed reporting includes confusion matrices, criterion agreement, raw agreement, Cohen's kappa, and uncertainty intervals.
Report undefined statistics and small subgroups explicitly. Do not hide them through pooled results.
Use fixed case versions and held-out cases. Record source, model, prompt, rule, simulator, and provider versions.
Review any change to those components for revalidation before release.

The existing requirements set factual accuracy at least 80%, hallucinations at most 5%, and mean feedback review at least 4/5.
Judge rejection must reach 80%, with false rejection at most 20%.
These are feedback and judge checks. They do not set the formal-assessment release threshold.
Governance must still choose acceptable false-pass and false-incomplete rates, agreement thresholds, and uncertainty handling.
Until those values and expert evidence exist, keep automated assessment release disabled.

Acceptance: a reviewable case manifest, independent labels, computed metrics, subgroup findings, and signed release decision.
Synthetic fixtures prove software behaviour only. They cannot be labelled educator-approved cases.

## D-08: data lifecycle and research

Keep the accepted separation between research consent and course access.
No retention duration or institutional approval can be inferred from this implementation request.
The privacy and research owners must supply the following schedule before activation or destructive work.

| Record class | Owner-supplied values required | Safe implementation boundary while pending |
| --- | --- | --- |
| Identity and course membership | Purpose, access, retention trigger and duration, correction and deletion process | Keep operational scope; avoid new identity exports |
| Source revisions and learning evidence | Approved uses, rights, passage retention, protected-reference rules | Preserve referenced revisions; no destructive retirement |
| Assessment and audit history | Retention schedule, holds, access roles, rollback and correction rules | Keep originals readable; corrections append history |
| Research records | Approved study, consent text and version, fields, recipients, expiry, withdrawal cutoff | No new participant enrolment, processing, or export without the complete gate |
| Backups and derived copies | Backup expiry, restore controls, withdrawal propagation, destruction evidence | No claim that withdrawal has removed all copies without evidence |

Propose withdrawal to block new research use immediately while preserving teaching access.
The approved data plan must settle existing exports, irreversibly anonymised records, protected histories, and backup handling.
Use explicit missingness reasons such as not collected, withdrawn, unavailable, and processing error. Never replace them with zero.
Store pseudonymous study identifiers separately from identity mappings and apply study-specific field allowlists.

Acceptance: approved schedule and institutional decision references, followed by permission, withdrawal, restore, and deletion tests.
This draft supplies engineering boundaries, not legal advice or an ethics decision.

## D-09: escalation handling

Propose one learning queue for assessor concerns and one technical queue for service faults.
Every case stores scope, source output, severity, status, owner, backup, target time, learner notice, and resolution reason.
Use acknowledgement, in progress, resolved, and closed states, with timestamped changes and a reopen path.
An unresolved critical issue blocks the affected output or action, without discarding accepted learner work.

Proposed service targets, subject to named owner approval:

| Severity | Example | Acknowledgement | Action target |
| --- | --- | --- | --- |
| Critical | Exposed private evidence or wrong-person formal decision | Within one staffed hour | Contain the affected path within four staffed hours |
| High | Blocked assessed submission or repeated invalid feedback | Within one business day | Workaround or reviewed next step within two business days |
| Routine | Unclear explanation or possible misconception | Within two business days | Reviewed response within five business days |

Owners must define service timezone, staffed hours, holidays, primary and backup names before targets are promised.
Propose sampling 10% of accepted AI feedback, plus every user report and repeated rejection.
Record the selection method, review result, learner notice where needed, and any follow-up validation.

Acceptance: replay-safe reporting, correct course ownership, backup reassignment, overdue handling, closure reason, and audit history.

## D-10: apply the existing retirement approval

Use `legacy-retirement-v1`, approved by the requesting user on 2026-09-06, effective immediately for implementation.
Its compatibility window is zero days across the application. Old consumers must update.
Remove numeric result interfaces and supporting score-driven behaviour through a coordinated change.
Preserve original attempts, protected legacy history, and audit records before obsolete active columns are removed.
An old score cannot become a formal PASS. Quantum probabilities retain their technical meaning.

The [original approval](task-08-approved-selections.md#d-10) controls the full scope.
Tasks 29, 31, and 37 still owe implementation and preservation evidence.

## D-11: second-subject reuse

Use the accepted introductory programming direction and proposed 16 developer-hour target.
Propose a module on tracing and correcting a small conditional program, using prediction, reasoning, revision, and fresh transfer.
Keep it in a separate course with its own sources and approved outcome criteria.

Count hands-on setup, source preparation, adapter work, debugging, tests, documentation, and required core changes.
Report elapsed waiting separately. Count work across contributors rather than only one person's clock.
An independent developer must perform or verify the exercise and review the effort log.
Pass only if the agreed scope works within 16 developer-hours and all core changes are disclosed.
This demonstrates extension effort. It does not demonstrate learning benefit in the second subject.

## D-12: release evidence

Use one institution-approved hosted pilot with the existing deployment package and a named operations owner, under selected D-12 A.
The owner must name the actual host, course scope, permitted providers and models, spend limit, reviewers, and release authority.
Do not infer those choices from available credentials or local defaults.

| Evidence | Required owner and environment | Evidence required before completion |
| --- | --- | --- |
| Browsers and access | Named reviewers; Chrome, Edge, Firefox, native Safari; named screen reader and OS pairs | Full role journeys, keyboard, focus, zoom, reflow, contrast, and circuit-text records |
| Security and recovery | Security reviewer and isolated restore target | Scoped access, fault recovery, accepted-record counts, restored files and database, safe migration proof |
| Load and cost | Operations owner; approved providers, host, test window, and budget | Actual full-loop measurements, usage, prices, currency assumptions, configuration, and error rates |
| Usability | Product testing owner and approved recruitment route | Required first-time educator and student trials, times, assistance, completion, and ratings |
| Hosted availability | Operations owner and monitoring target | Monthly observation against 99.5%; setup alone cannot establish availability |
| Final release | Named release authority | Final commit, current checks, independent review, open limits, backup, rollback, and recorded decision |

Use the thresholds in Tasks 35 through 41 and the controlling requirements.
Store later evidence under `docs/learnlens/evidence/` with commit, environment, command or method, date, and reviewer.
Do not store participant identities, secrets, raw private responses, or credentials there.
Native Safari, human reviews, ethics decisions, provider measurements, and availability cannot be replaced with local unit tests.

## Handoff and completion gate

Document checks passed on 2026-09-07: local file links, decision-ticket anchors, D-01 through D-12 coverage,
and Git whitespace validation. The package contains no invisible formatting characters or long dash punctuation.
The quantum source was opened for factual checking; it still requires course-source approval.
Runtime tests and CI were not run for this documentation-only draft. No release evidence is claimed.

The requesting user authorised sequential task branches and merges, beginning at Task 8.
The branch contains this package, the user's approved selections, linked decision-ticket records, and register corrections.
No runtime policy has been enabled.
The initial checkout was clean on `main` at `aca9476`. Tasks 1 through 7 appear in its existing history.

To finish Task 8:

1. Receive owner names, concrete scope identifiers, and the outstanding institutional and environment records.
2. Settle remaining detailed values with authorised owners, preserving the choices already recorded in the approved selections.
3. Record exact approvals in the existing decision tickets, with versions, dates, scope, and evidence links.
4. Update only the register entries whose own requirements are satisfied.
5. Validate links and the diff, then commit and merge this branch with a separate merge commit.
6. Record the resulting commit and start Task 9 from the updated `main`.

Manual context clearing is unavailable through the current tools.
Use this handoff and a fresh task note at each boundary; do not claim the session context was cleared.
Keep Task 8 incomplete while owner decisions remain missing, even if its draft documentation is committed.
