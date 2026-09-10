# Task 33 — research governance implementation

Status: technical implementation delivered; **production research remains closed**.
No institutional approval, recruitment, participant data, instrument, or study activation
is supplied by this work. The Task 32 protocol/data-plan drafts remain proposals.

## Checkout and scope

- Branch: `codex/task33-research-governance`.
- Actual starting commit: `27a397a66b5fb6544ba08d9c8950fbbc8c6b4ca4` on local `main`.
- Separate worktree: `C:/Users/Jordan.Tran/Downloads/Honours Project/Monash-Honours-Project/.tmp-task33/worktree`.
- `git status --short` was empty in that worktree before editing. The original
  checkout's uncommitted audit and parallel assignment files were read and preserved.
- Read the absolute original-checkout `docs/learnlens/main-audit-2026-09-10.md`,
  the required implementation/assessment/work-order files, settled Task 8 selections,
  Task 32 drafts, and existing research/access/export/worker/lifecycle code and tests.
- No GitHub access, fetch, push, merge, account integration, global Git configuration,
  shared dependency installation, CI change, or runtime configuration change.
  Commit identity is explicitly Jordan Tran
  `<226841807+jordann-trann@users.noreply.github.com>`.

## Implemented behaviour

`ResearchGovernanceService` interprets an append-only, typed governance ledger.
Every study has a monotonically increasing revision. Commands carry an expected
revision and actor-scoped request key; exact duplicates return the original receipt,
while conflicting reuse or concurrent revisions fail with a conflict. SQLite write
serialization keeps pair creation/finalization eligibility checks ordered with withdrawal.

The ledger records:

- Immutable study scopes: protocol/data-plan/consent/eligibility versions, exact courses,
  supported field paths and purposes, named processing researcher, validity window,
  withdrawal-rule reference, and authority-backed retention classes.
- Separate approval decisions: pending, approved, suspended, revoked, evidence and
  authority references, and effective/expiry times. Approval applies to an exact scope.
- Learner-self consent, refusal and withdrawal. Consent cannot be recorded by an educator
  or administrator on the learner's behalf. No approval, grant, or pseudonym is fabricated
  from enrolment. Re-consent authorizes future work only; it does not revive old cases.
- Eligibility attestations tied to the exact scope and rule version, with expiry and
  evidence references. Current user activation and course enrolment are additional checks.
- Researcher/study/course/field grants with expiry, revocation and recorded authority.
  Existing Task 5 `ScopedRole.RESEARCH` course permissions remain independently required.
  Ordinary analytics or administrator status never supplies a research export grant.
- Independent retention holds and releases, identified by record class and authority.
  The disposition service always denies destructive disposal. Missing schedules and overdue
  reviews are represented explicitly; no blanket retention period is invented.

Scopes require schedules for governance, identity mapping, technical pairs and export
audit. Other approved classes can be recorded. A new scope invalidates old approval,
consent, eligibility and grants until their new versions are supplied. An old-scope
withdrawal can still stop participation after an amendment.

The existing technical-pair processor has a fixed collection contract. It requires
**every** field in `PROCESSING_FIELDS`, including individual measurement columns and
explicit processing permissions for provider input, generated output, judge records,
source references, retrieval metadata and simulation references. A smaller approved
field set denies this processor; it does not silently collect extra fields. Optional
future reuse and delayed contact are unsupported and therefore not authorized.

## Processing and operational separation

`ConfiguredResearchEligibility` checks the release gate, configuration, a single
unambiguous approved study, participant scope and the named processing researcher's
current grants. The ordinary continuation intent is planned separately.

The outbox's default research adapter is `GovernedResearchJobRepository`. It resolves
the real immutable submission, task and workflow; rejects cross-course/task scope and
observations predating consent; and atomically commits the case binding and paired rows.
Existing unbound research rows are preserved and cannot receive retrospective consent.
Actor/submission pseudonyms use the existing HMAC abstraction with study-specific namespaces.
Identity-bearing consent records stay in the restricted ledger, outside analysis records.

The application worker's research passes check the unchanged closed production gate
before claiming research jobs. If later released, the wired baseline factory checks
current consent, eligibility, approval and processing grants before context retrieval,
before generation, before judgement and before saving a result. The context adapter
also checks workflow/submission/learner/task/course identity. A withdrawn or revoked
case cannot cause a later provider call or successful completion. A request already
sent to a provider cannot be recalled; revocation blocks subsequent stages and storage
of its result. Controlled denials retain a sanitized failure category.

Research conditions remain the existing paired **technical feedback** conditions.
No study-condition allocation, learner instrument, research response screen, or research
learner-model update is added. Tests create both technical conditions and compare every
non-research table before/after processing and consent transitions, including a
human-confirmed synthetic assessment. A separate real continuation-worker test proves
withdrawal does not stop ordinary model updates and approved activity suggestions.
PASS/INCOMPLETE, human confirmation, protected histories, supported conceptual hints
and separate unaided transfer are unchanged.

## API and export contract

- `POST /api/v1/research/governance/{study_id}/decisions`: authenticated, CSRF-protected
  typed commands; administrators record governance evidence, learners record only their
  own consent decisions. Responses explicitly report `production_active: false`.
- `GET /api/v1/research/governance/{study_id}/decisions`: administrator-only history,
  including recorded command, actor, revision and UTC timestamp.
- `GET /api/v1/research/governance/{study_id}/participation/{course_id}`: enrolled
  learner's own scope, consent and current revision, enabling a subsequent withdrawal.
- Existing `/api/v1/research/exports`: retains Task 5 authorization and the production
  gate. The default service additionally requires `study_id` and repeated exact `fields`
  query parameters, plus all study/course/consent/researcher permissions.

Governed output is `learnlens.research-export.v2`; filenames include `research-v2`.
JSON identifies `technical_feedback_pair` records and includes study/scope/export IDs,
requested fields and count. CSV contains exactly the requested approved columns, sorted
deterministically, with the existing UTF-8/BOM, quoting and formula protection.
The field dictionary is the scalar, non-processing members of `FieldPath` in
`app/schemas/research_governance.py`. Denied fields are omitted entirely, never null
placeholders. Quality scores are technical judge measures, not formal learner results.

Free-form output, judge prose, raw answers, drafts, prompts, source passages, arbitrary
nested data and direct identities are not v2 export fields. The existing v1 validation
and raw-response restrictions remain in place. There is no new raw rating-packet route.
Legacy v1 serializer helpers remain for compatibility and isolated mechanical tests;
the mounted production service uses governed v2.

An immutable export receipt records the scope, fields, courses, grant IDs, eligible
case/consent IDs, count and exclusion counts before any bytes. Preparation denial and
stream interruption are audited. All participants are rechecked before the header;
grants and participant eligibility are rechecked before each row. A changed permission
aborts the stream rather than releasing remaining data. Already-delivered bytes cannot
be recalled. Completion means the server iterator completed, not proof a recipient saved
the entire file. Download recipients are the authenticated, explicitly granted researchers;
downstream sharing and public disclosure remain separately approval-dependent.

## Data changes and restore

Forward migration `20260910_0045`, parent `20260910_0044`, adds only:

1. `research_governance_events` — restricted immutable commands and provenance.
2. `research_case_governance` — immutable study/consent/course/pseudonym case bindings.
3. `research_export_eligibility` — restricted immutable export manifests and outcomes.

There is no data backfill or approval seed. ORM and SQLite guards reject update, delete
and replacement. Unique keys protect revision/request replay. The migration is replayable,
matches model metadata, and has one head. Downgrade refuses populated governance history;
empty new tables can be removed. If an older migration then refuses to destroy its own
protected history, the database remains at `0044`, as the existing tests require.

Fresh migration tests compare existing table digests, foreign keys, replay and downgrade.
The existing verified-backup tool is reused to prove saved withdrawal and grant revocation
still deny use after a synthetic backup/restore. Restoring an older backup that predates a
withdrawal needs external reconciliation from the authoritative later governance record;
the closed release gate is the default quarantine, not a promise to reconstruct missing history.

## Verification

All commands run from this worktree's `src-main/backend` unless indicated otherwise.
The existing frozen Python 3.11.16 environment was reused without changes:

```powershell
$py = 'C:/Users/Jordan.Tran/Downloads/Honours Project/Monash-Honours-Project/src-main/backend/.venv/Scripts/python.exe'
$env:PYTHONPATH = '.'
```

There are **178 unique passing focused cases**, including **70 new governance cases**.
The final research/access/export/worker run passed **147/147 in 114.84 seconds**;
all **31/31 general migration cases** passed in the preceding extended run.
That preceding run was 128 passed/one failed: its remaining legacy-retirement manifest
expectation was corrected and all four legacy-retirement cases passed in the final run.
These are focused checks, not a full-suite or service-wide coverage claim.

Final commands/results:

```powershell
$researchTests = @(Get-ChildItem -Path tests/test_research*.py | ForEach-Object { $_.FullName })
& $py -m pytest @researchTests tests/test_terminal_integration_outbox.py tests/test_database_worker.py tests/test_task7_worker_recovery.py tests/test_local_worker_template.py tests/test_legacy_retirement.py -q --basetemp=C:/Users/Jordan.Tran/AppData/Local/Temp/ll-task33-release --tb=short --junitxml=.tmp-task33/release-focused.xml
# 147 passed; exit 0. Includes all 70 new governance cases.

& $py -m pytest tests/test_research_governance.py tests/test_research_governed_paths.py tests/test_research_governance_migration.py tests/test_terminal_integration_outbox.py tests/test_database_worker.py tests/test_task7_worker_recovery.py tests/test_local_worker_template.py tests/test_migrations.py tests/test_legacy_retirement.py -q --basetemp=C:/Users/Jordan.Tran/AppData/Local/Temp/ll-task33-final2 --tb=short --junitxml=.tmp-task33/final-focused2.xml
# 128 passed / 1 failed before the last legacy-retirement fixture correction.
# All 31 test_migrations.py cases passed; that migration implementation is unchanged afterward.

& $py -m ruff check app tests migrations scripts
# All checks passed; exit 0.
& $py -m ruff format --check app tests migrations scripts
# 517 files already formatted; exit 0.
& $py scripts/export_openapi.py --check
& $py scripts/generate_frontend_contracts.py --check
# Both generated contracts current; exit 0 each.
& $py -m alembic heads
# 20260910_0045 (head); exit 0.
git diff --check
# Exit 0.
```

The contracts were regenerated with the same two Python scripts without `--check`.
Frontend verification ran from this worktree's `src-main/frontend`:

```powershell
$node = 'C:/Users/Jordan.Tran/Downloads/Honours Project/Monash-Honours-Project/.tmp-task23-24/tools/node-v22.13.0-win-x64/node.exe'
& $node node_modules/eslint/bin/eslint.js .
& $node node_modules/typescript/bin/tsc -p tsconfig.app.json --noEmit --incremental false
# Both passed; exit 0. Node 22.13.0.
```

An ignored worktree-local `node_modules` junction reuses the existing installation.
No install, lockfile, shared dependency or shared TypeScript cache write was performed.
Logs/XML are retained in the ignored worktree directory `src-main/backend/.tmp-task33/`.
Each run uses its own fresh short `--basetemp` under
`C:/Users/Jordan.Tran/AppData/Local/Temp/ll-task33-*`; no learner database or server port is used.
Ordinary tests run serially; explicit concurrency tests use two workers.

Initial failures and resolutions:

- The first worktree creation was denied by the filesystem sandbox; the authorized Git
  metadata operation succeeded with the permission-aware tool. Original checkout untouched.
- The first sandboxed pytest run failed on Windows temporary-directory ACLs (30 setup
  errors plus cleanup error). Rerunning outside that sandbox with a fresh short temp
  directory passed all 30 cases. No test assertion or security policy was disabled.
- First existing regression batch: 75 passed, four migration replay failures. SQLite
  normalizes stored trigger SQL; the frozen migration needed explicit `IF NOT EXISTS`.
- First extended batch: 116 passed, four failures. Two new integration tests had an
  incorrect review-result attribute and seeded a generic fixture before a helper which
  selects its first course. Both fixture issues were corrected. Two old downgrade checks
  must continue expecting `0044` after safely removing empty `0045`; their original
  protected-history assertions were restored. The empty round-trip expectation is `0045`.
- Initial Ruff import-order/unused fixture diagnostics were corrected. No lint rule,
  assertion, skip, timeout, coverage threshold, or safeguard was relaxed.
- The subsequent 128-pass run exposed the legacy-retirement test's exact-head manifest
  comparison after removing empty extensions. It now verifies all protected records
  immediately and then restores the head and checks the original exact manifest.
  Its original data and archive assertions remain; all four cases pass.

## Changed files

```text
docs/learnlens/task-33-governance-implementation.md
src-main/backend/app/api/research_export_dependencies.py
src-main/backend/app/api/router.py
src-main/backend/app/api/routes/research_exports.py
src-main/backend/app/api/routes/research_governance.py
src-main/backend/app/models/__init__.py
src-main/backend/app/models/research_governance.py
src-main/backend/app/schemas/research_governance.py
src-main/backend/app/services/feedback/runtime.py
src-main/backend/app/services/research/governance.py
src-main/backend/app/services/research/governed_export.py
src-main/backend/app/services/research/governed_processing.py
src-main/backend/app/services/research/worker.py
src-main/backend/app/services/research_export_repository.py
src-main/backend/app/services/terminal_integrations/worker.py
src-main/backend/app/worker.py
src-main/backend/migrations/versions/20260910_0045_research_governance.py
src-main/backend/tests/support/migration_assertions.py
src-main/backend/tests/test_legacy_retirement.py
src-main/backend/tests/test_migrations.py
src-main/backend/tests/test_research_governance.py
src-main/backend/tests/test_research_governance_migration.py
src-main/backend/tests/test_research_governed_paths.py
src-main/backend/tests/test_terminal_integration_outbox.py
src-main/contracts/openapi.json
src-main/frontend/src/api/generated.ts
```

## Coordinator reconciliation and remaining external evidence

Shared generated files intentionally changed: `src-main/contracts/openapi.json` and
`src-main/frontend/src/api/generated.ts`. Regenerate both after integrating Task 29 so its
timestamp contract and these new governance endpoints/query fields are retained.
The small `app/worker.py`, feedback eligibility and terminal-outbox changes are the
authorized research-specific integration seams. There is no production change needed
outside the assigned ownership. Master checklist and historical audit are untouched.

Before any activation, named institutional/privacy/research/records/operations owners
must supply and verify the actual signed protocol and data plan, ethics decision,
consent/withdrawal materials and version, eligibility criteria, approved field/purpose
dictionary, named researcher and course grants/end dates, retention classes/authority/
owners/review dates, applicable holds, storage/provider-processing terms, recipient
agreements and disclosure rules. Administrator-entered evidence references are recording
attestations, not cryptographic verification or institutional approval by this software.

The later reviewed release change must replace `research_processing_approved()` only
after those records and release-environment checks exist. Keep the wired governed
repositories/context/export adapters; toggling `research_enabled` alone must never
authorize anything. Reconcile authoritative withdrawals/revocations before restoring
service, quarantine historical unbound rows, verify provider adapters and key custody,
and prove the scoped live-environment path. No current fixture is an activation record.

Task 34 still owns approved instruments, pre/post/transfer/retention and experience/reviewer
records, any learning-condition allocation, their exact field contracts, and restricted
reviewer packet access. This implementation is the governance foundation and existing
technical-pair/export integration, not a claim of complete NFR25 study data collection.

Combined full backend/frontend/browser suites, service-wide coverage gate, load campaigns,
hosted/provider exercises, manual accessibility and final integration are explicitly deferred
to the coordinator under this parallel assignment. Frontend screens are not added.
