# Assessed task and dashboard read repair

Date: 2026-09-06

Remaining Task 3 is implemented on `fix/assessed-task-dashboard-reads`.
The base is local main merge `46b4c1e`, which integrated Task 2 commit `d621a4e`.
This repair remains uncommitted for review. No remote push occurred.

## Result

Formal submissions now survive task reloads, submission history, learner dashboards,
educator student lists, educator dashboards, and recommendation reads.
The public submission service rebuilds task reads, so this also repairs that submission boundary.

Missing scores remain null. A real practice score of zero remains zero.
Score aggregates exclude formal attempts and missing scores. An empty average is null.
An absent average does not trigger score-based risk, while overdue-task checks still apply.
The latest formal response never falls back to an older practice score for that task.

Task summaries, history, and recent activity carry a separate formal-assessment marker.
It contains `result: null` and `visibility: withheld`.
The marker comes from the assessment form reference, never from a missing score.
The frontend separates a saved formal response from a practice score.
D01 result visibility remains pending, so these reads do not expose assessment decisions.

The task declaration reader also used the assessor criterion schema by mistake.
It now uses the learner criterion schema, which accepts the published task conditions.
OpenAPI and frontend contracts were regenerated.

## Verification

- The 15 new API cases failed before the repair during real submission processing.
- All 26 focused read and LMS core tests passed after the repair.
- The full backend suite passed: 676 tests, with 84.95% service coverage against an 80% gate.
- All 178 frontend tests passed across 52 files.
- The real submission, reload, history, and both-dashboard flow passed in Chrome, Edge, Firefox, and WebKit.
- The browser flow includes an Axe check of the educator student list.
- Backend Ruff lint and format checks passed.
- OpenAPI and frontend contract checks passed.
- Frontend TypeScript, ESLint, and production build checks passed.
- Separate Standards and Spec reviews found no blocking issues.

API cases cover formal-only history and mixed history with practice scores of zero and 80.
Mixed cases include an older score of 25 for the same assessed task.
Browser fixtures create independent users and assessment records in a disposable test database.
The initial multi-browser run exposed a test logout race. Waiting for the login screen fixed it.
The final four-browser run passed all four cases.

Commands from `src-main/backend`, with test environment variables and a unique pytest base directory:

```powershell
.venv/Scripts/python.exe -m pytest tests/test_assessed_lms_reads.py tests/test_lms_core_api.py --basetemp $readTemp -q
.venv/Scripts/python.exe -m pytest --basetemp $readTemp --cov=app.services --cov-report=term --cov-fail-under=80 -q --tb=short
.venv/Scripts/ruff.exe check .
.venv/Scripts/ruff.exe format --check .
.venv/Scripts/python.exe scripts/export_openapi.py --check
.venv/Scripts/python.exe scripts/generate_frontend_contracts.py --check
```

Commands from `src-main/frontend`, using Node 22:

```powershell
npm exec --yes --package=node@22 -- node node_modules/vitest/vitest.mjs run --maxWorkers=2
npm exec --yes --package=node@22 -- node node_modules/typescript/bin/tsc -b
npm exec --yes --package=node@22 -- node node_modules/eslint/bin/eslint.js .
npm exec --yes --package=node@22 -- node node_modules/vite/bin/vite.js build
npm exec --yes --package=node@22 -- node e2e/run.mjs assessed-reads.e2e.ts
```

## Limits and next work

This change repairs reads without migrating or rewriting stored history.
Full legacy-score retirement and lifecycle display remain separate tasks.
Task 4 is the next numbered handoff item. Task 15 still owns pending human assessment entry.
The additional case for withholding an already-confirmed stored decision was suggested in review but was not added.
The read mapper never queries decisions, and the new response type only permits a null result.

No hosted checks, live database changes, provider calls, or deployment occurred.
The complete browser suite, native Safari, dependency audits, and manual screen-reader checks were not run.
Frontend tests emitted existing canvas warnings, and the build emitted a chunk-size warning.
Neither failed its command.

Rollback is to revert this feature's schema, service, frontend, and generated-contract changes together.
No database migration needs reversal.
