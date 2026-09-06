# Evaluator settings repair

Date: 2026-09-06

Branch: `fix/assessment-evaluator-settings`

Base: `8b01cd9`, the local merge of Task 1 into `main`.
Task 1 was committed as `643597d` and merged with a separate merge commit.
No remote push occurred.

## Outcome

Remaining Task 2 now requires valid automatic evaluator settings before assessment approval.
The two reported cases, empty anchors and an unsupported `met` key, no longer accept arbitrary answers.
The new regression failed twice before the repair.

`RuleSettings` defines bounded phrase lists and rejects unknown fields, malformed lists, empty evidence rules, and contradictions.
Approval and runtime use the same validation. Required phrases cannot also contain an excluded phrase.
Phrase rules support `REMEMBER` only. Reasoning criteria use human assessment, which is now the authoring default.
The form offers required, alternative, and excluded phrases for explicit recall checks.
Changing evaluator settings clears the existing Bloom and access verification checks.

Older stored definitions also undergo runtime validation. Invalid settings create no criterion decision or automatic assessment result.
The production adapter keeps these attempts pending for human review and marks the fault as non-retryable.
Unstructured critical-error rules also require human assessment; phrase exclusions are the supported automatic form.
Mixed evaluation still requires explicit human input, even when its automatic check is unavailable.

## Requirements completed

- Remaining Task 2: typed settings, authoring controls, approval validation, runtime safeguards, and real UI-to-API tests.
- AT5 and AT8: scoped evidence for valid rule approval and criterion decisions.
- AT9 and AT10: scoped evidence that invalid evaluator configuration cannot become a learner result.

These are bounded repair claims. They do not complete the whole assessment workflow or evaluator release gate.

Changed code and tests:

- `src-main/backend/app/services/assessment/rule_settings.py`, `alignment.py`, `evaluators.py`, and `runtime.py` enforce safe rules.
- `src-main/backend/app/services/assessment/definitions.py` and `app/schemas/lms.py` default new criteria to human assessment.
- `src-main/frontend/src/features/assessment/assessmentDraft.ts`, `AssessorSetupPanels.tsx`, and `useAssessorSetup.ts` implement authoring controls.
- Backend evaluator, definition, API, and job tests verify rejection and preserved decisions.
- `src-main/frontend/e2e/assessment-setup.e2e.ts` and its disposable backend fixtures exercise real authoring APIs.
- `src-main/contracts/openapi.json` records the changed API default.

## Existing behaviour preserved

Human decisions keep their evidence and reasons. AI remains advisory until its separate release gate passes.
Missing responses still yield `NOT_EVALUABLE` when the evaluator settings are valid.
Valid recall rules retain required and alternative matching, with explicit exclusion checks added.
Rule evaluator provenance is now `rules.anchor.v2`; mixed evaluation uses `mixed.rules-human.v2`.

## Data changes

No migration or history rewrite occurs. Published history and saved learner responses remain untouched.
New drafts default to `human` in the API and service. Explicit `rules` drafts must pass approval validation.
The OpenAPI contract was regenerated; the frontend contract generator and drift checks passed.

Recovery means reversing only this branch's changes and regenerating contracts.
Keep unsupported rules under human review during any rollback, because the old evaluator accepts empty settings.

## Verification

Backend checks used Python 3.11.15. Frontend checks used Node 22.23.2.
The installed global Node 24 runtime was not used for frontend validation.

- Initial regression: **2 failed** through `RuleCriterionEvaluator.evaluate`, before changing production code.
- Full backend run: **657 passed**, service coverage **84.86%**, above the configured 80% gate.
- Final focused run: **61 passed**, including four API cases added after full-suite collection.
- Full frontend run with two workers: **173 passed** across 51 files.
- Final browser run: **8 passed** across Chrome, Edge, Firefox, and WebKit, including Axe checks.
  Each method uses a fresh course, task, and definition in a disposable database.
- Backend Ruff lint and format: passed across the backend.
- Frontend ESLint, TypeScript, and production build: passed.
- OpenAPI and frontend contract drift checks: passed.
- Separate Standards and Spec reviews: no remaining findings after strengthening negative test fixtures.

The first frontend run timed out in one existing setup test while other suites were active.
The full rerun passed with `--maxWorkers=2`.
The build reports its existing bundle-size advisory; tests report jsdom's canvas limitation.
Firefox's pointer-based course selection timed out. The final test uses the selector's keyboard path on every browser.
All eight cases then passed. No selector application code was changed.

Backend commands, from `src-main/backend`:

```powershell
$env:APP_ENV = 'test'
$env:DATABASE_URL = 'sqlite://'
$env:LEARNING_EVENT_PSEUDONYM_SECRET = 'ci-only-pseudonym-secret-32-bytes-minimum'
$repairTemp = Join-Path $env:TEMP ('learnlens-settings-' + [guid]::NewGuid().ToString('N'))
.venv/Scripts/python.exe -m pytest --basetemp $repairTemp --cov=app.services --cov-report=term --cov-fail-under=80 --tb=short -q
.venv/Scripts/ruff.exe check .
.venv/Scripts/ruff.exe format --check .
.venv/Scripts/python.exe scripts/export_openapi.py --check
.venv/Scripts/python.exe scripts/generate_frontend_contracts.py --check
```

The final focused run selected `test_rule_settings.py`, `test_criterion_evaluation.py`,
`test_assessment_definitions.py`, `test_assessment_definition_api.py`, and `test_assessment_evaluation_jobs.py`.
It used the same environment and a fresh unique pytest directory.

Frontend commands, from `src-main/frontend`:

```powershell
npm exec --yes --package=node@22 -- node node_modules/vitest/vitest.mjs run --maxWorkers=2
npm exec --yes --package=node@22 -- node node_modules/typescript/bin/tsc -b
npm exec --yes --package=node@22 -- node node_modules/eslint/bin/eslint.js .
npm exec --yes --package=node@22 -- node node_modules/vite/bin/vite.js build
npm exec --yes --package=node@22 -- node e2e/run.mjs assessment-setup.e2e.ts
```

## Open items

- Task 15 owns the queue and criterion-entry flow for pending human-only attempts.
  This repair prevents automatic decisions but does not finish that human workflow.
- An extended browser probe received `409` when revising an already-published definition.
  Its cause remains undiagnosed. Fresh recall and human authoring use separate test records.
  Do not claim that changing the evaluator on a published definition is verified.
- Task 3, assessed task and dashboard reads, remains the next numbered repair.

## Limits

Phrase matching checks literal text. It does not prove reasoning quality or validate educational criteria.
Assessors must still choose suitable recall evidence and approve real task conditions.
No production assessment activation, live database work, hosted checks, or provider calls occurred.
Dependency audits, the complete browser suite, native Safari, and manual screen-reader checks were not run.
This feature remains uncommitted on its branch for review.
