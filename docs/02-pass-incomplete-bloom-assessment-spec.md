# Pass/incomplete and Bloom assessment specification

Status: controlling assessment specification

Last updated: 2026-08-14

## 1. Decision in one sentence

The assessor chooses the target Bloom process and approves what evidence will prove it. LearnLens checks that evidence and returns only `PASS` or `INCOMPLETE`.

## 2. Rules that cannot be changed by implementation detail

1. `PASS` and `INCOMPLETE` are the only assessment result values.
2. The word `FAIL` must not be shown as an assessment result.
3. A failed rule check maps to `INCOMPLETE`.
4. Do not calculate or display marks, percentages, weighted totals, grade bands, or GPA values.
5. The assessor sets the target Bloom process before the learner begins.
6. The target is linked to an approved learning outcome, task form, evidence rule, and version.
7. The same assessment standard applies to all learners assigned to that assessment.
8. Approved access support may change how evidence is given. It must not lower the target.
9. Formative support and practice do not directly set a formal result.
10. The system may create a provisional result. An assessor controls a formal confirmed result.
11. Learners can see the target, criteria, result reason, missing evidence, and review path.
12. Every decision must be repeatable from saved evidence and saved rule versions.

## 3. Why a Bloom label is not enough

Bloom classifies the cognitive process required by a task. It does not provide a marking rule.

For example, an assessor may choose `ANALYSE`. The system still needs to know:

- What the learner must analyse.
- Which parts or relations must be found.
- What counts as valid evidence.
- Which errors are critical.
- Which tools and supports are allowed.
- Whether a new context or transfer is required.
- What makes the response complete enough to pass.

LearnLens must never ask an LLM, "What Bloom level is this student?" and use that answer as the grade. The correct question is, "Does this response meet the assessor-approved evidence rule for the target Bloom process?"

## 4. Assessment unit and result levels

### 4.1 Attempt result

An attempt result applies to one valid submission under one task-form version.

```text
AttemptResult = PASS | INCOMPLETE
```

An attempt can pass when it meets every mandatory rule for that task. It does not need a numeric score.

### 4.2 Outcome result

An outcome result combines the approved evidence for one learning outcome.

```text
OutcomeResult = PASS | INCOMPLETE
```

The assessor defines the evidence-sufficiency rule. Examples include:

- One approved multi-part assessment that samples all required evidence.
- Two independent task forms.
- One target-level task plus one transfer task.
- A required practical task and a required explanation task.

The system must not average attempts. It evaluates the stated Boolean rule.

### 4.3 Course result

If a course-level binary result is needed, define required outcomes in advance.

```text
CourseResult = PASS if every required outcome is PASS
CourseResult = INCOMPLETE otherwise
```

Do not use an average, compensation rule, or hidden weighting unless the product decision changes through formal approval.

## 5. Bloom target model

### 5.1 Revised Bloom process

| Value | What the learner must do | Useful evidence | Quantum example |
| --- | --- | --- | --- |
| `REMEMBER` | Retrieve or recognise accurate facts, terms, or symbols. | Correct recall or recognition without a cue that gives the answer. | Identify gate notation or define a basis state. |
| `UNDERSTAND` | Explain, predict, compare, classify, or represent meaning. | Accurate links between ideas, a prediction with reasons, or an equivalent representation. | Explain a Hadamard measurement distribution. |
| `APPLY` | Select and use a known method in a suitable case. | Correct method choice and execution under stated conditions. | Modify and run a familiar single-qubit circuit. |
| `ANALYSE` | Break a problem into parts and explain relations or causes. | Valid fault location, relation mapping, or cause analysis. | Find the conceptual cause of an unexpected result. |
| `EVALUATE` | Judge options against stated criteria and justify the judgement. | Criterion-based comparison with evidence and a defended choice. | Compare two circuits for accuracy and efficiency. |
| `CREATE` | Design, test, revise, and defend a solution under constraints. | A valid new artefact plus design reasons, test evidence, and revision. | Design a circuit for a new target behaviour. |

### 5.2 Knowledge dimension

Store one or more approved knowledge dimensions:

- `FACTUAL`: terms, symbols, and details.
- `CONCEPTUAL`: principles, models, and relations.
- `PROCEDURAL`: methods and when to use them.
- `METACOGNITIVE`: strategy choice and self-monitoring when this is an outcome.

The process and knowledge values must not be collapsed into one string.

### 5.3 Bloom safeguards

- A higher Bloom label does not automatically mean a harder or better task.
- A task verb does not prove the task's actual process.
- A high-level task may need lower-level knowledge, but the pass rule must say which parts are required.
- A learner cannot pass an `ANALYSE` target by only recalling correct facts.
- Generative AI use does not become safe merely because the task uses `CREATE` or `EVALUATE`.
- Task validity must be reviewed when the prompt, form, source, model, or criteria change.

## 6. Assessor setup requirements

An assessed task cannot be published until all required fields pass validation.

### 6.1 Outcome fields

| Field | Required rule |
| --- | --- |
| Outcome ID | Stable ID, unique within the course. |
| Learner wording | Clear statement shown before assessment. |
| Owner | Authorised educator or assessor. |
| Source | Approved course source and version. |
| Prerequisites | Required outcomes and any approved bypass rule. |
| Bloom process | One target process chosen by the assessor. |
| Knowledge dimension | At least one approved dimension. |
| Claim | Exact knowledge, reasoning, or skill to infer. |
| Supporting evidence | Observable features that support achievement. |
| Contradicting evidence | Features that show a critical gap or conflict. |
| Insufficient evidence | Cases that cannot support a decision. |
| Task model | Task family, context, form, and constraints. |
| Purpose | Must state if the task is assessed. |
| Pass rule | Versioned Boolean rule over mandatory criteria. |
| Support rule | Allowed instructional support and its effect. |
| Access rule | Equivalent modes and approved adjustments. |
| Tool rule | Allowed calculator, Qiskit, notes, code, or AI use. |
| Transfer rule | What changes in a transfer form, if required. |
| Decision authority | Provisional system result and required assessor action. |

### 6.2 Criterion fields

Each criterion must contain:

- Stable criterion ID.
- Learner-facing description.
- Assessor-facing evidence description.
- Link to the outcome claim and Bloom process.
- `mandatory` Boolean.
- Evidence source types that may satisfy it.
- Clear `MET`, `NOT_MET`, and `NOT_EVALUABLE` rules.
- Examples or anchors approved by the assessor.
- Critical error rules, if any.
- Allowed evaluator type: rules, human, validated AI, or mixed.
- Version, approval state, owner, and date.

Do not add points or weights to criteria.

### 6.3 Pass rule examples

Simple rule:

```text
PASS when every mandatory criterion is MET.
INCOMPLETE otherwise.
```

Rule with allowed optional evidence:

```text
PASS when:
  conceptual_explanation is MET
  AND target_bloom_action is MET
  AND critical_error is absent
  AND at least one of [simulation_interpretation, valid_alternate_evidence] is MET
INCOMPLETE otherwise.
```

Outcome rule with more than one task:

```text
PASS when:
  approved_target_task is PASS
  AND approved_transfer_task is PASS
  AND no unresolved evidence conflict exists
INCOMPLETE otherwise.
```

The rules engine must use a stored rule document or typed expression. Do not hide the rule inside a prompt.

## 7. Task design requirements by Bloom target

### 7.1 Remember

The task must require recall or recognition without an answer-revealing cue. Distractors must be plausible and reviewed. A matching task must not expose the answer through position or formatting.

Minimum pass evidence:

- Every mandatory fact or symbol is accurate.
- No critical confusion is present.
- The response comes from an allowed condition.

### 7.2 Understand

The task must require meaning, not copied wording. Use explanation, prediction, comparison, classification, or representation.

Minimum pass evidence:

- The central concept is accurate.
- The learner links cause, rule, or relation to the result.
- Any required prediction matches the reasoning, not just the final output.
- The response is not a copied model answer when independent work is required.

### 7.3 Apply

The task must require method selection and use. It should not tell the learner every step if independent application is the target.

Minimum pass evidence:

- The selected method fits the case.
- The method is carried out correctly enough to meet the outcome.
- The learner can explain the key choice when reasoning is part of the outcome.
- Critical syntax or circuit faults are absent.

### 7.4 Analyse

The task must contain parts, evidence, or relations that need inspection. It must not reduce to simple recall.

Minimum pass evidence:

- Relevant parts or variables are identified.
- Their relations or causal role are explained.
- The learner distinguishes the root cause from a surface symptom.
- The conclusion follows from the supplied or generated evidence.

### 7.5 Evaluate

The assessor must publish the judgement criteria. The task must offer a real choice or claim to assess.

Minimum pass evidence:

- The learner applies the approved criteria.
- The judgement uses task evidence.
- Trade-offs or limits are addressed where required.
- The conclusion is justified and internally consistent.

### 7.6 Create

The task must define a goal, constraints, and test conditions. A finished artefact alone is not enough.

Minimum pass evidence:

- The design meets mandatory constraints.
- The learner explains key choices.
- The artefact is tested with suitable evidence.
- Relevant faults are revised or defended.
- The result is the learner's valid work under the declared tool rule.

## 8. Evidence policy

### 8.1 Evidence that may support a result

- The submitted answer, explanation, code, or circuit.
- Reasoning required by the published outcome.
- Approved simulation output linked to the learner's response.
- Criterion evaluations and assessor notes.
- A fresh independent task.
- A transfer task when the outcome requires it.
- A valid reassessment under the same standard.

### 8.2 Evidence used for learning but not direct grading

- Confidence rating.
- Time taken, pauses, or breaks.
- Number of attempts.
- Hint use.
- Formative feedback use.
- Learner preference or format choice.
- Gamification points or badges.
- Research condition or consent.
- Learner-model probability or mastery estimate.

These may guide the next task. They cannot lower `PASS` or change it to `INCOMPLETE`.

### 8.3 Supported and independent evidence

Record instructional support separately:

| Level | Support | Result use |
| --- | --- | --- |
| `0` | No answer-revealing instruction. | May support independent evidence. |
| `1` | Goal reminder, self-check, or discrepancy prompt. | Use only if the task rule allows it. |
| `2` | Concept cue without the solution path. | Supported evidence. A fresh task may be needed. |
| `3` | Hint that narrows the solution path. | Supported evidence only. Use a fresh task for independence. |
| `4` | Partial worked step. | Learning evidence only. |
| `5` | Full worked example or direct answer. | Instruction only, not pass evidence for that item. |

The assessor may simplify this scale, but the stored rule must remain explicit.

### 8.4 Accessibility support

Access support is not instructional support. Examples include:

- Keyboard access instead of drag and drop.
- A semantic circuit description from the same circuit object.
- A data table for a histogram.
- Screen reader labels.
- Extra time or breaks under an approved plan.
- An equivalent response mode that keeps the same construct.

These must not increase the instructional-support level or lower the result.

### 8.5 Invalid evidence

Do not issue `INCOMPLETE` for a system-caused invalid attempt. Mark the attempt `VOID` or keep it `UNDER_REVIEW` and allow a fair new attempt.

Examples include:

- A broken or ambiguous task.
- Missing source data.
- A simulation fault that changes required evidence.
- Lost accepted work.
- A model timeout before evaluation completes.
- An access mode that does not preserve the target construct.
- A task-form version mismatch.

## 9. Evaluation flow

### 9.1 Required steps

1. Load the submission and exact response version.
2. Load the approved task, outcome, Bloom target, criteria, and pass-rule versions.
3. Confirm the task was designated as assessed before the start time.
4. Confirm the learner was assigned the task.
5. Check task validity, response completeness, permitted tools, support, and access conditions.
6. Gather only approved evidence sources.
7. Evaluate each criterion as `MET`, `NOT_MET`, or `NOT_EVALUABLE`.
8. Store evidence quotes or structured evidence, not just a label.
9. Run the deterministic pass rule.
10. Create a provisional `PASS` or `INCOMPLETE` with reason codes.
11. Run a Quality Judge check on grounding, criteria use, explanation, and bias.
12. Send formal results to an authorised assessor.
13. Store the assessor action and show the learner the allowed detail.

### 9.2 Normative decision logic

```text
if task_is_invalid or evaluator_did_not_complete:
    do not issue an assessment result
    keep UNDER_REVIEW or mark the attempt VOID
    provide a fair retry or human review

else if any mandatory criterion is NOT_EVALUABLE:
    provisional result = INCOMPLETE
    reason = MISSING_REQUIRED_EVIDENCE

else if every mandatory pass-rule clause is true:
    provisional result = PASS
    reason = TARGET_EVIDENCE_MET

else:
    provisional result = INCOMPLETE
    reason = CRITERIA_NOT_MET

if the result is formal:
    require authorised assessor confirmation or override
```

### 9.3 Result reason codes

Use stable, learner-safe reason codes.

```text
TARGET_EVIDENCE_MET
MISSING_REQUIRED_EVIDENCE
CRITERIA_NOT_MET
TARGET_BLOOM_ACTION_NOT_SHOWN
CRITICAL_CONCEPT_GAP
INDEPENDENT_EVIDENCE_NOT_SHOWN
TRANSFER_EVIDENCE_NOT_SHOWN
UNRESOLVED_EVIDENCE_CONFLICT
TASK_UNDER_HUMAN_REVIEW
```

System fault codes belong to the attempt or failure record, not the learner result.

## 10. Feedback rules

### 10.1 Pass feedback

A pass explanation must:

- State `PASS`.
- Name the outcome and target Bloom process.
- List the evidence that met each mandatory criterion.
- Avoid a numeric mark.
- State whether the result is provisional or confirmed.
- Give an optional next learning action that does not change the result.

Example:

```text
Result: PASS
Target: Analyse
Why: You identified the incorrect measurement assumption, linked it to the observed counts, and explained why the corrected circuit changes the distribution. All required criteria were met.
Status: Confirmed by the assessor.
```

### 10.2 Incomplete feedback

An incomplete explanation must:

- State `INCOMPLETE`.
- Avoid the word `fail` in learner-facing text.
- List criteria already shown.
- List missing or conflicting evidence.
- Give the next permitted action.
- State whether a new attempt, revision, transfer task, or assessor review is needed.
- Avoid revealing the full answer when the learner will try again.

Example:

```text
Result: INCOMPLETE
Target: Analyse
What is shown: You identified that the output distribution is unexpected.
What is still needed: Explain the conceptual cause and link it to the gate order.
Next step: Review the circuit states, then submit a new explanation for the fresh task.
```

### 10.3 Feedback safety

Feedback must not:

- Add marks or percentages.
- Infer motivation, ability, diagnosis, or learning style.
- Penalise low confidence, time, attempts, or access support.
- Claim a Bloom level that the assessor did not set.
- Hide missing evidence or rule conflicts.
- Reveal a complete reassessment answer.

## 11. Human review and decision rights

### 11.1 System actions

The system may:

- Check typed and rule-based criteria.
- Ask a validated AI evaluator for criterion evidence.
- Apply the stored Boolean pass rule.
- Create a provisional result.
- Flag conflicts, low evaluator confidence, or unusual answers.
- Suggest feedback and reassessment actions.

### 11.2 Assessor actions

Only an authorised assessor may:

- Approve the Bloom target and pass rule.
- Confirm a formal result.
- Override a provisional result.
- Void a faulty attempt.
- Approve a reassessment or alternate form.
- Resolve conflicting evidence.
- Decide an appeal or correction under course policy.

### 11.3 Required human-review triggers

Human review is required when:

- The evaluator returns `NOT_EVALUABLE` on a mandatory criterion.
- A result conflicts with another valid assessor decision.
- The task, source, rule, model, or prompt version changed mid-attempt.
- The AI evaluator confidence is below the approved task threshold.
- The answer is correct but uses an unusual valid method.
- The task may be ambiguous, inaccessible, or faulty.
- Academic-integrity action is considered.
- A learner requests review.
- A formal result is ready for confirmation.

## 12. Data contracts

Names may be adapted to the current code. The meaning and constraints must remain.

### 12.1 Assessment definition

```json
{
  "assessment_id": "asm_123",
  "course_id": "course_123",
  "outcome_id": "outcome_123",
  "purpose": "SUMMATIVE",
  "bloom_target": {
    "process": "ANALYSE",
    "knowledge_dimensions": ["CONCEPTUAL", "PROCEDURAL"],
    "rationale": "The learner must locate and explain the cause of a circuit error."
  },
  "task_form_version": "3",
  "criteria_version": "5",
  "pass_rule_version": "2",
  "permitted_tools": ["QISKIT_SIMULATOR"],
  "max_instructional_support_level": 1,
  "assessor_id": "user_456",
  "approval_state": "APPROVED"
}
```

### 12.2 Criterion evaluation

```json
{
  "criterion_id": "crit_root_cause",
  "decision": "MET",
  "evidence_refs": ["evidence_801", "response_span_14"],
  "reason": "The response links gate order to the changed measurement distribution.",
  "evaluator_type": "AI_ADVISORY",
  "evaluator_version": "assessment-evaluator-7",
  "confidence": 0.91
}
```

`confidence` belongs to evaluator quality. It is not a learner mark.

### 12.3 Assessment decision

```json
{
  "decision_id": "decision_901",
  "attempt_id": "attempt_701",
  "result": "PASS",
  "result_state": "PROVISIONAL",
  "reason_code": "TARGET_EVIDENCE_MET",
  "bloom_process": "ANALYSE",
  "criterion_evaluation_ids": ["eval_1", "eval_2", "eval_3"],
  "pass_rule_version": "2",
  "system_decided_at": "2026-08-14T10:00:00Z",
  "assessor_review": null
}
```

### 12.4 Assessor confirmation

```json
{
  "decision_id": "decision_901",
  "action": "CONFIRM",
  "confirmed_result": "PASS",
  "reason": "The saved evidence meets every mandatory criterion.",
  "assessor_id": "user_456",
  "reviewed_at": "2026-08-14T10:20:00Z"
}
```

### 12.5 Database constraints

Enforce at least:

- Result is `PASS` or `INCOMPLETE` when present.
- A confirmed result has an assessor and review time.
- An override has the earlier decision, new result, assessor, and reason.
- An approved assessment has a Bloom target and pass-rule version.
- A task cannot change its approved rule after an attempt starts.
- A decision references the exact response version.
- A learner cannot access another learner's decision.
- A research export cannot contain a direct learner ID.
- Numeric score, mark, percentage, and grade-band columns are not used for formal results.

## 13. API behaviour

Use current project routes if they exist. The API must support these actions.

### 13.1 Assessor actions

- Create or update an outcome blueprint.
- Set a Bloom target.
- Add and version criteria.
- Add and version a pass rule.
- Approve a task form.
- Publish an assessment.
- Review evidence and a provisional result.
- Confirm, override, withhold, or void a decision.
- Approve a reassessment.

### 13.2 Student actions

- Read the assigned target, criteria, conditions, and allowed tools.
- Start one valid attempt.
- Save drafts with version checks.
- Submit once through an idempotent request.
- Read provisional or confirmed result detail allowed by policy.
- Read feedback and next action.
- Request review.
- Start an approved reassessment.

### 13.3 API error rules

- Use `403` for denied role or course scope.
- Use `404` without leaking whether another learner's record exists.
- Use `409` for stale versions, duplicate finalisation, or a changed task rule.
- Use `422` for invalid Bloom, criteria, or result payloads.
- Use a safe `5xx` response for system failure and retain accepted work.
- Never return stack traces, prompts, secrets, or another learner's data.

## 14. User interface requirements

### 14.1 Assessor setup view

Show:

- Outcome and source.
- Bloom process selector.
- Knowledge-dimension selector.
- Claim and evidence fields.
- Mandatory criteria editor.
- Pass-rule preview in plain language.
- Tool, support, access, and transfer settings.
- Task-form preview.
- Validation faults before approval.
- Version and approval history.

The UI must warn that Bloom is not a score. It must block publication when the target and task do not align.

### 14.2 Assessor review queue

Show:

- Learner and course within authorised scope.
- Outcome, task, target Bloom process, and versions.
- Original response and evidence.
- Criterion-by-criterion system evaluation.
- Missing or conflicting evidence.
- Provisional `PASS` or `INCOMPLETE`.
- Model and Quality Judge details.
- Confirm, override, void, and return controls.
- Required reason field for override or void.

### 14.3 Student task view

Before the attempt, show:

- Outcome wording.
- Target Bloom process in plain language.
- What evidence is required.
- Allowed tools and support.
- Assessment purpose.
- Whether the result needs assessor review.

Do not expose hidden answer keys or evaluator prompts.

### 14.4 Student result view

Show:

- `PASS` or `INCOMPLETE` only.
- Provisional or confirmed state.
- Criteria met.
- Criteria still needed.
- Evidence used.
- Next permitted action.
- Assessor note when allowed.
- Review or correction control.

Use text, icon, and accessible status semantics. Do not rely on red or green alone.

### 14.5 Progress views

Keep four areas distinct:

- Activity completion.
- Learning evidence and feedback.
- Learner-model estimates with uncertainty.
- Formal binary results.

No chart may convert `PASS` and `INCOMPLETE` into a fake average score.

## 15. Reassessment

### 15.1 Default rule

An `INCOMPLETE` result should lead to an approved next chance where course policy allows it.

The new attempt must:

- Use the same outcome and target standard.
- Use an approved new or equivalent task form.
- Keep prior evidence and decisions.
- Avoid copying the full earlier answer.
- Record whether the attempt is a revision or fresh reassessment.
- Produce a new decision linked to the earlier one.

### 15.2 Result replacement

Do not average attempts. The assessor must choose one published rule:

- Latest valid evidence controls the current result.
- Any valid pass completes the outcome.
- A fixed set of required task forms must all pass.

Store the selected rule in the assessment policy. The safe pilot default is that a later valid `PASS` becomes the current result while the earlier `INCOMPLETE` remains in history.

## 16. Academic integrity

- State allowed AI and tool use before the task.
- Record declared tool use where required.
- Use fresh, contextual, or oral follow-up only when approved and proportionate.
- Treat copied-looking work as a review signal, not automatic proof.
- Do not let the assessment evaluator impose an integrity penalty.
- Only an authorised human may make a formal integrity decision.
- Keep integrity evidence and appeal rights separate from the pass rule.

## 17. AI evaluator release gate

Until this gate passes, AI criterion decisions remain advisory.

Required proof:

- Agreement with trained human assessors by task type.
- Human inter-rater reliability baseline.
- Tests for concise, unusual, non-standard, and alternate-format correct answers.
- Tests showing answer length, writing style, and formatting do not drive the result.
- Tests across approved access and response modes.
- False-pass and false-incomplete analysis.
- Review of group error patterns where lawful and supported by enough data.
- Task-specific human-review triggers.
- Revalidation after task, source, prompt, model, criteria, retrieval, or curriculum change.

Do not use the SRS Quality Judge threshold alone as proof that automated assessment is valid.

## 18. Audit and privacy

Each result audit record must include:

- Learner, course, outcome, assessment, task, and attempt IDs.
- Exact task form and source versions.
- Bloom target and knowledge dimensions.
- Assessment purpose and result eligibility.
- Tool, instructional support, and access conditions.
- Original response version and evidence links.
- Criterion evaluations and evaluator reasons.
- Model, prompt, retrieval, rule, and criteria versions.
- Provisional result and reason code.
- Quality Judge result.
- Assessor action and reason.
- Learner notice, review, correction, or appeal action.
- Correlation ID and timestamps.

Operational logs should use internal or pseudonymous IDs and avoid full answer text. Rich assessment records remain protected learning records, not general logs.

## 19. Migration from a numeric or pass/fail implementation

Codex must inspect the current code before migration.

### 19.1 Find every conflicting field and label

Search for:

- `score`, `mark`, `grade`, `percentage`, `points`, `band`, and `GPA`.
- `pass`, `fail`, `failed`, `failure`, and Boolean grade fields.
- Numeric rubric weights and totals.
- Progress charts that average learner results.
- CSV or JSON exports with numeric marks.
- LLM prompts that ask for a score or grade.
- Tests and fixtures that expect numeric output.

### 19.2 Classify each use

Keep non-assessment uses only when clearly named:

- Qiskit counts and probabilities.
- Confidence values.
- Model uncertainty.
- Quality metrics.
- Research measures.
- Optional gamification points.

These fields must not be called learner grades.

### 19.3 Database migration

1. Add typed result and lifecycle columns.
2. Add Bloom, criteria, pass-rule, and evidence links.
3. Map old learner-facing pass values to `PASS` only when the old rule is valid and auditable.
4. Map old fail values to `INCOMPLETE`, with `migration_reason` and the old value retained in a protected history field.
5. Do not infer `PASS` from a numeric threshold unless an assessor approves that mapping.
6. Remove or deprecate formal numeric grade columns after read-path migration.
7. Add database checks and API enum validation.
8. Backfill audit events for changed records.
9. Run rollback and record-count checks.

### 19.4 UI and API migration

- Replace learner-facing `Fail` with `Incomplete`.
- Remove numeric grade controls and charts.
- Keep progress and evidence displays.
- Version API changes or add a compatibility adapter.
- Reject new numeric formal-result writes.
- Update exports and tests before deleting old fields.

## 20. Required acceptance tests

### AT1 - Allowed results

Given any result write, when the value is not `PASS` or `INCOMPLETE`, the API and database reject it.

### AT2 - Fail mapping

Given an old `FAIL` record, when migration runs, the public result becomes `INCOMPLETE` and the old value remains in migration history.

### AT3 - No numeric grade

Given an assessed learner view or export, when it loads, no mark, percentage, weight, grade band, or GPA field is present.

### AT4 - Bloom required

Given an assessed task without a target Bloom process, when an assessor tries to publish it, publication is blocked.

### AT5 - Evidence rule required

Given a Bloom target without mandatory evidence criteria and a pass rule, publication is blocked.

### AT6 - Task alignment

Given an `ANALYSE` target with a recall-only task, review blocks approval and explains the mismatch.

### AT7 - Deterministic pass

Given the same response, evidence, and rule versions, repeated evaluation returns the same result and criterion decisions.

### AT8 - Pass rule

Given all mandatory criteria are met, evaluation returns provisional `PASS` with `TARGET_EVIDENCE_MET`.

### AT9 - Incomplete rule

Given one mandatory criterion is not met, evaluation returns `INCOMPLETE` and lists the missing evidence.

### AT10 - Invalid attempt fairness

Given a system fault invalidates the task, the system does not issue `INCOMPLETE`; it keeps review state or voids the attempt and offers a fair next action.

### AT11 - Access support

Given an approved equivalent access mode, the same valid evidence can pass and the support does not increase instructional scaffold level.

### AT12 - Hint neutrality

Given hint use during formative work, the formal result does not change. If independence is required, the system asks for a fresh task instead of making a deduction.

### AT13 - Confidence neutrality

Given identical valid responses with different confidence ratings, the assessment result is the same.

### AT14 - Time neutrality

Given identical valid responses with different allowed completion times, the result is the same.

### AT15 - Assessor confirmation

Given a formal provisional result, it cannot become `CONFIRMED` without an authorised assessor.

### AT16 - Override audit

Given an assessor override, the old result, new result, reason, assessor, and time remain retrievable.

### AT17 - Cross-course denial

Given an assessor outside the course, every task-rule and result-review route denies access.

### AT18 - Fresh reassessment

Given an incomplete result and an approved reassessment, the new task keeps the same standard, creates a new attempt, and preserves the earlier decision.

### AT19 - Feedback language

Given an incomplete result, learner-facing feedback uses `INCOMPLETE`, not `FAIL`, and gives a clear next action.

### AT20 - Judge namespace

Given a Quality Judge rejection, it cannot be read or stored as the learner's assessment result.

### AT21 - Version conflict

Given a rule version changes after an attempt starts, finalisation returns a conflict and requires review. It does not silently use the new rule.

### AT22 - Idempotent evaluation

Given the same evaluation request ID, retries create one decision, not duplicates.

### AT23 - Research separation

Given different research conditions or consent states, the same assessment evidence and rule produce the same result.

### AT24 - Accessible result

Given keyboard and screen-reader use, the learner can reach the result, criteria, next action, and review control without colour-only meaning.

## 21. Definition of done for assessment

The assessment feature is done only when:

- The current code gap report is complete.
- All assessed outcomes require a versioned Bloom target and evidence rule.
- Only `PASS` and `INCOMPLETE` can be written or shown.
- Numeric grading is removed from formal result paths.
- System evaluation is repeatable and evidence-linked.
- Formal results use the required assessor control.
- Learners get clear result reasons and a review path.
- Access support and instructional support are separate.
- The full audit record is saved.
- Role and course-scope tests pass.
- The migration is tested with real-shaped fixtures.
- All AT1 to AT24 tests pass or have an approved, documented exception.
- Accessibility checks cover assessor setup, review, student task, and result views.
- AI evaluation remains advisory until its separate release gate passes.
