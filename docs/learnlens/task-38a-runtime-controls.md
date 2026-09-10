# Task 38A — runtime timeout and infrastructure retry controls

Implemented on `codex/task38-runtime-controls`, isolated from frozen commit
`0bbf95e25e4124f7484944c9493d1165d7b8023b`. The completed benchmark branches and
the coordinator's validation checkout are preserved.

## Administrator contract

`GET /api/v1/admin/settings` now returns two operational controls, and the existing
administrator-only `PUT` accepts partial updates:

| Setting | Accepted values | Missing-row default |
| --- | --- | --- |
| `provider_timeout_seconds` | Strict integer, 1–60 seconds | Deployment `PROVIDER_TIMEOUT_SECONDS`, normally 60 |
| `max_infrastructure_attempts` | Strict integer, 1–3 total attempts | Deployment `MAX_INFRASTRUCTURE_ATTEMPTS`, normally 3 |

Explicit null, booleans, numeric strings, fractional values and values outside the
bounds are rejected. Omitted keys preserve existing values. Updates reuse
`SystemSetting` and its administrator identity, timestamp and existing audit event.
Demo/bootstrap setup leaves these rows absent until an administrator sets them,
so it does not overwrite deployment defaults. No migration is needed.

The immutable `RuntimePolicy` in `app/services/runtime_policy.py` resolves scalar
database values, avoiding stale ORM identity-map objects. Invalid persisted values
stop new configured execution; they do not fall back to a more permissive value.
The settings read reports a controlled 503 so an administrator can repair them.

## Execution and restart semantics

The database override is read before a new provider workflow or persistent pass.
An already executing provider workflow retains its policy snapshot. A committed
administrator change applies to the next operation/pass without restarting the API
or durable worker. Changing environment defaults still requires the normal process
restart. Existing execution leases and fencing tokens remain the ownership authority.

| Execution path | Timeout propagation | Infrastructure retry meaning |
| --- | --- | --- |
| Feedback generation/judge | Same policy reaches HTTP timeout, outer async provider deadline, context collector and pipeline | One HTTP attempt per provider call; durable feedback claims enforce the total workflow-execution ceiling |
| Synchronous task generation | HTTP timeout and one outer wall-time budget including retry waits | Up to the configured total connection attempts, only for pre-dispatch connect errors/timeouts; no enclosing worker retry queue |
| Research baseline | Fresh provider timeout on each governed pass | Fresh total job-attempt ceiling; governance remains authoritative |
| Activity continuation | Fresh adapter timeout on each pass | Fresh total job-attempt ceiling |
| Assessment evaluation and terminal reconciliation | Deterministic operations retain their existing execution behavior | Fresh recovery-attempt ceiling on each pass |
| Material recovery | Existing extraction/processing controls | Fresh recovery-attempt ceiling on each pass |

Simulation recovery and reminder processing retain their existing independent
policies. The new controls do not limit learner submissions, help use or revisions.

Feedback transport retries are deliberately not stacked inside durable retries.
Synchronous task generation retries connection establishment only. HTTP responses,
ambiguous read/write failures and malformed model output are not replayed by the
transport. The timeout bounds the complete asynchronous request operation, including
connection retry waits, rather than allocating a new wall-time allowance per retry.

Lowering the feedback attempt ceiling finalizes exhausted stale claims and due
retries. It does not revoke an active lease. Raising the ceiling does not resurrect
terminal work. Existing logical workflow IDs and execution counters are retained.
The quality policy still permits exactly one regeneration after rejection, even
when the infrastructure ceiling is one; it is not a provider-call or monetary cap.

## Verification

**55 focused tests passed**:

- 34 new configuration/adapter/worker tests, final run: 16.14 seconds.
- 21 existing provider-client, feedback-application and database-worker tests.

The new checks exercise real administrator routes and audit persistence, strict
boundaries and corrupt rows, deployment fallback and fresh scalar reads, bounded
pre-dispatch retries, non-replay of ambiguous failures, and cancellation of a
transport that ignores HTTPX timeout metadata.

A persistent `DatabaseWorker` instance executes two actual feedback workflows with
synthetic recording transports. After the administrator-managed policy changes,
recorded generator/judge HTTP timeouts change from 11 to 4 seconds without rebuilding
the worker. Both accepted and rejected quality judgments are exercised: rejection
still produces exactly one regeneration when infrastructure attempts are reduced
from three to one. Separate cases prove bounded recovery on the same logical work,
no resurrection after exhaustion, active-lease preservation, and fresh policy
delivery into all five other configurable persistent passes.

All provider traffic in these checks uses synthetic recording/failing transports.
The early run's two failures were test fixtures missing a synthetic model name;
they selected the intended local fallback. Those fixtures were corrected before
the final passing run. No paid provider or load campaign was used.

Reproduce from `src-main/backend` with the existing project Python environment:

```powershell
python -m pytest tests/test_task38_runtime_controls.py -q -p no:cacheprovider --basetemp=.tmp-task38a-tests
python -m pytest tests/test_llm_client.py tests/test_database_worker.py tests/test_feedback_application.py -q -p no:cacheprovider --basetemp=.tmp-task38a-existing-tests
python -m scripts.export_openapi --output .tmp-task38a-contracts/openapi.json
python -m scripts.export_openapi --check --output .tmp-task38a-contracts/openapi.json
python -m scripts.generate_frontend_contracts --input .tmp-task38a-contracts/openapi.json --output .tmp-task38a-contracts/generated.ts
python -m scripts.generate_frontend_contracts --check --input .tmp-task38a-contracts/openapi.json --output .tmp-task38a-contracts/generated.ts
```

Ruff lint/format checks pass on the 11 changed Python files. Branch-local OpenAPI
and TypeScript generation/checks pass. Compared with the frozen canonical contract,
only `SettingsRead` and `SettingsUpdate` change; routes and other schemas are identical.
Generated scratch files are uncommitted. The coordinator owns canonical regeneration
and master-ledger reconciliation. This slice adds backend controls; administrator UI
fields and the benchmark's older settings probe need follow-up wiring.

## Coordination seam and limits

Task 38B can extend the runtime-policy/dispatch seam with durable budget reservations
and complete failed-call/currency metering after the Task 34A migration slot. This
slice supplies neither budget enforcement nor complete spend accounting. Connection
retry limits are not spend limits, and existing crash recovery does not establish
exactly-once external provider execution. No provider billing, currency, performance,
research-release or pilot-readiness claim follows from these synthetic tests.

No full suite, migration, dependency/runtime modification, merge or push is included.
