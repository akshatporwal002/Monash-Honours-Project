# Task 29 progress timestamp correction

10 September 2026.

## Outcome

Progress responses now serialize explicit UTC instants after SQLite reload.
`2026-09-10T03:33:21.486860Z` displays as 1:33 pm in Sydney, preserving the
original recorded instant. Previously the offset-free value displayed as 3:33 am.

Tested baseline: `27a397a66b5fb6544ba08d9c8950fbbc8c6b4ca4`, matching the
[baseline audit](main-audit-2026-09-10.md).

## Requirements completed

- FR19, FR21, FR22 and FR39: progress timestamps retain their recorded instant in
  learner/cohort history, observations, estimates, results, adaptations, nested
  choices, evidence details and contributing records.
- A progress-specific validated timestamp type restores UTC to naive values
  from the known UTC database sources. Already-aware values are converted to UTC
  without relabelling their wall-clock time. Microseconds remain intact.
- `ProgressChoice` specializes the shared activity-history response for this
  boundary. The unrelated activity API is unchanged.
- OpenAPI documents the explicit UTC serialization; generated TypeScript reflects
  the progress-specific choice type. Timestamp wire fields remain date-time strings.

The service projects stored timestamps directly. SQLite removes their timezone
metadata on reload, and the previous response schemas accepted naive datetimes.
The frontend correctly interprets offset-bearing strings with `Date`; no frontend
production-code change or fixed Sydney offset is needed.

## Existing behaviour preserved

- Scoped learner and educator access, archived-course restrictions, evidence
  reveal guards and no-store responses are covered by the affected tests.
- Pending results remain unreleased. Formal results, whole-decision outcome
  selection, assessment rules and reassessment behaviour are unchanged.
- Observations, uncertain estimates, support and formal results stay separate.
- Weekly counts and filters retain their existing UTC date grouping. This fix
  changes timestamp serialization, not reporting-week policy.

## Data changes

None. There is no migration, historical backfill or timestamp rewrite.
The integration regression fixes insertion times before immutable fixture records
are first saved, opens a new SQLite session, and compares complete stored rows
before and after progress reads. It also checks the loaded ORM timestamp remains
naive while its separate response value carries UTC.

## Verification

The commands below use PowerShell, starting at the repository root with Node
22.13.0 on `PATH`. Verification reused installed dependencies without lock changes.

```powershell
$repo = (Get-Location).Path
$python = (Resolve-Path 'src-main/backend/.venv/Scripts/python.exe').Path
$env:APP_ENV = 'test'
$env:PYTHONPATH = '.'
$env:LEARNING_EVENT_PSEUDONYM_SECRET = 'timezone-tests-synthetic-secret-32-bytes-minimum'
```

Python 3.11.16, Node 22.13.0, Vitest 4.1.10 and Vite 8.1.3 were used.

### Reproduction before the fix

The original audit probe failed its timezone assertion. The recorded interval was
`2026-09-10T05:37:13.828846+00:00` to `2026-09-10T05:37:14.485383+00:00`;
both the service and JSON returned `2026-09-10T05:37:14.239488` without an offset.

From `src-main/backend`, the new regression was run before the fix:

```powershell
& $python -m pytest tests/test_learning_progress_timezones.py -q -x --basetemp="$repo/.tmp-progress-timezones/red2"
```

Result: **one expected failure in 2.53 s**, because the reloaded observation's
`utcoffset()` was `None`, rather than zero. After the schema change, the same
test file passed all **nine tests in 2.42 s** with basetemp `green1`.

### Final affected checks

From `src-main/backend`:

```powershell
& $python -m pytest tests/test_learning_progress.py tests/test_learning_progress_timezones.py tests/test_assessed_lms_reads.py tests/test_learner_results.py tests/test_reassessment.py tests/test_simulation_evidence.py tests/test_assessment_contracts.py -q --basetemp="$repo/.tmp-progress-timezones/backend-final"
& $python -m ruff check .
& $python -m ruff format --check .
& $python scripts/export_openapi.py --check
& $python scripts/generate_frontend_contracts.py --check
```

Results: **75 passed in 49.65 s**, zero failures/skips; Ruff passed;
**509 files already formatted**; both contract drift checks passed.
The contracts were regenerated with the same two scripts without `--check`.

From `src-main/frontend`:

```powershell
npm.cmd run test -- src/features/progress/LearningProgress.test.tsx --maxWorkers=1
npm.cmd run test -- src/features/progress/LearningProgress.test.tsx src/features/assessment/LearnerResultPanel.test.tsx src/features/assessment/OutcomeResultPanel.test.tsx src/features/assessment/contracts.test.ts src/app/assessedReads.test.tsx --maxWorkers=1
npm.cmd run lint
npm.cmd run build
```

Results: **27 new progress cases passed** in 5.36 s; the combined affected batch
passed **35 tests across five files** in 15.36 s. ESLint, TypeScript and the
production build passed. The existing 837.02 kB main-chunk advisory remains.

The new cases cover Sydney standard time, summer time, both 2026 daylight-saving
transitions, local midnight, the New Year boundary and explicit non-UTC offsets.
Component tests supply a deterministic viewer locale/zone to the real native
formatter while retaining real Date parsing and ICU conversion. They check
learner/cohort progress, all five history timestamp placements, contributing
records and evidence details without changing the host or shared test settings.

The original audit probe passed after the fix: the service returned
`2026-09-10T05:43:27.230558+00:00` and JSON returned
`2026-09-10T05:43:27.230558Z`, within the recorded creation interval.
A separate unmocked Node check, with `TZ=Australia/Sydney`, printed
`10/09/2026, 3:33:21 am` for the original audit string and
`10/09/2026, 1:33:21 pm` for that string with `Z`, confirming the ten-hour error.
`git diff --check` passed.

Initial sandbox attempts could not access pytest temporary directories or spawn
Vite's helper; those were environment failures, not passing test evidence. The
successful reruns used normal process/filesystem permissions. Ruff initially
panicked while traversing inaccessible scratch directories; both full backend
Ruff checks passed after those temporary directories were cleared.

## Limits

No live learner database, hosted deployment, native browser or complete browser
suite was exercised. This scoped correction assumes the existing progress source
columns contain UTC, as their writers specify. It cannot recover a timezone from
arbitrary externally imported local-wall-clock data. Other APIs' timestamp
semantics and reporting-week policy are outside this correction.
