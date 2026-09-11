# Source-led generation and assessment drafts

## Delivered behavior

CourseEditor offers the existing choice, short-answer, code, circuit, matching and sequencing formats plus prediction, reasoning, explanation, reflection and transfer. Basic generations are formative drafts. The new text activities quote a real supplied passage and retain typed responses in existing versioned evidence. Standalone transfer uses `supported.application: ResponseContent`: a new-context practice activity, without a claim of an unaided assessed stage. Blank typed responses cannot be bypassed with an unrelated top-level answer.

Basic practice activities do not receive an assessed `episode_plan`. Prediction checkpoints and private transfer receipts require approved assessment work. The normal practice form can save, submit, reload and revise each generated response without fabricating that work. A revision references an actual earlier response from the same learner, task and work; the generator never invents a first-response predecessor.

Offline code and circuit scaffolds select an H, X or CX gate actually named in the source. CX uses two qubits. Unsupported content returns a controlled authoring error instead of silently substituting H. Code explanations and short answers retain human evidence guidance instead of an outcome-word answer key. Multiple-answer recognition uses actual source excerpts; matching and sequencing preserve their exact source-excerpt contracts. These templates do not establish semantic validity or outcome alignment.

## Multipart assessed candidates

CourseEditor offers **Multipart circuit episode (one draft)** and **Multipart text episode (one draft)**. Both generation APIs accept one supported text or circuit type in multipart mode. Candidates propose SUMMATIVE purpose, Apply/procedural evidence, five mandatory human-review criteria, source anchors and an ALL_OF rule. Formal eligibility remains false, with access/Bloom/context review unfinished until a real assessor reviews the saved design.

- `hadamard_basis_transfer` preserves the existing exact-source family: supported |0>, then a private X-prepared |1> input. The exact transformation sentence and distinct inputs remain strictly validated.
- `source_application_transfer` works with other substantive course passages. Supported work applies a cited relationship; private transfer asks for a distinct example or circuit with a changed condition and a justified consequence. Every quote must occur in its bound passage. Educators must review the relationship, example demand and critical-error guidance.

`MultipartCandidate` is stored in immutable task revisions alongside an identical executable `EpisodePlanV1`. Validation retains every required stage, criterion, rule reference, proposed anchor and source link. Candidates cannot create approvals, task forms, formal eligibility or runtime response/checkpoint/simulation/stage identifiers. The fresh prompt and private assessor details stay outside learner previews until entry to the approved transfer stage.

Teaching approval alone does not release multipart candidates. GET/POST `/api/v1/assessment/courses/{course_id}/tasks/{task_id}/generated-assessment-draft?expected_revision_id={revision_id}` require active scoped assessor access and the exact current reviewed task. Preview is read-only; save uses the existing definition store, preserves all criteria and binds actual task/source provenance. It does not approve anything. Saving opens the [versioned definition editor](assessor-definition-editor.md).

## Variants and feedback-conditioned drafts

**Load variant and feedback options** lists current task revisions and eligible practice feedback for the selected course/outcome. `/api/v1/courses/{course_id}/generation-options` is educator-owner scoped. Both generation APIs accept optional `generation_context`: either a task/revision pair or a response/feedback pair. Callers cannot supply replacement prior-work content.

Variants bind the current revision and its digest. Stale revisions, unrecorded edits and foreign outcomes are rejected before provider invocation. The provider receives the prior prompt and produces a new draft with a changed-context demand; equivalence still needs review.

Feedback conditioning resolves a real immutable practice response and matching accepted, quality-approved feedback. It excludes assessed and private-transfer work. The provider receives the actual supported response and feedback as data. The local template chooses a follow-up focus from that feedback and the available response fields, without reproducing learner text or identifying the learner. These are new tasks, not same-work revision evidence.

`generation_lineage` comes from the server, never the model. It records source task/revision or response/feedback IDs and digests in the private task revision. Inputs are rechecked after generation. Learner projections omit this lineage and original response. All generated families retain GENERATED provenance and publication gates. The coordinator's FR17 quality-review seam belongs at task approval; this generator does not invent a receipt or independently call a judge on insertion.

## PD4 staging and extension contracts

The authoritative [PD4 requirement](../01-implementation-requirements.md) says “support or plan extension points” and explicitly permits MVP staging when missing types remain in the gap matrix. This delivery uses that permission for the five standalone identifiers below. These are **planned extensions, not implemented runtime types**. Related existing evidence does not close them. The coordinator owns their gap-matrix entries.

| Staged identifier | Authoring/generation definition | Response/evaluator extension |
| --- | --- | --- |
| `state_comparison` | Two named classical/quantum states, sources and explicit comparison dimensions | Typed similarities/differences tied to each state; completeness checks and reviewed semantic criteria |
| `diagnosis` | Source-grounded circuit, candidate fault and private repair guidance | Stable operation references, fault, evidence and correction; structure checks and reviewed diagnosis criteria |
| `probability_interpretation` | Versioned outcomes, exact probabilities or sampled counts, shots and source provenance | Typed interpretations distinguishing probability from frequency; bounds/normalization checks and reviewed reasoning criteria |
| `part_complete` | Immutable given steps, editable gaps and permitted completions | Stable gap/step responses preserving given work; completion checks and reviewed process criteria |
| `confidence` | Explicit scale wording/timing tied to a real prediction or response | Bounded rating and optional reason as learning evidence; no confidence threshold in a formal pass rule |

Circuit prediction/change, reflection after a prediction, matching/sequencing and new-context application have usable paths in the existing/new task families. Simulation remains bounded by the actual H/X/CX capabilities. Higher Bloom targets can be authored through the definition editor; local multipart templates propose Apply/procedural only. Source truth, alignment, equivalent demand and access equivalence remain real reviewer decisions.

Generated equivalent support content belongs to the release/reuse delivery. Its helper should attach practice representations to basic tasks and episode representations to multipart tasks. This change does not replace that work or claim that format names constitute equivalent content.

## Verification and integration

- `test_source_episode_generation.py`: all five basic text types; non-Hadamard text/circuit candidates; source anchoring; stale/foreign variants; real accepted feedback; private lineage; actual generated practice submission/reload and blank-response rejection; X/CX source-specific scaffolds.
- `test_multipart_generation.py`: exact-family invariants, invalid-provider rollback, existing-store preview/save, real earlier-work references and private transfer lifecycle.
- CourseEditor tests: matching, transfer, both multipart modes and both real context choices. Episode control test: standalone application entry and saved display without assessed-stage controls.
- Final targeted backend run: 18 passed, 8 deselected (source/multipart/related structured generation). Eight focused frontend tests passed; TypeScript and scoped Ruff/ESLint checks passed. One prior concurrent editor run timed out; serial rerun with a 15-second test limit passed. Immediate CI repairs separately passed 15 selected checks in commit `837c033`.

No migration, paid-provider call, real approval or deployment is performed. Coordinator integration must refresh OpenAPI/frontend contracts and fingerprints for `generation_context`, generation-options, expanded candidate families and optional `EpisodeStageResponseV1.application`. The temporary frontend optional intersection supports typechecking before that refresh. Retrieval/scanner integration and quality/support owners retain their assigned checks. No full suite or browser suite was run here.
