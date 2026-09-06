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
