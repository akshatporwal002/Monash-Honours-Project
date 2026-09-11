# Task 38 synthetic load and cost harness

This harness prepares operational evidence for NFR7, NFR8 and NFR22. It does not
approve a provider, environment, assessment evaluator or release. It supports
an explicitly unpaid loopback campaign as well as separately approved external
provider campaigns. The original fake smoke is historical orchestration evidence.

Run commands from `src-main/backend` with the coordinator's existing Python 3.11
environment. Only standard-library code and the already installed `httpx` are
used by the runner. Preparation additionally uses existing application/test
dependencies and unchanged Alembic migrations. No dependencies need changing.

## Profile and measurement boundaries

`LearningLoop` uses the mounted authenticated API under an explicitly supplied
prefix, such as `https://synthetic-host.example/api/v1`. It logs in separately for
every fresh synthetic learner, keeps that session's cookies, echoes the CSRF
cookie/header, sends the configured Origin, rejects redirects, and ignores proxy
environment variables. Duplicate normalized emails and duplicate authenticated
actors are rejected. Existing drafts or responses stop that learner's loop.

The profile follows the shipped complete-loop fixture: dashboard/task/progress,
assessment start, an approved conceptual hint, prediction checkpoint and H
simulation, separately entered unaided X-H-H transfer and simulation, draft save
and reload, submission, worker feedback, acknowledgement, model/next-activity
receipt, linked revision, second feedback and continuation, and accepted next
activity. No assessor action is automated; the result is observed through the
learner's permitted result endpoint. PASS and INCOMPLETE both count as a finished
human-confirmed result. Withheld/returned/void/pending results never become an
invented formal outcome. The first immutable response remains separate from its
revision. The single hint is a workload choice, not an instructional hint cap.

**The assessed generator and judge deliberately use local templates** in
`app/services/feedback/assessed.py`, regardless of the configured provider.
Consequently this profile also submits a formative explanation to the approved
next activity and waits for its feedback. That path reaches the existing
`ResponsesStructuredLlmClient` when credentials/provider/model are configured.
It does not enable AI assessment. The profile is named
`task38-single-qubit-v1-synthetic-only`; include the formative follow-on cost in
its denominator and do not compare it with differently defined loops.

| Report category | Boundary | Requirement comparison |
| --- | --- | --- |
| ordinary | Authenticated dashboard, task, draft and submission-list reads | p95 <= 2 s at 50 VUs |
| progress | Authenticated progress API response, including serialization/network | p95 <= 3 s at 50 VUs; browser render remains separate |
| feedback | Formative submission dispatch to terminal feedback receipt, including submission acceptance, queue/worker and polling wait | p95 <= 10 s at 50 VUs; prove actual provider execution from usage |
| assessed_feedback | Both locally generated assessed-feedback operations using the same end-to-end boundary | Descriptive only; no external-provider claim |
| simulation / continuation / human_confirmation | Separate operations, retained in raw samples | Assessment-evaluation target is pending approval; human wait is not ordinary-request latency |

All started HTTP requests, timeouts, fallback/failed workflows, cancelled
operations and failed loops remain in the report. A safe fallback is a degraded
loop, even though its HTTP request succeeded. Poll requests, authentication and
mutations are included in HTTP error accounting but not in ordinary latency.
The HTTP error denominator is attempted HTTP calls; loop error rate counts loop
statuses other than `complete` and `awaiting_human`, including human timeouts.
Both are reported, so successful polls cannot hide failed loops. The NFR error
limit is strictly below 1%, not <= 1%.

Percentiles use nearest rank (`ceil(0.95*n)`). Elapsed timeout/cancellation samples
are right-censored lower bounds, not completed response times. An affected
category cannot report `within_threshold_observed=true`. Polling adds up to one
poll interval to an end-to-end observation; retain that interval in comparisons.
Threshold observations are never a production compliance declaration.

Scenarios accept 5–100 VUs; including 50 emits the 50-user report section.
Scenario sizes run sequentially. Each phase has at most its VU count in active
loops, and each VU performs the configured number of rounds with fresh learners.
The warm-up phase fully drains before measurement starts. These are closed-loop,
round-bounded periods with a wall-time deadline, not constant-arrival-rate tests.
Reports retain phase duration, peak active loops, configured sizes, unstarted
loops, and every warm-up record separately. No think time is inserted. Slow
operations lower offered throughput; this must be considered when interpreting
scaling. The baseline is 5 VUs; growth above it is compared with <= 25%, and the
comparison remains pending until both 5 and 100 are present. A two-user fake run
cannot establish scaling.

## Tiny fake smoke (safe now)

```powershell
python -m scripts.task38_benchmark fake --run-id task38-smoke-v1 --output .tmp-task38/smoke.json
```

The deterministic `httpx.MockTransport` never opens a socket. Its 50 ms per-call
clock and two-poll feedback delay are invented. The CLI limits fake runs to two
VUs, one warm-up round and one measurement round. Smoke outcomes remain
`awaiting_human`; actual external cost is null. A new output path is required for
each invocation. The checked-in Task 38 smoke summary records the original
delivery. The current adapter adds formative draft save/readback calls, so a new
smoke has additional requests; wall timestamps/durations and source digest also vary.

## Unpaid local capacity measurement

```powershell
python -m scripts.task38_benchmark.local --directory ../../.tmp-task38/local-50 --users 50 --warmup-rounds 1 --measurement-rounds 1 --ack-synthetic-only
```

This launcher requires a new directory, prepares fresh synthetic learners, and
owns one loopback API and one durable worker against its new database. It pins
subprocess imports to the current checkout, clears the provider key, selects
local templates and an unreachable loopback provider endpoint, disables research,
and retains CSRF, rate limits, simulation limits and production worker behavior.
Source scanning uses the explicit test-only scanner scope for the disposable
fixture processes; this is not a scanner effectiveness result. Additional learner
identities satisfy the mounted login schema. No emails are sent.

Local mode has bounded requests, users, rounds and timeouts. Monetary amounts and
provider budget approvals stay absent. It records `SYNTHETIC LOCAL CAPACITY`, not
provider performance or hosted capacity. A 50-user run needs 100 fresh learners
with the illustrated warmup/measurement settings. All errors and pending human
results remain visible. The launcher waits for bounded feedback drain, stops only
its owned processes, checks the listener closed, and snapshots the stopped
database. Windows TIME_WAIT does not mean the server remains running.

Private credentials/database/logs remain in the requested scratch directory.
`report.json` contains measured phase/HTTP/operation data and `usage.json` contains
scoped metadata. No answer text or credentials enter these reports. Local records
cannot establish a zero-cost external provider or a human-confirmed cost denominator.
Do not pass `local_only` to the external `run` command; only this owned launcher
can select it. Historical/synthetic fixtures do not replace institutional approvals
required for hosted, real-participant or external-provider campaigns.

## Later campaign preparation (coordinator only)

1. Record the integrated commit, successful Tasks 35–37 checks, synthetic host
   approval, provider/model permission, workload approval, named operator and
   human assessors. Do not activate research to run this operational benchmark.
2. Prepare a new directory/database; never point the preparer or runner at an
   existing learner environment. The example scenario sizes total 190 VUs;
   with one warm-up and ten measurement rounds they require 2,090 distinct
   synthetic learners in a shared synthetic course. This is a repeatable profile,
   not evidence of expert approval of its teaching content.

```powershell
python -m scripts.task38_benchmark.prepare --directory .tmp-task38/campaign-A --learners 2090 --ack-synthetic-only
```

The preparer refuses an existing directory, migrates only its new database,
reuses `tests/support/learning_loop.py` to prepare synthetic teaching approvals,
and enrolls unique synthetic learners. It creates no learner responses, feedback
or formal decisions. `roster.json` and `fixture-private.json` contain private test
credentials: retain them in the restricted scratch directory. Do not commit or
attach them to reports. The fixture's educator has the existing scoped assessor
setup. Provision a separate synthetic administrator through the supported setup
if needed; do not reuse institutional learner/admin credentials.

3. The coordinator starts the real API and one durable worker against that exact
   new database and its separate uploads directory, using the existing
   [worker operations](../../../docs/worker-operations.md) and
   [deployment guide](../../../docs/deployment.md). Reserve a distinct API
   port (for example 18338 after checking it is free); this harness starts no
   servers. Set provider secrets via the approved environment/secret mechanism,
   never the harness config. Inspect `/api/v1/ready`; retain readiness and actual
   sanitized runtime settings before proceeding. Keep rate limits and CSRF on.
   Readiness alone does not prove model execution: absent credentials can select
   local feedback, and the assessed path always remains local.
4. Copy `example-config.json` into the restricted scratch directory. Fill the
   target/API prefix, browser Origin, provider/model, actual runtime metadata and
   exact source/prompt/rule/model/deployment/fixture versions. Empty approval,
   version or budget values must be resolved before real execution. The runtime
   snapshot is **operator-declared**, not a measured admin read. Task 38A exposes
   timeout/retry controls through administrator settings; retain the separate
   settings-probe receipt and actual execution evidence. Config contains no API key, passwords
   or connection strings. The roster is read separately and only its digest is
   saved in the report.
5. Set a finite integer `max_requests`, positive decimal `max_cost_aud`, and a
   positive `loop_cost_ceiling_aud` covering **all** provider calls, judge calls,
   regeneration, retries, follow-on jobs and in-flight work for a loop. This
   ceiling is a conservative exposure bound, not an estimate or the AUD 0.10
   acceptance threshold. Record its derivation and an independently enforced
   provider/gateway spend cap in `provider_budget_record` and
   `runtime.provider_budget_enforcement`. The production adapter now implements
   durable server reservations; configure its approved allocation, currency,
   provider/model/endpoint-bound prices and policy version as described in
   [durable metering](../../../../docs/learnlens/task-38-durable-metering.md).
   Monetary settings are deployment configuration, not mutable harness assertions.
   Without matching approval/enforcement the external campaign remains blocked.

Reservations are taken atomically before dispatch and never refunded. Dispatch
stops at the request budget or reserved cost ceiling; later loops are recorded
as budget-limited. Client cancellation/deadlines stop new work but cannot cancel
already accepted server jobs or prevent their provider charges. Retain the full
reservation and let the coordinator drain/inspect the worker after stopping.
Server-side enforcement is essential because the load client alone cannot enforce spend.
There is no client-side retry of submissions or failed feedback; normal server
retry policy remains active and its costs must be reconciled.

## Runtime setting authority checks (later)

Create private `settings-credentials.json`:

```json
{
  "admin": {"email": "SYNTHETIC ADMIN EMAIL", "password": "PRIVATE PASSWORD"},
  "learner": {"email": "SYNTHETIC LEARNER EMAIL", "password": "PRIVATE PASSWORD"},
  "desired": {
    "llm_provider": "APPROVED DIFFERENT PROVIDER",
    "llm_model": "APPROVED DIFFERENT MODEL",
    "provider_timeout_seconds": 15,
    "max_infrastructure_attempts": 2
  }
}
```

```powershell
python -m scripts.task38_benchmark settings --config .tmp-task38/config.json --credentials .tmp-task38/settings-credentials.json --ack-synthetic-target --ack-provider-budget --output .tmp-task38/settings-result.json
```

Run this while no load is active and no other operator edits settings. The probe
requires all four new values to differ from originals. Timeout must be an integer
from 1 to 60 seconds; infrastructure attempts must be an integer from 1 to 3,
including the first attempt. Configure at least **32 requests** for this command.
The probe expects learner PUTs to be 403, checks unchanged values after denial,
rejects out-of-range administrator writes with 422, applies each valid value as
administrator, and reads it back. It restores all four original values in
`finally` and verifies restoration. Two requests are reserved for restoration;
a failed restoration requires operator action before any campaign. Blank or
otherwise unrestorable original values stop the probe before mutation. Provider
and model identifiers must be nonblank and have no surrounding whitespace.
Budget is configured through the server deployment and is never sent by this settings probe.
CRUD/readback does not prove provider execution or enforcement: timeout/retry
effect remains pending an instrumented execution receipt, and provider/model
effect remains pending later workflow usage. For each approved configuration
variant, the operator sets the values through the existing admin settings UI,
records its audit event, then runs with a fresh roster and matching config.

## Later campaign and cost commands

```powershell
python -m scripts.task38_benchmark run --config .tmp-task38/config.json --roster .tmp-task38/campaign-A/roster.json --ack-synthetic-target --ack-provider-budget --output .tmp-task38/campaign-A-report.json
```

For a standalone 50-user run set `users` to `[50]` and prepare
`50 * (warmup_rounds + measurement_rounds)` fresh learners. Preserve raw reports
for every provider/configuration variant. Ctrl+C returns a partial run report;
any failed/budget-limited/cancelled loop gives a nonzero exit. `awaiting_human`
can give exit zero for a technically complete observation, but does **not** count
as a complete formal loop or a successful cost gate.

For complete formal-loop costs, set an approved positive `human_timeout` and a
suitable `phase_timeout`, schedule authorized human reviewers, and have them
review/confirm the revised assessed response through `/assessor/review` while
the runner observes the learner result endpoint. Human wait is separately
recorded and never included in the 10-second feedback target. There is no
automatic MET/confirmation shortcut. If reviewers cannot complete within the
window, retain the pending run and schedule a fresh adequately staffed run.

After the server jobs drain, obtain a consistent backup/snapshot of **only this
synthetic database** using the existing approved backup procedure. Never copy a
live SQLite file or run the extractor against existing learner data.

```powershell
python -m scripts.task38_benchmark extract-usage --report .tmp-task38/campaign-A-report.json --snapshot .tmp-task38/synthetic-snapshot.sqlite --ack-synthetic-snapshot --output .tmp-task38/usage-unreconciled.json
python -m scripts.task38_benchmark report --report .tmp-task38/campaign-A-report.json --usage .tmp-task38/usage-reconciled.json --output .tmp-task38/campaign-A-cost-report.json
```

The extractor opens an existing snapshot read-only and selects only metadata
for the report's submission IDs from `feedback_records`, `judge_evaluations`, and
the durable `provider_usage` ledger when present. Ambiguous dispatches and failed
attempts survive even if feedback was never persisted. Available token counts,
estimates, original reservations, held exposure, currency, pricing/policy versions,
nullable actuals and receipt references remain separate. For metered submissions,
external generation metadata is retained under `legacy_generation_metadata` and
the durable attempts supply financial rows, preventing duplicate spend. Legacy
and otherwise unattributed calls still need explicit coverage reconciliation.
It includes all persisted generations/judges, including rejected generations,
provider/model/prompt, source references, judge rule, tokens, usage completeness
and recorded estimated cost. It never reads answer/feedback/source text or
research exports. Database cost estimates have no recorded currency provenance;
the extractor therefore never labels them as actual AUD cost. Durable estimates
also remain estimates. Known billed subtotals survive missing token counts, while
incomplete usage still prevents a complete cost gate. The report rejects reuse
of one billing receipt across two rows and mismatched pricing versions. `NOT_SENT`
and `RELEASED` records are retained but excluded from billed spend without fabricating
a zero-value invoice. Reconciliation can never turn a local-only campaign into
approved external-cost evidence.

An operator reconciles missing/in-flight/failed provider attempts and any other
agents against provider billing, retaining unique receipt IDs and loop IDs. Add
`billing_receipt`, `billed_cost`, `billing_currency`, `agent` and `feature` to each
external record. Preserve the original `recorded_estimated_cost`; do not replace
it with the bill. Add `pricing["provider/model"]` with the official price source,
date, currency, schedule version and all applicable rates (including caching or
other billing dimensions), and `fx` with currency, positive `aud_per_unit`,
source and date. AUD billing still needs an explicit rate of 1 and provenance.
Price schedules explain charges; the AUD calculation uses the recorded billed
amount, not an invented token price.

Only after accounting for every loop and every external call may the operator
set `coverage.complete=true`, list every `covered_loop_ids` entry, and supply
`coverage.reconciliation_record`. This is an externally reviewable attestation;
the harness does not authenticate invoices. Local template rows remain visible
but are excluded from external evidence, and all-local/missing-billing runs keep
cost unknown. Fake reports cannot become real evidence by attaching a ledger.

Per-scenario AUD cost is **all measured-loop external spend, including failed
and pending loops, divided by human-confirmed complete measured loops**. Warm-up
spend is reported separately. Zero complete loops means a null average, not zero.
Agent/feature/provider/model totals and the input ledger are retained. Campaign
setup/content-generation costs are outside this pre-provisioned learner profile;
record them separately, without silently amortizing them into its denominator.

## Checks and integration verification

```powershell
python -m pytest tests/test_task38_benchmark_harness.py tests/test_task38_benchmark_usage.py tests/test_task38_settings_probe.py -q -p no:cacheprovider --basetemp=.tmp-task38-tests
python -m ruff check scripts/task38_benchmark tests/test_task38_benchmark_harness.py tests/test_task38_benchmark_usage.py
python -m ruff format --check scripts/task38_benchmark tests/test_task38_benchmark_harness.py tests/test_task38_benchmark_usage.py
```

These unit tests cover the adapter against deterministic HTTP transport,
production request schemas, scheduling bounds, cancellation, failure accounting,
hand-calculated percentiles/currency/denominators and a metadata-only synthetic
SQLite snapshot. The additional bounded integration regression invokes the actual
preparer and runs one fresh synthetic learner against a loopback API on port
4690 and a separate durable worker, using local providers with empty API credentials.
It saves a typed explanation draft, reads it back and submits the formative episode.
Test-only observation of actual local generator/judge inputs verifies that the typed
explanation reaches both; no duplicate legacy answer can conceal missing episode data.
An unexpected next-task type, assessment or episode plan stops the profile.

```powershell
python -m pytest tests/test_task38_benchmark_integration.py -q -p no:cacheprovider --basetemp=.tmp-task38-integration-check
```

Reserve port 4690 before running; the regression refuses an occupied port and
terminates only the processes it starts, with bounded kill/wait fallback. It writes
private fixtures, provider-input observations and logs beneath
pytest's isolated temporary directory. See the separate
[integration verification note](../../../../docs/learnlens/task-38-integration-verification.md)
for prerequisites, observed failures and results. This is adapter compatibility
evidence, not a load campaign, provider cost measurement or approval record.
Full suites, external provider verification and 5–100-user campaigns remain separate;
existing service coverage gates stay intact.
Provider compatibility, rates and currency should be checked against official
sources at campaign time; this delivery supplies no purported current prices.
