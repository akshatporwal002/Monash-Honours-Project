# LearnLens implementation decisions

This log records key implementation choices for later user review.
It complements the [approved policy selections](task-08-approved-selections.md) and the [remaining task list](../../LearnLens_Remaining_Tasks.md).
It does not claim that missing institutional approvals or release measurements exist.

## 2026-09-07: continue engineering under the selected policies

The user selected D-05 B, D-07 C, and the recommended A options elsewhere.
D-10 retains its earlier immediate-retirement approval.
Those selections are settled and recorded in versioned approval records.

Integrate the Task 8 decision records before starting the next implementation branch.
Task 8's remaining scoped activation records stay visible; their absence does not block unrelated source storage or recovery work.
Each later task must distinguish completed software from missing live approval or external evidence.
Do not enable AI assessment suggestions before the separate validation gate passes.
Do not impose the superseded two-hint cap during supported assessment.

Rationale: the task list permits unrelated implementation while specific policy records remain pending.
The user asked to continue and record key decisions for later review.
This preserves that direction without inventing approval owners, research consent, or a hosted environment.

## Task 9: immutable sources and passage references

Status: implemented; final validation is recorded in the [Task 9 handoff](task-09-source-history.md).

Preserve each successful extracted source revision and its passages instead of deleting old chunks during reprocessing.
Current search uses the latest indexed extraction. Existing output references identify their original passages.
Keep the search projection separate from the immutable archive, so index rebuilding cannot erase citations.
Record source approval and revocation as append-only events, retaining the approval linked to each output when used.
Task 12 will enforce approval within the complete publication lifecycle.
Retirement removes a source from new retrieval, while authorised reviewers retain access to its preserved history.
Do not enable destructive source deletion while the retention schedule remains unresolved.
Backfill existing material and chunk records without treating legacy content as newly approved by a named educator.

Use content hashes in upload filenames to preserve earlier files during replacement.
Keep retired sources accessible through course-scoped reviewer routes, including lookup by output and passage ID.
Backfilled references use `legacy-unverified`; do not reconstruct missing historical approvals or passages from current content.

Verification covers online and offline ingestion, source changes, output references, course access, and migrations.
Complete processing claim recovery belongs to Task 10; Task 9 must still avoid publishing a partial revision.

The first frontend suite run had one timeout while backend and build checks ran in parallel.
The complete frontend suite passed with two workers and unchanged test deadlines.
Use bounded local test concurrency when running these suites together.

## Task boundaries and context

Use a separate branch and merge commit for each task's integrated work.
Keep exact test results, outstanding scope, and resume instructions in the task's handoff document.
Manual context clearing is unavailable through the current tools. Do not claim it has occurred.

## Task 10: recover material processing through the existing worker

Task 9 merged into local main at `3f0ce614855957a5e28003a6664c48d6494e9013`.
Task 10 branches from that merge as `feat/task-10-material-processing-recovery`.

Store the processing claim on the material row, alongside its existing lifecycle state and revision counter.
Both processors use one claim service for ownership, expiry, retries, and publication.
The final SQL transaction checks the claim before changing chunks and again before committing the source revision.
An expired or replaced claim cannot publish or overwrite a newer result.

Use the existing database worker for saved uploads, due retries, and interrupted processing.
Extraction runs outside its event loop so worker ownership heartbeats can continue.
Keep the selected processing backend on the claim. Missing semantic adapters produce a visible bounded failure.
Do not silently replace semantic processing with offline indexing during recovery.

Technical defaults are a 300-second lease and a 5-second retry delay.
Use the existing infrastructure-attempt limit, which defaults to three and cannot exceed three.
These limits govern processing work, not the learner's approved hint allowance or assessment attempts.
An explicit educator retry starts a fresh processing revision after automatic work stops.
Source replacement resets processing state, and retirement cancels further publication.

Expose safe errors and retry dates in material reads. Keep execution tokens internal.
Add status refresh and manual retry controls to the course editor.
The [Task 10 handoff](task-10-material-processing-recovery.md) records validation and operational limits.

## Task 11: bound simulation and preserve the distinction between state and sampling

Task 10 merged into local main at `7fe68f77776018b972441f0988a39b68e3fb1cb9`.
Task 11 branches from that merge as `feat/task-11-durable-simulation-evidence`.

Run Qiskit in a child process so the parent can enforce and clean up a timed-out execution.
Keep the existing HTTP limit of 30 operations and apply it to every core caller.
Use a 15-second budget, two concurrent child processes per API process, and one native Aer thread per child.
These are technical defaults, not approved assessment conditions.

Store exact statevector probabilities separately from sampled frequencies.
Keep amplitudes and explicit bit ordering so later criteria do not confuse matching distributions with matching states.
Preserve the current ideal H/X/CX scope; additional gates and noise models need their own supported execution path.
Circuit-format validation must not trigger an unrecorded simulation.

Preserve circuit versions, execution requests, and terminal outcomes in separate append-only tables.
Save requests before execution and results before returning successful evidence.
Request keys identify retries of the same execution. A changed input needs a new key.
Feedback references a stored run linked to its immutable submission, policy, and engine versions.
Keep private practice separate from course-scoped access to task and feedback runs.

After 20 seconds, the worker records an unfinished request as interrupted.
This gives the 15-second process budget five seconds to record its outcome.
Late output cannot replace terminal evidence. A fresh run requires a new request key.
The legacy stateless wrapper is retired so every application execution has durable evidence.
No historical run settings are inferred or backfilled.

The [Task 11 handoff](task-11-simulation-evidence.md) records implementation and final local validation: 782 backend tests, 85.52% service coverage, and 180 frontend tests.
Migration, contract, lint, format, and production-build checks passed.


## Task 12: separate staff eligibility from assessor access

Task 11 merged into local main at `42ffe03b06a47468ecc3dd41975dcee3e9dd7895`.
Task 12 branches from that merge as `feat/task-12-educator-publication-controls`.

Use the course owner as the course lead who approves teaching staff eligibility under D-02.
Only active educator accounts qualify through this initial teaching-staff policy.
Keep the administrator's course-scoped grant as a separate action with its own audit record.
Link each grant to the exact course-lead approval that supports it.

Store eligibility changes as append-only versions, with reasons and optional end dates.
A grant cannot extend beyond its supporting approval.
Withdrawal or replacement of that approval stops access through its linked grant.
Re-approval requires a new administrator grant; it does not revive an earlier appointment.
Preserve legacy grants without inventing missing approvals or treating them as current permissions.

Add the migration without rebuilding the protected SQLite grant table.
Keep research-role activation closed until the later governed research work.
These controls implement the selected policy; test appointments do not appoint staff to a live course.
Task review, source and condition checks, publication, and their user interfaces remain in progress.
This assessor-eligibility checkpoint passed 803 backend tests with 85.64% service coverage, all 29 migration tests, and contract, lint, format, and frontend-build checks.
See the [Task 12 handoff](task-12-publication-controls.md) for evidence and remaining work.

## Task 12: review exact teaching content

Store each authored or generated task revision as immutable content with a digest.
Include the outcome statement, task prompt, instructions, marking guidance, sources, and circuit settings.
Keep generation provenance distinct from educator approval.
Save review actions separately, with the actor, reason, sequence, and exact source approval IDs.
Editing a task creates a new revision and requires a fresh review.
Changed outcome content, retired sources, and replaced or revoked source approvals invalidate current availability.

Use an explicit submitted, approved, rejected, and withdrawn review lifecycle.
The course educator records teaching-content reviews. Administrators and current course assessors can inspect history.
Learners cannot read the review archive or its marking answers.
The review screen sends expected revision and review versions so stale browser tabs cannot overwrite reviewed work.
Task generation and task editing never create implicit approvals.

Teacher-authored practice may use the reviewed task itself as its teaching content without external passages.
Generated tasks and all formal assessment forms require approved external source passages.
This distinction preserves the existing authored-practice path without weakening formal source approval.
Circuit approval validates the current H/X/CX limits and rejects unsupported settings without executing a simulation.
Empty starter circuits are valid authoring templates; execution still requires at least one gate.

Migration `20260907_0027` archives existing course tasks as unapproved legacy snapshots.
It never invents a historical reviewer or approval date.
The archive blocks destructive downgrade, including when the records came from migration backfill.
Recovery uses a verified backup taken before the upgrade.

Task 12 remains unmerged. Learner publication enforcement, formal publication, source review screens,
and staff appointment screens still need integration and verification.
The task-review checkpoint passed 832 backend tests with 85.83% service coverage and all 183 frontend tests.
Migration, contract, lint, format, and production-build checks passed. Native publication journeys remain due.
