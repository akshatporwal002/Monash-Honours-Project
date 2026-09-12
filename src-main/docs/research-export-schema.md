# Research export schema

Exports are separate, versioned contracts. A technical measurement export is not a full learning
study dataset. Current routes require authenticated course/study authority and the applicable
release, consent, purpose and field grants. Production study use remains closed until real
approvals and deployment opt-in exist; fixture approvals and draft forms are not authority.

All paths below use the default `/api/v1` prefix. The machine-readable request contracts are in
[OpenAPI](../contracts/openapi.json). The source allowlists are
[research governance](../backend/app/schemas/research_governance.py),
[instrument contracts](../backend/app/schemas/research_instruments.py) and
[study contracts](../backend/app/schemas/research_study.py).

## Current routes and versions

| Route | Request selection | JSON schema / content |
| --- | --- | --- |
| `GET /research/exports` | `format=csv` or `json`, explicit `study_id`, repeated `fields` query parameters, authorised course and optional date/condition/task-type/model/judge filters | `learnlens.research-export.v2`, `record_kind: technical_feedback_pair`; minimal selected technical fields |
| `POST /research/instruments/{study_id}/{course_id}/exports` | JSON `format`, explicit `fields` and `stages` | `learnlens.instrument-export.v1`; coded instrument responses and status/correction records |
| `POST /research/instruments/{study_id}/{course_id}/study/exports` | JSON `format`, explicit `fields` and `stages` | `learnlens.full-study-export.v1`; selected study, coded instrument and governed operational snapshot projections |

The two POST routes require CSRF protection. Responses are private/no-store downloads. The technical
route supplies `X-Export-ID`; instrument/full-study routes supply `X-Research-Export-Id`. Each service
persists a prepared eligibility/audit receipt before streaming,
rechecks authority and included records before headers and during the stream, and records completion
or interruption. An interrupted stream is not a complete export; its partial bytes must not be
counted as a successfully reconciled sample. Exclusion counts and source record references remain
in the protected prepared receipt.

## Minimal technical v2

The current dependency supplies `GovernedResearchExportService`, not the retained legacy v1
service. Export fields are the non-`processing.*` members of `TechnicalPairField`:

```text
case_id,pseudonymous_user_id,course_id,task_id,task_type,submission_reference,
experimental_condition,judge_decision,correctness_score,relevance_score,
grounding_score,actionability_score,safety_score,unsupported_claim_count,latency_ms,
input_tokens,output_tokens,total_tokens,estimated_cost,regeneration_count,fallback_used,
status,comparable,usage_complete,measurement_schema_version,created_at,completed_at
```

`processing.*` permissions govern the fixed technical-pair processing contract; they cannot be
selected as export columns. In particular v2 does not export raw responses/code, generated-output
prose, judge reasons, provider inputs, retrieved-source bodies or simulation payloads. Consent for
technical processing does not grant operational-text export. Correctness/judge metrics describe
AI-output quality, not the learner's formal result or a measured learning benefit.

Fields are deduplicated and sorted for CSV and recorded in the JSON envelope. The envelope also
contains study, scope and export IDs, record count and records. The route bounds date ranges to
365 days and course selection to 1,000 references. The configured row limit defaults to 100,000;
v2 bounds inspected rows as well as included rows and reads candidates in batches of 250. Legacy
rows without current eligible case bindings or safe content are excluded. CSV quotes every cell,
uses UTF-8 with a BOM and applies spreadsheet-formula protection.

## Coded instrument and full-study dictionary

| Field group | Meaning and limits |
| --- | --- |
| `instrument.record_id`, `participant_id`, `course_ref`, `sequence_id`, `form_id`, `form_version`, `item_id` | Exact record/form and pseudonymous sequence linkage; each key carries the `instrument.` prefix |
| `instrument.stage`, `outcome_ref`, `task_ref`, `response_ref` | Stage and linked learning references, with the same prefix on each key |
| `instrument.choice_code`, `integer_value` | Approved coded response values; raw `instrument.response_text` is not an export field |
| `instrument.missing_reason`, `event_kind`, `reason_code`, `revision`, `supersedes_id`, `correction_reason_code` | Explicit gaps, status and append-only correction lineage; same prefix throughout |
| `study.record_id`, `participant_id`, `sequence_id`, `stage`, `condition`, `plan_id`, `record_kind` | Selected allocation/stage identity and approved condition; each key carries the `study.` prefix |
| `study.instrument_record_id`, `packet_id`, `rubric_code`, `value_code`, `missing_reason` | Linked coded review/outcome records; same prefix throughout. Private packet text and governance provenance are not automatically exported |
| `operational.*` | Exact, separately governed learning-source projections described below; available only through full-study export |

Supported stage identifiers are `T0_BASELINE`, `T1_STUDY_ACTIVITY`, `T1_FORMAL_SUPPORTED`,
`T1_FORMAL_UNAIDED`, `T2_CONCEPTUAL`, `T2_TRANSFER`, `T3_CONCEPTUAL` and `T3_TRANSFER`.
Optional delayed stages require an approved plan. Missingness distinguishes `not_collected`,
`not_applicable`, `participant_skipped`, `technical_failure`, `not_evaluable`, `outside_window`,
`withdrawn` and `not_approved`; it never invents a response or result.

Instrument export permits at most 24 selected fields; full-study export at most 64. Both require
1–8 stages. Instrument export rejects scans above 1,000 records. Full-study export independently
bounds scanned study events and instrument observations to 1,000 each. These are scan bounds, not
claims of an unlimited participant export. Superseded instrument observations are omitted;
full-study operational data uses the latest snapshot revision for each selected slot. JSON
contains a versioned envelope and records; it does not reuse the technical-v2 envelope fields.
CSV headers are sorted selected field paths, all cells are quoted and formula-protected, and
nested operational values are JSON encoded. These two CSV streams use UTF-8 without the technical
export's BOM. Fields absent for a particular record kind can be blank/null; interpret the selected
record kind, coded missingness and operational `missing_reason` rather than treating blanks as zero.

## Governed operational evidence and text

The full-study route can select evidence, model/source references, adaptations/overrides, AI and
judge output, simulation, latency/tokens, reserved/exposure/estimated/actual cost, outcome and
moderation fields from `OperationalField`. A field projects an object containing `value`,
`missing_reason`, `source_digest`, `source_references` and `adapter_version`. An absent actual-cost
record remains null with missingness; an estimate is not billed cost.

`operational.response_text`, `code`, `episode`, `ai_output`, `adaptation_reasons` and
`override_reasons` are text-bearing selections (each key has the `operational.` prefix). They
require separate operational purpose/field permissions, current participant consent and a
source-digest-bound redaction approval under the current plan. They do not become permissible
through the minimal technical export or an instrument read grant. Preview can report
`redaction_required`; snapshot collection rejects missing required redaction. Snapshot reads and
exports revalidate exact stage/response links, current authority, source digest, adapter version
and redaction bindings. Source drift or withdrawn authority fails closed.

Preparation routes under `/research/instruments/{study_id}/{course_id}/study` are
`POST /operational/preview`, `POST /operational/snapshots` and
`GET /operational/snapshots/{snapshot_id}`. `GET /reconciliation` reports pseudonymous recorded,
missing and ambiguous stages; it does not manufacture learning outcomes. Full-study export consumes
saved snapshots rather than collecting arbitrary live text during download.

For the release, consent and exact disposal procedure, use
[the study governance guide](../../docs/learnlens/task-32-34-release-reconciliation-disposal.md).
Only restricted instrument-text deletion is currently implemented; other record classes, old
backups and external copies remain subject to approved procedures and possible class-specific
software. A download does not grant onward disclosure or disposal authority.

## Historical technical v1 contract

The following describes the retained `ResearchExportService` /
`quantumlearn.research-export.v1` contract and historical exports. It is not the current default
service mounted at `GET /api/v1/research/exports`, which uses governed v2.

Research exports are authorization-scoped, terminal-only snapshots. They are fail-closed on the
initial `research_export_created` audit write: no response bytes may be sent until that record is
durable. A stream failure creates a sanitized failed audit event.

### Historical filters and limits

The export route supports CSV or JSON plus course, UTC half-open date range, condition, task type,
model, and judge-decision filters. The date range is at most 365 days. Course scope is intersected
with authorization and is bounded to 1,000 course references per synchronous request. Results are
streamed in batches of 1,000 and the synchronous export cap is 100,000 rows.

### Stable v1 fields

CSV uses this fixed order:

```text
case_id,pseudonymous_user_id,course_id,task_id,task_type,submission_reference,
experimental_condition,input_reference,retrieved_sources,simulation_reference,
generated_output,judge_decision,judge_reason,correctness_score,relevance_score,
grounding_score,actionability_score,safety_score,unsupported_claim_count,latency_ms,
input_tokens,output_tokens,total_tokens,estimated_cost,regeneration_count,fallback_used,
status,failure_category,comparable,usage_complete,measurement_schema_version,created_at,
completed_at
```

Nested values use canonical sorted JSON. Timestamps are UTC ISO-8601. Costs are fixed decimal
strings. Every CSV field is quoted, UTF-8 output has a BOM, and cells beginning with `=`, `+`, `-`,
or `@` after optional whitespace, plus tab/newline/control-prefixed cells, are prefixed with an
apostrophe to prevent spreadsheet formulas.

JSON uses a `quantumlearn.research-export.v1` envelope with `generated_at`, applied filters,
`record_count`, and records. Filenames contain only the fixed `quantumlearn-research-` prefix and
a UTC timestamp.

Exports contain pseudonyms only and exclude raw answers/drafts, prompt text, source chunks, direct
identities, credentials, report/feedback prose copied from student surfaces, and raw exceptions.
Input references are bounded opaque strings. Retrieved sources are strictly limited to bounded
`source_id`, display `label`, and finite 0-1 `relevance_score` values. Structured generated output
is bounded by encoded bytes, nesting depth, node count, collection size, and string size, and is
recursively rejected when sensitive key variants or credential-like values are present.

Legacy or corrupted terminal rows that fail this privacy contract are excluded fail-closed.
Failed rows must carry only a bounded lowercase sanitized failure category, while non-failed rows
must not carry one.
Counting and streaming apply the same validation, so the JSON `record_count` cannot advertise a
row that is omitted from the stream. Iterator failures, task cancellation, and client-closed
streams append the same sanitized failed-export audit event before preserving control flow.
