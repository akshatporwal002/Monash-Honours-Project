# Task 38A — runtime timeout and infrastructure retry controls

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

Ruff lint/format checks pass on the 11 changed Python files. OpenAPI
and TypeScript generation/checks pass. Within the Task 38A delta, only
`SettingsRead` and `SettingsUpdate` change; routes and other schemas are identical.
Canonical OpenAPI and frontend TypeScript contracts include the settings changes.

## Retry-transition correction

Independent review found that three queues could strand scheduled retries after
lowering the limit, and assessment failure handling retained a constant ceiling.
Separate corrective commit `bb503dbd3122828468506c501cf74ad2e0b40739` fixes these
transitions. The [correction receipt](task-38a-retry-exhaustion-correction.md)
records four reproduced failures, seven passing new regressions, and 46 passing
related queue/fencing checks. One migration/backup subprocess case was excluded.

## Administrator UI and settings-probe follow-up

The existing administrator settings screen now exposes both bounded integer fields
with associated labels, help, native limits and accessible error descriptions.
It displays fetched values, locks controls during a save, preserves edits after a
failed save, and accepts the server's returned values on success. Partial updates
send only edited settings, preserving an unset model or an unfamiliar fetched
provider when changing operational limits. Missing or invalid runtime values fail
visibly instead of inventing defaults. Budget and billing controls remain absent.

The settings probe checks provider, model, timeout and attempt count: learner
denials, administrator boundary rejection, valid updates/readback, and restoration
of all four original settings on success or failure. It requires a minimum of 32
requests and reserves two for restoration. Unrestorable originals (including a
blank model rejected by PUT) stop before any mutation. Budget remains explicitly
unsupported. A CRUD receipt still marks actual execution effects as pending;
the earlier instrumented runtime tests are separate evidence.

Canonical `src-main/contracts/openapi.json` and frontend `src/api/generated.ts`
are regenerated together. Frontend settings types now derive
from that contract. Within the Task 38A delta, only `SettingsRead` and
`SettingsUpdate` change; the combined contract also includes Task 34A instruments.

Follow-up checks:

- **42 harness/probe tests passed**, 0.72 seconds, covering authority, strict inputs,
  bounds, restoration after response failure/request exhaustion, and preflight guards.
- **11 admin component tests passed**, 9.88 seconds total Vitest duration. Existing
  `src/test/App.test.tsx` also passed **21 tests** after updating its settings fixture.
- TypeScript build checking, targeted ESLint, Ruff and both canonical contract checks pass.
- Vite production build passes (2,319 modules); its existing large-bundle warning remains.
- No browser server or manual browser session was started. Component tests exercise
  labels, descriptions, invalid input, pending controls and failed-save recovery.

Commands, run in `src-main/backend` or `src-main/frontend` respectively:

```powershell
python -m pytest tests/test_task38_benchmark_harness.py tests/test_task38_settings_probe.py -q --tb=short -p no:cacheprovider --basetemp=.tmp-task38a-ui-harness-final
python -m ruff check scripts/task38_benchmark tests/test_task38_settings_probe.py tests/test_task38_benchmark_harness.py
python -m scripts.export_openapi --check
python -m scripts.generate_frontend_contracts --check

node node_modules/vitest/vitest.mjs run src/components/AdminWorkspace.test.tsx
node node_modules/vitest/vitest.mjs run src/components/AdminWorkspace.test.tsx src/test/App.test.tsx
node node_modules/typescript/bin/tsc -b
node node_modules/eslint/bin/eslint.js src/components/AdminWorkspace.tsx src/components/AdminWorkspace.test.tsx src/app/api.ts src/app/types.ts src/test/App.test.tsx
node node_modules/vite/bin/vite.js build
```

The first combined component run passed App's 21 tests but found a missing brace in
the new test helper; after that syntax fix, one assertion needed to include the
existing reminder checkbox's help text in its accessible name. The final isolated
component run passed all 11 tests. Initial harness assertions treating timeout/retry
as unsupported were updated for the new contract. No assertions or gates were removed.

Checks used Python 3.11.16, Node 22.13.0 and the unchanged dependency lockfiles.

## Budget and billing limitations

Task 38B can extend the runtime-policy/dispatch seam with durable budget reservations
and complete failed-call/currency metering in a subsequent migration. This
slice supplies neither budget enforcement nor complete spend accounting. Connection
retry limits are not spend limits, and existing crash recovery does not establish
exactly-once external provider execution. No provider billing, currency, performance,
research-release or pilot-readiness claim follows from these synthetic tests.

Current combined validation is recorded in [integration verification](next-wave-integration-verification-2026-09-10.md).
