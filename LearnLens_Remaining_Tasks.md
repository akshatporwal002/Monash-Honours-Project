# LearnLens task progress and remaining work

The task-view admission candidate `8c8b5d5` was rejected after its clean
50-user campaign worsened to 35/50 awaiting human assessment, 14 request
timeouts and one interrupted simulation. Its helper, integration, tests and draft
provenance were reverted to `197ffde` (application code equivalent to `67b6c92`).
All failed measurements remain recorded; Task 38 still needs engineering.

Rollback `4c85519` restores application code, tests and validation tooling exactly
to `197ffde`. The already-running [CI run 34689653226](https://github.com/akshatporwal002/Monash-Honours-Project/actions/runs/34689653226)
subsequently passed on rejected candidate `8c8b5d5`: **2,141 backend tests,
400 frontend tests and 144 browser checks**, plus dependency and secret gates.
That source-specific result confirms the corrected feedback fixtures but is
neither a capacity pass nor a new full-suite run of the restored source.

Updated: **12 September 2026**. Current pushed application source is `67b6c92`. [CI run 34687133232](https://github.com/akshatporwal002/Monash-Honours-Project/actions/runs/34687133232) passed frontend and dependency jobs. Backend recorded **2,122 passes and two stale test-call failures**, with **90.22% service coverage**. Both calls are corrected and their five-case file passes locally; OpenAPI and frontend contract checks also pass. Secret scanning found one documentation false positive, now narrowly corrected and verified locally. The hosted run remains failed; these follow-up checks are separate evidence.

**30 of 41 numbered implementations are delivered; 11 tasks still need software or acceptance work.** The count is **30 completed, 10 partial and one remaining**. Read each task's progress, next action, acceptance condition and evidence before starting work.

| Work state | Tasks | Meaning |
| --- | --- | --- |
| Completed numbered implementation | 1–7, 9–27, 29–31, 36 | Functionality is delivered. Maintain it; load, human and release acceptance stay in dependent tasks. |
| Active software/performance work | 38 | The retained runtime reached 45/50 awaiting human assessment but still missed ordinary and formative latency targets and had five early request timeouts. The subsequent candidate worsened to 35/50 and was reverted. |
| Human/external acceptance primarily outstanding | 8, 28, 32, 33, 34, 35, 37, 39, 40, 41 | Actual approvals, people, content or an approved environment remain due. Task 39's identified browser repair now passes combined CI; native browser, assistive-technology and first-time-user acceptance remain. Task 33 may need further record-class disposal work after the data plan is approved. |

Task 30's reminder rules and candidate-scan repair and Task 22's continuation functionality are delivered. Their load behavior remains Task 38 work. Completed implementation does not certify performance or release acceptance.

## Source and verification snapshot

`67b6c92` includes atomic checkpoint/transfer saves, durable continuation handoff and progress writes, joined model hydration, batched first-feedback-view records and scoped start validation. It also includes preference cancellation on document exit, retained browser diagnostics, installed-package verification and updates to four existing teammate guides. No runtime journal or private write-admission experiment was shipped.

| Evidence | Source and result | Limit |
| --- | --- | --- |
| Backend CI | `67b6c92`: **2,122 passed, two failed, one warning**, 1,494.41 seconds, **90.22% service coverage**. Both failures passed an obsolete ninth argument to `get_feedback`. The corrected five-case fixture passes in 1.32 seconds; scoped lint/format and both contract checks pass. | All 2,124 backend case identities are accounted for across CI and the focused correction; this is not a claim of a new full-suite pass. |
| Frontend CI | `67b6c92`: **400 unit tests in 98 files**; **136 ordinary browser checks, four complete learning loops and four misconception journeys**, all on their first attempt. Lint, type checking and production build pass. | Native Safari, manual assistive technology and actual first-time-user trials remain separate. |
| Security/dependencies | Dependency job passed. Secret job found one ordinary-prose match; only that exact historical fingerprint was excluded, and current prose was reworded. The pinned local gate passed across 305 text commits / 404 reachable commits, with zero history findings and the unchanged expected positive control. | The failed hosted scan is retained as failed. [Scanner receipt](docs/learnlens/secret-scan-gate-2026-09-10.md) records the exact finding and follow-up scope. |
| Installed release package | CI passed a noneditable production-only installation: **325 application modules**, both console entries and **60 migration revisions**, head `20260911_0055`. | This verifies packaged imports and copied sidecars, not a container or approved-host deployment. |
| Retained runtime 50-user measurement | Clean `67b6c92`: **45/50 awaiting human**, five request timeouts and zero continuation timeouts; **ordinary p95 4.4337269 s**, progress **1.5165027 s**, formative feedback **35.7989416 s**, assessed response **74.6502288 s**. | **Failed:** 10% journey errors and 5/7,360 HTTP errors. Ordinary: 331 observations, two censored; progress: 93; formative: 45; assessed: 90. Stage timings are conditional; no human-confirmed completion or actual external billing. |

The previous clean `2b9c951` campaign reached 31/50 awaiting human with six continuation timeouts and 13 request timeouts; its successful full CI remains historical. The retained runtime improves on that baseline but does not establish a latency pass; the subsequent rejected candidate regressed. All eleven dated campaigns, including warmup failures, remain in the [capacity evidence](docs/learnlens/task-38-local-capacity-20260911.md). [Integration evidence](docs/learnlens/integration-verification-2026-09-11.md) retains exact source scopes. Overlapping focused counts are not summed into another suite.

Migration/readiness head: `20260911_0055`. The [requirement matrix](docs/learnlens/implementation-gap-matrix.md) covers **143 requirements: 97 implemented, 33 partial, 13 unverified**. Requirements and numbered tasks use different denominators.

## Next software work

**Task 38:** the five remaining measurement timeouts occur during initial task read, start, help or simulation before a submission or workflow exists. A narrow 50-actor startup diagnostic identified waiting for the first learning-event write as the dominant task-read cost. Preserve durable events, authorization, request deadlines and transaction ownership while reducing this contention. Validate any actual runtime repair with affected checks and a clean representative campaign.

Private query-scope changes reduced reads but did not improve the overall matched startup workload, so they were rejected. A private admission probe improved task-read waiting but exposed global SQL/async/cleanup hazards; it was not a production repair or a full-capacity result. The subsequent task-view-only admission candidate passed 62 focused checks and two reviews, but its clean full campaign worsened from 45/50 to 35/50 awaiting human; the candidate was reverted. Its 14 request timeouts and one interrupted simulation remain recorded. Earlier DELETE/WAL and mixed-workload admission results remain historical, and runtime journal settings are unchanged.

Task 39's identified document-exit preference race is repaired; the current complete Linux/browser CI passes all 144 browser checks first attempt with strict error assertions intact. Continue its actual native-browser, screen-reader, zoom/contrast and first-time-user acceptance when the required people and devices are available.

Actual provider spending, study activation and human approvals require their real approved inputs. Installed-package verification is complete; execution in the approved deployment environment remains due. Task 33's approved data plan may reveal additional disposal work; protected learning/assessment history must remain intact.

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

    **Progress:** Offline tooling retains 108 DRAFT cases and blank review forms, zero approved cases and zero included system-output/rating pairs. Live moderation, signed evaluator release/import and ten-dimension human review are implemented. Current source fingerprints use the refreshed 127-entry draft manifest; historical numerical receipts and their paired manifests remain unchanged. Quality stays UNVERIFIED and advisory AI release PENDING.

    **Verified:** Current 127-entry draft manifest digest `f88aa8436570434cbcf1464f9a3b0c1e37714d34ec21d4c339ecf335ad7601b3`; 44 validation-tool checks pass. The historical 12-scenario numerical receipt remains bound to `3604cb3d6e8f2f10a479b2799baae9e2f22f047a73867133ac4f0daa887d921c`; its matching distributions supply no expert approval or new-source numerical execution.

    **Next action:** Human/expert input: approve at least 100 cases and source bindings, record actual outputs and independent ratings, calculate agreement/fairness/error measures, and sign separate content and AI-assessment release decisions. Maintain source fingerprints; the current draft digest does not replace historical numerical or expert evidence. Current configured checks and their follow-up corrections are recorded under Task 36.

    Dependencies: Tasks 11, 15, 16, 23, and 25; Task 8, D-07 and D-12. Suggested owner: assessors and evaluation reviewers.

    Done when the approved evaluator gate passes. Required content targets include at least 80% factual accuracy, at most 5% hallucinations, and feedback review averaging 4/5. Judge rejection must reach 80%, with false rejection at most 20%. Establish a trained-human agreement baseline and report criterion agreement by task type with uncertainty. Test answer length, writing style, and approved access modes. Feedback and judge thresholds cannot clear the separate AI assessment release gate.

    Evidence: [current implementation/delivery](docs/learnlens/task-35-validation-tooling.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

36. **[Completed] Refresh traceability and run the complete automated checks.**

    **Progress:** All 143 requirements remain mapped: 97 implemented, 33 partial and 13 unverified. Traceability and automated-check implementation remain complete. Current `67b6c92` CI recorded 2,122 backend passes and two obsolete direct-route test calls, with 90.22% service coverage. The corrected five-case file passes locally. Current frontend and dependency CI passed; the exact documentation scanner false positive is corrected locally. The hosted run is not relabelled as successful.

    **Verified:** Frontend: 400 unit tests/98 files and all 144 browser checks first attempt, with lint/type/build passing. Backend: 2,122 CI passes plus the two repaired cases passing within a five-case focused run; scoped lint/format and OpenAPI/TypeScript drift checks pass. Production-only installed-package verification passed for 325 modules, both console entries and 60 migrations. The pinned local history scan passes with the unchanged positive control; see the source snapshot and integration receipt for separate scopes.

    **Next action:** Maintain traceability and verify affected checks for further repairs. Retain the failed hosted run and its bounded correction receipts. A new runtime change requires new combined CI; documentation-only reconciliation does not justify repeating unchanged application suites. Task 38 remains active engineering; manual and hosted acceptance remain separate.

    Dependencies: Tasks 1-34 for the final combined run. Run targeted checks with each earlier change. Suggested owner: integration and independent reviewers.

    Done when evidence and independent review apply to the final commit. Keep manual and external checks separate. New dependency audits are required; the previously updated packages are not assumed to remain vulnerable or permanently safe.

    Evidence: [current implementation/delivery](docs/learnlens/task-36-requirements-reconciliation.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

37. **[Partial] Prove security, migration safety, restart recovery, and restore completeness.**

    **Progress:** Current-head upgrade/readiness, all-table backup/restore comparison, source-byte preservation and protected-history checks are implemented at head 0055. These cases passed in current `67b6c92` backend CI; that job failed only two unrelated stale feedback-route fixture calls. Production-only installed-package verification also passed. Approved-host/provider security and operational drills remain unverified.

    **Verified:** test_task37_integrated_recovery.py compares every table and source bytes after restore and checks readiness/protected histories. The post-`2b9c951` benchmark-only export repair uses normal SQLite recovery on the owned stopped synthetic fixture, cannot create a missing source, and explicitly closes both connections. Its hot-journal/committed-data regression is included in 32 focused passing checks; independent review found no blockers. This is distinct from a hosted recovery drill.

    **Next action:** Perform approved-host/provider security, restart, backup/restore and rollback drills with actual approved inputs. Keep benchmark fixture export recovery separate from application and hosted acceptance evidence.

    Dependencies: Tasks 9, 10, 19, 25, 26, 28, 33, and 36. Suggested owner: platform and security reviewers.

    Done when zero accepted records are lost or duplicated, all verification records restore, and one migration head matches readiness. Preserve protected histories during rollback. No open critical or high security finding may remain.

    Evidence: [current implementation/delivery](docs/learnlens/task-36-37-39-validation.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

38. **[Partial] Measure load, provider cost, and runtime configuration changes.**

    **Progress:** Runtime `67b6c92` includes atomic checkpoint/transfer saves, continuation/outbox handoff, fenced progress writes, joined model hydration, batched feedback-view records and scoped start validation. Its clean 50-user campaign reached 45/50 awaiting human assessment, with five early request timeouts and zero continuation timeouts. Ordinary API p95 4.4337269 seconds and formative feedback p95 35.7989416 seconds still miss their targets. Contention remains active engineering work.

    **Verified:** Measurement journey errors: 10%; HTTP errors: 5/7,360. Ordinary p95 4.4337269 seconds (331 observations, two censored), progress 1.5165027 seconds (93), formative feedback 35.7989416 seconds (45), assessed response 74.6502288 seconds (90). Stage timings are conditional. Warmup retained 21 awaiting human, 18 continuation timeouts, four feedback timeouts, six request timeouts and one interrupted simulation. The database export and process cleanup succeeded. No human-confirmed completion or actual external billing is claimed; all prior campaigns remain preserved.

    **Next action:** Engineering: reduce the measured first-write contention in early task/start/help/simulation paths while preserving required telemetry and validation. Private extra query scopes did not improve total time and were rejected; the private gate has not been promoted to runtime. Keep deadlines unchanged and validate a justified implementation with focused correctness checks and a clean campaign. Approved-host comparable 5–100 scaling, browser rendering and billed human-confirmed loop cost remain separate.

    Dependencies: Tasks 25, 35, 36, and 37; Task 8, D-12. Suggested owner: platform and operations.

    Done when average external LLM cost is at most AUD 0.10 per loop. Save usage, prices, currency assumptions, and configuration. Verify authorised provider, model, timeout, retry, and budget changes without source edits. Let measurements decide whether SQLite or worker concurrency needs changing.

    Evidence: [current implementation/delivery](docs/learnlens/task-38-load-cost-harness.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

39. **[Partial] Complete browser, accessibility, and first-time usability checks.**

    **Progress:** The identified learner-preference document-exit race is repaired in `67b6c92`: abort before a queued fetch starts, and retry only interrupted initial loads when a cached page returns. Loaded unsaved choices are preserved. Current frontend CI passes 400 unit tests/98 files and all 144 browser checks on the first attempt, including all four complete learning loops. Earlier duplicate-panel repairs and permanent guards remain.

    **Verified:** Nine affected unit checks and seven distinct focused WebKit cases passed locally, with controlled error-observer cases. Current CI: 136 ordinary browser checks, four complete learning loops and four misconception journeys all first attempt. Passive bounded diagnostics retain context; runtime-error, accessibility, retry and timeout assertions remain unchanged. Local controlled reproduction does not rewrite the old artifact's unknown timing. Native Safari, named screen-reader/manual WCAG and first-time usability acceptance remain absent.

    **Next action:** Human/device acceptance: record native Safari, named screen-reader, zoom/contrast observations and actual first-time educator/learner trials. Preserve the current passing automated coverage and investigate any new concrete failure from its retained context; no unresolved reproduced browser code defect is claimed at this snapshot.

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

    **Progress:** Deployment/readiness configuration, shared API/worker settings and backup/restore/rollback tooling are delivered. CI verifies a noneditable production-only installed package with all 325 application modules and 60 migrations. Hosted acceptance and release handoff remain unperformed; packaged imports do not certify a container, TLS, operational supervision or 99.5% calendar-month availability.

    **Next action:** External/release input: execute the approved deployment package and hosted operational drills, verify TLS/storage/worker supervision, collect availability evidence and obtain a named release handoff after dependent gates pass.

    Dependencies: Tasks 1-40, with all applicable decisions and evidence resolved. Suggested owner: release owner, operations, and product owner.

    Done when the tested commit, deployment settings, evidence, owners, open limits, and rollback steps form a reviewed handoff. Update architecture, setup, assessor, learner review, privacy, export, and operations guides. Pilot activation follows the recorded release decision.

    Evidence: [current implementation/delivery](src-main/docs/deployment.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).
