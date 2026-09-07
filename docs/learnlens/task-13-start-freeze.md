# Task 13: freeze the assessment standard when work starts

Status: implemented and locally verified; independent review and integration remain coordinator gates.

## Learner behavior

Opening a formal workspace now starts assessed work against the exact form shown to the learner.
The start saves an immutable reference before the learner enters an answer.
Draft saves and submissions carry that reference through reloads and retries.
A new rule version returns HTTP 409 and asks the assessor to review the conflict.
It never replaces the original standard or overwrites the saved draft during that failed write.

The workspace keeps the learner's saved answer visible after a conflict and disables further writes.
A temporary start failure can retry the same displayed form.
Retries do not fetch a newer standard automatically.
The condition panel shows approved support, separate transfer conditions, and nested accessibility settings clearly.

Current Task 12 source, educator review, publication, course access, and prerequisite checks remain required.
A stale formal task cannot become practice scoring.
Saved drafts and attempts retain their existing learner ownership checks.
A successful submission retry returns its original response after publication changes, subject to current course access.
Changing the content or supplying another work reference with that key returns a conflict.

## Stored contract

`assessment_work_starts` stores one immutable start for each learner and task.
It binds the definition, task form, Bloom target, pass rule, and exact task approval.
The published form binds the exact teaching revision. Its approval binds the educator review and source approval events.
The start also stores source passage IDs, declared conditions, and its start time.
Submission source citations use these saved references.

- `TaskRead.assessment.task_form_version_id` identifies the displayed approved form.
- `POST /api/v1/students/me/tasks/{task_id}/start` accepts `{task_form_version_id}` and returns `DraftRead`.
- `DraftRead` and `AttemptRead` expose nullable `assessment_work_start_id`.
- `DraftWrite` and `SubmissionCreate` accept the same reference and reject another learner's reference.
- Direct first draft or response creation also freezes the currently approved bundle before accepting the content.

The explicit POST adds no assessment-start mutation to task GET requests.
The existing student task GET still records its task-view learning event.
The API does not expose marking answers, criterion anchors, or provisional results through the new fields.

A learner lock serializes start and response allocation.
The same course lock used by publication protects the standard check and write transaction.
Concurrent starts return one reference. A start racing publication either binds its displayed form or conflicts.
Existing unversioned drafts with content require assessor review before they can become formal assessed work.
Empty legacy drafts receive no invented historical start during migration.

## Revision repair found by the browser

The migrated browser database rejected a second publication with `invalid task_form_versions version order`.
The authoring service created a new form identity but assigned the definition's later version number.
The repair reuses the task's form identity and increments that identity's version sequence.
A new form starts at version one, independent of the definition version.

Criterion versions now follow their own identity sequence too.
The migrated regression adds a criterion, removes it, and restores it in a later definition.
Its original identity stays intact, and its next version follows its own prior version.
The current declaration orders definition versions before form versions.
Earlier published forms and criteria remain immutable.

## Migration and recovery

Migration `20260907_0029` follows `20260907_0028` and adds the work table and nullable response links.
It does not backfill approval or rewrite earlier response values.
SQLite guards reject start updates, deletes, replacement writes, invalid scope, and response reference changes.
Model events also reject changes to start records.
Replay retains the exact stored start and leaves foreign keys valid.
Historical migration fixtures use their actual older response schema when creating pre-upgrade evidence.

Take a verified database backup before upgrade.
Populated protected history blocks downgrade before any schema changes.
Restore the verified pre-upgrade backup for rollback when protected evidence exists.

## Policy boundaries

D-01 continues to hide provisional formal results from learners.
D-05 remains unlimited approved conceptual hints, with a separate unaided transfer stage and approved access support.
This task preserves and displays those conditions; it does not implement the later learning episode or hint workflow.
D-07 AI assessment suggestions remain disabled pending their separate validation gate.

The conflict path requests review. This task does not add a reset or reassessment authorization endpoint.
The original work reference cannot be silently replaced through a new draft save.
Future reassessment work must define an explicit new-work identity and preserve this history.
No synthetic fixture approval establishes live staff, course, source, or institutional authorization.

## Local verification

The focused backend run passed 76 tests.
It includes real migrated rule publication, start and submission references, legacy drafts, ownership isolation,
source and task publication regressions, SQL protection, migration replay, downgrade refusal, and concurrent requests.
A changed standard rejects new writes while an identical submitted-response retry retains the original response.

All 28 focused frontend tests passed across three files.
They cover exact start references, save and submit, visible conflicts, retained local edits,
private history, nested conditions, and a successful retry after a temporary start failure.
Backend lint and formatting passed across 346 files.
Frontend lint and the production build passed. The existing large-bundle and jsdom canvas warnings remain.
The coordinator generated and checked the OpenAPI and frontend contracts in this worktree.

Chrome used a newly migrated synthetic localhost database, normal login, CSRF protection, and ordinary application policies.
The browser opened the assessment, started its exact form, saved an answer, and restored it after reload.
The fixture then published a replacement definition through the assessment service.
Submission returned the explicit version conflict with the original work reference.
Reload retained the saved answer and disabled new writes.
The final screenshots were visually inspected. Ports 8133 and 5233 were closed after the check.

Evidence is in ignored `src-main/backend/.tmp-task13`:

- `final-focused05.log`: 76 backend checks passed.
- `frontend-final.log`, `frontend-lint.log`, `build-final.log`: frontend checks and build.
- `backend-lint.log`, `backend-format.log`: backend quality checks.
- `browser-final-check.log`: completed Chrome journey.
- `browser-final/result.json`: observed start, draft, and submission references.
- `browser-final/original-draft.png`, `rule-change-conflict.png`, and `reload-preserves-work.png`: browser evidence.

The reproducible browser fixture is `tests/task13_browser_server.py`.
Use a fresh `TASK13_BROWSER_RUN` directory name for each seeded run.
The frontend check is `e2e/task13-start-freeze.local.mjs` and requires `TASK13_PYTHON`.
Run the backend on 8133 and a local frontend proxy on 5233.
Set the same `TASK13_BROWSER_RUN` for the backend and browser check.
Node 22.13.0 and Python 3.11 were used.

Combined full suites, independent Standards and Spec reviews, and integration remain coordinator-owned gates.


## Independent review corrections

Two review findings required changes to client retry behavior.
A temporary SQLite writer conflict now returns HTTP 409 with structured detail:
`{"message": "Another submission is being recorded; retry this request", "code": "assessment_write_busy"}`.
The API client exposes that code separately from the readable message.
The workspace leaves save and submit available for this retryable conflict.
It preserves local edits, the original work reference, and the submission idempotency key.
Other HTTP 409 conflicts still block writes, including changed assessment standards.
No request or successful response schema changed.

After a draft loads successfully, retrying a failed start sends only the exact start request again.
It does not fetch or apply the saved draft again.
Edits made after the start failure therefore remain intact.
A failed draft read can still retry the draft read itself.

The review regression passed 15 backend tests and 29 frontend tests.
The backend check creates real SQLite write contention, checks its stable error code, and retries the same form.
Frontend checks cover edits entered after the failure but before retry, no duplicate draft read,
retryable save and submission conflicts, and unchanged payloads and idempotency keys on retry.
Existing standard-change conflict tests remain passing.
Frontend lint and production build passed.
The fresh Chrome journey passed again against a newly migrated `browser-review` database.
Review logs are `review-backend06.log`, `review-frontend06.log`, `review-lint06.log`,
`review-build06.log`, and `browser-review-check.log` under the same ignored scratch directory.
Both local test servers were stopped after this check.
