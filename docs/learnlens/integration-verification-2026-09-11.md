# Integration verification — 11 September 2026

Updated with additional verification on 12 September 2026.

**Current runtime source: `67b6c92166793f96b56ef364c89b08bd483e2030`, pushed to
main.** The newest combined-source and capacity results are recorded at the end
of this receipt. Earlier sections retain their original source and execution
scope; references there to pending work are historical snapshots.

The six deliveries merged at `46aebb3` now share migration head `20260911_0051`,
registered models and regenerated API/TypeScript contracts. This receipt covers
the first integration batch and the compatibility corrections described below.
Further generated-task, formative-support, integrity-cue and assessor-editor
work is separate and requires its own affected checks.

## Recorded checks

**139 distinct backend cases pass across the recorded focused runs.** This is
not a complete application suite or a new coverage measurement. Case identities
were reconciled from JUnit reports, retaining the latest result for each case:

| Scope | Recorded result |
| --- | --- |
| Scanner-aware conditional reuse | 1 passed |
| Operational exports, canonical choices, structured tasks and moderation | 40 passed, 3 fixture failures; those cases passed after correction |
| Corrected moderation and refreshed validation tooling | 44 passed, including four moderation cases overlapping the preceding run |
| Combined migrations, protected history, replay, backup and metadata | 52 passed, 3 fixture failures; the three corrected cases passed on their own rerun |
| Shared course editor, study pages and app routing | 31 passed, 1 accessible-label failure; the corrected case passed on its own rerun, accounting for all 32 distinct frontend cases |

Backend Ruff checks and formatting pass across 540 files. Frontend TypeScript
and lint pass; the changed course editor also passed its subsequent scoped lint
and type check. Canonical OpenAPI and generated TypeScript drift checks pass.
The requirement matrix validator accepts all 143 rows. These checks retain
the existing production gates and use synthetic local data with no paid calls.

## Integration corrections

- Ordered the independently developed migrations 0047 through 0051, updated
  readiness and table inventory, and made new budget/moderation DDL replay-safe.
  Historical downgrade tests still exercise their original guards; current-head
  tests verify refusal before protected intake history changes.
- Added explicit synthetic scanning opt-ins to the new sourced test modules.
  Shared written-explanation fixtures now use `short_answer`, matching their
  actual content, instead of a quiz without declared choices.
- Exercised the study collector against the real provider ledger and moderation
  tables: exact response/course/task joins, nullable actual billing, reconciliation,
  multiple moderation cycles, pseudonymization and source-change invalidation.
- Corrected migration fixtures to supply a matching assessor review when testing
  the separate immutable-evidence guard, record normal course creation history,
  and explicitly assign the synthetic moderation policy owner assessor access.
- Made the indexed-material button's accessible name match “Reprocess and scan”;
  failed-material recovery retains “Retry processing”.

The validation manifest now includes the new moderation, provider, source-scan,
generation, typed-response and support dependencies. All 12 numerical fixture
distributions match. The 108 cases remain **DRAFT**, with zero expert-approved
cases, content/feedback/judge quality **UNVERIFIED** and AI release **PENDING**.
Numerical matches do not establish human or operational acceptance.

## Limits and remaining work

The prior 1,607-backend/319-frontend/132-browser receipt applies to its dated
source, not automatically to this integration. A full browser suite, actual
scanner/container execution, approved hosted deployment, representative paid
load/cost campaign and human/expert study/accessibility acceptance were not run
in this batch. The [task ledger](../../LearnLens_Remaining_Tasks.md) retains
12 unfinished numbered tasks and separates software from acceptance records.
The [operational checklist](operational-acceptance-checklist.md) identifies the
actual owner records still required.

## Follow-up integration

Source `72392d9` includes practice representations (`70ea786`, `c26bcae`),
submission review cues (`ba95955`, `99becc1`), multipart generation (`7f12e3e`,
`95b66a3`) and versioned assessor editing (`067f476`, `daed691`). These deliveries
add no migration beyond head 0051. Their delivery notes retain their scoped
owner checks; overlapping reruns are not added to the first-batch counts.

Independent review identified and corrected cross-task instructional support
during active transfer, fresh-input disclosure in generated public criteria,
scaffolding false positives in review cues, wrong-course editor access checks,
and obsolete generated-save callbacks. Each correction has a focused regression.
The editor owner records 28 passing affected UI cases and six backend checks.

Three additional checks passed against the integrated source:

| Integration boundary | Result |
| --- | --- |
| Course-wide transfer: instruction and replay blocked, approved access preserved | 1 passed, 5.32 seconds |
| Submission review cues against migrated immutable storage | 1 passed, 8.48 seconds |
| Generated-draft bridge with final authoring response | 1 passed, 3.81 seconds |

Canonical OpenAPI/TypeScript contracts and draft validation fingerprints were
refreshed. Ruff check/format passes across 607 files, the 143-row matrix is valid,
and frontend TypeScript, production build and lint pass. The build first found
invalid Windows-encoded ellipses in two study pages; those characters are now
UTF-8. Two Python files received formatting-only corrections. The build retains
a non-blocking large-bundle warning.

The draft report remains **108 DRAFT, zero approved, quality UNVERIFIED and AI
release PENDING**. The numerical receipt is deliberately retained from `fbf9ca6`:
its 12 matches belong to that recorded manifest. Quantum implementation and
scenario fixtures are unchanged; no new numerical execution is claimed and its
manifest digest has not been rewritten to imply one.

The full application/coverage/browser suite is delegated to the repository's
Quality and release gate on the pushed source. **The first CI run failed; see the
recorded result below.** The duplicate
standalone migration invocation was removed from CI because the full backend
suite already includes that file; all migration tests and the 80% service coverage
gate remain. This avoids an extra full local run followed by identical CI work.
Actual hosted, paid-provider, expert and human accessibility acceptance remains
outside these synthetic checks.

## First complete CI result and fixture repairs

[Quality and release gate run 34549196518](https://github.com/akshatporwal002/Monash-Honours-Project/actions/runs/34549196518)
ran against `262f2f6`. Secret and dependency checks passed. The backend recorded
1,775 passing cases, 19 failures and one setup error, with 89.61% service coverage
against the unchanged 80% gate. Frontend unit tests recorded 357 passes and
12 failures. Frontend browser/build stages did not run after that unit failure.
This is a failed combined run, not a passing application receipt.

The identified fixture repairs are integrated into local source `8161d2`:

| Repair | Focused evidence |
| --- | --- |
| Practice catalog mock response shape (`2616677`, merged at `8748fb2`) | 25 affected frontend tests passed; type and scoped lint checks passed. |
| Provider child-process import paths and runtime-control fixture forwarding (`63aaf45`) | Three affected selectors passed with inherited `PYTHONPATH` unset. |
| Canonical choice responses and scanned generation fixtures (`837c033`) | 15 affected tests passed. Invalid choices remain rejected rather than being normalized into invented answers. |
| Scoped scan fixtures and complete course/module upload fixtures (`6990432`) | 11 affected tests passed. The benchmark preparer and its child API/worker explicitly opt into synthetic scanning. |
| Child-worker scan-policy parity (`5934d14`) | Both previously failing recovery tests passed after reproducing their failures. The complete learning loop passed in 5.84 seconds; the integrated interruption/restore test passed in 61.24 seconds. |

The recovery failures were traced to `GROUNDING_UNAVAILABLE` /
`APPROVED_SOURCE_MISSING`: parent fixture scan settings were not inherited by
child workers. The repair supplies the same required synthetic policy version to
the children; it does not weaken production source checks. The two root files
passed scoped Ruff checks and formatting. Other owner receipts retain their
scoped lint evidence. These overlapping selectors are not summed into a second
full-suite count. Further feature integration requires a new combined CI result.

The [backend interface crosswalk](backend-module-interfaces.md) documents all
15 Section 8.2 modules and independently selectable test entry points for NFR9.
Its linked files were checked for existence; documenting test entry points is
not a claim that those tests were rerun.

## Second implementation wave

The next local integration includes source-led core and multipart generation,
actual feedback-conditioned task variants, generated support drafts and reviewed
stage access; complete generated teaching-content review; BP3 approval alignment;
reviewed learner profiles and linked progress interpretations; signed evaluator
release and exact-output import; governed study release/reconciliation and restricted
instrument text disposal; and approved-source vector retrieval.

Initial-generation integration at `e4468d6` attaches candidates and binds installed
formats and their quotes to immutable source passages before task revision capture.
Two focused formative/multipart journeys passed in 7.69 seconds, including retained
quality-review links and access-only transfer alternatives. An additional retained
support-marker approval regression passed in 1.97 seconds. Those overlap earlier
owner cases and are not added into a full-suite total.

The combined 0052–0054 migration chain initially exposed a SQLite constraint
reflection mismatch in 0054. Explicit named table constraints corrected it. The
complete upgrade, metadata comparison and protected-history downgrade check then
passed in 12.71 seconds. This records head 0054 only; subsequent migrations require
fresh integrated evidence.

Independent evaluator review found a read race around the course lock. `a875e15`
checks moderation visibility after acquiring that lock. `6980068` additionally
withholds suggestions for selected attempts before ORIGINAL review, including
candidate import/review, while preserving existing original/second visibility after
recorded independent decisions. Four focused owner checks passed. Historical
exposure is not retroactively certified as blind.

Canonical contracts were refreshed at `a8e608b`; frontend type checking, production
build and lint passed on the combined support/profile/moderation UI. The build has
a non-blocking large-bundle warning. No full local application rerun was made.

The first two real local 50-user campaign receipts remain failed measurements.
They exposed synchronous connection-pool blocking and then populated-dashboard read
amplification. The NullPool correction and accurate request-timeout labels are
integrated; the remaining populated-dashboard remediation and a fresh campaign are
active software work. Zero external provider usage does not prove billed cost.

The live-feedback FR17 gap is corrected in `0cc0f02`. Its owner recorded 131 focused
passes in 26.07 seconds, followed by 31 overlapping receipt cases after final
persistence hardening. Missing/stale/incomplete new reviews cannot authorize release;
historical v1 reads and honest structural-only local/assessed behavior remain.
The combined head 0055 upgrade/metadata/history check passed in 15.81 seconds.
Canonical contracts are unchanged by the private receipt; Ruff passes across 655 files. Final fingerprints, combined CI and ledger closure
follow these fixes. The current requirement matrix contains 143 rows: 97 implemented,
33 partial and 13 unverified. Human content/construct reviews, staffing, approved
study/data-plan records, paid-provider evidence, native/manual accessibility,
independent reuse effort and approved hosted operations remain separate acceptance.
Restricted-text disposal does not implement erasure of every research class or backup.

Dashboard correction `2f7007c` removed unused class-wide aggregates and repeated request-local pathway/completion work. Its copied populated-fixture diagnostic completed 50/50 logins and 50/50 dashboards; the maximum dashboard time was 5.875 seconds, so this is not a two-second target pass. Query count fell from 748 to 198. The earlier 408908e campaign recorded dirty source because of a restored whitespace-only diagnostic edit; its recorded dirty flag is retained. Final combined campaign evidence is still pending.

The second dashboard correction `54f34af` is integrated at `28d13f9`. It reduces the same populated read to 93 queries and bounds reuse to one exact read/session, invalidated on writes, flush, commit and rollback. Seven owner regressions passed. Its isolated dashboard p95 remains 2.875 seconds, above target. The [sanitized failed-campaign and diagnostic receipt](task-38-local-capacity-20260911.md) preserves failures and hashes. The next full campaign uses the combined clean source. Independent read-only review of the final feedback gate found no blocking issue.

Final candidate fingerprints were refreshed after `28d13f9`: 116 required files and 117 manifest entries, including release-packet tooling. The draft runner reports 108 cases, 108 blank forms, zero approvals and zero included result pairs, with no stale/missing fingerprint blocker; quality remains UNVERIFIED and AI release PENDING. The numerical receipt is unchanged and its exact original manifest from `fbf9ca6` is preserved as numerical-manifest.json. No numerical or provider execution was repeated.

## Combined `f8b7d13` measurement

The clean integrated 50-user campaign reached `awaiting_human` in 42 of 50
measured journeys; eight timed out. Ordinary-request p95 was 15.866519 seconds
with two censored observations, progress p95 was 10.770247 seconds and formative
feedback p95 was 39.725035 seconds. These fail to establish the respective
2/3/10-second targets. The measured HTTP error rate was 0.566%, while the
journey error rate was 16%; those denominators must not be conflated.

The campaign drained and stopped its owned processes. No human confirmation or
external provider billing occurred. Exact counts, runtime bounds and artifact
hashes are in the [capacity receipt](task-38-local-capacity-20260911.md).
Follow-up diagnosis reproduced API event-loop blocking during SQLite writer
contention and substantial repeated reads within submission transactions.
Remediation and a new measured receipt remain active software work.

[Combined CI run 34555972980](https://github.com/akshatporwal002/Monash-Honours-Project/actions/runs/34555972980)
targets the same pushed source. Frontend lint, production build and all 395
unit/accessibility tests in 97 files passed. Browser execution hit the 20-minute
job timeout after repeated failures in four scenarios: assessed reload/read,
rules and human assessment setup, and fresh equivalent-form work. The later
complete-worker-loop and misconception stages did not run. The browser gate is
incomplete and failed. The backend completed with 1,972 passes and 27 failures
in 1,446.78 seconds, with 90.01% service coverage against the unchanged 80% gate.
The workflow is failed, not a passing combined receipt.
The secret gate identified one historical documentation false positive;
the [scoped repair receipt](secret-scan-gate-2026-09-10.md) records the exact
exclusion and passing full-history scan with its retained positive control.
That local repair does not turn the original failed CI job into a passing result.

## Repairs following the second complete CI run

The 0055 replay repair checks the existing receipt column's shape before reuse
and restores missing history guards without rewriting values. All 11 affected
migration replay cases and four new shape/history-protection checks passed in
144.60 seconds. TEXT, NOT NULL and default-bearing incompatible columns remain
rejected; protected populated-history downgrade remains blocked.

All four failed browser scenarios now pass their focused headless Firefox runs.
Assessed reads use the authored short-answer response, fresh equivalent forms
explicitly start separate work, and both authoring scenarios verify that missing
alignment is rejected before completing the displayed alignment and publishing.
Rejection and accessibility checks remain in place. No wider browser suite was
repeated locally.

Backend fixture repairs supply explicit current source approvals, complete
quality-review findings and criterion alignment. The generation fixture contains
the outcome-relevant source and gate material required for its six requested task
types. Fifteen affected checks passed in the initial focused batch; five upload/
source checks required a shorter local temporary path on Windows. Four then passed,
and the remaining generation case passed after its source fixture was corrected.
These account for 20 distinct checks, including unchanged historical hash vectors
and new application-content binding checks. The overlapping follow-up typed
feedback file passed all 24 cases in 24.36 seconds: original supported/transfer
golden hashes, exact intermediate serialization, real practice/formal replay and
feedback, and application-content tampering. A shared verifier accepts only the
canonical digest or the exact intermediate typed serialization. New writes remain
canonical; stored hashes and evidence references are not rewritten.

API dispatch repairs move blocking submission/background/feedback/activity work
off the foreground event loop, with bounded background capacity and cancellation
drain before session cleanup. Focused owner regressions cover contention, claim
arguments, retries, rollback and security ordering; independent review found no
blocking issue. Submission reads fell from 1,456 to 348 SELECTs in copied-fixture
diagnostics, with unchanged three UPDATEs and 17 INSERTs. Concurrent-host timing
was noisy; these query reductions are not a new load acceptance result.

The final source-approval batching reduces the same submission to 282 SELECTs,
with unchanged writes. The latest isolated sample measured 0.210 seconds total
and 0.204 seconds holding the writer lock. Eleven focused source tests passed in
8.72 seconds. Independent review identified and resolved a pending-history refresh
issue: the final query reads fresh material scalars while preserving dirty immutable
entities for rejection by their history guards. Exact scan policy stays in the
existing helper; there is no reuse across writes. The next complete campaign
determines whether these changes meet the load targets.

The repaired candidate has 122 required source files and 123 manifest entries,
with digest `918bb71bc96351faec59ceb6038b0efb3d3a68a09e21a580c03e9c84e868b841`.
It retains 108 draft cases and blank forms, zero approvals and zero included result
pairs. Quality remains UNVERIFIED and AI release PENDING. Both the numerical
receipt and its original manifest remain byte-for-byte unchanged. Canonical API
contracts remain current; Ruff checks passed and formatting was normalized across
the five files reported by the final check. No full local suite was duplicated.

## Combined `5a57b66` campaign and simulation repair

The clean 50-user campaign reached human assessment for eight measured journeys;
40 ended with simulation timeouts and two with request timeouts. Ordinary-request
p95 was 7.803099 seconds. Progress p95 of 1.332045 seconds and formative feedback
p95 of 3.287348 seconds are conditional observations from surviving journeys;
they do not establish complete-loop acceptance. The overall journey error rate
was 84%. Owned processes stopped, the listener closed and feedback work drained.
The [capacity receipt](task-38-local-capacity-20260911.md) preserves the exact
counts, limits and hashes. No external billing or human confirmations occurred.

A bounded diagnostic reproduced fresh Qiskit process startup exhausting the
shared queue/execution deadline, with at most two children alive concurrently.
Twelve callers with a three-second diagnostic budget produced four completions,
six busy responses and two timeouts. The repair keeps the existing two process
slots and 15-second production budget, reuses only successful exact seeded
numerical results in a 128-entry LRU, and shares concurrent identical work.
Keys include ordered circuit inputs, shots, seed, policy and installed engine
versions. Returned results are detached copies. Every learner operation still
creates its own scoped durable run and outcome; no learner evidence is cached.

Forty-six distinct focused checks passed across three overlapping receipts,
including follower deadlines, failed-owner wakeups, retry after child failures,
eviction, deep-copy isolation, genuine child timeout and separate learner runs.
Both independent read-only reviews found no remaining blocker. Repeating the
bounded diagnostic from a cleared cache completed all 12 callers in 1.141 seconds
with one child execution. This is repeated-input evidence; diverse circuits still
use the bounded child execution path. A new complete load campaign remains due.

Numerical revalidation matched all 12 ideal-circuit scenarios after this boundary
change. Its new receipt and saved manifest preserve the prior numerical artifacts.
The refreshed 123-entry manifest digest is
`3604cb3d6e8f2f10a479b2799baae9e2f22f047a73867133ac4f0daa887d921c`.
The draft runner retains 108 draft cases, zero approvals and zero included pairs;
quality is UNVERIFIED and AI release remains PENDING. Combined CI on `5a57b66`
is still running. Its repository history scan found no secrets, but the synthetic
positive control failed. A deterministic control now passes local detection and
two regression checks without weakening history coverage or detection assertions;
the [secret-gate receipt](secret-scan-gate-2026-09-10.md) records the scope.

The completed `5a57b66` backend CI passed all 2,030 tests with one warning in
1,507.90 seconds and 90.16% service coverage. This includes the migration and
integrated recovery/reuse cases; the OpenAPI and generated frontend contracts
were current. Frontend lint, build and 395 unit/accessibility tests passed, as
did all 124 configured browser cases in 7.4 minutes. The separate complete-loop
browser test failed in all four browsers because it accessed the tutor before
explicit assessed work start; static review also found obsolete assessor field
IDs later in that journey. The subsequent misconception browser step did not
run. Dependency audit passed. The workflow remains failed because of that
complete-loop step and the synthetic secret-detection control; its successful
jobs do not certify the later simulation repair.

## Combined `7dddf9d` capacity result

The next clean campaign removed simulation timeouts from measured journey
outcomes, but still failed: 18 of 50 journeys reached human assessment, 19 ended
with continuation timeouts and 13 with request timeouts. Ordinary-request p95
was 8.023919 seconds against the two-second target. Progress p95 was 1.375461
seconds and formative feedback p95 6.672365 seconds; these are conditional on
surviving journeys. The HTTP error rate was 0.395% over 4,558 measured requests,
while the journey error rate was 64%. Both denominators remain explicit.

All feedback work drained and owned processes/listener stopped. No human result
or external billing was fabricated. The [capacity receipt](task-38-local-capacity-20260911.md)
records exact counts and hashes. Long database waits and continuation delays
remain active software diagnosis; repeated numerical reuse alone does not meet
the representative performance target.

The complete-loop browser fixture now explicitly starts assessed work and uses
the displayed assessor field labels. Its focused headless Firefox run passed
in 35.7 seconds, retaining tutor, transfer, non-leakage, saved evidence, revision,
activity choice, synthetic human confirmation and accessibility assertions.
The separate misconception journey, previously not reached in CI, passed
unchanged in headless Firefox in 16.6 seconds. A first local attempt stalled
before login because the correct Windows headless setting was not supplied;
that environment failure was corrected without an application change. Both
test servers were stopped. These two scoped checks do not replace the final
four-browser CI gates.


## Reviewed reminder and task-read repair candidate

The effective-deadline candidate filter preserves latest arrangement, revocation,
base-deadline fallback and active reminder pauses. Authoritative delivery locking,
publication checks, opt-out, rolling limits and pagination remain unchanged.
Twenty-seven focused reminder tests passed in 39.55 seconds. On the same copied
fixture, the first actual worker round dropped from 2.422 seconds, 2,922 SELECTs
and 25 UPDATE/commit pairs to 0.016 seconds, one SELECT and zero writes. The second
round correctly skips the scan during the existing idle interval. Both rounds
still processed continuations and outboxes; owned children were reaped.

Task availability/projection now uses the existing per-operation validation scope,
ending before the separate TASK_VIEW event and commit. Seven focused checks passed
in 17.14 seconds, including output/event preservation, fresh source/publication
checks and learner authorization. A narrow 16-actor burst of 32 actual mounted GET
routes, using signed cookie authentication, returned only HTTP 200. Dashboard p95
was 1.824360 seconds; task GET p95 was 0.846284 seconds, with exactly 16 view inserts.
It excludes login, worker and simulation load; a full 50-user campaign is still due.
Independent read-only review found no concrete blocker in either repair. No full
local suite was repeated.

The affected 123-entry draft manifest is refreshed to
`a8a2ed00081e63f31574fa5ae0c5b30f7e2665b8494a46285b1058e179d2e52f`.
The runner retains 108 draft cases, zero approvals and zero included pairs. Quality
is UNVERIFIED and AI release PENDING. Existing paired numerical receipts are retained;
no duplicate numerical revalidation was needed for these read-path changes.


## `dff979d` verification and status-only feedback polling

The clean `dff979d` campaign remains failed: 16/50 measured journeys reached human
assessment, 23 timed out waiting for continuation, ten had request timeouts and
one observed failed feedback. Ordinary p95 was 5.710440 seconds with three censored
observations among 266; progress p95 1.422584 seconds and formative feedback p95
7.368817 seconds are conditional on reached stages. HTTP errors were 25/5,336
(0.469%) while journey errors were 68%. All feedback work drained; owned processes
stopped and the listener closed. Ten continuation outboxes remained pending.
The capacity receipt preserves both incomplete work and all prior failures.

[CI run 34568934688](https://github.com/akshatporwal002/Monash-Honours-Project/actions/runs/34568934688)
has passed dependency and secret scanning. Its completed frontend job passed lint,
build, 395 unit/accessibility tests, 124 ordinary browser cases and all four
misconception journeys. Three complete-loop browser runs passed initially; Firefox
passed on one retry after its first submission response wait timed out. The job is
successful, but that flake remains explicit. Backend CI is still running.

A separate copied-fixture 50-caller diagnostic completed all 100 task-read and
simulation requests without SQLite errors. It found foreground thread saturation
and cumulative writer pressure, with task GET p95 7.047 seconds and simulation p95
12.093 seconds; this was neither a full campaign nor evidence of a deadlock.

Status-only feedback polling was then measured to repeat 49 SELECTs per response
before returning no content. Returning that same no-content status before context
collection removes those reads, with identical complete response JSON. This does
not skip route authorization or any checks before releasing retained feedback.
Six new regressions failed before the repair; all 19 focused status, existing
release and ownership checks passed after it in 41.56 seconds. Independent review
found no blocker. Five unnecessary E402 suppressions were also removed by moving
imports to their normal groups; listener registration order is unchanged. The
[suppression audit](lint-suppression-audit-2026-09-11.md) records remaining justified
boundaries and inactive maintenance annotations. Changed files pass Ruff checks.

The refreshed draft manifest digest is
`480a5f0277421fef2ff91d706ea24bf90277f7dafd6804d39207dfc965760422`.
There remain 108 draft cases, zero approvals and zero included pairs; quality is
UNVERIFIED and AI release PENDING. Existing numerical receipt/manifest pairs were
preserved without repeating the unchanged numerical calculation checks. These
later polling/import changes still require combined-source verification.


The subsequent concurrent worker/poll diagnostic located repeated curriculum,
publication and source checks inside the continuation decision while its claim
transaction held the writer. A scope around the pure `ActivityService.decide`
phase now reuses only those successful reads; it ends before category review,
suggestion persistence and the renewed claim fence. Eight focused checks passed
in 24.20 seconds, covering complete decision equivalence, publication changes between
calls, invalidation after an in-scope flush, lease expiry, restart, concurrent
idempotency and retry. Independent review found no blocker.

The same bounded two-round/200-request diagnostic reduced continuation SELECTs
from 448/479 to 103/132, with unchanged writes and commits. All 200 requests returned
HTTP 200 and the owned worker stopped. Combined writer-held time fell from 7.812
to 5.970 seconds, but claim acquisition still waited: this does not establish
capacity. The diagnostic included 100 explicitly projected status-only claims
and 100 actual terminal reads; it did not alter persisted workflow content.
Final combined campaign measurement remains due.

The final candidate draft manifest is now
`aadbfb11b4a22e272a0cb9af606f0f8ad27249ade07aad40f280558b9dd5c619`;
the zero-approval/zero-included-pair state and historical numerical pairs remain.
CI now retains failed-attempt page context and screenshots for seven days, even
when a retry succeeds, excluding video and trace archives. The earlier Firefox
flake's actual cause is unproven because its artifacts were not retained; no UI
or timeout change was made from that incomplete evidence.

## Published `ad187aa` results and remaining capacity work

Both `dff979d` and `ad187aa` are published on main. The earlier
[dff979d CI run](https://github.com/akshatporwal002/Monash-Honours-Project/actions/runs/34568934688)
completed successfully: 2,067 backend cases passed with one warning and 90.19%
service statement coverage. Its frontend, dependency and secret gates also
passed, with the previously recorded Firefox retry retained as a limitation.

The [ad187aa CI run](https://github.com/akshatporwal002/Monash-Honours-Project/actions/runs/34570781006)
completed successfully on 11 September at 07:04 UTC. Its backend passed **2,075
cases**, one warning, in 1,514.75 seconds with **90.21% service statement coverage**.
Formatting, lint, generated-contract, migration/recovery, secret and dependency
gates passed. These results were collected on 12 September without rerunning the
suite. Frontend passed lint/build and 395 unit and
accessibility cases in 97 files. Ordinary browser checks had 123 first-attempt
passes and one WebKit circuit-keyboard case that passed on retry. All four real
worker learning loops and all four misconception journeys passed first attempt.
The WebKit failure was a captured console access-control error for a practice
representation request; it is not established as a failed circuit operation.
Its retained [failure artifact](https://github.com/akshatporwal002/Monash-Honours-Project/actions/runs/34570781006/artifacts/10188069584)
supports further diagnosis. Independent inspection found all circuit operations,
persistence, simulation and Axe assertions passed before the final error-list
assertion failed. Playwright's WebKit adapter also maps JavaScript-source console
errors to page errors; the message alone does not establish an unhandled promise
rejection. Catalog cancellation is plausible but unproven. Preserve the assertion
and capture sanitized request-failure details if it recurs; no speculative error
filter or timeout change was made. Successful retries are not reported as
first-time passes or as proof that the browser issue is fixed.

The clean 50-user campaign on `ad187aa` **failed**. It reached the human-assessment
boundary for 28/50 measured journeys; 15 had continuation timeouts and seven had
request timeouts. Journey errors were 44%, separate from 20 HTTP errors across
5,125 attempts (0.3902%). Ordinary-request p95 was 5.507467 seconds across 299
observations, failing the two-second target. Conditional progress p95 was
1.726871 seconds (78 observations); conditional formative feedback p95 was
18.099249 seconds (28 observations), failing its ten-second target. These API
measurements do not measure browser rendering. No human-confirmed complete loop
or actual paid-provider cost was obtained.

Owned processes stopped and the listener closed. Feedback work drained, but nine
continuation outboxes and one continuation job remained pending; one simulation
was interrupted. The [capacity receipt](task-38-local-capacity-20260911.md) and
paired JSON preserve exact counts, hashes and all seven earlier runs.

Three private configuration experiments used the same bounded two-round,
200-request diagnostic. Each returned 200/200 HTTP successes, which is not the
full load workload. With the default 40 foreground slots, status/terminal p95
were 3.812/16.484 seconds. Eight global slots improved terminal p95 to 7.218 but
worsened status p95 to 6.188 seconds. Limiting only terminal work to eight slots
produced 4.078/18.562 seconds and was rejected. A private SQLite WAL copy with
FULL durability produced 4.093/12.797 seconds, but total diagnostic time increased
from 25.0 to 27.828 seconds. Extra per-connection verification overhead limits
the WAL comparison; it does not justify a production journal change. The copy's
backup returned `ok` from SQLite `quick_check`, and the original database retained its
journal mode. No production concurrency or journal setting changed.

Task 38 still needs engineering to reduce SQLite writer contention and
continuation delays, followed by a representative clean campaign. Future work
should retain claim fencing, durable learner evidence and request limits rather
than weaken them to pass a measurement. Comparable 5–100-user scaling,
approved-host validation and actual billed human-confirmed loop cost remain
separate acceptance work. Docker and paid providers were not used in this run.

## 12 September: task-panel repair, continuation work and recovered evidence

Main was already current when fetched. Runtime commit `2b9c951` publishes two
reviewed repairs and refreshed Task 35 draft provenance:

- Distinct React keys for the representation panel and deadline stop duplicate
  panels accumulating during task saves. The regression reproduced duplicates
  before the repair. Five mounted keyboard cases passed; the permanent WebKit
  keyboard case passed with new panel/deadline count assertions after saves and
  reload. No retry, timeout or error-filter allowance was increased.
- Continuation updates omit a full learner-model view that their caller never
  uses. This removes five post-store SELECTs per new model while preserving the
  normal builder's default view, fresh initial reads, cumulative evidence,
  correction behavior and atomic progress/model persistence. Twelve focused
  checks passed, including claim expiry, restart, concurrent head changes and
  rollback. Independent review found no blocker. This is a bounded work
  reduction, not a claim that load targets are met.

The current draft manifest is
`35277bdb8e9dd9096ea457ed59bd4c8e87b9da79a504bd3b83c72226eae8cea2`.
Its 108 cases remain drafts with zero approvals/included pairs; quality is
UNVERIFIED and AI release PENDING. The earlier numerical receipt and matching
historical manifest remain paired; numerical tests were not repeated for these
non-numerical changes.

[CI run 34668835636](https://github.com/akshatporwal002/Monash-Honours-Project/actions/runs/34668835636)
completed successfully for runtime `2b9c951`, with all four jobs passing. Backend
job `103486157887` completed at `2026-09-12T03:17:09Z`: **2,077 passed**,
one warning, in **1,448.33 seconds (24:08)** with **90.18% service statement
coverage**. Formatting, lint, generated contracts, migration/recovery, secret
and dependency gates passed. Frontend
passed 396 unit/accessibility cases in 97 files, 124 ordinary browser cases on
first attempt and four misconception journeys on first attempt. Three complete
learning loops passed first attempt; WebKit passed on retry. Its first attempt
reached the next-activity URL before the final error-list assertion reported a
`learner-preferences/me` access-control-check console message. The retained
[failure artifact](https://github.com/akshatporwal002/Monash-Honours-Project/actions/runs/34668835636/artifacts/10289832868)
is evidence for diagnosis, not proof of a failed learner operation. Successful
retries remain distinct from first-attempt passes.

Private controlled WebKit probes clarified the earlier practice-catalog message.
After the duplicate-key repair, an intentionally held request cancelled by a
busy-state transition produced `requestfailed` without a page error. Intentional
reload produced catalog and tutor transport-console page errors while the final
DOM remained correct. Observers installed before page scripts saw zero
`window.error` or `unhandledrejection` events. Positive controls verified that
actual throws and rejected promises were captured, and a caught non-cancellation
network failure did not create a page error. The forced-reload diagnostic failed
its strict page-error assertion as expected. Playwright maps some WebKit console
messages to page errors; this supports transport-console classification in that
controlled case, but does not prove every CI retry has the same cause. No blanket
filter was added; unmatched tutor/preference messages still need exact diagnosis.

A corrected private journal comparison applied journal-mode verification only
once before timing and used equal 200-request/two-worker-round workloads on fresh
copies. DELETE returned 200/200 HTTP successes with status/terminal p95
2.063/9.954 seconds and 12.328 seconds total. WAL returned 200/200 with
3.141/9.812 seconds and 15.453 seconds total. Both made 19 UPDATEs, 108 INSERTs,
one DELETE and 118 commits including cleanup; backups passed `quick_check`.
The comparison retained FULL durability and the 30-second writer budget. It
provided no overall reason to change production journal mode. These narrow
measurements do not certify the full campaign or isolate gains across dates.

The clean `2b9c951` 50-user campaign **failed**: 31/50 reached human assessment,
six had continuation timeouts and 13 request timeouts. Journey errors were 38%,
separate from 18/5,454 measured HTTP errors. Ordinary p95 was 5.601966 seconds
with one censored observation; conditional formative p95 was 27.481452 seconds
and progress 1.993978 seconds. No human-confirmed loop or actual external cost
was measured. The [capacity receipt](task-38-local-capacity-20260911.md) and JSON
preserve exact outcomes, all eight earlier campaigns and artifact hashes.

Its post-shutdown export encountered a hot rollback journal. A subsequent
benchmark-tooling repair opens the existing stopped synthetic fixture in `mode=rw`
for normal SQLite recovery, then backs it up with explicitly closed connections.
A reproduced hot-journal regression and launcher/usage checks passed: **32 cases**.
Independent review found no blocker. Original measurement bytes were preserved;
only export/count/cost postprocessing was recovered, with an explicit annotation
that drain/cleanup were reassessed afterward. The workload was not rerun. Source
and snapshot passed `quick_check`; 19 continuation outboxes remained pending and
one job running, despite no unfinished feedback workflows. This repair changes
benchmark tooling only and has focused evidence separate from runtime CI.

Task status remains **30 completed, 10 partial, one remaining: 11 unfinished**.
Tasks 38 and 39 retain engineering/reliability work. The other open tasks primarily
need actual approvals, expert ratings, approved content/hosts or human trials;
Task 33 may require additional record-class disposal after its retention plan is
approved. Five standalone PD4 forms remain explicitly staged extensions under
the controlling requirements, rather than newly discovered mandatory MVP gaps.
These checks used local synthetic data, with external providers and research
activation disabled; no Docker-based or approved-host measurement is claimed.

A final private FIFO write-admission prototype also failed to improve the whole
workload. Both paired phases used fresh identical fixtures and separate API and
worker engines; their gates were independent, matching separate admission domains.
Baseline versus gate: total 11.469 versus 12.047 seconds, status p95 1.594 versus
2.453 seconds, terminal p95 7.484 versus 6.015 seconds. Both worker rounds became
slower. Both returned 200/200 HTTP successes with zero database errors and identical
19 UPDATEs, 108 INSERTs, one DELETE and 118 commits. Gate budget maintenance added
238 PRAGMAs, included in measured wall time. SQLite integrity checks passed.
The prototype consumed the existing configured busy budget, retained ownership
until actual transaction completion and checked cancellation, failed commit,
nested independent writes and queue cleanup. It remains an in-process diagnostic,
not full-load proof. No production gate was introduced; all owned workers stopped.
Configuration experiments are finished. Further Task 38 work needs transaction
and continuation-queue design changes backed by representative evidence; neither
WAL nor a process-local admission gate is an established remedy.

## Installed package and teammate handoff verification — 12 September

A noneditable wheel built from the local `dbdec4b` working tree passed an
isolated import and entry-point smoke check. The source was dirty; this is a
candidate artifact receipt, not a clean-source full-suite result. The probe
loaded 324 application modules from the installed package, both worker and
administrator-provisioning entry points, 60 copied migration revisions through
head `20260911_0055`, and the copied backup command's help path. Removing
`app.worker` from a separate installed copy failed as expected, proving that
the checkout's editable installation cannot hide a missing packaged module.
The wheel SHA-256 is
`2e96c0a0b16deceb06b40a8b42522f391e797cf15956f5cf39000e7b98bbbf72`.

The reusable check is `src-main/scripts/verify_installed_package.py`. CI now
prepares its own production-only, noneditable dependency environment with the
release installation flags before running the probe. Local smoke dependencies
came from the existing locked all-extras environment; the production-only CI
step needs its own completed CI receipt. This does not execute a container,
create an administrator, activate research, exercise an approved scanner or
establish hosted deployment acceptance.

Four existing teammate guides now describe the implemented operator and learner
flows: `src-main/README.md`, `src-main/docs/architecture.md`,
`src-main/docs/task-type-extension.md`, and
`src-main/docs/research-export-schema.md`. They distinguish local structural
receipts from semantic approval, current export contracts from historical ones,
and the implemented conditional reuse example from staged standalone task
forms. Source paths, links and actual UI labels were checked. The guides and
package checker passed independent source review. No actual approval or named
operator record was supplied by this documentation work.

## Checkpoint, transfer and browser repairs — local candidate

Checkpoint capture previously called a draft save that committed before locking
again to preserve the checkpoint. An independent request could replace that
draft in between, causing the first request to freeze the second request's
input. A late checkpoint/evidence failure also left the draft changed. The
adjacent transfer-start path had the same split-transaction issue. Draft
validation, checkpoint/evidence capture and transfer-stage creation now use the
same existing sequence lock and final transaction. Access checks, immutable
history and required response validation remain intact.

Three checkpoint regressions failed before the fix. The corrected checkpoint
and surrounding lifecycle/evidence checks passed 65 cases in 97.01 seconds.
Two transfer regressions then failed before the analogous repair; the final
checkpoint/transfer/lifecycle selection passed 39 cases in 52.38 seconds. These
selections overlap. Independent source review found no blocker. A separate
25-caller start/checkpoint diagnostic returned 50/50 successes in both arms and
reduced commits from 75 to 50, but total time increased from 4.609 to 5.734
seconds. This establishes a correctness repair, not a throughput improvement.

The WebKit investigation reproduced the exact learner-preferences access-control
message by delaying the application's initial preference fetch until document
exit. Before the fix, the fetch started with an unaborted signal after
`pagehide`; WebKit reported the transport message and the fetch rejected with
`TypeError: Load failed`. The component now aborts that read on document exit,
skips queued work after cancellation, and retries an interrupted initial load
when a cached page resumes. Already-loaded unsaved choices are preserved.

Three of four new lifecycle regressions failed before the repair. The final
preference selection passed nine unit cases in 5.49 seconds, plus TypeScript,
scoped lint and the production build. Seven distinct focused WebKit cases
passed across a six-pass verification run and one targeted positive-control
rerun: the latter corrected only an expected error-message prefix in the new
observer test. The original public learning loop passed in 24.9 seconds. In the
repaired controlled boundary, abort precedes fetch start, rejection is an
`AbortError`, and no page error, window error or unhandled rejection occurs.

Permanent passive diagnostics preserve document/error/request context as
bounded, redacted JSON. Genuine throw, rejected-promise and caught-network
controls are retained. The original page-error and accessibility assertions,
timeouts and retry limits are unchanged. The old CI artifact lacks a request
timeline, so the controlled reproduction does not prove the original CI timing.
Combined Linux/browser CI is still required for this candidate; local WebKit
does not establish native Safari, assistive-technology or first-time-user
acceptance. Independent review found no source blocker.

## Continuation and feedback-view transaction work — local candidate

Model hydration now loads linked estimate/evidence identities with a joined
read, reducing the current/timeline path from five SELECTs to three while
preserving scope, corruption, metadata and predecessor checks. Local
continuation creation shares its transaction with outbox acknowledgement, and
progress recording shares its existing lease/claim fence with the durable
progress marker. Rollback and replacement-claim cases are retained. Focused
verification passed selections of 17, 101 and 32 cases; these overlap and are
not added into a full-suite count. Independent review found no blocker.

The first combined continuation diagnostic was slower than its immediately
following baseline (21.047 versus 12.703 seconds). A subsequent frozen-module
baseline/candidate/candidate/baseline block measured 11.485, 9.140, 12.390 and
12.250 seconds, with 200/200 HTTP successes in each arm. Timings overlap; no
statistically established gain or consistent gross slowdown is inferred.
The first baseline completed one fewer recommendation: its other job retained
progress and scheduled a retry for `next_task_recommender_unavailable`. The
other arms completed both recommendations. Unequal worker outcomes prevent
treating the four durations as equivalent-work throughput proof.

The dominant remaining narrow-workload write cost came from separate first-view
learning and audit records. The candidate preserves both records in one fresh
telemetry session, independent of the student request. Existing typed mappings,
pseudonymization, strict correlation/replay checks and best-effort behavior are
retained. A physical SQLite transaction precedes per-record savepoints. A
failed preflight read rolls back before the partner is checked, preserving
recovery from an invalidated connection. No access/release check or recorded
event is suppressed.

The frozen feedback-view pair returned 200/200 successful requests in both
arms, with equal retained table counts and successful integrity checks. Total
time fell from 10.203 to 9.078 seconds and commits from 115 to 65. This is a
single narrow diagnostic with two worker rounds, separate API/worker engines,
unchanged timeouts and no external provider. It does not establish the complete
50-user journey, hosted scaling or billed cost. After that pair, only the cold
connection-failure path was extended: if a lost database connection aborts the
batch, each unsettled prepared record gets at most one independent recovery
attempt, using its original identifiers and replay rules. Known conflicts are
not retried. Newly inserted but uncommitted records remain eligible for recovery.

The combined repository/API/transaction-fault selection passed 55 cases;
subsequent focused selections passed 17 and 15 cases for fixture compatibility
and preflight recovery. The write-disconnect regression failed before its fix;
the corrected recorder selection passed 17 cases in 12.06 seconds, followed by
six bounded-disconnect/conflict/outer-rollback checks in 2.60 seconds. These
selections overlap. Independent review cleared the final recovery bookkeeping.
The normal-path timing pair was not rerun for the cold-failure-only change.
Final integrated verification remains to be recorded for the final source.

Task start now uses the existing operation-local validation scope, with its
sequence lock and operation order unchanged. The real regression reproduced
three identical revision/review lookups before writes and two after the course
update. Reuse reduces each unchanged phase to one lookup; required draft-flush
and course-write invalidation remain. The new checks and surrounding work-start,
dashboard-read and submission-concurrency checks passed 28 cases in 28.70
seconds, including source revocation across requests and after a draft flush.
Independent review is clear. No additional cohort latency result is claimed
for this final read-work change.

The draft validation manifest now includes the four model/continuation/handoff
repository dependencies changed in this batch: 126 required paths and 127 total
entries. Digest: `f88aa8436570434cbcf1464f9a3b0c1e37714d34ec21d4c339ecf335ad7601b3`.
The 44 existing validation-tool checks pass. All 108 cases remain drafts, with
zero approved cases or included rating pairs, quality UNVERIFIED and AI release
PENDING. Historical numerical evidence keeps its original source and digest;
it was not rerun or rebound to this candidate. The 143-row matrix is valid.


## Published 67b6c92 — combined CI and bounded corrections

The candidate sections above were published in `67b6c92166793f96b56ef364c89b08bd483e2030`.
Their references to local candidates and pending CI are historical. [CI run
34687133232](https://github.com/akshatporwal002/Monash-Honours-Project/actions/runs/34687133232)
finished with frontend/dependency success and backend/secret-job failures:

| Scope | Recorded result |
| --- | --- |
| Backend job 103535963625 | 2,122 passed, two failed, one warning; 1,494.41 seconds (24:54); 90.22% service coverage, above the unchanged 80% gate. |
| Backend correction | Both failures were obsolete ninth positional arguments in the feedback-read variants of `test_feedback_route_contention.py`. The test now names `view_events` and `security`; security rejection and event-loop release assertions remain. All five cases pass in 1.32 seconds. Scoped lint/format and the two contract checks skipped by CI also pass. |
| Frontend job 103535963451 | 400 unit tests/98 files; 136 ordinary browser checks (9.1 minutes), four complete learning loops (1.7 minutes) and four misconception journeys (39.5 seconds), all first attempt. Lint/type/build pass. |
| Installed package | Production-only noneditable installation passed: 325 application modules, both console entries and 60 migrations, head `20260911_0055`. No source-checkout fallback, container or approved-host claim. |
| Dependencies | Job 103535963548 succeeded. |
| Secret scan and correction | Job 103535963552 found one ordinary-prose false positive. Only its exact historical fingerprint is excluded and the current prose is reworded. The pinned local gate passes: 305 text commits / 404 reachable, zero history findings and one unchanged expected positive-control finding. The [scanner receipt](secret-scan-gate-2026-09-10.md) retains artifact identity and scope. |

The two repaired cases account for all 2,124 backend case identities across
CI and the focused correction. This is not a fresh complete-suite pass, and the
hosted run is retained as failed. No unchanged frontend or full backend suite
was repeated just for the test-call and prose corrections.

## Clean 67b6c92 load campaign and remaining engineering

The campaign used one warmup and one measured round of 50 synthetic users,
with peak concurrency 50 in both. Measurement reached **45 awaiting human,
five request timeouts and zero continuation timeouts**. Journey errors were
10%; HTTP errors were 5/7,360. Ordinary p95 was 4.4337269 seconds (331 observed,
two censored), progress 1.5165027 seconds (93), formative feedback 35.7989416
seconds (45) and assessed response 74.6502288 seconds (90). Ordinary and
formative targets still fail. Stage metrics are conditional on reaching them.

Warmup retained 21 awaiting human, 18 continuation timeouts, four feedback
timeouts, six request timeouts and one interrupted simulation. Export and
owned-process cleanup succeeded. All ten campaigns and raw-receipt hashes
remain in the [capacity record](task-38-local-capacity-20260911.md). Zero actual
human confirmations or external provider invoices were generated.

The five measurement timeouts occurred before a submission/workflow existed:
two task reads, one start, one help and one simulation. A separate 50-actor
startup diagnostic identified waiting for the first learning-event INSERT as
the dominant task-read delay. Two extra validation scopes reduced reads but
made the matched 250-request workload slower (14.969 to 16.157 seconds); they
were rejected and kept private. One equal-scope private FIFO admission probe
reduced that workload to 13.859 seconds and task-read p95 from 14.468 to 4.000
seconds, preserving all table counts. Both arms included the extra scopes, so
this is not a gate-only comparison against published 67b6c92. Global async,
ownership, SQL-coverage and cleanup hazards remain; no gate was shipped and no
full-capacity result is inferred. Runtime journal settings remain unchanged.

The task count remains **30 completed, 10 partial, one remaining**. Task 38
retains active engineering. Task 39's identified browser repair now passes
combined CI; its remaining acceptance needs actual native-browser, assistive-
technology and first-time-user observations. Other open tasks retain their
named human/content/provider/host inputs; no approval or rating is fabricated.


## Task-view admission candidate after 197ffde

The task-view-only candidate wraps the final required event and existing commit
after unchanged authorization/projection. A file-backed SQLite engine using
NullPool admits these writes in arrival order. Other pools/databases, active
database transactions, pending mutations and event-loop callers retain their
previous behavior. Queue waiting, event flush and commit share the remaining
SQLite timeout budget; no deadline is increased. Cleanup releases the opaque
ticket, attempts all listener removals, makes any persistent listener inert,
restores or invalidates a still-open connection and preserves the primary error.
No generic commit lock, SQL interception or other writer scheduling is added.

Before implementation, four behavior regressions and four cleanup-fault cases
failed. The final focused selection passed **62 cases in 62.06 seconds**, covering
the helper, task projection, dashboard queries, core LMS API, feedback telemetry
and route contention. Lint/format pass; two independent read-only reviews found
no blocker. The new helper is included in mandatory validation provenance:
**127 required paths / 128 entries**, draft digest
`d02e626c134453dff44ea4748762b679e83c8d06e6eb8a63a884727b8090d964`.
All 44 validation-tool checks pass in 1.61 seconds. Cases remain 108 DRAFT,
zero approved or included pairs, quality UNVERIFIED and AI release PENDING.
Historical numerical evidence remains unchanged.

The preceding private task-view-only experiment used unchanged 67b6c92 application
code and the same frozen fixture in both arms: 250/250 requests each, identical
before/after table counts and 1,100 inserts / 250 updates / 300 commits. Total
duration was 14.969 versus 14.250 seconds; task-view p95 13.609 versus 10.063
seconds. Substantial waiting remained, including 7.750 seconds in admission.
This one narrow comparison supports evaluation, not a throughput or full-capacity
claim. The production candidate separately fixes pool and cleanup boundaries;
its clean representative campaign and combined CI remain to be recorded.
