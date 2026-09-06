# Browser assessment record isolation

Date: 2026-09-06

## Outcome

Task 6 gives each assessment browser test private records.
Review tests receive a fresh assessor, course, response, attempt, and provisional decision.
Playwright creates these records again for every browser project, repeat, and retry.
Authoring tests also receive private accounts with one course assignment.
The assessed-submission browser test already creates its own course and accounts.

All four review actions run in every browser.
Each test requires the exact initial provisional state and checks the returned decision ID.
It also checks the expected result, lifecycle, and first review revision.
Keyboard, accessibility, and reflow assertions remain in place.
Assessor route accessibility now requires its own fixture and cannot silently skip those routes.

## Delivery and fixed base

The user authorised merging Task 5 into local `main` before starting this task.

- Task 5 feature commit: `b17d393`.
- Task 5 merge and Task 6 base: `d188f97d8f1f194513a0d0a30984493563557400`.
- Task 6 branch: `test/task-6-browser-assessment-isolation`.
- Task 5 used a separate merge commit. The checkout was clean before branching.
- No push occurred during this task. `origin/main` remained at `dd7bccce0b4b61c5eb366308faa9805bf07be149` after fetching.
- Task 6 remains uncommitted. Task 7 has not started.

The latest remote main run was [34030803224](https://github.com/akshatporwal002/Monash-Honours-Project/actions/runs/34030803224).
Backend, dependency audit, and secret scan passed.
Browser tests reported 50 passed and six failed in assessor accessibility and review.
That run predates the local Task 5 merge and these Task 6 changes.
There is no remote CI result for this branch.

## Reproduction

Before editing, the Chrome and Edge review tests both passed against the shared decision.
Their withhold and return actions left it provisional, masking the problem.
A repeated Firefox confirmation exposed the state dependency.
The second execution sent `CONFIRM` with state `CONFIRMED` and revision `1`.
The mounted API returned HTTP 422: `only a provisional result can be confirmed`.
The first execution also encountered a separate Firefox teardown failure after changing the decision.
The API restriction was correct. Reusing the same seeded decision was the test defect.

## Changes and boundaries

- `tests/support/assessment.py` accepts optional unique suffixes while preserving existing default seeds.
- `tests/support/assessment_review.py` creates a private review context and explicit assessor assignment.
- `tests/browser_e2e_server.py` creates review data on request, instead of seeding one shared decision at startup.
- `tests/support/assessment_authoring.py` creates a private account for each authoring context.
- `e2e/fixtures/assessment.ts` provides test-scoped review data and attaches record IDs for retry evidence.
- Review, authoring, and assessor accessibility browser tests consume private contexts.
- `tests/test_browser_assessment_fixtures.py` verifies the fixtures through real mounted authentication and review routes.
- `src/features/assessment/assessment.module.css` lets record IDs wrap within the assessor screen's grid.
  This scoped presentation fix preserves full IDs and the existing 320-pixel reflow check.

Python paths above are relative to `src-main/backend`; frontend paths are relative to `src-main/frontend`.
The fixture endpoints exist only in the disposable browser test server.
A regression checks that none are mounted by the production application.
Confirmation, override, course access, replay, and result visibility code is unchanged.
D-01 remains pending, and Task 3's withheld learner-result marker remains intact.
Synthetic authoring and research approvals stay confined to existing test overrides.

## Verification

Focused Chrome checks passed all 11 tests.
Mounted fixture and assessor checks passed all 15 tests.
They verify distinct records, one course per account, and hidden cross-course reads and writes.
An invalid same-result override returns 422. Reconfirming a confirmed result also returns 422.
Exact replay returns the same review revision and adds no extra review.
The second fixture retains a provisional decision with empty review history after the first fixture changes.

Frontend lint and production build passed.
Frontend unit and accessibility checks passed 178 tests across 52 files.
The full backend suite passed 733 tests, including migration checks, with 85.22% service coverage.
Ruff lint and formatting passed across 309 Python files.
OpenAPI and frontend contract drift checks passed. No regeneration was needed.
The locked dependency check passed with `uv lock --check --offline`.

The first headless full browser run reported 71 passed and one Firefox reflow failure.
The return action succeeded, but fresh UUID values widened the page by 67 pixels at a 320-pixel viewport.
A focused repeat reproduced the overflow twice in three executions, at 68 and 72 pixels.
The scoped wrapping fix addresses this layout defect without shortening IDs or weakening assertions.
After that fix, five fresh Firefox return-action executions passed the original reflow checks.
The final complete four-browser suite passed all 72 tests, with no retries or skipped tests.
Its report contains 20 distinct course, response, attempt, and decision sets for review and assessor accessibility.
The forced-retry probe passed all 16 actual retries across the four actions and four browsers.
All first executions completed their action and failed only at the deliberate post-test hook.
The JSON audit verified 32 distinct course, response, attempt, and decision sets across those executions.
The temporary probe was removed after verification.
Each action also passed alone in a separate disposable run across all four browsers: 16 checks passed.
`git diff --check` passed, and the index remains empty.
Raw local logs are retained under the ignored `.scratch/task6-verification/` directory.

### Repeatable commands

Use the locked Python 3.11 environment and supported Node 22.
Backend checks use `APP_ENV=test` and a test-only learning-event pseudonym secret.
Run from `src-main/backend`:

```powershell
.venv/Scripts/ruff.exe check .
.venv/Scripts/ruff.exe format --check .
.venv/Scripts/python.exe -m pytest --cov=app.services --cov-report=term-missing --cov-fail-under=80
.venv/Scripts/python.exe scripts/export_openapi.py --check
.venv/Scripts/python.exe scripts/generate_frontend_contracts.py --check
uv lock --check --offline
```

Run from `src-main/frontend`:

```powershell
npm run lint
npm test
npm run build
$env:QUANTUMLEARN_FIREFOX_HEADLESS='1'
node e2e/run.mjs
node e2e/run.mjs assessment-review.e2e.ts --grep 'Confirm result'
```

Repeat the final command for `Withhold result`, `Return for review`, and `Override result`.
Each invocation starts a new disposable database and selects only that action in all four browsers.

For actual retry evidence, a temporary copy of the review spec adds this hook:

```typescript
test.afterEach(async ({}, testInfo) => {
  if (testInfo.status === 'passed' && testInfo.retry === 0) {
    throw new Error('TASK6_FORCE_RETRY_AFTER_SUCCESSFUL_REVIEW')
  }
})
```

Run that copy with `--retries=1 --reporter=list,json`, then remove the temporary spec.
The audit requires exactly the deliberate error on the first execution and a passing retry.
It compares attached course, response, attempt, and decision IDs across both executions.
The hook is not part of the normal suite. The local probe script, source, report, and ID audit remain in the ignored evidence directory.

## Independent reviews

The `code-review` skill reviewed the working tree against `d188f97` in separate agents.
Both agents included the new untracked test files.

### Standards

No code violations or actionable baseline smells found.
Test support follows existing conventions and uses explicit course scope and real review rules.
The follow-up review requested documenting the CSS delta and including it in rollback.
The reviewer checked those additions and closed the finding.
Standards total: 0 open findings.

### Spec

No implementation findings or Task 7 scope creep found.
Fresh test-scoped contexts cover each project and retry without changing finalization rules.
The reviewer checked the completed browser and retry evidence and closed the documentation finding.
The remaining isolated-action checks subsequently passed as recorded above.
Spec total: 0 open findings.

## Limits and rollback

This task changes test infrastructure and one scoped assessor presentation rule.
It does not approve production policy or deploy the application.
The initial complete local run hit repeated Windows headed Firefox timeouts and was stopped.
The rerun uses the existing `QUANTUMLEARN_FIREFOX_HEADLESS=1` option, matching CI browser mode.
No browser assertion, timeout, worker count, or production rule was weakened.

Rollback consists of reverting this task's test, fixture, and assessor stylesheet changes together.
No production schema, migration, API contract, or persisted live record changed.
Reverting restores the shared assessment fixture and its known order dependency.
Keep Task 4 and Task 5 production restrictions in place.
