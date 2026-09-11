# Governed operational evidence collector (NFR25)

Status: software capability; actual approved study use remains unverified. No approval,
protocol, instrument, participant record, billing receipt or reviewer judgement is seeded.
Technical-v2 and its fixed paired-processing field contract remain unchanged.

## Authority and storage

The collector requires the separate `study_operational_evidence` purpose, exact
`operational.*` field permissions, named course research grants, current consent and
eligibility, and a `study_operational_manifests` retention schedule. Read, collect and
export permissions are distinct. The existing production research gate remains closed.

A capture binds one allocation and exact instrument record to the current study plan,
consent event, sequence, form and stage. It checks the instrument's integrity and owned
operational response/task/outcome links. It appends a `snapshot` event to migration0048's
immutable study ledger: selected fields, source digests, pseudonymous source references,
adapter versions and reviewed redaction instructions. It does not persist the raw
operational dataset or precompute learner outcomes. The schema change needs no additional
migration. Exact request retries are safe; new source states require an explicit new
snapshot revision. Neither old consent nor an older plan can revive records.

Every preview, read, export preparation and emitted snapshot row rechecks scope, purpose,
grants, consent, eligibility, plan/redaction-rule binding, source lineage and selected
source digests. It refreshes mutable operational rows. Changed latency, newly available
records or later billing reconciliation cannot silently alter a captured snapshot.
Preparation excludes ineligible/stale snapshots with private reason counts; a later
change aborts the stream and records interruption. Previously delivered bytes cannot
be recalled. The latest snapshot revision per instrument record is selected routinely.

## Exact field/source mapping

All names below have the `operational.` prefix. Each selected field is an envelope of
`value`, explicit `missing_reason`, selected-source digest, pseudonymous source references
and adapter version. Unrequested fields are absent. JSON retains nested typed evidence;
CSV serializes envelopes as quoted JSON cells, retaining code/newlines on decoding.
Records are separated by family rather than interpreting study ratings as formal results.

| Fields | Existing source and exact join | Projection |
| --- | --- | --- |
| `response_text`, `code`, `episode` | Instrument `links.response_id` to immutable `SubmissionAttempt`; learner/task/course and consent time checked | Reviewed redacted text; code formatting retained |
| `evidence` | `LearningEvidence.response_version_id` plus learner/course/task | Evidence type, provenance, observation type, actual stored support level, source/schema versions, occurrence time and pseudonymous reference |
| `model_references` | `WorkflowRun.submission_id` plus exact task/course; its feedback and judges; `ActivityProgress.snapshot_id` with learner/course/outcome checks; optional exact provider attempts | Provider/model/prompt/policy and learner-model/rule versions; no prompts, endpoint URLs, context blobs or identity fields |
| `adaptations`, `adaptation_reasons` | Exact workflow's `ActivityProgress`, `ActivitySuggestion` and ordered `ActivityChoice` | Controlled state/rule/choice and pseudonymous selected tasks; reason prose requires separate reviewed redaction |
| `overrides`, `override_reasons`, `outcome` | `AssessmentAttempt.response_version_id` plus learner/course; its `AssessmentDecision`, `AssessorReview`, `HumanAssessmentAction` | Recorded binary result/lifecycle, frozen Bloom/pass-rule references, actions and revisions; separately reviewed reason prose. No automatic confirmation or study-to-grade conversion |
| `source_references`, `ai_output` | Exact workflow's feedback records; released accepted/fallback output only | Source references are study-namespaced HMACs; output prose is separately reviewed/redacted. Source URLs/query strings and arbitrary attributions are not exported |
| `judge_result` | Judges of those exact feedback records | Stored judge status/decision, quality-policy version and technical quality dimensions, explicitly separate from learner grades |
| `simulation` | `SimulationRun.submission_id` and owner; circuit owner/course/task checked | Pseudonymous circuit/run references, shots, policy/engine versions, recorded status and validated binary measurement counts; arbitrary result prose excluded |
| `latency_ms` | Exact response workflow | Recorded nullable latency, never an invented zero |
| `input_tokens`, `output_tokens`, `estimated_cost` | Optional provider ledger below; legacy exact feedback/judge fallback when no ledger rows exist | Per-attempt observations; incomplete usage stays null with `usage_incomplete`. Legacy estimate currency remains explicitly unrecorded |
| `actual_cost`, `reserved_cost`, `exposure_cost` | Optional provider ledger only | Separate nullable per-attempt amounts with recorded currency and millionth-of-currency unit; no conversion, summation or estimate-to-actual substitution |
| `moderation` | Optional moderation reviews selected by exact assessment-attempt IDs | Pseudonymous review/attempt references, stage, cycle when recorded, result; all cycles retained. No inferred moderation completion or evaluator approval |

Support levels are exported as stored historical observations alongside their provenance
and versions. They are not reclassified from a missing source version, a hint count or
research stage. Historical hardcoded levels are not rewritten. The current operational
capture owner resolves newly approved support representations in the learning workflow.

## Optional versioned adapters

`learnlens.provider-usage.v1` reads `provider_usage` only when its expected columns exist.
It matches all of `provenance.context.submission_id`, `task_id`, and `course_id`. Provider
response IDs, billing receipt IDs, actors, raw endpoints and arbitrary context are excluded.
Failed/retried transport attempts remain distinct. A null `actual_micros` remains null;
observed tokens do not imply a billed actual. Later reconciliation changes the digest and
requires recapture. Reserved/exposure amounts are never labelled actual spending.

`learnlens.assessment-moderation.v1` reads optional moderation review tables through exact
assessment-attempt IDs. It retains recorded cycle numbers; older schemas yield a null cycle,
not an invented cycle. It does not import unmerged model modules or equate ordinary formal
confirmation with expert moderation. Course-level evaluator-validation events have no exact
attempt binding in this contract and are not guessed into the export.

Absent adapters yield `adapter_unavailable`; absent linked records yield `not_recorded`.
These are missing-data states, not evidence of zero cost, no adaptation, a completed review,
or an unsuccessful learner result. The optional adapter bounds are 500 matching records;
full export retains its 1,000 inspected-record bounds. These are implementation limits,
not approved study sizes or retention periods.

## Redaction workflow and UI

Raw-field previews expose only digest/provenance and `redaction_required` until an externally
reviewed redaction is supplied. A review binds the exact digest, the current plan's redaction
rule reference, an evidence reference and zero-based, half-open Unicode code-point spans. Empty spans still require a real
review. Selected spans are removed; known participant names/emails, common credential
patterns, identity-labelled JSON values, URLs and local paths receive additional filtering.
This is a safeguard, not proof of anonymity: the responsible reviewer must identify other
people, indirect identifiers and condition clues. A reference is a recorded attestation,
not independent verification of institutional authority. No default approval is supplied.

The researcher page previews selected fields and captures only reviewed snapshots. The
participant page offers the operational-evidence purpose separately from instrument consent.
The full study export offers each operational field explicitly. Participant corrections and
researcher missingness/attrition/deviation controls retain the exact allocation and stage.

Under the existing study prefix, new routes are POST `operational/preview`, POST
`operational/snapshots`, GET `operational/snapshots/{snapshot_id}` with exact `fields`,
and POST `responses` for authorized researcher instrument/status capture. They use the
existing session, CSRF, no-store and instrument rate-limit boundaries. Export remains
POST `exports`, with its separate export rate limit.

## Verification and remaining records

Focused tests exercise source lineage, unauthorized fields/actors, consent replacement,
withdrawal and revocation, redaction/source-digest binding, code formatting, no raw dataset
duplication, explicit missingness, optional provider matching and null billing semantics,
independent-session source changes during streaming, real evidence/adaptation/simulation
records, and mounted API authentication/CSRF. UI checks cover explicit purpose/field choices,
review-gated capture, reviewer ratings, researcher missing-stage capture and exact export
selection. Generated contracts can be rebuilt by the integration owner with
`python scripts/export_openapi.py` then `python scripts/generate_frontend_contracts.py`
from the backend directory. Temporary generation/type checking was also exercised without
modifying the canonical generated files.

NFR25 remains partial until actual approved fields/purposes/retention schedules, reviewed
instrument/rubric/redaction content, named grants, consent and participant-stage reconciliation
are evidenced in an authorized study. This delivery provides the software controls; it does
not claim institutional approval, expert agreement, measured educational effects or live use.

Verification receipt (2026-09-11): 101 distinct affected backend cases are accounted
for across scoped runs: the original instrument service/API set (67), study workflows
(20), and operational collector (14). Runs of 86, 19, 33, 15 and 2 overlap; they are not
summed as separate cases. The final two checks cover the optional provider adapter's
expected schema and mounted API after route-import cleanup. Fourteen distinct frontend
cases are covered: eight study interactions plus six existing routing checks. Frontend
TypeScript and scoped ESLint, Python Ruff, temporary OpenAPI/TypeScript generation and
standalone generated-TypeScript checking pass. No full backend/frontend/browser suite,
live provider call, deployment or real study processing was performed.
