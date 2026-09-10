# Task 25: complete quantum learning loop

Local implementation on 9 September 2026, based on main `34d686f`.
Local verification finished on 10 September 2026. Tasks 25, 27 and 29 share one delivery branch.

## Outcome

The connected journey exposed a continuation defect. Prediction checkpoints were
saved before submission, so they had no response-version ID. The continuation
filter only loaded evidence with that ID. It also excluded transfer observations.

Continuation now includes the exact prediction checkpoints named by the frozen
response and its transfer evidence. It checks learner, course, outcome, task and
work-start scope. Other saved predictions stay outside that response's model update.
The model rule version is now `continuation-observations.v2`.

These observations remain uncertain. They cannot establish mastery or determine
a formal result. Existing snapshots and workflow receipts are preserved.
No database migration or public API change is needed.

The task workspace also had two elements named `task-response`. Its response link
now has one focus target, verified in the connected browser journey.

The real human-assessed journey exposed another defect. Criteria requiring an
approved human evaluator produced technical-fault reports. These non-retryable
review requests now reach the assessor queue as `HUMAN_EVALUATION_REQUIRED`.
Actual processing failures and exhausted worker leases retain technical routing.
Existing reports and decisions remain unchanged; fenced retries create no duplicate cases.

## Connected checks

`tests/test_complete_learning_loop.py` exercises the real persisted services:

- Reviewed synthetic sources, an approved outcome and human-assessed criteria.
- Prediction before results, single-H simulation and a fresh X,H,H circuit.
- Saved simulation references, checked feedback, linked revision and reflection.
- Versioned learner snapshots and an accepted next activity from the approved pathway.
- Hidden results before human review, correct assessor routing and confirmed binary results.
- Replayed submissions and human actions without duplicate records.

The recovery case starts a real worker subprocess. It kills that process only after
the model receipt commits and before a suggestion is saved. A new worker reclaims
the expired leases and reuses that exact snapshot. It completes one suggestion.
The test advances an injected clock; it does not rewrite accepted history.

`e2e/learning-loop.e2e.ts` covers the connected learner and assessor UI. Each browser
gets new synthetic users, a course, source reviews, criteria and pathway records.
No response, feedback, model or assessment decision is prebuilt. The isolated server
uses ordinary authentication, CSRF, the shipped local providers and database worker.
It does not install application dependency overrides.

## Run the checks

From `src-main/backend`, using the installed locked Python environment:

```powershell
$env:APP_ENV = 'test'
$env:LEARNING_EVENT_PSEUDONYM_SECRET = 'task25-synthetic-pseudonym-secret-32-bytes'
.venv/Scripts/python.exe -m pytest tests/test_complete_learning_loop.py
```

From `src-main/frontend`:

```powershell
npm.cmd run test:e2e:learning-loop
```

The browser command runs in CI as a separate step. Its synthetic server is available
only through the test launcher and binds to localhost. Existing E2E tests retain
their own server. Both commands support the shared API and web port settings.

## Verification record

- The first connected regression failed because prediction and transfer evidence
  were absent from the model receipt. The corrected continuation batch passed 20 cases.
- All three complete-loop backend cases passed, including the actual process kill.
- The incorrect human-review routing reproduced in a focused test. All 25 assessment,
  escalation and complete-loop regression checks then passed with the fix.
- Chrome, Edge, Firefox and Playwright WebKit passed the complete journey on Node 22.13.0,
  including validated feedback and the learner's explicit review acknowledgement.
- Firefox failed before opening its first page inside the sandbox, twice. The
  unchanged headless Firefox journey passed with desktop process permissions.
- Each passing browser journey had no WCAG-tagged axe violations or page errors.
- All 273 frontend tests passed on Node 22.13.0. Lint, TypeScript and the production
  build passed. The build retains its existing large-chunk advisory.
- The first full backend run had 1,238 passes and five failures, with 87.58% service
  coverage. The local environment lacked the locked `tzdata` package. Frozen sync
  restored it and aligned `httpx2` and `httpcore2` with the unchanged lock file.
  All 14 reminder, migration, route and complete-loop corrective checks passed.
- The existing browser suite had 116 passes and four deadline-flow failures from
  the same missing timezone data. All eight reminder browser checks passed after sync.
- The final four-browser rerun passed with assessor routing and cached-feedback
  withholding assertions. It also saved full-page screenshots for each browser.
- Python and production npm audits found no known vulnerabilities. The full npm
  tree retains two moderate development advisories and no high or critical findings.
  Both configured npm gates passed. Gitleaks found no secrets in the changed files.
- The final full backend run passed all 1,243 tests with 87.91% service coverage
  against the restored frozen environment. This includes migration and recovery checks.
  The reviewed transfer-fixture correction passed its three focused cases separately.
- A lock-file comparison found six stale frontend tool packages. `npm ci` restored
  the exact locked tree. Lint, build and all 273 frontend tests passed again.
- The final existing browser run passed 119 of 120 cases. The WebKit tutor/result
  journey timed out during its assessor context; it passed unchanged on a focused
  rerun, alongside the other WebKit tutor case (two passes). This remains a recorded
  intermittent browser failure, not an entirely green initial run.
- The final separate complete-loop suite passed all four browser projects against
  the restored dependencies, including the corrected fresh transfer fixture.

Initial fixture failures were corrected: a missing student profile, inherited CORS
settings, a wrong profile import and its required display name. Browser selectors
were corrected to match the current conversation and always-visible result history.
The simulation check uses a floating-point tolerance for exact statevector values.
No runtime guard, production timeout or assessment assertion was weakened.

Spec review found that the original fixture revealed its transfer answer in the
lesson and public criterion. The corrected lesson covers only single-H behavior.
General reference material is stored separately. The new X,H,H transfer requires
a fresh prediction, and its public criterion states no answer. Backend payload
and browser checks reject early prompt or solution disclosure. All three backend
cases and all four browser journeys passed after this correction.

The final learner screenshot shows feedback withheld after human confirmation.
That is the existing release check: cached pending-assessment guidance cannot remain
visible after its human-review context changes. The journey verifies validated
feedback before that change and the safe withholding afterward.

Local raw logs are under `src-main/backend/.tmp-q25/`. Browser failure and screenshot
artifacts use the existing `src-main/frontend/test-results/` folder.

## Standards review

Independent read-only review found no documented-standard violations or material
code smells. The correction review also cleared the separate lesson/source fixture
and its optional source-text argument. Review covered the complete uncommitted
Task 25 change against base `34d686f`.

## Spec review

Independent read-only review raised one P2 finding: the original fixture exposed
the transfer answer. A second review confirmed that the fresh-circuit correction
and hiding checks resolve it. No other concrete spec defect or unasked production
change was found. Test execution remains recorded separately above.

Open review findings: Standards 0; Spec 0.

## Limits and remaining work

The sources and human actions are synthetic test records. They do not supply expert
quantum validation, real course activation, study approval or a hosted release.
The shipped local feedback path does not prove live-provider quality or cost.
Native Safari and manual assistive-technology checks remain Task 39 work.
The wider fault, security and restore matrix remains Task 37 work.

The following local batch delivered Task 27's misconception cycle and Task 28's
related escalation integration. See the [Task 27 record](task-27-misconception-cycle.md)
for its separate verification and remaining activation limits.
