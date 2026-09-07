# Task 12: educator review and publication controls

Status: partially implemented. Staff eligibility and grant screens, source review, task editing and review,
and learner publication enforcement are implemented. Formal assessment publication remains unfinished.

Branch: `feat/task-12-educator-publication-controls`.
Base: Task 11 merge `42ffe03b06a47468ecc3dd41975dcee3e9dd7895`.
The base worktree was clean, and its tree matched the tested Task 11 feature commit.
Task 11 passed 782 backend tests with 85.52% service coverage and 180 frontend tests.

## Required outcome

An authorised assessor can publish a valid assessment form through the application without test overrides.
Generated tasks have review, editing, approval, rejection, and preserved history.
Unreviewed generated tasks and unsupported circuits remain unavailable to learners.
Publication requires complete outcome, criterion, source, support, access, and task-form versions.
Course publication must check the state of its individual tasks.

## Implemented assessor eligibility

The course owner acts as the course lead for D-02 approval records.
Only an active course lead can approve or withdraw eligibility for an active educator account.
Each record retains the course, staff member, actor, reason, policy version, sequence, and optional expiry.
History is append-only. Stale edits return a conflict, and concurrent changes cannot overwrite each other.
The course lead and administrators can read paginated history; other users cannot.

`POST /assessment/courses/{course_id}/assessor-eligibility` records approval or withdrawal.
`GET /assessment/courses/{course_id}/assessor-eligibility` reads its history.
These routes work through ordinary authentication without an eligibility-policy override.
Approval does not itself grant assessor access.

An administrator records the separate course-specific grant through the existing assignment endpoint.
The grant stores its exact eligibility approval ID and cannot outlive that approval.
Optional grant start and end dates are now exposed by the request schema.
Grant creation and eligibility changes take the same course write lock.
The lock does not change the course's content or update timestamp.

Access checks and authentication responses require the grant's approval to remain current.
Withdrawal, expiry, or an inactive teaching account prevents assessor access.
A replacement approval does not revive the old grant; an administrator must record a new grant.
Existing grants without a linked approval remain historical records and cannot supply current assessor access.
The production eligibility policy permits only educator accounts for assessor grants.
It continues to deny research-role activation, which belongs to Task 33.

Migration `20260907_0026` adds the approval archive and a nullable foreign key on existing grants.
SQLite adds that reference without rebuilding the protected grant table.
The reference uses the default foreign-key no-action behavior, and approval history also rejects deletion directly.
No course-lead approvals are inferred or backfilled for historical grants.
Upgrade replay preserves history. A populated archive blocks downgrade before destructive DDL.
Readiness requires the new head. Contracts are regenerated and their drift checks pass.

Focused eligibility, permission, authentication, review, definition, and research-boundary checks passed 69 tests.
The 20 eligibility checks include the real lead-to-administrator API path without policy overrides.
They also cover scheduling a new grant after a prior approval was withdrawn.
All 29 migration tests pass. Frontend lint and production build pass, with the existing bundle-size warning.
The complete backend suite passed 803 tests with 85.64% service coverage on this assessor-eligibility checkpoint.
Ruff lint and formatting checks passed for 329 files.
Task 12 has not merged; its remaining review and publication work is still required.

## Remaining publication work

`app/api/assessment_dependencies.py` still denies assessment publication through its default publication policy.
The existing dependency exports remain intact.

`AssessmentDefinitionService` already drafts and freezes outcome, criterion, condition, and task-form versions.
Inspect its approval validation and HTTP authoring workflow before extending it.
`LmsService._validate_publishable` now checks current educator approval for every task in the course.

Task 9 supplies immutable source revisions, passages, approval events, and output references.
Task 11 supplies `simulation_capabilities()` and `validate_circuit()` for supported circuit checks.
Task 13 will freeze the selected assessment bundle when the learner starts work.

## Policy boundaries

Use the existing [approved selections](task-08-approved-selections.md).
D-05 B permits unlimited approved conceptual hints during supported assessment and separate unaided transfer.
D-07 C permits assessor-facing AI suggestions only after the separate validation gate passes.
Do not enable AI assessment suggestions, research collection, or a live institutional pilot through this task.
Real staff can complete scoped authoring and approval records through the implemented application.
Test fixtures do not establish approval for a live course.

## Next work

Connect the formal publication policy to current approved sources, task revisions, conditions, and supported circuit capabilities.
Verify the actual UI-to-API journey, stale approvals, changed content, revoked grants, missing sources, and unsupported circuits.
Check read access for an assigned assessor who is not the course owner, including source history and setup screens.
Update contracts, migration protection, the decision log, and the remaining-task record before the next local merge.

## Task revision and review implementation

`TaskRevision` stores immutable snapshots with exact outcome content, task text, answers, source references, and generation provenance.
`TaskReviewEvent` records explicit submission, approval, rejection, and withdrawal, including reasons and the exact source approval IDs.
Task creation, edits, and generation save revisions inside their authoring transactions without implicit approval.
The course educator records review actions. Current assigned assessors and administrators have read-only review access.
Learners cannot read the archive or its marking guidance.

`GET /tasks/{task_id}/review` returns the current review state and unmet checks.
`GET /tasks/{task_id}/review/history` returns paginated revisions and their review events.
`POST /tasks/{task_id}/review` records an explicit action with expected revision and review versions.
Task edits accept an expected revision ID and reject stale writes when supplied.
Date values in review responses use UTC.

The course editor now opens a saved-task review screen with editing, review actions, reasons, and earlier content.
Unsaved edits disable review actions. Conflicts remain visible and do not produce a false success state.
The course publication button is labelled separately from individual task approval.
Educators can edit answer choices, required terms, code fragments, gates, and starter or expected circuit settings.
Edits preserve other saved marking fields. Circuit controls expose gate targets, qubits, shots, and seed.

Current approval checks require valid module and outcome scope, teaching content, marking guidance, and supported circuit settings.
Generated tasks require approved external source passages. The formal publication path must invoke the stronger source requirement.
Teacher-authored practice can use its reviewed content without external source passages.
Edits, changed outcome content, source retirement, and changed source approval events invalidate availability.
Learner lists, task access, draft writes, submission, simulation, and course publication enforce these checks.

Migration `20260907_0027` adds the archive and backfills existing course tasks as unapproved legacy revisions.
Replay preserves the archive. SQL update, delete, and replacement attempts fail.
Populated history blocks downgrade before schema changes. Restore a verified pre-upgrade backup for recovery.

The full backend suite passed 832 tests with 85.83% service coverage.
It includes all 30 migration tests, 27 review-service checks, and the mounted authoring and review API journey.
The API journey verifies stale edits and review actions, protected marking answers, revision history, and UTC dates.
Concurrent review requests create one event; the second request returns a conflict.
The evidence recovery test verifies that backfilled task history stays protected and restores the pre-upgrade backup.

All 183 frontend tests across 53 files passed.
The new screen tests exercise review reasons, expected versions, edits, history, and stale-request failures.
Backend lint, formatting across 336 files, OpenAPI drift, frontend contract drift, frontend lint, and the production build passed.
The build retains the existing large-bundle warning.
Native browser and complete publication journeys remain due with the rest of Task 12.

Local logs are in `src-main/backend/.tmp-task12/review-full02.log`, `review-frontend-tests02.log`, and `review-frontend-build02.log`.
These ignored logs support this checkpoint; the task remains unmerged and is not release-approved.

## Learner access, source review, and staff screens

Unapproved tasks are absent from learner course lists, dashboards, recommendations, and new reminder selection.
Direct task reads and new work return a conflict when current approval is absent or stale.
Withdrawing approval preserves the learner's own saved drafts, attempts, and simulation history under existing course access rules.
The task page offers a read-only saved-work view after an availability conflict.
Partial history failures show a load error while keeping successfully loaded work visible.

Demo setup creates a draft course and unreviewed task revisions. It no longer publishes a new course implicitly.
Tests that need available tasks now record source and task approvals explicitly through the real services.
These fixture approvals are test evidence, not authority for a live course.

The source panel shows exact saved passages, revisions, review reasons, and approval history.
Review writes send the expected approval sequence and reject stale changes.
Retired materials cannot receive a new approval. Reapproving a source requires fresh task review before learner use resumes.
Current assigned assessors can read source revisions, passages, and output citations without changing approvals.
Withdrawing their eligibility removes these reads on the next request.

The course editor provides eligibility approval, withdrawal, optional expiry, and paginated history.
Its staff picker returns active teaching account names and IDs, current eligibility, and each latest decision.
Only the course lead and administrators can read that directory.
The administrator course screen records separate assessor grants and shows their current effective access state.
Grant history includes the original actor, reason, dates, linked approval, and revocation details.
Historical grants remain visible when their eligibility approval expires or is withdrawn.

Saved task review is reachable from every course-editor step.
The browser check exposed that the old final-step placement could prevent review while another source was still pending.

## Current validation checkpoint

The full backend suite passed 839 tests with 85.96% service coverage.
This includes the ordinary authenticated staff approval and grant path, private history reads,
withdrawal and reapproval behavior, unsupported circuits, source revocation, saved work, and migration checks.
Backend lint, formatting, OpenAPI drift, and generated frontend contract checks passed.

All 193 frontend tests across 56 files passed, along with lint and the production build.
The final placement change for the saved-task review button received a separate targeted check.
Logs are `staff-full01.log`, `staff-frontend02.log`, `staff-build03.log`, and `staff-editor03.log` in `.tmp-task12`.

The isolated Chrome check used `tests/task12_browser_server.py` with a newly migrated local database and demo accounts.
It used ordinary authentication, CSRF checks, and application policies, with no dependency overrides.
The browser verified blocked course publication, source approval, saved circuit edits,
rejected six-qubit approval, fresh review after correction, and successful one-qubit task approval.
It also recorded course-lead eligibility and the separate administrator grant, showing an active history entry.
The user explicitly approved that fixture permission test after automatic approval review initially blocked it.
Browser grant revocation was separately blocked and awaits the user's reply to the follow-up request.
API coverage for revocation passes. Complete formal publication and its browser journey remain due.

No Task 12 merge or remote publication has occurred.
