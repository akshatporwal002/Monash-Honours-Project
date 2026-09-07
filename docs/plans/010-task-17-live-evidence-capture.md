# Task 17: Capture learning evidence through the live application

Status: grounded; implementation in progress
Branch: `feat/task-17-live-evidence-capture`
Base: `4081a62` (Task 16 merged)
Authorization: user requested this branch and Task 17 implementation.

## Evidence and scope

`LearnLens_Remaining_Tasks.md`, Task 17 requires an authorised ordered evidence
history from real learner actions, preserving original observations through retries
and partial failures. Tasks 9, 11 and 14 are merged. FR19, FR29, NFR16, NFR17 and
NFR20 control history, provenance, privacy, transactions and audit. Formal results
remain separate under the assessment specification.

`services/evidence/repository.py` already validates immutable records, artifacts,
links and replay but commits its own transaction. `LmsService` commits drafts,
checkpoints, support requests and submissions without writing learning evidence.
`SimulationEvidenceService.finish` owns the simulation-result transaction.
Episode response v1 preserves reasoning, explanation, reflection and transfer;
work starts freeze conditions, task approval, form and source references. Feedback
GET currently records analytics views but no operational evidence.

The old `.agents/instructions/core.md` and `.agents/workflows/change-delivery.md`
are absent from this base. Follow the user-supplied delivery sequence instead.

## Implementation

1. Add a caller-owned transaction option to evidence persistence; preserve existing
   standalone behavior. Source actions and evidence must commit together. Capture
   failure rolls back the current action, never earlier accepted history.
2. Add server-only live evidence construction from authoritative submissions,
   immutable checkpoints, approved support uses and simulation outcomes. Stable
   source-derived identities make replay safe. Keep exact protected content and
   frozen provenance, distinguish observations from inference, and link revisions
   and episode observations without importing formal result values.
3. Wire captures into existing write transactions. Preserve task/course access
   checks, approved support conditions and simulation recovery. No model updates,
   correction workflow, adaptive recommendations or research activation.
4. Add a bounded, read-only learner task evidence endpoint and an explicit feedback
   acknowledgement command wired to the feedback UI. Record acknowledgement as
   self-reported feedback use, never claim polling proves learning or reading.
5. Add real-service and mounted API tests for a complete episode, replay, revision,
   cross-scope denial, pagination, protected provenance, failure rollback and
   simulation recovery. Verify feedback acknowledgement through frontend tests.
6. Regenerate contracts; run appropriate backend/frontend checks, migration checks
   and browser verification where the environment supports them. Obtain independent
   test, standards and specification reviews; resolve findings and record limits.

## Design boundaries

The evidence writer participates in the source transaction instead of an
asynchronous best-effort call. Existing durable submission and simulation recovery
therefore remain authoritative. All identifiers, event kinds, timestamps and
provenance come from server records. A missing outcome must not be fabricated.
Historical artifacts keep lossless source references when source content exceeds
artifact bounds. Hints and accessibility support remain distinct. A revision link
means derived-from, not an inferred contradiction or changed assessment result.

## Verification and delivery

Test seams: existing LMS command API, simulation execution/recovery, the mounted
learner evidence API and feedback acknowledgement UI. Include repository transaction
regression coverage because existing standalone callers must retain their behavior.
No migration is intended: use existing evidence/artifact/link tables and their
append-only protections. Verify one existing Alembic head and migration regression.
Update Task 17 handoff and traceability only to the scope of verified evidence.
Human PR review is a later gate; no request while tests or local reviews are missing.

## Open limits

No live approval, hosted, screen-reader, learning-validity or performance claim is
made by this implementation. Task 18 owns model inference; Task 19 owns educator
corrections and wider model views. Report unavailable checks as NOT RUN.
