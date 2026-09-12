# Task 38 local capacity and recovery receipt

These are unpaid synthetic loopback measurements. They do not establish hosted
capacity, external-provider performance, human assessment results or cost per
human-confirmed learning loop. The initial 50-user campaigns failed. Their raw
reports remain unchanged in ignored scratch storage, and their sanitized metrics
and SHA-256 digests are retained in
[the machine-readable receipt](task-38-local-capacity-20260911.json).

## Software delivered

- `63aaf45`: portable subprocess imports for both provider interruption tests and
  the runtime-control fixture's required monkeypatch argument. With inherited
  `PYTHONPATH` unset, the three previously failing selectors passed in 12.77 s.
- `09d0889`: upload-owner fixture dependency, explicitly scoped synthetic scanning.
- `d223c975`: bounded unpaid launcher, valid generated learner identities, durable
  usage extraction and cost reconciliation. It preserves nullable actual costs,
  failed/unknown attempts and separate legacy metadata without double counting.
  The three harness/usage/launcher files passed 62 tests in 0.86 s; the additional
  learner identity contract passed in 0.60 s.
- `408908e`: file-backed SQLite uses `NullPool` so synchronous connection checkout
  cannot block the event loop needed to release sessions held across awaits.
  Memory database pooling, foreign keys and the 30 s writer timeout are preserved.
  The minimized old-pool reproduction failed 5 of 20 asynchronous reads. The fix
  passed that reproduction, 50 mounted logins and four durable budget/dispatch/
  reconciliation races: six tests in 9.13 s with inherited `PYTHONPATH` unset.
- `7dc8d62`: request wall timeouts now report `request_timeout`. Previously they
  could escape as `TimeoutError` and be labelled `phase_deadline`. The regression
  reproduced that exact mismatch; all 34 harness tests passed in 0.53 s. Original
  report labels remain unchanged, and those failures were always counted.
- `2f7007c`: populated dashboards avoid unused whole-class progress calculations,
  share completed-task lookups and validate each pathway once per dashboard read.
  Readers are newly created per operation, never cached across requests or on a
  session. The same populated three-task dashboard fell from 748 to 198 queries.
  Adding 20 unrelated enrollments previously grew a smaller fixture from 309 to
  349 queries; the regression now keeps query work independent of that growth.
- `54f34af`: successful task/source/formal-declaration validation reads are reused
  only within one dashboard operation and its exact database session. Returning
  or raising discards the scope; flush, commit, rollback and non-select statements
  invalidate it. Pending ORM changes also prevent reuse. No exceptions are cached.
  The same populated dashboard fell further from 198 to 93 queries, an 87.6%
  reduction from the original 748. A real formal-plus-practice fixture reproduced
  15 source-approval reads; the corrected read performs seven, retaining distinct
  optional/required checks and the formal publication check.

The dashboard correction passed six focused scope, approval, formal-assessment
exclusion and prerequisite tests in 13.69 s. Its two dashboard regressions passed
in 3.58 s, including fresh confirmation evidence, isolation from another learner,
and removal of old bypasses after a new pathway is published. Three finalized
login/concurrency checks passed in 10.33 s. Scoped Ruff checks passed. These are
affected tests, not a full-suite result.

The final validation-reuse change passed seven focused tests in 12.33 s, including
retirement of a source after an earlier successful read, invalidation after a
flush within the operation, and rejection by a later dashboard request. Scoped
Ruff checks passed again.

## Measured campaigns before dashboard correction

All runs used Windows AMD64, Python 3.11.16, 12 reported logical CPUs, SQLite,
one API process and one durable worker. They retained CSRF, rate limits and
simulation bounds. External provider execution and research were disabled.
The material scanner was explicitly synthetic, so these runs provide no malware
scanner effectiveness evidence. Polling was one second; the request bound was
30 s, feedback bound 90 s and phase bound 600 s. The workload is closed-loop,
with fresh learners and no think time.

| Run | Measured journeys reaching human assessment | HTTP errors / attempts | Ordinary p95 | Formative feedback p95 |
| --- | --- | --- | --- | --- |
| Five-user launcher validation | 5 / 5 | 0 / 169 | 3.072 s | 5.636 s |
| Initial 50-user campaign, `d223c975` | 4 / 50 | 36 / 329 (10.94%) | at least 30.021 s; censored | 33.945 s, only four observations |
| After pool correction, `408908e` | 0 / 50 | 50 / 99 (50.51%) | at least 30.038 s; all 49 observations censored | no observations |

The five-user validation had no warm-up and used the launcher before its commit;
its manifest correctly records a dirty source tree. It is launcher validation,
not a 50-user baseline or scaling result. Each 50-user campaign had one warm-up
and one measurement round, using 100 fresh learners in total. The second also
records a dirty source tree: removing temporary diagnostic middleware had left
one launcher blank-line change. The middleware itself was absent. Preserve those
flags and source digests when comparing results.

The initial measured 50-user outcomes were four `awaiting_human`, 29
`phase_deadline`, seven `request_timeout` and ten `simulation_timed_out`. The
second measured outcomes were 39 `phase_deadline` and 11 `request_timeout`.
Because these reports precede the timeout-label fix, the phase labels do not
prove the 600 s phase deadline expired. All failed journeys remain failures.

All three runs drained their feedback workflows, stopped their owned processes
and verified that their listeners closed. Their stopped databases contain zero
provider-usage rows and zero assessment decisions. Actual external cost and cost
per complete loop remain null; locally generated zero estimates are not external
billing evidence. No human assessor action was automated.

## Populated-dashboard diagnosis

An empty-profile mounted test completed 50 concurrent login/dashboard sequences.
A copied populated synthetic database then reproduced the failure without a
worker, feedback or simulations: 48 of 50 logins succeeded, but all 48 dashboards
timed out at the diagnostic 12 s bound. Private stack traces showed repeated
task and curriculum queries. Profiling established the redundant whole-class
aggregate and repeated pathway checks described above.

After the dashboard correction, the same copied database with the original 30 s
request bound completed 50 of 50 logins and 50 of 50 dashboards. Maximum observed
times were 8.140 s and 5.875 s respectively. This isolated diagnostic is not a
complete learning-loop capacity result and does not satisfy the ordinary-request
2 s target. Temporary stack instrumentation was removed from the application;
diagnostic scripts and logs remain private scratch artifacts.

After `54f34af`, another isolated populated probe completed all 50 logins and all
50 dashboards. Dashboard p95 was 2.875 s (maximum 3.157 s); login p95 was 4.640 s
(maximum 4.968 s). The ordinary target is still not met. Both isolated probe
distributions and source/result hashes are in the JSON receipt; they are separate
from full-campaign outcomes. The diagnostic measured each implementation before
its commit, and the named commits contain those changes.

## Next integrated measurement

The coordinator requested that the next full campaign wait for the combined
main branch, including the final feedback-category review migration. The earlier
failed receipts must remain visible beside that result. Run from `src-main/backend`
using the existing supported Python environment and imports pinned to this checkout:

```powershell
python -m scripts.task38_benchmark.local --directory ../../.tmp-task38/local-50-integrated --users 50 --warmup-rounds 1 --measurement-rounds 1 --ack-synthetic-only
```

The directory must be new. Keep private rosters, database snapshots and logs in
ignored scratch storage. The public receipt contains bounded metadata and hashes,
not learner credentials or machine/account paths.

External cost evidence still requires an approved provider/model/endpoint,
attributable prices and token bounds, records for budget, currency and policy, billing
receipts and any required FX evidence. A human-confirmed denominator requires
real assessor confirmation. Hosted and real-participant campaigns require their
own approved environment and study records. None of those approvals is invented
by the unpaid launcher.

## Integrated 50-user measurement on clean `f8b7d13`

The integrated campaign started at `2026-09-11T12:47:55.820785+10:00`
on `f8b7d13a854550b3b1044e516f5f63b69c6ba794`, branch `main`, with
`dirty: false`. It used the same bounded synthetic local runtime described above,
one warm-up round and one measurement round: 100 planned journeys, peak measured
concurrency 50, and 2,845 HTTP attempts across both phases. Earlier failed runs
remain in this document and the JSON receipt.

The measured round reached `awaiting_human` in **42 of 50 learning journeys**;
eight ended in `request_timeout`. No human-confirmed loop completed. Measured
HTTP errors were 8 / 1,414 (0.566%), below the exclusive 1% HTTP threshold;
the journey error rate was 16%. These are different denominators.

| Metric | Observations | Measured p95 | Errors / censored | Target |
| --- | --- | --- | --- | --- |
| Ordinary requests | 322 | 15.866519 s | 2 / 2 | 2 s; not established with censored observations |
| Progress requests | 90 | 10.770247 s | 0 / 0 | 3 s; not met |
| Formative feedback | 42 | 39.725035 s | 0 / 0 | 10 s; not met |
| Assessed feedback | 84 | 47.404997 s | 0 / 0 | No threshold defined by this report |

Measurement wall time was 300.155064 s; warm-up wall time was 296.710905 s.
The stopped database retained 258 submissions, 172 assessment attempts, zero
assessment decisions, 258 workflows, 258 learner-model snapshots and zero durable
provider-usage rows. The usage export contains 516 local metadata records:
258 feedback-generation and 258 feedback-judge records (344 `local`, 172
`local-deterministic`). Those records are excluded from external billing evidence.
External provider execution was disabled; recorded external provider/model
observations are empty. Actual external AUD subtotal and cost per complete loop
are null, with cost status `unknown_or_incomplete` and no complete-loop denominator.

The campaign drained all feedback workflows, stopped its owned processes and
verified the listener closed. Billing coverage remains incomplete, with no
reconciliation record. This run establishes neither production compliance nor
external-provider cost/performance, and it performs no human assessment.

Raw artifacts remain in ignored scratch storage. Their sanitized raw counts,
source clean flag, runtime bounds, warm-up outcomes and exact metrics are retained
in the JSON receipt, together with these SHA-256 hashes:

- Report: `83f3517cf950aa5b9ea82f772cbc0980732fe49c3f084099e219e780fb93b227`
- Usage export: `4154990f0c3b7bf7e59bae22233947b597d52c07e38e6ddb9bbafabedd5d9976`
- Stopped database snapshot: `cacdabd32fef7b37a9f72ed1111bafb36c51dbb45e1da428171ae825705a461c`
- Harness: `951d3cd08c5c9d62faf1e16e9525a13673a4fd67c69e33eebf162a4c9567eb75`

## Integrated 50-user measurement on clean `5a57b66`

**This campaign failed overall: 84% of measured journeys ended in errors.**
Only 8 / 50 reached `awaiting_human`; 40 ended in `simulation_timed_out` and
two in `request_timeout`. No human-confirmed loop completed. Measured HTTP errors
were 2 / 998 (0.2004%), which excludes the simulation outcomes returned without
an HTTP error and must not be substituted for the journey error rate.

| Metric | Observations | Measured p95 | Errors / censored | Target |
| --- | --- | --- | --- | --- |
| Ordinary requests | 224 | 7.803099 s | 0 / 0 | 2 s; not met |
| Progress requests | 58 | 1.332045 s | 0 / 0 | 3 s; met for observed requests |
| Formative feedback | 8 | 3.287347 s | 0 / 0 | 10 s; met for only eight observations |
| Assessed feedback | 16 | 15.128609 s | 0 / 0 | No threshold defined by this report |

The lower progress and feedback latencies are conditional on reaching those
stages. They do not establish a successful 50-user learning journey or erase the
simulation failures. Warm-up outcomes were 44 `simulation_timed_out`, one
`simulation_interrupted` and five `awaiting_human`.

The run started at `2026-09-11T03:30:21.088589+00:00` on
`5a57b666a1e7a50a249fcf6436f65b3dfd79f5c9`, branch `main`, with
`dirty: false`. It retained the same synthetic local runtime and bounds, with
one warm-up and one measurement round, 100 planned journeys and 1,720 total HTTP
attempts. Both phases reached 50 active loops. Warm-up took 88.268789 s and
measurement took 108.180683 s. All prior campaign records remain unchanged.

The stopped database retained 39 submissions, 26 assessment attempts, zero
assessment decisions, 39 workflows, 39 learner-model snapshots and zero durable
provider-usage rows. The export contains 78 local metadata records: 39 feedback
generation and 39 judge records (52 `local`, 26 `local-deterministic`). They are
excluded from external billing evidence. External provider execution was disabled;
actual external AUD subtotal and cost per complete loop remain null with
`unknown_or_incomplete` cost status, incomplete billing coverage and no human
completion denominator.

The report confirms all feedback workflows drained, owned processes stopped and
the listener closed. Exact counts, runtime bounds, source metadata and sanitized
usage aggregates are retained in the JSON receipt. Raw artifacts remain private
scratch evidence; SHA-256 hashes are:

- Report: `8882f229f642923eb1be1e44ed803196b42a2ad22e45d1b8861af72212fcbfe5`
- Usage export: `7e2d61ccdcd0c6b6c629095e21f7d2f155a20bcb9089834863ebdbd1cd7e1cf8`
- Stopped database snapshot: `a17e33854a6cda2a8444c1dc3150e615ce888582bfc002cef2ea5441887d3971`
- Harness: `951d3cd08c5c9d62faf1e16e9525a13673a4fd67c69e33eebf162a4c9567eb75`

## Integrated 50-user measurement on clean `7dddf9d`

**This campaign failed overall: 64% of measured journeys ended in errors.**
Of 50 measured journeys, 18 reached `awaiting_human`, 19 ended in
`continuation_timeout` and 13 in `request_timeout`. No human-confirmed loop
completed. HTTP errors were 18 / 4,558 (0.3949%); this separate denominator
does not establish successful journey completion.

| Metric | Observations | Measured p95 | Errors / censored | Target |
| --- | --- | --- | --- | --- |
| Ordinary requests | 275 | 8.023919 s | 0 / 0 | 2 s; not met |
| Progress requests | 68 | 1.375461 s | 0 / 0 | 3 s; met for observed requests |
| Formative feedback | 18 | 6.672365 s | 0 / 0 | 10 s; met for only 18 observations |
| Assessed feedback | 57 | 71.773195 s | 2 / 2 | No threshold defined by this report |

Progress and feedback observations are conditional on reaching those stages.
Warm-up outcomes were 19 `awaiting_human`, 10 `continuation_timeout`, 20
`request_timeout` and one `feedback_failed`. Neither phase reports a simulation
timeout as its journey outcome. Across both phases, the stopped snapshot has
165 simulation runs: 164 completed and one interrupted, with
`simulation_interrupted` recorded once and no run missing an outcome. These
snapshot counts are not a measurement-only denominator. This repeated-input
campaign does not establish capacity for diverse numerical inputs.

The run started at `2026-09-11T13:46:03.626809+10:00` on
`7dddf9deaa27e27a74f7457a5d9ac018d2294e20`, branch `main`, with
`dirty: false`. One warm-up and one measurement round planned 100 journeys and
made 8,867 HTTP attempts. Both phases reached 50 active loops. Warm-up took
310.320635 s; measurement took 292.732540 s. Runtime bounds and the local
synthetic environment are retained in the JSON receipt.

The stopped database retained 147 submissions, 110 assessment attempts, zero
assessment decisions, 147 workflows, 131 learner-model snapshots and zero durable
provider-usage rows. The usage export contains 282 local metadata records:
141 feedback-generation and 141 judge records (208 `local`, 74
`local-deterministic`). Those records are excluded from external billing evidence.
External execution was disabled; recorded external provider/model observations
are empty. Actual external AUD subtotal and cost per complete loop remain null,
with `unknown_or_incomplete` cost status, incomplete billing coverage, no
reconciliation record and no human-completion denominator.

The report confirms all feedback workflows drained, owned processes stopped and
the listener closed. It does not claim all continuation work completed. Earlier
campaigns remain unchanged. Raw artifacts stay in ignored scratch storage;
SHA-256 hashes are:

- Report: `12adf0e55143122254848ddd1ed291fc91dd40fff0afac7d6b36ddc40f2612a5`
- Usage export: `344595cbfc6a19f781aae6ba9e3e6cfd1dddb9f2d504c6b2bdfbfe3394c94e78`
- Stopped database snapshot: `75970d773729fd28d90ff626176a7e61c02143a465d8f5166688d90bba0f9d26`
- Harness: `951d3cd08c5c9d62faf1e16e9525a13673a4fd67c69e33eebf162a4c9567eb75`

## Integrated 50-user measurement on clean `dff979d`

**This campaign failed overall: 68% of measured journeys ended in errors.**
Of 50 measured journeys, 16 reached `awaiting_human`, 23 ended in
`continuation_timeout`, 10 in `request_timeout` and one in `feedback_failed`.
No human-confirmed loop completed. Measured HTTP errors were 25 / 5,336
(0.4685%); that separate denominator does not establish journey completion.

| Metric | Observations | Measured p95 | Errors / censored | Target |
| --- | --- | --- | --- | --- |
| Ordinary requests | 266 | 5.710440 s | 3 / 3 | 2 s; not established with censored observations |
| Progress requests | 63 | 1.422584 s | 0 / 0 | 3 s; met for observed requests |
| Formative feedback | 16 | 7.368817 s | 0 / 0 | 10 s; met for only 16 observations |
| Assessed feedback | 63 | 59.563637 s | 1 / 0 | No threshold defined by this report |

Progress and feedback timings are conditional on journeys reaching those stages.
Warm-up outcomes were 33 `awaiting_human`, 14 `request_timeout`, two
`continuation_timeout` and one `simulation_interrupted`. Across both phases,
the stopped database retained 166 simulation runs: 164 completed and two
interrupted, with no run missing an outcome. Repeated inputs do not establish
diverse-input numerical capacity.

The run started at `2026-09-11T06:12:31.023873+00:00` on
`dff979d0324e374229304a142233746644bbe59b`, branch `main`, with
`dirty: false`. One warm-up and one measurement round planned 100 journeys and
made 10,747 HTTP attempts. Both phases reached 50 active loops. Warm-up took
288.954540 s; measurement took 296.720672 s. Exact runtime bounds and the
synthetic local environment remain in the JSON receipt.

The stopped database retained 185 submissions, 136 assessment attempts, zero
assessment decisions, 185 workflows, 175 learner-model snapshots and zero durable
provider-usage rows. It also retained 185 continuation outboxes (175 completed,
10 pending), 175 continuation jobs (174 completed, one running), 175 progress
receipts and 174 activity suggestions. The report's feedback-drain success does
not mean continuation work completed.

The usage export contains 362 local metadata records: 181 feedback-generation
and 181 judge records (264 `local`, 98 `local-deterministic`). These are excluded
from external billing evidence. External execution was disabled; external
provider/model observations are empty. Actual external AUD subtotal and cost per
complete loop remain null, with `unknown_or_incomplete` cost status, incomplete
billing coverage, no reconciliation record and no human-completion denominator.

Owned processes stopped and the listener closed. Earlier campaigns remain
unchanged. Raw artifacts remain in ignored scratch storage; SHA-256 hashes are:

- Report: `7fc3e158e2ea39036ff3a66c1f8d1c254f436a81750e9fcaab3c4c8bf0f8717b`
- Usage export: `27c7c2d94c5aa559ba64d450740af466f03d4dd832cbe1d378cd1d16aac04325`
- Stopped database snapshot: `5b43d120b4eab8efc419145dd9b9ec5372d1d064620cbff0be4339e71c7c0b13`
- Harness: `951d3cd08c5c9d62faf1e16e9525a13673a4fd67c69e33eebf162a4c9567eb75`

## Integrated 50-user measurement on clean `ad187aa`

**This campaign failed overall: 44% of measured journeys ended in errors.**
Of 50 measured journeys, 28 reached `awaiting_human`, 15 ended in
`continuation_timeout` and seven in `request_timeout`. No human-confirmed loop
completed. Measured HTTP errors were 20 / 5,125 (0.3902%); this separate
denominator does not establish successful journey completion.

| Metric | Observations | Measured p95 | Errors / censored | Target |
| --- | --- | --- | --- | --- |
| Ordinary requests | 299 | 5.507467 s | 0 / 0 | 2 s; not met |
| Progress requests | 78 | 1.726871 s | 0 / 0 | 3 s; met for observed requests |
| Formative feedback | 28 | 18.099249 s | 0 / 0 | 10 s; not met |
| Assessed feedback | 71 | 48.336747 s | 0 / 0 | No threshold defined by this report |

Progress and feedback timings are conditional on reaching those stages; only
28 formative feedback observations were available. More journeys reached the
human handoff than in the preceding campaign, but ordinary-request and formative
feedback latency still exceeded their targets. Warm-up outcomes were 36
`awaiting_human` and 14 `request_timeout`.

The run started at `2026-09-11T06:37:24.366679+00:00` on
`ad187aa1b8be294d496bbc5ce05309fac2c7a841`, branch `main`, with
`dirty: false`. One 50-user warm-up and one 50-user measurement round planned
100 journeys and made 10,325 HTTP attempts. Both phases reached 50 active loops.
Warm-up took 269.237378 s; measurement took 258.557552 s. Exact runtime bounds
and synthetic local configuration are retained in the JSON receipt.

Across both phases, the stopped database retained 211 submissions, 147 assessment
attempts, zero assessment decisions, 211 workflows, 201 learner-model snapshots
and zero durable provider-usage rows. There were 177 simulation runs: 176 completed
and one interrupted, with no missing outcome. Repeated inputs do not establish
diverse-input numerical capacity. Continuation outboxes numbered 211 (202
completed, nine pending); 202 continuation jobs included 201 completed and one
pending. The database retained 201 progress receipts and 201 activity suggestions.

The usage export contains 418 local metadata records: 209 feedback-generation
and 209 judge records (290 `local`, 128 `local-deterministic`). They are excluded
from external billing evidence. External execution was disabled; recorded
external provider/model observations are empty. Actual external AUD subtotal
and cost per complete loop remain null, with `unknown_or_incomplete` cost status,
incomplete billing coverage, no reconciliation record and no human-completion
denominator.

The report confirms all feedback workflows drained, owned processes stopped and
the listener closed. Continuation work remained incomplete. All seven earlier
campaigns are preserved. Raw artifacts stay in ignored scratch storage;
SHA-256 hashes are:

- Report: `b2387de715f4ae65716d0b9fadbad977b93263bdeaafc18dba58b839825d317d`
- Usage export: `78e81b1d6072977880b8c911a412bd789d5dbd74171d3dd01dca15f544ce8eaf`
- Stopped database snapshot: `2760c8a3176a51dd322f03cef5cc9ba8525f4cf28b5ffb9d5c9fd3689ac67dd2`
- Harness: `951d3cd08c5c9d62faf1e16e9525a13673a4fd67c69e33eebf162a4c9567eb75`
