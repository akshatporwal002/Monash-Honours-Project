# Task 34A — governed study instrument foundation

Status: backend foundation for synthetic validation. **Production research remains
closed.** This is not completion of Task 34, an approved questionnaire, an approved
study, recruitment, or permission to process participant data.

Branch: `codex/task34-governed-instruments`, based on frozen
`0bbf95e25e4124f7484944c9493d1165d7b8023b`, in `.tmp-task34a/worktree`.
Migration `20260910_0046` follows `20260910_0045`. No changes are merged or pushed.

## Delivered behaviour

Versioned forms have bounded choice, integer, and restricted-text items, explicit
stages, controlled status/correction reasons, a support-manifest reference, and a
canonical SHA-256 content digest. Definitions always state `synthetic_only: true`
and `review_status: DRAFT_FOR_REVIEW`. A freeze binds an exact digest for synthetic
validation; it does not represent human or institutional approval. Editing creates
a new version which requires its own freeze. Stale versions and conflicting
request-key reuse fail; exact retries preserve the original receipt.

Research responses bind the exact frozen form, participant consent event, study
scope, course, learning sequence, and stage. They record explicit missingness,
attrition, and deviations without deriving a zero or a study outcome. Every response
item requires a value or a missingness reason. Corrections append a new revision
with a controlled reason; originals remain intact. Conflicting concurrent corrections
cannot both supersede the same record. Routine exports select the latest revision
of each series; a scoped read can inspect an earlier revision.

Optional outcome/task/response links are validated against the course and response
owner. Operational responses predating the bound consent are rejected. Formal-stage
response observations require an existing matching assessment attempt. Missingness,
attrition, and deviation may be recorded without a response or attempt; any optional
links still undergo ownership, course, and consent-timing checks. Links do not write
to teaching, formal assessment, learner models, or operational responses. There is
no allocation, scoring, grade conversion, or computed research outcome.

The existing hardcoded `research_processing_approved()` gate still denies production
collection, response reads, and exports. Draft form preparation also requires the
current Task 33 scope, approval, purpose, and named grant, but does not open this gate.
Positive processing tests replace the gate only inside synthetic fixtures.

## Authority and data boundaries

Task 33 gains the separate `study_instruments` purpose and exact `instrument.*`
field names. The technical paired processor's `PROCESSING_FIELDS` remains its
original 34 fields. Technical export query typing and service checks explicitly
exclude all instrument fields. No pair-processing requirements are expanded.

Instrument operations require `instrument.define`, `instrument.collect`,
`instrument.read`, or `instrument.export`, plus the relevant data fields. Collection
requires permission and participant consent for all stored instrument fields.
Read/export requests select only explicitly permitted fields. Current study/course
scope, named researcher grant, consent, and eligibility are checked again on use.
Scope changes, withdrawal, revocation, ineligibility, and consent replacement deny
old records; re-consent cannot retroactively revive them.

| Field group | Exact suffixes after `instrument.` | Routine projection |
| --- | --- | --- |
| Provenance | `record_id`, `participant_id`, `course_ref`, `sequence_id`, `form_id`, `form_version`, `item_id`, `stage` | Only selected permitted fields |
| Learning links | `outcome_ref`, `task_ref`, `response_ref` | Study-scoped HMAC references |
| Coded values | `choice_code`, `integer_value`, `missing_reason` | Values or explicit nulls; no imputed score |
| History/status | `event_kind`, `reason_code`, `revision`, `supersedes_id`, `correction_reason_code` | Only selected permitted fields |
| Restricted evidence | `response_text` | Never returned by these read/export routes |

Identity mapping is separate from observation data. Participant, course, sequence,
and learning references use a configured study-namespaced HMAC secret; missing keys
fail closed. Actor IDs, subject IDs, emails, original sequence keys, operational
answers, form prompts, and raw text do not enter routine instrument exports.
Free text is stored separately in `restricted_instrument_evidence`, with integrity
digests. This slice supplies no raw-evidence read or reviewer-packet route.

CSV and JSON exports use deterministic field ordering and one row per item (one
row for a status record), scoped to explicit stages. CSV uses quoting and formula
protection. Preparation, completion, and interruption receipts are append-only;
the private preparation receipt records scope, requested fields/stages, selected
record IDs, exclusion reason counts, and a digest of the prepared projection.
Authority and participant eligibility are checked before streaming and before each
row. Withdrawal during streaming aborts further output; already delivered bytes
cannot be recalled. Interrupted JSON is intentionally incomplete.

The 30-item, 10,000-character, and 1,000-inspected-record bounds are implementation
limits, not approved study sizes or retention settings. Governance requires explicit
retention classes for `instrument_definitions`, `instrument_records`, and
`restricted_instrument_evidence`, alongside governance/mapping/export receipts.
No retention duration or disposal approval is invented or executed.

## Persistence and routes

Migration 0046 creates five research-only tables: `research_instrument_forms`,
`research_instrument_freezes`, `research_instrument_bindings`,
`research_instrument_records`, and `restricted_instrument_evidence`. Frozen DDL
includes immutable update/delete/replacement guards. There are no participant,
instrument, approval, or allocation seeds. Forward replay is idempotent; downgrade
refuses before dropping anything if any instrument table contains history. Empty
0046 tables may be downgraded before the independent populated-0045 guard is tested.

Under `/api/v1/research/instruments/{study_id}/{course_id}` the routes create/read
forms, freeze exact versions, collect/read records, and export explicit projections.
Mutations use authenticated sessions and CSRF checks; responses use `no-store`.
Instrument writes use the registered `research-instruments` bucket. Exports reuse
the existing `exports` limit unchanged.

The preceding independent commit `c627c7ac02ed0ec42ae270f5d4d4961936ec0e8d`
fixes POST request-body replay: once buffered messages are exhausted, middleware
awaits the real receive channel so streaming can finish or observe a disconnect.
Declared and streamed oversized bodies still fail before routing. Existing material
content and technical research export streams use GET and bypass this body replay;
the new POST instrument export exposed the defect.

Integration overlap: this branch also registers the missing `research-governance`
rate-limit bucket, needed for actual authenticated Task 33 decision writes at the
frozen base. The coordinator is extracting that Task 33-only correction separately.
Preserve one registration when integrating both changes; it does not open research.

## Validation and remaining dependencies

Focused validation covers forms/freeze/versioning, exact retries and concurrent
corrections, field bounds, learning-link ownership and consent timing, missingness,
withdrawal during export, re-consent, scopes/grants, raw-data exclusion, technical
pair isolation, actual authentication/CSRF/rate limiting, CSV/JSON routes, database
immutability, forward/replayed migration, guarded downgrade, and verified backup
restore. Related Task 33, assessment-contract, and clean-database migration tests
are included. Branch-local OpenAPI and TypeScript contracts are regenerated and
checked; the generated TypeScript compiles independently.

Final receipt (2026-09-10): **135 passed in 99.78 seconds**, without warnings, for
`test_research_instruments.py`, `test_research_instruments_api.py`,
`test_research_instruments_migration.py`, `test_research_governance.py`,
`test_research_governed_paths.py`, `test_research_governance_migration.py`,
`test_assessment_contracts.py`, the clean-database test
`test_migrations.py::test_definition_migration_upgrades_clean_database`,
`test_request_size_streaming.py`, and `test_security_policies.py`.
Ruff check and format check pass for all 18 changed Python files. OpenAPI and
frontend-generation `--check`, generated-TypeScript `tsc --noEmit`, and
`git diff --check` pass. Commands ran from this branch's backend with
`PYTHONPATH=.`; the existing Python/TypeScript installations were used read-only.

Post-review correction: the formal-attempt requirement previously also rejected
status records for never-submitted formal stages. The regression command
`pytest tests/test_research_instruments.py -k 'formal_status_records and none' -q`
reproduced all six failures (two formal stages by three status kinds) with
`formal_observation_reference_required` before the fix. The requirement now applies
only to `kind=response`. The expanded matrix covers absent/owned links, nonexistent
references, other-user responses, other-course outcomes, and the retained attempt
requirement for response observations. Status projections retain explicit nulls and
missingness reasons, never a fabricated zero. No schema, migration, gate, or field
permission changes are part of this correction.
Correction validation: **67 passed in 37.56 seconds** across instrument service and
mounted API tests, without warnings; Ruff check/format and `git diff --check` pass.

Integration-readiness correction: `app/core/readiness.py` now pins
`MIGRATION_HEAD = "20260910_0046"` to match this branch's Alembic head. Before the
change, `pytest tests/test_deployment_runtime.py::test_readiness_migration_pin_matches_the_alembic_head -q -p no:cacheprovider --tb=short`
failed in 1.57 seconds with `20260910_0045 != 20260910_0046`. After the one-line
correction, `pytest tests/test_deployment_runtime.py tests/test_health.py tests/test_worker_health.py -q`
passed **16 checks in 22.76 seconds**, without warnings. Ruff check/format and
`git diff --check` pass. Contracts are unchanged. This receipt is separate from the
135 original checks and 67 instrument-correction checks; no full suite was run.

Next dependency: human-reviewed instrument content and support manifests, approved
field/purpose/retention decisions, and an explicit approval workflow for real
instruments. Follow-up work includes learner/researcher UI, approved redaction and
blinding for reviewer packets, rating workflows, study allocation, outcome analysis,
and the complete NFR-25 data-management/export contract. These are not implemented
or approved by this foundation. Retention disposal and production activation remain
separate governed work.
