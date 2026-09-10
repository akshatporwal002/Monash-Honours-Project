# Integration verification — 10 September 2026

**Combined validation: IN_PROGRESS.** Application source is unchanged from `6d20416c6760d4841828c9e59cc74679d8ca0ae7`. Browser test source is `91237a52576cd68a1e5c3ed1b2729526ffbd3ac2`; corrected backend test source is `1afd0b192efe11e804e12ec21d80337890dd9c84`. The complete backend rerun is in progress.

**12 of 41 tasks still need work: 29 completed implementations, 11 partial and one remaining.** The [task list](../../LearnLens_Remaining_Tasks.md#concrete-work-left-after-the-local-changes) describes each remaining action. Automated results do not establish expert, institutional, participant-study or hosted-release approval.

## Implemented changes

- [Governed instruments](task-34a-governed-instruments.md): versioned draft forms/freezes, stage bindings, append-only observations and explicit missingness/attrition/deviation. Routine projections exclude restricted text. Technical-pair processing retains its original 34 fields. Production research stays closed. Sole migration/readiness head is 0046.
- [Runtime controls](task-38a-runtime-controls.md): administrator timeout and infrastructure-attempt settings, strict persisted bounds, safe partial updates and immutable policy per operation. [Retry exhaustion](task-38a-retry-exhaustion-correction.md) terminalizes due exhausted work without revoking active leases or resurrecting terminal jobs. Infrastructure retries remain separate from one quality regeneration.
- [Recovery](task-37-integrated-recovery.md): accepted-episode worker crash/restart, exactly-once records and complete database/source restore with protected histories and governance withdrawal/revocation retained.
- Assessor dialog focus is restored after late evidence/access reads. Deterministic Cancel/Confirm tests cover the race. This does not establish the cause of the older unconfirmed WebKit empty-reason timeout.
- Task 35 fingerprints cover runtime policy, transport, executor/repository/worker and task-generation runtime. Dependent draft artifacts are refreshed: **108 DRAFT, zero approved/outputs/ratings, 12/12 numerical matches, quality UNVERIFIED and AI release PENDING**.

## Executed checks

| Check | Result |
| --- | --- |
| Full frontend | 319 tests in 85 files passed; zero failed/skipped; 203.76 seconds |
| Browser main journeys | 93 Chrome/Edge/WebKit and 31 Firefox cases passed |
| Browser learning-loop journeys | 3 Chrome/Edge/WebKit and 1 Firefox cases passed |
| Browser misconception journeys | 3 Chrome/Edge/WebKit and 1 Firefox cases passed |
| Total browsers | **132 passed**, zero failed/skipped/flaky |
| Initial full backend | 1,599 passed / 8 failed; 88.93% service coverage; 2,178.27 seconds; failures corrected below |
| Corrected retirement and typed-practice tests | 17 passed in 51.60 seconds |
| Focused runtime integration | 64 passed in 66.58 seconds |
| Focused instrument/governance/security integration | 216 passed in 173.78 seconds |
| Focused migration/recovery/provenance batch | 120 passed / 4 empty-table assertion failures in 353.65 seconds; corrected assessment/migration follow-up: 18 passed in 59.80 seconds |
| Final full backend | IN_PROGRESS; 1,607 collected; unchanged 80% service-coverage gate |
| Root checks | 13 passed plus 9 subtests in 9.43 seconds |
| Frontend quality | Full ESLint, TypeScript and production build passed; focused browser-test lint/types passed after correction |
| Backend quality | Ruff check/format passed across 556 files |
| Contracts and migrations | Canonical OpenAPI/TypeScript drift checks and sole 0046 head/readiness checks passed |
| Dependencies | Python: zero known vulnerabilities in 66 third-party distributions; editable application excluded. Full/production npm audits: zero known vulnerabilities. uv lock check passed for 69 packages |
| Secret gate | At 0399ebd: 235 text commits, zero history findings; positive control detected/redacted. Final-source gate pending |
| Documentation | 143 exact requirement rows; 29/11/1 task sets; manual kit: 9 documents, 58 links, 36 routes, 27 blank human-validation cases |

The existing Vite chunk-size advisory remains. The initial backend run emitted one Pydantic warning from a synthetic invalid support-level fixture; it did not fail that test. Dependency audits are dated observations. npm audits used all 425 unchanged public-registry lock entries with a synthetic root package identity; application dependencies and lockfiles were not changed.

## Failures and corrections

1. The security merge duplicated the governance bucket key. Ruff F601 reproduced it; removing the duplicate retains one governance bucket and one instrument bucket, each 60/minute.
2. Escaped in-process feedback failures reloaded administrator policy. Two persisted scheduling regressions reproduced wrong behavior when limits changed 1→3 and 3→1. Failure recording now retains the captured policy. Both regressions passed.
3. Four older downgrade-manifest assertions counted five new empty tables after safe removal. The existing empty-extension comparison now includes those tables only when empty; populated histories and full-manifest downgrade guards remain checked. The focused assessment/migration composition passed 18 tests.
4. The first browser group mixed the current frontend with an older backend through an editable installation: 87 passed / 6 administrator failures. Pinning Python imports to the checked source fixed the mismatch. This mixed-source run is excluded from final proof.
5. The first correctly pinned group passed 92 cases and failed WebKit's assessed-read axe check with `page-has-heading-one`. The test could match a learner name on the departing dashboard before Students loaded. It now waits for the destination URL and visible Students h1 before the unchanged learner/no-Average/full-axe assertions. All 132 cases then passed.
6. The retirement round-trip test expected 0045 after upgrading to current head 0046. Only the expected final head changed; the historical rollback target 0043 and single-head assertion remain.
7. Five recording-client replacements accepted one argument after runtime added a policy argument. The typed-practice file reproduced 7 failures / 6 passes. All five adapters now match the signature. Six negative cases additionally require persisted `context_integrity_error`; this new guard failed in all six cases before correction and passed afterward, preventing an unrelated infrastructure failure from satisfying a denial test.

No application change was required for the final two test corrections. Independent standards and specification reviews found no remaining defect in these changes. No test skip, timeout increase, accessibility exclusion, coverage reduction or broad suppression was introduced.

## Reproduction and boundaries

Use Python 3.11.16, Node 22.13.0 and the committed lockfiles. Run backend tests from `src-main/backend` with APP_ENV=test, an empty LLM_API_KEY, RESEARCH_ENABLED=false and fresh temporary database/upload paths. Pin PYTHONPATH to the selected backend and tests directories when using an editable installation from another checkout.

```powershell
python -m pytest --cov=app.services --cov-report=term-missing --cov-report=xml --cov-report=json --cov-fail-under=80 -p no:cacheprovider --basetemp=<fresh-temporary-directory> --junitxml=<report-path> --tb=short
python -m ruff check .
python -m ruff format --check .
python -m scripts.export_openapi --check
python -m scripts.generate_frontend_contracts --check
```

From `src-main/frontend`, run the configured Vitest, ESLint, TypeScript and production build commands. Browser verification executes `node e2e/run.mjs` in each of three modes: main (no mode flag), `--learning-loop` and `--misconceptions`, first with Chrome/Edge/WebKit projects and then Firefox. Use fresh output/data directories, free private API/web ports and the configured browser versions. Expected inventory is 93+31+3+1+3+1=132; skipped/flaky cases do not count as passes.

Task 34 still needs approved content, user/reviewer workflows, allocation/outcomes and full approved study exports. Task 38 still needs durable metering, budget reservation/reconciliation/enforcement and an approved representative load/cost campaign. Task 37's local fixture evidence does not establish hosted/live-provider recovery. Human accessibility/usability, expert evaluation, independent reuse and hosted release remain open in the task list and requirement matrix.

The isolated import order `task_review` before the assessment package still exposes a pre-existing circular import in unchanged code. Normal API/assessment composition passes; this does not establish standalone importability. A separate repair should test both fresh-process import orders. Older audit and validation results remain scoped to their recorded sources.
