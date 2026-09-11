# Learner start, structured tasks and reviewed support

## Delivered behavior

New assessed work opens as a preview of the published conditions. The learner must activate **Start assessed task** before entering a response, requesting instructional support, saving or submitting. Existing started drafts revalidate their original displayed form through the idempotent start endpoint. Retry and version-conflict behavior preserves the original work reference and local edits.

`matching` and `sequencing` are first-class task types. Definitions contain stable item IDs, text and source-passage references. Matching is one-to-one; sequencing contains each declared item once. Versioned JSON responses retain item IDs and optional exact reviewed labels in the existing protected answer field. Partial drafts are allowed; submissions require complete, unique, known items. Extra fields, invented labels, invalid keys and undeclared item sources are rejected.

Educators can select either type for generation and edit its definition and private answer key in task review. Learners use native selects or move buttons; saved evidence uses a table or ordered list with the submitted labels. The independent handler compares exact pairs/order when a private key is supplied. Formal responses continue through the approved criterion and human-review path; a type-handler match never confirms a result.

The offline generator creates bounded source-excerpt matching and reconstruction exercises. These are formative drafts, not evidence of pedagogical validity. Generation version `task-generation-v2` requires purpose, difficulty basis, intended evidence, expected response features, tools, instructional support, access modes, equivalent formats and rubric version. Task, source, provider/model and reviewed-rubric versions remain in existing immutable revision and source-use records. Removing the teaching design blocks approval of a v2-generated task. Older reviewed generator versions retain their existing contract.

Reviewed episode plans can contain text, visual, worked-example, circuit and stepwise instructional representations. Each has source references, an equivalence rationale, equivalent text and an explicit support level. Diagram steps and circuit operations have text equivalents. The server releases only the requested frozen item. The existing support receipt stores its original form and item index; evidence capture resolves the support level from that frozen plan. Repeated use is allowed without a result penalty. Fresh transfer hides both new requests and replayed instructional content, while existing approved access support remains available.

Tutor dialogue creates a normal-priority review case for repeated answer-only requests or explicit copied-solution language. The cue preserves the relevant turn IDs, rule version and uncertainty. Cases are deduplicated by learner, task, context and signal kind. The response redirects to reasoning. Neither the cue nor its review case changes assessment evidence or results, and neither asserts misconduct. This is a limited dialogue-language detector, not plagiarism or authorship detection.

## Scope that remains open

| Area | Supported boundary and remaining gap |
| --- | --- |
| FR8 generation | The selector offers the six existing basic response types plus matching/sequencing. The local generator rejects episode-only prediction/reasoning/explanation/revision/reflection/transfer generation with an authoring action instead of silently producing a keyword task. Their existing typed manual episode flows remain. Complete automatic generation of every assessed multipart definition, approved Bloom target and criterion anchor remains open. |
| FR9/PD4 types | Matching/sequencing now have authoring, generation, draft/submission, rendering and evaluation contracts. `state_comparison`, `diagnosis`, `probability_interpretation`, `part_complete` and standalone `confidence` remain staged identifiers; related evidence can still be collected through existing circuit/code/episode activities. |
| FR35 equivalence | The new forms are reviewed instructional support for the supported episode stage. They do not automatically establish equivalent accessible forms for every construct or transfer task. Actual content/source approval and construct-equivalence review remain required. |
| FR22/FR39 learning/calibration | Validated changes in understanding/reasoning and confidence calibration are not established by weekly counts or confidence records. This delivery adds no validated learning-gain or calibration estimator. |
| PD3 strategy/useful format | Strategy success/failure and which format improves a learner's understanding remain unproven. Opening support, choosing a format, repeating or revising is observed activity, not evidence that the strategy worked. |
| Human evidence | Named assistive-technology checks, expert content/criterion validity, and institutional/source/form activation approvals remain external records. Synthetic tests establish software behavior only. |

## Contracts and migration

- New schemas: `structured_tasks.py`, `generated_task_design.py`, `support_representations.py`.
- Public additions: `TaskType` values, `TaskRead.structured_task`, `EpisodeStateRead.representation_choices`, `EpisodeHelpUseReceipt.representation` and reviewed `EpisodePlanV1.support_representations`.
- Migration `20260911_0050` expands the task CHECK constraint. It preserves rows, indexes, triggers and foreign keys and is replay-safe. Downgrade requires restoring a verified backup. The coordinator sets its final predecessor and readiness pin.
- The coordinator regenerates final API/frontend contracts after integration. Provider accounting, moderation and study/export behavior belong to their respective deliveries.

## Focused verification

`test_structured_tasks.py` covers exact evaluation, invalid payloads, grounded generation, review requirements, partial drafts, reloads, revisions and formal frozen-version conflicts. `test_structured_tasks_migration.py` verifies a populated forward upgrade, preserved protected history/triggers, both allowed values, unknown-type rejection, replay and downgrade refusal.

`test_task14_support.py` covers all five representations, exact frozen support levels, idempotent history and transfer replay suppression. `test_tutor.py` covers uncertain review cues, deduplication and unchanged assessment work.

Frontend checks cover explicit keyboard start and retry behavior, existing saved typed episode results, partial matching drafts and readable saved labels, keyboard sequencing, representation request/transfer hiding, and the generation selector. Type checking and scoped lint were run. No full backend, frontend or browser suite, paid-provider call, deployment or real study processing was performed for this delivery.
