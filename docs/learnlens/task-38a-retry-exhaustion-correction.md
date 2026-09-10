# Task 38A — retry exhaustion correction

Independent review of `27087ff42a3d8d1270e7c54945dd1f240e8c2705` found that
assessment evaluation, continuation and terminal integration could strand a due
scheduled retry after the attempt ceiling was lowered. Assessment also scheduled
a second attempt after its first retryable fault when claimed with a ceiling of one.

The finalizers previously selected only expired running jobs. They now also select
due scheduled retries whose attempt count exhausts the current ceiling. Updates
compare the selected state, execution token, count, lease and retry timestamp so
concurrent ownership or terminal changes remain fenced. Original failure categories
are retained and terminalization clears retry schedules. Assessment's immutable
claim now carries the ceiling used to claim it; failure handling uses that snapshot
instead of the constant three. No migration or public API contract change is needed.

Regression evidence, run from `src-main/backend` with the shared read-only Python
3.11 executable and isolated temporary databases:

```powershell
python -m pytest tests/test_task38_retry_exhaustion.py -q --tb=short -p no:cacheprovider --basetemp=.tmp-task38a-exhaustion-red2
python -m pytest tests/test_task38_retry_exhaustion.py -q --tb=short -p no:cacheprovider --basetemp=.tmp-task38a-exhaustion-green
python -m pytest tests/test_task38_retry_exhaustion.py tests/test_assessment_evaluation_jobs.py tests/test_continuation_repository.py tests/test_terminal_integration_outbox.py -k 'not killed_assessment_claim' -q --tb=short -p no:cacheprovider --basetemp=.tmp-task38a-exhaustion-related
python -m ruff check app/services/assessment/jobs.py app/services/continuation/repository.py app/services/terminal_integrations/repository.py tests/test_task38_retry_exhaustion.py
```

- Red: **4 failed, 3 passed**, 5.66 seconds. Three queues remained scheduled;
  the actual assessment executor also scheduled a retry despite its one-attempt limit.
- Green: **7 passed**, 4.87 seconds.
- Related queue/fencing coverage: **46 passed, 1 deselected**, 30.03 seconds.
  The excluded killed-process/backup scenario runs migrations and is reserved for
  the coordinator. Ruff passes on all four changed Python files.
- An initial test accessor incorrectly expected an execution token on the public
  continuation record; corrected to inspect its actual persisted job before the
  recorded red run above.

The regressions preserve unexpired leases, wait until scheduled retries are due,
prevent resurrection after raising the ceiling, retain terminal failure history,
and keep immutable learner responses unchanged. No assessment decision is fabricated.
All provider faults are synthetic. No full suite, migration, provider campaign,
dependency change, merge or push was performed.
