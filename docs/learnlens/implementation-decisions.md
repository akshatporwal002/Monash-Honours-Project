# LearnLens implementation decisions

This log records key implementation choices for later user review.
It complements the [approved policy selections](task-08-approved-selections.md) and the [remaining task list](../../LearnLens_Remaining_Tasks.md).
It does not claim that missing institutional approvals or release measurements exist.

## Task 20: explicit global preferences with task-specific limits

Store presentation choices per learner because the current consumers span courses.
Keep every save and reset as a new revision; defaults do not create a record during reads.
Use authenticated identity, expected versions, and request keys for ownership, conflicts, and retries.
Preference choices belong in their own archive, not in inferred learner-model snapshots.
They do not supply evidence of learning or change a formal result.

Resolve effective settings through the existing scoped task and frozen episode readers.
Opt-out retains requested values and returns baseline settings with personalisation explicitly disabled.
Fresh application suppresses optional instructional presentation and repeat practice.
Approved access support, required feedback, and reflection remain available.
Repeat practice starts only a local draft for permitted ordinary practice; existing submission rules still apply.

Only text and stepwise support presentation are offered. No alternate response form or generated explanation is promised.
The detailed interface, defaults, recovery rules, and tests are recorded in the [Task 20 handoff](task-20-learner-preferences.md).
The current instruction permits implementation without sub-agents. Reviews are separate coordinator self-reviews, not independent agent verdicts.
No remote delivery or work beyond Task 20 is included.

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

The initial task-review checkpoint passed 832 backend tests with 85.83% service coverage and all 183 frontend tests.
Migration, contract, lint, format, and production-build checks passed.

## Task 12: current approvals govern new work

Learners can start or submit work only against currently approved teaching content.
Withdrawing approval blocks new work while preserving their own saved drafts, attempts, and simulation history.
The read-only saved-work screen keeps successful reads visible when another history request fails.
Course publication requires approval for every saved task. New demo courses start as drafts without inferred approvals.
Test fixtures record explicit review actions when a test needs available content.

Source review records the expected sequence to prevent stale writes.
Source reapproval does not revive an old task approval. The educator must review that task again.
Current assigned assessors can read source history, but only course owners and administrators can change source approval.

Staff selection reveals only active teaching account names and IDs, latest eligibility, and current eligibility state.
The course lead and administrators can read this course-scoped directory; other accounts cannot.
Administrator grant history distinguishes effective access from historical or scheduled appointments.
Eligibility approval still requires the separate administrator grant defined by D-02.

Task review is available from every course-editor step, including when source processing is incomplete.
Typed marking fields preserve unrelated saved criteria. Circuit editing exposes H, X, CX, qubits, shots, and seed.
Drafts can retain invalid settings for correction, but approval rejects unsupported circuits.

This checkpoint passed 839 backend tests with 85.96% service coverage and 193 frontend tests.
The final task-review placement change passed seven targeted frontend tests and a fresh lint and build check.
The Chrome fixture verified source approval, circuit correction, task approval, course publication rejection,
and the separate course-lead and administrator appointment steps through ordinary application policies.
The user explicitly approved staff permission testing within this synthetic localhost fixture.
The user approved all fixture appointment changes. Browser revocation and regrant then passed.

This was an intermediate checkpoint. The formal publication completion below supersedes its remaining-work note.


## Task 12: publish only exact reviewed formal content

Bind each new formal task form to its saved task revision and digest.
Bind publication to the exact educator review event and its approved sources.
A changed source approval requires fresh teaching review and a new formal definition, even if task text is unchanged.
Missing or stale formal publication blocks learner work without reverting to practice scoring.

Current assessor access is checked inside the publication service as well as the API.
The service locks the course while validating authority and saves all approvals together.
Every early validation failure releases its transaction.
Blank nested conditions are invalid. Explicit declarations of no tools, support, or transfer are valid where approved.
The generic validator does not invent a course's teaching policy or activate the separate AI assessment gate.

Migration 0028 preserves legacy forms with absent review bindings. It does not infer historical approval.
Published references are immutable, and recovery from populated migrations requires a verified pre-upgrade backup.

The assessor task picker reads saved identities and sources. Current assigned assessors receive read-only source controls.
Human teaching approval and the administrator's appointment remain separate decisions.
The browser fixture proved publication without policy overrides and without live accounts.

The user's latest instruction limits this run to completing Task 12, then committing, pushing, and merging into main.
Stop after that integration. Tasks 13 onward remain on the task list.

## 2026-09-07: resume remaining tasks with isolated workers

The new coordinator request supersedes the previous Task 12 stopping instruction.
The user authorises task-owned commits, pushes, pull requests, verified batch merges, and local main synchronization.
Keep a separate branch and integration merge commit for each numbered task.
No live institutional approval follows from this engineering authority.

Fetched origin/main remains `d5ac7cb335a2b1ccdab674e0cab4c61c950b9b35`.
GitHub confirms PR 8 merged at that commit and post-merge run `34072852835` passed.
Task 13 starts there. Task 32 protocol drafting runs in a separate worktree alongside it.
The coordinator owns shared contracts, migration ordering, integration, and progress records.

Task 13 uses an explicit learner start action instead of creating assessment starts during task GET requests.
Existing task-view telemetry is unchanged by that interface choice.
The action binds the declared published form before workspace edits begin.
Drafts and submissions carry the saved work reference. Changed approval or publication returns an explicit conflict.
Do not silently adopt a newer standard or expose marking guidance through the learner reference.
Historical drafts receive no invented start-time approval. Migration 0029 is reserved for this task.

The [coordinator record](coordinator-progress.md) tracks dependencies, ownership, review, tests, delivery, and external gates.
Task 32 remains partial until the required research review, approval, and preregistration records exist.

The user named Arv Surana as research lead. This records ownership without inferring study approval.
Task 13's migration requires runtime readiness to expect revision `20260907_0029`.
The combined suite caught the stale pin; the correction passed the affected runtime and launcher checks.
WebKit authoring checks reproduced an offscreen dropdown after programmatic focus moved between distant form fields.
The helper now scrolls the trigger into view and checks visibility before opening its menu.
Ten repeated real authoring journeys passed with ordinary pointer clicks and unchanged approval assertions.
No product permissions, assessment rules, or test timeouts changed for this correction.

## 2026-09-07: conclude the current batch

The user now asks to finish the tasks in progress, commit and merge into main, then provide an update.
This narrows the earlier continuous delivery instruction to current Tasks 14 and 15.
Complete their remaining correction, independent review, combined checks, PR, and post-merge verification.
Synchronize local main and stop before starting Tasks 16, 17, or 24.
The reviewed Task 32 draft remains partial, with Arv Surana named as research lead and external approvals outstanding.

## 2026-09-07: Batch A delivered, episode and human review work begins

PR 9 merged as `865467740c1c122834bd67d3c7f6a7ca77bd381c` after all final-head gates passed.
Post-merge CI `34078012664` passed 873 backend tests, 31 migrations, 72 browser cases, and all other configured checks.
Service coverage was 86.19%. Local main was clean and matched origin/main before the next worktrees were created.
Task 13 is complete. Task 32 remains partial despite its reviewed drafts being merged.

Tasks 14 and 15 use separate worktrees and file ownership from that verified main.
Task 14 owns the canonical episode payload and immutable response-reader contract.
Task 15 consumes that contract for complete evidence inspection and human criterion decisions.
The coordinator owns shared authoring, publication, generated contracts, migration ordering, and integration.

The private fresh-transfer plan belongs in educator-reviewed task content and a matching frozen task-form snapshot.
Learner reads expose stage metadata and permitted support. Transfer content is released only through authorised stage entry.
Solutions remain private. Prediction and explanation are the default required supported responses.
Reasoning and reflection remain available without an accidental formal penalty for reflection or approved help use.

Initial circuit rules use explicit `circuit_v1` settings for declared qubits and an ordered h/x/cx operation sequence.
They make structural claims only. Unsupported conceptual criteria remain reachable by a human assessor.
Human decisions use append-only action and criterion records, current scoped access, worker fencing, and an exact state token.
No operational AI assessment suggestions are enabled by this work.

The deleted learner-correction branch was recovered at `fda2459fdb6f529f933e48494f9f39787d420d2e`.
A local archive reference preserves its existing history for Task 19 reuse. The remote branch was not restored.
Task 19 must still reconcile its migration, preserve corrections across later snapshots, and add scoped application routes and screens.

Publication now distinguishes the strict circuit-plus-human path from AI-assisted mixed evaluation.
Only MIXED criteria with validated `circuit_v1` settings may use that human review path.
VALIDATED_AI and other MIXED settings remain blocked by D-07 pending Task 35.
Circuit authoring states the structural limit and requires a fresh review after settings change.
The browser check preserved the earlier published rule version when publishing the later mixed-human version.

Episode migration checks must use upgraded databases with existing protected history.
Metadata-created databases alone miss changes to the persisted task-type CHECK constraint.
Downgrade preflight must run before any table or column changes when protected history prevents rollback.


## Task 21: approved practice paths and diagnostic evidence

A pathway version belongs to one course outcome. It contains at least three ordered,
approved tasks, with concept, source, task-form, assessment-rule, and exit-rule links.
Publication freezes the linked task reviews. A changed task or source approval requires
a new pathway version before its diagnostic can be used for a bypass.

Diagnostics are learning evidence. They never create a formal result. A current course
assessor verifies independent conditions and confirms or declines the requested practice
bypass. The record preserves the learner response, affected target, reason, and exact
pathway version. Earlier approvals remain historical; they do not apply to a replacement pathway.

An accepted ordinary response satisfies a declared completion exit rule. It is not proof
of mastery. Optional guidance fades only after a confirmed diagnostic bypass satisfies a
step's prerequisite. Personalisation opt-out stops this optional change. Approved help
and access support remain available. Formal task conditions stay authoritative.

Task 22 will connect the graph to durable automatic activity selection. Task 21 does not
change the existing continuation adapters or activate AI assessment suggestions.
