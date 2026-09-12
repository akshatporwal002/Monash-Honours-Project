# LearnLens task progress and remaining work

Updated: **12 September 2026**. Current pushed runtime is `2b9c951`; [CI run 34668835636](https://github.com/akshatporwal002/Monash-Honours-Project/actions/runs/34668835636) completed successfully across all four jobs. Backend: 2,077 passed, one warning, 90.18% service coverage. Task 36 execution and traceability are reconciled for this source; historical receipts remain source-specific. The failed 50-user campaign and unresolved WebKit reliability remain Tasks 38 and 39.

**30 of 41 numbered implementations are delivered; 11 tasks still need software or acceptance work.** The count is **30 completed, 10 partial and one remaining**. Unfinished tasks include engineering and acceptance work; they are not eleven missing features. Read each task's **Progress**, **Next action**, acceptance condition and evidence link before starting work.

| Work state | Tasks | Meaning |
| --- | --- | --- |
| Completed numbered implementation | 1–7, 9–27, 29–31, 36 | Functionality is delivered. Maintain it; broader load, human and release acceptance stays in the dependent tasks. |
| Active software/reliability work | 38, 39 | SQLite contention/continuation load and unresolved WebKit reliability remain. Delivered fixes are pushed and verified; further changes need affected tests and new CI. |
| Human/external acceptance primarily outstanding | 8, 28, 32, 33, 34, 35, 37, 40, 41 | Tooling largely exists; actual approvals, people, content or an approved environment are missing. Task 39 also retains manual acceptance alongside its unresolved browser flake; Task 33 may need additional disposal implementation after the data plan is approved. |

Task 30's functional reminder rules and measured candidate-scan repair are delivered; remaining campaign performance is tracked in Task 38. Likewise, Task 22's continuation functionality exists while its load-time queue delay remains unresolved; the reviewed decision-scope repair has eight focused checks and is included in the failed `ad187aa` load measurement. Completed implementation does not certify performance or release acceptance.

## Source and verification snapshot

This is a dated snapshot, not a live Git status. Pushed runtime `2b9c951` includes the duplicate-panel key repair and omission of an unused continuation learner-model view, alongside the earlier scoped read optimizations. Its clean 50-user campaign failed. Backend, frontend, security and dependency CI succeeded. A later benchmark-only hot-journal export repair passed 32 focused checks and independent review; it is not a new runtime load result. Runtime journal configuration is unchanged: a corrected private DELETE/WAL comparison found no overall WAL benefit. Private write-admission work is complete: the gate worsened total/status and worker timings despite improving terminal reads, so no runtime gate was shipped.

| Evidence | Source and result | Limit |
| --- | --- | --- |
| Current runtime CI | `2b9c951`: [CI run 34668835636](https://github.com/akshatporwal002/Monash-Honours-Project/actions/runs/34668835636); **all four jobs SUCCESS**. Backend job `103486157887` completed at `2026-09-12T03:17:09Z`: **2,077 passed**, one warning, **1,448.33 s (24:08)**, **90.18% service coverage**. | Configured checks do not close the failed load target or manual/hosted acceptance. |
| Frontend CI | `2b9c951`: **SUCCESS**, 396 unit tests in 97 files; 124 ordinary browser first-attempt passes; three complete-loop first-attempt passes plus WebKit retry #1; four misconception first-attempt passes. | The complete-loop final error list captured a learner-preferences same-origin access-control message after the next-activity assertion. Artifact `10289832868` is retained; this CI cause remains unproven. |
| Security/dependencies | `2b9c951`: security and dependency jobs succeeded. | Source-specific automated checks; hosted TLS/scanner efficacy and release acceptance remain separate. |
| Feedback-status optimization | Included in pushed `ad187aa`: non-content status responses return before release-context loading, **49 SELECTs to zero**, identical response; **19 focused release/access checks passed in 41.56 s**. | Terminal-content release/access checks remain enforced; the combined campaign still failed. |
| Suppression/exclusion audit | [Audit and accountable maintenance roles](docs/learnlens/lint-suppression-audit-2026-09-11.md) recorded; five E402 suppressions removed by moving imports. | Import cleanup is included in the successful `ad187aa` CI; reasons and maintenance roles remain documented. |
| Local simulation fix | `7dddf9d`: **46 distinct focused checks**, **12/12 numerical scenarios matched**; fresh learner evidence and execution limits preserved. | Historical numerical receipt; identical-input reuse does not prove diverse-input throughput. |
| Latest 50-user load campaign | Clean `2b9c951`: **31/50 awaiting human**, six continuation timeouts and 13 request timeouts; **ordinary p95 5.6019665 s**, progress **1.9939775 s**, formative feedback **27.481452 s**, assessed response **49.523947 s**. | **Failed**, with 38% journey errors and 18/5,454 HTTP errors. Ordinary: 297 observations, one censored; progress: 80; formative: 31; assessed: 70. Timings are conditional; no human-confirmed completion or actual external billing. |

Historical full-CI receipts remain source-specific: `ad187aa` passed with 2,075 backend tests, one warning and 90.21% service coverage; `dff979d` passed with 2,067 backend tests and 90.19% coverage. Earlier run 34558650591 failed overall. Current `2b9c951` has its own completed backend receipt: 2,077 passed and 90.18% service coverage. [Integration evidence](docs/learnlens/integration-verification-2026-09-11.md) and [capacity evidence](docs/learnlens/task-38-local-capacity-20260911.md) retain exact source/run scopes, failures and limits. Focused counts overlap and must not be added into a claimed complete suite.

The migration/readiness head is `20260911_0055`. The [current requirement matrix](docs/learnlens/implementation-gap-matrix.md) covers **143 requirements: 97 implemented, 33 partial, 13 unverified**. Requirements and numbered tasks use different denominators. The matrix's delivery register and each task's evidence links describe implemented features; older reports retain historical scope.

## Next software work, in order

**Local repair progress, 12 September:** checkpoint and transfer responses now
preserve each request's input and evidence in one transaction; affected checks
and independent review pass. The preference document-exit cancellation repair
passes nine affected unit checks and seven distinct focused WebKit cases, with
strict error assertions retained. Installed-package smoke verification and four
existing teammate guides are also complete locally. These changes await final
integration and combined CI. Task 38 performance investigation is active. A
paired feedback-view diagnostic reduced commits from 115 to 65 and total time
from 10.203 to 9.078 seconds, with 200/200 successful requests and equal retained
records in both arms; this does not establish full-journey capacity. The
[integration receipt](docs/learnlens/integration-verification-2026-09-11.md)
records exact test scope and limitations. This candidate work does not change
the 11-task acceptance count.

1. **Task 38 — resolve measured contention and continuation load.** Pushed `2b9c951` omits an unused continuation learner-model view (12 focused checks) and retains earlier scoped-read repairs. Its clean 50-user campaign still had 38% journey errors and missed ordinary/formative latency targets. A private write-admission gate also gave no overall benefit and was rejected; corrected DELETE/WAL diagnostics found no overall benefit, so runtime journal settings remain unchanged. A benchmark-only hot-journal export repair preserves committed data after owned-process shutdown (32 focused checks, independent review clear). Verify any actual runtime repair with affected tests and a clean campaign; do not increase deadlines to mask failures. Approved-host comparable 5–100 scaling and billed complete-loop cost remain missing.
2. **Task 39 — finish evidence-led browser reliability work.** Duplicate practice-panel/deadline sibling keys are fixed in `2b9c951`, with five mounted checks and one focused WebKit keyboard pass; permanent browser assertions reject orphaned panels across save/reload transitions. A private held-reload probe reproduced WebKit transport-console messages with no window error or unhandled rejection; separate positive controls validated the observers. This does not establish every CI flake cause: current CI retried WebKit complete-loop after a learner-preferences access-control message. Keep the retained context, diagnose the exact failure, and preserve runtime-error assertions. No error filter or timeout has been relaxed.

Earlier scoped repairs remain delivered: reminder candidate filtering passed 27 focused checks and reduced the copied-fixture scan from 2.422 seconds/2,922 SELECTs/25 write pairs to 0.016 seconds/one SELECT/zero writes. Pure task-read validation passed seven checks; a narrow 16-actor/32-request mounted diagnostic returned all HTTP 200, with dashboard p95 1.824 seconds and task GET p95 0.846 seconds. These earlier diagnostics exclude the full journey and do not override the failed clean campaign.

Approved-host deployment packaging remains unverified. Actual provider spending, study activation and human approvals require their real approved inputs. Task 33's approved data plan may reveal additional record-class disposal work; protected learning/assessment history must remain intact.

## Numbered task ledger

Each completed entry describes its delivered scope and names any acceptance dependency still tracked elsewhere. The original dependencies and completion criteria remain below so another contributor can check the intended requirement rather than infer completion from a test count.

1. **[Completed] Prevent unknown evidence from satisfying a negated pass rule.**

    **Progress:** Pass rules preserve unknown, missing and conflicting evidence through negation and nested Boolean expressions; they cannot fabricate a mandatory criterion pass.

    **Next action:** Implementation complete. Retain unknown/conflicting-evidence regression coverage in Task 36.

    Dependencies: none. Suggested owner: assessment backend.

    Done when regression tests cover those cases, including nested rules, while retaining explicit review reasons and the mandatory-criterion checks.

    Evidence: [current implementation/delivery](docs/learnlens/negated-pass-rule-repair.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

2. **[Completed] Require real evaluator rules before approving an assessment.**

    **Progress:** Typed evaluator settings are validated during authoring, approval and runtime. Empty or unsupported automatic rules are rejected; unsupported criteria route to human assessment.

    **Next action:** Implementation complete. Actual approved criterion/evaluator settings belong to Tasks 8 and 35.

    Dependencies: none. Suggested owner: assessment backend and assessor UI.

    Done when empty, unknown, or contradictory settings block approval and fail safely during evaluation. Test the actual UI-to-API authoring path.

    Evidence: [current implementation/delivery](docs/learnlens/evaluator-settings-repair.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

3. **[Completed] Repair task and dashboard reads after assessed submissions.**

    **Progress:** Assessed task reloads, histories and dashboards preserve absent marks and separate activity from formal results. Mixed histories no longer require invented numeric scores.

    **Next action:** Functional read repair complete. Remaining concurrent task/dashboard latency is tracked in Task 38.

    Dependencies: none. Suggested owner: LMS backend and frontend contracts.

    Done when task reload, learner dashboard, educator dashboards, recommendations, and history work after formal submissions. Include mixed legacy and assessed records. Do not convert missing scores to zero.

    Evidence: [current implementation/delivery](docs/learnlens/assessed-read-repair.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

4. **[Completed] Close the direct learner evaluation and visibility bypass.**

    **Progress:** Learner evaluation access, duplicate requests and provisional-result visibility are restricted. D-01 keeps pending verdicts hidden until authorized confirmation.

    **Next action:** Implementation complete. Keep pending verdicts hidden and retain scoped replay/visibility coverage in Task 36.

    Dependencies: none for the immediate restriction; Task 8, decision D-01, for approved learner visibility. Suggested owner: assessment API.

    Done when duplicate requests create no duplicate decisions and learners see only policy-approved information.

    Evidence: [current implementation/delivery](docs/learnlens/learner-evaluation-bypass-restriction.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

5. **[Completed] Restrict unapproved research processing and export access now.**

    **Progress:** Research access is separate from analytics and teaching permissions. Integrated Task 33 adds study/field/consent controls, while the production release gate stays closed.

    **Next action:** Immediate access restriction complete. Actual governed study activation belongs to Tasks 32–34 and 41.

    Dependencies: none for the immediate restriction. Governed activation follows Task 33. Suggested owner: access controls and research backend.

    Done when ordinary analytics access cannot authorise research exports. Missing approval, revoked permission, and disabled participation must prevent research processing without restricting course access or changing results.

    Evidence: [current implementation/delivery](docs/learnlens/research-access-restriction.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

6. **[Completed] Give every browser test its own assessment records.**

    **Progress:** Assessor browser actions use independent synthetic fixtures for confirm, override, withhold and return. The 124-case browser suite passed on 5a57b66. A later complete-loop test needed explicit work start and current field selectors; that correction is now pushed and is not an assessment-record isolation regression.

    **Next action:** Assessment-fixture isolation complete. Final combined browser verification is tracked in Tasks 36 and 39.

    Dependencies: none. Suggested owner: test infrastructure.

    Done when each action passes alone, in the complete browser run, and on retry without relying on another test. This audit did not reproduce a current browser launch failure.

    Evidence: [current implementation/delivery](docs/learnlens/browser-assessment-isolation.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

7. **[Completed] Start the durable worker and check actual readiness.**

    **Progress:** The launcher starts API/frontend/recovery worker, applies migrations and waits for readiness. The integrated readiness pin now matches head 0055. Configured combined readiness/recovery checks passed in Task 36 CI for `ad187aa`; earlier receipts retain their dated scope. The approved operational/hosted drill remains Tasks 37/41 work.

    **Next action:** Startup/readiness implementation complete. Worker throughput remediation belongs to Task 38; hosted supervision to Tasks 37 and 41.

    Dependencies: none for local template mode. Suggested owner: platform.

    Done when an accepted submission finishes after a worker restart without another submission request. Local mode and research settings must match the chosen adapters. Task 22 supplies the complete adaptive worker path.

    Evidence: [current implementation/delivery](docs/learnlens/durable-worker-startup.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

8. **[Partial] Record the decisions needed to activate each feature.**

    **Progress:** Policy selections are settled in D-01–D-12. Concrete course/source/form/staff/study/retention/environment and release records remain due; fixture approvals and user policy choices do not supply institutional or expert approval.

    **Next action:** Human input: record the actual approved courses, sources, forms, staffing, study/data-plan and release environment. Preserve settled D-01–D-12 selections; fixture records are not live approvals.

    Dependencies: none. Suggested owners: product owner, assessors, privacy, research, and operations.

    Done when each dependent feature has the specific approval it needs. Unrelated implementation can continue while a decision remains pending. Test fixture settings do not approve live policy.

    Evidence: [current implementation/delivery](docs/learnlens/task-08-approved-selections.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

9. **[Completed] Preserve the exact approved sources used by each output.**

    **Progress:** Exact approved source revisions, passages, approvals and citations remain immutable. Intake stores HTTPS bytes, quarantines uploads and enforces hash/policy/claim-bound scanning; historical source reads remain available within scope. Approved-source vector retrieval and operation-local source-approval batching are integrated. Course metadata/context has a separate versioned restore ledger. Actual approved scanner policy and efficacy remain external evidence.

    **Next action:** Immutable source handling complete. Obtain approved scanner/retention policy and operational efficacy evidence under Tasks 8, 33 and 37.

    Dependencies: none for versioned storage; Task 8, D-08, for retention and destructive deletion rules. Suggested owner: retrieval and data.

    Done when an authorised reviewer can recover the exact cited passage after a source changes. Keep course scope and page, slide, or heading locations intact.

    Evidence: [current implementation/delivery](docs/learnlens/task-09-source-history.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

10. **[Completed] Recover interrupted material processing.**

    **Progress:** Interrupted extraction/indexing can resume without duplicate or partially published source revisions. Original resources and processing state are preserved.

    **Next action:** Processing recovery implementation complete. Retain concurrent-claim and recovery coverage in final Task 36 CI.

    Dependencies: Task 9. Suggested owner: retrieval and worker.

    Done when a saved upload finishes or reports a recoverable failure after interruption. Concurrent workers must not publish duplicate or partial source revisions. Retain the original upload and useful processing status.

    Evidence: [current implementation/delivery](docs/learnlens/task-10-material-processing-recovery.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

11. **[Completed] Store trustworthy simulation evidence and enforce execution limits.**

    **Progress:** Bounded Qiskit/Aer execution retains settings, counts, exact probabilities, bit order, engine versions and text evidence. Local commit 7dddf9d adds a bounded 128-entry exact-result cache and shares identical concurrent calculations, while retaining two child-process slots, the original deadline and separate learner run/outcome records. Expert validity and native/manual accessibility remain separate acceptance.

    **Verified:** 46 distinct focused checks passed across overlapping receipts. All 12 numerical scenarios matched after the simulation change. A cold 12-caller diagnostic improved from four to 12 completions; that is repeated-input evidence, not diverse-input capacity.

    **Next action:** Simulation evidence implementation complete, including the pushed local exact-result reuse fix verified in Task 36. Diverse-input load and complete-loop latency remain Task 38 work.

    Dependencies: none. Suggested owner: quantum services.

    Done when runs are bounded and reproducible from saved settings. Use exact probabilities or sampling tolerances where justified. Gate presence or distribution agreement must not stand in for every state property or conceptual claim.

    Evidence: [current implementation/delivery](docs/learnlens/task-11-simulation-evidence.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

12. **[Completed] Finish educator approval, assessor setup, and publication controls.**

    **Progress:** Explicit educator review, current source approval, assessor eligibility and publication validation block unreviewed or invalid assessed tasks. New approvals enforce full BP3 criterion/result alignment and complete task-category quality review while preserving historical approvals. A real course still needs its named content approvals.

    **Next action:** Publication controls complete. Supply real course-specific source, content and assessor approvals under Task 8.

    Dependencies: Tasks 2 and 9; Task 8, D-02, D-04, and D-05. Circuit publication also needs Task 11. Suggested owner: course and assessment teams.

    Done when an authorised assessor can publish a valid form without test overrides. Unreviewed generated tasks and unsupported circuits must remain unavailable to learners.

    Evidence: [current implementation/delivery](docs/learnlens/task-12-publication-controls.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

13. **[Completed] Freeze assessment versions when the learner starts work.**

    **Progress:** Starting assessed work freezes approved task/outcome/criteria/rule and conditions. The learner now explicitly activates Start assessed task before response, support or writes; resumed drafts revalidate their original work reference. Later changes preserve the bundle or return a conflict, and practice is not rebound to assessment.

    **Verified:** The locally corrected complete-loop browser test asserts the tutor is absent before explicit assessed start and visible afterward, then completes the journey.

    **Next action:** Start/freeze implementation complete. Integrate the locally repaired complete-loop browser fixture under Tasks 36 and 39.

    Dependencies: Tasks 8 and 12. Suggested owner: assessment and task workspace.

    Done when a rule change during an open draft preserves the original approved bundle or returns an explicit conflict. A later version must never silently replace the declared standard.

    Evidence: [current implementation/delivery](docs/learnlens/task-13-start-freeze.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

14. **[Completed] Complete the learning episode inside the task workspace.**

    **Progress:** Typed prediction, reasoning, code/circuit, revision, reflection and transfer retain drafts/submission/history. Matching/sequencing use typed definitions and opaque IDs; choices validate declared IDs without fallback content. Source-led basic and multipart generation, reviewed current-task variants, accepted-feedback conditioning and generated support drafts are integrated with frozen source references and publication gates. Unaided-transfer restrictions remain enforced. PD4 explicitly permits the five documented extension contracts to stay staged; actual semantic/content approval remains separate.

    **Next action:** Learning-episode implementation complete. Preserve end-to-end draft/reload/transfer behavior in final CI; expert/accessibility acceptance belongs to Tasks 35 and 39.

    Dependencies: Tasks 11 and 13; Task 8, D-04 and D-05, for approved assessed stages. Suggested owner: task engine and frontend.

    Done when each supported response survives draft, submit, reload, revision, and controlled simulation failure. Every type needs accessible controls, evidence extraction, evaluator support, and export representation.

    Evidence: [current implementation/delivery](docs/learnlens/task-14-learning-episode.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

15. **[Completed] Make unsupported assessment criteria reachable by a human assessor.**

    **Progress:** Human assessors inspect frozen evidence, evaluate criteria and confirm/override/withhold/return/void with retained history. Live sampling, blind second review, drift/disagreement resolution and immutable correction cycles now gate confirmation. Evaluator fingerprints/expiry invalidate stale validation; actual expert release and separate advisory AI activation remain outstanding.

    **Next action:** Human-assessment workflow complete. Actual reviewer training, sampling and separate advisory AI release belong to Tasks 28 and 35.

    Dependencies: Tasks 1, 2, 11, 12, and 13. Suggested owner: assessment backend and review UI.

    Done when an assessor can inspect evidence, record criterion decisions and reasons, apply the pass rule, and finalise the result. Keep operational AI assessment suggestions disabled until Task 35 passes its separate approved gate. After that gate, suggestions remain advisory and humans confirm results.

    Evidence: [current implementation/delivery](docs/learnlens/task-15-human-assessment.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

16. **[Completed] Deliver grounded assessed feedback under the approved help policy.**

    **Progress:** Grounded feedback enforces current source/help/release conditions, complete ten-dimension review for new generated feedback, one regeneration and a fixed safe fallback. Immutable quality receipts and original/intermediate response-hash compatibility are integrated. Feedback approval never confirms a formal assessment result.

    **Next action:** Grounded-feedback implementation complete. Actual content-quality ratings and release decisions belong to Task 35; concurrent feedback performance belongs to Task 38.

    Dependencies: Tasks 9, 11, 12, and 15; Task 8, D-05. Suggested owner: feedback and retrieval.

    Done when approved feedback states missing evidence without exceeding allowed help. Preserve one regeneration, fixed fallback, rejection reasons, and source/model/prompt/rule versions. Feedback approval must not confirm an assessment result.

    Evidence: [current implementation/delivery](docs/learnlens/task-16-grounded-feedback.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

17. **[Completed] Capture learning evidence through the live application.**

    **Progress:** Live interactions append scoped, ordered, replay-safe evidence linked to immutable response/task/source/support history. Newly captured representation support resolves the maximum applicable frozen declaration with existing time/stage filters; worked-example/stepwise intensity reaches supported evidence while unaided transfer stays independent. Historical observations are not reclassified.

    **Next action:** Live evidence capture complete. Preserve exact original hashes, scope and immutable history in final CI.

    Dependencies: Tasks 9, 11, and 14. Suggested owner: evidence services.

    Done when a real learner journey creates an authorised, ordered evidence timeline. Replays and partial failures must preserve originals without duplicate accepted observations.

    Evidence: [current implementation/delivery](docs/learnlens/task-17-live-evidence.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

18. **[Completed] Update the shared learner model from real evidence.**

    **Progress:** Evidence produces versioned cumulative learner estimates with uncertainty, provenance and concurrency/replay controls. The integrated profile dimensions and educator interpretations link back to supporting evidence. These remain unvalidated teaching estimates, not mastery measurements or grades.

    **Next action:** Learner-model implementation complete. Actual construct validity and learning-effectiveness evidence belong to Tasks 32, 34 and 35.

    Dependencies: Task 17. Suggested owner: learner services.

    Done when concurrent or repeated processing creates consistent snapshots. Produce validated snapshots for teaching services. Tasks 22 and 23 must demonstrate decisions that change because of an estimate. Rule-based uncertainty must remain labelled as an unvalidated estimate until tested.

    Evidence: [current implementation/delivery](docs/learnlens/task-18-shared-learner-model.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

19. **[Completed] Integrate learner corrections and expose scoped evidence and model views.**

    **Progress:** Learners annotate/challenge evidence and model information; scoped educator review and later model updates retain the original records and correction history.

    **Next action:** Correction and scoped-view implementation complete. Retain immutable correction/replay coverage in Task 36.

    Dependencies: Tasks 17 and 18. Suggested owner: learner services and frontend.

    Done when learner corrections and scoped reviews preserve originals and are consumed by later snapshots without replacing history.

    Evidence: [current implementation/delivery](docs/learnlens/task-19-corrections.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

20. **[Completed] Add learner preferences and control over non-essential support.**

    **Progress:** Learner preferences, explicit override and non-essential support opt-out are delivered. Reviewed formative and assessed representations have immutable delivery evidence and frozen support intensity; transfer retains approved access-only alternatives. Source-grounded generated support drafts and source bindings are also implemented. Actual content equivalence and human acceptance remain due.

    **Next action:** Preference and generated-representation delivery complete. Human equivalence/content/accessibility acceptance remains under Tasks 8, 35 and 39.

    Dependencies: Tasks 14 and 17; Task 8, D-05, for assessed conditions. Suggested owner: learner experience.

    Done when preferences and opt-out persist, support remains separate from access, and no choice changes formal results or essential access.

    Evidence: [current implementation/delivery](docs/learnlens/task-20-learner-preferences.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

21. **[Completed] Build the curriculum links and approved diagnostic paths.**

    **Progress:** Approved curriculum graphs link outcomes, sources, forms, prerequisites and exit guidance. Diagnostics record learning evidence and require eligible assessor confirmation before practice bypass; they cannot replace formal assessment.

    **Next action:** Curriculum/diagnostic implementation complete. Obtain actual approved course graphs/forms under Task 8.

    Dependencies: Tasks 12, 18, and 20. Suggested owner: learning pathway services.

    Done when approved graphs and diagnostics enforce scope, independent conditions and human-confirmed practice bypass without granting formal credit.

    Evidence: [current implementation/delivery](docs/learnlens/task-21-curriculum-diagnostics.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

22. **[Completed] Connect learner evidence to the next approved activity.**

    **Progress:** The shipped worker connects eligible checked feedback to one model update and an approved activity suggestion. Accept/defer/replace, opt-out, stale approvals, overrides and recovery retain reasons and history. In the latest load run, timed-out continuation jobs eventually completed, but queue delay exceeded the harness deadline; functionality is delivered and capacity remains failed.

    **Next action:** Continuation functionality complete; measured queue delay remains unresolved under Task 38. The reminder-scan repair is implemented; measure the combined campaign before considering a worker scheduling redesign.

    Dependencies: None; coordinator verifies the integrated release.

    Done when accepted evidence causes exactly one model update and approved suggestion; choices, override, restart and stale-approval behavior preserve the standard.

    Evidence: [current implementation/delivery](docs/learnlens/task-22-approved-activity-continuation.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

23. **[Completed] Add tutor dialogue and a controlled sequence of hints.**

    **Progress:** Grounded tutor dialogue and reviewed support survive reload and stop instructional help during separate unaided transfer. Bounded retained dialogue and submitted answer/code/episode evidence create uncertain, deduplicated human-review cues and reasoning redirects with no penalty. Frozen scaffolding is excluded; stored responses and formal decisions are unchanged. Staff response and effectiveness require actual acceptance evidence; no plagiarism verdict is implied.

    **Next action:** Tutor/help controls complete. Actual staffing and teaching-quality evidence belong to Tasks 28 and 35.

    Dependencies: Tasks 16, 17, 18, and 20. Suggested owner: teaching services and task workspace.

    Done when conversation state survives reload, help follows assessed conditions, and outputs pass the feedback checks. Answer-seeking cues should redirect to reasoning without making an automatic misconduct finding.

    Evidence: [current implementation/delivery](docs/learnlens/task-23-24-tutor-and-results.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

24. **[Completed] Complete learner results, review requests, and appeal resolution.**

    **Progress:** Learner result views, review requests, assessor resolutions and notices preserve scope, reasons and decision history. Pending verdicts stay hidden; released results expose evidence and the next permitted action.

    **Next action:** Result/review implementation complete. Native assistive-technology and usability acceptance belongs to Task 39.

    Dependencies: Tasks 3, 4, 13, and 15; Task 8, D-01. Suggested owner: assessment experience.

    Done when requests and resolutions preserve scope, reasons, notices, and decision history. Learners must distinguish pending review from a confirmed result and reach every action without relying on colour.

    Evidence: [current implementation/delivery](docs/learnlens/task-23-24-tutor-and-results.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

25. **[Completed] Prove one complete quantum learning loop before expanding coverage.**

    **Progress:** Real persisted services connect prediction, simulation, checked feedback, revision/reflection, fresh transfer, learner-model update, approved activity and synthetic human confirmation. Backend complete-loop and recovery coverage passed in the integrated suite. The browser fixture now starts assessed work explicitly and uses visible assessor labels; that correction passed a focused Firefox journey.

    **Verified:** 5a57b66 backend CI passed; the later local complete-loop Firefox check passed in 35.7 seconds with retained evidence, human-result and accessibility assertions.

    **Next action:** Complete-loop functionality and the pushed browser-fixture correction are verified in completed Task 36 CI; 50-user performance remains Task 38.

    Dependencies: Tasks 10, 14, 16, 18, 22, 23, and 24, including their prerequisites. Suggested owner: integrated feature team.

    Done when one browser journey and backend integration test traverse the real services. Interrupt processing and prove recovery. A returned task ID or passing component test alone does not complete this milestone.

    Evidence: [current implementation/delivery](docs/learnlens/task-25-complete-learning-loop.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

26. **[Completed] Implement reassessment and outcome-level result selection.**

    **Progress:** Authorized reassessment uses a fresh equivalent form under the same standard, preserving earlier decisions. Published whole-decision outcome policies never average attempts or replace confirmed evidence with a pending attempt.

    **Next action:** Reassessment/result-selection implementation complete. Actual approved equivalent forms belong to Task 8.

    Dependencies: Tasks 12, 13, 15, and 24; Task 8, D-06. Suggested owner: assessment.

    Done when every earlier decision remains readable, the same standard applies, and attempts are never averaged. Review, return, withholding, reassessment, and result replacement must have distinct effects.

    Evidence: [current implementation/delivery](src-main/backend/tests/test_reassessment.py); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

27. **[Completed] Complete the misconception check and recovery cycle.**

    **Progress:** The committed, merged misconception cycle supplies reviewed probes, teaching, revision, fresh evidence, uncertain/persisted/weakened/corrected states, educator corrections and preserved exit/recovery. Unresolved reviews already feed Task 28's assessor queue.

    **Verified:** The unchanged misconception Firefox journey passed in 16.6 seconds, covering saved probe/help/revision/fresh evidence, human corrections, progress links and accessibility.

    **Next action:** Misconception cycle complete. Retain final four-browser coverage under Task 39; approved content and human effectiveness evidence remain separate.

    Dependencies: Tasks 18, 19, 21, 22, and 23. Suggested owner: learner and teaching services.

    Done when evidence can leave a hypothesis uncertain, persisted, weakened, or corrected. A single wrong response must not create a certain label. Show why the next intervention was selected.

    Evidence: [current implementation/delivery](docs/learnlens/task-27-misconception-cycle.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

28. **[Partial] Add a human escalation and AI-output reporting workflow.**

    **Progress:** Separate queues, ownership/triage, acknowledgement/action/resolution/closure, notices and feedback sampling are implemented, with misconception/tutor review cues and live assessment moderation. D-09 still needs named operators/backups, staffed calendar/timezone, approved targets/sampling, training and activation records.

    **Next action:** Human/operations input: name primary and backup operators, staffed calendar/timezone, response targets, sampling/training and activation authority. The queues and reporting workflow already exist.

    Dependencies: Tasks 15, 16, 19, 23, and 27; Task 8, D-09. Suggested owner: educator experience and operations.

    Done when a report moves through acknowledgement, action, resolution, and closure with an audit trail. Accepted AI feedback must also be available for human sampling.

    Evidence: [current implementation/delivery](src-main/backend/app/services/escalation.py); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

29. **[Completed] Finish progress views and retire numeric learner-result semantics.**

    **Progress:** Scoped progress separates observations, support, uncertain estimates, adaptations and released binary results. Numeric learner marks were retired after immutable preservation; known UTC timestamps normalize on reads. Backend and 124-case browser CI passed on 5a57b66, and the later focused misconception journey exercised linked learner/educator progress and correction history.

    **Next action:** Progress/result semantics complete. Configured combined verification passed in Task 36; concurrent latency remains Task 38 and human accessibility trials remain Task 39.

    Dependencies: Tasks 3, 18, 19, 22, 24, 26, and 27. Final legacy removal also needs Task 8, D-10. Suggested owner: LMS, analytics, and frontend.

    Done when each important indicator links to scoped evidence, UTC instants survive reload/display, and protected legacy history stays intact under immediate D-10 retirement. Quantum probabilities and technical quality measures remain separate.

    Evidence: [current implementation/delivery](docs/learnlens/task-29-progress-timezones.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

30. **[Completed] Move reminder writes out of dashboard reads and finish reminder rules.**

    **Progress:** Reminder writes run outside dashboard reads. Timezones/DST, extensions, access plans, opt-out, completion and rolling 24-hour guards are implemented. A later load diagnosis found unnecessary worker scans of tasks with no effective deadline: roughly 2,900 reads and 25 write/commit pairs per pass. The reviewed candidate-query optimization now passes 27 focused checks and reduces the same diagnostic pass to one read and zero writes; full-load acceptance remains Task 38.

    **Next action:** Functional reminder rules and the candidate-query repair are complete. Task 38 must measure the combined load; preserve latest deadline arrangements, revocations, opt-out and delivery limits.

    Dependencies: Tasks 20, 22, and 24. Suggested owner: LMS and worker.

    Done when repeated dashboard reads make no state changes. Test simultaneous processing, time-zone boundaries, extensions, completed work, and disabled notifications.

    Evidence: [current implementation/delivery](src-main/docs/reminders-and-backups.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

31. **[Completed] Make gamification optional and remove learner rankings.**

    **Progress:** Optional private participation rewards recognize learning activity without public ranking, score-driven awards or assessment/access penalties. Replays and retries cannot duplicate awards.

    **Next action:** Optional private gamification complete. Retain replay, opt-out and assessment-neutrality coverage in Task 36.

    Dependencies: Tasks 20 and 29. Suggested owner: learner experience and LMS.

    Done when points never alter assessment, pathway standards, or essential access. Replays, retries, slower pace, breaks, and approved support must not create penalties or duplicate rewards.

    Evidence: [current implementation/delivery](src-main/backend/tests/test_gamification_preferences.py); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

32. **[Partial] Approve the learning-study protocol and data plan.**

    **Progress:** Protocol and data-plan drafts exist; Arv Surana is the user-named research lead. Protocol/ethics/privacy/retention decisions, preregistration, approved instruments and other named authorities remain outstanding.

    **Next action:** Human input: obtain approved protocol, ethics/privacy/data plan, preregistration, instruments and named authorities before study activation.

    Dependencies: Task 8, especially D-03, D-07, and D-08. Planning can run alongside implementation. Suggested owner: research lead and governance.

    Done when an approved protocol covers unaided conceptual understanding, transfer, and any delayed-retention claims. Technical judge performance must not be presented as proof of learning improvement.

    Evidence: [current implementation/delivery](docs/learnlens/task-32-study-protocol.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

33. **[Partial] Enforce research permission, consent, and governed exports.**

    **Progress:** Append-only scopes/approvals, consent/refusal/withdrawal, eligibility, study/course/field grants, retention holds and governed technical-v2 processing/export are delivered. Study and operational capture/export recheck their separate purposes/permissions. Exact approved study-release receipts can enable governed use after deployment opt-in; no actual study has been enabled. Authorized restricted instrument text disposal is implemented with immutable receipts and restore exclusion. Actual approvals, record-class schedules and release-environment validation remain due; other deletion classes may require implementation after the approved plan resolves protected-history obligations.

    **Next action:** Human/external input: supply actual consent/grants, approved record-class schedules and deployment opt-in. Then verify activation/disposal in the approved environment; additional disposal classes may require software once protected-history obligations are resolved.

    Dependencies: Tasks 5, 9, 17, 18, 22, 24, and 32; Task 8, D-03 and D-08. Suggested owner: research backend and privacy.

    Done when unapproved processing and exports fail closed. Revoked access, withdrawal, and missing consent must be tested. Research condition and participation must not change teaching access, adaptation, or formal results.

    Evidence: [current implementation/delivery](docs/learnlens/task-33-governance-implementation.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

34. **[Partial] Build and verify the learning-study instruments and records.**

    **Progress:** Versioned instruments now have learner/researcher UI, self responses, missingness/attrition/deviation, allocation, redacted blinded packets, ratings/outcomes and dedicated full-study CSV/JSON export. Operational snapshots add exact consented response/stage evidence and source/redaction/authority revalidation during streaming. A pseudonymous stage reconciliation workflow now distinguishes missing, recorded and ambiguous evidence without inventing outcomes. Approved instrument/rubric/redaction content, actual participant records and activation remain due; technical-v2 is unchanged. See [study workflows](docs/learnlens/task-34-study-workflows.md) and [operational evidence](docs/learnlens/task-34-operational-evidence.md).

    **Next action:** Human/research input: approve instrument, rubric and redaction content, then collect/reconcile actual participant stages and export an approved sample through the existing workflows.

    Dependencies: Tasks 25, 29, 32, and 33. Suggested owner: research and analytics.

    Done when a complete approved sample exports in CSV or JSON with linked learning stages and no direct identity fields. Keep learning outcomes separate from feedback correctness and judge metrics. Label local template generation accurately.

    Evidence: [current implementation/delivery](docs/learnlens/task-32-data-plan.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

35. **[Partial] Validate quantum content, feedback, and assessment against expert judgements.**

    **Progress:** Offline tooling retains 108 DRAFT cases and blank review forms, zero approved cases and zero included system-output/rating pairs. Live moderation, signed evaluator release/import and ten-dimension human review are implemented. Current source fingerprints use the refreshed 123-entry draft manifest; historical numerical receipts and their paired manifests remain unchanged. Quality stays UNVERIFIED and advisory AI release PENDING.

    **Verified:** Current 127-entry draft manifest digest `f88aa8436570434cbcf1464f9a3b0c1e37714d34ec21d4c339ecf335ad7601b3`; 44 validation-tool checks pass. The historical 12-scenario numerical receipt remains bound to `3604cb3d6e8f2f10a479b2799baae9e2f22f047a73867133ac4f0daa887d921c`; its matching distributions supply no expert approval or new-source numerical execution.

    **Next action:** Human/expert input: approve at least 100 cases and source bindings, record actual outputs and independent ratings, calculate agreement/fairness/error measures, and sign separate content and AI-assessment release decisions. Maintain source fingerprints; the current draft digest does not replace historical numerical or expert evidence. Configured CI and traceability for `2b9c951` are complete under Task 36.

    Dependencies: Tasks 11, 15, 16, 23, and 25; Task 8, D-07 and D-12. Suggested owner: assessors and evaluation reviewers.

    Done when the approved evaluator gate passes. Required content targets include at least 80% factual accuracy, at most 5% hallucinations, and feedback review averaging 4/5. Judge rejection must reach 80%, with false rejection at most 20%. Establish a trained-human agreement baseline and report criterion agreement by task type with uncertainty. Test answer length, writing style, and approved access modes. Feedback and judge thresholds cannot clear the separate AI assessment release gate.

    Evidence: [current implementation/delivery](docs/learnlens/task-35-validation-tooling.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

36. **[Completed] Refresh traceability and run the complete automated checks.**

    **Progress:** All 143 requirements remain mapped: 97 implemented, 33 partial and 13 unverified. Traceability and automated-check implementation remain complete, with historical full CI for `ad187aa`. Current pushed `2b9c951` completed [CI run 34668835636](https://github.com/akshatporwal002/Monash-Honours-Project/actions/runs/34668835636): all four jobs succeeded; backend passed 2,077 tests with one warning and 90.18% service coverage. Tasks 38 and 39 remain open.

    **Verified:** Current frontend: 396 unit tests/97 files, 124 ordinary first-attempt browser passes, three complete-loop first-attempt passes plus WebKit retry #1, four misconception first-attempt passes. Security/dependency jobs succeeded. Historical `ad187aa`: 2,075 backend passes and 90.21% service coverage. Current backend job `103486157887` completed at `2026-09-12T03:17:09Z`: 2,077 passed, one warning, 1,448.33 seconds (24:08), 90.18% service coverage; no historical count is promoted to the new source.

    **Next action:** Configured execution and source-specific reconciliation are complete for `2b9c951`. Maintain traceability and run affected checks plus new CI for further repairs. Continue Tasks 38/39 independently; successful configured checks do not certify load, manual or hosted acceptance.

    Dependencies: Tasks 1-34 for the final combined run. Run targeted checks with each earlier change. Suggested owner: integration and independent reviewers.

    Done when evidence and independent review apply to the final commit. Keep manual and external checks separate. New dependency audits are required; the previously updated packages are not assumed to remain vulnerable or permanently safe.

    Evidence: [current implementation/delivery](docs/learnlens/task-36-requirements-reconciliation.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

37. **[Partial] Prove security, migration safety, restart recovery, and restore completeness.**

    **Progress:** Current-head upgrade/readiness, all-table backup/restore comparison, source-byte preservation and protected-history checks are implemented at head 0055. They passed in historical `ad187aa` backend CI and the current successful `2b9c951` configured backend suite. Approved-host/provider security and operational drills remain unverified.

    **Verified:** test_task37_integrated_recovery.py compares every table and source bytes after restore and checks readiness/protected histories. The post-`2b9c951` benchmark-only export repair uses normal SQLite recovery on the owned stopped synthetic fixture, cannot create a missing source, and explicitly closes both connections. Its hot-journal/committed-data regression is included in 32 focused passing checks; independent review found no blockers. This is distinct from a hosted recovery drill.

    **Next action:** Perform approved-host/provider security, restart, backup/restore and rollback drills with actual approved inputs. Keep benchmark fixture export recovery separate from application and hosted acceptance evidence.

    Dependencies: Tasks 9, 10, 19, 25, 26, 28, 33, and 36. Suggested owner: platform and security reviewers.

    Done when zero accepted records are lost or duplicated, all verification records restore, and one migration head matches readiness. Preserve protected histories during rollback. No open critical or high security finding may remain.

    Evidence: [current implementation/delivery](docs/learnlens/task-36-37-39-validation.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

38. **[Partial] Measure load, provider cost, and runtime configuration changes.**

    **Progress:** Runtime `2b9c951` includes delivered budget/runtime and scoped performance fixes, including omission of unused continuation view hydration. Its clean 50-user campaign still failed: 31/50 awaiting human assessment, six continuation timeouts and 13 request timeouts. Ordinary API p95 5.6019665 seconds and formative feedback p95 27.481452 seconds miss their targets. Contention and continuation reliability remain active engineering work.

    **Verified:** Journey errors: 38%; HTTP errors: 18/5,454. Ordinary p95 5.6019665 seconds (297 observations, one censored), progress 1.9939775 seconds (80), formative feedback 27.481452 seconds (31), assessed response 49.523947 seconds (70). Stage timings are conditional on reaching those stages. No human-confirmed completion or actual external billing is claimed. Corrected private DELETE/WAL comparison found no overall WAL benefit; runtime journal configuration is unchanged. Later benchmark-only export recovery has 32 focused passing checks, not another load result.

    **Next action:** Engineering: reduce write-transaction duration and continuation queue delay using representative traces; the completed journal/admission experiments did not establish a safe remedy. Preserve durable claims, deadlines and independent sessions. Validate a demonstrated runtime repair with affected checks and a clean campaign. API timings do not measure browser rendering; approved-host comparable 5–100 scaling and billed human-confirmed complete-loop cost remain separate.

    Dependencies: Tasks 25, 35, 36, and 37; Task 8, D-12. Suggested owner: platform and operations.

    Done when average external LLM cost is at most AUD 0.10 per loop. Save usage, prices, currency assumptions, and configuration. Verify authorised provider, model, timeout, retry, and budget changes without source edits. Let measurements decide whether SQLite or worker concurrency needs changing.

    Evidence: [current implementation/delivery](docs/learnlens/task-38-load-cost-harness.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

39. **[Partial] Complete browser, accessibility, and first-time usability checks.**

    **Progress:** Current `2b9c951` frontend CI succeeded: 396 unit tests in 97 files, 124 ordinary browser first-attempt passes, three complete-loop first-attempt passes plus WebKit retry #1, and four misconception first-attempt passes. Duplicate TaskView sibling keys are fixed; five mounted checks and one focused WebKit keyboard pass verify unique panels/deadlines and task-change reset, with permanent save/reload browser guards.

    **Verified:** Current failure-context artifact `10289832868` retains the complete-loop learner-preferences access-control console error after the next-activity assertion. Separately, a private held-reload probe reproduced catalog/tutor WebKit transport-console messages with zero window error/unhandled-rejection events; actual throw, rejected-Promise and noncancel network-failure controls validated observation. This supports classification for that probe, not every CI occurrence. No error filters, retries or timeouts were relaxed. Native Safari, named screen-reader/manual WCAG and first-time usability acceptance remain absent.

    **Next action:** Engineering/reliability: diagnose the exact retained complete-loop failure without blanket transport/CORS filtering or timeout increases. Keep the successful duplicate-panel fix and positive runtime-error controls. Human input remains native Safari, named screen-reader/zoom/contrast observations and first-time educator/learner trials.

    Dependencies: Tasks 24-31 and 36; Task 8, D-12. Suggested owner: accessibility reviewers and product testing.

    Done when key paths meet WCAG 2.2 AA with no critical access fault. Record usability averaging at least 7/10. Five first-time educator setup trials must finish within 20 minutes. At least 80% of first-time students must complete the required journey unaided within 15 minutes.

    Evidence: [current implementation/delivery](docs/learnlens/task-39-manual-validation-kit.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

40. **[Partial] Demonstrate the approved reuse target.**

    **Progress:** Conditional-programming factories and integrated tests exercise feedback, durable worker continuation, scoped model snapshots, accepted adaptation choices and assessed transfer. That synthetic reuse coverage passed within backend CI on 5a57b66. Approved module/source content, independently observed execution and measured contributor effort remain outstanding.

    **Verified:** test_conditional_programming.py contains the complete synthetic evidence/model/adaptation/assessment path. Passing CI establishes software compatibility, not independent human effort or approved-domain validity.

    **Next action:** Human/external input: supply the approved second-domain module/sources and an independent verifier; execute and record full reuse and per-contributor effort against 16 developer-hours. Synthetic model/adaptation/assessment reuse already has integrated test coverage.

    Dependencies: Tasks 25 and 36; Task 8, D-11. Suggested owner: a developer outside the main feature implementation.

    Done when the approved 16 developer-hour target is met and independently verified. Verify that core evidence, model, adaptation, and assessment engines remain reusable.

    Evidence: [current implementation/delivery](docs/learnlens/task-40-conditional-programming.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

41. **[Remaining] Complete hosted validation and the release handoff.**

    **Progress:** Deployment/readiness configuration, shared API/worker settings and backup/restore/rollback tooling are delivered. Hosted acceptance and release handoff have not been performed; local synthetic application tests do not certify deployment packaging, TLS, operational supervision or 99.5% calendar-month availability.

    **Next action:** External/release input: execute the approved deployment package and hosted operational drills, verify TLS/storage/worker supervision, collect availability evidence and obtain a named release handoff after dependent gates pass.

    Dependencies: Tasks 1-40, with all applicable decisions and evidence resolved. Suggested owner: release owner, operations, and product owner.

    Done when the tested commit, deployment settings, evidence, owners, open limits, and rollback steps form a reviewed handoff. Update architecture, setup, assessor, learner review, privacy, export, and operations guides. Pilot activation follows the recorded release decision.

    Evidence: [current implementation/delivery](src-main/docs/deployment.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).
