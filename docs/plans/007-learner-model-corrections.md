# 007: Learner evidence annotations and model corrections

Status: proposed

Owner: Raveen

Created: 2026-08-24

Target branch: `raveen-person-b-learning-intelligence`

## Outcome

Add a small, backend-first correction slice that lets a learner annotate their own immutable
learning evidence or challenge a learner-model inference, and lets the assigned educator record
an append-only review outcome. Accepted corrections will be linked to a later learner-model
snapshot without rewriting the original evidence, inference, or any formal assessment result.

This plan deliberately stops at isolated backend contracts, persistence, services, and API
exports. It does not build the later evidence-timeline UI, recommendation engine, misconception
lifecycle, cohort analytics, formal-result review, or shared application-shell integration. The
plan plus its six implementation steps are intended to form approximately seven small commits.

## Source evidence

| Claim or rule | Evidence | Requirement |
| --- | --- | --- |
| Learner-model information is evidence-linked, uncertainty-aware, versioned, non-diagnostic, and separate from formal results. | `docs/01-implementation-requirements.md:400`; `src-main/backend/app/services/learner_model/contracts.py:LearnerModelSnapshotPayload`; `src-main/backend/app/services/learner_model/repository.py:74` | FR30, NFR27, NFR31, AC15 |
| Learners must be able to correct or annotate misleading evidence or learner-model information while the original and review history remain available. | `docs/01-implementation-requirements.md:432`; `docs/01-implementation-requirements.md:505`; `docs/01-implementation-requirements.md:553` | FR37, PD8, BP7, AC14 |
| Educators must be able to inspect and correct learner-model information, and material actions must be audited. | `docs/01-implementation-requirements.md:436`; `docs/01-implementation-requirements.md:952` | FR38, NFR20, AC16 |
| The approved Person B sequence names learner annotation and educator correction as the next unfinished learner-model step. | `docs/plans/001-person-b-platform-implementation.md:670-698` | FR30, FR37, PD8, BP7, NFR20, AC14, AC15 |
| Evidence and learner-model storage are append-only and already retain course, learner, outcome, correlation, version, and time metadata. | `src-main/backend/app/models/learning_evidence.py:LearningEvidence`; `src-main/backend/app/models/learner_model.py:49`; `src-main/backend/migrations/versions/20260816_0019_learning_evidence.py`; `src-main/backend/migrations/versions/20260816_0020_learner_model.py` | FR19, FR29, FR30, NFR17 |
| The current deterministic builder preserves old snapshots and creates a later snapshot for contradicting evidence, but it has no correction input or correction linkage. | `src-main/backend/app/services/learner_model/builder.py:DeterministicLearnerModelBuilder`; `src-main/backend/tests/test_learner_model.py:152` | FR30, PD8, NFR27 |
| Separate correction states and privacy-bounded audit action names already exist, but no correction records or service use them. | `src-main/backend/app/domain/platform_enums.py:60`; `src-main/backend/app/services/evidence/safety.py:32`; repository search found no correction model, repository, or API | FR37, PD8, NFR20 |
| Existing learner-model tests cover evidence scope, idempotency, immutable history, uncertainty, provider failure, and non-diagnostic safety only. | `src-main/backend/tests/test_learner_model.py:99-375`; `src-main/backend/tests/test_learner_model_safety.py:61-107` | FR30, NFR27, NFR31, AC15 |

## Current-state trace

1. Trusted server adapters create strict `EvidenceRecord` values and the evidence service checks an
   injected access policy before atomically storing protected content, metadata, and links.
2. `SqlAlchemyEvidenceRepository` returns metadata-only timeline references by default and exposes
   protected artefacts only through a separate authorised read.
3. `LearnerModelBuildService` loads explicitly requested, in-scope evidence through
   `SqlAlchemyLearnerModelRepository.observations`, creates a deterministic snapshot, and stores the
   snapshot, estimates, and evidence links append-only.
4. A single weak misconception or independence signal remains uncertain, and contradicting later
   evidence creates a new snapshot rather than mutating earlier history.
5. `CorrectionAction` already separates `ANNOTATED`, `ACCEPTED`, `REJECTED`, and `NEEDS_REVIEW`
   from learner assessment results. No ORM model, migration, contract, repository, service, or
   route currently persists or exposes these actions. This behaviour is `MISSING`.
6. Current access code can prove student enrolment and educator course ownership, but no
   correction-specific policy currently enforces learner self-scope or educator review scope. This
   behaviour is `MISSING`.
7. Existing audit abstractions reserve learner-annotation and educator-correction action names,
   but no production correction path emits them. Central audit integration remains `PARTIAL`.
8. The implementation gap matrix still describes the pre-merge absence of the learner-model
   foundation. Its FR30, NFR27, and AC15 rows are stale and must be updated only with proof from the
   completed slice.
9. Targeted baseline tests were `NOT RUN`: `uv` is unavailable in the current host shell. The
   exact attempted command was
   `uv run --frozen pytest -q tests/test_learner_model.py tests/test_learner_model_safety.py`.

## Proposed design

Use two append-only records plus one append-only linkage:

```text
immutable evidence or estimate
           |
           v
learner annotation ----> educator review history
                                  |
                         accepted review only
                                  v
                     later learner-model snapshot
```

- A learner annotation targets exactly one in-scope `LearningEvidence` or
  `LearnerOutcomeEstimate`. It stores protected note text in the authorised learning record, but
  only a digest and opaque identifiers are emitted to general audit metadata.
- An educator review targets one annotation and records `ACCEPTED`, `REJECTED`, or
  `NEEDS_REVIEW`. Each review references the previous review version so stale requests fail rather
  than overwrite newer history.
- Exact idempotent replay returns the existing record. Reusing an idempotency key with different
  content returns a conflict.
- An accepted correction does not reverse the meaning of evidence automatically. The next model
  rebuild marks the affected inference `NEEDS_REVIEW`, retains the original evidence links, and
  appends a correction-to-snapshot link. A replacement inference needs fresh evidence or an
  educator-authored later snapshot.
- Rejected and pending annotations remain visible in correction history but do not change model
  output. Learner-authored note text is untrusted context and is never fed into the deterministic
  inference rules.
- Correction status is not a submission state, Quality Judge decision, progress state, or formal
  `PASS`/`INCOMPLETE` result. The correction service has no assessment-result mutation port.
- The isolated API router is exported for later bounded integration. This slice does not edit the
  shared application router, generated contracts, `App.tsx`, or frontend shared types.

## Step 1: Add strict correction contracts

Files:

- New `src-main/backend/app/services/learner_model/correction_contracts.py`
- `src-main/backend/app/domain/platform_enums.py` only if an additional target-kind enum is needed
- New `src-main/backend/tests/test_learner_model_correction_contracts.py`

Changes:

- [x] Define frozen, extra-forbid learner-annotation and educator-review commands and read models.
- [x] Require one target kind, opaque/versioned identifiers, course/learner/outcome scope,
  correlation ID, actor, timestamp, idempotency key, and bounded note or reason text.
- [x] Reuse `CorrectionAction` while preventing learner annotations from claiming educator review
  actions and preventing reviews from claiming `ANNOTATED`.
- [x] Reject formal-result, numeric-score, research-condition, diagnosis, demographic, and unknown
  fields.
- [x] Treat learner note text as protected untrusted content rather than model evidence.

Edge and failure cases:

- Empty, oversized, timezone-naive, multi-target, unsupported-action, or unsafe extra-field
  payloads fail validation before persistence.

**Acceptance:** `test_learner_model_correction_contracts.py` proves strict shapes, action/target
rules, privacy boundaries, and rejection of assessment, research, and diagnostic fields.

## Step 2: Add append-only correction persistence

Files:

- `src-main/backend/app/models/learner_model.py`
- New `src-main/backend/migrations/versions/20260824_0022_learner_model_corrections.py`
- `src-main/backend/app/core/readiness.py`
- `src-main/backend/tests/test_learner_model_corrections.py`
- `src-main/backend/tests/test_migrations.py`

Changes:

- [x] Add append-only learner annotation, educator review, and correction-snapshot link models.
- [x] Enforce exactly one evidence-or-estimate target, same-scope foreign keys, version ordering,
  idempotency, review ancestry, and allowed action checks.
- [x] Add learner/outcome timeline, target, annotation review-history, correlation, and idempotency
  indexes.
- [x] Add SQLite update/delete triggers for all correction tables.
- [x] Add a forward revision from current head `20260816_0021` and advance the readiness pin.
- [x] Refuse destructive downgrade when correction data exists; require verified backup recovery.

Edge and failure cases:

- Cross-course targets, orphan reviews, duplicate versions, direct updates/deletes, partial schema,
  and populated downgrade are rejected without changing existing evidence or snapshots.

**Acceptance:** model and migration tests prove clean and legacy upgrade, repeat-safe upgrade,
constraints, append-only triggers, zero existing-record loss, empty downgrade, and populated
downgrade refusal.

**Verification (2026-08-24):** Ruff passed for all changed Python files. The learner-model,
deployment-runtime, and full migration selection passed with 82 tests; one Python 3.12 SQLite
datetime-adapter deprecation warning remains upstream of this change.

## Step 3: Implement scoped correction repository and service

Files:

- `src-main/backend/app/services/learner_model/repository.py`
- New `src-main/backend/app/services/learner_model/corrections.py`
- `src-main/backend/app/services/learner_model/safety.py`
- `src-main/backend/tests/test_learner_model_corrections.py`

Changes:

- [x] Add repository operations for annotation creation, review creation, exact replay, correction
  history, latest-review lookup, and accepted-correction lookup.
- [x] Validate target and reviewer scope in the repository even when the caller supplies a
  permissive policy.
- [x] Implement learner self-scope and assigned-educator course-scope policies from current
  enrolment/course data.
- [x] Require optimistic latest-review version checks and return a typed stale-review conflict.
- [x] Return non-enumerating not-found behaviour for missing and inaccessible targets.

Edge and failure cases:

- Cross-learner, cross-course, inactive, stale, conflicting replay, and concurrent duplicate
  requests create no partial correction history.

**Acceptance:** service/repository tests prove learner self-scope, educator course scope,
non-enumeration, exact replay, conflicting replay, optimistic concurrency, and atomic history.

**Verification (2026-08-24):** Ruff passed for the correction repository, service, safety module,
and tests. The learner-model, deployment-runtime, and full migration selection passed with 86
tests; the existing Python 3.12 SQLite datetime-adapter deprecation warning remains.

## Step 4: Make later snapshots respect accepted corrections

Files:

- `src-main/backend/app/services/learner_model/builder.py`
- `src-main/backend/app/services/learner_model/repository.py`
- `src-main/backend/tests/test_learner_model_corrections.py`
- `src-main/backend/tests/test_learner_model.py`

Changes:

- [x] Resolve accepted correction reviews for evidence and estimates used by a new build command.
- [x] Preserve the previous snapshot and original evidence links unchanged.
- [x] Emit a later `NEEDS_REVIEW` estimate for the affected dimension rather than silently
  reversing, deleting, or replacing the earlier inference.
- [x] Store the accepted-review-to-new-snapshot link atomically with the new snapshot.
- [x] Ensure rejected or pending reviews do not change deterministic output.

Edge and failure cases:

- A correction accepted after a build starts creates a version conflict or later rebuild; it never
  changes the in-flight snapshot silently. Provider failure leaves evidence, corrections, and old
  snapshots unchanged.

**Acceptance:** deterministic tests prove accepted, rejected, pending, stale, and provider-failure
paths; the original snapshot remains byte-for-byte retrievable and the later snapshot links the
accepted correction.

**Verification (2026-08-24):** Ruff passed for the changed builder, repository, and correction
tests. The learner-model, safety, correction-contract, deployment-runtime, and migration selection
passed with 92 tests; the existing Python 3.12 SQLite datetime-adapter deprecation warning remains.

## Step 5: Add privacy-bounded audit events

Files:

- `src-main/backend/app/services/learner_model/corrections.py`
- `src-main/backend/app/services/evidence/safety.py`
- `src-main/backend/tests/test_learner_model_corrections.py`
- `src-main/backend/tests/test_evidence_privacy.py`

Changes:

- [ ] Emit the existing learner-annotation and educator-correction action names through an
  injected audit sink after authoritative correction persistence.
- [ ] Include action, outcome, correlation, schema/version, and opaque actor/resource
  fingerprints only.
- [ ] Keep learner note, educator reason, direct learner identity, evidence text, inference text,
  and exception details out of general audit metadata.
- [ ] Make audit failure visible as bounded operational state without rolling back accepted
  correction history.

Edge and failure cases:

- Audit sink and pseudonymisation failures cannot erase an accepted annotation or review and
  cannot leak their exception text to callers.

**Acceptance:** privacy tests inspect success, failure, replay, and fallback audit events and find
no protected note, reason, direct identity, evidence content, or raw exception text.

## Step 6: Export isolated correction APIs and close the slice

Files:

- New `src-main/backend/app/api/routes/learner_model_corrections.py`
- New `src-main/backend/app/api/learner_model_correction_dependencies.py`
- New or updated `src-main/backend/app/api/person_b_router.py`
- New `src-main/backend/tests/test_learner_model_corrections_api.py`
- `docs/learnlens/implementation-gap-matrix.md`
- This plan

Changes:

- [ ] Add learner annotation, educator review, and authorised correction-history endpoints.
- [ ] Map missing/inaccessible targets to the same non-enumerating response, stale versions to
  `409`, invalid contracts to `422`, and safe persistence failure to `503`.
- [ ] Apply current request-security and rate-limit controls to mutating endpoints.
- [ ] Export the isolated router without mounting it in the shared application router.
- [ ] Add API integration tests and update only gap-matrix rows supported by current proof.
- [ ] Record exact completed checks and all remaining UI/integration limitations in this plan.

Edge and failure cases:

- Another learner cannot discover whether a target exists. An out-of-course educator is denied.
  Repeated requests are idempotent, stale reviews do not overwrite, and safe errors expose no
  notes, identifiers, stack traces, or database details.

**Acceptance:** API tests prove learner self-access, educator course access, cross-scope denial,
idempotency, stale conflict, safe errors, correction history, and unchanged formal results; the
gap matrix cites exact current files and tests without claiming the later UI complete.

## Full verification

Run targeted checks after the step that introduces each behaviour:

```zsh
cd src-main/backend
uv run --frozen pytest -q tests/test_learner_model_correction_contracts.py
uv run --frozen pytest -q tests/test_learner_model_corrections.py tests/test_learner_model.py
uv run --frozen pytest -q tests/test_learner_model_corrections_api.py tests/test_evidence_privacy.py
uv run --frozen pytest -q tests/test_migrations.py
uv run --frozen ruff check app/services/learner_model app/models/learner_model.py app/api tests/test_learner_model_correction_contracts.py tests/test_learner_model_corrections.py tests/test_learner_model_corrections_api.py
uv run --frozen ruff format --check app/services/learner_model app/models/learner_model.py app/api tests/test_learner_model_correction_contracts.py tests/test_learner_model_corrections.py tests/test_learner_model_corrections_api.py
```

Then run the applicable repository release checks from `.github/workflows/quality.yml`:

```zsh
cd src-main/backend
uv lock --check
uv sync --frozen --all-extras
uv run --frozen ruff check .
uv run --frozen ruff format --check .
APP_ENV=test DATABASE_URL=sqlite:///./ci-tests.db LEARNING_EVENT_PSEUDONYM_SECRET=ci-only-pseudonym-secret-32-bytes-minimum uv run --frozen pytest --cov=app.services --cov-report=term-missing --cov-fail-under=80
APP_ENV=test LEARNING_EVENT_PSEUDONYM_SECRET=ci-only-pseudonym-secret-32-bytes-minimum uv run --frozen pytest tests/test_migrations.py
APP_ENV=test LEARNING_EVENT_PSEUDONYM_SECRET=ci-only-pseudonym-secret-32-bytes-minimum uv run --frozen python scripts/export_openapi.py --check
APP_ENV=test LEARNING_EVENT_PSEUDONYM_SECRET=ci-only-pseudonym-secret-32-bytes-minimum uv run --frozen python scripts/generate_frontend_contracts.py --check
```

For this plan-only commit, run:

```zsh
git diff --check
rg -n '^## (Outcome|Source evidence|Current-state trace|Proposed design|Step [1-6]|Full verification|Migration and rollback|Risks and controls|Missing-data report|PR mapping)' docs/plans/007-learner-model-corrections.md
```

The frontend, browser, manual accessibility, hosted, load, cost, external evaluator, and user-study
checks are `NOT APPLICABLE` to this backend-only slice. They remain required for later UI,
integration, and pilot-readiness claims.

## Migration and rollback

- Add forward migration `20260824_0022` from verified current head `20260816_0021`.
- Upgrade creates empty correction tables and append-only triggers; it does not rewrite learning
  evidence, learner-model snapshots, assessment decisions, or audit history.
- Tests record pre/post row counts and foreign-key checks for existing evidence/model fixtures.
- Empty correction tables may downgrade to `20260816_0021` for migration testing.
- Populated correction history blocks destructive downgrade before schema changes. Recovery uses a
  verified database backup or a forward corrective migration; no automated history deletion is
  planned.
- The shared application does not read correction records until the isolated router is integrated,
  so rollback of unmounted application code is removal of the isolated module while retaining the
  append-only database history.

## Risks and controls

| Risk | Impact | Control and proof |
| --- | --- | --- |
| A correction mutates or deletes original evidence/inference. | Destroys the learning history and makes decisions unreproducible. | Append-only tables/triggers, immutable contracts, foreign-key links, and before/after history tests. |
| Learner note text becomes model input. | Prompt injection or unsupported learner claims could alter inference. | Treat note as protected untrusted content; builder consumes only typed correction state and opaque IDs. |
| A stale educator action overwrites a newer review. | Loses review history and educator intent. | Prior-review/version precondition, `409` conflict mapping, and concurrent review tests. |
| A cross-course actor can discover or change model data. | Privacy and authorisation breach. | Service/repository scope checks, non-enumerating errors, and cross-learner/course tests. |
| Accepted correction silently creates a new learner claim. | Replaces one unsupported inference with another. | Move affected dimension to `NEEDS_REVIEW`; require fresh evidence or explicit educator-authored later state. |
| Correction state is confused with assessment result. | Could change a formal `PASS`/`INCOMPLETE` outside assessor control. | Separate contracts/tables/enums, architecture/import tests, and no assessment mutation port. |
| Audit failure rolls back accepted learning history or leaks notes. | Data loss or privacy breach. | Correction persistence remains authoritative; audit uses bounded fingerprints and failure tests. |
| Gap-matrix updates overclaim the slice. | Misstates pilot readiness. | Update only rows with exact code/test/runtime proof; keep API mounting and UI `MISSING` or `PARTIAL`. |

## Missing-data report

| Missing decision or evidence | Owner | Blocking effect |
| --- | --- | --- |
| `uv` is unavailable in the current shell, so the existing learner-model baseline was not rerun during planning. | Development environment owner | Does not block the written plan; blocks implementation handoff until locked targeted and migration checks can run. |
| Shared router and frontend integration ownership remains reserved for the later Person A/Person B handoff. | Person A and Person B | Does not block isolated service/API implementation; correction endpoints are not user-reachable until the bounded integration step is approved. |
| No retention/deletion duration is approved for learner annotations and correction history. | Product/privacy governance | Does not block append-only creation; blocks any purge, destructive downgrade, or retention automation. |

No hidden evidence-count, grading, reassessment, or diagnostic policy is introduced by this plan.

## PR mapping

The implementation PR must mirror all six steps, checklist items, acceptance lines, verification
results, risks, and open items. Suggested commit mapping:

1. `docs(plans): add plan 007 learner model corrections [skip ci]`
2. `feat(learner-model): add correction contracts`
3. `feat(learner-model): persist append-only corrections`
4. `feat(learner-model): add scoped correction service`
5. `feat(learner-model): link accepted corrections to snapshots`
6. `feat(learner-model): audit correction actions safely`
7. `feat(learner-model): expose isolated correction APIs`

Each implementation commit must include the tests for the behaviour it introduces. The branch
must remain draft and must not request human review until the required test and local-review gates
pass on the current head.
