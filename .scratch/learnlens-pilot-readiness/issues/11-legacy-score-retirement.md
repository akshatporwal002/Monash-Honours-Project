# Approve legacy score and client retirement

ID: 11
Parent: [LearnLens route to pilot readiness](../map.md)
Label: wayfinder:grilling
Type: grilling
Mode: HITL
Status: resolved
Direction: accepted
Assignee: Codex, recording the requesting user's decision
Blocked by: none
Decision authority: Requesting user, through this conversation
Source tasks: 3, 8, 29, 31, 37
Policy: D-10

## Question

What compatibility window and retirement process applies to legacy numeric data and clients?

- Identify affected clients and protected histories from current repository and deployment evidence.
- Set notices, migration conditions, retirement dates, and rollback limits.
- Keep absent numeric values distinct from zero and preserve the existing formal binary-result rules.

A resolution must provide: An approved compatibility policy and retirement plan tied to identified clients, preserved history, and migration checks.

## Context

- [Policy register: Approve legacy score and client retirement (D-10)](../../../docs/learnlens/known-limits-and-deferred-decisions.md)
- [Related build tasks](../../../LearnLens_Remaining_Tasks.md)

## Comments

Charted on 6 September 2026. No answer or policy approval has been recorded.

### Explanation requested

The user excluded this recommendation from their acceptance and requested a fuller explanation.
No retirement policy, compatibility period, or deletion action has been approved.

A client is software calling the backend, including the LearnLens browser frontend.
Current dashboard code uses numeric average fields, while formal submissions leave the old score field empty.
Retirement must update those readers and writers together, or define a transition for a confirmed older consumer.

Protected original records remain separate from the interfaces being retired.
The existing archive stores source results, scores, and migration details; retiring an interface does not authorise deleting that history.
An old numeric mark is not sufficient evidence for a new formal PASS.

Proposed direction, awaiting the user's answer: retire numeric-grade interfaces before the pilot through a coordinated application update.
Preserve protected history and add a compatibility period only if a confirmed older consumer requires one.
Live deployments, external consumers, and live historical row counts have not been verified.

Evidence to consult when settling the policy:

- [Current educator score display](../../../src-main/frontend/src/components/EducatorDashboard.tsx)
- [Task-summary score contract](../../../src-main/backend/app/schemas/lms.py)
- [Protected assessment history](../../../src-main/backend/app/models/assessment.py)
- [Migration and API requirements](../../../docs/02-pass-incomplete-bloom-assessment-spec.md)

## Answer

The user selected immediate retirement: "you can remove all the old stuff immediately".
This resolves the earlier choice about keeping a temporary compatibility period.

Policy version: legacy-retirement-v1
Recorded: 2026-09-06
Approver: Requesting user, through this conversation
Effective: Immediately for implementation; no grace period or old-client support requirement

### Retirement rule

Retire the old numeric-grading interfaces and supporting behaviour through a coordinated frontend and backend update.
The compatibility window is zero days. Older consumers must update; they do not justify keeping a compatibility adapter.
Document the removal with the implementation. No advance-notice period delays the change.

The known scope includes numeric learner-result fields, score-based dashboard summaries and recommendations,
passing-score settings, score-linked rewards, and related frontend types, API readers, exports, and tests.
Remove obsolete active database columns after preserving their original values and updating all active readers and writers.
Apply this across the application; the decision is not limited to one course or client version.

### Preservation and validation

Keep original attempts, protected assessment history, and migration audit records readable.
Their retention or deletion belongs to the separate data-lifecycle policy.
An old percentage does not become a formal PASS. Simulation probabilities and technical quality measures keep their own meanings.

Use a forward migration where schema changes are needed. Verify history preservation, record counts, and one migration head.
Cover fresh and populated databases, formal-only and mixed histories, updated API contracts, and learner and educator views.
Preserve a verified recovery path through backups and the prior package; do not reopen old score behaviour as a permanent adapter.

Known consumers include the current browser frontend and internal LMS projections.
No claim is made about live external integrations or live record counts. Any later-discovered old consumer must update under this policy.

### Handoff

Carry the decision into the existing dashboard repair, numeric-result retirement, gamification, and migration-safety tasks.
This ticket resolves the planning decision. Application changes, migration execution, and their test evidence remain implementation work.
