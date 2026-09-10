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
No workflow leases, formal decisions or feedback rows are injected by the test.

The original adapter reached both assessed feedback workflows, revision,
continuation and next-task acceptance, then received HTTP 422 when submitting an
answer-only EXPLANATION. The task requires typed episode evidence. The harness now
checks that the chosen activity is an unassessed explanation with no episode plan,
saves and reads back `episode.supported.explanation`, then submits that episode.
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
   the worker failed with `context_integrity_error`. The stored practice episode
   used `assessment.response.v2`; the assessment-context provider classified it as
   a missing assessment attempt. Independent task, retrieval and feedback context
   construction validated. This is a production dependency owned by the
   coordinator, not a fixture approval or harness transport failure.

## Verification record

The focused harness and usage regressions pass: **50 passed**. A separate preparer
refusal regression passes, proving that an existing directory is rejected without
changing its contents. Metadata extraction against the stopped diagnostic database
read four local generation/judge records from the two completed assessed workflows
and retained `unknown_or_incomplete` cost with a null AUD average. Ruff lint and
format checks cover the harness and its tests. Final real integration verification
is pending the coordinator's practice-schema correction.

Reproduce from `src-main/backend` with the project's existing Python environment:

```powershell
python -m pytest tests/test_task38_benchmark_integration.py -q -p no:cacheprovider --basetemp=.tmp-task38-integration-check
python -m pytest tests/test_task38_benchmark_harness.py tests/test_task38_benchmark_usage.py -q -p no:cacheprovider --basetemp=.tmp-task38-unit-check
python -m ruff check scripts/task38_benchmark tests/test_task38_benchmark_harness.py tests/test_task38_benchmark_usage.py tests/test_task38_benchmark_integration.py
python -m ruff format --check scripts/task38_benchmark tests/test_task38_benchmark_harness.py tests/test_task38_benchmark_usage.py tests/test_task38_benchmark_integration.py
```

The integration test refuses an occupied port and terminates only its own API and
worker. Its scratch directory contains private synthetic fixtures, SQLite data,
preparer/API/worker logs and `adapter-result.json`; none are committed. The report
contains the actual readiness response and adapter observations, not credentials.

This is single-learner adapter compatibility evidence. It supplies no 5–100-user
load, latency/scaling acceptance, external-provider execution, billed AUD cost,
human-confirmed formal outcome, research approval or release approval. No full
suite, live provider, participant run, merge or push is part of this verification.
