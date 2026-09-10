# Task 38 — bounded integration verification

Verification branch: `codex/verify-benchmark-integration`, created from integrated
commit `d30570eb048443bc2ac46a6b420f0153d5904d69`. The original Task 38 delivery
branch and commit `9eb6d06055bb8f35d3d0e49b8e32b61344ca5289` remain unchanged.

## Scope and harness correction

The actual preparer provisions one fresh synthetic learner in a new SQLite
database. A real loopback API on port 4690 and a separate durable worker exercise
the production `LearningLoop` transport with cookies, CSRF and rate limits enabled.
Provider selection is explicitly local, the API key is empty, and research is
disabled. The worker uses `app.worker.main`, matching its installed entry point.
Test-only observation wrappers in both API and worker record the actual submission
context received by the local generator and judge, then delegate unchanged to their
shipped methods. Receipts retain the executing process.
No workflow leases, formal decisions or feedback rows are injected by the test.

The original adapter reached both assessed feedback workflows, revision,
continuation and next-task acceptance, then received HTTP 422 when submitting an
answer-only EXPLANATION. The task requires typed episode evidence. The harness now
checks that the chosen activity is an unassessed explanation with no episode plan,
saves and reads back `episode.supported.explanation`, then submits that episode.
The formative payload has no duplicate legacy answer; both recorded provider inputs
must contain the typed explanation, not the `Frozen multipart response` placeholder.
Unexpected conditions stop the profile before draft or submission writes. The fake
transport now rejects the original answer-only payload, and regression tests cover
the typed response and each changed-condition stop.

## Integration dependencies and observed failures

1. The preparer migrated successfully to `0045`, but readiness still expected
   `0044` and returned HTTP 503. The coordinator's prerequisite
   `a38e6af5fad7f475c4b4032492e68db3c9f429ce` was applied as `064684b` on this
   branch. The final regression requires HTTP 200 and every readiness check ready.
   Earlier diagnostic runs preserved the failed readiness gate; they did not
   establish readiness or release approval.
2. After the typed explanation correction, its submission returned HTTP 201, but
   its feedback workflow failed with `context_integrity_error`. The stored practice episode
   used `assessment.response.v2`; the assessment-context provider classified it as
   a missing assessment attempt. Independent task, retrieval and feedback context
   construction validated. This is a production dependency owned by the
   coordinator, not a fixture approval or harness transport failure.
3. The coordinator also identified lost typed content at the generic feedback input
   boundary. A terminal `validated` result alone cannot establish content delivery;
   the final regression checks the generator and judge's actual received inputs.
   The coordinator's two prerequisite commits were applied in order:
   `0b4322021fc562a969d6af4ba6cec45863c8b335` as `b86f2b6`, then
   `af7bfb8050b4efb427ed513a691ce2b5cbad182e` as `1c1e1b2`.
4. The first run with both prerequisites completed all workflows but failed the
   test's input-receipt check. The observer covered only the worker, while the
   shipped API's `InProcessFeedbackExecutor` handled feedback. The final test
   observes both processes without changing leases or execution ownership.

## Verification record

On 2026-09-10, **54 focused checks passed**: 50 harness/usage tests and four
integration/preparer/cleanup tests. The final fresh integration file completed in
28.35 seconds. Ruff lint and format checks passed for all 11 harness/test Python
files. No broader suite was run in this task.

The final run observed:

- HTTP 200 readiness, every check ready, database migration `20260910_0045`.
- One fresh synthetic learner; 35 actual HTTP requests, all measured operations successful.
- Three immutable submissions, two assessment attempts, three completed feedback
  workflows, three learner-model snapshots, one worker heartbeat, zero assessment decisions.
- `learning_complete=true`, `status=awaiting_human`, `formal_result=null`.
- Both actual formative generator and judge inputs contained
  `practice.feedback-evidence.v1`, empty legacy answer/code/circuit, and the exact
  typed `episode.supported.explanation`.
- **API background execution handled both captured provider calls.** The durable
  worker was active, but this run does not prove durable feedback recovery. The
  coordinator's dedicated API-to-offline-worker tests cover that separate path.
- Six usage records from the stopped database backup. Recorded provider/model pairs:
  `local/bounded-extractive-v1`, `local-deterministic/quantumlearn-rules-v1`, and
  `local-deterministic/quantumlearn-judge-v1`.
- Cost remains `unknown_or_incomplete`; external AUD subtotal and per-complete-loop
  average are null, with zero human-confirmed complete loops. Local records are
  excluded from external-cost evidence.
- Both owned processes stopped; a subsequent socket bind confirmed port 4690 released.

The earlier diagnostic failures remain under their separate scratch directories.
The final private receipts are under
`src-main/backend/.tmp-task38-integration-final2/test_preparer_and_real_local_l0/`
in this verification worktree. Their SHA-256 hashes are:

| Receipt | SHA-256 |
| --- | --- |
| `adapter-result.json` | `610670c4b65f4053ccd499c739c4e3a58654d9bdd6fe14176fd08f070977050f` |
| `api-inputs.jsonl` | `fa969615166278cba6e7dc453fb43d43e246394eda8e8df56fa76e1dee29e8b2` |
| `usage-result.json` | `07bfa999400457fbccf493e15a2d9096d017137c4325c3580a71b7591a051159` |
| `usage-snapshot.sqlite` | `538a895adee983476cca51f968e81bd2e127f500517b4c60a38213ac98e1ef9a` |

Reproduce from `src-main/backend` with the project's existing Python environment:

```powershell
python -m pytest tests/test_task38_benchmark_integration.py -q -p no:cacheprovider --basetemp=.tmp-task38-integration-check
python -m pytest tests/test_task38_benchmark_harness.py tests/test_task38_benchmark_usage.py -q -p no:cacheprovider --basetemp=.tmp-task38-unit-check
python -m ruff check scripts/task38_benchmark tests/test_task38_benchmark_harness.py tests/test_task38_benchmark_usage.py tests/test_task38_benchmark_integration.py
python -m ruff format --check scripts/task38_benchmark tests/test_task38_benchmark_harness.py tests/test_task38_benchmark_usage.py tests/test_task38_benchmark_integration.py
```

The integration test refuses an occupied port and terminates only its own API and
worker. A shutdown timeout triggers a bounded kill/wait fallback; a failure cleaning
up one process does not skip the other process or closing the logs. Its scratch
directory contains private synthetic fixtures, SQLite data, preparer/API/worker logs,
provider-input receipts for whichever process executes feedback, `usage-result.json`
and `adapter-result.json`; none are committed. The adapter report contains the actual
readiness response and adapter observations, not credentials.

This is single-learner adapter compatibility evidence. It supplies no 5–100-user
load, latency/scaling acceptance, external-provider execution, billed AUD cost,
human-confirmed formal outcome, research approval or release approval. No full
suite, live provider, participant run, merge or push is part of this verification.
