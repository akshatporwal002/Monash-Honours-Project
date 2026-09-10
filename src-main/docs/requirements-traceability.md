# LearnLens requirements traceability

Inspected integration: `d30570eb048443bc2ac46a6b420f0153d5904d69`, 10 September 2026. **Combined final validation: IN_PROGRESS.**

The [current implementation gap matrix](../../docs/learnlens/implementation-gap-matrix.md) is the authoritative status ledger for every numbered requirement. Its 143 rows link each controlling definition to precise production/service/route/model/migration/UI paths, named fixture tests, dated evidence, current gap, dependency and acceptance check. This file is a crosswalk, not a second independently maintained status table.

Definitions and settled policy remain in [implementation requirements](../../docs/01-implementation-requirements.md), [assessment specification](../../docs/02-pass-incomplete-bloom-assessment-spec.md), [work order](../../docs/03-codex-implementation-work-order.md) and [Task 8 selections](../../docs/learnlens/task-08-approved-selections.md). The [baseline report](../../docs/learnlens/task-36-requirements-reconciliation.md) and [main audit](../../docs/learnlens/main-audit-2026-09-10.md) remain evidence at `27a397a`, not an audit of the later integrated tree.

## Complete requirement crosswalk

| Family | Exact inventory | Authoritative row/evidence location |
| --- | --- | --- |
| FR | FR1–FR39 — 39 rows | Matrix: each exact ID once; same ID in baseline wording/evidence ledger; integrated I-* overrides where listed |
| PD | PD1–PD12 — 12 rows | Matrix: each exact ID once, including integrity cues, curriculum, learner corrections and escalation |
| BP | BP1–BP15 — 15 rows | Matrix: each exact ID once, including moderation, validated AI release, purpose/retention/withdrawal and version control |
| NFR | NFR1–NFR31 — 31 rows | Matrix: each exact ID once, with actual measurements separated from preparation/fixture proof |
| AC | AC1–AC22 — 22 rows | Matrix: each exact ID once, with complete-loop evidence and remaining study/access/release acceptance |
| AT | AT1–AT24 — 24 rows | Matrix: each exact ID once, including binary result, frozen standard, human control and research neutrality |

Total **143**, no duplicated definitions. The former MVP table covered only FR1–FR28/NFR1–NFR25. FR29–39, NFR26–31 and all PD/BP/AC/AT rows are part of the controlling expanded inventory; repeated IDs in old SRS/Person 4 text are aliases to the current definitions, not extra requirements. The full original wording is retained in the baseline ledger, so replacing this stale status table removes no authoritative requirement.

## Current reconciliation

- Tasks 25/27/29 are committed and integrated. Task 27 already supplies misconception escalation to Task 28; only staffing/activation remains for that task. The timezone fix is now in integrated source, with fresh-session UTC regression coverage and scoped delivery receipts.
- Task 33 adds real versioned governance/consent/withdrawal and restricted technical-pair v2 export controls. Production remains closed; full Task 34 learning-study instruments/exports and actual approvals remain absent.
- Task 35 has 108 draft cases and offline metrics/import tooling, zero expert approvals or ratings. Its numerical fixture check cannot validate AI assessment. The D-07 operational suggestion gate stays disabled and humans confirm formal results.
- Task 38 supplies a fake/fixture-tested harness, not real performance/cost evidence; typed follow-on submission is pending integration. Task 39 supplies blank human-test procedures, not actual trials; circuit keyboard placement/semantics is pending integration and native/assistive-technology checks remain due.
- Task 40's dependence on an unfinished Task 25 is stale. It still needs approved sources, full second-subject model/adaptation reuse, independently observed practice and measured developer effort.
- Former score/average/mastery-radar/leaderboard descriptions are superseded by protected numeric-history retirement and separate evidence/uncertain-estimate/binary-result projections. Game points, quantum probabilities and technical quality measures remain distinct permitted values.
- Frontend stability/Vitest and secret-scan repairs are integrated; their passing branch receipts do not make final combined validation green. The migration graph head is 0045, with the baseline runtime pin still 0044. The [post-baseline register](../../docs/learnlens/implementation-gap-matrix.md#post-baseline-coordinator-receipts) records coordinator readiness fix `a38e6af` and Task 35 provenance refresh `0eaf467`, their focused receipts and the superseded unfinished backend run. Earlier suite totals/head versions remain historical; final combined validation is pending.

The [master task list](../../LearnLens_Remaining_Tasks.md) records **29 completed implementation, 10 partial and 2 remaining**. Requirement-level statuses are more granular and are listed only in the matrix. Final runtime receipts, manual/expert approval and hosted evidence remain coordinator/human obligations. No fixture approval or agent review establishes pilot readiness.
