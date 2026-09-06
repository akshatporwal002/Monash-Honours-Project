# Worker operations

QuantumLearn's MVP uses SQLite and exactly one database-backed worker process. The worker acquires
the singleton durable heartbeat slot before scanning any queue; a second live process fails closed.
After the ownership timestamp becomes stale, one replacement process may take over. Apply migrations
before starting either the API or worker.

## Local Windows launcher

Run `./start-quantumlearn.ps1` from the repository root with Python 3.11, uv, and Node.js 22 installed.
The launcher prepares dependencies, validates backend settings, applies migrations, then starts the API, frontend, and durable worker.
It copies `.env.example` only when `.env` is missing. Review the backend file before choosing a database.
The local template selects the built-in offline adapters and disables research processing.
The API and worker inherit the same environment and use the same backend working directory.

Startup succeeds only after the frontend responds and the actual API readiness route passes every required check.
The default route is `http://127.0.0.1:8000/api/v1/ready`; a configured API prefix is respected.
Checks cover the database, migrations, worker heartbeat, pseudonym secret, production adapters, and model credentials.
`/health` alone does not establish worker readiness. A missing or stale heartbeat blocks startup success.

The default setup deadline is 600 seconds. The service readiness deadline is 90 seconds.
Use `-SetupTimeoutSeconds`, `-StartupTimeoutSeconds`, and `-NoBrowser` to change those launch options.
Ports 8000 and 5173 must be free. The launcher reports a conflict without stopping the existing listener.
Child startup failures and readiness timeouts produce a nonzero exit and stop the owned process tree.
Messages expose service roles, exit codes, and allowed readiness check names, without provider output or credentials.

Keep the launcher open while using the app. Press Ctrl+C to stop its services.
An explicit stop file also supports controlled shutdown:

```powershell
./start-quantumlearn.ps1 -NoBrowser -StopFile "$PWD/.scratch/my-session.stop"
# From another PowerShell session, create the exact file supplied above.
New-Item -ItemType File -Path "$PWD/.scratch/my-session.stop"
```

Choose a new, absent stop-file path for each run. A pre-existing stop file is rejected.
Windows Job Objects own the hidden helper processes and their descendants before execution begins.
Normal shutdown, startup failure, or supervisor termination closes that ownership boundary and stops those processes.
Unrelated processes are never selected by port, command name, or a saved PID for termination.
This local launcher does not provide a hosted service manager or automatic worker restart.

## Feedback jobs

An API request creates or reclaims a durable workflow claim. Claims use a UUID execution token,
300-second lease, persisted attempt count, next retry time, course/task scope, and monotonic
latency. All stage changes, lease renewals, terminal writes, and failure writes are fenced by
workflow UUID plus execution token. A stale executor must stop when a fenced update affects no row.

The worker scans for due failed workflows and expired nonterminal claims. It atomically assigns a
new execution token and attempt before invoking the same feedback executor, so a crashed API
background task is recoverable without another POST. The claim scan is indexed by stage, retry
time, lease expiry, and start time. Recovered executions receive the worker's independent
database-backed best-effort audit mapper automatically, including terminal exhausted-attempt
events.

Renew the lease around provider stages. Each provider call is bounded to 60 seconds. At most three
controlled infrastructure attempts are allowed; expired claims become reclaimable. Released
feedback remains durable and idempotent even if continuation or research dispatch later fails.

## Terminal integration outbox

Before the terminal workflow commit, the pipeline evaluates research eligibility with a bounded
metadata-only call and prepares privacy-safe research/continuation intents. Valid intents are
inserted into `terminal_integration_outbox` in the same transaction as released feedback. They
contain pseudonyms, opaque scope/reference IDs, correlation, and bounded research measurements,
but no answer, prompt, feedback, source chunk, or direct learner ID. Invalid optional adapter
output is omitted without rolling back feedback.

The worker processes this outbox immediately after feedback recovery. Claims have a UUID token,
300-second lease, and at most three attempts. If the target integration commits and the process
crashes before the outbox completion, the stale claim is replayed safely because research-pair and
continuation creation are idempotent by workflow UUID. The following baseline pass can only see a
pending baseline after the research pair is durable.

## Baseline jobs

Built-in production composition currently preserves research outbox rows and baseline jobs without claiming them.
Research exports remain restricted by the separate course grant and closed governance gate.
The global research flag cannot approve a study or consent. Task 33 owns governed activation.
The generic baseline mechanisms below remain available for isolated tests and future approved integration.

Baseline claims use the same token/lease fencing and reclaim expired `running` rows. A claim
performs exactly one same-model generation and one evaluation-only judge call, with no ordinary
provider retry. Failures store bounded categories rather than exceptions. Completion/failure
updates must match the claim token. Crash recovery is bounded to three claims; an expired third
claim is token/lease-fenced into a terminal sanitized failure instead of being claimed a fourth
time.

## Continuation jobs

Terminal feedback schedules one `continuation_jobs` row keyed by workflow UUID. Exact replays must
match the stored pseudonymous actor, course, completed task, and correlation references; conflicting
workflow-ID reuse is rejected. The worker records the team progress callback first, persists that
checkpoint, and only then asks the injected recommender for an opaque next-task reference.

Claims use a 300-second lease, UUID execution token, and a maximum of three processing attempts.
Pending work, due retries, and expired running claims are recoverable. Progress, retry, completion,
and failure writes also match the attempt number and execution token, so an expired worker cannot
overwrite its successor. A restart resumes from the durable progress checkpoint and does not repeat
the progress callback. Missing progress or recommender adapters fail closed, but released feedback
remains available.

## Worker heartbeat

The worker loop refreshes the singleton `worker_heartbeats` row with its bounded UUIDv4 owner and
UTC timestamp, including while every queue is idle and while provider calls are in flight.
Ownership renewal matches the current worker UUID; it cannot overwrite a fresh different owner.
Readiness checks that durable row from the API process. A missing, malformed, future-skewed, or
stale heartbeat is not ready. Heartbeat persistence errors are sanitized and never create job
output.

## Safe startup and shutdown

1. Load environment values from the deployment secret manager.
2. Run `uv run --frozen alembic upgrade head`.
3. Configure `WORKER_ADAPTER_FACTORY` as `package.module:create_worker_adapters`. The callable
   receives `Settings` and must return `app.worker.WorkerAdapters`; missing adapters fail closed.
   Local offline use selects `app.worker:build_offline_worker_adapters` with `RESEARCH_ENABLED=false`.
   External adapters remain trusted application code and require review before deployment.
4. Start `uv run --frozen quantumlearn-worker` and wait for its durable heartbeat.
5. Verify readiness: database connectivity, Alembic head, durable worker heartbeat, pseudonym
secret, and every required production adapter. Readiness must not invoke an LLM.
6. Accept API traffic.
7. On shutdown, stop claiming work, finish or abandon the active claim within the lease, and
   terminate. Do not clear tokens manually.

## Recovery

After a crash, restart the worker. The next scan reclaims only expired claims with a new token.
Never edit job status or delete evidence to force a retry. Investigate using correlation ID,
resource UUID, stage, latency, and sanitized failure category. Raw prompts, answers, provider
output, source chunks, identities, and credentials are prohibited in diagnostic logs.

For continuation work, inspect only state, attempt count, lease, retry time, and sanitized failure
category. Do not clear `progress_recorded`: it is the restart-safe idempotency checkpoint. Readiness
will remain unavailable until the restarted worker writes a fresh durable heartbeat.
Checking readiness for a missing SQLite path must not create an empty database file.

The recovery acceptance test uses a disposable migrated database and one accepted LMS submission.
It pauses a real worker after claim acquisition, rejects a duplicate worker, and kills the paused process.
After the real 30-second test leases expire, the production worker entry point resumes that same submission.
No second submission request is sent. The test checks one durable feedback result, replay identity, and stale-token fencing.
The initial API claim uses an injected one-millisecond lease.
Worker claims and ownership use supported 30-second settings. Stored timestamps are never edited to force recovery.
The API background executor and first worker pipeline use explicit fault-injection substitutes.
Recovery uses the built-in local feedback pipeline with a grounded synthetic task.
This evidence covers formative feedback recovery. Existing assessment tests retain the withheld learner-result boundary.

Launcher acceptance uses actual Windows subprocesses for port conflicts, child failures, bounded setup and readiness waits,
explicit shutdown, and supervisor death with a grandchild process. An unrelated process survives owned shutdown.
A slow HTTP response test checks the total probe deadline, including responses that keep sending bytes.
The combined PowerShell smoke also checked all six readiness checks, exit zero, and closed service ports after shutdown.
Task 7 logs remain under ignored `.scratch/task7-verification/` in its validation checkout.
These local checks do not approve research processing, provisional learner-result visibility, or pilot deployment.

SQLite should reside on durable storage with backups appropriate to the deployment. Never copy
the live database file directly. During a maintenance window, stop the API and worker, then run:

```powershell
cd src-main/backend
.venv\Scripts\python.exe scripts/verify_sqlite_backup.py `
  --database quantumlearn.db `
  --output-dir backups
```

The command uses SQLite's backup API to create a uniquely named backup, restores that backup to an
isolated temporary database, runs `integrity_check` and `foreign_key_check`, and compares the row
count and SHA-256 content digest for every application table. It exits non-zero on any mismatch and
keeps a data-free verification manifest beside the backup. Retain both files according to the
deployment's encrypted retention policy. Test disaster recovery against a copy in a non-production
environment; never overwrite the active database as part of a restore test.
