# LearnLens remaining tasks

Current integration status: **10 September 2026**, inspected at `4fe8bb8184359e1fae606bc8cdd559fe54bc4760` on `codex/integrate-parallel-20260910`.
**Combined final validation: PASS for the current delivered scope.** See the coordinator receipt below and the remaining implementation/evidence gaps.

Coordinator final receipt: The corrected delivery at `4fe8bb8184359e1fae606bc8cdd559fe54bc4760` passed 1,475 backend tests with 88.73% service coverage (80% minimum), 306 frontend tests across 84 files, and 132 configured browser checks at `ece4bedd41c36c7c37e89a10ce20fcd96a329f0f`. There were no failed, skipped or flaky cases in these final receipts. Root checks, lint/build, migration and contract checks, dependency audits and the full-history secret gate also pass. The coordinator report records exact commands, source trees, original failures and corrected runs. This verifies the delivered code; it does not close manual, expert, institutional or hosted-release requirements, or include unmerged next-batch branches. A separately reproduced assessor dialog-return focus race remains open in this source and is assigned to the next integration.

| Status | Count | Tasks |
| --- | --- | --- |
| Completed implementation | 29 | 1–7, 9–27, 29–31 |
| Partial: tooling, activation, integration or evidence remains | 10 | 8, 28, 32, 33, 35, 36, 37, 38, 39, 40 |
| Remaining | 2 | 34, 41 |

“Completed implementation” is the delivered numbered task scope; it does not mean all related requirement clauses or release gates have passed. The [current requirement matrix](docs/learnlens/implementation-gap-matrix.md) is authoritative for all 143 FR/PD/BP/NFR/AC/AT rows, with current gaps and acceptance checks. The [baseline Task 36 report](docs/learnlens/task-36-requirements-reconciliation.md) and [historical main audit](docs/learnlens/main-audit-2026-09-10.md) remain immutable evidence at `27a397a`; their former branch-only or missing-control statements do not describe this later integrated tree. Older detailed delivery records retain their original revisions and failures/reruns.

Settled [Task 8 selections](docs/learnlens/task-08-approved-selections.md) remain controlling: PASS/INCOMPLETE and human confirmation, hidden provisional verdicts, unrestricted approved conceptual hints during supported work, separate unaided transfer, protected histories, no research participation penalty and the 16 developer-hour reuse target. Missing institutional/expert/content/host approvals must be supplied as actual records, never inferred from fixtures.

## Integrated deliveries and final verification

The eight original deliveries and subsequent readiness, typed-practice, validation-provenance and circuit fixes are recorded in the [matrix evidence register](docs/learnlens/implementation-gap-matrix.md#integrated-evidence-register). Runtime readiness and the migration graph both use `20260910_0045`. The earlier d305 readiness and keyboard defects are dated findings, resolved in this inspected integration.

- **Circuit:** keyboard H/X target selection, explicit removal names and live/saved CX control/target text are integrated. Nine final focused cases passed according to the delivery record. FR14's bounded implementation is delivered; NFR4/AC17/AT24 still need actual manual accessibility evidence.
- **Typed practice:** purpose separation and complete bounded generator/judge input are integrated at fa0c6ee. The corrected focused run passed 80 cases, including actual model-request assertions, 20,000-character bounds, digest, approval, transfer and cached-release restrictions. No external model was called by those regressions.
- **Task 35:** provenance refreshes 0eaf467 and 0af4873 include the changed practice-input dependencies. Latest reported tooling results are 44 tests and 12/12 numerical checks, with 108 DRAFT cases, zero approved, quality UNVERIFIED and AI release PENDING.
- **Task 38:** final owner receipt `471f185a089d660f439ab9e21adf0113d01fdb96` verifies one fresh synthetic learner against a real local API, 35 successful HTTP calls, three feedback workflows and both actual local provider inputs; 54 focused checks passed. The owned benchmark changes are integrated as be3e92a, 9239dc1 and 0bbf95e. Six local usage rows have null actual AUD cost and zero human-confirmed loops. It is compatibility evidence, not a representative load/cost campaign or recovery proof. See the [dated receipt summary](docs/learnlens/implementation-gap-matrix.md#post-baseline-coordinator-receipts).
- **Final frontend/source receipt:** 306 frontend tests across 84 files passed with zero failed/skipped; lint/build pass and frontend trees at e93842f/0bbf95e match. API/TypeScript contract drift and Ruff (539 files) pass at 0bbf95e per the coordinator.
- **Final combined evidence:** **PASS for the current delivered scope.** Exact source identities and results are in the coordinator receipt above; the known focus-return race and external acceptance gates remain open.
- **Additional requirement gaps:** recoverable course revisions, upload malware policy, broader generated/accessible task types, integrity review cues, moderation/AI revalidation and fuller model/feedback-effectiveness evidence remain in the matrix.

## Numbered task ledger

Dependencies and acceptance conditions are retained below; current descriptions replace obsolete present-tense findings. Re-run relevant checks after integration without weakening assertions, coverage gates or safeguards.

1. **[Completed] Prevent unknown evidence from satisfying a negated pass rule.**

    Pass rules preserve unknown, missing and conflicting evidence through negation and nested Boolean expressions; they cannot fabricate a mandatory criterion pass.

    Dependencies: none. Suggested owner: assessment backend.

    Done when regression tests cover those cases, including nested rules, while retaining explicit review reasons and the mandatory-criterion checks.

    Evidence: [current implementation/delivery](docs/learnlens/negated-pass-rule-repair.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

2. **[Completed] Require real evaluator rules before approving an assessment.**

    Typed evaluator settings are validated during authoring, approval and runtime. Empty or unsupported automatic rules are rejected; unsupported criteria route to human assessment.

    Dependencies: none. Suggested owner: assessment backend and assessor UI.

    Done when empty, unknown, or contradictory settings block approval and fail safely during evaluation. Test the actual UI-to-API authoring path.

    Evidence: [current implementation/delivery](docs/learnlens/evaluator-settings-repair.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

3. **[Completed] Repair task and dashboard reads after assessed submissions.**

    Assessed task reloads, histories and dashboards preserve absent marks and separate activity from formal results. Mixed histories no longer require invented numeric scores.

    Dependencies: none. Suggested owner: LMS backend and frontend contracts.

    Done when task reload, learner dashboard, educator dashboards, recommendations, and history work after formal submissions. Include mixed legacy and assessed records. Do not convert missing scores to zero.

    Evidence: [current implementation/delivery](docs/learnlens/assessed-read-repair.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

4. **[Completed] Close the direct learner evaluation and visibility bypass.**

    Learner evaluation access, duplicate requests and provisional-result visibility are restricted. D-01 keeps pending verdicts hidden until authorized confirmation.

    Dependencies: none for the immediate restriction; Task 8, decision D-01, for approved learner visibility. Suggested owner: assessment API.

    Done when duplicate requests create no duplicate decisions and learners see only policy-approved information.

    Evidence: [current implementation/delivery](docs/learnlens/learner-evaluation-bypass-restriction.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

5. **[Completed] Restrict unapproved research processing and export access now.**

    Research access is separate from analytics and teaching permissions. Integrated Task 33 adds study/field/consent controls, while the production release gate stays closed.

    Dependencies: none for the immediate restriction. Governed activation follows Task 33. Suggested owner: access controls and research backend.

    Done when ordinary analytics access cannot authorise research exports. Missing approval, revoked permission, and disabled participation must prevent research processing without restricting course access or changing results.

    Evidence: [current implementation/delivery](docs/learnlens/research-access-restriction.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

6. **[Completed] Give every browser test its own assessment records.**

    Assessor browser actions use independent synthetic assessment fixtures. Confirm, override, withhold and return scenarios no longer depend on another test's state.

    Dependencies: none. Suggested owner: test infrastructure.

    Done when each action passes alone, in the complete browser run, and on retry without relying on another test. This audit did not reproduce a current browser launch failure.

    Evidence: [current implementation/delivery](docs/learnlens/browser-assessment-isolation.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

7. **[Completed] Start the durable worker and check actual readiness.**

    The launcher starts API/frontend/recovery worker, applies migrations and waits for readiness. Recovery is implemented and readiness now matches migration head 0045 through a38e6af. The separate single-learner benchmark reports all readiness checks ready; current automated recovery checks pass; the separate integrated operational drill and hosted release remain Task 37/41 work.

    Dependencies: none for local template mode. Suggested owner: platform.

    Done when an accepted submission finishes after a worker restart without another submission request. Local mode and research settings must match the chosen adapters. Task 22 supplies the complete adaptive worker path.

    Evidence: [current implementation/delivery](docs/learnlens/durable-worker-startup.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

8. **[Partial] Record the decisions needed to activate each feature.**

    Policy selections are settled in D-01–D-12. Concrete course/source/form/staff/study/retention/environment and release records remain due; fixture approvals and user policy choices do not supply institutional or expert approval.

    Dependencies: none. Suggested owners: product owner, assessors, privacy, research, and operations.

    Done when each dependent feature has the specific approval it needs. Unrelated implementation can continue while a decision remains pending. Test fixture settings do not approve live policy.

    Evidence: [current implementation/delivery](docs/learnlens/task-08-approved-selections.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

9. **[Completed] Preserve the exact approved sources used by each output.**

    Versioned approved material and exact source passages remain recoverable after reprocessing, replacement and retirement; source scope and review bindings are retained.

    Dependencies: none for versioned storage; Task 8, D-08, for retention and destructive deletion rules. Suggested owner: retrieval and data.

    Done when an authorised reviewer can recover the exact cited passage after a source changes. Keep course scope and page, slide, or heading locations intact.

    Evidence: [current implementation/delivery](docs/learnlens/task-09-source-history.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

10. **[Completed] Recover interrupted material processing.**

    Interrupted extraction/indexing can resume without duplicate or partially published source revisions. Original resources and processing state are preserved.

    Dependencies: Task 9. Suggested owner: retrieval and worker.

    Done when a saved upload finishes or reports a recoverable failure after interruption. Concurrent workers must not publish duplicate or partial source revisions. Retain the original upload and useful processing status.

    Evidence: [current implementation/delivery](docs/learnlens/task-10-material-processing-recovery.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

11. **[Completed] Store trustworthy simulation evidence and enforce execution limits.**

    Bounded Qiskit/Aer simulation retains settings, counts, exact probabilities, bit order and equivalent text evidence, with controlled errors. Keyboard target selection and explicit live/saved CX text are integrated; expert validity and native/manual accessibility remain separate acceptance work.

    Dependencies: none. Suggested owner: quantum services.

    Done when runs are bounded and reproducible from saved settings. Use exact probabilities or sampling tolerances where justified. Gate presence or distribution agreement must not stand in for every state property or conceptual claim.

    Evidence: [current implementation/delivery](docs/learnlens/task-11-simulation-evidence.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

12. **[Completed] Finish educator approval, assessor setup, and publication controls.**

    Explicit educator review, current source approval, assessor eligibility and publication validation block unreviewed or invalid assessed tasks. A real course still needs its named content approvals.

    Dependencies: Tasks 2 and 9; Task 8, D-02, D-04, and D-05. Circuit publication also needs Task 11. Suggested owner: course and assessment teams.

    Done when an authorised assessor can publish a valid form without test overrides. Unreviewed generated tasks and unsupported circuits must remain unavailable to learners.

    Evidence: [current implementation/delivery](docs/learnlens/task-12-publication-controls.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

13. **[Completed] Freeze assessment versions when the learner starts work.**

    Starting assessed work freezes the approved task/outcome/criteria/rule and declared conditions. Later changes preserve the original bundle or return a conflict; completed practice is not rebound to assessment.

    Dependencies: Tasks 8 and 12. Suggested owner: assessment and task workspace.

    Done when a rule change during an open draft preserves the original approved bundle or returns an explicit conflict. A later version must never silently replace the declared standard.

    Evidence: [current implementation/delivery](docs/learnlens/task-13-start-freeze.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

14. **[Completed] Complete the learning episode inside the task workspace.**

    Typed prediction, reasoning, code/circuit, revision, reflection and unaided transfer survive saved drafts, submission and reload. Two-qubit keyboard placement and explicit live/saved circuit semantics are integrated; full manual equivalence is not yet established. Typed practice now retains complete bounded evidence at both feedback model inputs with digest/approval/transfer guards.

    Dependencies: Tasks 11 and 13; Task 8, D-04 and D-05, for approved assessed stages. Suggested owner: task engine and frontend.

    Done when each supported response survives draft, submit, reload, revision, and controlled simulation failure. Every type needs accessible controls, evidence extraction, evaluator support, and export representation.

    Evidence: [current implementation/delivery](docs/learnlens/task-14-learning-episode.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

15. **[Completed] Make unsupported assessment criteria reachable by a human assessor.**

    Eligible course assessors inspect frozen evidence and evaluate HUMAN criteria, then confirm, override, withhold, return or void with retained reasons/history. Operational AI criterion suggestions remain disabled pending the separate D-07 gate.

    Dependencies: Tasks 1, 2, 11, 12, and 13. Suggested owner: assessment backend and review UI.

    Done when an assessor can inspect evidence, record criterion decisions and reasons, apply the pass rule, and finalise the result. Keep operational AI assessment suggestions disabled until Task 35 passes its separate approved gate. After that gate, suggestions remain advisory and humans confirm results.

    Evidence: [current implementation/delivery](docs/learnlens/task-15-human-assessment.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

16. **[Completed] Deliver grounded assessed feedback under the approved help policy.**

    Grounded feedback enforces current source/help/release conditions, records quality decisions, allows one regeneration and preserves a fixed safe fallback. Feedback approval cannot confirm a formal result.

    Dependencies: Tasks 9, 11, 12, and 15; Task 8, D-05. Suggested owner: feedback and retrieval.

    Done when approved feedback states missing evidence without exceeding allowed help. Preserve one regeneration, fixed fallback, rejection reasons, and source/model/prompt/rule versions. Feedback approval must not confirm an assessment result.

    Evidence: [current implementation/delivery](docs/learnlens/task-16-grounded-feedback.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

17. **[Completed] Capture learning evidence through the live application.**

    Live interactions append ordered, scoped and replay-safe evidence linked to immutable response, task, source and support history.

    Dependencies: Tasks 9, 11, and 14. Suggested owner: evidence services.

    Done when a real learner journey creates an authorised, ordered evidence timeline. Replays and partial failures must preserve originals without duplicate accepted observations.

    Evidence: [current implementation/delivery](docs/learnlens/task-17-live-evidence.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

18. **[Completed] Update the shared learner model from real evidence.**

    Evidence produces versioned cumulative learner estimates with uncertainty, provenance and concurrency/replay controls. These rule-based estimates remain unvalidated teaching estimates, not mastery measurements or grades.

    Dependencies: Task 17. Suggested owner: learner services.

    Done when concurrent or repeated processing creates consistent snapshots. Produce validated snapshots for teaching services. Tasks 22 and 23 must demonstrate decisions that change because of an estimate. Rule-based uncertainty must remain labelled as an unvalidated estimate until tested.

    Evidence: [current implementation/delivery](docs/learnlens/task-18-shared-learner-model.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

19. **[Completed] Integrate learner corrections and expose scoped evidence and model views.**

    Learners annotate/challenge evidence and model information; scoped educator review and later model updates retain the original records and correction history.

    Dependencies: Tasks 17 and 18. Suggested owner: learner services and frontend.

    Done when learner corrections and scoped reviews preserve originals and are consumed by later snapshots without replacing history.

    Evidence: [current implementation/delivery](docs/learnlens/task-19-corrections.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

20. **[Completed] Add learner preferences and control over non-essential support.**

    Learner-owned preference revisions, access support and optional personalization controls persist. Opt-out, corrections, slower pace and help do not change frozen assessment standards; full equivalent-content breadth remains in the requirement matrix.

    Dependencies: Tasks 14 and 17; Task 8, D-05, for assessed conditions. Suggested owner: learner experience.

    Done when preferences and opt-out persist, support remains separate from access, and no choice changes formal results or essential access.

    Evidence: [current implementation/delivery](docs/learnlens/task-20-learner-preferences.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

21. **[Completed] Build the curriculum links and approved diagnostic paths.**

    Approved curriculum graphs link outcomes, sources, forms, prerequisites and exit guidance. Diagnostics record learning evidence and require eligible assessor confirmation before practice bypass; they cannot replace formal assessment.

    Dependencies: Tasks 12, 18, and 20. Suggested owner: learning pathway services.

    Done when approved graphs and diagnostics enforce scope, independent conditions and human-confirmed practice bypass without granting formal credit.

    Evidence: [current implementation/delivery](docs/learnlens/task-21-curriculum-diagnostics.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

22. **[Completed] Connect learner evidence to the next approved activity.**

    The shipped worker connects eligible checked feedback to one model update and approved next-activity suggestion. Accept/defer/replace, opt-out, stale approvals, educator overrides and recovery preserve reasons and history. Task 23 is already delivered.

    Dependencies: None; coordinator verifies the integrated release.

    Done when accepted evidence causes exactly one model update and approved suggestion; choices, override, restart and stale-approval behavior preserve the standard.

    Evidence: [current implementation/delivery](docs/learnlens/task-22-approved-activity-continuation.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

23. **[Completed] Add tutor dialogue and a controlled sequence of hints.**

    Persisted grounded tutor dialogue and reviewed conceptual hints survive reload, record help and stop instructional help during separate unaided transfer. D-05 has no instructional hint-count cap; answer-seeking redirects make no automatic misconduct finding.

    Dependencies: Tasks 16, 17, 18, and 20. Suggested owner: teaching services and task workspace.

    Done when conversation state survives reload, help follows assessed conditions, and outputs pass the feedback checks. Answer-seeking cues should redirect to reasoning without making an automatic misconduct finding.

    Evidence: [current implementation/delivery](docs/learnlens/task-23-24-tutor-and-results.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

24. **[Completed] Complete learner results, review requests, and appeal resolution.**

    Learner result views, review requests, assessor resolutions and notices preserve scope, reasons and decision history. Pending verdicts stay hidden; released results expose evidence and the next permitted action.

    Dependencies: Tasks 3, 4, 13, and 15; Task 8, D-01. Suggested owner: assessment experience.

    Done when requests and resolutions preserve scope, reasons, notices, and decision history. Learners must distinguish pending review from a confirmed result and reach every action without relying on colour.

    Evidence: [current implementation/delivery](docs/learnlens/task-23-24-tutor-and-results.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

25. **[Completed] Prove one complete quantum learning loop before expanding coverage.**

    The complete quantum learning loop is committed and merged: prediction, simulation, checked feedback, revision, reflection, transfer, model update, approved next activity and human confirmation use real persisted services with synthetic approvals. Worker-kill recovery reuses the committed model receipt. This milestone is no longer uncommitted or awaiting initial implementation.

    Dependencies: Tasks 10, 14, 16, 18, 22, 23, and 24, including their prerequisites. Suggested owner: integrated feature team.

    Done when one browser journey and backend integration test traverse the real services. Interrupt processing and prove recovery. A returned task ID or passing component test alone does not complete this milestone.

    Evidence: [current implementation/delivery](docs/learnlens/task-25-complete-learning-loop.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

26. **[Completed] Implement reassessment and outcome-level result selection.**

    Authorized reassessment uses a fresh equivalent form under the same standard, preserving earlier decisions. Published whole-decision outcome policies never average attempts or replace confirmed evidence with a pending attempt.

    Dependencies: Tasks 12, 13, 15, and 24; Task 8, D-06. Suggested owner: assessment.

    Done when every earlier decision remains readable, the same standard applies, and attempts are never averaged. Review, return, withholding, reassessment, and result replacement must have distinct effects.

    Evidence: [current implementation/delivery](src-main/backend/tests/test_reassessment.py); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

27. **[Completed] Complete the misconception check and recovery cycle.**

    The committed, merged misconception cycle supplies reviewed probes, teaching, revision, fresh evidence, uncertain/persisted/weakened/corrected states, educator corrections and preserved exit/recovery. Unresolved reviews already feed Task 28's assessor queue.

    Dependencies: Tasks 18, 19, 21, 22, and 23. Suggested owner: learner and teaching services.

    Done when evidence can leave a hypothesis uncertain, persisted, weakened, or corrected. A single wrong response must not create a certain label. Show why the next intervention was selected.

    Evidence: [current implementation/delivery](docs/learnlens/task-27-misconception-cycle.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

28. **[Partial] Add a human escalation and AI-output reporting workflow.**

    Separate assessor/technical queues, ownership, triage, acknowledgement/action/resolution/closure, notices and feedback sampling exist, including Task 27 misconception escalation. Remaining work is D-09 named operators/backups, staffed calendar/timezone, approved targets/sampling and activation records.

    Dependencies: Tasks 15, 16, 19, 23, and 27; Task 8, D-09. Suggested owner: educator experience and operations.

    Done when a report moves through acknowledgement, action, resolution, and closure with an audit trail. Accepted AI feedback must also be available for human sampling.

    Evidence: [current implementation/delivery](src-main/backend/app/services/escalation.py); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

29. **[Completed] Finish progress views and retire numeric learner-result semantics.**

    Scoped progress separates observations, support, uncertain estimates, adaptations and released binary results. Numeric learner marks were retired after immutable preservation. The integrated timezone repair normalizes known UTC response timestamps after SQLite reload without rewriting stored history; final combined regression is PASS for the current delivered scope.

    Dependencies: Tasks 3, 18, 19, 22, 24, 26, and 27. Final legacy removal also needs Task 8, D-10. Suggested owner: LMS, analytics, and frontend.

    Done when each important indicator links to scoped evidence, UTC instants survive reload/display, and protected legacy history stays intact under immediate D-10 retirement. Quantum probabilities and technical quality measures remain separate.

    Evidence: [current implementation/delivery](docs/learnlens/task-29-progress-timezones.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

30. **[Completed] Move reminder writes out of dashboard reads and finish reminder rules.**

    Reminder writes run outside dashboard reads. Course timezones/DST, extensions, access plans, opt-out, completion and rolling 24-hour delivery guards preserve prior records.

    Dependencies: Tasks 20, 22, and 24. Suggested owner: LMS and worker.

    Done when repeated dashboard reads make no state changes. Test simultaneous processing, time-zone boundaries, extensions, completed work, and disabled notifications.

    Evidence: [current implementation/delivery](src-main/docs/reminders-and-backups.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

31. **[Completed] Make gamification optional and remove learner rankings.**

    Optional private participation rewards recognize learning activity without public ranking, score-driven awards or assessment/access penalties. Replays and retries cannot duplicate awards.

    Dependencies: Tasks 20 and 29. Suggested owner: learner experience and LMS.

    Done when points never alter assessment, pathway standards, or essential access. Replays, retries, slower pace, breaks, and approved support must not create penalties or duplicate rewards.

    Evidence: [current implementation/delivery](src-main/backend/tests/test_gamification_preferences.py); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

32. **[Partial] Approve the learning-study protocol and data plan.**

    Protocol and data-plan drafts exist; Arv Surana is the user-named research lead. Protocol/ethics/privacy/retention decisions, preregistration, approved instruments and other named authorities remain outstanding.

    Dependencies: Task 8, especially D-03, D-07, and D-08. Planning can run alongside implementation. Suggested owner: research lead and governance.

    Done when an approved protocol covers unaided conceptual understanding, transfer, and any delayed-retention claims. Technical judge performance must not be presented as proof of learning improvement.

    Evidence: [current implementation/delivery](docs/learnlens/task-32-study-protocol.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

33. **[Partial] Enforce research permission, consent, and governed exports.**

    Technical governance controls are delivered and integrated: append-only study scopes/approvals, learner-self consent/refusal/withdrawal, eligibility, additional study/course/field grants, retention holds, governed processing and restricted technical-pair CSV/JSON v2 exports. Production research remains closed even with settings/fixture approvals. Actual approval/activation, retention disposal policy and release-environment validation remain due; full learning-study instruments belong to Task 34.

    Dependencies: Tasks 5, 9, 17, 18, 22, 24, and 32; Task 8, D-03 and D-08. Suggested owner: research backend and privacy.

    Done when unapproved processing and exports fail closed. Revoked access, withdrawal, and missing consent must be tested. Research condition and participation must not change teaching access, adaptation, or formal results.

    Evidence: [current implementation/delivery](docs/learnlens/task-33-governance-implementation.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

34. **[Remaining] Build and verify the learning-study instruments and records.**

    Complete approved learning-study instruments and records remain to be built: pre/in-process/post, unaided concept/transfer/retention, learner experience, educator/reviewer evidence, condition allocation where approved, attrition/deviations/missingness and governed full-stage exports. Task 33 supplies governance and technical-pair export only.

    Dependencies: Tasks 25, 29, 32, and 33. Suggested owner: research and analytics.

    Done when a complete approved sample exports in CSV or JSON with linked learning stages and no direct identity fields. Keep learning outcomes separate from feedback correctness and judge metrics. Label local template generation accurately.

    Evidence: [current implementation/delivery](docs/learnlens/task-32-data-plan.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

35. **[Partial] Validate quantum content, feedback, and assessment against expert judgements.**

    Offline review/import/metrics tooling and 108 DRAFT probes across 12 families are integrated. There are zero approved cases, expert ratings or recorded system outputs; 540 channel outputs are missing. The 12/12 numerical simulation checks establish fixture consistency only. Expert review, actual outputs, agreement/fairness/error thresholds, revalidation and signed D-07 release remain outstanding; no operational AI suggestion gate was activated.

    Dependencies: Tasks 11, 15, 16, 23, and 25; Task 8, D-07 and D-12. Suggested owner: assessors and evaluation reviewers.

    Done when the approved evaluator gate passes. Required content targets include at least 80% factual accuracy, at most 5% hallucinations, and feedback review averaging 4/5. Judge rejection must reach 80%, with false rejection at most 20%. Establish a trained-human agreement baseline and report criterion agreement by task type with uncertainty. Test answer length, writing style, and approved access modes. Feedback and judge thresholds cannot clear the separate AI assessment release gate.

    Evidence: [current implementation/delivery](docs/learnlens/task-35-validation-tooling.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

36. **[Partial] Refresh traceability and run the complete automated checks.**

    The immutable baseline and current matrix account for all 143 requirements. The current delivery's combined checks and independent reviews pass at the source revision recorded in the coordinator report. Task 36 remains partial because its Tasks 1–34 dependency set includes outstanding Task 34 work; repeat the combined checks and reconcile evidence after the next feature integration.

    Dependencies: Tasks 1-34 for the final combined run. Run targeted checks with each earlier change. Suggested owner: integration and independent reviewers.

    Done when evidence and independent review apply to the final commit. Keep manual and external checks separate. New dependency audits are required; the previously updated packages are not assumed to remain vulnerable or permanently safe.

    Evidence: [current implementation/delivery](docs/learnlens/task-36-requirements-reconciliation.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

37. **[Partial] Prove security, migration safety, restart recovery, and restore completeness.**

    Local migration, scope/security, durable worker, contention and verified database/source restore coverage exists; Task 33 adds governance-history/withdrawal/revocation restore fixtures and the secret-scan repair is integrated. Full-system/research/live-provider, hosted TLS and operational recovery/rollback drills remain incomplete.

    Dependencies: Tasks 9, 10, 19, 25, 26, 28, 33, and 36. Suggested owner: platform and security reviewers.

    Done when zero accepted records are lost or duplicated, all verification records restore, and one migration head matches readiness. Preserve protected histories during rollback. No open critical or high security finding may remain.

    Evidence: [current implementation/delivery](docs/learnlens/task-36-37-39-validation.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

38. **[Partial] Measure load, provider cost, and runtime configuration changes.**

    The opt-in harness has a final owner receipt for typed follow-on submission, actual local generator/judge inputs and bounded process cleanup: 54 focused checks and one fresh learner with 35 successful real HTTP calls. The owned delivery is integrated at 0bbf95e. Its six local usage rows have null actual AUD cost; API background execution handled the captured calls, so worker heartbeat alone is not recovery proof. Runtime timeout/retry/budget controls, full metering, provider approval and representative 50-user latency, 5–100 scaling and <=AUD 0.10 human-confirmed complete-loop cost remain open.

    Dependencies: Tasks 25, 35, 36, and 37; Task 8, D-12. Suggested owner: platform and operations.

    Done when average external LLM cost is at most AUD 0.10 per loop. Save usage, prices, currency assumptions, and configuration. Verify authorised provider, model, timeout, retry, and budget changes without source edits. Let measurements decide whether SQLite or worker concurrency needs changing.

    Evidence: [current implementation/delivery](docs/learnlens/task-38-load-cost-harness.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

39. **[Partial] Complete browser, accessibility, and first-time usability checks.**

    Automated browser/keyboard/reflow/axe coverage and a manual-validation kit with 27 blank role cases are integrated. Native Safari, actual screen-reader/native zoom/contrast checks and first-time usability trials remain undone. T39-C1 keyboard target-wire placement/removal and T39-C2 explicit live/saved CX control/target text are fixed with focused and browser receipts; actual human speech verification remains due. The inherited timestamp fix is now integrated.

    A separate controlled regression now reproduces lost dialog-return focus when a late evidence read finishes during assessor access checking. Cancel and Confirm both fail in that sequence. Its application correction and focused tests are assigned to the next integration; the current delivered source retains this known gap. The coordinator report distinguishes it from the earlier unconfirmed WebKit empty-reason timeout.

    Dependencies: Tasks 24-31 and 36; Task 8, D-12. Suggested owner: accessibility reviewers and product testing.

    Done when key paths meet WCAG 2.2 AA with no critical access fault. Record usability averaging at least 7/10. Five first-time educator setup trials must finish within 20 minutes. At least 80% of first-time students must complete the required journey unaided within 15 minutes.

    Evidence: [current implementation/delivery](docs/learnlens/task-39-manual-validation-kit.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

40. **[Partial] Demonstrate the approved reuse target.**

    Conditional-programming draft factories and 13 reuse fixtures are merged. Tasks 21/22/25 are delivered, so their old not-yet-integrated wording is obsolete. Exact approved sources/module, independently observed full evidence/model/adaptation/assessment reuse, named verifier and measured per-contributor effort against the selected 16 developer-hour target remain due.

    Dependencies: Tasks 25 and 36; Task 8, D-11. Suggested owner: a developer outside the main feature implementation.

    Done when the approved 16 developer-hour target is met and independently verified. Verify that core evidence, model, adaptation, and assessment engines remain reusable.

    Evidence: [current implementation/delivery](docs/learnlens/task-40-conditional-programming.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).

41. **[Remaining] Complete hosted validation and the release handoff.**

    Hosted deployment validation and reviewed release handoff remain outstanding. Package/configuration existence does not prove hosted TLS, persistent storage, worker supervision, backup/restore/rollback, named ownership or 99.5% calendar-month availability.

    Dependencies: Tasks 1-40, with all applicable decisions and evidence resolved. Suggested owner: release owner, operations, and product owner.

    Done when the tested commit, deployment settings, evidence, owners, open limits, and rollback steps form a reviewed handoff. Update architecture, setup, assessor, learner review, privacy, export, and operations guides. Pilot activation follows the recorded release decision.

    Evidence: [current implementation/delivery](src-main/docs/deployment.md); requirement-level gaps and named tests are in the [matrix](docs/learnlens/implementation-gap-matrix.md).
