# LearnLens remaining tasks

Reviewed on 6 September 2026 against local `main` at `d049eef`.

This is the recommended work order for completing the proposed LearnLens architecture and the wider repository requirements. Each numbered task states its dependencies, current gap, and completion check. Tasks with no shared dependency can run in parallel. A dependency means the earlier task must supply the needed working contract or behaviour before integration.

The review used [LearnLens_Architecture_and_Sources.md](LearnLens_Architecture_and_Sources.md), the [implementation requirements](docs/01-implementation-requirements.md), the [assessment specification](docs/02-pass-incomplete-bloom-assessment-spec.md), and the [work order](docs/03-codex-implementation-work-order.md). It also inspected backend services, mounted routes, frontend screens, migrations, tests, CI, launch scripts, and existing plans.

Existing foundations include authentication, course setup, material extraction, six task handlers, Qiskit simulation, feedback checking, and durable jobs. Versioned assessment definitions, immutable submitted attempts, provisional binary results, and audited assessor actions also exist. Evidence and learner-model services exist, but their application integration remains incomplete. These foundations should be extended.

This was a code and document audit, with two focused Python probes. Both probes reproduced the defects in Tasks 1 and 2. Full test suites, browser tests, live providers, GitHub CI, hosted environments, and human studies were not run. Other defect findings below are based on current source. The stored learning-intelligence branch was inspected without fetching it. Its remote state may have changed.

The older [gap matrix](docs/learnlens/implementation-gap-matrix.md) dates from 14 August and still marks some existing assessment features as missing. Its status counts are not current. Recent dependency updates and the assessment merge are already on local `main`; repeating those completed changes is not a remaining task.

1. **Prevent unknown evidence from satisfying a negated pass rule.**

    Dependencies: none. Suggested owner: assessment backend.

    The pass-rule engine converts an unknown criterion to false before applying `NOT`. A probe with `ALL_OF(a, NOT(b))`, mandatory `a`, `a=MET`, and `b=NOT_EVALUABLE` returned `PASS`. Preserve uncertainty through nested rules. Unknown, missing, or conflicting evidence must not become positive evidence through negation.

    Done when regression tests cover those cases, including nested rules, while retaining explicit review reasons and the mandatory-criterion checks.

    Evidence: [pass_rules.py](src-main/backend/app/services/assessment/pass_rules.py), `PassRuleEngine` and `_evaluate_expression`.

2. **Require real evaluator rules before approving an assessment.**

    Dependencies: none. Suggested owner: assessment backend and assessor UI.

    The setup UI writes empty `approved_anchors`, and the backend defaults to `RULES`. A probe using the answer `bananas` and Bloom `UNDERSTAND` returned `MET` with empty anchors. An unsupported `met` anchor key produced the same result. Add typed evaluator settings, authoring controls, and approval validation. Route criteria beyond reliable automatic checks to human assessment.

    Done when empty, unknown, or contradictory settings block approval and fail safely during evaluation. Test the actual UI-to-API authoring path.

    Evidence: [assessmentDraft.ts](src-main/frontend/src/features/assessment/assessmentDraft.ts), [alignment.py](src-main/backend/app/services/assessment/alignment.py), and [evaluators.py](src-main/backend/app/services/assessment/evaluators.py).

3. **Repair task and dashboard reads after assessed submissions.**

    Dependencies: none. Suggested owner: LMS backend and frontend contracts.

    Assessed submissions store `score=None`. Recommendations and educator summaries still add every attempt's score. Task reads also construct a summary whose schema requires an integer score. These paths cannot safely handle formal-only or mixed histories. Preserve absent numeric data and return separate activity and formal-result fields.

    Done when task reload, learner dashboard, educator dashboards, recommendations, and history work after formal submissions. Include mixed legacy and assessed records. Do not convert missing scores to zero.

    Evidence: [lms.py](src-main/backend/app/services/lms.py), `submit`, `_task_read`, `_calculate_recommendations`, `educator_students`, and `educator_dashboard`; [LMS schemas](src-main/backend/app/schemas/lms.py), `LatestAttemptSummary`.

4. **Close the direct learner evaluation and visibility bypass.**

    Dependencies: none for the immediate restriction; Task 8, decision D-01, for approved learner visibility. Suggested owner: assessment API.

    The mounted learner evaluation route calls the evaluator synchronously and returns the provisional result. It bypasses the normal durable submission job and lacks the pending visibility policy. Restrict this path or route it through the existing job service. Apply ownership, course scope, visibility, and replay controls to any learner retry or status endpoint.

    Done when duplicate requests create no duplicate decisions and learners see only policy-approved information.

    Evidence: [assessment_evaluation.py](src-main/backend/app/api/routes/assessment_evaluation.py), [assessment jobs](src-main/backend/app/services/assessment/jobs.py), and [policy register](docs/learnlens/known-limits-and-deferred-decisions.md).

5. **Restrict unapproved research processing and export access now.**

    Dependencies: none for the immediate restriction. Governed activation follows Task 33. Suggested owner: access controls and research backend.

    The export policy currently grants access through ordinary educator/admin analytics permissions. Runtime eligibility checks only the global research setting. Enforce the existing separate research permission and deny unapproved processing while consent and study controls are incomplete. Do not wait for the full learning-study implementation to close these paths.

    Done when ordinary analytics access cannot authorise research exports. Missing approval, revoked permission, and disabled participation must prevent research processing without restricting course access or changing results.

    Evidence: [research export access policy](src-main/backend/app/services/access.py), [runtime eligibility](src-main/backend/app/services/feedback/runtime.py), and [policy register](docs/learnlens/known-limits-and-deferred-decisions.md).

6. **Give every browser test its own assessment records.**

    Dependencies: none. Suggested owner: test infrastructure.

    Assessor browser tests perform different actions against one seeded decision. The file explicitly allows its lifecycle to depend on run order. Create isolated attempts for each test, browser project, and retry. Keep the real confirmation and override rules intact.

    Done when each action passes alone, in the complete browser run, and on retry without relying on another test. This audit did not reproduce a current browser launch failure.

    Evidence: [assessment-review.e2e.ts](src-main/frontend/e2e/assessment-review.e2e.ts), [browser_e2e_server.py](src-main/backend/tests/browser_e2e_server.py), and [E2E runner](src-main/frontend/e2e/run.mjs).

7. **Start the durable worker and check actual readiness.**

    Dependencies: none for local template mode. Suggested owner: platform.

    The PowerShell launcher starts only the API and frontend, then checks `/health`. The existing readiness probe also checks the worker heartbeat and required runtime state. Start and manage the worker, wait for `/ready`, and show useful startup errors. Shut down only processes owned by the launcher.

    Done when an accepted submission finishes after a worker restart without another submission request. Local mode and research settings must match the chosen adapters. Task 22 supplies the complete adaptive worker path.

    Evidence: [start-quantumlearn.ps1](start-quantumlearn.ps1), [readiness.py](src-main/backend/app/core/readiness.py), and [worker operations](src-main/docs/worker-operations.md).

8. **Record the decisions needed to activate each feature.**

    Dependencies: none. Suggested owners: product owner, assessors, privacy, research, and operations.

    Eleven entries in the decision register remain `PENDING`. D-10 already approves immediate legacy retirement for implementation. Record named owners, approved values, versions, dates, and affected scope for the remaining entries. Start with one quantum outcome and its real criteria, tools, help rules, and learner result policy. Also resolve reassessment, role assignment, evaluator release, retention, escalation, reuse, and release environments.

    Task 8 progress, 7 September 2026: [decision package](docs/learnlens/task-08-decision-package.md) prepared from the saved accepted directions. Remaining policy details and named owner approvals are still required. Task 8 is not complete.

    Done when each dependent feature has the specific approval it needs. Unrelated implementation can continue while a decision remains pending. Test fixture settings do not approve live policy.

    Evidence: [known-limits-and-deferred-decisions.md](docs/learnlens/known-limits-and-deferred-decisions.md), D-01 through D-12.

9. **Preserve the exact approved sources used by each output.**

    Dependencies: none for versioned storage; Task 8, D-08, for retention and destructive deletion rules. Suggested owner: retrieval and data.

    Material reprocessing deletes and recreates chunks. Current task references and hashes do not preserve a complete immutable source revision and passage. Add durable source versions, locations, approval state, and output links. Reprocessing, replacement, or retirement must preserve evidence already used by a task, feedback item, or assessment.

    Done when an authorised reviewer can recover the exact cited passage after a source changes. Keep course scope and page, slide, or heading locations intact.

    Evidence: [ingestion.py](src-main/backend/app/services/rag/ingestion.py), [material_indexing.py](src-main/backend/app/services/material_indexing.py), [persistence models](src-main/backend/app/models/persistence.py), and [material routes](src-main/backend/app/api/routes/materials.py).

10. **Recover interrupted material processing.**

    Dependencies: Task 9. Suggested owner: retrieval and worker.

    Processing saves `PROCESSING` before extraction. Later requests reject material already in that state, and the worker has no material recovery pass. Add durable processing claims, stale-claim recovery, bounded retries, and clear terminal errors.

    Done when a saved upload finishes or reports a recoverable failure after interruption. Concurrent workers must not publish duplicate or partial source revisions. Retain the original upload and useful processing status.

    Evidence: [MaterialProcessor](src-main/backend/app/services/rag/ingestion.py), [offline material processing](src-main/backend/app/services/material_indexing.py), and [worker.py](src-main/backend/app/worker.py).

11. **Store trustworthy simulation evidence and enforce execution limits.**

    Dependencies: none. Suggested owner: quantum services.

    Simulation supports H, X, and CX, with qubit and shot limits. It lacks an operation limit and process-level timeout. Its probabilities are sampled frequencies. Feedback reruns circuits without saving a durable run there. Persist circuit versions, digest, qubit order, measurement mapping, seed, shots, engine versions, counts, and run status. Expose the supported capabilities for publication checks in Task 12.

    Done when runs are bounded and reproducible from saved settings. Use exact probabilities or sampling tolerances where justified. Gate presence or distribution agreement must not stand in for every state property or conceptual claim.

    Evidence: [quantum.py](src-main/backend/app/services/quantum.py), [SubmittedCircuitSimulationProvider](src-main/backend/app/services/feedback/runtime.py), and [QuantumCircuitHandler](src-main/backend/app/services/task_types.py).

12. **Finish educator approval, assessor setup, and publication controls.**

    Dependencies: Tasks 2 and 9; Task 8, D-02, D-04, and D-05. Circuit publication also needs Task 11. Suggested owner: course and assessment teams.

    Generated tasks become ordinary task rows without a general review lifecycle. Course publication checks do not prove individual task approval. Formal definition approval exists, but runtime publication policy remains closed. Add review, edit, approve, reject, and history controls. Connect approved role policies and require complete outcome, criterion, source, support, access, and task-form versions.

    Done when an authorised assessor can publish a valid form without test overrides. Unreviewed generated tasks and unsupported circuits must remain unavailable to learners.

    Evidence: [task_generation.py](src-main/backend/app/services/rag/task_generation.py), [LmsService._validate_publishable](src-main/backend/app/services/lms.py), [assessment dependencies](src-main/backend/app/api/assessment_dependencies.py), and [assessment definitions](src-main/backend/app/services/assessment/definitions.py).

13. **Freeze assessment versions when the learner starts work.**

    Dependencies: Tasks 8 and 12. Suggested owner: assessment and task workspace.

    Current submission code selects the assessment bundle when the learner submits. Immutable submitted attempts do not freeze the conditions at task opening or draft creation. Save the approved task, rules, sources, and conditions when assessed work begins. Carry that reference through draft saves and submission.

    Done when a rule change during an open draft preserves the original approved bundle or returns an explicit conflict. A later version must never silently replace the declared standard.

    Evidence: [LmsService.submit](src-main/backend/app/services/lms.py), [AssessmentSubmissionService](src-main/backend/app/services/assessment/submissions.py), and assessment specification AT21.

14. **Complete the learning episode inside the task workspace.**

    Dependencies: Tasks 11 and 13. Suggested owner: task engine and frontend.

    Six task handlers exist, but answer, code, and circuit fields do not capture the full learning sequence. Add typed prediction, reasoning, explanation, revision, reflection, and transfer responses. Stage matching, sequencing, and other required extensions explicitly. Keep instructions, circuit editing, results, explanations, and feedback together. Save predictions before revealing results where required.

    Done when each supported response survives draft, submit, reload, revision, and controlled simulation failure. Every type needs accessible controls, evidence extraction, evaluator support, and export representation.

    Evidence: [task_types.py](src-main/backend/app/services/task_types.py), [TaskView.tsx](src-main/frontend/src/components/TaskView.tsx), and requirements FR9, FR12-FR14, PD4-PD5, and PD11.

15. **Make unsupported assessment criteria reachable by a human assessor.**

    Dependencies: Tasks 1, 2, 11, 12, and 13. Suggested owner: assessment backend and review UI.

    Production evaluation supports only the rule adapter. Unsupported evaluators leave jobs `REVIEW_REQUIRED` without a decision. The current review queue selects decisions, so those attempts miss the queue. Add a queue for unresolved attempts and a criterion-entry workflow. Connect suitable deterministic circuit checks and approved human or mixed evaluation paths.

    Done when an assessor can inspect evidence, record criterion decisions and reasons, apply the pass rule, and finalise the result. Keep AI evaluation advisory until Task 35 passes its approved gate.

    Evidence: [assessment runtime](src-main/backend/app/services/assessment/runtime.py), [review.py](src-main/backend/app/services/assessment/review.py), and [evaluation job tests](src-main/backend/tests/test_assessment_evaluation_jobs.py).

16. **Deliver grounded assessed feedback under the approved help policy.**

    Dependencies: Tasks 9, 11, 12, and 15; Task 8, D-05. Suggested owner: feedback and retrieval.

    Frozen assessment context already exists. However, the production generator rejects every assessed context and releases a fixed fallback. Implement criterion-linked feedback and permitted revision guidance. Connect task-scoped retrieval that checks material availability and relevance. Record claim-to-passage support beyond citation membership. Extend checks for answer leakage, inappropriate help, unsupported learner claims, and missing reflection.

    Done when approved feedback states missing evidence without exceeding allowed help. Preserve one regeneration, fixed fallback, rejection reasons, and source/model/prompt/rule versions. Feedback approval must not confirm an assessment result.

    Evidence: [PendingAssessmentFeedbackGenerator](src-main/backend/app/services/feedback/agent.py), [feedback runtime](src-main/backend/app/services/feedback/runtime.py), [judge.py](src-main/backend/app/services/feedback/judge.py), and [assessment feedback tests](src-main/backend/tests/test_assessment_feedback_context.py).

17. **Capture learning evidence through the live application.**

    Dependencies: Tasks 9, 11, and 14. Suggested owner: evidence services.

    Append-only evidence services, trusted adapters, privacy checks, and replay controls exist. They are not connected to the mounted learner workflow. Record predictions, reasoning, hints, simulation, responses, revisions, feedback use, reflection, and transfer. Link each item to its task, response, conditions, source, and earlier evidence where relevant.

    Done when a real learner journey creates an authorised, ordered evidence timeline. Replays and partial failures must preserve originals without duplicate accepted observations.

    Evidence: [evidence service](src-main/backend/app/services/evidence/service.py), [evidence adapters](src-main/backend/app/services/evidence/adapters.py), [API router](src-main/backend/app/api/router.py), and [adapter tests](src-main/backend/tests/test_evidence_capture_adapters.py).

18. **Update the shared learner model from real evidence.**

    Dependencies: Task 17. Suggested owner: learner services.

    The versioned model builder and repository exist without application consumers. Define how observations support or contradict an estimate, then connect one controlled update path. Keep understanding, possible misconceptions, assistance, response to feedback, and transfer distinct. Preserve prior snapshots, uncertainty, recency, rule versions, and evidence links.

    Done when concurrent or repeated processing creates consistent snapshots. Produce validated snapshots for teaching services. Tasks 22 and 23 must demonstrate decisions that change because of an estimate. Rule-based uncertainty must remain labelled as an unvalidated estimate until tested.

    Evidence: [builder.py](src-main/backend/app/services/learner_model/builder.py), [learner-model repository](src-main/backend/app/services/learner_model/repository.py), and [learner-model tests](src-main/backend/tests/test_learner_model.py).

19. **Integrate learner corrections and expose scoped evidence and model views.**

    Dependencies: Tasks 17 and 18. Suggested owner: learner services and frontend.

    Stored branch `origin/raveen-learning-intelligence` contains correction contracts, services, models, a migration, and tests. Review and reuse that work before rebuilding it. It is not integrated into local `main`, and it does not add mounted correction routes or screens. Reconcile its migration with current main, then add learner annotations and authorised educator corrections.

    Done when learners can inspect and challenge an estimate. Keep original evidence, review reasons, correction history, and later snapshots. Prove one migration head and protected-history recovery.

    Evidence: [current learner-model services](src-main/backend/app/services/learner_model), [current API router](src-main/backend/app/api/router.py), and the stored branch diff. Its proposed migration is `20260824_0022_learner_model_corrections.py`; current main's head is `20260821_0022`.

20. **Add learner preferences and control over non-essential support.**

    Dependencies: Tasks 14 and 17; Task 8, D-05, for assessed conditions. Suggested owner: learner experience.

    A preference enum exists, but there is no complete preference store, API, or screen. Add pace, format, explanation detail, optional breaks, repeat practice, and personalisation controls. Let learners correct saved choices. Keep access support separate from instructional help.

    Done when preferences persist and learners can disable non-essential personalisation. Choices, help use, access support, and slower pace must not lower formal results. Do not infer a diagnosis or fixed learning style.

    Evidence: [platform enums](src-main/backend/app/domain/platform_enums.py), [TaskView.tsx](src-main/frontend/src/components/TaskView.tsx), and requirements FR35-FR37 and NFR31.

21. **Build the curriculum links and approved diagnostic paths.**

    Dependencies: Tasks 12, 18, and 20. Suggested owner: learning pathway services.

    Ordered outcomes and task prerequisites exist. They do not form the required concept, outcome, source, activity, task-form, and evidence-rule graph. Add those links with versioned exit rules. Support at least three ordered tasks, declared support levels, and fading help after suitable success. Add initial diagnostics and learner-requested prior-mastery checks, including independent conditions and the required assessor confirmation for bypass.

    Done when diagnostics produce learning evidence and explain a permitted pathway change. They must not become formal grades by default. Reject invalid prerequisite links and preserve the assessed standard.

    Evidence: [LearningOutcome](src-main/backend/app/models/lms.py), [LearningTask](src-main/backend/app/models/persistence.py), [current recommendation logic](src-main/backend/app/services/lms.py), and requirements FR10-FR11 and PD1-PD2.

22. **Connect learner evidence to the next approved activity.**

    Dependencies: Tasks 7, 18, 20, and 21. Suggested owner: pathway and worker teams.

    Durable continuation exists. Its shipped progress adapter does nothing, and its recommender returns the completed task reference. Replace these placeholders with model and pathway adapters. Select approved activities from prerequisites and evidence. Save the reason, uncertainty, model snapshot, rule version, learner choice, and educator override.

    Done when checked feedback leads to one model update and a suitable next activity. Restart and retry must not duplicate updates. Learners can defer or replace allowed suggestions without changing the assessment standard.

    Evidence: [worker.py](src-main/backend/app/worker.py), `_OfflineProgressAdapter` and `_OfflineNextTaskRecommender`; [continuation service](src-main/backend/app/services/continuation/service.py).

23. **Add tutor dialogue and a controlled sequence of hints.**

    Dependencies: Tasks 16, 17, 18, and 20. Suggested owner: teaching services and task workspace.

    The current task view has submission and feedback, but no complete tutor conversation or hint progression. Begin with a probing question or conceptual hint. Ask learners to explain their reasoning before further help when the task requires it. Ground replies in the current course and task, and record assistance as evidence.

    Done when conversation state survives reload, help follows assessed conditions, and outputs pass the feedback checks. Answer-seeking cues should redirect to reasoning without making an automatic misconduct finding.

    Evidence: [TaskView.tsx](src-main/frontend/src/components/TaskView.tsx), [API router](src-main/backend/app/api/router.py), [feedback pipeline](src-main/backend/app/services/feedback/pipeline.py), and the architecture's Tutor Agent responsibilities.

24. **Complete learner results, review requests, and appeal resolution.**

    Dependencies: Tasks 3, 4, 13, and 15; Task 8, D-01. Suggested owner: assessment experience.

    Assessor actions exist, but the learner loop is incomplete. Show the permitted result, lifecycle, Bloom target, met and missing criteria, evidence, reasons, and next action. Connect learner-owned review requests to an assessor workflow. The existing appeal model is not a complete route or screen.

    Done when requests and resolutions preserve scope, reasons, notices, and decision history. Learners must distinguish pending review from a confirmed result and reach every action without relying on colour.

    Evidence: [assessment models](src-main/backend/app/models/assessment.py), `AppealOrCorrection`; [review service](src-main/backend/app/services/assessment/review.py), [TaskView.tsx](src-main/frontend/src/components/TaskView.tsx), and AT15-AT17, AT19, AT24.

25. **Prove one complete quantum learning loop before expanding coverage.**

    Dependencies: Tasks 10, 14, 16, 18, 22, 23, and 24, including their prerequisites. Suggested owner: integrated feature team.

    This is the architecture's first delivery milestone. Use one approved introductory outcome. Exercise task selection, prediction, reasoning, circuit work, saved evidence, checked feedback, revision, reflection, learner-model update, and an unaided transfer activity. Include assessor review when the task is assessed.

    Done when one browser journey and backend integration test traverse the real services. Interrupt processing and prove recovery. A returned task ID or passing component test alone does not complete this milestone.

    Evidence: [architecture](LearnLens_Architecture_and_Sources.md), [existing MVP loop test](src-main/backend/tests/test_mvp_learning_loop.py), and [continuation service](src-main/backend/app/services/continuation/service.py).

26. **Implement reassessment and outcome-level result selection.**

    Dependencies: Tasks 12, 13, 15, and 24; Task 8, D-06. Suggested owner: assessment.

    The `ReassessmentLink` model exists without an active workflow. General resubmission still relies on `allow_resubmission`. Add eligibility, an approved equivalent form, a fresh attempt, prior-decision links, and the current-result rule. Implement approved evidence-sufficiency rules across attempts for outcome results. Add course binary results only where required and defined.

    Done when every earlier decision remains readable, the same standard applies, and attempts are never averaged. Review, return, withholding, reassessment, and result replacement must have distinct effects.

    Evidence: [ReassessmentLink](src-main/backend/app/models/assessment.py), [LmsService.submit](src-main/backend/app/services/lms.py), and [assessment specification](docs/02-pass-incomplete-bloom-assessment-spec.md), sections 4 and reassessment rules.

27. **Complete the misconception check and recovery cycle.**

    Dependencies: Tasks 18, 19, 21, 22, and 23. Suggested owner: learner and teaching services.

    The model can store a possible misconception. It does not complete the question, alternate explanation, revision, and transfer cycle. Add supporting and contradicting evidence, a suitable probe, targeted help, and a fresh check. Preserve state changes and educator corrections.

    Done when evidence can leave a hypothesis uncertain, persisted, weakened, or corrected. A single wrong response must not create a certain label. Show why the next intervention was selected.

    Evidence: [learner-model builder](src-main/backend/app/services/learner_model/builder.py), [learner-model contracts](src-main/backend/app/services/learner_model/contracts.py), and requirements FR34 and AC13.

28. **Add a human escalation and AI-output reporting workflow.**

    Dependencies: Tasks 15, 16, 19, 23, and 27; Task 8, D-09. Suggested owner: educator experience and operations.

    Assessment review and audit flags do not cover the required escalation process. Extend existing feedback reporting into managed escalation and cover other AI outputs. Route repeated rejection, failed evaluation, conflicting evidence, and unresolved misconceptions to an owned queue. Store severity, evidence links, status, target time, response, resolution reason, and learner notice.

    Done when a report moves through acknowledgement, action, resolution, and closure with an audit trail. Accepted AI feedback must also be available for human sampling.

    Evidence: [FeedbackReportButton.tsx](src-main/frontend/src/features/feedback/FeedbackReportButton.tsx), [feedback routes](src-main/backend/app/api/routes/feedback.py), [feedback repository](src-main/backend/app/services/feedback/repository.py), and requirements PD7, PD12, FR38, and NFR20-NFR21.

29. **Finish progress views and retire numeric learner-result semantics.**

    Dependencies: Tasks 3, 18, 19, 22, 24, 26, and 27. Final legacy removal also needs Task 8, D-10. Suggested owner: LMS, analytics, and frontend.

    Learner and educator screens still expose scores and averages. Replace these with clearly separated activity, evidence, uncertain estimates, and formal binary results. Add individual and cohort views for revision, independence, transfer, misconceptions, feedback use, and adaptation history. Remove score-driven learner progress, recommendations, averages, and misleading result wording. Current formal submissions already skip numeric grading.

    Done when each important indicator links to scoped evidence. Preserve protected legacy history through the approved retirement window. Quantum probabilities and technical quality measures remain valid within their own context.

    Evidence: [StudentDashboard.tsx](src-main/frontend/src/components/StudentDashboard.tsx), [EducatorDashboard.tsx](src-main/frontend/src/components/EducatorDashboard.tsx), [TaskView.tsx](src-main/frontend/src/components/TaskView.tsx), and [analytics services](src-main/backend/app/services/analytics).

30. **Move reminder writes out of dashboard reads and finish reminder rules.**

    Dependencies: Tasks 20, 22, and 24. Suggested owner: LMS and worker.

    `student_dashboard` creates reminders, stores recommendations, and commits during a GET. Move these changes to explicit commands or scheduled jobs. Add course time zones, extensions, access plans, notification preferences, and current completion checks. Enforce at most one reminder per task in 24 hours with a concurrency-safe rule.

    Done when repeated dashboard reads make no state changes. Test simultaneous processing, time-zone boundaries, extensions, completed work, and disabled notifications.

    Evidence: [lms.py](src-main/backend/app/services/lms.py), `student_dashboard`, `_create_overdue_reminders`, and `_create_reminder`; [behaviour findings](docs/plans/009-lms-behaviour-findings.md).

31. **Make gamification optional and remove learner rankings.**

    Dependencies: Tasks 20 and 29. Suggested owner: learner experience and LMS.

    The points card is always shown, a perfect-score award remains, and educator data includes a leaderboard. Add a real opt-out. Recognise allowed participation, reflection, revision, and feedback use without ranking learners or tying rewards to a formal mark.

    Done when points never alter assessment, pathway standards, or essential access. Replays, retries, slower pace, breaks, and approved support must not create penalties or duplicate rewards.

    Evidence: [gamification.py](src-main/backend/app/services/gamification.py), [StudentDashboard.tsx](src-main/frontend/src/components/StudentDashboard.tsx), and [educator dashboard projection](src-main/backend/app/services/lms.py).

32. **Approve the learning-study protocol and data plan.**

    Dependencies: Task 8, especially D-03, D-07, and D-08. Planning can run alongside implementation. Suggested owner: research lead and governance.

    Existing research documentation focuses on technical feedback comparisons. Define the learning question, comparator, allocation, outcomes, sample-size basis, exclusions, missing-data rules, withdrawal, retention, and reviewer blinding. Obtain the required ethics decision and preregister the approved study before recruitment. Separate research consent from course access.

    Done when an approved protocol covers unaided conceptual understanding, transfer, and any delayed-retention claims. Technical judge performance must not be presented as proof of learning improvement.

    Evidence: [research-methodology.md](src-main/docs/research-methodology.md), the [architecture](LearnLens_Architecture_and_Sources.md), and requirements BP12-BP14 and NFR25.

33. **Enforce research permission, consent, and governed exports.**

    Dependencies: Tasks 5, 9, 17, 18, 22, 24, and 32; Task 8, D-03 and D-08. Suggested owner: research backend and privacy.

    Export access currently delegates to ordinary analytics access. Runtime research eligibility checks only the global setting. Require explicit course-scoped research permission and an approved study. Add versioned consent, withdrawal, field approvals, missing-data reasons, retention, and participant eligibility. Extend the pseudonymous export with evidence, model, adaptation, and result references.

    Done when unapproved processing and exports fail closed. Revoked access, withdrawal, and missing consent must be tested. Research condition and participation must not change teaching access, adaptation, or formal results.

    Evidence: [access.py](src-main/backend/app/services/access.py), `SqlAlchemyResearchExportAccessPolicy`; [feedback runtime](src-main/backend/app/services/feedback/runtime.py), `ConfiguredResearchEligibility`; [research exports](src-main/backend/app/services/research_export.py).

34. **Build and verify the learning-study instruments and records.**

    Dependencies: Tasks 25, 29, 32, and 33. Suggested owner: research and analytics.

    Paired technical evaluation records and export v1 exist. Add the approved pre-task, in-process, post-task, learner-experience, and educator-review records. Implement unaided conceptual, fresh transfer, and delayed-retention activities where required. Record help conditions, deviations, attrition, missingness, and actual provider/model/prompt/rule versions.

    Done when a complete approved sample exports in CSV or JSON with linked learning stages and no direct identity fields. Keep learning outcomes separate from feedback correctness and judge metrics. Label local template generation accurately.

    Evidence: [research export schema](src-main/backend/app/schemas/research_export.py), [research services](src-main/backend/app/services/research), and requirements NFR25 and NFR30.

35. **Validate quantum content, feedback, and assessment against expert judgements.**

    Dependencies: Tasks 11, 15, 16, 23, and 25; Task 8, D-07 and D-12. Suggested owner: assessors and evaluation reviewers.

    Automated evaluator classes and fake-provider tests do not establish educational validity. Build at least 100 educator-approved quantum cases. Measure factual accuracy, hallucinations, useful feedback, flawed-output rejection, false rejection, false pass, and false incomplete. Include alternate response forms and unusual valid approaches. Repeat validation after material model, prompt, source, or rule changes.

    Done when the approved evaluator gate passes. Required content targets include at least 80% factual accuracy, at most 5% hallucinations, and feedback review averaging 4/5. Judge rejection must reach 80%, with false rejection at most 20%. Establish a trained-human agreement baseline and report criterion agreement by task type with uncertainty. Test answer length, writing style, and approved access modes. Feedback and judge thresholds cannot clear the separate AI assessment release gate.

    Evidence: [requirements NFR12-NFR14 and NFR28](docs/01-implementation-requirements.md), [evaluator services](src-main/backend/app/services/assessment/evaluators.py), and [research methodology](src-main/docs/research-methodology.md).

36. **Refresh traceability and run the complete automated checks.**

    Dependencies: Tasks 1-34 for the final combined run. Run targeted checks with each earlier change. Suggested owner: integration and independent reviewers.

    Update every FR, PD, BP, NFR, AC, and AT row against current code and evidence. Replace obsolete missing-feature claims and broken references to retired plans. Run configured formatting, lint, contracts, migration, backend, frontend, browser, dependency, and secret checks. Maintain at least 80% backend service statement coverage.

    Done when evidence and independent review apply to the final commit. Keep manual and external checks separate. New dependency audits are required; the previously updated packages are not assumed to remain vulnerable or permanently safe.

    Evidence: [quality.yml](.github/workflows/quality.yml), [implementation-gap-matrix.md](docs/learnlens/implementation-gap-matrix.md), and [work order](docs/03-codex-implementation-work-order.md).

37. **Prove security, migration safety, restart recovery, and restore completeness.**

    Dependencies: Tasks 9, 10, 19, 25, 26, 28, 33, and 36. Suggested owner: platform and security reviewers.

    Existing migration and worker tests cover useful parts. Exercise the complete system with concurrent submissions, process termination, provider timeout, malformed output, simulation failure, and database contention. Check cross-user/course access, costly-route limits, upload handling, secret protection, and safe logs. Restore the database and uploaded files into an isolated environment.

    Done when zero accepted records are lost or duplicated, all verification records restore, and one migration head matches readiness. Preserve protected histories during rollback. No open critical or high security finding may remain.

    Evidence: [worker operations](src-main/docs/worker-operations.md), [assessment migration guide](docs/learnlens/person-a-assessment-migration.md), [deployment guide](src-main/docs/deployment.md), and requirements NFR5, NFR15-NFR17, NFR23.

38. **Measure load, provider cost, and runtime configuration changes.**

    Dependencies: Tasks 25, 35, 36, and 37; Task 8, D-12. Suggested owner: platform and operations.

    Run representative full learning loops with actual approved providers. At 50 concurrent users, ordinary requests must reach p95 at most 2 seconds, progress at most 3 seconds, and feedback at most 10 seconds. Test 5 to 100 users with errors below 1% and ordinary-request p95 growth at most 25%. Set a separate assessment-evaluation target.

    Done when average external LLM cost is at most AUD 0.10 per loop. Save usage, prices, currency assumptions, and configuration. Verify authorised provider, model, timeout, retry, and budget changes without source edits. Let measurements decide whether SQLite or worker concurrency needs changing.

    Evidence: [configuration](src-main/backend/app/core/config.py), [LLM service](src-main/backend/app/services/llm.py), [deployment configuration](src-main/deploy), and requirements NFR7-NFR8 and NFR22.

39. **Complete browser, accessibility, and first-time usability checks.**

    Dependencies: Tasks 24-31 and 36; Task 8, D-12. Suggested owner: accessibility reviewers and product testing.

    Test complete student, educator, assessor, and administrator paths on current Chrome, Edge, Firefox, and native Safari. Record keyboard, focus, screen-reader, contrast, zoom, reflow, error, and circuit-text checks. Automated access checks and Playwright WebKit do not replace the missing manual or native evidence.

    Done when key paths meet WCAG 2.2 AA with no critical access fault. Record usability averaging at least 7/10. Five first-time educator setup trials must finish within 20 minutes. At least 80% of first-time students must complete the required journey unaided within 15 minutes.

    Evidence: [browser tests](src-main/frontend/e2e), [frontend components](src-main/frontend/src/components), and requirements NFR1-NFR4 and NFR18.

40. **Demonstrate the approved reuse target.**

    Dependencies: Tasks 25 and 36; Task 8, D-11. Suggested owner: a developer outside the main feature implementation.

    The second-subject reuse target still needs approval and practical evidence. Configure one demo module for another technical subject using the existing extension points. Record effort and any core changes needed. Keep this exercise separate from claims that learning results generalise to that subject.

    Done when the approved target is met. The requirements propose 16 developer-hours, but that number is not yet an approved policy. Verify that core evidence, model, adaptation, and assessment engines remain reusable.

    Evidence: [task-type extension guide](src-main/docs/task-type-extension.md), requirements NFR9, NFR11, NFR24, and [decision D-11](docs/learnlens/known-limits-and-deferred-decisions.md).

41. **Complete hosted validation and the release handoff.**

    Dependencies: Tasks 1-40, with all applicable decisions and evidence resolved. Suggested owner: release owner, operations, and product owner.

    Deployment packages and guides exist, but this audit did not verify a hosted installation. Prove the same package works locally and in the approved hosted environment. Check TLS, persistent files, database state, worker supervision, readiness, monitoring, backup, and rollback. Collect hosted availability evidence against the 99.5% monthly target; configuration alone cannot prove it.

    Done when the tested commit, deployment settings, evidence, owners, open limits, and rollback steps form a reviewed handoff. Update architecture, setup, assessor, learner review, privacy, export, and operations guides. Pilot activation follows the recorded release decision.

    Evidence: [compose.yaml](src-main/deploy/compose.yaml), [compose.hosted.yaml](src-main/deploy/compose.hosted.yaml), [deployment.md](src-main/docs/deployment.md), and [implementation work order](docs/03-codex-implementation-work-order.md).

Tasks 1-7 can begin immediately while owners resolve Task 8. Source, quantum, and test work can run in parallel. Task 25 is the first complete learning-loop milestone. Tasks 26-41 extend the remaining product flows and establish the evidence needed for a pilot. The architecture does not require separate servers for each named agent, a new database by default, or Self-RAG reflection-token training.
