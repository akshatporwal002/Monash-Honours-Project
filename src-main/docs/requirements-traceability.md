# LearnLens requirements traceability

Inspected integration: `6d20416c6760d4841828c9e59cc74679d8ca0ae7`, 10 September 2026. **Combined final validation: IN_PROGRESS.**

Current next-wave validation: **IN_PROGRESS** at frozen application/test source `6d20416c6760d4841828c9e59cc74679d8ca0ae7`. Full frontend: 319 tests across 85 files passed; lint, types, build, dependency audits, contracts, Ruff and migration-head checks passed. Full backend coverage and all 132 browser cases are still being verified. The first browser run loaded the primary checkout backend through its editable installation; that mixed-source run is diagnostic evidence only and must be repeated with worktree imports pinned. No current combined PASS, expert approval, research activation or hosted-release acceptance is claimed.

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
- Task 33 adds real versioned governance/consent/withdrawal and restricted technical-pair v2 export controls. Production remains closed. Task 34A now supplies governed versioned instrument-stage records; full approved workflows/exports and actual approvals remain due.
- Task 35 has 108 draft cases and offline metrics/import tooling, zero expert approvals or ratings. Its numerical fixture check cannot validate AI assessment. The D-07 operational suggestion gate stays disabled and humans confirm formal results.
- Task 38 now has a dated final owner receipt for one real local learner, typed follow-on submission, exact actual generator/judge inputs and cleanup: 54 focused passes and 35 successful HTTP calls. Actual AUD remains null; representative load, provider approval, durable metering and budget enforcement remain open; administrator timeout/retry controls are now implemented. Task 39 circuit keyboard/removal and explicit live/saved CX text fixes are integrated, restoring bounded FR14 implementation; manual NFR4/AC17/AT24 evidence remains due.
- Task 40's dependence on an unfinished Task 25 is stale. It still needs approved sources, full second-subject model/adaptation reuse, independently observed practice and measured developer effort.
- Former score/average/mastery-radar/leaderboard descriptions are superseded by protected numeric-history retirement and separate evidence/uncertain-estimate/binary-result projections. Game points, quantum probabilities and technical quality measures remain distinct permitted values.
- Frontend stability/Vitest and secret-scan repairs are integrated; their passing branch receipts do not make final combined validation green. Runtime readiness now matches migration head 0046. The [receipt register](../../docs/learnlens/implementation-gap-matrix.md#post-baseline-coordinator-receipts) records integrated readiness `a38e6af`, provenance `0eaf467`/`0af4873`, practice `0b43220`/`af7bfb8`, circuit corrections and the later Task 38 owner receipt. The corrected practice run passed 80 focused cases, including bounded actual model inputs and digest/approval/transfer guards. The superseded unfinished backend run is not a pass. The coordinator reports the final 306-test/84-file frontend run, lint/build, contracts and Ruff passing; older totals remain historical. Those earlier results remain historical; current combined evidence is IN_PROGRESS.

The [master task list](../../LearnLens_Remaining_Tasks.md) records **29 completed implementation, 11 partial and 1 remaining: 12 unfinished**. Requirement-level statuses are more granular and are listed only in the matrix. The [current next-wave report](../../docs/learnlens/next-wave-integration-verification-2026-09-10.md) owns current runtime receipts; manual/expert approval and hosted evidence remain separate obligations. No fixture approval or agent review establishes pilot readiness.

Current source changes, named production/tests and evidence boundaries are in [I-WAVE](../../docs/learnlens/implementation-gap-matrix.md#i-wave). Task 34A instruments, Task 38A runtime controls, Task 37 local recovery and the assessor focus fix are integrated. **12 tasks remain unfinished**; final combined validation is **IN_PROGRESS**.
