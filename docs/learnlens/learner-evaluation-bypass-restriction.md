# Direct learner evaluation restriction

Date: 2026-09-06

## Outcome

Task 4 closes the direct learner evaluation bypass.
Authenticated learners receive HTTP 403 from
`POST /api/v1/assessment/attempts/{assessment_attempt_id}/evaluate`.
The route does not resolve an attempt, construct an evaluator, or return a decision.
Missing, owned, foreign, and replayed identifiers receive the same denial.
Unauthenticated requests receive HTTP 401. Other roles remain denied.

Normal task submission retains its durable evaluation job and recovery worker.
Task 3's formal marker remains `{"result": null, "visibility": "withheld"}`.
D-01 remains pending. This restriction grants no visibility or assessment approval.
No learner evaluation retry or status endpoint was added.

## Base and remote checks

- Base: `e709a8a41aabdcd07b78caf129518ae0aa294f3a`.
- Feature branch: `fix/task-4-learner-evaluation-bypass`.
- The initial worktree was clean on `main`.
- Fetch confirmed that local `main` and `origin/main` matched the base.
- No commits, staging, push, merge, deployment, or live database changes occurred.

[Base CI run 34029611751](https://github.com/akshatporwal002/Monash-Honours-Project/actions/runs/34029611751)
was running when checked before editing. It later finished with a failure.
Backend tests, migrations, contracts, dependency audit, and secret scan passed.
Frontend lint, unit tests, and build passed. Browser E2E reported 50 passed and six failed.
The failures affected educator/assessor accessibility and keyboard assessment review
in Edge, Firefox, and WebKit. Their logs report missing visible elements.
These results describe the base commit, not the uncommitted Task 4 changes.
Repairing the broader browser suite remains separate work.

## Requirements completed

- Task 4's immediate restriction: the mounted route rejects direct evaluation.
- FR1 and FR3, within this boundary: authentication and denial prevent foreign record access.
- Replay safety: repeated denial requests do not change evaluation records or invoke evaluation.
- D-01 guard: responses contain no provisional decision, reason code, or decision identifier.
- Existing task submission and history still enforce current course access before replay or reads.

This is bounded security repair evidence. It does not complete all FR1, AT19, or AT24 requirements.

## Changes

- `src-main/backend/app/api/routes/assessment_evaluation.py` now returns a fixed denial.
  Its evaluator dependency and request/result models were removed.
- `src-main/backend/tests/test_assessment_evaluation_api.py` checks the retired API contract.
- `src-main/backend/tests/test_learner_evaluation_boundary.py` exercises the mounted API.
- `src-main/contracts/openapi.json` and `src-main/frontend/src/api/generated.ts` were regenerated.
  The operation is deprecated, with no success response or provisional-result schema.

The durable job service, result mapper, assessment policy register, and database schema were not changed.

## Reproduction

The regression test ran before the route fix, through `create_app()` and FastAPI's TestClient.
It used real login, a disposable SQLite database, and the production rule evaluator.
A fixture supplied an approved `REMEMBER` phrase rule and a submitted response containing `Hadamard`.
Fixture approval applies only to the test data.

The learner's direct request returned HTTP 201 with `PASS`, `PROVISIONAL`,
and reason `TARGET_EVIDENCE_MET`. It created one decision while the durable job remained `pending`.
The regression failed at its expected HTTP 403 assertion.
After the fix, that same test denies evaluation and proves the recovery worker can finish the pending job once.

## Verification

- Focused backend suite: 88 passed.
- Full backend suite: 711 passed, including migration tests. Service coverage was 85.02%, above the 80% gate.
- Full frontend suite: 178 passed across 52 files.
- Ruff lint and format: passed across 305 Python files.
- OpenAPI and frontend contract drift checks: passed.
- Frontend TypeScript, ESLint, and production build: passed using Node 22.23.2.
- Assessed-read browser regression: Chrome, Edge, Firefox, and WebKit passed.
  Firefox first failed to launch its tab subprocess in the sandbox.
  Its isolated rerun outside the sandbox passed without code or test changes.
- `uv lock --check --offline`: passed with a writable temporary cache.
- `git diff --check`: passed.

The new tests cover five job states: pending, running, scheduled retry, human review, and completed.
Each is tested for the owner, another student, withdrawn enrolment, archived course, educator, and anonymous caller.
They compare full attempt, job, decision, criterion, and evaluation-audit rows before and after repeated denials.
They also reject evaluator construction and calls through test guards.
Existing and missing attempt identifiers return identical bodies for each caller.

Normal mounted submission uses the real durable application, executor, and rule adapter.
The test substitutes only the independent feedback executor.
Duplicate submission creates one response, assessment attempt, job, criterion evaluation, and provisional decision.
A conflicting replay returns HTTP 409 without evaluation changes.
Post-evaluation task reads and history retain the withheld marker.
Cross-course and revoked-access submission replays and history reads are denied without evaluation effects.

Backend commands run from `src-main/backend` with `APP_ENV=test`, a disposable database,
and a test-only pseudonym secret. Each pytest run used a unique base directory.

```powershell
.venv/Scripts/python.exe -m pytest tests/test_learner_evaluation_boundary.py tests/test_assessment_evaluation_jobs.py tests/test_assessment_evaluation_api.py tests/test_assessment_submissions.py tests/test_assessed_lms_reads.py tests/test_lms_core_api.py --basetemp $task4Temp -q --tb=short
.venv/Scripts/python.exe -m pytest --basetemp $task4Temp --cov=app.services --cov-report=term --cov-fail-under=80 -q --tb=short
.venv/Scripts/ruff.exe check .
.venv/Scripts/ruff.exe format --check .
.venv/Scripts/python.exe scripts/export_openapi.py --check
.venv/Scripts/python.exe scripts/generate_frontend_contracts.py --check
uv lock --check --offline
```

Frontend commands run from `src-main/frontend` with the installed Node 22 executable.

```powershell
node node_modules/vitest/vitest.mjs run --maxWorkers=2
node node_modules/typescript/bin/tsc -b
node node_modules/eslint/bin/eslint.js .
node node_modules/vite/bin/vite.js build
node e2e/run.mjs assessed-reads.e2e.ts
node e2e/run.mjs assessed-reads.e2e.ts --project=firefox
```

## Standards review

The independent Standards reviewer found no documented violations or actionable code smells.
The review covered the working-tree diff against the base, including the new boundary test.
It confirmed that the restriction preserves the existing submission service and matches the contract changes.

## Spec review

The independent Spec reviewer found no code findings.
Task 4 explicitly permits immediate restriction. The tests cover denial, replay, course scope,
durable processing, and the withheld marker. No Task 5 work was found.
Both reviews used the code-review skill and the supplied local specifications.
The skill's issue-tracker configuration is absent; no issue-tracker lookup was needed.

Review totals: Standards 0 findings; Spec 0 code findings.
Both reviewers also checked the completed handoff and found no issues.
Local check logs are retained in ignored `.scratch/task4-verification/` for inspection.

## Data changes and rollback

No migration, backfill, or stored-history rewrite is required.
Rollback would restore the route, its contract test, and both generated contracts from the recorded base.
Remove only this task's added boundary test and handoff when discarding the complete change.
Do not reset or clean unrelated work.

Restoring the old route would reopen the known bypass.
Any operational rollback must keep that endpoint denied until a replacement passes the same boundary tests.
Existing durable jobs and accepted submissions need no reversal.

## Limits and open items

- D-01 still needs product-owner and assessor approval before learner result visibility can be activated.
- Task 5 has not started. No research access or processing changes were made.
- The full local browser suite, native Safari, manual screen-reader checks, and hosted tests were not run.
- Dependency files are unchanged. Fresh local dependency audits and Gitleaks were not run;
  the recorded base CI passed those gates. Uncommitted changes have no remote CI run.
- Frontend checks emitted existing canvas and bundle-size warnings.
- Initial npm checks could not access the default cache. Direct use of installed Node 22 resolved that setup issue.
- This task does not establish pilot readiness or approve automatic assessment release.
