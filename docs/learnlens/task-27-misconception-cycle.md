# Task 27: reviewed misconception checks

Local implementation on 10 September 2026, based on main `34d686f`.
Tasks 25, 27 and 29 share one delivery branch.

## Delivered behaviour

Course educators can open a learning check from a learner's saved feedback and
scoped evidence. They approve a possible hypothesis, confidence, probe, alternate
explanation, support level, fresh question, evidence rule and selection reason.
The cycle freezes these choices and its reviewed task and source versions.

Learners answer the probe, read the explanation, revise, and explicitly start a
fresh check. Starting that check hides earlier teaching and denies tutor and
conceptual hints for the task. Access support remains available. Each response
records reasoning, confidence and declared instructional help.

Educators link supporting and contradicting observations before recording
UNCERTAIN, PERSISTED, WEAKENED or CORRECTED. Persistence uses the stages approved
for that cycle. Correction requires contradicting evidence from its unaided fresh
check. One wrong answer cannot produce a certain label. Review reasons, next
actions, initial evidence and each correction remain visible in history.

Uncertain and persisted reviews create one unresolved-misconception signal in
Task 28's assessor queue. The queue includes the preserved cycle. Correcting a
hypothesis does not silently close a human case. Existing queue owners handle
acknowledgement, action, resolution and closure.

The learner can end an unfinished check with a reason. The educator can retire
one after approval drift or another content problem. Both preserve saved work
and release the check's help restriction. A replacement needs a new approved
fresh question. Writes use version checks and exact request replay.

## Evidence and formal assessment

Teaching explanations produce separate scaffold evidence with their approved
support level. Later practice and assessed revisions retain that support and
its evidence link. Earlier responses keep their original observations.

Frozen formal responses expose the actual teaching to assessors and feedback
context. Answer-revealing instruction and teaching after a fresh stage began
cannot silently become pass evidence. These items stay available as learning
evidence and need a fresh approved task for a formal result. No existing result
is changed by opening, answering or reviewing a misconception check.

New learner-model snapshots preserve earlier estimates, evidence and uncertainty.
They also retain accepted learner corrections and their review links. A teaching
review does not replace the formal assessment authority.

## Storage and recovery

Migration `20260910_0043` adds immutable hypotheses, responses, reviews and closure
records. Foreign keys and append-only guards protect accepted history. Readiness
expects this single head. No migration has been applied to a live database.

A populated downgrade refuses before changing tables or the migration version.
The preflight also retains the earlier migrations' history guards. Model or
queue failures roll back the whole review transaction. The migration tests cover
fresh, populated and preserved-history paths.

For release, back up the database and source files before applying the migration.
Use the existing isolated restore procedure to recover the prior package. Do not
drop populated learning-check tables or rewrite their histories as a rollback.

## Verification

The focused final backend batch passed 51 tests. It covered the cycle, all four
states, exact retries, stale requests, roles, real authentication and CSRF, scope,
approval drift, exit, model corrections, transaction rollback, migration safety,
support attribution, assessor visibility and formal-result boundaries.

The earlier migration batch passed all 45 checks. Ruff and generated API contract
checks pass. Independent Standards and Spec reviews have no open findings after
the corrections below.

The full combined backend run finished in 46 minutes 59 seconds: 1,252 passed,
eight failed, and service coverage reached 87.88%. Seven failures expected the old
migration head. The other rejected two gap-matrix status rows. These were fixed
while the full run retained its previously loaded test functions. All eight
failures then passed in a separate 21-test batch, which finished in 114.31 seconds.
The runtime did not change between these runs. The full run also emitted one
fixture-only Pydantic warning about an integer supplied for a support-level enum.

The new browser journey uses real authentication, CSRF and the isolated local
test server. Every browser gets separate synthetic learner and educator records.
It covers teacher approval, failed-save retry, reload, revision, fresh work,
uncertain review, correction history and automated accessibility checks.

The first four-browser run stopped at an ambiguous test selector. After that
selector was corrected, Chrome, Edge and WebKit passed. Firefox completed the
workflow and accessibility assertions but timed out while taking its screenshot.
Its separate unchanged rerun passed in 18.9 seconds. The final run then passed all
four browsers in 32.7 seconds and saved their history screenshots. The Firefox
capture was visually inspected and showed readable, unclipped history.

The full frontend run passed 269 tests and had five timeouts. All ten tests in
those five files then passed unchanged with one worker. The new assessor support
display test passed in the full run. Final Node 22 lint and production build
checks passed. The build retains the existing large-chunk advisory.

The final source scan covered 67 changed files and found no leaks. A separate
checkpoint manifest triggered three generic-key matches on file hashes. Each
value was verified against its source file; the source-only scan is clear.
Dependencies are unchanged from the Task 25 audited lockfiles.

Local logs are under `src-main/backend/.tmp-q25/`. Browser screenshots are under
`src-main/frontend/test-results/misconceptions/`.

The combined and corrective logs are `backend-combined-final.log` and
`backend-combined-corrective.log`. The final four-browser log is
`q27-browser-artifacts.log`. A local code checkpoint and hash manifest are saved
under `.tmp-q25/` for separating later work. No deployment has been performed.

## Independent review corrections

Spec review found an exit gap after teaching approval changed. It also found
teaching disclosure during the original assessed transfer. Closure records and
the assessed-stage gate resolve both.

Standards review found that new snapshots could lose accepted corrections and
that persistence used an implicit stage rule. Snapshot correction links and the
educator-approved stage rule resolve those findings.

Final review found missing support attribution in practice revisions and formal
assessor context. Scoped scaffold reads, the frozen-response teaching record,
formal result-use guards and real submission regressions resolve both findings.

Open findings: Standards 0; Spec 0. Reviews were read-only and did not run tests.

## Activation limits

Synthetic prompts and educator actions prove application behaviour. They do not
approve real quantum content or an expert judgement baseline. Course educators
must approve each real check and its evidence rule before use. Task 28 still
needs the recorded D-09 operational owners and staffing details.

Research consent, expert validation, native Safari, manual accessibility, live
provider measurements and hosted release evidence remain separate tasks.
