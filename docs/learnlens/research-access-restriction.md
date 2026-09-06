# Research access and processing restriction

Date: 2026-09-06

## Outcome

Task 5 separates research exports from ordinary analytics access.
Exports require a current course-scoped `research` assignment.
Educator, administrator, and assessor access do not supply that permission.
The existing role service checks revocation, expiry, start time, and account status on each request.

Study and consent controls remain incomplete, so a separate production gate blocks exports even with a valid grant.
The mounted route returns HTTP 403 without a grant, or HTTP 503 with `research_governance_pending` when approval is missing.
Both denials occur before export preparation or streaming.
The global research flag cannot supply approval.

Runtime feedback creates no research handoff under either global flag setting.
The built-in worker preserves queued research intents and baseline jobs without claiming them.
It continues processing teaching continuation, feedback, and assessment work.
D-03 and D-08 remain pending. Task 33 still owns study approval, consent, withdrawal, and governed activation.
Task 6 has not started.

## Task 4 delivery and Task 5 base

The user authorised committing, merging, and pushing Task 4 before starting the next task.

- Task 4 feature commit: `b799cf1`.
- Task 4 merge commit and Task 5 base: `dd7bccce0b4b61c5eb366308faa9805bf07be149`.
- Task 4 was merged with a separate merge commit and pushed to `origin/main`.
- Local `main`, remote `main`, and the clean checkout matched before creating this branch.
- Task 5 branch: `fix/task-5-research-access-restriction`.
- Task 5 remains unstaged and uncommitted. No deployment or live database changes occurred.

[Post-merge CI run 34030803224](https://github.com/akshatporwal002/Monash-Honours-Project/actions/runs/34030803224)
passed backend, dependency audit, and secret scan.
Its browser suite reported 50 passed and six failed.
The failures affect educator/assessor accessibility and keyboard review in Edge, Firefox, and WebKit.
The same six cases failed before Task 4 in run `34029611751`.
They are recorded separately from the uncommitted Task 5 checks.

## Reproduction

Before the restriction, two mounted API tests logged in as a real educator and administrator.
The production access policy allowed both to reach export preparation without a research grant.
A recording export-service substitute returned a synthetic record.
Both requests returned HTTP 200, with one preparation call each.
The tests failed their expected HTTP 403 assertions.

A third regression enabled the global research flag.
The runtime eligibility adapter returned true without checking an approved study or consent.
It failed the expected false assertion.

These probes used disposable test data. They did not export production records or contact a model provider.

## Changes

- `app/services/access.py` now uses active assignments from `RoleAssignmentService`, filtered to `ScopedRole.RESEARCH`.
  Ordinary analytics policy remains unchanged.
- `app/services/research/governance.py` supplies a closed production approval gate.
  It has no environment switch that can grant study or participant approval.
- `app/api/routes/research_exports.py` checks that gate after course permission and before preparing an export.
- `app/services/feedback/runtime.py` requires governance approval as well as the research flag.
- `app/worker.py` installs a disabled baseline pass and limits built-in outbox processing to continuation.
- The terminal integration worker and repository support filtering claims and exhausted-claim recovery by integration type.
  Research rows cannot block eligible continuation rows or be finalised by that filtered pass.

Backend paths above are relative to `src-main/backend`.
Existing isolated export and browser fixtures explicitly override the gate for synthetic studies.
Those overrides exercise export mechanics. They do not approve production access.
The generic research components remain available for isolated tests and later governed integration.

## Verification

- Focused backend checks: 90 passed.
- Full backend suite: 727 passed, including migration tests.
  Service coverage was 85.20%, above the 80% gate.
- Ruff lint and format: passed across 307 Python files.
- OpenAPI and frontend contract drift checks: passed. No contract regeneration was needed.
- Relevant browser regressions: 27 passed in the combined four-browser run.
  One Firefox export case timed out during browser-context teardown.
  Its isolated rerun passed without changing code, assertions, or timeouts.
- Locked dependency check: passed with `uv lock --check --offline` and a temporary cache.
- `git diff --check`: passed.

`test_research_access_boundary.py` covers ordinary educator/admin denial, missing grants, assessor-only grants,
revoked or expired grants, future grants, inactive accounts, and course scope.
A valid research grant reaches the closed approval gate but never export preparation.
Grant revocation leaves ordinary analytics access unchanged.

The production worker tests seed legacy research pairs and pending or exhausted research outbox rows.
They compare complete stored rows before and after repeated worker passes.
No baseline context, generator, or judge is invoked.
Teaching continuation still completes once with the research flag either on or off.

The mounted MVP learning loop runs under both flag settings.
It preserves course access, material access, feedback, replay, progress, and user isolation.
It creates continuation intents without research rows or research intents.
Task 4's mounted denial and durable assessment regression tests are included in the focused suite.

Commands from `src-main/backend` used `APP_ENV=test`, a disposable database,
a test-only pseudonym secret, and a unique pytest base directory.

```powershell
.venv/Scripts/python.exe -m pytest tests/test_research_access_boundary.py tests/test_research_export_api.py tests/test_research_export.py tests/test_terminal_integration_outbox.py tests/test_mvp_learning_loop.py tests/test_database_worker.py tests/test_person4_e2e.py tests/test_learner_evaluation_boundary.py --basetemp $task5Temp -q --tb=short
.venv/Scripts/python.exe -m pytest --basetemp $task5Temp --cov=app.services --cov-report=term --cov-fail-under=80 -q --tb=short
.venv/Scripts/ruff.exe check .
.venv/Scripts/ruff.exe format --check .
.venv/Scripts/python.exe scripts/export_openapi.py --check
.venv/Scripts/python.exe scripts/generate_frontend_contracts.py --check
```

Browser checks use installed Node 22.23.2 from `src-main/frontend`:

```powershell
node e2e/run.mjs person4.e2e.ts assessed-reads.e2e.ts
node e2e/run.mjs person4.e2e.ts --project=firefox --grep 'E2E entry'
```

Local logs are retained in ignored `.scratch/task5-verification/`.

## Standards review

The independent Standards reviewer found no violations or actionable code smells.
The review covered all production and test changes against the recorded base, including both new Python files.

## Spec review

The independent Spec reviewer found no missing or incorrect Task 5 behaviour.
The closed gate follows the immediate restriction requirement while keeping active governance deferred.
The reviewer found no Task 6 or Task 33 implementation.

Review totals: Standards 0 findings; Spec 0 findings.
Both reviews used the code-review skill and the supplied local specifications.
Both reviewers also checked this handoff and found no issues.
Suite results were recorded from the completed local checks.

## Data changes and rollback

No schema migration, backfill, data deletion, or stored-result rewrite is needed.
Research backlog stays stored for a later approved retention or recovery decision.
It must not be automatically resumed when study controls are introduced.

Discarding this local change requires restoring only its changed paths from the recorded base
and removing its added governance module, boundary test, and this handoff.
Do not reset or clean unrelated work.

An operational rollback must keep research exports and research processing blocked.
Restoring the previous analytics-based export policy or flag-only eligibility would reopen the known bypasses.
Keep baseline processing disabled and research outbox rows excluded until a reviewed replacement is ready.

## Limits and next work

- Task 33 must implement approved study scope, versioned consent, withdrawal, field approval, and participant eligibility.
  Changing the closed function to true is not a valid activation procedure.
- D-03 still controls production research assignment. Test grants do not settle that policy.
- D-08 still controls retention and destructive handling of preserved research records.
- The built-in composition is covered. Arbitrary external worker adapters remain trusted application code and need review before use.
- Teaching analytics were not redesigned. Task 34 owns broader research and learning analytics separation.
- No live research data, hosted environment, external model, or destructive operation was used.
- The full local browser suite, native Safari, and manual accessibility checks were not run.
- No frontend production source, dependency lock, or database model changed.
  Frontend unit tests and fresh dependency audits were not repeated for this backend restriction.
- The merged Task 4 CI remains failing on the recorded browser cases. No Task 5 remote CI exists.
- These checks do not establish pilot readiness or approve study recruitment.
