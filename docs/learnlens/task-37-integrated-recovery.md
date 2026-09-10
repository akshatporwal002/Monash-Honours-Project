# Task 37 — integrated local recovery and restore

Status: **PREPARED; subprocess drill NOT RUN**. The coordinator is running the
combined suites on another frozen checkout. This branch must wait for the explicit
drill execution signal before starting worker processes.

Base: `4fe8bb8184359e1fae606bc8cdd559fe54bc4760`.
Branch: `codex/task37-integrated-recovery`.

## Agreed verification boundaries

The assignment explicitly selected the authenticated submission API, a real
durable worker claim/crash/restart, persisted exactly-once learning records, and
the shipped database/source backup and restore interfaces. Database assertions
are intentional evidence of history preservation, not substitutes for API checks.

One synthetic assessed episode is accepted through the real cookie/CSRF API.
Only the API's lost background dispatch and the worker pause after its committed
claim are injected. Recovery uses the existing 30-second ownership/job leases;
no stored clocks, execution counters, results or evidence are rewritten.
The worker is killed and replaced without another submission POST. Checked
feedback, learner estimate and next-activity records must appear exactly once.

A synthetic authorised assessor then records a decision through the shipped
human-assessment service. This fixture action is not expert validation or a real
assessor's approval. Study consent, withdrawal and researcher revocation belong
to the same synthetic learner/course, while the production research gate remains
closed throughout. No real participant, provider or study is used.

The stopped database and current/historical source bytes are bundled and restored
into a new directory. Verification checks IDs, content digests, foreign keys,
immutable history, UTC chronology, API feedback/result reads, withdrawal and
revocation denials, and the still-closed research gate. A backup created before a
later withdrawal cannot know that future event: operational restoration requires
an authoritative later governance record and reconciliation before research use.

## Isolation and limits

All data, marker files and logs are under pytest's private temporary directory.
The API uses FastAPI's TestClient at origin `http://127.0.0.1:4710`; it opens no
network listener. Worker subprocesses use local adapters, empty provider keys,
a loopback-only unusable provider endpoint, a new migrated SQLite file and private
uploads. Only process handles created by the drill are terminated. Cleanup is
bounded and attempts every owned process and log even after a shutdown failure.

No production files, migrations, shared settings, generated contracts or master
ledger are changed. This drill cannot establish hosted TLS, live-provider
recovery, institutional approval, workload capacity, or release readiness.

## Verification receipts

Preparation: Ruff lint and format checks pass for all three new Python files.
The six isolated worker-configuration checks pass (`6 passed, 1 deselected in
1.51s`). They reject a different database, different uploads, research enabled,
non-local provider, provider credential, and missing private database. These
checks start no worker processes. The initial sandboxed attempts failed in
pytest temporary-directory setup with Windows ACL denial; the same scoped
selection passed with execution outside the sandbox and a private worktree path.
Actual API/worker/crash/restore drill: **NOT RUN; awaiting coordinator signal**.

From `src-main/backend`, after the coordinator schedules the subprocess run:

```powershell
python -m pytest tests/test_task37_integrated_recovery.py -q -p no:cacheprovider --basetemp=../../.tmp-t37-drill
```

Failures and exact scoped results will be retained here after execution. Passing
helper checks alone do not establish the integrated recovery claim.
