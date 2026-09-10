# Task 38 — load and cost harness delivery

## Outcome

Implemented the opt-in harness and synthetic fixtures, not the real campaign.
NFR7/NFR8/NFR22 compliance remains unestablished. The runnable commands,
configuration format, bounded budgets, human-review workflow and exact later
campaign instructions are in the [harness guide](../../src-main/backend/scripts/task38_benchmark/README.md).
The [smoke summary](task-38-smoke-summary.json) is explicitly synthetic.

## Requirements prepared

- **NFR7:** separate ordinary/progress/formative-feedback p95, HTTP errors,
  worker-inclusive feedback timing, timeout/cancelled lower bounds and a 50-VU
  report section. Backend progress API timing does not establish browser render
  latency. A separate LLM assessment-evaluation target remains pending.
- **NFR8:** configurable 5–100 VUs, bounded active loops, unique authenticated
  synthetic actors, sequential scenarios, warm-up/measurement barriers, phase
  deadlines, failure accounting and a 5-VU baseline/100-VU scaling comparison.
- **NFR22:** scoped read-only usage extraction, provider/model/prompt/rule/source
  references, separate recorded estimates, explicit billing and currency
  provenance, per-agent/feature totals and AUD per complete measured loop.
  Missing receipts/currency/coverage or zero complete loops leave actual cost
  unknown. Local template metadata cannot establish external provider cost.
- **Runtime settings:** administrator and learner probes use the existing
  cookie/CSRF `GET/PUT /admin/settings` interface. Provider/model are changed,
  read back and restored. Timeout/retry/budget are recorded as missing runtime
  interfaces. Unit tests validate this against the current `SettingsUpdate`
  contract; live authorization/effect remains for the coordinator.

## Real interface evidence and preserved behavior

The adapter follows `frontend/e2e/learning-loop.e2e.ts`,
`backend/tests/test_complete_learning_loop.py` and
`backend/tests/support/learning_loop.py`. It calls mounted authentication, LMS,
episode, simulation, feedback, activity-continuation, progress and learner-result
routes. Its outbound episode, simulation, submission and activity bodies are
checked against existing production schemas in unit tests. No internal E2E route
or direct database mutation is used by the load runner.

The current `AssessedFeedbackGenerator` and `AssessedFeedbackJudge` intentionally
return local templates. Their latency is retained as `assessed_feedback`.
The harness also submits the approved formative next activity, whose feedback
path can call the existing configured external client. Only that operation feeds
the `feedback` p95 series. Actual provider execution still needs usage evidence;
a configured model name or a passing readiness check is insufficient.

Supported conceptual hints, separate unaided transfer, immutable response and
revision links, uncertain model snapshots, and human result confirmation remain
intact. The runner never writes human criteria or confirms a result. Both human
PASS and INCOMPLETE finish the formal loop; pending results do not. The cost
denominator is the explicitly defined assessed-plus-formative-follow-on profile,
with all measured external spend (including failed loops) divided by complete
human-confirmed measured loops. Warm-up spend is separate.

## Data and ownership

All implementation changes are new Task 38 scripts, fixture, tests or docs:

- `src-main/backend/scripts/task38_benchmark/__init__.py`
- `src-main/backend/scripts/task38_benchmark/__main__.py`
- `src-main/backend/scripts/task38_benchmark/core.py`
- `src-main/backend/scripts/task38_benchmark/adapter.py`
- `src-main/backend/scripts/task38_benchmark/fake.py`
- `src-main/backend/scripts/task38_benchmark/usage.py`
- `src-main/backend/scripts/task38_benchmark/prepare.py`
- `src-main/backend/scripts/task38_benchmark/example-config.json`
- `src-main/backend/scripts/task38_benchmark/README.md`
- `src-main/backend/tests/test_task38_benchmark_harness.py`
- `src-main/backend/tests/test_task38_benchmark_usage.py`
- `src-main/backend/tests/fixtures/task38_benchmark/episode.json`
- `docs/learnlens/task-38-load-cost-harness.md`
- `docs/learnlens/task-38-smoke-summary.json`

No production services, schemas, migrations, generated contracts, package files,
locks, CI, shared configuration, Task 35 tooling, master checklist or historical
audit changed. Tests use in-memory transport and their own small SQLite metadata
fixtures. The optional preparer creates only a new absent-directory database and
uses existing migrations and fixture helpers; it was not executed. No server,
shared port or learner database was used. Rollback is removal of this optional
harness; no production data migration or history rollback is involved.

## Verification and exact commands

Working directory for checks:
`src-main/backend`.
The coordinator's existing Python environment was used read-only; no dependency
install or shared runtime change occurred. In the commands below `$task38Python`
is exactly:

```powershell
$task38Python = 'C:\Users\Jordan.Tran\Downloads\Honours Project\Monash-Honours-Project\src-main\backend\.venv\Scripts\python.exe'
```

| Check | Command and result |
| --- | --- |
| Focused unit checks | `& $task38Python -m pytest tests/test_task38_benchmark_harness.py tests/test_task38_benchmark_usage.py -q -p no:cacheprovider --basetemp=.tmp-task38-tests-final3` — **47 passed** |
| Scoped lint | `& $task38Python -m ruff check scripts/task38_benchmark tests/test_task38_benchmark_harness.py tests/test_task38_benchmark_usage.py` — **all checks passed** |
| Scoped format | `& $task38Python -m ruff format --check scripts/task38_benchmark tests/test_task38_benchmark_harness.py tests/test_task38_benchmark_usage.py` — **10 files already formatted**, including the supported Markdown formatting check |
| Tiny smoke | `& $task38Python -m scripts.task38_benchmark fake --run-id task38-smoke-v1 --output .tmp-task38/smoke-final.json` — **exit 0**, 132 fake HTTP calls, two warm-up and two measured loops, zero HTTP/loop errors, all four awaiting human confirmation |
| Patch integrity | `git diff --cached --check` — passed before commit |

The smoke's invented per-request latency is 0.05 s and formative feedback p95 is
2.15 s. These numbers test report math, not production latency. Actual external
cost is null. The checked-in summary preserves manifest, phase sizes/durations,
loop outcomes and aggregate metrics; full raw samples remain in the isolated
ignored `.tmp-task38/smoke-final.json`. Its manifest truthfully records the
starting commit plus a dirty working tree and the exact harness source digest.
Wall times and timestamps are not deterministic; fake transport latencies and
request sequence are deterministic. A prior tiny `.tmp-task38/smoke.json` had
the same outcomes before metadata-report refinements.

Initial failures and resolutions:

1. The first `git worktree add '.tmp-task38-worktree' -b codex/task38-load-cost-harness main`
   was denied while creating a Git ref lock. The identical authorized operation
   succeeded after the tool's permission review. No original changes were moved.
2. The initial focused pytest run used `--basetemp=.tmp-task38-tests`; 40 tests
   passed, three temporary-directory fixtures errored and cleanup hit Windows
   access denial. The identical test files passed **43/43** using approved
   process access and `.tmp-task38-tests-approved`. Later additions brought the
   final focused count to 47. No assertion, timeout, skip or coverage gate was
   relaxed. Subsequent temporary directories were unique.
3. Initial scoped lint passed; the first format check identified eight Python
   files. Scoped `ruff format` corrected them and the final check passed.
4. An initial documentation-summary export used an incorrect relative output
   path and returned FileNotFoundError; it wrote no file. The corrected absolute
   path generated only the Task 38 summary in this worktree.

## Coordinator dependencies and exact proposed follow-up

These are proposals outside this assignment; none was implemented here.

| Dependency | Current evidence | Coordinator follow-up |
| --- | --- | --- |
| Runtime timeout/retry/budget | `app/schemas/lms.py:SettingsUpdate/SettingsRead` expose provider/model but not these controls; `app/core/config.py:Settings` supplies timeout/retry via environment | If runtime mutation is required, add bounded typed settings fields, audited administrator writes in `LmsService.update_settings`, per-workflow configuration snapshots consumed consistently by API and worker, and an enforceable spend-reservation/cap service. Keep learner writes forbidden. Decide/approve exact semantics before implementation. |
| Provider endpoint/credential changes | Runtime provider name/model select through `runtime_model_selection`; transport endpoint and credential are environment settings | Confirm approved Responses-compatible provider composition and credential routing. A changed provider label alone does not prove a different provider was used. Verify new-workflow receipts after each approved change. |
| Full usage coverage | Learner feedback API omits usage; stored generation/judge records have tokens and estimates, but missing/unpersisted provider failures may be absent and currency provenance is not stored | Reconcile all attempts with provider billing, including cancelled jobs, regeneration and retries. If operational metering is required, add a privacy-scoped call-level receipt/usage interface with currency, pricing version and explicit missingness; do not repurpose research exports. |
| External budget enforcement | The client can bound requests/reserve declared per-loop exposure but cannot stop already accepted server jobs | Supply a reviewed conservative per-loop bound and enforceable provider/gateway cap, plus named operator approval. Record and drain outstanding server work after cancellation. |
| Real and browser measurements | This delivery executes only unit/fake transport code | After integration, run authenticated API/worker/fixture preparation smoke, then the approved 5–100 campaign and separate progress browser-render measurements on the final deployment. Retain errors and all failed/incomplete loops. |
| Human/expert approvals | D-05/D-07 selections are settled; exact course/source/staff/environment and validation records remain outstanding | Supply expert-reviewed source/task fixtures for the intended campaign, Tasks 35–37 evidence, D-12 provider/environment approval, named operators/assessors, approved budget, timestamped prices/FX and a separately approved assessment-evaluation target. |

## Limits and deferred checks

No live provider calls, paid usage, 5–100-user campaign, deployment, real server
integration, preparation/migration run, hosted performance claim or learning
effectiveness claim is made. Actual settings authorization/propagation and
provider costs remain unverified. No institutional, expert, ethics or release
approval was inferred from fixtures or user policy selections.

Combined backend/frontend/browser suites, service coverage, full-history secret
scan, dependency/security gates and full load campaigns are explicitly deferred
to the coordinator after integration, as instructed. The existing 80% coverage
gate and all application safeguards remain unchanged. This note is separate
from the master task list and does not mark Task 38's real evidence complete.
