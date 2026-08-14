# LearnLens implementation requirements

Status: implementation baseline

Last updated: 2026-08-14

Primary sources: `LearnLens_Project_Document.pdf`, `Software Requirements Specification updated.pdf`, and `LearnLens Learning, Assessment and Grading Blueprint.docx`

## 1. Purpose

This document is the main build specification for LearnLens. Codex must use it to audit the current code, keep working features, find gaps, and add missing behaviour.

This is not a greenfield brief. Codex must first prove what already exists. It must not replace working code without a clear reason and test coverage.

The detailed assessment rules are in [`02-pass-incomplete-bloom-assessment-spec.md`](./02-pass-incomplete-bloom-assessment-spec.md). The work sequence is in [`03-codex-implementation-work-order.md`](./03-codex-implementation-work-order.md).

## 2. Controlling product decisions

These rules override any conflicting wording in the source documents.

1. The only learner assessment results are `PASS` and `INCOMPLETE`.
2. A response that does not meet the pass rule maps to `INCOMPLETE`. Do not display `FAIL` as a third result.
3. Numeric marks, percentages, grade bands, weighted course marks, GPA values, and score-based grade caps are out of scope.
4. The assessor selects the target revised Bloom cognitive process for each assessed outcome or task.
5. The assessor must also approve the evidence criteria that show the target was achieved. A Bloom label alone cannot grade a response.
6. The system evaluates the submitted evidence against the approved criteria and returns `PASS` or `INCOMPLETE`.
7. A formal result remains subject to assessor confirmation, correction, or override. The system may make a provisional result automatically.
8. Formative practice, diagnostics, confidence, time, hints, attempts, breaks, and access supports cannot lower an assessment result.
9. Learner-model estimates, progress states, research metrics, and gamification records are not assessment results.
10. Accessibility support is separate from instructional scaffolding. Approved access support does not weaken the standard.
11. Adaptation may change sequence, pace, format, or support. It must not secretly change the target standard for one learner.
12. All important decisions must retain evidence, rule versions, model versions, reasons, actors, and timestamps.

## 3. Required vocabulary and enums

Use one meaning for each term across the database, API, UI, logs, tests, and analytics.

### 3.1 Assessment result

```text
AssessmentResult = PASS | INCOMPLETE
```

- `PASS` means the approved evidence rule for the assessor-set Bloom target was met.
- `INCOMPLETE` means the rule was not met, evidence was missing, or review is still needed.
- Never use `0`, `1`, `false`, `failed`, or a percentage as the public grade.
- An internal Boolean such as `target_achieved` may exist, but `false` must map to `INCOMPLETE`.

### 3.2 Result lifecycle

```text
ResultState = NOT_ASSESSED | PROVISIONAL | CONFIRMED | OVERRIDDEN | VOID
```

This state is separate from `AssessmentResult`.

- `NOT_ASSESSED` means no valid decision exists.
- `PROVISIONAL` means the system evaluated the evidence but an assessor has not confirmed it.
- `CONFIRMED` means an assessor accepted the result.
- `OVERRIDDEN` means an assessor changed the provisional result and recorded a reason.
- `VOID` means the attempt cannot be used, such as after a task fault or policy decision.

### 3.3 Submission state

```text
SubmissionState = NOT_STARTED | DRAFT | SUBMITTED | UNDER_REVIEW | RETURNED | COMPLETED
```

Submission state must not be overloaded as the assessment result.

### 3.4 Assessment purpose

```text
AssessmentPurpose = DIAGNOSTIC | FORMATIVE | AS_LEARNING | SUMMATIVE | RESEARCH
```

Only a task declared as assessed before the learner starts may create a formal `PASS` or `INCOMPLETE` result.

### 3.5 Bloom target

```text
BloomProcess = REMEMBER | UNDERSTAND | APPLY | ANALYSE | EVALUATE | CREATE
BloomKnowledge = FACTUAL | CONCEPTUAL | PROCEDURAL | METACOGNITIVE
```

Store the process and knowledge dimension separately. Australian spelling uses `ANALYSE` in the UI. API compatibility may use a documented wire value such as `analyze`, but one mapping must be used everywhere.

## 4. Scope

The pilot covers selected introductory quantum computing content. It includes superposition, measurement, interference, entanglement, gates, and circuit behaviour. It may also cover quantum random number generation, teleportation, Deutsch-Jozsa, Bernstein-Vazirani, and Grover's algorithm.

The system must support:

- Course, module, material, and learning-outcome setup.
- PDF, DOCX, PPTX, and HTTPS learning resources.
- Educator review of AI-generated tasks and content.
- Adaptive diagnostics and prior-mastery checks.
- Multiple task types and progressive micro-tasks.
- Prediction, explanation, attempt, feedback, revision, reflection, and transfer.
- Qiskit Aer simulation with accessible text evidence.
- RAG grounded in educator-approved material.
- Quality review before AI output reaches learners.
- Time-ordered learning evidence and learner-model history.
- Explainable adaptation with learner and educator control.
- Possible-misconception checks that remain uncertain until supported.
- Individual and cohort learning-progress views.
- Pass/incomplete assessment against an assessor-set Bloom target.
- Accessibility, privacy, audit, safe fallback, and research export.

The first release must not:

- Diagnose disability, neurodivergence, medical status, psychology, motivation, or fixed ability.
- Treat a final answer, AI score, or Bloom label as enough proof of achievement.
- Use research participation or demographic data to change teaching or results.
- Publicly rank learners.
- Penalise help use, retries, access support, breaks, extra time, or low confidence.
- Present AI output as approved educator content when it has not passed review.
- Claim that the pilot proves transfer to other study areas.

## 5. User roles and permissions

### 5.1 Student

Students must be able to:

- Sign in and access only their assigned activities and records.
- Select a learning goal or continue a current pathway.
- Open a task, save a draft, submit, revise, reflect, and repeat when allowed.
- Complete each supported response type.
- Record predictions, explanations, reasoning, and confidence when requested.
- Use Qiskit-based circuit activities without losing work after a controlled error.
- Receive grounded and quality-checked feedback.
- View their own time-ordered evidence and learner-model summaries.
- Distinguish recorded evidence from uncertain system inference.
- View why a task, format, pace, support level, or next step was suggested.
- Accept, defer, or replace a non-essential suggestion.
- Change non-essential pace, format, feedback, and scaffold preferences.
- Correct inaccurate saved preferences.
- Disable non-essential personalisation.
- Take optional breaks and repeat formative work without penalty.
- Ask for a prior-mastery check where the educator has approved one.
- View the assessor-set Bloom target, evidence criteria, allowed tools, and task conditions before an assessed attempt.
- View `PASS` or `INCOMPLETE`, the decision reasons, missing evidence, and next action.
- Request human review or use the approved correction and appeal path.
- Report inaccurate, unsafe, biased, inaccessible, or unsuitable AI output.

Students must never access another student's data.

### 5.2 Educator and assessor

An educator may also hold an assessor permission. The permission must be explicit.

Educators must be able to:

- Create, edit, publish, archive, and inspect their courses and modules.
- Upload or link material and inspect its retrieval status.
- Create versioned learning outcomes and prerequisites.
- Review, edit, approve, reject, and report generated tasks.
- Inspect sources, expected evidence, task forms, and Quality Judge results.
- Inspect learner evidence, model updates, uncertainty, and adaptation reasons.
- Correct possible-misconception classifications.
- Set allowed adaptation rules and thresholds.
- Override tasks, recommendations, pace, format, difficulty, and scaffold levels.
- View individual and cohort progress within assigned courses.
- Review flagged AI output and repeated agent failures.
- Record reasons for important changes and overrides.

Assessors must also be able to:

- Set the Bloom process and knowledge dimension for an assessed outcome or task.
- Define the claim, required evidence, mandatory criteria, and pass rule.
- Set permitted tools, instructional support, and access conditions.
- Approve parallel task forms and transfer rules.
- Publish the target and criteria before the learner begins.
- Review the full evidence used by the system.
- Confirm, withhold, void, or override a provisional result.
- Record a reason when changing or withholding a result.
- Return an incomplete attempt with clear next steps and reassessment rules.

Educators must only access courses and learners assigned to them.

### 5.3 Administrator

Administrators must be able to:

- Create, edit, deactivate, and reactivate accounts.
- Manage course records and system settings.
- Configure LLM providers and models without source changes.
- Configure cost, retry, timeout, and feature-flag settings.
- Manage approved research export access.
- Review system-wide audit, security, backup, and failure records.
- Archive data using approved rules without breaking referential integrity.

### 5.4 Research access

Research access is not implied by another role. It needs separate approval and least-privilege controls. Research users receive approved pseudonymous fields only.

## 6. Functional requirements

The `FR` number keeps traceability with the SRS. The wording below includes the new binary result model.

### 6.1 Identity, course, and content

#### FR1 - User role management

Provide student, educator, assessor, administrator, and approved research permissions. Protected pages and API routes must enforce role and course scope.

Done when all role and cross-course denial tests pass.

#### FR2 - Educator account access

Authenticate valid educators, show the right dashboard, and reject invalid or out-of-scope access.

#### FR3 - Student account access

Authenticate students and show only assigned activities and their own records.

#### FR4 - Course configuration

Allow educators to create, view, edit, publish, and archive courses with a title, description, modules, enrolment state, and version history. Changes must persist across sessions.

#### FR5 - Learning material intake

Accept PDF, DOCX, and PPTX files up to 20 MB and valid HTTPS links. Validate file type, size, access, malware policy, parse result, and course ownership. Keep the original resource and processing state.

#### FR6 - Learning outcome setup

Allow educators to create, edit, version, retire, and delete unused outcomes. Each outcome must belong to a module.

An assessed outcome must also store:

- Learner-facing wording.
- Owner and approval state.
- Source and source version.
- Prerequisites and bypass rule.
- Bloom process and knowledge dimension.
- Claim and observable evidence rules.
- Task families and parallel-form rules.
- Assessment purpose.
- Mandatory criteria and pass rule.
- Tool, support, access, transfer, and review conditions.

#### FR7 - Content retrieval

Each retrieval request must return at least one source-labelled passage from authorised course material or state that no relevant passage was found. Store the query, filters, returned chunks, rank, source versions, and retrieval model version.

### 6.2 Task and pathway management

#### FR8 - Adaptive and reviewable task generation

Generate an educator-reviewable task with:

- Prompt and response type.
- Difficulty basis.
- Course, module, outcome, and source links.
- Assessment purpose.
- Target Bloom process and knowledge dimension, if assessed.
- Intended evidence type.
- Expected response features and mandatory criteria.
- Pass rule for an assessed task.
- Permitted tools and support.
- Access modes and equivalent formats.
- Prediction, reasoning, confidence, revision, reflection, misconception, or transfer parts where useful.
- Task, prompt, model, source, and rubric versions.

An assessed task cannot be released until an assessor approves these fields.

#### FR9 - Multiple task types

Create, show, accept, save, and evaluate at least:

- Single-answer multiple choice.
- Multiple-answer selection.
- Short answer.
- Explanation and reasoning.
- Code explanation.
- Code completion or change.
- Quantum circuit interpretation or construction.
- Prediction.
- Reflection.
- Transfer or new-context application.

Each type needs a typed response schema, validation, accessible controls, evaluator contract, and tests.

#### FR10 - Scaffolded learning pathway

Allow a complex topic to use at least three ordered tasks with clear difficulty, prerequisites, support level, and exit rules. Support must fade after success where suitable.

#### FR11 - Sequencing and prior-mastery bypass

Present tasks in prerequisite order. A learner may request an educator-approved diagnostic. Record its evidence, target, independent conditions, provisional decision, assessor confirmation, reason, and affected pathway.

#### FR12 - Task completion and revision

Support open, draft, submit, revise, reflect, and repeat actions. Show submission state, original response, later versions, feedback, and current result.

Repeated formative work and approved support must not reduce progress, gamification, or assessment status.

#### FR13 - Code-based learning

Retain code formatting in the UI, API, database, feedback, and export. Support gate identification, behaviour explanation, fault finding, and code change tasks.

#### FR14 - Quantum simulation and accessible evidence

Run valid small circuits through Qiskit Aer. Display the circuit, counts or probabilities, shot count, and an equivalent text form. Collect a prediction before revealing results when prediction is assessed.

Invalid code, timeouts, and simulation faults must return a controlled error. The learner's work must remain saved.

### 6.3 Feedback and AI quality

#### FR15 - Automated feedback

Generate and store feedback for each submitted supported task. Link it to the learner, task, response version, source evidence, agent run, and Quality Judge result.

#### FR16 - Actionable learning feedback

Feedback must address reasoning and process, not just correctness. For an incomplete response, it must identify the gap, give the least revealing useful support, invite revision or reflection, and state a next action.

For a pass, confirm what evidence met the rule. Add a reasoning check or transfer task where suitable.

#### FR17 - AI output quality review

Review generated tasks, explanations, suggestions, feedback, and provisional assessments for:

- Factual accuracy.
- Grounding and source use.
- Relevance.
- Outcome and Bloom alignment.
- Evidence-rule alignment.
- Suitable support and answer leakage.
- Clear language and useful next steps.
- Accessibility and inclusive wording.
- Bias and unsupported learner claims.
- Support for reflection and independent work.

The judge's own result must use a separate enum such as `APPROVED` or `REJECTED`. It must not be confused with the learner's `PASS` or `INCOMPLETE`.

#### FR18 - Feedback validation and fallback

Display AI feedback only after judge approval. Regenerate once after rejection. After a second rejection, show a safe fallback, keep the submission, log both attempts, and flag educator review when needed.

### 6.4 Evidence, learner model, and adaptation

#### FR19 - Progress and evidence history

Preserve a time-ordered history of predictions, explanations, attempts, revisions, confidence, feedback, hints, scaffolds, reflections, misconception checks, transfer, submission state, assessment result, result lifecycle, and timestamps.

Do not store numeric learner marks. New evidence must not overwrite older evidence.

#### FR20 - Learning and research events

Record authorised pre-learning, in-process, post-learning, learner-experience, and educator-review events under a pseudonymous research ID. Include course, outcome, activity, evidence type, attempt, condition, time, and agent or model version.

Research capture needs consent, withdrawal, missing-data, and field-approval controls.

#### FR21 - Student progression view

Show completion, task state, `PASS` or `INCOMPLETE`, result lifecycle, attempt history, revisions, confidence change, feedback use, misconception evidence, independence, transfer, and outcome summaries.

Separate observation from system inference. Never show another student's information.

#### FR22 - Educator progress view

Show individual and cohort changes in understanding, reasoning, confidence calibration, feedback use, misconception correction, scaffold use, independence, transfer, and binary assessment results.

Allow inspection of the evidence and uncertainty behind important model changes and adaptations.

#### FR23 - Explainable suggestions

After a learner-model update, suggest a next task or support choice from observable evidence. It may change explanation, difficulty, task size, scaffold, format, pace, guidance, practice rate, feedback, or next activity.

Show a short reason. Allow authorised learner and educator override. Do not change the approved assessment standard.

#### FR24 - Notifications

Create an in-app reminder when a task is at least 24 hours overdue. Create no more than one reminder for the same task in any 24-hour period. Respect course time zone, extensions, access plans, completion, and notification preferences.

#### FR25 - Inclusive gamification

Gamification is optional and off by user choice. It must not rank learners publicly or affect `PASS` or `INCOMPLETE`.

It may recognise reflection, revision, persistence, feedback use, misconception correction, or transfer. It must not penalise pace, retries, access support, breaks, hints, or scaffolds.

#### FR26 - Persistent data

Persist every domain record in Section 7 with stable IDs, valid links, version data, and course scope. Use transactions for multi-record decisions.

#### FR27 - Administration

Allow only administrators to manage accounts and system settings. Prefer deactivate and archive actions over destructive deletion when dependent data exists.

#### FR28 - End-to-end learning loop

Complete one uninterrupted loop covering course setup, material intake, outcome and Bloom setup, task approval, evidence capture, explanation, attempt, checked feedback, revision, reflection, transfer, learner-model update, explainable next step, pass/incomplete assessment where declared, storage, and audit.

#### FR29 - Continuous learning evidence

Link every evidence item to the learner, course, outcome, activity, response version, source interaction, task conditions, and time. Capture both supporting and contradicting evidence.

#### FR30 - Learner model

Maintain a time-ordered, outcome-specific learner model. It may estimate proficiency, reasoning strengths and gaps, possible misconceptions, confidence calibration, feedback use, scaffold dependence, independence, transfer, and recency.

Each inference needs evidence links, uncertainty, model version, prior state, and time. It is not an assessment result and must not store protected diagnoses or demographic labels.

#### FR31 - Assess As You Learn cycle

A full concept episode should include prior knowledge or prediction, explanation, progressive practice, initial attempt, feedback, revision, reflection, transfer, and a learner-model update where useful.

Do not force every prompt into every micro-task. One final answer or result is not enough evidence of learning change.

#### FR32 - Adaptive support

Adapt only from observed evidence, explicit preferences, learner choices, and authorised educator rules. Keep the approved Bloom target and pass standard stable.

#### FR33 - Adaptation trace

For each important adaptation, store the trigger evidence, learner-model state, action, reason, uncertainty, agent, model version, time, and override history.

#### FR34 - Possible-misconception support

Treat a misconception as a hypothesis. Store supporting and contradicting evidence and confidence. Ask a short check question, give targeted help, allow revision, use a fresh or transfer task, and record `PERSISTED`, `WEAKENED`, `CORRECTED`, or `UNCERTAIN`.

#### FR35 - Inclusive learning choices

Where the construct permits, offer text, visual, worked example, circuit, and stepwise forms. Allow explanation length, feedback form, pace, breaks, and repeat practice controls.

#### FR36 - Reflection

Support selected prompts for prediction, reasoning, confidence, comparison, changed understanding, next action, and independent reuse. Keep reflection brief and timed to useful moments.

#### FR37 - Learner control

Allow learners to inspect and change non-essential preferences, request more or less support, change a format, accept or replace a suggestion, correct a saved preference, disable non-essential personalisation, and revisit work without penalty.

#### FR38 - Educator and assessor oversight

Allow educators to inspect evidence and reasons, control generated content, correct misconceptions, change adaptations, set rules, review flags, and record actions.

Allow assessors to set the Bloom target and pass evidence, then confirm or override a provisional `PASS` or `INCOMPLETE` result.

#### FR39 - Learning-progression analytics

Show individual and cohort trends for the evidence areas in FR22. Keep observed facts, model estimates, binary results, and research measures distinct. Show uncertainty where relevant.

### 6.5 Project-document requirements not fully captured by the SRS numbers

These requirements come from the LearnLens Project Document. Codex must include them in the gap audit even when the SRS has no matching FR number.

#### PD1 - Initial adaptive diagnostic

When a learner first starts an outcome or pathway, offer an educator-approved diagnostic that can capture prior knowledge, reasoning, confidence, possible misconceptions, and needed support. Record the result as learning evidence. Do not treat it as a formal grade by default.

#### PD2 - Curriculum and concept graph

Represent links among outcomes, concepts, prerequisites, activities, task forms, sources, evidence criteria, and assessment rules. The path engine must use these links when it selects a task. A flat list of questions does not meet this requirement.

#### PD3 - Dynamic learner profile

The learner model must be able to represent outcome-linked prior knowledge, strengths, gaps, possible misconceptions, confidence, useful explanation forms, successful and unsuccessful strategies, and support needs. Each value needs evidence, time, uncertainty, and version data.

Do not turn these values into a fixed ability or learning-style label.

#### PD4 - Full task range

In addition to FR9, support or plan extension points for:

- Circuit outcome prediction.
- Classical and quantum state comparison.
- Circuit error identification.
- Circuit change for a stated outcome.
- Measurement-probability interpretation.
- Part-complete solution work.
- Matching and sequencing.
- Confidence prompts.
- Reflection on an incorrect prediction.
- Application in a new context.

The MVP may stage these task types, but the gap matrix must show which are missing.

#### PD5 - Controlled circuit variation and diagnosis

The quantum layer must support controlled circuit variations, state or measurement views, syntax and structure checks, and technical fault detection. It must provide evidence to other agents without giving the full answer too early.

#### PD6 - Academic integrity response

Detect repeated answer-only requests or copied-solution signals as review cues. Redirect the learner to a prediction, explanation, partial step, or fresh task. Do not make an automatic misconduct finding or assessment penalty.

#### PD7 - Human escalation workflow

Create a real escalation process, not only a log flag. It needs:

- Trigger type and severity.
- Learner, course, outcome, and correlation links.
- Evidence and agent history.
- Queue owner.
- `OPEN`, `ACKNOWLEDGED`, `IN_PROGRESS`, `RESOLVED`, and `CLOSED` states.
- Due or service target.
- Educator response and resolution reason.
- Learner notice when suitable.
- Audit history.

Triggers include persistent misconceptions, conflicting evidence, possible wrong AI content, repeated judge rejection, unusual learning patterns, failed assessment evaluation, or inadequate automated feedback.

#### PD8 - Learner correction of model information

Allow a learner to challenge, correct, or annotate inaccurate evidence or learner-model information. Keep the original record, the learner note, the review outcome, and later model changes.

#### PD9 - Educator content approval gate

Generated tasks and material educational content need an explicit approval state. Course configuration alone is not approval. Store the reviewer, version, action, reason, and time.

#### PD10 - Feedback-effectiveness analytics

Help educators identify feedback that leads to useful revision or transfer, questions that may be unclear, common misconceptions, learners needing support, and learners ready for harder work. Treat these as evidence-based indicators, not fixed labels.

#### PD11 - Progressive scaffold sequence

For suitable circuit work, support a sequence such as initial state, gate choice, predicted state change, simulation check, difference explanation, circuit change, and combined solution. The exact steps remain outcome-specific.

#### PD12 - Human-guided consequential decisions

Educators remain responsible for outcome design, content approval, key interventions, assessment rules, and formal results. AI agents support those actions but do not replace the accountable human role.

### 6.6 Assessment-blueprint controls that remain required

The binary result change removes numeric marks. It does not remove these validity and fairness controls.

#### BP1 - Prospective purpose

Declare each task as diagnostic, formative, as-learning, assessed, or research before evidence is collected. Practice cannot become assessed after the learner completes it.

#### BP2 - Evidence-centred design

For each assessed outcome, state the claim, supporting evidence, contradicting evidence, insufficient evidence, task conditions, criteria, decision rule, and next action.

#### BP3 - Construct alignment

Keep the trace from outcome to Bloom target, activity, task, evidence, criteria, feedback, result, and adaptation. Block approval when a link is missing.

#### BP4 - More than one weak signal

Do not infer broad mastery, independence, or a persistent misconception from one answer or one AI label. The assessor must define sufficient evidence for the decision being made.

#### BP5 - Supported versus independent work

Record instructional help and fresh independent evidence separately. A successful revision shows learning, but it does not prove independent performance on the same revealed item.

#### BP6 - Construct-equivalent access

For each assessed task, define the intended construct, unrelated access demands, equivalent modes, approved adjustments, and any alternate mode that would change the construct.

#### BP7 - Learner rights

Learners can see the outcome, target, criteria, conditions, evidence, result reason, and review path. They can correct or annotate misleading model data and disable non-essential personalisation without penalty.

#### BP8 - Consequential audit

Keep the exact task form, sources, Bloom target, criteria, rule, tools, support, access mode, response, evaluator, model, prompt, retrieval, system result, assessor action, and review history.

#### BP9 - Assessment moderation

Use approved criterion descriptions and response anchors. Train assessors on shared examples. Preserve original, second-review, and resolved decisions with reviewer identity and time.

For the pilot, the blueprint proposes double review of the first 20 responses in each major task family, then 25 percent of later responses. It also proposes a drift check every 50 responses or each major review session. Treat these as reviewable pilot settings, not code constants.

Any disagreement between `PASS` and `INCOMPLETE` requires resolution before a formal result is confirmed.

#### BP10 - Automated evaluator validation

Compare AI criterion decisions with trained human decisions. Test each task type, alternate response form, concise answer, unusual valid method, and relevant learner group. Check both false-pass and false-incomplete errors.

The old ordered-score ICC target does not fit a binary result. Report binary agreement with uncertainty and an approved statistic. A provisional planning target may use kappa of at least 0.70, with a stronger target near 0.90 for higher-stakes use. Governance must approve the final gate.

#### BP11 - Model and rule drift

Repeat validation after a material change to the model, prompt, retrieval, source, task, Bloom target, criteria, pass rule, or curriculum. Keep the old result tied to the old versions.

#### BP12 - Research readiness

Before pilot recruitment:

- Obtain the required ethics decision.
- Separate research consent from course access and results.
- Pre-register the main outcome, hypotheses, conditions, allocation, rules, exclusions, sample-size basis, missing-data plan, group analyses, and deviations.
- Blind outcome reviewers to research condition where practical.
- Report attrition, missingness, technical faults, and result uncertainty by condition.

#### BP13 - Data-purpose separation

Keep identity mapping, operational learning records, assessment records, preferences and access settings, and research data in distinct access layers. Pseudonymous learning traces are not anonymous.

#### BP14 - Retention and withdrawal

Implement retention, deletion, and research withdrawal from an approved data plan. Do not invent a universal retention period in code.

#### BP15 - Change control

Do not use a new evaluator, prompt, task form, criterion, or pass rule on an attempt that began under an older approved version. A version conflict requires review.

## 7. Required data model

The current SRS figure is not complete. Do not implement from that figure alone.

### 7.1 Identity and course data

- `User`
- `RoleAssignment`
- `Course`
- `Module`
- `Enrollment`
- `LearningMaterial`
- `MaterialVersion`
- `SourceChunk`
- `LearningOutcome`
- `OutcomeVersion`
- `OutcomePrerequisite`

### 7.2 Outcome and assessment design

- `OutcomeBlueprint`
- `BloomTarget`
- `EvidenceRule`
- `Criterion`
- `CriterionVersion`
- `TaskModel`
- `TaskForm`
- `TaskApproval`
- `AssessmentPolicy`
- `PermittedToolRule`
- `InstructionalSupportRule`
- `AccessCondition`
- `TransferRule`

### 7.3 Learning activity and evidence

- `Activity`
- `Task`
- `Submission`
- `ResponseVersion`
- `LearningEvidence`
- `ConfidenceRecord`
- `FeedbackInteraction`
- `SupportEvent`
- `ReflectionRecord`
- `SimulationRun`
- `TransferResult`
- `MisconceptionHypothesis`
- `MisconceptionEvidenceLink`

### 7.4 Learner state and decisions

- `LearnerPreference`
- `AccessibilityPreference`
- `AuthorisedAdjustmentReference`
- `LearnerModelSnapshot`
- `OutcomeEstimate`
- `AdaptationDecision`
- `LearnerOverride`
- `EducatorOverride`
- `Recommendation`

Do not store diagnosis details in the learner model. If an authorised adjustment needs a reference, store the minimum functional rule and access scope.

### 7.5 Assessment decisions

- `AssessmentAttempt`
- `CriterionEvaluation`
- `AssessmentDecision`
- `AssessorReview`
- `ReassessmentLink`
- `AppealOrCorrection`

`AssessmentDecision` must store both `result` and `result_state`. It also needs the Bloom target version, rule version, evidence links, system reason, assessor, override reason, and time.

### 7.6 AI, audit, and operations

- `AgentRun`
- `AgentCall`
- `QualityReview`
- `RetrievalRun`
- `ModelConfiguration`
- `PromptVersion`
- `AuditEvent`
- `Reminder`
- `GamificationRecord`
- `FailureEvent`
- `FallbackEvent`
- `BackupVerification`

### 7.7 Research data

- `ResearchParticipantMap`
- `ResearchConsentState`
- `ResearchWithdrawal`
- `ExperimentalCondition`
- `ResearchEvent`
- `ResearchExportJob`
- `MissingDataReason`

Operational identity data must be separate from research IDs. Experimental condition and research demographics must not feed production adaptation or assessment.

### 7.8 Data rules

Every record must follow these rules where applicable:

- Use a stable unique ID.
- Store `created_at`, `updated_at`, and the responsible actor or agent.
- Store course scope and enforce it in queries.
- Use foreign keys and transactions.
- Keep old evidence and decision versions.
- Use soft deletion or archive states for records with dependants.
- Keep direct evidence separate from model inference.
- Keep instructional support separate from access support.
- Keep assessment results separate from workflow state and progress state.
- Keep AI judge approval separate from learner assessment results.
- Record the source, model, prompt, rule, task, and rubric versions used.
- Use idempotency keys for submissions, agent callbacks, and result creation.

## 8. System and agent design

### 8.1 Required technical base

- React frontend with role-specific views.
- FastAPI backend with typed request and response models.
- SQLite for the MVP, with a clear move path to a managed relational database.
- Qiskit and Qiskit Aer for controlled circuit work.
- External LLM integration behind a provider-neutral interface.
- RAG and vector search for approved course material.
- Environment-based secrets and provider settings.
- HTTPS in hosted use.

### 8.2 Backend module boundaries

Keep these areas behind documented interfaces and independent tests:

- Authentication and role access.
- Courses, material, and outcomes.
- Retrieval and source grounding.
- Tasks and activity state.
- Evidence capture.
- Learner model.
- Misconception support.
- Adaptation and suggestions.
- Assessment rules and assessor review.
- Orchestration and shared state.
- Qiskit execution.
- Feedback and Quality Judge.
- Preferences, access conditions, and overrides.
- Progress and research export.
- Audit, privacy, fallback, and recovery.

These may share a service in the MVP. They do not each need a separate deployed service.

### 8.3 Agent responsibilities

#### Orchestration Agent

Manage shared state versions, call order, branching, retries, timeouts, conflict rules, fallbacks, escalation, and audit. It must not hide an unresolved conflict.

#### Learning Path Agent

Choose the next approved activity, format, pace, difficulty, and support. Explain the choice and allow override. It cannot change the assessed target or pass rule.

#### Tutor Agent

Use approved sources to explain concepts. Offer alternate forms and probing questions. Avoid giving the complete answer too early.

#### Circuit Agent

Select or create a circuit that matches the outcome, learner readiness, and task rule. Control complexity and create a text description from the same circuit object.

#### Simulation Agent

Run controlled Qiskit jobs, store settings and output, and help compare a prediction with evidence. Simulation output cannot replace learner reasoning.

#### Quiz Agent

Create approved task types, vary forms, collect reasoning where needed, check possible misconceptions, and issue transfer tasks.

#### Feedback Agent

Use the response, evidence, and support history. Give the least revealing useful cue, invite revision, and state the next action.

#### Learner Model and Evidence Agent

Append observations, create versioned inferences, retain uncertainty, and never diagnose or label the learner.

#### Assessment Evaluator

Apply the assessor-approved Bloom evidence rule. Return criterion evidence, missing evidence, a provisional `PASS` or `INCOMPLETE`, and a reason. It cannot invent a rule or finalise a formal result without the approved control.

#### Quality Judge

Check both educational quality and assessment-rule use. Reject unsupported, unsafe, inaccessible, biased, ungrounded, answer-revealing, or misaligned output.

## 9. Required workflows

### 9.1 Course setup

1. Educator creates a course and module.
2. Educator adds material.
3. The system validates, extracts, chunks, indexes, and reports any fault.
4. Educator creates outcomes and prerequisites.
5. For assessed outcomes, the assessor sets Bloom and evidence rules.
6. The system generates or stores task forms.
7. Educator reviews sources, task conditions, access modes, and criteria.
8. Educator publishes the course and approved tasks.

### 9.2 Continuous learning loop

1. Load the course, outcome, preferences, current model, and recent evidence.
2. Suggest an activity and explain why.
3. Let the learner accept or choose an allowed option.
4. Capture prior knowledge or a prediction where useful.
5. Give an approved explanation or activity.
6. Capture the initial response and reasoning.
7. Run simulation where needed.
8. Generate and check feedback.
9. Let the learner revise and reflect.
10. Use a fresh or transfer task where useful.
11. Append evidence and update the learner model.
12. Suggest the next action.
13. Store every important call and decision.

### 9.3 Assessment and pass/incomplete result

1. Confirm the task was declared assessed before it began.
2. Load the approved Bloom target and evidence-rule versions.
3. Check the attempt, tool, support, access, and independence conditions.
4. Evaluate each mandatory criterion from the learner response and allowed evidence.
5. Create a provisional `PASS` only if the full pass rule is met.
6. Otherwise create `INCOMPLETE` with missing criteria and a next action.
7. Run Quality Judge checks on the reason and evidence links.
8. Send the result for assessor review when formal.
9. Store confirmation, override, withholding, or void action.
10. Show the learner an accessible result explanation and review path.

### 9.4 Misconception support

1. Store an uncertain hypothesis, not a fact.
2. Link both supporting and contradicting evidence.
3. Ask a short check question in another form or context.
4. Rule out a slip, unclear task, missing prerequisite, language issue, or UI fault.
5. Give targeted support.
6. Let the learner revise.
7. Use a fresh or transfer check.
8. Record the new hypothesis state and educator action.

### 9.5 Failure and conflict handling

- Save accepted learner work before external calls.
- Use set timeouts and retry limits.
- Make retries idempotent.
- Use safe fallbacks after repeated AI failure.
- Keep the learner in a usable state after a simulation fault.
- Escalate important agent conflicts and repeated judge rejection.
- Never create a formal result from an incomplete or failed evaluator run.
- Log the correlation ID, versions, failure reason, retry, fallback, and final state.

## 10. Non-functional requirements

### NFR1 - Usability

Average user rating must be at least 7 out of 10 in the approved student and educator review.

### NFR2 - Educator setup time

Across at least five first-time trials, course creation, one resource upload, one outcome, and one generated task must take no more than 20 minutes.

### NFR3 - Student learnability

At least 80 percent of first-time student testers must sign in, open a task, submit it, and find feedback without help within 15 minutes.

### NFR4 - Accessibility

All key student, educator, assessor, and admin paths must meet WCAG 2.2 AA. Test keyboard use, focus, screen reader flow, labels, errors, contrast, zoom, reflow, and equivalent circuit or result text. Release with no open critical access fault.

### NFR5 - Reliability

Scripted tests must lose or duplicate zero accepted records. The app must return to a usable state after a forced restart.

### NFR6 - Availability

Hosted service target is at least 99.5 percent each calendar month, excluding announced maintenance.

### NFR7 - Performance

With 50 concurrent users:

- Ordinary request p95 is at most 2 seconds.
- Progress page p95 is at most 3 seconds.
- AI feedback p95 is at most 10 seconds.
- Error rate is below 1 percent.

Add a separate target for assessment evaluation if it uses an LLM. Do not hide a longer assessment wait under the ordinary request target.

### NFR8 - Scale

From 5 to 100 concurrent users, keep errors below 1 percent. Ordinary request p95 may rise by no more than 25 percent.

### NFR9 - Modularity

Every module in Section 8.2 needs a documented interface and an independent test entry point.

### NFR10 - Maintainability

Before release:

- Formatting, lint, type, and static checks report zero errors.
- No open critical or high security or quality finding remains.
- Backend service statement coverage is at least 80 percent.
- Generated files, migrations, and tests may be excluded only by written rule.
- Every suppression has a reason and owner.

### NFR11 - Extensibility

A developer must add one demo task type through the extension interface without changing current task-type implementations.

### NFR12 - Accuracy

Across at least 100 educator-approved quantum cases, at least 80 percent of generated tasks, feedback, and evaluations must be factually correct. Hallucination rate must be no more than 5 percent.

### NFR13 - Feedback quality

Educator review average must be at least 4 out of 5 for accuracy, clarity, relevance, useful action, outcome fit, and suitable support. At least 80 percent of sampled incomplete responses must get a clear next action and revision chance.

### NFR14 - AI validation

The judge must reject at least 80 percent of deliberately flawed samples and falsely reject no more than 20 percent of correct samples.

### NFR15 - Security

Pass all protected-route tests. Hash credentials, encrypt network traffic, protect secrets, validate uploads, limit circuit work, and release with no open critical or high security finding.

### NFR16 - Privacy

Operational logs must exclude direct student IDs and unneeded answer text. Store learning text only in authorised learning records. Use course scope, least privilege, approved export fields, and minimal learner-model retention.

### NFR17 - Data integrity

Use database rules to block invalid links. Concurrent submissions must create a consistent attempt order. Restore testing must reproduce 100 percent of the verification records.

### NFR18 - Browser support

Run key paths on the latest test-time versions of Chrome, Edge, Firefox, and Safari.

### NFR19 - Portability

The same deployment package and tests must work locally and in one hosted setup by configuration change only.

### NFR20 - Auditability

Important actions must create an audit event with actor or agent, action, time, result, correlation ID, and model or rule version.

Include sign-in, course change, task generation, submission, feedback, model update, misconception state, adaptation, learner choice, educator or assessor override, provisional result, final result, retry, and fallback.

### NFR21 - Ethical AI use

Mark AI-generated content, show sources where useful, and give a report control. Approved safety tests must produce no abusive, biased, harmful, diagnostic, or unsupported learner claim.

### NFR22 - Cost

Average external LLM cost must not exceed AUD 0.10 per full learning loop. An administrator must change provider or model without source changes. Track cost by agent and feature.

### NFR23 - Robustness

Invalid input, missing source, incomplete response, timeout, bad model output, simulation fault, and external failure tests must end without an unhandled error, app crash, or accepted-data loss.

### NFR24 - Reuse

The SRS phrase "within a few days" is not testable. Proposed release gate: configure and run one demo module for a second technical subject within 16 developer-hours, without changing the core evidence, learner-model, adaptation, or assessment engine. The team must approve or replace this number.

### NFR25 - Research support

Export each approved learning sequence as CSV or JSON under a pseudonymous ID. Include condition, stage, outcome, evidence, model references, adaptations, overrides, sources, AI output, judge result, simulation, latency, tokens, and cost. Required fields must be present in all included sample records, subject to withdrawal and missing-data rules.

### NFR26 - Clear and predictable learning design

Use clear instructions, stable layout, small steps, low visual clutter, flexible pace, optional breaks, and consistent navigation. Apply Universal Design for Learning without assigning fixed learning styles.

### NFR27 - Learner-model safety

Every important inference needs evidence and uncertainty. Users must tell evidence from inference.

### NFR28 - Pedagogical judge coverage

Test flawed outputs for bad support, unclear language, access faults, bias, unsupported learner claims, answer leakage, missing reflection, and weak support for independent work. Reject at least 80 percent.

### NFR29 - Adaptation explanation

For every sampled important adaptation, an authorised reviewer must retrieve its evidence, reason, uncertainty, agent, model, learner response, and override history.

### NFR30 - Research data completeness

For all pilot participants included in final analysis, store the condition and all required available pre, in-process, post, learner-experience, and educator-review records, subject to approved withdrawal and missing-data rules.

### NFR31 - Non-diagnostic adaptation

Never infer or store diagnostic, disability, medical, psychological, demographic, or neurodivergence status in the learner model. Adapt only from observed learning evidence, explicit preferences, learner choices, and authorised educator action.

## 11. Acceptance criteria

### AC1 - Secure access

All sign-in, role, course-scope, record-ownership, and admin denial tests pass. Audit logs contain no banned personal data.

### AC2 - Course and content setup

An educator can create, save, publish, reopen, and archive a course with a valid resource and outcome. Invalid files and links return clear errors without partial records.

### AC3 - AI-assisted tasks

The system creates grounded, source-linked, outcome-linked tasks for all required types. Each assessed task includes an approved Bloom target and evidence rule.

### AC4 - Checked feedback

Only judge-approved feedback reaches the learner. Two rejected attempts produce a safe fallback and an audit trail.

### AC5 - Student learning and control

A student can complete the full learning path, use allowed options, repeat formative work without penalty, view evidence and reasons, and see only `PASS` or `INCOMPLETE` for assessed work.

### AC6 - Analytics and privacy

Students see only their data. Educators see assigned courses. Views separate evidence, inference, results, and research measures. Approved exports are pseudonymous.

### AC7 - Admin controls

Only administrators can complete admin actions. Every action creates an audit event.

### AC8 - End-to-end loop

The full workflow in FR28 finishes without lost work, broken links, an unhandled error, or a missing audit record.

### AC9 - System quality

All applicable NFR release gates pass with saved evidence. A build or HTTP 200 response alone is not enough.

### AC10 - Research export

An approved export contains the set condition, evidence stages, sources, model and prompt versions, judge results, simulation, latency, tokens, cost, and withdrawal handling.

### AC11 - Visible learning change

A complete journey shows initial thinking, reasoning, confidence where used, attempt, feedback, revision, reflection, transfer, and model update. It does not rely on one final result.

### AC12 - Evidence-based adaptation

Different seeded evidence causes a justified change in at least one allowed support area. The reason, uncertainty, versions, and override controls are visible. The target assessment standard stays fixed.

### AC13 - Misconception check

A seeded possible misconception follows the hypothesis, check, support, revision, transfer, and state-update flow.

### AC14 - Inclusive learner control

The learner can change allowed pace, format, feedback, and support. They can repeat formative work and request a prior-mastery check without penalty.

### AC15 - Safe learner model

Every sampled important inference has evidence and uncertainty. The safety set contains no diagnosis, protected stereotype, or unsupported fixed-ability claim.

### AC16 - Educator and assessor control

An authorised user can inspect evidence, approve tasks, correct a misconception, change an adaptation, set Bloom and evidence rules, and confirm or override a result. Every change is audited.

### AC17 - Accessible key paths

Course setup, learning, simulation, feedback, assessment result, and review paths pass WCAG 2.2 AA checks. Circuit and result evidence works by keyboard and screen reader.

### AC18 - Pilot evidence

The pilot captures approved pre, in-process, post, learner-experience, and educator-review data. The learning comparison and technical LLM comparison remain separate.

### AC19 - Binary result enforcement

Database constraints, API schemas, UI controls, exports, and tests accept only `PASS` and `INCOMPLETE` as assessment results. Numeric marks and `FAIL` are rejected or migrated.

### AC20 - Bloom target evaluation

An assessor can set a Bloom target and outcome-specific evidence criteria. The system returns `PASS` only when all approved mandatory rules are met. The same response returns the same result under the same versioned rule.

### AC21 - Incomplete recovery

An incomplete result identifies missing criteria, gives a suitable next action, and follows the approved reassessment rule. It does not average old formative work into a later decision.

### AC22 - Consequential review

A formal result cannot reach `CONFIRMED` without an authorised assessor action. Overrides and void actions need a reason and retain the old decision.

## 12. Source conflicts resolved by this specification

### 12.1 Score references

SRS references to scores in FR19, FR21, user permissions, stories, and acceptance text now mean binary assessment results plus separate learning evidence. Do not add numeric learner marks.

### 12.2 Blueprint numeric grading

The blueprint's future numeric model, 0 to 3 rubric total, 75 percent threshold, criterion weights, course mark, grade bands, and score replacement rules are not part of this build.

The useful parts remain:

- Outcome and evidence alignment.
- Assessor-set Bloom target.
- Clear evidence rules.
- Supported versus independent evidence.
- Access support kept separate from instruction.
- Human control, moderation, audit, and review rights.

### 12.3 Progress states

Terms such as `DEVELOPING`, `SUPPORTED_PROFICIENCY`, or `INDEPENDENT_MASTERY` may exist as learner-model states. They must not appear as formal assessment results.

### 12.4 Gamification points

Points, levels, or badges may exist only as optional engagement data. They cannot set, change, predict, or display a formal result.

### 12.5 Bloom use

Bloom describes the cognitive process the task asks the learner to show. It is not a numeric ladder and does not prove task difficulty. The assessor must define observable evidence for the chosen level.

## 13. Decisions still needed before a live pilot

Codex must expose these as settings or tracked decisions. It must not invent hidden defaults.

- Which users may hold assessor permission.
- Whether a provisional system result is shown before assessor review.
- How many independent observations an outcome needs.
- Which assessment results allow reassessment.
- Whether the latest valid attempt replaces the earlier result.
- Which criteria are mandatory for each outcome.
- What access and tool conditions apply to each task.
- Which actions trigger required human review.
- How long learning, assessment, audit, and research records are kept.
- How consent, withdrawal, and missing data work in the pilot.
- The approved 16-hour reuse target in NFR24.
- The assessment evaluator accuracy and fairness release thresholds.
- The final escalation owner and service target.

Until these are approved, use safe settings: formal results need assessor confirmation, incomplete work may be retried through an approved new attempt, and no automated decision is final.
