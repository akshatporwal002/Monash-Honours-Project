# Task 18: Shared learner model from live evidence

## Outcome

The learner-model service now has one controlled `update` operation. It accepts
only scoped evidence IDs with support-or-contradiction relations from a
versioned trusted adjudicator, reads immutable Task 17 evidence, and appends a
complete learner/course/outcome snapshot when the cumulative state changes.

The returned teaching view contains the snapshot chain position, model and rule
versions, uncertainty, recency, reason code, and relation-bearing evidence
links. Rule-based outputs always state `validated=False` with the
`UNVALIDATED_RULE_ESTIMATE` classification. That label describes inference
validity; it is not an assessment result.

## Consistency and boundaries

- Snapshot and estimate IDs derive from canonical scope, predecessor, versions,
  and evidence relations. Reordered or repeated work returns the existing
  snapshot without a duplicate write.
- Repository head checks and bounded service retries preserve one linear history
  when independent workers process overlapping evidence. Stored snapshots,
  estimates, and links remain append-only.
- The rules keep understanding, possible misconception, assistance, feedback
  use, and transfer in distinct dimensions. Event occurrence alone does not
  establish understanding, improvement, dependence, or successful transfer.
- The service has no learner-controlled write route and does not implement
  recommendations, formal assessment, learner corrections, or educator views.
  Those belong to later tasks.

## Controlled update boundary

`LearnerModelBuildService.update(command) -> LearnerModelBuildResult` is the
supported application operation. The caller supplies the learner/course/outcome
scope, trigger/correlation identity, rule/model versions, and trusted
adjudications. The module resolves immutable evidence and the current head,
canonicalizes cumulative relations, derives deterministic identities, builds the
complete snapshot, atomically compares and appends or replays, and validates the
stored view before returning it. Lower-level builder and repository operations
remain internal seams for focused tests.

Evidence remains authoritative and durable when model processing fails. Do not
couple model writes to Task 17 source transactions: continuation workers can
retry the deterministic update after accepted evidence has been stored.

## Evidence semantics

Separate observation, inference, and teaching decision. An evidence event's type alone usually does not say whether a learner understood something. The update path must therefore accept relations only from a trusted, versioned rule/evaluator output, never from learner input or a public request. Repository validation must reject `DERIVES_FROM`, duplicate evidence IDs, and out-of-scope evidence.

The versioned rule table in `builder.py` governs eligible signals. Each row must identify the eligible evidence types, target dimension, meaning of `SUPPORTS`, meaning of `CONTRADICTS`, minimum signal threshold, and reason-code version. Apply these safe meanings:

| Concern kept distinct | Dimension(s) | Supporting evidence means | Contradicting evidence means | Guardrail |
| --- | --- | --- | --- | --- |
| Understanding | `PRIOR_KNOWLEDGE`, `REASONING_STRENGTH`, `REASONING_GAP`, `INDEPENDENCE` | A trusted rule/evaluator explicitly found the linked prediction, reasoning, response, or revision consistent with the outcome under the recorded support conditions | A trusted rule/evaluator explicitly found it inconsistent with the outcome | Never equate submission, confidence, completion, or simulation execution with understanding |
| Possible misconception | `POSSIBLE_MISCONCEPTION` | An explicit misconception check supports the named hypothesis | A check, revision, alternate explanation, or later probe explicitly contradicts that hypothesis | One supporting signal remains uncertain; never emit a diagnosis or fixed trait |
| Assistance | `SCAFFOLD_DEPENDENCE`, `INDEPENDENCE` | Recorded instructional help supports help-use/dependence, or an independently adjudicated performance supports independence | Independently adjudicated performance can contradict dependence; supported-condition performance can contradict independence | Access support is never instructional dependence; a help request alone says only that help was used |
| Response to feedback | `FEEDBACK_USE` | An explicit acknowledgement plus a linked later revision/reflection shows the defined response behavior | A trusted check explicitly finds that the targeted issue persists | Viewing/acknowledging feedback alone does not prove use or improvement |
| Transfer | `TRANSFER` | A trusted check explicitly supports application on the fresh transfer task | A trusted check explicitly contradicts transfer | Starting or submitting a transfer task does not prove successful transfer |

Do not collapse `REASONING_STRENGTH` and `REASONING_GAP` into whichever relation happens to occur first. A dimension has stable semantics: evidence may support or contradict that dimension. Mixed support and contradiction must produce `UNCERTAIN`, retain every link, and use the newest linked observation as `evidence_observed_at`.

## Cumulative snapshots

Each new snapshot is a full state for one learner/course/outcome, not a delta. Merge prior linked signals with newly eligible signals by `(dimension, evidence_id)`, preserving the original relation. Sort dimensions and signals by stable enum/ID ordering before hashing, building, comparing, and returning them.

Rules for accumulation:

- A repeated evidence ID with the same dimension and relation is a replay and adds nothing.
- Reusing an evidence ID with a different relation or incompatible dimension is a conflict requiring review; never rewrite its historical meaning.
- Evidence not eligible under the active rule version is omitted rather than forced into a nearby dimension.
- If canonical cumulative input is unchanged and no accepted correction requires a successor, return the current snapshot with `created=False`; do not append an empty successor.
- If input changes, `prior_snapshot_id` must equal the current head and `record_version` must be `head.record_version + 1` (or `1` for the first snapshot).
- Snapshot identity/idempotency must be derived from scope, predecessor identity, rule/model versions, and the canonical evidence/relation set. Estimate identity must derive from the resulting snapshot identity plus dimension. Retries and concurrent workers therefore propose byte-for-byte equivalent payloads.
- `occurred_at` must be deterministic (the maximum included evidence observation time), while database `created_at` remains persistence time. Never use worker wall-clock time in logical identity.

## Concurrent appends

Treat the predecessor as optimistic-concurrency state. In one repository transaction, resolve/lock the current head where supported, compare it with the proposed predecessor, validate all evidence and estimates, and append the complete snapshot. A candidate with no predecessor is valid only when the scope has no snapshot; a candidate with a predecessor is valid only when it names the unique current head.

Database uniqueness remains the final arbiter. On `IntegrityError`, rollback before any reread, load the snapshot by deterministic idempotency identity in a fresh transaction state, and:

- return `created=False` only when the entire stored snapshot, estimates, ordered relations, versions, predecessor, and timestamps equal the proposal;
- otherwise raise `LearnerModelConflictError` for stale/forked or inconsistent processing;
- allow the build service to re-resolve the head and retry once only when another writer appended an equivalent/compatible predecessor during the race; keep the retry bounded.

This produces one linear history for both simultaneous identical work and overlapping updates. It must not silently accept two different successors to the same prior snapshot.

## Teaching-facing read contract

Current-snapshot and timeline reads share the same hydration contract. The returned immutable view must contain:

- snapshot ID, prior snapshot ID, scope, record version, source, schema/model/rule versions, logical occurrence time;
- every estimate's ID, dimension, inference status, numeric uncertainty, reason code, evidence recency, and ordered `(evidence_id, relation)` links;
- an explicit validation classification suitable for teaching services.

For `ModelSource.RULE_BASED`, always expose the literal label `UNVALIDATED_RULE_ESTIMATE` and a non-optional `validated=False`. Do not let `SUPPORTED` be rendered or interpreted as scientifically validated confidence. Reserve a validated classification for a future approved validation process; human review of a non-rule provider is a release gate, not empirical validation. Hydration must fail closed if a snapshot has no estimates, an estimate has no evidence link, scope/version metadata is missing, uncertainty is out of range, duplicate dimensions exist, or the predecessor chain is inconsistent.

Continuation and tutor decisions must use this read interface, retain the selected snapshot and rule version, and verify that changing a relevant estimate can change an otherwise identical permitted teaching decision. They must not depend on ORM rows or builder internals. See the [continuation contract](task-22-approved-activity-continuation.md) and [tutor and results contract](task-23-24-tutor-and-results.md).

## Verification

`test_learner_model.py` covers trusted-adjudication controls, rule semantics,
real persisted evidence scope, cumulative snapshots, replay, two-session
concurrency, stale-head rebuilding, protected history, teaching-view safety,
and provider/review failures. The repository's existing migration test confirms
the established append-only tables remain valid; Task 18 adds no migration.

Rule verification must include improvement, conflicting-evidence, and
insufficient-evidence examples, retaining evidence links and explicit uncertainty.
An observed change in an estimate does not establish an educational improvement.
Accepted correction effects and preservation of original evidence are defined in
the [learner corrections contract](task-19-corrections.md).
