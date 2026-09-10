# Task 35 — offline validation tooling delivery

Date: 10 September 2026.

## Outcome

Implemented an offline, strict review importer and validation runner, deterministic
metric tests, 108 DRAFT quantum criterion probes, blank independent-review forms,
a blinded reviewer packet, and a separate review protocol. Actual expert validation
and AI assessment release remain outstanding. No generated case is educator-approved.

The bounded draft run reports **108 cases, 12 families, zero approved cases, zero
recorded system outputs, zero expert ratings, 540 missing case/channel outputs**.
Every unsupported estimate is null. Content/feedback/judge status is **UNVERIFIED**;
AI assessment release is **PENDING**; operational AI suggestions remain **false**.
The 108 cases include nine variants per family and 36 deliberately flawed feedback
candidates. The 72 candidate controls also require review, not assumed approval.

The separate numerical run matched all 12 expected ideal distributions using the
existing public `simulate_circuit` interface. Saved evidence includes exact probabilities,
sample counts, statevectors, bit order, measurement mappings, seed 35, 32 shots,
engine versions and manifest/scenario hashes. This establishes numerical consistency
for these fixtures, not human approval of explanations or full outcome validity.

## Requirements supported

| Requirement | Preparation/tool evidence | Still required |
| --- | --- | --- |
| Task 35; NFR12 | 108 source/criterion-mapped DRAFT cases; independent factual/hallucination rates per output channel | At least 100 genuinely educator-approved cases and actual model outputs |
| NFR13 | Six separate feedback dimensions, action/revision denominator, original independent scores retained | Calibrated expert rubric and completed ratings |
| NFR14 | Flawed-rejection and false-rejection denominators; 36 flawed draft feedback candidates | Actual judge runs and resolved expert labels |
| BP9–11; assessment specification §17 | Independent ratings, third-party adjudication, reviewer-pair baseline, confusion matrices, kappa, uncertainty and version drift checks | Approved population/statistic, accuracy/fairness/error limits and release decision |
| D-04/D-05/D-07 | Separate prediction/explanation/application probes; access/style variants; supported/unaided conditions; permanently pending offline assessment-release field | Approved full multipart forms, equivalent access modes, named reviewers and all D-07 activation evidence |

Thresholds are extracted from controlling NFR12–14 text, not invented. There is no
combined approval score, numeric learner grade or assumed AI-assessment error limit.
The provisional kappa planning values are not implemented as release thresholds.

## Changed files

Only new Task 35-owned files are included:

- `docs/learnlens/task-35-validation-tooling.md` — this delivery note.
- `docs/learnlens/task-35-review-protocol.md` — methods, schema workflow, source versions,
  review responsibilities, limitations and activation dependencies.
- `docs/learnlens/task-35-reviewer-packet.md` — 108 blinded, shuffled reviewer entries.
- `src-main/backend/scripts/task35_validation/__init__.py`
- `src-main/backend/scripts/task35_validation/schema.py`
- `src-main/backend/scripts/task35_validation/metrics.py`
- `src-main/backend/scripts/task35_validation/runner.py`
- `src-main/backend/scripts/task35_validation/prepare.py`
- `src-main/backend/tests/test_task35_validation_metrics.py`
- `src-main/backend/tests/test_task35_validation_runner.py`
- `src-main/backend/tests/fixtures/task35_validation/scenarios.json`
- `src-main/backend/tests/fixtures/task35_validation/draft-bundle.json`
- `src-main/backend/tests/fixtures/task35_validation/manifest.json`
- `src-main/backend/tests/fixtures/task35_validation/review-import.schema.json`
- `src-main/backend/tests/fixtures/task35_validation/blank-review-forms.json`
- `src-main/backend/tests/fixtures/task35_validation/numerical-evidence.json`

## Existing behaviour and data preserved

No production behaviour changed. PASS/INCOMPLETE results, human confirmation,
protected histories, unrestricted approved supported-stage conceptual hints and
separate unaided transfer remain the selected policy. Accessibility support is not
a result penalty. Research governance and disabled operational AI-assessment suggestions
were not modified. There are no migrations, backfills or dependency/lockfile/CI changes.
Reverting this commit removes only offline scripts, tests, fixtures and documentation.

## Exact verification commands and results

PowerShell commands below run from the worktree's `src-main/backend` directory.
`$task35Python` selects the existing coordinator-managed backend environment read-only;
no install, sync or runtime setup was performed. Its Python is 3.11.16, Pydantic 2.13.4,
Qiskit 2.5.1 and Aer 0.17.2.

```powershell
$task35Python = 'C:\Users\Jordan.Tran\Downloads\Honours Project\Monash-Honours-Project\src-main\backend\.venv\Scripts\python.exe'

& $task35Python -m ruff check scripts/task35_validation tests/test_task35_validation_metrics.py tests/test_task35_validation_runner.py
& $task35Python -m ruff format --check scripts/task35_validation tests/test_task35_validation_metrics.py tests/test_task35_validation_runner.py

& $task35Python -m scripts.task35_validation.prepare

& $task35Python -m scripts.task35_validation.runner --bundle tests/fixtures/task35_validation/draft-bundle.json --current-manifest tests/fixtures/task35_validation/manifest.json --report ../../.tmp-task35-checks/draft-report.json

& $task35Python -m pytest tests/test_task35_validation_metrics.py tests/test_task35_validation_runner.py -q --basetemp=../../.tmp-task35-checks/pytest5 -o cache_dir=../../.tmp-task35-checks/cache --junitxml=../../.tmp-task35-checks/unit-final.xml

& $task35Python -m scripts.task35_validation.prepare --numerical-report tests/fixtures/task35_validation/numerical-evidence.json
```

Results: lint passed; all seven Python files formatted; deterministic preparation
produced 108 cases; draft runner completed with UNVERIFIED/PENDING; **44 tests passed
in 0.55 seconds**, no skips; **12/12 numerical distributions matched**. The numerical
runner is sequential, uses the application's 15-second per-circuit limit and Aer's
existing single-thread setting. The JUnit and full draft report remain in task scratch;
the numerical receipt is committed. Runner exit 0 means the offline report was produced,
not that any release gate passed. Invalid import/schema/reference data returns exit 2
and a fail-closed error report.

From the worktree root, `git diff --check` passed before staging. Staged scope and
whitespace checks are repeated before commit. No combined coverage result is claimed.
The repository's coverage threshold, tests and assertions were not weakened.

### Initial failures and resolutions

- Initial sandboxed `git worktree add -b codex/task35-validation-tooling .tmp-task35-worktree main`
  could not create the Git ref lock. The same requested worktree operation succeeded
  with approved normal permissions; it started at the audited commit.
- The tracked root `.venv` points to a different machine's absent Python 3.12.2 and
  could not start. Used the existing backend Python 3.11.16 environment without changing
  either environment or shared setup.
- First focused run: **27 passed, two setup errors**, with missing/blocked pytest
  temporary paths and cache warnings. Explicit scratch-parent creation did not resolve
  the sandbox ACL issue; a second attempt also failed setup/cleanup with WinError 5.
  Running the same tests with normal process permissions and a fresh isolated basetemp
  passed all 29 then-present cases. Expanded subsequent runs passed 42 and finally 44.
  No assertion, skip, timeout or coverage configuration was relaxed. Two disposable
  cache directories from those failed attempts were removed after absolute-path checks.
- Initial formatting corrected one import ordering issue. Final lint and formatting
  checks pass. No application defects were changed as part of this task.
- Explicit IBM API 2.5 web pages could not be opened. The source register therefore
  identifies the successfully read 2.3 reference pages and the actual 2.5.1 runtime
  separately; source/version reconciliation remains an expert prerequisite.

## Open dependencies and human evidence

See the [review protocol](task-35-review-protocol.md#people-and-evidence-required-to-complete-task-35)
for the exact review checklist. The supplied records name Arv Surana as research lead,
but do not name Task 35 quantum experts, trained assessors, adjudicator, accessibility
reviewer, methods reviewer or release authority. Those appointments, training and signed
approval references remain blank rather than being fabricated.

Experts must approve sources/case coverage and complete actual independent ratings,
adjudication and fair-treatment analysis. Governance must supply AI-assessment error
limits, approved agreement statistic/precision, review triggers, revalidation rules and
the signed release decision. Actual provider outputs and authorised provider/environment
records are still needed. Task 32/33 study approval and processing controls remain separate
prerequisites for any learner research use.

No outside-ownership production patch is necessary for this offline delivery. Future
operational suggestions must be integrated by the coordinator only after D-07 evidence
exists, preserving human confirmation. After material changes to fingerprinted files,
the coordinator must regenerate/review draft manifests and rerun focused evidence;
never simply relabel old real ratings with a new digest.

## Explicitly deferred checks and limits

Combined backend/frontend/browser suites, combined coverage, live-provider evaluation,
load/scaling/cost campaigns and final integration are reserved for the coordinator.
No research participant, actual expert validation, manual access trial, hosted environment,
native browser, provider accuracy or learning-effectiveness evidence is claimed here.
The importer verifies shape and linkage, not signature authenticity or institutional
approval. These convenience drafts and correlated variants cannot establish population
fairness or operational assessment validity, even when synthetic metrics appear perfect.
