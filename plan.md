# Task 19: Integrate Learner Corrections and Scoped Evidence/Model Views

## Goal and completion boundary

Deliver one integrated, authorised workflow in which:

1. a learner can inspect their own evidence and learner-model estimates;
2. the learner can annotate evidence or challenge an estimate without changing the original;
3. an authorised educator for that course can inspect the same history and append a reasoned review outcome;
4. an accepted review is carried into a later full learner-model snapshot as `NEEDS_REVIEW`, with explicit links to the review and the unchanged original evidence/estimate; and
5. both roles can see the ordered evidence, estimate, annotation, review, and later-snapshot history through mounted application routes and accessible screens.

Task 19 does not change a formal assessment result, infer a replacement learner claim from free text, implement reassessment, build cohort analytics, or introduce adaptation policy. Formal assessment corrections remain in the assessment review workflow. Learner notes and educator reasons are protected learning records and are never inference inputs or general audit payloads.

## Grounded current state

- Tasks 17 and 18 are present on `main`. Task 17 stores live, ordered, immutable evidence. Task 18 exposes a deterministic `LearnerModelBuildService.update(...)` seam, cumulative append-only snapshots, optimistic head handling, complete current/timeline views, relation-bearing evidence links, and explicit `UNVALIDATED_RULE_ESTIMATE` labelling.
- The real Alembic head is now `20260907_0031`, not the `20260821_0022` head named in the original Task 19 description. Task 19 must add one new linear revision from `20260907_0031` and advance the readiness pin.
- The remote branch named in the task is no longer available locally, but its recovered commit `fda2459fdb6f529f933e48494f9f39787d420d2e` is readable. Its diff contains correction contracts, three append-only models, a migration, repository/service logic, privacy-bounded auditing, correction-aware build behavior, and extensive tests. It contains no mounted routes or frontend screens.
- The recovered implementation predates the completed Task 18 module. Its contracts, schema constraints, access cases, audit privacy rules, and failure scenarios are reusable. Its large edits to `builder.py` and `repository.py` must be ported behavior-by-behavior onto current `main`, not cherry-picked or copied wholesale.
- `src-main/backend/app/api/router.py` currently mounts no evidence, learner-model, or correction routes. The frontend has authenticated student and educator workspaces but no evidence/model timeline feature.

## Domain and architecture decisions

### Keep observation, estimate, annotation, review, and result separate

- **Evidence** is the immutable observation from Task 17.
- **Estimate** is the immutable, evidence-linked inference from Task 18.
- **Learner annotation** is the learner's protected statement that evidence or an estimate may be inaccurate or needs context.
- **Educator correction review** is an append-only `ACCEPTED`, `REJECTED`, or `NEEDS_REVIEW` decision with a reason and prior-review/version precondition.
- **Formal assessment result** is outside this module and cannot be read or mutated through a correction command.

The learner does not directly change an estimate. An accepted review does not reverse an evidence relation or manufacture a replacement estimate. The next controlled model update retains the original evidence links, appends a new full snapshot, marks the affected dimension `NEEDS_REVIEW`, and links the accepted review to that snapshot. Fresh trusted evidence or a future explicitly governed authoring path is required to support a different inference.

### Use two deep application modules

Keep a small correction command interface for annotation, educator review, and history reads. Put target validation, self/course scope, idempotency, optimistic review ancestry, non-enumeration, audit privacy, and transaction handling behind that interface.

Keep evidence/model projection behind a separate read interface. It owns scoped pagination, deterministic ordering, protected-content filtering, timeline composition, and mapping ORM data to role-safe response contracts. Routes and React screens consume these interfaces; they must not assemble correction state from ORM rows or duplicate authorisation logic.

### Authorisation and disclosure rules

- A learner may read and annotate only records belonging to their active identity and course enrolment.
- An educator may read/review only learners in a course for which their current assignment grants the required teaching authority. Assessor authority alone must not be silently treated as learner-model correction authority unless the existing assignment model explicitly grants both.
- Missing and inaccessible learner, evidence, estimate, annotation, and review targets use the same non-enumerating response.
- Timeline summaries expose evidence metadata and provenance, not protected response/artefact content. If an existing authorised artefact-read seam is used, expose it as an explicit secondary action rather than embedding content in list responses.
- All reads return `Cache-Control: no-store`; writes use the existing authentication, CSRF/request-security, correlation-ID, rate-limit, and sanitised-error conventions.

## Reuse strategy for recovered work

Before implementation, extract the recovered versions with `git show fda2459:<path>` and compare each against current `main`.

Reuse with adaptation:

- strict, frozen correction contract shapes and banned-field checks;
- target-kind and correction-action enum separation;
- annotation, review-history, and review-to-snapshot persistence concepts;
- exactly-one-target, same-scope foreign keys, idempotency, review ancestry, append-only triggers, and populated-downgrade guard;
- self-scope/course-scope, non-enumeration, exact replay, stale review, and concurrency scenarios;
- privacy-bounded audit metadata and failure behavior;
- accepted/rejected/pending correction semantics.

Do not transplant:

- the recovered migration revision identifiers or old readiness pin;
- recovered wholesale `builder.py`/`repository.py` changes that would replace Task 18 cumulative snapshots, deterministic identities, current-head checks, hydration validation, or race recovery;
- old assumptions about evidence selection, estimate view fields, or application wiring;
- its backend-only stopping boundary.

## Implementation plan

### 1. Characterise and protect the Task 17/18 baseline

- Run the existing evidence, learner-model, safety, migration, deployment-readiness, and generated-contract checks before editing.
- Add narrow regression tests that freeze Task 18's current view, cumulative snapshot, replay, conflicting-head, and protected-history behavior.
- Inventory current course-role helpers and select one canonical policy for educator correction authority; do not create a second interpretation in route code.

### 2. Port strict correction contracts

Add correction request/read contracts under the learner-model schema/module conventions used on current `main`:

- target exactly one evidence ID or estimate ID;
- include course, learner, outcome, correlation, idempotency, actor, and timezone-aware occurrence metadata;
- learner commands permit only `ANNOTATED` with a bounded note;
- educator commands permit only `ACCEPTED`, `REJECTED`, or `NEEDS_REVIEW`, require a bounded reason, and include the expected latest review version/ID;
- reject numeric results/scores, diagnoses, demographic/research fields, arbitrary support/contradiction relations, unknown fields, empty notes, and oversized text.

Keep public request schemas actor-free where identity must come from the authenticated request; build the internal command server-side.

### 3. Add one reconciled append-only migration

Create a newly numbered migration, expected to be `20260908_0032_learner_model_corrections.py`, with `down_revision = "20260907_0031"` after rechecking the head immediately before implementation.

Add:

- learner annotations targeting exactly one scoped evidence row or estimate row;
- educator correction reviews linked to an annotation and optional previous review;
- accepted-review-to-later-snapshot links;
- unique idempotency receipts, monotonic review versions, same-scope composite foreign keys, target/history/correlation indexes, and action/shape checks;
- SQLite append-only update/delete triggers matching the repository's supported database behavior.

The upgrade is additive and must not rewrite Task 17 evidence, Task 18 snapshots/estimates/links, or assessment history. Downgrade is permitted only when all three new tables are empty; otherwise it fails before dropping anything. Update ORM exports and readiness only after migration tests pass.

### 4. Port and deepen the correction module

Implement annotation, review, and history operations behind one correction interface:

- validate target existence and complete scope again in persistence, even after policy checks;
- store annotation/review plus idempotency receipt atomically;
- return exact replay without appending; reject key reuse with different content;
- append educator reviews using the latest-review precondition; stale or concurrent losers return a typed conflict and never overwrite;
- order history deterministically by version/time plus ID;
- map missing and unauthorised targets to one typed non-enumerating outcome;
- emit audit events only after authoritative persistence, containing action/outcome, opaque fingerprints, correlation, and schema version—not note/reason text, direct identity, evidence content, inference text, exception text, or assessment data;
- preserve the stored correction if the general audit sink fails, while returning/recording a bounded operational audit status.

### 5. Integrate accepted corrections into the current Task 18 update seam

Extend the existing `LearnerModelBuildService.update(...)` orchestration minimally:

- resolve accepted, not-yet-linked reviews relevant to the cumulative evidence/estimates in the proposed build;
- include the canonical accepted-review set in deterministic logical identity and exact-replay comparison;
- verify the correction head has not changed between resolution and append;
- for each affected existing dimension, produce `NEEDS_REVIEW` in the later complete snapshot while retaining the original estimate and all original evidence relations in prior history;
- insert review-to-snapshot links atomically with the new snapshot;
- do not append when neither evidence nor applicable correction state changes;
- keep rejected and pending reviews visible in history but behaviorally inert;
- preserve Task 18's one-linear-head, bounded retry, validation label, and provider-failure guarantees.

Add a regression for an annotation/review accepted after a build begins: the in-flight build must conflict or omit it and a later retry must create the correction-aware successor; it must never change the already-built snapshot silently.

### 6. Add scoped projection and correction routes

Mount a learner-model/evidence router in `app/api/router.py` with typed endpoints along these lines (final paths should follow existing naming conventions):

- `GET /learner-model/me/timeline` — learner's paginated evidence, estimates, corrections, and snapshot transitions;
- `POST /learner-model/me/annotations` — annotate/challenge own evidence or estimate;
- `GET /courses/{course_id}/learners/{learner_id}/learner-model/timeline` — authorised educator view;
- `POST /courses/{course_id}/learners/{learner_id}/learner-model/annotations/{annotation_id}/reviews` — append educator outcome.

Use stable cursor pagination based on the deterministic timeline order, with a bounded page size and opaque cursor. Return observation, inference, annotation, educator review, and snapshot transition as distinct typed entries. Estimate entries include dimension, inference status, numeric uncertainty, reason code, evidence recency, evidence relations, rule/model/source versions, and the mandatory validation classification. A missing estimate is “not enough evidence,” never zero.

Map exact replay to `200`, new creation to `201`, stale/idempotency conflict to `409`, invalid contracts to `422`, non-enumerating misses to `404`, request-security/rate-limit failures through existing mappings, and bounded persistence failure to `503`.

### 7. Generate contracts and build learner/educator screens

- Export OpenAPI and regenerate frontend contracts through repository scripts; do not hand-maintain duplicate wire types.
- Add an isolated evidence/learner-model feature with an API adapter, timeline mapper, learner view, educator view, annotation form, and review form.
- Mount the learner page in the authenticated student workspace and the educator page from a selected learner in the educator workspace, guarded with the existing non-enumerating route posture.
- Present observation, estimate, annotation, review, and later snapshot as visibly and semantically different entries. Colour is supplementary only.
- Explain uncertainty and the `UNVALIDATED_RULE_ESTIMATE` label in plain language. Never render uncertainty as mastery, probability of passing, ability, risk, or a numeric grade.
- Show the original evidence/estimate beside its challenge history; never visually replace it with the latest review.
- Support loading, empty, partial/no-estimate, validation error, conflict-refresh, unauthorised/not-found, and retryable server-error states.
- After a `409`, retain the user's draft, refresh history, and require an explicit resubmission against the new version.
- Meet keyboard, focus, label, live-region, reflow, and screen-reader requirements. Forms must expose remaining/maximum text length and associate field errors programmatically.

### 8. Prove recovery, integration, and no regression

Run focused tests first, then the repository quality gates. Record exact commands and outcomes in a Task 19 evidence note, and update requirement/gap documentation only for behavior actually proven.

## Test and acceptance matrix

| Scenario | Required proof |
| --- | --- |
| Learner reads own history | Ordered scoped timeline includes evidence, estimates, uncertainty, provenance, correction history, and later snapshots without protected artefact leakage. |
| Learner reads/annotates another learner | Same non-enumerating response as a missing target; no row or audit detail leaks. |
| Educator reviews in assigned course | Append-only outcome with actor, reason, time, correlation, and review ancestry is visible to learner and educator. |
| Educator reviews outside scope | Non-enumerating denial and no partial write. |
| Exact annotation/review replay | Same stored record returned; no duplicate history. |
| Reused key with different content | `409`; original record unchanged. |
| Two reviews race | At most one next version; loser gets stale conflict; both attempted reasons cannot overwrite each other. |
| Accepted correction | Later full snapshot is appended, affected dimension is `NEEDS_REVIEW`, originals remain byte-for-byte readable, and review-to-snapshot link exists. |
| Rejected/pending review | Visible in history; no model change. |
| Provider/build/audit failure | Evidence, corrections, and earlier snapshots remain durable; no partial successor and no protected data in errors/audit. |
| Formal assessment isolation | Correction paths cannot change assessment decisions, criterion decisions, `PASS`/`INCOMPLETE`, or review lifecycle. |
| Migration from current head | Upgrade preserves seeded protected evidence/model/assessment history and yields exactly one Alembic head. |
| Populated downgrade | Fails before any correction table/history is removed. |
| Protected-history recovery | Restore a pre-migration backup into a fresh database, upgrade to head, and prove original evidence/snapshots plus correction history checksums/counts and foreign keys. |
| Learner browser journey | Inspect estimate, read evidence/reason/uncertainty, submit challenge, see pending history, then see educator outcome and later snapshot. |
| Educator browser journey | Open an authorised learner, inspect the same evidence/model context, append a reasoned outcome, and handle a stale review safely. |
| Accessibility | Unit/Axe plus keyboard and reflow checks; status is not encoded by colour alone and dynamic updates are announced. |

## Migration and protected-history recovery procedure

1. Recheck `alembic heads`; stop if the expected predecessor changed and renumber/rebase the new revision.
2. Create a pre-upgrade database containing representative Task 17 evidence, a multi-version Task 18 snapshot chain, assessment protected history, and unrelated current tables.
3. Record row counts plus stable content digests for protected tables and make a recoverable database copy using the database-supported backup mechanism.
4. Upgrade to Task 19 head; assert all prior counts/digests, foreign-key integrity, append-only triggers, new empty tables, readiness, and exactly one head.
5. Add annotation/review/snapshot-link history; assert a downgrade refuses before schema mutation.
6. Restore the backup to a separate database, upgrade it to head, replay the correction commands, and assert the same protected-history digests and logically equivalent correction/snapshot history.
7. Test empty downgrade only as migration reversibility evidence. Production rollback is forward-fix or verified restore; it never deletes populated correction history.

## Verification commands

Use the repository's locked environment and current workflow commands. At minimum:

```zsh
cd src-main/backend
.venv/bin/pytest -q tests/test_learner_model.py tests/test_learner_model_safety.py tests/test_learner_model_correction_contracts.py tests/test_learner_model_corrections.py tests/test_learner_model_corrections_api.py tests/test_evidence_privacy.py
.venv/bin/pytest -q tests/test_migrations.py tests/test_deployment_runtime.py
.venv/bin/alembic heads
.venv/bin/ruff check app tests
.venv/bin/ruff format --check app tests
.venv/bin/python scripts/export_openapi.py --check
.venv/bin/python scripts/generate_frontend_contracts.py --check

cd ../frontend
npm test -- --run
npm run lint
npm run build
```

Run the new authenticated browser journeys in the repository's existing local E2E harness and then the full backend/frontend suites required by CI. Report environmental or unavailable checks as `NOT RUN`, never as passed.

## Definition of done

Task 19 is complete only when all of the following are true:

- mounted backend routes and mounted student/educator screens make the workflow reachable in the real application;
- learners can inspect and challenge only their own estimates/evidence;
- authorised educators can append reasoned reviews only within course scope;
- originals, review reasons, complete correction history, and later snapshots remain readable and linked;
- accepted corrections affect only a later controlled snapshot and cannot mutate evidence, prior estimates, or formal results;
- stale/replayed/concurrent requests have deterministic, tested outcomes;
- privacy-bounded auditing and sanitised errors expose no protected note/reason/content;
- OpenAPI and generated frontend contracts are current;
- accessibility and authenticated browser journeys pass;
- Alembic reports exactly one head; migration preservation, populated-downgrade refusal, and protected-history backup recovery are proven; and
- Task 17/18, assessment-history, readiness, and full relevant regression suites pass.

## Main risks and controls

| Risk | Control |
| --- | --- |
| Old branch overwrites newer Task 18 semantics | Port tests/contracts/schema concepts selectively; preserve the current update and repository interfaces. |
| Correction becomes an unsupported learner claim | Learner text remains untrusted; accepted review yields `NEEDS_REVIEW`, not a reversed relation or replacement inference. |
| Scope leak through timelines or identifiers | Authorise in policy and persistence, use non-enumerating responses, metadata-only lists, and cross-scope tests. |
| Review race loses history | Append-only versions, prior-review precondition, unique constraints, transaction rollback/reread, and two-session concurrency test. |
| Correction is confused with formal assessment | Separate contracts/tables/enums and architecture tests forbidding assessment mutation dependencies. |
| Migration forks current history | New revision from the rechecked actual head, readiness update, `alembic heads` gate, and migration-chain regression. |
| Rollback destroys learner challenges | Populated downgrade guard, forward-fix policy, verified backup/restore rehearsal, and checksum proof. |
| UI implies scientific certainty or fixed ability | Preserve uncertainty and validation labels, use neutral language, and test prohibited score/ability/result presentation. |
