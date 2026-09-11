# Multipart generation and assessment-draft bridge

## Delivered slice

The course generator offers **Multipart Hadamard episode (one draft)**. It sends `generation_mode: multipart`, one task, and `quantum_circuit`. Both generation APIs accept the mode; the service rejects unsupported modes, counts and task-type combinations. Ordinary generation remains formative. Multipart metadata and its proposed assessment design both declare SUMMATIVE, while formal eligibility remains false.

The first supported family is `hadamard_basis_transfer`: supported input |0>, followed by a private fresh |1> input prepared by X. It uses the existing circuit editor, prediction checkpoint, supported reasoning/explanation/reflection and transfer stores. The candidate declares five mandatory human-review criteria and an ALL_OF rule referencing every criterion. It includes proposed met/not-met anchors, source quotes, criterion-to-source links, proposed Apply/procedural metadata, tools, conditions, sufficiency and next-action/reassessment guidance. These are proposals, not approved criteria or demonstrated semantic validity.

The offline generator deliberately recognizes only a supplied passage containing this exact sentence:

> Hadamard maps |0> to (|0> + |1>)/sqrt(2) and |1> to (|0> - |1>)/sqrt(2).

Other wording and content fail with an authoring action. This exact-template restriction also applies to provider candidates in this first family. Containing the sentence establishes a reproducible source anchor, not that the surrounding document endorses it or that the candidate measures the intended outcome. No source is synthesized or approved by the generator.

## Validation and provenance

`MultipartCandidate` is retained inside the existing task revision's marking criteria; `EpisodePlanV1` remains the executable plan. Validation requires matching plans, distinct prescribed supported/transfer circuit inputs, every required stage and criterion, consistent purpose, all criterion references in the Boolean rule, human evaluators, proposed anchors and exact source membership/quotes. Source references are rebound with the existing frozen source binding before the task revision is captured. Multipart generations use prompt version `task-generation-multipart-v1`.

Generated candidates cannot supply task forms, formal eligibility, access-equivalence approval, learner response/checkpoint/simulation/stage identifiers or approval references. Revision means a later response referencing a real earlier response to the same learner/task/work; the first response is not forced to cite nonexistent work. Existing episode runtime validation checks actual references and rejects foreign or invented records. It also checks prediction inputs and the separate transfer-stage receipt. It does not infer that a learner's submitted answer is correct from the stage's presence.

Teaching approval alone does not release these generated episodes to learners. They require an approved assessment form so the existing assessed-work and private-transfer contracts are available.

## Existing-store authoring bridge

Reviewed rows in the assessment task picker expose **Preview generated assessment design** and **Save generated assessment draft** through `GeneratedAssessmentDraft.tsx`.

GET/POST `/api/v1/assessment/courses/{course_id}/tasks/{task_id}/generated-assessment-draft?expected_revision_id={revision_id}` require active course-scoped assessor access. GET is read-only. POST locks the course, rechecks the current task/source review and requested revision, then calls the existing assessment-definition creation path. It preserves all five criteria, anchors and the Boolean rule and binds the actual task revision/form provenance. Stale, unreviewed, foreign and unauthorized requests fail. An outcome with an existing definition produces the existing conflict rather than a second identity or silent replacement.

The saved definition is DRAFT, with `formal_result_eligible: false`, access review required, and no verified elicited Bloom processes. The existing approval service rejects it until the required design review is completed. No approval or deployment is performed by this bridge.

The panel currently previews and saves; it does not itself edit or publish the saved multi-criterion definition. The coordinator has assigned lossless editing of existing definitions to the separate assessment-UI delivery. Integration should pass the returned `assessment_definition_id` and course to that editor. The existing read route is `/api/v1/assessment/courses/{course_id}/definitions/{assessment_definition_id}/history`. Keep all criteria/forms when handing off; the older single-criterion `SetupValues` form is not a lossless target.

## Remaining software and human work

- Generalized source interpretation, alternate wording, additional quantum families, multiple candidate variants and higher Bloom targets are not implemented by this family.
- Standalone prediction/reasoning/explanation/revision/reflection/transfer generation remains rejected by the basic offline generator. Their fields participate in this circuit episode; this is not six new standalone generation paths.
- First-response revision is not generated. Feedback-conditioned regeneration and cross-task prior-work selection remain open; actual later same-work response references use the current runtime.
- Fresh transfer is a distinct declared input and stage. Psychometric equivalence, novelty relative to the learner's broader history, and outcome/criterion validity require further design and evidence.
- Support representation delivery, practice preferences and integrity cues remain owned by their separate implementations. This generator creates no support representations.
- Actual source/task/form approval, assessor eligibility, access-equivalence decisions and Bloom verification remain human records. Synthetic test approvals do not establish any of them.

No migration is needed. The coordinator owns final OpenAPI/frontend contract regeneration, fingerprints and combined checks. Public changes include optional generation modes, one-task multipart request validation, `AssessmentAuthoringTaskRead.generated_assessment_candidate`, the generated-draft endpoints and SUMMATIVE as a proposed generated-design purpose.

## Focused verification

`tests/test_multipart_generation.py`: four tests passed in the final run: candidate invariants/unsupported content; invalid provider output without persistence; scoped reviewed-version preview/save preserving all criteria without approval; generated episode lifecycle with real versus invented work references and separate transfer. The bridge test also verifies that an unverified candidate cannot pass existing approval.

Frontend selectors: `CourseEditor.test.tsx -t 'generation sends the chosen'` passed both matching and multipart cases; `GeneratedAssessmentDraft.test.tsx` passed explicit save and stale-review cases. TypeScript and scoped ESLint/Ruff checks passed. No full backend/frontend/browser suite, paid provider, deployment or real approval was run.
