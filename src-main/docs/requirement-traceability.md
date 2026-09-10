# Feedback and research integration traceability

Inspected integration: `6d20416c6760d4841828c9e59cc74679d8ca0ae7`, 10 September 2026. **Combined final validation: IN_PROGRESS.**

Current next-wave validation: **IN_PROGRESS** at frozen application/test source `6d20416c6760d4841828c9e59cc74679d8ca0ae7`. Full frontend: 319 tests across 85 files passed; lint, types, build, dependency audits, contracts, Ruff and migration-head checks passed. Full backend coverage and all 132 browser cases are still being verified. The first browser run loaded the primary checkout backend through its editable installation; that mixed-source run is diagnostic evidence only and must be repeated with worktree imports pinned. No current combined PASS, expert approval, research activation or hosted-release acceptance is claimed.

The [current implementation gap matrix](../../docs/learnlens/implementation-gap-matrix.md) is the authoritative status ledger for every numbered requirement. Its 143 rows link each controlling definition to precise production/service/route/model/migration/UI paths, named fixture tests, dated evidence, current gap, dependency and acceptance check. This file is a crosswalk, not a second independently maintained status table.

Definitions and settled policy remain in [implementation requirements](../../docs/01-implementation-requirements.md), [assessment specification](../../docs/02-pass-incomplete-bloom-assessment-spec.md), [work order](../../docs/03-codex-implementation-work-order.md) and [Task 8 selections](../../docs/learnlens/task-08-approved-selections.md). The [baseline report](../../docs/learnlens/task-36-requirements-reconciliation.md) and [main audit](../../docs/learnlens/main-audit-2026-09-10.md) remain evidence at `27a397a`, not an audit of the later integrated tree.

## Person 4 capability crosswalk

The original Person 4 brief is a subset of the expanded product. Every ID below resolves to the exact current matrix row; ranges include every integer ID between their bounds and duplicate references are not counted again. The companion [complete-family crosswalk](requirements-traceability.md) accounts for all 143 definitions.

| Requirement IDs | Capability | Evidence catalog in current matrix / baseline report |
| --- | --- | --- |
| FR15, FR28, NFR9 | Durable feedback orchestration and connected loop | E-FEEDBACK, E-LOOP, E-RECOVERY; I-MAP; full interface documentation/final integration still scoped by NFR9 |
| FR16, NFR12, NFR13, NFR21 | Grounded actionable feedback and educational safety | E-FEEDBACK, E-RESULT, E-TUTOR; I-EXPERT; actual expert measurements remain absent |
| FR17, FR18, NFR14, NFR23 | Quality review, one regeneration, fixed safe fallback | E-FEEDBACK, E-EVAL, E-RECOVERY; I-EXPERT; fixture judge pass is not AI-assessment approval |
| FR15–FR18, NFR7, NFR21 | Authorized feedback states, reports and accessible UI | E-FEEDBACK, E-ESCALATION, E-ACCESS; I-ACCESS, I-LOAD; human/access/load evidence remains open |
| FR20, NFR16, NFR20 | Operational evidence, purpose separation and audit | E-EVIDENCE, E-SECURITY; I-GOV; full study-stage instruments remain Task 34 |
| FR20, NFR12–NFR14, NFR22, NFR25 | Technical research pairs, quality metrics and usage records | I-GOV, I-EXPERT, I-LOAD; technical comparisons do not demonstrate educational improvement |
| NFR16, NFR25, AC10 | Governed restricted export | I-GOV supersedes unrestricted legacy v1/analytics authorization claims; live processing closed, full study export incomplete |
| NFR16, NFR20, NFR21 | Scoped analytics, output reporting and audit | E-PROGRESS, E-SECURITY, E-ESCALATION; I-GOV, I-TIME; no learner grades from research/quality metrics |
| FR28, AC4, AC6, AC8, AC10 | End-to-end learner/feedback/continuation and research boundaries | E-LOOP, E-FEEDBACK, E-ADAPT; I-GOV; complete local quantum loop is delivered but study export/release acceptance remains partial |

Catalog prefixes refer to exact source/model/migration/frontend and named-test paths in the [matrix](../../docs/learnlens/implementation-gap-matrix.md#integrated-evidence-register) and its linked immutable baseline catalog. Current matrix gaps and I-* overrides control where old catalog prose differs from integrated code.

## Scenario evidence and its limits

| Scenario | Existing connected/focused evidence | What it does not prove |
| --- | --- | --- |
| Correct/incorrect answer, code explanation, quantum response | Feedback source/response validation and complete-loop fixtures; E-FEEDBACK/E-EPISODE/E-QISKIT/E-LOOP | Expert factual accuracy or all alternate formats |
| Rejection then successful regeneration; two rejections | Named pipeline/tutor retry/fallback cases in E-FEEDBACK/E-TUTOR | Quality thresholds on an approved expert dataset |
| Provider timeout, missing retrieval, simulation failure | E-FEEDBACK/E-QISKIT/E-RECOVERY cases preserve accepted work and safe error states | Complete hosted/live-provider drills or latency targets |
| Export after technical-pair completion | I-GOV tests exact approved scalar fields, before-byte/between-row consent/grant rechecks and audit | Production availability, complete learning-study stages, raw-answer export or actual institutional approval |
| Withdrawal/refusal/condition changes | I-GOV actual ledger transitions preserve non-research/formal history and ordinary adaptation | Approved live participation or final study data completeness |
| Worker recovery and learner choice | E-LOOP/E-ADAPT plus I-PRACTICE connect protected typed evidence, model and next activity; I-LOAD adds a real single-learner local compatibility receipt | API background feedback in the benchmark does not prove durable recovery, full load/cost acceptance or second-subject reuse |
| Browser/accessibility | Prior automated journeys plus integrated I-ACCESS keyboard/removal and explicit live/saved CX text fixes | Native Safari, manual screen reader/zoom, first-time usability or full key-path WCAG acceptance |

The original fixture harness deliberately replaces provider/security/research boundaries for deterministic cases. Its export scenario cannot be cited as proof that the production release gate is open. Real provider access remains forbidden in ordinary automated tests; the separate Task 38 receipt uses real local HTTP and local providers only. It proves typed input compatibility, not external-provider execution, representative load or billed cost; those campaigns still require configured approvals.

## Release handoff

Full combined validation is **IN_PROGRESS**. The focus correction is integrated; final browser evidence and external acceptance gates remain distinct.

Current source changes, named production/tests and evidence boundaries are in [I-WAVE](../../docs/learnlens/implementation-gap-matrix.md#i-wave). Task 34A instruments, Task 38A runtime controls, Task 37 local recovery and the assessor focus fix are integrated. **12 tasks remain unfinished**; final combined validation is **IN_PROGRESS**.
