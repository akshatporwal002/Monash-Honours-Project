# Task 10: recover material processing

Status: implemented and locally verified on 7 September 2026; ready for local integration.

Branch: `feat/task-10-material-processing-recovery`.
Base: Task 9 merge `3f0ce614855957a5e28003a6664c48d6494e9013`.

## Recovery behaviour

The material row now stores its execution token, lease expiry, attempt count, retry date, and processing backend.
Both offline and semantic processors acquire the same durable claim before reading the saved upload.
Claims compare the stored material version, content hash, storage key, state, attempt count, and prior token.
Concurrent requests therefore cannot both own the same processing run.

Publication checks the claim and takes the database writer lock before replacing current chunks.
The transaction saves complete source history, then checks the live claim again before committing.
A late executor cannot replace a recovered revision or mark a newer run as failed.
Original uploads and previously published source revisions remain preserved.

The database worker now scans material work alongside its existing queues.
It processes pending uploads, due failures, and expired claims without requiring another API request.
It also handles legacy saved uploads whose processing metadata predates this migration.
The third interrupted claim becomes a visible terminal failure instead of being claimed a fourth time.
Non-retryable document errors stop immediately. Other processing errors use the bounded retry schedule.

The default worker supports offline extraction through the shipped adapter.
Semantic recovery uses the optional `WorkerAdapters.material_processor_factory(session, backend)` extension.
If that adapter is absent or cannot start, the worker records a bounded configuration failure.
It does not claim that an offline extraction is a recovered semantic index.

## Educator controls

Material reads expose safe error text, attempt count, retry time, and lease expiry.
Execution tokens stay internal.
The course editor shows processing errors and scheduled retries, and provides a status refresh action.
Once automatic processing stops, an educator can request a fresh processing run.

`POST /api/v1/courses/{course_id}/materials/{material_id}/process?force=true`
starts that fresh run, provided no live claim owns the material.
Course management checks still apply.
Replacement resets the processing fields. Retirement prevents further publication and clears retry scheduling.

## Settings and deployment

| Setting | Default | Purpose |
| --- | --- | --- |
| `MATERIAL_PROCESSING_LEASE_SECONDS` | 300 | Maximum lease held by one execution |
| `MATERIAL_PROCESSING_RETRY_SECONDS` | 5 | Delay before a retryable failure is due |
| `MAX_INFRASTRUCTURE_ATTEMPTS` | 3 | Automatic attempts per processing revision |

Apply migration `20260907_0024` before starting the API and worker.
It follows `20260907_0023`; the readiness pin now expects the new head.
The migration adds columns and an indexed recovery scan without rebuilding the protected material table.
It supports repeat execution and refuses unsafe populated downgrades before changing the schema.

The API and worker must share the same database, upload directory, and processing configuration.
Back up the database and uploads together.
The deployment still uses one worker ownership slot; no extra server or queue service was added.

## Verification

Targeted tests cover competing claimants, process exit after claim persistence, worker restart recovery,
late semantic results, lease expiry during publication, due retries, retry exhaustion, legacy uploads,
missing adapters, safe API status, explicit retry, and course scope.
The frontend test covers scheduled recovery, status refresh, and a successful explicit retry.

| Check | Result |
| --- | --- |
| Full backend suite on the final code | 754 passed; 85.69% service statement coverage |
| Recovery tests included in that suite | 13 passed |
| Fresh migration and Alembic schema comparison | No new upgrade operations detected |
| Backend lint and format | Passed; 320 files already formatted |
| OpenAPI and generated TypeScript drift checks | Passed |
| Frontend unit and accessibility suite, two workers | 179 passed across 52 files |
| Frontend lint and production build | Passed |
| Git whitespace check | Passed |

The final rerun includes UTC status timestamps and the manual-retry backend guard.
The earlier backend run passed 752 tests before those final checks were added.
The production build retains its existing warning about a JavaScript chunk exceeding 500 kB.
Local logs are saved under `src-main/backend/.tmp-task10/` as ignored validation artifacts.
These results record local engineering evidence; final independent and hosted release checks remain separate.

## Limits and next task

A claim lease prevents stale publication. It does not terminate a blocked native parser or embedding call.
The worker keeps its heartbeat while extraction runs in a thread.
If a process stops, the replacement worker can reclaim expired work from the saved upload.
Complete process termination, provider fault, and security drills remain part of Task 37.

The semantic vector index remains rebuildable cache state. SQLite controls accepted source revisions and citation history.
Source approval and publication policy remain Task 12.
Task 11 adds durable simulation evidence and execution limits.
No remote CI, live provider, hosted availability, or institutional approval is claimed by this task.
GitHub publication remains pending the requested push approval.
