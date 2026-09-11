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
attributable prices and token bounds, budget/currency/policy records, billing
receipts and any required FX evidence. A human-confirmed denominator requires
real assessor confirmation. Hosted and real-participant campaigns require their
own approved environment and study records. None of those approvals is invented
by the unpaid launcher.
