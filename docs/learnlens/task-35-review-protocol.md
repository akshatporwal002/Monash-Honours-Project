# Task 35 offline review protocol

Status: **DRAFT; expert validation and operational AI assessment activation remain PENDING.**

This package prepares validation work; it is neither a research instrument approval nor
a formal assessment record. The 108 synthetic criterion probes comprise 12 scenario
families with nine matched variants each. There are six task formats, three text input
forms, prediction/explanation/application probes, and supported/unaided stages.
Thirty-six deliberately flawed feedback candidates and 72 candidate controls support
judge preparation. These are authored inputs, not observed system outputs. No case is
educator-approved. Twelve correlated families are not 108 independent content topics.

The first approved course assessment still needs the complete D-04 multipart
prediction, explanation and fresh application criteria, all mandatory. These probes
isolate those constructs; their binary probe comparisons do not establish a complete
course PASS. The two-qubit extension cases need separate scope approval. The package
does not cover teleportation, Deutsch–Jozsa, Bernstein–Vazirani or Grover in depth.
Experts must expand coverage for any intended release that includes those topics.

## Files and review order

- [Blinded assessment packet](task-35-reviewer-packet.md): opaque IDs, shuffled order,
  prompts, responses, criterion descriptions, sources and stage conditions. It excludes
  draft labels, rationales, feedback candidates and all system decisions. Supply separate
  copies to the two trained assessors. Do not give them the author bundle before locking
  both sets of independent ratings; keep any blinding breach in the approval record.
- [Author bundle](../../src-main/backend/tests/fixtures/task35_validation/draft-bundle.json):
  108 DRAFT cases, expected criterion labels and rationales, draft feedback candidates,
  draft judge flaw labels/reasons, and empty outputs, ratings, approvals and reviewers.
  Use for content preparation and later reconciliation, not to seed a human gold standard.
- [Blank forms](../../src-main/backend/tests/fixtures/task35_validation/blank-review-forms.json):
  null identities, decisions, provenance and adjudication. This is a worksheet, not an
  import-ready set of completed ratings. The empty author bundle is import-ready.
- [Import schema](../../src-main/backend/tests/fixtures/task35_validation/review-import.schema.json):
  exported from the strict Pydantic contract. Cross-record checks in the runner are also
  required; validating JSON Schema alone cannot establish valid references or independence.
- [Manifest](../../src-main/backend/tests/fixtures/task35_validation/manifest.json):
  model, prompt, source, rule, retrieval, task, curriculum and Bloom revisions, exact
  local artifact fingerprints, and source register. It honestly records `NOT_RUN`
  for provider/model execution and retrieval.
- [Numerical receipt](../../src-main/backend/tests/fixtures/task35_validation/numerical-evidence.json):
  local ideal circuit calculations only, bound to scenario and manifest digests.
- [11 September numerical revalidation](../../src-main/backend/tests/fixtures/task35_validation/numerical-revalidation-20260911.json):
  all 12 ideal-circuit scenarios match after bounded exact-result simulation reuse,
  bound to its [saved manifest](../../src-main/backend/tests/fixtures/task35_validation/numerical-revalidation-manifest-20260911.json).
  This supplies numerical evidence only; conceptual approval remains pending.

The candidate feedback controls are proposals, not guaranteed high-quality feedback.
Experts may find them insufficiently specific. The judge flaw label, the six feedback
ratings and factual correctness are different judgements. For example, a neutral transfer
notice can respect help policy while providing no immediate conceptual revision advice.
Do not award invented positive ratings to make a target pass.

## Sources and version limits

The following primary references were opened on 10 September 2026:

| ID | Precise reference | Content checked |
| --- | --- | --- |
| H23 | [IBM HGate, Qiskit 2.3 API](https://quantum.cloud.ibm.com/docs/en/api/qiskit/2.3/qiskit.circuit.library.HGate) | Matrix representation and self-inverse property |
| X23 | [IBM XGate, Qiskit 2.3 API](https://quantum.cloud.ibm.com/docs/en/api/qiskit/2.3/qiskit.circuit.library.XGate) | Basis-state exchange and matrix representation |
| CX23 | [IBM CXGate, Qiskit 2.3 API](https://quantum.cloud.ibm.com/docs/en/api/qiskit/2.3/qiskit.circuit.library.CXGate) | Conditional target flip, control/target convention |
| STATE23 | [IBM Statevector, Qiskit 2.3 API](https://quantum.cloud.ibm.com/docs/en/api/qiskit/2.3/qiskit.quantum_info.Statevector) | `from_instruction`, exact probabilities and sampling |
| BITS | [IBM bit-ordering guide](https://quantum.cloud.ibm.com/docs/en/guides/bit-ordering) | Integers, strings, statevector ordering; unversioned web guide |
| POLICY | [Task 8 selections](task-08-approved-selections.md) | D-04, D-05 and D-07, `task-08-selections-v1` |

The installed numerical runtime is Qiskit **2.5.1**, Aer **0.17.2**; this is not the
documentation version. Attempts to open explicit 2.5 API pages returned web-tool
access errors. The available 2.3 pages are identified as pinned older documentation,
not described as the latest release. Drafts rely on the stated gate mathematics and
public application simulator, not new SDK usage advice. Experts must reconcile the
approved SDK version and preserve the exact authorised passages. An access date or a
live URL alone is not an immutable approved source revision. Each future source entry
needs `approval_reference` and `immutable_artifact`, with that artifact included in the
manifest's file digests. These remain absent, and prevent a verified quality status.

## Importing recorded outputs and ratings

Work in a new, synthetic-only offline bundle. Do not import real learner records into
this tooling under this assignment. It does not implement consent, research export,
course access or institutional governance. Keep study outcome evidence, operational
quality observations, uncertain model estimates and formal human results separate.

1. Freeze the case/criterion/source versions. Record a real reviewer roster containing
   the reviewer's name, stable ID, expertise, training and appointment references.
   An external custodian must verify those references; this offline importer cannot
   authenticate a signature or establish that a named human performed the work.
2. Preserve the proposed model/provider revision, prompt artifacts, retrieval settings,
   task/rule/curriculum/Bloom versions and all source artifacts in a new manifest.
   Add local fingerprints for every artifact and use exact model identifiers in the
   `model` component. Record execution in the external provenance receipt. Set manifest
   provenance to `RECORDED` only when that evidence actually exists.
3. Obtain separate educator case approvals tied to `case_digest`, `manifest_digest`,
   named reviewer ID and `approval_reference`. Immutable DRAFT cases stay DRAFT;
   approval records are separate, not an overwritten historical label. Changing a case
   requires new digests and new approval/review records.
4. Record at most one output per case and channel in a bundle. Channels are `task`,
   `feedback`, `evaluation`, `judge`, `assessment`. Use separate bundles/manifests for
   models, regeneration stages, pipeline conditions or repeated runs. Preserve the
   actual text (or structured output serialised as text); for judge runs include the
   exact candidate supplied and bind it through the case/output digests. Candidate
   feedback is not a recorded generator output. Judge decisions use `APPROVED` or
   `REJECTED`; learner/probe results use only `PASS` or `INCOMPLETE`.
5. An output is `RECORDED`, `MISSING`, `INVALID` or `ABSTAINED`. A non-recorded state
   needs a reason and cannot carry decisions. A recorded assessment needs the complete
   criterion map and binary result; `NOT_EVALUABLE` stays a distinct criterion label.
   Preserve contradictory system decisions for error review; do not silently repair
   an output from its criteria or fabricate an assessor result.
6. Obtain exactly two independent ratings per case/channel, each with reviewer ID,
   timestamp including timezone, reason, manifest and case digests. Content/feedback/
   judge ratings additionally bind the exact output digest. Human `assessment` ratings
   bind the case only and must have `output_digest: null` to preserve blinding.
   `RATED` requires all relevant values; `ABSTAINED`/`INVALID` require null values and
   a reason. Missing ratings are absent records, never zeroes. IDs and references must
   be unique and known. Unknown fields, coerced scores and scores outside 1–5 fail import.
7. Preserve both original ratings. Any differing values require an adjudication with
   exactly those two original rating IDs, a third named reviewer, timestamp, resolved
   values and reason. The runner never replaces original records or uses adjudicated
   values for the human inter-rater baseline. Numerical feedback averages retain both
   original independent scores even after adjudication. Keep prior bundles as historical
   evidence; use a new version for corrections, not last-write-wins deduplication.
8. Import with the runner against a separately supplied current manifest. Canonical
   object digests use `digest()` in `runner.py`: sorted compact ASCII JSON after schema
   normalisation, SHA-256. Local text artifacts use UTF-8 with BOM/CRLF normalisation,
   so a Windows checkout does not create false drift. Any substantive artifact/version
   change makes earlier evidence stale. The runner cannot discover remote provider or
   source changes automatically; the custodian must update the current manifest.

Channel values are intentionally disjoint:

| Channel | Required human values |
| --- | --- |
| task / evaluation | `factual_correct`, `hallucination` |
| feedback | Above plus all six `feedback_ratings`, `incomplete_response`, `next_action_and_revision` |
| judge | `flawed` (human judgement of the candidate the judge was given) |
| assessment | Exact criterion decisions and the reference binary probe/assessment result |

Rate factual correctness against the preserved evidence, not the model's confidence.
For hallucination, mark any incorrect or unsupported factual claim in the output.
Feedback dimensions are accuracy, clarity, relevance, useful action, outcome fit and
suitable support. Proposed anchors are 1 = seriously deficient, 2 = substantial repair,
3 = partly adequate, 4 = adequate with minor improvements, 5 = fully adequate. Named
experts must calibrate and approve dimension-specific anchors before measurement.
These planning anchors do not substitute for human training or an approved statistic.

## Measures, denominators and uncertainty

The unit is one case/channel/output, not a claim, token or reviewer. Eligible pairs
are the case count times five channels. The report retains included counts, exclusive
exclusion reasons and overall rating-state counts. Omission priority is missing output,
non-recorded output state, missing/extra reviewers, abstained/invalid review, unresolved
disagreement. A structural import error rejects the entire bundle with an error report;
it is not silently dropped to improve a denominator. Excluded pairs cannot clear a gate.

| Measure | Numerator / denominator |
| --- | --- |
| Factual accuracy, separately for task/feedback/evaluation | Outputs independently reviewed and resolved as factually correct / usable resolved outputs in that channel |
| Hallucination, separately by those channels | Outputs with at least one human-identified incorrect/unsupported claim / usable resolved outputs in that channel |
| Feedback rating, separately for each of six dimensions | Sum of each output's mean of its two original independent scores / usable resolved feedback outputs; no adjudication inflation or extra weighting for extra reviewers |
| Action and revision | Incomplete-response feedback with both a clear next action and revision chance / usable feedback rated as addressing an incomplete response |
| Flawed-output rejection | Human-labelled flawed candidates rejected by the system judge / usable human-labelled flawed candidates |
| False rejection | Human-labelled correct candidates rejected by the system judge / usable human-labelled correct candidates |
| False pass | Recorded system PASS where human reference is INCOMPLETE / usable human INCOMPLETE references |
| False incomplete | Recorded system INCOMPLETE where human reference is PASS / usable human PASS references |
| Criterion agreement | Exact matching system/human labels / usable pairs for that exact criterion version; includes NOT_EVALUABLE as its own category |
| Human baseline | Exact matches between the two original trained assessors / paired rated cases, separately by task type, criterion and named reviewer pair; available even without system outputs |

Every zero denominator yields null, never 0%, 100% or a positive target. Result and
criterion agreement include confusion matrices and descriptive Cohen's kappa. Kappa
is null for empty samples or constant marginals. No ordered-score ICC is used.
Rates include 95% Wilson intervals. Bounded [1,5] means include conservative 95%
Hoeffding intervals. These assume independent units. The 12 families have correlated
variants, so rates/means/agreement also supply a fixed-seed, 1,000-replicate bootstrap
that resamples whole scenario families. Fewer than two observed families yields no
cluster interval. Small-family percentile intervals are exploratory; even a degenerate
perfect interval is not proof of zero population error. Kappa is descriptive without
an inferential interval. The methods reviewer must approve population sampling,
adequate precision and the final statistic before using any result as release evidence.

Task type, variant, access form, writing style and stage are reported separately;
the per-metric denominator exposes sparse strata. No protected demographic membership
is invented or inferred. Lawful group analysis, adequate sample sizes and disclosure
rules require later approved evidence. Nothing here establishes group fairness.

## Targets and release boundary

The runner reads numeric targets from `docs/01-implementation-requirements.md`
(NFR12–14). Unrecognised requirement wording fails closed for manual reconciliation.
Current targets are: at least 100 educator-approved cases; factual accuracy at least
80%; hallucination at most 5%; each feedback dimension averaging at least 4/5;
action/revision coverage at least 80%; flawed rejection at least 80%; false rejection
at most 20%. Per-channel/per-dimension reporting is conservative and avoids hiding a
poor component in a pooled score. `MET` compares an observed point estimate with its
requirement, not a confidence-bound release decision.

Missing approvals, real version provenance, preserved approved sources, fresh manifests,
required content/feedback/judge ratings, or nonzero denominators yields `UNVERIFIED`.
With complete evidence, `TARGETS_MET` or `TARGETS_NOT_MET` describes only those quality
targets. Missing assessment outputs remain separate exclusions and do not substitute
for feedback evidence. The assessment release field is **always PENDING** and the
operational AI suggestions field is **always false**. There is deliberately no
activation flag or production integration. D-07 numerical error limits, statistic,
fairness rules, review triggers, revalidation plan and release authority are not supplied
by NFR12–14; neither kappa 0.70 nor 0.90 is adopted as an approved threshold.

## People and evidence required to complete Task 35

No quantum expert, assessor, adjudicator or Task 35 release authority is named in the
supplied approval records. **Arv Surana is the named research lead**, not a recorded
quantum content approver. Do not assign approvals to that person by inference.

| Appointment still required | Concrete review and signed evidence |
| --- | --- |
| Course lead and quantum-content expert(s): name pending | Approve intended course/topic scope, exact source passages and versions, all case prompts/labels/rationales, alternate methods, ambiguity handling, task-format fit and coverage of at least 100 approved cases. Review phase versus probability, finite shots, bit order, product/entangled distinctions, simulator limits and draft feedback candidates. |
| Two trained assessors: names pending | Calibrate on separate approved examples; independently rate blinded responses using frozen criterion anchors; confirm multipart D-04 evidence rules and conditions; supply original timestamps, reasons and baseline agreement by task family. |
| Third adjudicator: name pending | Resolve original disagreements with rationale, preserve both originals and identify any required case/anchor correction and re-review. |
| Accessibility reviewer and course assessor: names pending | Approve equivalent typed, dictated and structured-text modes; verify concise, verbose and alternate correct reasoning receives equivalent treatment without lowering standards; examine matched cases and actual access trials. |
| Methods reviewer, with Arv Surana for any proposed study use | Approve sampling, family dependence, precision, rating anchors, baseline statistic, exclusions, lawful subgroup evidence and separation from research outcomes. Task 32/33 approvals are still required for study collection/export. |
| Assessment governance/release authority: name pending | Supply actual AI-assessment numerical error limits, task-specific triggers, fairness review, version revalidation rules, complete recorded results and a signed evaluator release decision. |
| Provider/environment owner: name pending | Approve actual provider/model permissions and budget; record versioned outputs in an authorised environment. No paid calls were made here. |

Once these records exist, the coordinator can plan production integration through the
existing human-confirmed assessment workflow. No production change is needed to use
the offline packet. Any future operational activation change belongs to the coordinator
and is outside this branch's ownership.
