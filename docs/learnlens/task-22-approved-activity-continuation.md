# Task 22: approved activity continuation

This records the original implementation and local verification of Task 22.
The [integration record](task-22-main-integration.md) describes the later combined storage and migration sequence.
Task 35 operational AI assessment remains disabled.

## Technical dependencies

Continuation consumes the [Task 20 preference interface](task-20-learner-preferences.md)
and the [Task 21 approved pathway graph](task-21-curriculum-diagnostics.md).
The shared learner model also preserves Task 19 correction history.

## Behavior and eligibility

`build_offline_worker_adapters` now supplies `ApprovedActivityAdapter` for both continuation ports.
The existing worker binds it to the active database and clock. Feedback generation remains behind its existing adapters.
The ordinary terminal transaction and outbox still hand work to the continuation queue.

Only a completed `FIRST_PASS` or `SECOND_PASS` workflow with accepted feedback and a `VALID`/`PASS`
judge evaluation can update the learner model. The judge checks feedback quality, not learner success.
Safe fallback and unchecked feedback produce an explicit ineligible receipt without model inference.
Missing evidence and personalisation opt-out also avoid optional model updates.

The adapter loads response, reasoning, prediction, revision, explanation, and reflection evidence for the exact
learner, course, outcome, task, and submission. It reuses the shared model build service and Task 19 corrections.
New event occurrence remains uncertain, with uncertainty 1. It never becomes a mastery or formal result claim.
Prior evidence relations and correction review state remain linked through successor snapshots.

Selection follows the current educator-approved graph and checks actual task access and prerequisites.
Practice steps use their published `accepted_response` exit rule, without requiring a legacy numeric pass.
This is ordinary practice navigation. It grants no new diagnostic bypass and does not apply to formal assessment.
Task 21 assessor-confirmed bypass and optional fading rules remain authoritative.
The completed task and other completed activities cannot become fake next activities.

The dashboard projects durable continuation choices and honors defer and opt-out.
Before a decision exists, unlocked course navigation remains available. Numeric averages no longer rank recommendations.
Formal criteria, Bloom targets, pass rules, frozen conditions, results, supported hints, and transfer rules are unchanged.
Approved conceptual hints remain unrestricted in supported assessment. Transfer remains unaided except for approved access support.
Research participation and sensitive traits are absent from selection inputs.

## Interfaces and transactions

| Interface | Contract |
| --- | --- |
| `ProgressUpdate` | Existing workflow and scope fields plus the claim execution token. Its idempotency key must equal the workflow ID. |
| `NextTaskRequest` | Existing workflow and scope fields plus the claim execution token. |
| Next-task result | Task ID or `None`. A completed decision may explicitly contain no activity. |
| `ActivityAction` | Strict action, expected version, request key, optional allowed task ID, and bounded reason. Unknown fields are rejected. |
| `ActivityRead` | State, reason, uncertainty, evidence IDs, snapshot/rule/preference/pathway versions, options, chosen activity, and history. |

Migration `20260909_0035` adds protected progress receipts, suggestions, and choice history.
It changes only the continuation completion constraint needed for a null next activity.
Model readiness and generated API contracts use this head.

The progress transaction acquires the SQLite writer lock by updating the claimed queue row.
It checks the active token and lease before reading authoritative scope and again before committing.
The shared repository's caller-owned transaction mode prevents an internal model commit.
A workflow-keyed progress receipt and its model update commit together or both roll back.
The suggestion transaction separately fences its claim and commits one workflow-keyed decision.
A restart between these transactions reuses the model receipt. Duplicate delivery cannot create another snapshot or suggestion.

Each decision stores the trigger workflow, evidence IDs, frozen full model snapshot, rule version, preference values/version,
approved pathway version, reason, uncertainty, options, and timestamp. The progress receipt also links its own snapshot.
Choices store actor, action, selected task, reason, request key, history version, and time.
Database and ORM guards reject protected updates, deletes, and replacement inserts.

Actions acquire the course writer lock, recheck current scope and eligibility, then compare history version.
An exact request replay writes nothing. A reused key with different content or stale version returns a conflict.
Learners can accept, defer, or replace allowed options. Only the owning educator can override, with a nonblank reason.
Approval and access changes invalidate affected options. Manual choices never change assessment standards.

## Mounted experience and failure states

Routes under `/api/v1/activity-continuation` support submission lookup, workflow read, actions, and paged course-owner lists.
Reads are scoped and noncacheable. Mutations use the existing CSRF and rate guards.
SQL write failures return a retryable, sanitized error and preserve the original request key.

The learner component is mounted beside feedback in `TaskView`.
It polls while processing and provides inspect, accept, defer, replace, refresh, retry, and open-chosen-activity controls.
The course editor mounts learner decisions with educator overrides and reasons.
Both retain draft choices when a save fails. History survives reload and ordinary authentication.

Explicit states cover processing, unavailable, ineligible feedback, insufficient evidence, conflicting evidence,
no eligible activity, stale approval, and personalisation disabled. A null activity never becomes a completed-task fallback.
Saved work, required feedback, and the course workspace remain usable when optional continuation fails.

## Verification

All 1,141 backend tests are covered by the full run and corrective rerun. Service coverage is 87.23%.
The full run completed in 901.24 seconds: 1,139 passed and two failed assertions.
One failure was a missing matrix step reference. The other expected the older downgrade error wording.
Both were fixed without changing application behavior. The two affected files then passed all 20 tests in 14.12 seconds,
with coverage appended and the 80% gate passing. This records the actual run history rather than claiming one clean invocation.
The full run included all 19 Task 22 tests and all 31 migration checks.

- Final focused backend checks: 34 passed, including 19 Task 22 tests and existing LMS/learning-loop tests.
- Frontend unit and accessibility suite: 70 files, 249 tests passed.
- Existing browser regression: 84 passed across Chrome, Edge, Firefox, and WebKit.
- Final authenticated Task 22 journey: passed in all four browsers, with zero page errors and Axe violations.
- The journey uses ordinary sign-in, real API writes, migrated SQLite, the checked-feedback pipeline, and shipped worker wiring.
  It verifies accept, reload, defer, replace, educator override reason, learner history, activity navigation, and 390px reflow.
- Gitleaks scanned all 85 implementation and dependency files and found no leaks.
- Ruff check and format pass across 423 Python files. OpenAPI and generated frontend contracts are current.
- Frontend lint and production build pass. The existing large-chunk warning remains.
- Frozen Python lock/install and dependency audit pass after patching only `httpcore2` and `httpx2` from 2.9.1 to 2.12.0.
- npm audit passes the required high-severity gate. The full development tree reports two moderate Vitest-related advisories.
  The production tree reports zero vulnerabilities. No frontend package upgrades were bundled into Task 22.

Tests exercise actual persistence, duplicate delivery, retry, restart between writes, expired leases, stale workers,
concurrent delivery, concurrent conflicting choices, scope forgery, revoked access, approval changes, failed writes,
transaction rollback, opt-out, correction consumption, null activity, migration replay, and protected downgrade refusal.

## Separate self-reviews

### Standards self-review

Reviewed the Task 22 delta against repository contracts, security boundaries, and quality workflow.
Found and fixed transaction ownership, stale-worker fencing, strict action fields, and migration preflight ordering.
The additive migration rejects populated downgrade before any DDL. Shared standalone model behavior remains covered.
The dashboard retains the existing recommendation projection while using durable Task 22 decisions as authority.
No independent review is claimed.

### Spec self-review

Checked Task 22 behavior and boundaries against the implementation requirements.
Found and fixed two integration gaps: practice unlocking still read numeric grades, and the dashboard still ranked scores.
Practice navigation now uses the already-approved exit rule. The dashboard respects saved deferrals and opt-out.
Checked feedback does not establish mastery; uncertainty and existing correction review requirements remain explicit.
Task 23 and Task 35 stay outside scope. No independent review is claimed.

### Test Judge self-review

Checked whether tests prove outcomes through real writes and actual wiring rather than only injected return values.
Persistence tests use real SQLite sessions and worker passes. The populated migration test upgrades real persisted activity history.
Concurrent tests assert one durable result and a linear choice history. Browser tests use actual authentication and API services.
Failure injection proves rollback and stable retry keys. Earlier failures were fixed and their relevant suites rerun.
The full run exposed a matrix step-reference omission and an inherited downgrade-message assertion.
Both were corrected. The final 20-test rerun passed, and combined service coverage is 87.23%.
Independent review, remote CI, deployment, and pilot effectiveness are not claimed.

### Reproducible commands and local evidence

Run from `src-main/backend` with Python 3.11 and the project environment.
Set `APP_ENV=test`, a test-only pseudonym secret, and an isolated SQLite `DATABASE_URL`.
Set `PYTHONPATH` to the backend being tested if using a separate Python environment.

```text
uv lock --check
uv sync --frozen --all-extras
python -m pytest --cov=app.services --cov-report=term-missing --cov-fail-under=80 -o tmp_path_retention_policy=failed
ruff check .
ruff format --check .
python scripts/export_openapi.py --check
python scripts/generate_frontend_contracts.py --check
uv run --frozen --with pip-audit==2.9.0 pip-audit --skip-editable
```

From `src-main/frontend`, using Node 22:

```text
npm.cmd ci --audit=false
npm.cmd run lint
npm.cmd test
npm.cmd run build
npm.cmd run test:e2e
npm.cmd audit --audit-level=high
npm.cmd audit --omit=dev --audit-level=high
node e2e/task22-activity.local.mjs
```

The journey requires `QUANTUMLEARN_BACKEND_PYTHON` and accepts `TASK22_BROWSER` values
`chrome`, `edge`, `firefox`, and `webkit`. It owns ports 8172 and 5272, and stops its own helper processes.
Each run creates a fresh database, `result.json`, logs, and a mobile screenshot under backend `.tmp-task22`.
PowerShell may wrap native stderr as `NativeCommandError`; exit status and actual test/audit output determine success.

## Recovery

1. Back up the target SQLite database before applying migrations. Run Alembic upgrade to head in the normal release process.
2. Start API and worker with the same database and approved provider configuration. The offline factory is for local mode.
3. If a continuation claim expires, use the existing bounded worker retry path. Do not delete receipts or repeat submission.
4. For a failed choice save, retry its original key. For version conflict, refresh before making a new choice.
5. If approval changes, the educator must review and publish the pathway again. A new response can trigger a new decision.
6. Populated protected history cannot be downgraded in place. Use a forward fix or restore the pre-migration backup.

This is SQLite local verification. Other database engines, production provider behavior, pilot outcomes, and remote CI remain unverified.
History is retained for scoped reads; large-history performance has not been load-tested.
