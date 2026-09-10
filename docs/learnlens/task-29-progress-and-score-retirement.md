# Task 29: evidence-based progress and legacy score retirement

10 September 2026. This delivery builds on main `34d686f` and Tasks 25 and 27.
Local verification is complete. No live database has been migrated.

## Progress and evidence

Learners can inspect their learning progress by course and outcome. Course
educators can view the cohort, focus on one learner, and inspect the same records.
The views separate observations, instructional support, uncertain estimates,
misconception reviews, adaptation choices and released formal results.

Counts open paged records from the same scope and filters. Weekly trends retain
these separate meanings. Result trends show each response's current released
decision, grouped by submission week. Earlier decisions remain in result history.
Pending, withheld and void work stays unreleased, including in counts and filters.

Estimates keep uncertainty, prior snapshots, reasons and evidence links. Adaptation
records keep their trigger observations and learner or educator choices. History
links preselect the course, learner and outcome. Missing evidence stays unknown.
Support counts describe recorded observations, not a count of distinct attempts.

Observation links open the preserved learner-facing content after checking its
scope and digest. The view excludes internal task and provider context. Fresh
checks retain their history restrictions, including unrevealed simulation runs.
Unsupported artifact formats keep a clear unavailable message and evidence ID.

The API enforces current course access and active enrollment. Educators must own
the course. Archived course owners can inspect frozen history; learners cannot
use that exception. Progress reads create no evidence, decisions or other records.

## Numeric marks and practice

Active submission models, APIs, feedback inputs, learning events and dashboards
no longer assign or expose learner marks. Score averages, score-based risk rules
and administrator pass thresholds are removed. Technical retrieval measures and
quantum probabilities retain their existing meanings.

Saving practice records participation. It cannot create a formal PASS. Approved
pathway exit rules still apply, and old practice cannot complete a now-formal
task. A stale pathway does not block unrelated work. The local feedback template
states that it has not evaluated the answer instead of claiming an outcome.

## Migration and recovery

D-10 approved immediate retirement under `legacy-retirement-v1`, with no
compatibility window. Migration `20260910_0044` follows Task 27's `20260910_0043`.
It archives full original rows from both legacy submission tables, including
null and numeric marks. It also preserves the two retired threshold settings.

The immutable archive keeps source table, source ID, original payload, policy,
migration version and capture time. The migration then removes active score
columns and their constraints. It preserves other values, inbound references,
indexes and history guards. Payload comparisons and foreign-key checks run before
commit. An injected failure test verifies rollback after a table rebuild.

Replay verifies archived rows and permits new unscored submissions. Populated
downgrades refuse before changing tables or the migration version. Empty database
upgrade, downgrade and upgrade are tested. Readiness expects head `20260910_0044`.

For a later release, stop writers and take a verified database and source backup.
Test the migration on an isolated restored copy before changing the live target.
Inspect archive counts, source IDs, payloads, foreign keys and readiness there.
Use the existing backup and restore procedure if recovery is needed. Restore the
matching application package and database together. Do not remove populated
history or treat a destructive downgrade as rollback.

## Verification

The combined backend run completed in 19 minutes 52 seconds: 1,261 passed and
seven failed. Four failures expected an earlier downgrade error. One new fixture
missed required outcome fields. Two older integration tests still supplied
retired score arguments or expected the old metrics version. After corrections,
all 65 tests across the seven affected files passed together in 92.68 seconds.
The combined process had loaded tests before several of those corrections.
It also reported one fixture-only support-level enum serialization warning.

Focused checks also passed ten progress and simulation-boundary tests and four
legacy-retirement tests. All 272 frontend tests passed. Ruff, frontend lint,
production build and generated API contract checks passed. The build retains
its existing large-chunk advisory.

The extended misconception and progress journey passes in Chrome, Edge, Firefox
and WebKit, including automated accessibility checks and saved-answer inspection.
The final run passed all four projects in 26.1 seconds. Its Firefox capture was
visually checked and showed readable, unclipped progress and result history.

The complete learning-loop regression also passed all four projects. Its first
run found a low-contrast revision selector in Chrome. Explicit foreground and
background colors resolved it; the final run passed in 1.3 minutes.

The source scan covered 153 files. Three matches were existing synthetic
evaluation idempotency keys, verified unchanged against the baseline. Excluding
those exact matches left zero findings. Dependencies are unchanged from the
Task 25 audited lockfiles. CI repeats the locked dependency and coverage gates.

Standards review: PASS, zero open findings. Scoped simulation reads and the pure
episode reveal guard resolved its final history-disclosure finding.

Spec review: PASS, zero open findings. Exact response and observation links,
paged contributing records and cohort trends resolved its final gaps.

Both reviews were independent and read-only. The reviewers did not run tests.
Local logs are under `src-main/backend/.tmp-q25/`. Browser captures are under
`src-main/frontend/test-results/misconceptions/`.
Combined and corrective logs are `q29-full.log` and
`q29-combined-corrective.log`. Final browser logs are `q29-browser-final.log`
and `q29-learning-loop-final.log`.

The first PR CI run passed 112 existing browser cases. Eight cases failed because
two older tests expected the retired analytics heading. Both now expect the
current progress heading. All eight corrected cases passed locally in 18.4 seconds.
The correction retained their route and accessibility checks. Separate Spec and
Standards reviews passed again with zero findings.

The backend CI limit is now 45 minutes. The previous main run had been cancelled
after 20 minutes during backend tests; successful earlier runs took 17-19 minutes.
The longer allowance retains every test, migration, contract and coverage gate.

## Remaining work

Tasks 33-35, 38 and 41 remain separate. Existing partial tasks still need their
recorded operational approvals and release evidence. These synthetic checks do
not establish content validity, hosted readiness, native Safari support, manual
accessibility, live provider performance or permission to activate a study.
