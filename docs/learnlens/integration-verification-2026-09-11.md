# Integration verification — 11 September 2026

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
