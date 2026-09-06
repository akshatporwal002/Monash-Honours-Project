# Task 12: educator review and publication controls

Status: partially implemented; assessor eligibility and grant controls are in place. Task review, publication, and their UI remain unfinished.

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
`LmsService._validate_publishable` currently checks course content but lacks a general task review lifecycle.

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

Inspect the task-generation, course-publication, role-assignment, and assessment-definition routes and their UI consumers.
Add the task review lifecycle and user interfaces for course-lead approvals and administrator grants.
Then connect the publication policy to current approved sources, task versions, conditions, and supported circuit capabilities.
Verify the actual UI-to-API journey, stale approvals, changed content, revoked grants, missing sources, and unsupported circuits.
Check read access for an assigned assessor who is not the course owner, including source history and setup screens.
Provide administrator grant-history reads alongside the new course-lead eligibility history.
Update contracts, migration protection, the decision log, and the remaining-task record before the next local merge.
