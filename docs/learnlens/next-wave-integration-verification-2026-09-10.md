# Next-wave integration and verification — 10 September 2026

Status: **PREPARATION_IN_PROGRESS; full combined validation NOT STARTED**. The coordinator must supply the final promoted-main/browser-correction source and explicitly release full validation before this branch freezes. No current-main promotion is performed here.

## Source and scope

The isolated branch `codex/integrate-next-wave-20260910` began at coordinator candidate `ece4bedd41c36c7c37e89a10ce20fcd96a329f0f` in `.tmp-next-wave/worktree`. The shared primary checkout is not edited or switched. Personal author and committer are Jordan Tran `<226841807+jordann-trann@users.noreply.github.com>`; global configuration is unchanged. No push, paid provider, participant work or production research activation is authorized or performed.

Reviewed deliveries merged in order, with no textual conflicts:

| Delivery | Reviewed source | Integration |
| --- | --- | --- |
| Task 34A governed instruments | `686e300c7cfdcc477ac2b078be97b3e391d413b3` | `562962e` |
| Task 38A runtime controls | `edaedcd5eea3e1eb2a36a3f2d3a0ff18ec789961` | `c1375e0` |
| Task 37 recovery source | `e795bda6b64be581f9af625978dec49d85e79266` | `fb70b24` |
| Task 37 final evidence note | `fefbd99bd6421d07706017fd21d8bdb2146de9d5` | `70db4cc57c8fdf6d4d09e2e9ef8bc57f3c142db2` |

Owner scope and original receipts remain in [Task 34A](task-34a-governed-instruments.md), [Task 38A](task-38a-runtime-controls.md), its [retry correction](task-38a-retry-exhaustion-correction.md), and [Task 37](task-37-integrated-recovery.md). The coordinator's uncommitted next-parallel-wave plan was read from the primary checkout without editing it.

## Integration corrections

The automatic security merge retained two identical `research-governance` dictionary keys. Ruff reproduced F601; removing the duplicate preserves exactly one 60/minute registration and the new independent `research-instruments` 60/minute bucket. Original technical-pair processing/export fields remain isolated from instruments. Migration 0046 is the sole new head and readiness uses 0046. The private-learner circuit-browser correction from the starting candidate remains intact.

Independent Standards and Spec reviews both identified one P2: the API feedback executor captured a RuntimePolicy for the running pipeline but created an unsnapshotted repository when recording an escaped failure. If an administrator changed the limit during context collection, failure recording used the new ceiling. Two regressions reproduced wrong persisted retry scheduling: 1→3 scheduled an unwanted retry; 3→1 prematurely terminalized. The executor now retains the successfully loaded policy for failure recording; if resolution initially fails, it retries the same injected loader rather than bypassing it with global defaults. Both reviewers cleared the correction after inspection.

The first two test-authoring attempts referred to claim-view fields on the ORM row and failed with AttributeError. After correcting the assertions to actual persisted `current_stage` and `next_retry_at`, both cases failed on the intended scheduling discrepancy before the application fix. Final focused execution includes both passing regressions. No production clocks, leases, human decisions or retry ceilings were weakened.

Canonical OpenAPI and generated TypeScript were regenerated using repository tools and match their combined schemas. The Task 35 mandatory fingerprints additionally cover the changed runtime-policy, provider transport, executor, workflow repository/worker and task-generation runtime dependencies. Preparation regenerated the manifest, all dependent draft bundle/forms and numerical evidence. The initial numerical-only command did not refresh drafts, and the draft runner still reported stale runtime provenance; the required separate preparation command resolved it. The final report has no stale/manifest blocker, **108 DRAFT cases, zero approved, quality UNVERIFIED and AI release PENDING**. All **12/12** numerical distributions match; this supplies no expert approval or model-quality evidence.

## Focused preparation receipts

All runs use existing Python 3.11.16 and Node 22.13.0. Frontend dependencies were copied into this worktree from the matching-lockfile installation; shared dependencies were not mutated. Python subprocess checks use fresh short Windows OS-temp roots. Raw logs, JUnit and draft reports stay in this worktree's ignored `.tmp-next-wave-checks/` directory.

| Check | Result |
| --- | --- |
| Runtime controls, retry exhaustion, feedback application, database worker and LLM client | 64 passed in 66.58 seconds |
| Instruments, governance, streaming, security, readiness/health and validation tooling | 216 passed in 173.78 seconds |
| AdminWorkspace and App components | 32 passed in 22.59 seconds |
| TypeScript and focused administrator ESLint | PASS |
| Backend Ruff / formatting | PASS, 504 files formatted |
| Root launcher/checker tests | 13 passed plus 9 subtests in 11.65 seconds |
| Baseline traceability and manual-kit checks | 143 exact rows/446 references; 9 kit documents, 58 links, 36 UI routes and 27 blank cases, no errors |
| Canonical OpenAPI and generated TypeScript drift | PASS after combined generation |
| Task 35 numerical consistency | 12/12 match; all 108 cases remain unapproved drafts |
| Combined migration/recovery, benchmark probe and post-refresh tooling | RUNNING; final receipt pending |
| Full backend coverage, full frontend and browser matrices | NOT STARTED; awaiting coordinator release |

The source reviews found no additional confirmed material defect within the assigned slices. Their standards and spec findings were recorded separately and both corrected; source review is not test execution. Full-service coverage, browser counts, dependency/security checks and final-source evidence will be appended only after actual execution.

## Remaining product and release work

The proposed canonical reconciliation moves Task 34 from remaining to partial (29 completed / 11 partial / 1 remaining, Task 41) because versioned synthetic instruments, governed stage records and missingness/deviation/attrition now exist. It still needs approved instruments/support manifests, learner/researcher UI, reviewer packets/ratings, allocation, outcomes and complete approved study exports. Production research remains closed. Task 38 supplies runtime timeout/infrastructure-attempt controls and partial administrator saves; budget reservations/enforcement, full metering, approved pricing/providers and representative load/cost evidence remain later work. The fixed single quality regeneration is separate from infrastructure retries.

Task 37's original seven-case synthetic receipt is local recovery evidence, with a 1 ms injected initial API lease and real 30-second worker leases, no second submission, and same-human-review-state backup/restore comparison. Repeating it after migration 0046 is focused integration evidence, not hosted TLS, live-provider recovery, institutional approval or complete Task 37 sign-off. Human accessibility/usability and expert/evaluator approvals remain open. Independent requirements review recommends NFR30/AC18 move MISSING to PARTIAL: substantial governed capture exists, while approved pilot capture and complete experience/reviewer workflows remain due. No pilot acceptance is implied. The canonical ledgers will be reconciled after final-source integration; no full Task 34/38 or release-completion claim is made.
