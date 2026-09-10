# Task 21: curriculum and approved diagnostics

This records the original implementation and local verification on 9 September 2026.
The [Task 22 integration record](task-22-main-integration.md) describes the later combined storage and migration sequence.

## Delivered behavior

Educators can publish an outcome pathway from the course editor. Each immutable version
contains at least three ordered tasks. Its links identify concepts, prerequisites,
approved task revisions, source approvals, task forms, difficulty, support levels,
evidence guidance, and any formal assessment rule versions.

Publication rejects duplicate tasks, cycles, forward or missing prerequisites,
foreign outcome tasks, missing sources, and unapproved content. It preserves existing
task prerequisites. Source or task approval changes require a new pathway version
before an old diagnostic can grant a bypass.

The student dashboard offers initial diagnostics and learner-requested prior-mastery
checks. A start records the exact pathway version, purpose, target, prompt, and
independent conditions. Responses capture prior knowledge, reasoning, confidence,
concept uncertainty, requested support, and the learner's declaration about independence.
They are protected learning evidence, with `SELF_REPORTED` provenance for the observation.
They are not mastery estimates or formal results.

Diagnostic responses remain `needs_review` until a current course assessor confirms
or declines the requested practice bypass. Confirmation requires a reason. An advance
also requires the learner's declaration and the assessor's independent-condition check.
General educator access does not grant this authority. Reviews are available from
the course editor and the assessor review workspace.

A confirmed advance can satisfy practice prerequisites. It cannot unlock or replace
formal assessment. Learners see the reason and a link to the approved practice target.
Earlier work remains available. No assessment decision or grade is created.

An accepted ordinary response satisfies the declared completion exit rule. Completion
alone is not proof of success. Optional guidance fades only when confirmed diagnostic
success satisfies a step's prerequisite. The educator chooses the allowed support
levels. Learners can still open approved guidance and hints. Personalisation opt-out
stops optional fading. Transfer and formal assessment conditions remain authoritative.

## Interfaces and storage

The mounted API uses `/api/v1/curriculum`:

| Method and path | Use |
| --- | --- |
| GET `/courses/{course_id}/pathways` | Latest published pathway for each outcome |
| POST `/outcomes/{outcome_id}/pathways` | Course owner publishes a new version |
| POST `/diagnostics` | Learner starts an initial or prior-mastery diagnostic |
| GET `/diagnostics/{id}` | Owner or authorised teaching/assessor read |
| GET `/courses/{course_id}/diagnostics` | Scoped history, 20 per page, maximum 100 |
| POST `/diagnostics/{id}/response` | Learner submits evidence once |
| POST `/diagnostics/{id}/confirmation` | Current course assessor records a decision |

Strict request schemas reject extra fields and forged identities. Reads use `no-store`.
Mutations use the existing authentication, CSRF, and request-rate controls.
Publication checks `expected_version`. Request keys identify immutable receipts.
Identical retries return the saved record; conflicting payloads return 409.
Database conflicts and unavailable writes produce recoverable errors.
The screens retain unsaved entries after failed requests.

Migration `20260909_0034` follows the Task 20 migration `20260908_0033`.
It adds four append-only tables: pathway versions, diagnostic sessions, responses,
and confirmations. SQLite guards reject updates, deletes, and replacement inserts.
Replay restores missing guards. Populated history blocks destructive downgrade.
The response and its learning evidence commit in one transaction. Course write locks
serialize publication and diagnostic commands with content-review writes.

`pathway_progress()` supplies approved prerequisite bypasses and optional support levels
to the existing LMS. Task 20's effective-preference response adds a nullable
`pathway_support_level`. Formal tasks retain their existing prerequisite rules.
Generated OpenAPI and frontend contracts include these interfaces.

## Validation

All evidence below is from the original local implementation checks.

| Check | Result and evidence |
| --- | --- |
| Full backend suite | 1,121 passed; 86.94% service coverage |
| Final Task 21 and requirement matrix tests | 19 passed (16 Task 21 and 3 matrix checks), including concurrent replay and migrated populated-history checks |
| Task 20 and Task 21 focused integration | 32 passed before the final concurrency case |
| Full frontend suite | 246 passed in 69 files |
| Existing browser regression suite | 84 passed across Chrome, Edge, Firefox, and WebKit |
| Task 21 authenticated journeys | Passed in all four browsers |
| Final educator-to-learner journey | UI publication, diagnostic save/reload, assessor confirmation, approved practice link, and guidance fading passed |
| Accessibility | Task 21 browser Axe found zero violations; 390px reflow and keyboard controls passed |
| Build and lint | Production build, frontend lint, Ruff check and format passed |
| Migration and contracts | Migration suite included in full backend run; head 0034; OpenAPI and generated-contract drift checks passed |
| Dependencies | Python audit and full/production npm audits found no known vulnerabilities; lock check passed |

Browser helpers used synthetic data and ordinary authentication. No service or role
authorization overrides were used in those journeys.

The full backend run preceded one added concurrency test and the stricter response
binding type. The final 16-test run covers that final contract, concurrency, and
the expanded migrated-history case. No backend behavior changed afterward.

One frontend run timed out in an unchanged assessment setup test. Its unfinished
interaction affected the following test. The full rerun passed after concurrent
backend and browser work finished. No assessment test timeout or assertion was weakened.
Earlier browser harness failures involved course-selector and login-role interactions;
the final journeys use the actual native and custom controls correctly.
The existing production bundle-size warning remains. The Python audit skips the
editable application itself and checks its installed dependencies.

## Separate self-reviews

Standards review: checked module boundaries, current actor scope, bounded requests,
append-only records, migration replay, generated types, and draft recovery. Fixed the
assessment dataclass projection and used the existing course write-lock pattern.

Spec review: checked FR10, FR11, PD1, and PD2 against the mounted workflow. Added an
assessor-workspace entry so assigned assessors can reach diagnostic reviews. Confirmed
that formal assessment cannot be bypassed and that opt-out stops optional fading.
Task 22's automatic activity selection remains outside this change.

Test Judge review: checked full-suite logs, real persistence, authenticated UI/API
journeys, current contracts, migration recovery, and the exact local limitations.
The final checks pass. These are separate self-review passes, not independent reviews.

## Recovery and remaining scope

Task 22 provides the separate automatic approved-activity selection and durable continuation.
Task 35's operational AI assessment remains disabled. Hosted operation, native Safari,
screen-reader use, and human study acceptance were not established by these local checks.
This implementation does not supply live course approvals or institutional study records.

At this original revision, an empty 0034 migration can be downgraded. For populated history, restore a verified
backup instead of deleting learning or approval records.
