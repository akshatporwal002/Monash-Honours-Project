# Task 18 Implementation Plan: Update the Shared Learner Model from Real Evidence

## Goal and completion boundary

Implement one deep learner-model module that accepts a scoped, deterministic update request, resolves immutable Task 17 evidence, creates or replays exactly one append-only snapshot, and returns a validated teaching-facing read model. The module must preserve predecessor history, evidence recency, support/contradiction links, rule and model versions, and uncertainty.

Task 18 must make the learner-model seam usable by Tasks 22 and 23, but must not implement pathway selection, tutor dialogue, learner corrections, formal assessment, or model-validity research. Those consumers must later prove that two otherwise identical decisions change when a relevant estimate changes and must retain the snapshot and rule version used.

No database migration is expected: the existing snapshot, estimate, and evidence-link tables already persist the required history and provenance. If implementation proves that an explicit persisted validation-status field is unavoidable, stop and revise this plan rather than silently broadening the migration scope. For Task 18, derive the teaching-facing validation label from the immutable `model_source` and version metadata.

## Grounded current state

- `src-main/backend/app/services/evidence/live.py` now creates stable, append-only evidence from real predictions, support use, submissions/revisions, transfer attempts, simulations, and feedback acknowledgements. Its links are provenance links (`DERIVES_FROM`), not learner-model support/contradiction judgments.
- `builder.py` currently requires callers to provide every evidence ID and its support/contradiction relation. It groups types into dimensions and assigns fixed uncertainty, but it has no application-oriented update command, no cumulative-state policy, and no explicit unvalidated-rule label.
- `repository.py` verifies evidence scope, stores snapshots atomically, detects sequential exact replay, and exposes a timeline. It does not select new evidence, resolve the current head, reject a stale/forked predecessor, recover a same-payload uniqueness race, or expose all metadata teaching consumers need.
- `test_learner_model.py` proves deterministic construction, basic replay, append-only history, weak misconception handling, provider failure isolation, and migration creation. It does not exercise real Task 17 evidence, simultaneous writers, cumulative snapshot updates, or the teaching-facing read contract.

## Architecture and design

### 1. Put the controlled seam in the learner-model module

Expose one application-facing operation on `LearnerModelBuildService`, conceptually `update(command) -> LearnerModelBuildResult`. The caller supplies scope, trigger/correlation identity, rule/model versions, and trusted adjudications; the module owns all remaining orchestration:

1. Resolve and validate the evidence within the learner/course/outcome scope.
2. Resolve the current snapshot head for that scope.
3. Canonicalize the cumulative evidence set and relation assignments.
4. Derive deterministic snapshot and estimate identities from the logical input, not from call timing or a random caller value.
5. Build the complete next snapshot.
6. Atomically compare-and-append or return the winner of an identical replay/race.
7. Read back and validate the stored snapshot before returning it to a teaching consumer.

Keep the lower-level builder and repository operations available as internal seams for focused tests, but make the update operation the only supported application path. Do not wire learner-model writes directly into Task 17 source transactions: evidence remains authoritative and durable if model processing fails, while the continuation/worker flow can safely retry the deterministic update.

### 2. Define evidence semantics explicitly

Separate observation, inference, and teaching decision. An evidence event's type alone usually does not say whether a learner understood something. The update path must therefore accept relations only from a trusted, versioned rule/evaluator output, never from learner input or a public request. Repository validation must reject `DERIVES_FROM`, duplicate evidence IDs, and out-of-scope evidence.

Use a single, documented rule table in `builder.py`. Each row must identify the eligible evidence types, target dimension, meaning of `SUPPORTS`, meaning of `CONTRADICTS`, minimum signal threshold, and reason-code version. Apply these safe meanings:

| Concern kept distinct | Dimension(s) | Supporting evidence means | Contradicting evidence means | Guardrail |
| --- | --- | --- | --- | --- |
| Understanding | `PRIOR_KNOWLEDGE`, `REASONING_STRENGTH`, `REASONING_GAP`, `INDEPENDENCE` | A trusted rule/evaluator explicitly found the linked prediction, reasoning, response, or revision consistent with the outcome under the recorded support conditions | A trusted rule/evaluator explicitly found it inconsistent with the outcome | Never equate submission, confidence, completion, or simulation execution with understanding |
| Possible misconception | `POSSIBLE_MISCONCEPTION` | An explicit misconception check supports the named hypothesis | A check, revision, alternate explanation, or later probe explicitly contradicts that hypothesis | One supporting signal remains uncertain; never emit a diagnosis or fixed trait |
| Assistance | `SCAFFOLD_DEPENDENCE`, `INDEPENDENCE` | Recorded instructional help supports help-use/dependence, or an independently adjudicated performance supports independence | Independently adjudicated performance can contradict dependence; supported-condition performance can contradict independence | Access support is never instructional dependence; a help request alone says only that help was used |
| Response to feedback | `FEEDBACK_USE` | An explicit acknowledgement plus a linked later revision/reflection shows the defined response behavior | A trusted check explicitly finds that the targeted issue persists | Viewing/acknowledging feedback alone does not prove use or improvement |
| Transfer | `TRANSFER` | A trusted check explicitly supports application on the fresh transfer task | A trusted check explicitly contradicts transfer | Starting or submitting a transfer task does not prove successful transfer |

Do not collapse `REASONING_STRENGTH` and `REASONING_GAP` into whichever relation happens to occur first. A dimension has stable semantics: evidence may support or contradict that dimension. Mixed support and contradiction must produce `UNCERTAIN`, retain every link, and use the newest linked observation as `evidence_observed_at`.

### 3. Build complete cumulative snapshots

Each new snapshot is a full state for one learner/course/outcome, not a delta. Merge prior linked signals with newly eligible signals by `(dimension, evidence_id)`, preserving the original relation. Sort dimensions and signals by stable enum/ID ordering before hashing, building, comparing, and returning them.

Rules for accumulation:

- A repeated evidence ID with the same dimension and relation is a replay and adds nothing.
- Reusing an evidence ID with a different relation or incompatible dimension is a conflict requiring review; never rewrite its historical meaning.
- Evidence not eligible under the active rule version is omitted rather than forced into a nearby dimension.
- If canonical cumulative input is unchanged, return the current snapshot with `created=False`; do not append an empty successor.
- If input changes, `prior_snapshot_id` must equal the current head and `record_version` must be `head.record_version + 1` (or `1` for the first snapshot).
- Snapshot identity/idempotency must be derived from scope, predecessor identity, rule/model versions, and the canonical evidence/relation set. Estimate identity must derive from the resulting snapshot identity plus dimension. Retries and concurrent workers therefore propose byte-for-byte equivalent payloads.
- `occurred_at` must be deterministic (the maximum included evidence observation time), while database `created_at` remains persistence time. Never use worker wall-clock time in logical identity.

### 4. Enforce a single linear head under races

Treat the predecessor as optimistic-concurrency state. In one repository transaction, resolve/lock the current head where supported, compare it with the proposed predecessor, validate all evidence and estimates, and append the complete snapshot. A candidate with no predecessor is valid only when the scope has no snapshot; a candidate with a predecessor is valid only when it names the unique current head.

Database uniqueness remains the final arbiter. On `IntegrityError`, rollback before any reread, load the snapshot by deterministic idempotency identity in a fresh transaction state, and:

- return `created=False` only when the entire stored snapshot, estimates, ordered relations, versions, predecessor, and timestamps equal the proposal;
- otherwise raise `LearnerModelConflictError` for stale/forked or inconsistent processing;
- allow the build service to re-resolve the head and retry once only when another writer appended an equivalent/compatible predecessor during the race; keep the retry bounded.

This produces one linear history for both simultaneous identical work and overlapping updates. It must not silently accept two different successors to the same prior snapshot.

### 5. Return a validated teaching-facing snapshot

Add a repository read operation for the current snapshot (and reuse a shared hydration function for timeline reads). The returned immutable view must contain:

- snapshot ID, prior snapshot ID, scope, record version, source, schema/model/rule versions, logical occurrence time;
- every estimate's ID, dimension, inference status, numeric uncertainty, reason code, evidence recency, and ordered `(evidence_id, relation)` links;
- an explicit validation classification suitable for teaching services.

For `ModelSource.RULE_BASED`, always expose a literal label such as `UNVALIDATED_RULE_ESTIMATE` and a non-optional `validated=False`. Do not let `SUPPORTED` be rendered or interpreted as scientifically validated confidence. Reserve a validated classification for a future approved validation process; human review of a non-rule provider is a release gate, not empirical validation. Hydration must fail closed if a snapshot has no estimates, an estimate has no evidence link, scope/version metadata is missing, uncertainty is out of range, duplicate dimensions exist, or the predecessor chain is inconsistent.

Tasks 22 and 23 should depend only on this read interface, not ORM rows or builder internals. This keeps future teaching decisions coupled to a stable, provenance-rich snapshot and makes their estimate-driven behavior testable at one seam.

## Target files and modifications

### `src-main/backend/app/services/learner_model/builder.py`

- Add the application-facing update command/result orchestration while retaining the provider adapter as an internal seam.
- Centralize the versioned evidence-to-dimension rule table and relation semantics; remove the current behavior that changes the reasoning dimension based on relation.
- Add canonical grouping, cumulative merge, stable ordering, deterministic IDs/timestamps, minimum-evidence rules, and explicit mixed-evidence handling.
- Keep dimensions separate and ensure one estimate per dimension.
- Carry prior state forward without mutating old payloads or losing old evidence links.
- Add bounded conflict retry around compare-and-append and return the validated stored view, not merely a write receipt, to application consumers.
- Keep provider/review failures bounded and ensure they cannot mutate evidence or snapshots.

### `src-main/backend/app/services/learner_model/repository.py`

- Expand observation reads to support the controlled path's scoped selection/canonical order and to provide only metadata needed by the rule implementation; do not expose protected artifact text by default.
- Add current-head lookup and complete snapshot hydration shared by `current(...)` and `timeline(...)`.
- Expand view dataclasses to include scope, record/version metadata, estimate IDs, reason codes, recency, relation-bearing evidence links, and the explicit validation classification.
- Add compare-and-append validation: first/head rules, exact current predecessor, monotonic record version, deterministic replay, and no fork from a stale head.
- Make exact replay comparison canonical and complete, including relation values and all estimate metadata.
- Recover identical uniqueness races after rollback; distinguish a true replay from a conflicting idempotency reuse or competing fork.
- Preserve atomic snapshot/estimate/link insertion and translate database failures into the existing bounded safety/persistence errors.
- Keep timeline order deterministic and validate hydrated snapshots before exposing them to teaching modules.

### `src-main/backend/tests/test_learner_model.py`

- Replace synthetic-only happy-path coverage with fixtures that use stable Task 17-style evidence metadata and source-derived IDs, while retaining narrow repository validation tests where useful.
- Add table-driven rule tests for each distinct concern and both relation directions, including ineligible event types, access-support separation, feedback acknowledgement without revision, transfer attempt without adjudication, and mixed evidence.
- Assert complete cumulative snapshots, predecessor and record-version progression, immutable old snapshots, recency, rule/model versions, reason codes, and exact relation-bearing evidence links.
- Assert canonical behavior when evidence arrives in different input/query orders and when the same evidence is processed repeatedly.
- Assert explicit `UNVALIDATED_RULE_ESTIMATE`/`validated=False` labeling on every rule-based teaching view, including `SUPPORTED` estimates.
- Add current-view validation tests proving malformed/incomplete persisted state fails closed and cross-scope reads cannot leak learner data.
- Add provider failure/review-gate regressions and ensure evidence history remains durable.
- Keep the existing migration test as a regression check; do not add schema expectations unless scope is deliberately revised.

## Step-by-step coding blueprint

1. **Characterize the current interface.** Run the learner-model tests unchanged. Record current replay, history, safety, and migration behavior so refactoring preserves intentional guarantees.
2. **Write failing teaching-view tests.** Specify the complete current-snapshot read model, relation-bearing links, recency/version fields, stable ordering, and mandatory unvalidated-rule label.
3. **Deepen repository hydration.** Introduce one private hydration implementation used by both current and timeline reads; validate completeness and scope before returning immutable views.
4. **Write failing rule-semantics tests.** Cover the five concern groups, positive/negative relations, weak misconception evidence, mixed signals, and forbidden shortcuts from mere event occurrence to cognition.
5. **Replace ad hoc branching with the versioned rule table.** Make dimensions stable, calculate statuses/uncertainty deterministically, generate versioned reason codes, and preserve all contributing links and latest evidence time.
6. **Write failing cumulative-update tests.** Start from no head, append new evidence, replay unchanged evidence, and add contradictory evidence. Assert full-state successors and untouched predecessors.
7. **Implement canonical cumulative assembly.** Resolve the head, hydrate prior signals, merge new adjudications, sort all inputs, derive deterministic IDs and logical time, and skip no-op successors.
8. **Write failing stale-head and race tests.** Cover identical simultaneous requests, reordered identical requests, same idempotency key with different content, different updates against one predecessor, and a later retry after another writer wins.
9. **Implement repository compare-and-append.** Validate predecessor/head and record version inside the transaction, rely on database uniqueness as the final guard, rollback on integrity failure, then reread and compare the winner before deciding replay versus conflict.
10. **Add a bounded orchestration retry.** Retry only the recognized compatible-head race once; propagate semantic conflicts and persistence failures without spinning or generating a new logical identity.
11. **Exercise real persistence concurrency.** Use two independent sessions/connections and a synchronization barrier so both workers resolve the same initial head before storing. Do not simulate concurrency by calling the same session sequentially. Use the project's production-representative database fixture if SQLite locking cannot express the race; keep a deterministic sequential conflict test as the portable baseline.
12. **Prove consumer readiness.** Through the public learner-model interface, retrieve a complete validated view and use a small fake teaching consumer in the test to choose different allowed actions for two distinct estimate states. This proves the seam needed by Tasks 22/23 without implementing either task's production policy.
13. **Run focused and regression validation.** Format/lint the three changed files, run `test_learner_model.py`, then the evidence/continuation/feedback tests most likely to catch seam regressions, followed by the backend suite if feasible. Verify Alembic still has one head and the existing learner-model migration test passes.

## Validation strategy and acceptance matrix

| Scenario | Expected result |
| --- | --- |
| Same logical evidence processed twice | One snapshot; second result identifies the same snapshot with `created=False` |
| Same evidence supplied in a different order | Same canonical payload, IDs, status, uncertainty, recency, and links |
| Two independent workers process the same update concurrently | Exactly one row set is created; both receive the same complete snapshot; no partial estimates/links |
| Two workers propose different successors to the same head | At most one becomes the next head; the loser receives a bounded conflict or rebuilds once from the winner; no fork |
| Later evidence supports or contradicts an estimate | A new full snapshot points to the old head; old rows and links remain unchanged |
| Mixed supporting and contradicting evidence | `UNCERTAIN`, all links retained, latest evidence timestamp retained |
| One misconception signal | Remains uncertain and explicitly possible, never a diagnosis |
| Hint/access/feedback/transfer event without adjudication | Records the appropriate observation only; does not claim understanding, improvement, dependence, or successful transfer |
| Rule-based estimate is `SUPPORTED` | Teaching view still says `validated=False` and `UNVALIDATED_RULE_ESTIMATE` |
| Missing/out-of-scope/duplicate/reclassified evidence | Fail closed; create no snapshot and do not alter evidence |
| Provider failure or missing required review | Return the bounded state and leave all histories unchanged |
| Teaching consumer reads current state | Receives complete scope, versions, uncertainty, recency, reasons, and relation-bearing evidence links |

For the concurrency proof, assert database counts for snapshots, estimates, and evidence links in addition to returned values. Reopen a fresh session after workers finish to avoid identity-map artifacts. Assert there is exactly one current head (a snapshot not referenced as a predecessor), a linear predecessor chain with monotonically increasing record versions, and no duplicate dimension per snapshot.

## Definition-of-Done traceability

- **“Define how observations support or contradict an estimate”**: the versioned rule table and its table-driven tests define eligible evidence, relation meaning, thresholds, and prohibited shortcuts.
- **“Connect one controlled update path”**: the build module's single update interface owns evidence resolution through validated snapshot return.
- **“Keep understanding, possible misconceptions, assistance, response to feedback, and transfer distinct”**: stable dimensions, explicit eligibility rules, and one-estimate-per-dimension validation prevent conflation.
- **“Preserve prior snapshots, uncertainty, recency, rule versions, and evidence links”**: cumulative append-only payloads and complete teaching views expose and test each field.
- **“Concurrent or repeated processing creates consistent snapshots”**: deterministic canonical identities, optimistic predecessor checks, uniqueness-race recovery, and real multi-session tests prove consistency.
- **“Produce validated snapshots for teaching services”**: fail-closed hydration returns only complete, scoped, provenance-rich views; “validated” here means structurally validated for consumption, not empirically validated inference quality.
- **“Tasks 22 and 23 must demonstrate decisions that change because of an estimate”**: Task 18 supplies the stable current-snapshot interface and a fake-consumer contract proof; the production decision demonstrations remain acceptance requirements of Tasks 22 and 23.
- **“Rule-based uncertainty remains labelled as an unvalidated estimate until tested”**: every rule-derived view carries mandatory `validated=False` and `UNVALIDATED_RULE_ESTIMATE`, independent of inference status.

## Non-goals and implementation cautions

- Do not infer formal grades, criterion outcomes, diagnoses, misconduct, protected traits, fixed ability, or learning style.
- Do not read protected artifact content merely to infer correctness; correctness/support relations require an authorized, versioned adjudication.
- Do not treat `SUPPORTED` as “validated,” and do not convert uncertainty into a learner score or mastery percentage.
- Do not mutate or delete prior snapshots, estimates, evidence, or links.
- Do not let caller-supplied random IDs or wall-clock timestamps determine replay identity.
- Do not create a public write route for arbitrary support/contradiction relations.
- Do not couple the learner-model repository to continuation, tutor, assessment, or frontend modules. Those modules consume the teaching-facing interface in later tasks.
