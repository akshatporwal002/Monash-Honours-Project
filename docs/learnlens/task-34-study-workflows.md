# Study workflows and dedicated export

The Tasks 33/34 workflow adds a study plan with externally supplied authority,
allocation and redaction references, exact frozen forms for each stage, controlled
conditions and reviewer rubrics. No questionnaire, protocol, institutional approval
or live participant record is seeded. Production research remains closed.

Migration `20260911_0048` adds immutable `research_study_events`. It preserves actor,
request digest, scoped revision, consent binding and content digest. Exact retries
return the same receipt. Plan replacement invalidates old allocations; corrections
to instrument evidence invalidate old reviewer packets. Populated downgrade fails.
The integration owner orders the migration with the other delivery branches.

Participant pages support self consent/refusal/withdrawal and assigned form responses,
including explicit skipped answers. Self collection validates account, allocation,
consent, form and stage, and retains the actual participant actor. Researcher pages
prepare form versions/plans, record allocations, prepare redacted study packets,
rate assigned packets, record stage-linked outcomes, inspect eligible records and
request exact export fields. Administrator status alone gives no research grant.

A packet requires an independent named researcher, a matching observation/sequence,
a supplied redaction review reference and the current rubric. Packet reads expose
only the packet reference, stage, rubric and reviewed evidence. They omit participant,
account, sequence and condition metadata. Human redaction must also remove identifiers
or condition clues in the prose; recording the reference does not verify that review.
Raw instrument answers are not exposed through routine researcher reads or exports.
Ratings use supplied codes or explicit missingness, never numeric learner grades.

Routes are mounted below
`/api/v1/research/instruments/{study_id}/{course_id}/study`:
`plan`, `decisions`, `records`, `my-forms`, `my-responses`, `packets/{packet_id}`,
and `exports`. Mutations enforce sessions, CSRF and the existing instrument/export
rate limits. Responses are no-store. UI routes are `/research` (entry),
`/research/:studyId/:courseId` and `/study/:studyId/:courseId`.

`learnlens.full-study-export.v1` is a separate CSV/JSON contract. It combines study
allocation, instrument items/status, ratings and outcomes. Observations must match
the current allocation, sequence, form and stage. Selected condition/provenance fields
join to those observations. Only requested granted/consented fields are projected.
Unapproved field requests fail; withdrawn, replaced-consent and stale records are
excluded with private reason counts. Authority and eligibility are rechecked before
the header and every row, and interruption is audited. Delivered bytes cannot be
recalled. CSV quoting/formula protection and JSON interruption detection are retained.
The technical paired processor and technical-v2 export field contracts are unchanged.

Scope/grants now support `study.*` fields and require explicit retention schedules
for `study_workflows` and `study_reviewer_packets`. No retention duration or disposal
approval is invented. External study approval, approved instrument/rubric content,
redaction/blinding review, named grants and actual participant use remain human work.
The subsequent NFR25 collector delivery covers operational context beyond these
study workflow records; this slice alone does not complete NFR25.

Focused verification: 86 backend checks passed across the study workflow tests and
existing instrument service/API regressions; after tightening export joins, 19 study
checks were rerun. Two frontend test files cover five new study interactions and six
existing routing checks (11 passing). These are synthetic functional checks, not
participant usability, expert validation or institutional approval evidence.
