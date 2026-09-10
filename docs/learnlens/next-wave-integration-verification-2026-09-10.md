# Next-wave integration and verification — 10 September 2026

Status: **IN_PROGRESS — combined validation is not yet a pass**. Application/test source froze at `6d20416c6760d4841828c9e59cc74679d8ca0ae7` after integrating coordinator main `4f26d05b05a682e7cd90031ed81fbadb2bb56faa` and the final assessor-focus correction `b0f6f122691b73e74310985c8c701158df258755`. Coordinator documentation commit `1047522b823620e5133c2d53afd8758233c9469c` was merged while tests continued; it changes no application/test source. The coordinator owns root/main promotion and GitHub publication.

**12 of 41 numbered tasks still need work: 29 completed implementations, 11 partial and one remaining (Task 41).** The [master checklist](../../LearnLens_Remaining_Tasks.md#concrete-work-left-after-the-local-changes) gives one concrete action for each unfinished task. Task 34 moves to partial because its instrument foundation is implemented; this is not full study or release approval.

Current executed receipts: **319 frontend tests across 85 files passed in 203.76 seconds**, zero failed/skipped; full ESLint, TypeScript and production build passed. Backend Ruff/format (556 files), generated contract drift, sole migration/readiness head 0046, uv lock check, Python dependency audit and both full/production npm audits passed. Python audit inspected the existing environment through an isolated audit tool. npm audits used an exact copy of all 425 public registry dependency lock entries with only the project root identity replaced by a synthetic name; each dependency entry was verified identical, no installed dependencies or source lockfile changed, both reports contain zero known vulnerabilities. The existing Vite chunk-size advisory remains.

Full backend coverage (1,607 collected cases) and all 132 configured browser cases are running on fresh synthetic databases, short OS-temp directories and private API/web ports 4820/4813. The first browser run failed administrator routes because the shared virtual environment editable installation resolved the older primary-checkout backend. Its mixed-source results are retained as diagnostic evidence only. Pinning PYTHONPATH to this worktree resolves app and SettingsRead here and exposes both runtime fields; all configured cases must be rerun. The initial three-engine browser group finished 87 passed / 6 administrator-route failures in 8.2 minutes; none counts as final-source backend evidence. Its full log/report/runner are preserved under browser-mixed-checkout. The corrected full rerun is underway. The backend run has also observed a legacy-retirement round-trip failure; its test still expects head 0045, but the final traceback must confirm the cause before correction. No combined browser/backend pass or final secret-scan pass is claimed. Final receipts will be appended after actual execution.

## Source and scope

The isolated branch `codex/integrate-next-wave-20260910` began at coordinator candidate `ece4bedd41c36c7c37e89a10ce20fcd96a329f0f` in `.tmp-next-wave/worktree`. The shared primary checkout is not edited or switched. Personal author and committer are Jordan Tran `<226841807+jordann-trann@users.noreply.github.com>`; global configuration is unchanged. The user later authorized personal-account publication. The coordinator published main 1047522 and integration branch 1076ba2, then delegated subsequent branch publication and final validated main fast-forward after its task became idle. No paid provider, participant work or production research activation is authorized or performed.

Reviewed deliveries merged in order, with no textual conflicts:

| Delivery | Reviewed source | Integration |
| --- | --- | --- |
| Task 34A governed instruments | `686e300c7cfdcc477ac2b078be97b3e391d413b3` | `562962e` |
| Task 38A runtime controls | `edaedcd5eea3e1eb2a36a3f2d3a0ff18ec789961` | `c1375e0` |
| Task 37 recovery source | `e795bda6b64be581f9af625978dec49d85e79266` | `fb70b24` |
| Task 37 final evidence note | `fefbd99bd6421d07706017fd21d8bdb2146de9d5` | `70db4cc57c8fdf6d4d09e2e9ef8bc57f3c142db2` |

Owner scope and original receipts remain in [Task 34A](task-34a-governed-instruments.md), [Task 38A](task-38a-runtime-controls.md), its [retry correction](task-38a-retry-exhaustion-correction.md), and [Task 37](task-37-integrated-recovery.md). The coordinator's next-parallel-wave plan is integrated through main 4f26d05; its earlier uncommitted copy was read without editing the primary checkout.

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
| Backend Ruff / formatting | PASS across the full backend tree, 556 files formatted |
| Root launcher/checker tests | 13 passed plus 9 subtests in 11.65 seconds |
| Baseline traceability and manual-kit checks | 143 exact rows/446 references; 9 kit documents, 58 links, 36 UI routes and 27 blank cases, no errors |
| Canonical OpenAPI and generated TypeScript drift | PASS after combined generation |
| Task 35 numerical consistency | 12/12 match; all 108 cases remain unapproved drafts |
| Combined migration/recovery, benchmark probe and post-refresh tooling | 120 passed / 4 migration assertion failures in 353.65 seconds; all seven recovery cases passed (56.35 summed case seconds), benchmark/provenance cases passed; corrected four assertions plus assessment contracts/populated-instrument guards: 18 passed in 59.80 seconds |
| Full backend coverage and browser matrices | IN_PROGRESS at frozen source 6d20416; administrator-demo browser failure under investigation |
| Full frontend suite / lint / types / build | 319 tests across 85 files passed in 203.76 seconds; all checks PASS |

The focused 124-case batch reproduced four older downgrade-history assertions: the only differences were the five empty 0046 instrument tables safely removed before an earlier populated-history guard halted the downgrade. The shared comparison helper already omits explicitly named empty removable extensions. Adding only the five new table names under its unchanged zero-row condition preserves every populated table and digest. Independent Standards review cleared this correction; dedicated populated-instrument refusal tests still compare the full database manifest. Production migration 0046 is unchanged.

The first narrow correction rerun passed five cases but one case failed during isolated import, before its assertions: importing task_review first enters assessment/access through the assessment package initializer, which eagerly imports definitions and then the partially initialized TaskReviewService. All four relevant source files are unchanged from ece4bed. The assessment-contract/normal-API-composition rerun passed all 18 cases in 59.80 seconds and is retained separately; it validates integration but does not fix standalone importability. This pre-existing defect is a follow-up outside the owned integration; a minimal later fix can defer the sole definitions-to-TaskReviewService import and test both fresh-process import orders.

The coordinator reproduced a separate assessor-dialog return-focus race: evidence resolves while the asynchronous Confirm access check remains pending, consuming the return target before the dialog opens. Final correction b0f6f12, including two deterministic Cancel/Confirm regressions, is now integrated; both pass in the full 319-test frontend suite. The intermediate f71b9d18 alone was not treated as complete. This finding is distinct from the earlier unconfirmed WebKit empty-reason timeout; no causal explanation of that older timeout is claimed. Full browser execution remains pending.

The source reviews found no additional confirmed material defect within the assigned slices. Their standards and spec findings were recorded separately and both corrected; source review is not test execution. Full-service coverage, browser counts, dependency/security checks and final-source evidence will be appended only after actual execution.

## Remaining product and release work

The proposed canonical reconciliation moves Task 34 from remaining to partial (29 completed / 11 partial / 1 remaining, Task 41) because versioned synthetic instruments, governed stage records and missingness/deviation/attrition now exist. It still needs approved instruments/support manifests, learner/researcher UI, reviewer packets/ratings, allocation, outcomes and complete approved study exports. Production research remains closed. Task 38 supplies runtime timeout/infrastructure-attempt controls and partial administrator saves; budget reservations/enforcement, full metering, approved pricing/providers and representative load/cost evidence remain later work. The fixed single quality regeneration is separate from infrastructure retries.

Task 37's original seven-case synthetic receipt is local recovery evidence, with a 1 ms injected initial API lease and real 30-second worker leases, no second submission, and same-human-review-state backup/restore comparison. Repeating it after migration 0046 is focused integration evidence, not hosted TLS, live-provider recovery, institutional approval or complete Task 37 sign-off. Human accessibility/usability and expert/evaluator approvals remain open. Independent requirements review recommends NFR30/AC18 move MISSING to PARTIAL: substantial governed capture exists, while approved pilot capture and complete experience/reviewer workflows remain due. No pilot acceptance is implied. The canonical ledgers now record that foundation and the unchanged 12 unfinished tasks; no full Task 34/38 or release-completion claim is made.

Preparation is complete with the baseline isolated-import limitation retained. The final source and focus correction are now integrated, and full suites are in progress. The retry/provenance correction is committed at `d988a70`; preparation commit `071913130ebe3b01d088468fa42dbed7fa007d1f` records the empty-table comparison correction. No full combined validation pass is claimed.
