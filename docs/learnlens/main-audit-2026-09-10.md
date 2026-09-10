# Main implementation and test audit — 10 September 2026

## Audited revision and scope

Local `main` was fast-forwarded from `34d686f` to
`27a397a66b5fb6544ba08d9c8950fbbc8c6b4ca4` (PR #12, Tasks 25/27/29).
The working tree was clean before the update. Fetch used the repository-specific
GitHub username `jordann-trann`; the effective author identity is Jordan Tran,
`226841807+jordann-trann@users.noreply.github.com`. Global Git settings were not changed.

This audit reads the numbered [task list](../../LearnLens_Remaining_Tasks.md),
implementation and assessment requirements, approval records, delivery records,
mounted API routes, representative services and their regression tests. It runs
the configured automated suites against this revision. It does not activate a
study, deploy a service, migrate an existing learner database, or approve content.
Application source and test assertions are unchanged by this audit.

The checklist records **29 tasks with completed implementation, seven partial
tasks, and five remaining tasks**. Completion of implementation is different from
evidence of educational effectiveness or approval for a live release.
One additional functional defect was reproduced in Task 29's progress timestamps;
the task remains delivered but needs that correction.

## Fresh verification

The shipped backend suite passes, every configured browser journey has passing
evidence, and every frontend case has passed across full runs and an isolated
rerun. The frontend full-run gate remains timing-sensitive. A separate audit
probe reproduces a progress timestamp defect that the existing suite misses.

| Check | Result |
| --- | --- |
| Locked Python environment | `uv lock --check --offline` and online `uv sync --frozen --all-extras` passed; Python 3.11.16, quantum extras installed |
| Frontend dependency tree | Node 22.13.0 / npm 10.9.2; installed package versions match the lock; omitted packages are optional platform packages |
| Backend service suite and coverage | **1,268 passed; zero failures, errors or skips. Service coverage 88.54% (12,050 / 13,609 statements), above the unchanged 80% gate.** Includes all 31 `test_migrations.py` cases and the quantum extras. |
| Windows launcher tests outside the backend suite | 7 passed |
| Additional progress timestamp audit probe | Failed as expected for a reproduced defect: UTC timestamps lose their offset after SQLite reload and display ten hours early in Sydney on the audit date |
| Frontend unit/component tests | All 272 unique cases have passing evidence across runs. Default full run: 265 passed / seven timeouts. Full one-worker run: 271 passed / one timeout. The remaining pathway-editor case passed unchanged alone in 4.45 seconds. Neither full run was entirely green. |
| Existing browser suite | All 120 unique cases passed: Chrome 30, Edge 30 and WebKit 30 in the initial run; Firefox 30 after replacing its incomplete browser installation for this audit. Initial Firefox launch failures remain recorded. |
| Complete learning-loop browser suite | Four passed: Chrome, Edge, Firefox and WebKit |
| Misconception/progress browser suite | Four passed: Chrome, Edge, Firefox and WebKit |
| Additional curriculum and activity Chrome smoke journeys | Two passed, including educator pathway publication, diagnostics, scoped assessor confirmation, worker-driven suggestions, accept/defer/replace and educator override |
| Backend lint and formatting | Passed; 508 Python files already formatted |
| Frontend lint, TypeScript and production build | Passed; 837.02 kB minified main JavaScript chunk (244.33 kB gzip) triggers the size advisory |
| OpenAPI and generated frontend contract drift | Passed |
| Alembic heads | One head: `20260910_0044` |
| Python dependency audit | Passed; no known vulnerabilities reported |
| Production npm audit | Passed; zero reported vulnerabilities |
| Full npm audit | High/critical gate passed; two moderate findings affecting `vitest` and `@vitest/mocker` remain |
| Full Git-history secret scan | Failed: six synthetic test-idempotency-key matches across 181 commits; inspected in historical source, not credential leaks |
| Docker/hosted deployment | Not exercised: Docker Desktop Linux engine was unavailable; no hosted environment was tested |

All browser launches are headless and use isolated local fixture servers. Browser
tests use synthetic users, course approvals and human decisions. Playwright WebKit
does not establish native Safari support.

Configured browser coverage totals **128 unique passing journeys**, with no skipped
cases. The two additional local Chrome scripts are separate from that total.
The saved Firefox progress screenshot was also inspected: observations, uncertain
estimates, pending formal results and evidence links are visibly separated without
clipped content. This limited visual inspection is not a manual accessibility trial.

The initial sandboxed frontend launch could not spawn Vite's helper process; no
tests ran in that attempt. It was rerun with process permissions. The first
single-worker diagnostic rerun was affected by a long execution interruption:
one test reported roughly 1,665 seconds before timing out. Its three failures
and 18 passes are retained separately and are not treated as clean evidence.

The machine's default Node is 26.7.0, outside the repository's `>=22.13 <23`
requirement. This audit explicitly uses the available Node 22.13.0 runtime.
The original pinned Firefox installation cannot start because its `mozglue`
assembly is missing (confirmed by the Windows SideBySide event). All 30 Firefox
cases initially failed before opening a page. A clean copy of the same Firefox
151.0 / Playwright revision 1532 was downloaded into the audit directory and its
launch was verified. The original shared installation was not modified.

The backend run reports one Pydantic serializer warning in the existing
misconception-support fixture (`explanation_support_level` supplied as integer 5
instead of its enum). All assertions passed. Its recorded 60-minute wall time
includes the observed execution interruption and concurrent local checks; it is
not a runtime latency or load measurement.

The first sandboxed Gitleaks invocation stopped reading Git history early despite
returning exit code zero. Its apparent clean result is invalid. The complete
rerun scanned 181 commits and is the result reported above. No history was
rewritten and no scanner rule or finding was suppressed.

## Implemented features and evidence

The table maps implementation to the 41-task checklist. “Implemented” describes
the shipped behavior and test coverage; the fresh suite results above determine
whether this revision's automated checks pass.

| Task | Status | Behavior and main evidence |
| --- | --- | --- |
| 1 | Implemented | Pass rules preserve unknown/conflicting evidence under negation; `test_pass_rule_engine.py` and assessment evaluation tests. |
| 2 | Implemented | Typed evaluator rules, approval validation and human routing for unsupported criteria; rule-setting, authoring and browser setup checks. |
| 3 | Implemented | Assessed task reloads, histories and dashboards handle formal results without invented numeric marks; assessed LMS read tests and browser journey. |
| 4 | Implemented | Learner evaluation access, duplicate requests and pending-result visibility are restricted; assessment API and submission tests. |
| 5 | Implemented | Ordinary analytics access cannot export research; research needs scoped grants and the production processing gate remains closed; `test_research_access_boundary.py`. |
| 6 | Implemented | Assessor browser actions receive independent assessment fixtures; confirm, override, withhold and return journeys. |
| 7 | Implemented | Launcher starts API/frontend/worker, applies migrations and waits for readiness; seven root launcher cases and worker recovery tests. |
| 8 | Partial | Policy directions are selected; exact course/staff/source/study/retention/environment activation records still require completion. |
| 9 | Implemented | Versioned approved source passages and immutable references survive source changes; source-history and grounding tests. |
| 10 | Implemented | Interrupted material extraction/indexing can resume without publishing duplicate revisions; material-processing recovery tests. |
| 11 | Implemented | Bounded Qiskit simulation preserves settings, counts, exact probabilities, bit order and controlled failures; `test_quantum_simulation.py` and simulation evidence tests. |
| 12 | Implemented | Educator review, assessor eligibility and publication checks prevent unreviewed or invalid tasks from release; task-publication and authoring tests. |
| 13 | Implemented | Starting assessed work freezes the approved task, outcome, conditions and rules; work-start and frozen-history tests. |
| 14 | Implemented | Prediction, reasoning, circuit work, revision, reflection and fresh transfer have preserved typed responses; episode lifecycle and workspace tests. |
| 15 | Implemented | Authorized human assessors can evaluate unsupported criteria and confirm/override/withhold/return results with reasons; human-review API/UI tests. |
| 16 | Implemented | Grounded feedback obeys help and release policy, records validation/rejection, allows one regeneration and uses a safe fallback; Task 16 tests. |
| 17 | Implemented | Live interactions create scoped, ordered, replay-safe evidence; live-evidence and capture-adapter tests. |
| 18 | Implemented | Evidence produces versioned learner estimates with uncertainty, provenance and concurrency/replay controls; learner-model tests. Estimates are not validated mastery measures. |
| 19 | Implemented | Learners inspect evidence and request corrections; educators review corrections without replacing original history; learner-model API/UI tests. |
| 20 | Implemented | Preferences, access support and optional adaptation controls persist and remain separate from assessment standards; Task 20 and browser preference checks. |
| 21 | Implemented | Approved curriculum graphs and diagnostics support scoped prerequisite/practice decisions; `test_curriculum.py` and the passing authenticated Chrome publication/diagnostic journey. |
| 22 | Implemented | The worker connects accepted evidence to one model update and approved next-activity suggestion; choices, opt-out, stale approvals and restart behavior are tested in `test_activity_continuation.py`; the authenticated Chrome choice/override journey also passed. |
| 23 | Implemented | Tutor dialogue and reviewed hints survive reload, record support, and stop conceptual help at unaided transfer; tutor and browser tests. |
| 24 | Implemented | Learners see released results and preserved review/appeal history; scoped human resolution retains reasons and notices; learner-result and tutor/result journeys. |
| 25 | Implemented | A real persisted quantum loop links prediction, simulation, checked feedback, revision, reflection, learner model, next activity and human results; three connected backend cases and a dedicated four-browser suite. |
| 26 | Implemented | Reassessment uses a fresh equivalent form, preserves prior decisions and selects whole approved outcomes without averaging; reassessment and outcome-result tests. |
| 27 | Implemented | Reviewed misconception probes progress through teaching, revision, fresh evidence and uncertain/persisted/weakened/corrected reviews; support attribution, exit and recovery tests plus a dedicated browser journey. |
| 28 | Partial | Reporting, separate human queues, ownership, acknowledgement/resolution, feedback sampling and misconception escalation exist. Named operators, staffing calendars and D-09 activation records remain due. |
| 29 | Implemented; timestamp defect | Progress separates observations, support, uncertain estimates, adaptation and released results with scoped evidence links; active scores are retired after immutable legacy preservation. Existing progress and migration tests pass, but the additional probe finds incorrect local-time display. |
| 30 | Implemented | Reminder writes run outside dashboard reads; time zones, extensions, opt-out and rolling delivery guards are supported; reminders and browser deadline checks. |
| 31 | Implemented | Optional participation-based rewards do not rank learners or affect results/access; gamification tests and opt-out browser journey. |
| 32 | Partial | Study protocol and data-plan drafts exist; institutional decisions, approved instruments/fields/retention, consent records and preregistration remain outstanding. |
| 33 | Remaining | Versioned consent, withdrawal, approved-study/field enforcement and governed exports need implementation. Existing production gate returns false. |
| 34 | Remaining | Approved linked pre/post/transfer/retention and experience/reviewer study instruments and complete study exports remain to be built. Technical export helpers alone do not complete this. |
| 35 | Remaining | Expert quantum/content/feedback/evaluator validation and the separate AI-assessment release gate are missing. AI evaluator helpers are not an approved operational assessor. |
| 36 | Partial | Automated gates and portions of traceability exist; this audit refreshes evidence for the tested revision. Full requirement-row reconciliation and final validation after remaining work are still required. |
| 37 | Partial | Local access/security, durable jobs, migration guards, contention and source/database backup/restore have tests; complete release-environment/research/live-provider drills remain. |
| 38 | Remaining | Representative 50-user latency, 5–100-user scaling, live-provider configuration changes and actual per-loop AUD cost evidence are missing. |
| 39 | Partial | Automated browser, keyboard, reflow and axe coverage exist; native Safari, manual screen reader/native zoom and first-time usability trials remain. |
| 40 | Partial | Conditional-programming draft factories and 13 reuse tests exist; approved content, measured effort, independent practical verification and complete model/adaptation reuse evidence remain due. |
| 41 | Remaining | Hosted deployment validation, availability evidence, operational ownership, reviewed rollback and release handoff remain outstanding. |

## What does not currently work or is not ready

1. **P2 — Progress history displays the wrong local timestamp (Task 29).**
   A fresh synthetic assessment was saved between `03:33:20` and `03:33:21` UTC.
   After SQLite reload, `LearningProgressService` returns
   `2026-09-10T03:33:21.486860` without an offset. The progress component uses
   `new Date(value).toLocaleString()`, which treats that string as local time.
   On the verified `Australia/Sydney` runtime, the result is **3:33 am instead of
   1:33 pm**, ten hours early. This can also place an event on the wrong local day.
   The saved Firefox progress screenshot exhibits the same problem.
   Source: `src-main/backend/app/services/learning_progress.py:298`,
   `src-main/backend/app/schemas/progress.py:47`, and
   `src-main/frontend/src/features/progress/LearningProgress.tsx:11`.
   Normalize the known UTC database timestamps at the API boundary, serialize an
   explicit offset, and add a SQLite-reload/non-UTC display regression. Do not
   shift stored historical instants. The existing suite does not catch this;
   the separate in-memory audit probe does. No application fix was made during
   this read-and-test audit.
2. **Production research processing/export is intentionally unavailable.**
   `app/services/research/governance.py` returns `False`; the mounted export route
   returns `research_governance_pending` for otherwise authorized research users.
   Tests that override that gate verify export mechanics, not production readiness.
3. **Validated AI assessment suggestions are not operational.** The shipped
   assessment runtime uses approved rule criteria and human handling for other
   criteria. Expert cases, accuracy/fairness measurements and a recorded release
   decision are still needed. Human confirmation remains part of the selected policy.
4. **Full frontend runs are timing-sensitive.** Seven initial timeouts were
   observed. The affected files cover pathway authoring, the E2E harness,
   episode authoring/workspace, assessor review and deadline arrangements.
   Running the whole suite with one worker left only the pathway-editor timeout.
   That unchanged test passed alone in 4.45 seconds, close to its five-second
   limit. Its test types several fields character by character before publication
   and a failed-save retry. These results establish a reproducible suite-reliability
   problem, not a confirmed broken publication feature. All 272 cases have a
   passing result, but this is not an entirely green full-run claim.
5. **The full-history secret gate fails on six synthetic values.** These are
   test request/evaluation idempotency identifiers. They need a narrowly justified
   scanner disposition; they are not evidence of live exposed credentials.
6. **Two moderate development dependency findings remain.** The fresh npm audit
   identifies `vitest` and `@vitest/mocker` under advisory GHSA-82fw-gwwq-j7x9 and
   reports fixes available. There are no high/critical findings in that audit.
7. **Release and learning claims remain unverified.** Passing synthetic tests
   cannot establish expert-approved content, learning gains, hosted reliability,
   live-provider quality/cost, native Safari or manual accessibility.
8. **The default local tooling needs attention.** Use Node 22 for this repository,
   repair or explicitly select the clean pinned Firefox, and start Docker when
   validating the deployment package. The machine defaults to Node 26, the shared
   Firefox copy is incomplete, and the Docker engine was unavailable.

## Checklist reconciliation

- Tasks 25 and 27 are merged in `27a397a`; their numbered headings still say
  “Completed locally, uncommitted.” Treat those words as stale. Task 29 is also
  merged. The top-level implementation status table is the useful current count.
- Older task paragraphs intentionally preserve 6 September findings. For example,
  Task 33's ordinary-analytics export-bypass wording is superseded by Task 5:
  current source enforces research grants and blocks unapproved processing.
- The August gap matrix and the old 381-test snapshot in
  `docs/04-remaining-implementation-tasks.md` are historical evidence, not current
  suite results. Likewise, old references to migration head `0042` are superseded
  by the current single head `20260910_0044`.
- Task 28 no longer needs misconception integration; Task 27 supplies it. Its
  remaining gap is operational activation details.
- Task 40's statement that Task 25 is unfinished is outdated, but the other reuse
  acceptance gaps remain. This audit does not mark any human approval complete.

## Recommended remaining work

1. Fix the reproduced Task 29 timestamp defect, resolve the reproducible automation
   issues and development advisories, and
   reconcile stale checklist/traceability wording against this revision (Task 36).
   In particular, reduce incidental per-keystroke cost in the pathway publication
   test while retaining its publication/retry assertions and dedicated keyboard
   coverage; use bounded worker concurrency for repeatable local runs. The isolated
   pass does not justify declaring the existing full-run gate stable.
2. Record the concrete activation details and escalation owners (Tasks 8/28),
   and finish approval of the study protocol/data plan (Task 32).
3. Implement and test governed consent, withdrawal, field access and exports
   (Task 33), followed by the approved study instruments and linked records (34).
4. Build the expert-approved case set and measure content, feedback and evaluator
   quality, including fairness and false-pass/false-incomplete behavior (35).
5. Finish full-system security/restart/restore drills (37) and then measure actual
   provider latency, scale, runtime reconfiguration and cost (38). The checklist
   requires 50-user p95 targets and an average external LLM cost at most AUD 0.10
   per complete loop; local templates do not supply those measurements.
6. Run native Safari/manual accessibility and first-time learner/educator trials
   (39), and obtain independent evidence for the 16 developer-hour reuse target (40).
7. Validate the approved hosted package and complete the reviewed release handoff
   (41), including TLS, persistent sources/database, worker supervision, monitoring,
   backup/restore and availability evidence.

## Reproduction and retained artifacts

Raw logs and structured results are retained in `.tmp-audit-20260910/` at the
repository root. That directory is ignored by Git. Important files include
`backend-full.log`, `backend-tests.xml`, `coverage.xml`, `root-tests.xml`,
`frontend-tests.json`, `frontend-rerun.json`, `frontend-serial.json`,
`pathway-isolated.json`, browser JSON reports and artifacts,
lint/build/contract logs, dependency audit JSON, and redacted history-scan results.
The additional defect reproduction is `probe_progress_time.py`, with
`progress-time-probe.log`, `progress-time-probe-confirmed.log` and
`progress-time-display.log`. It creates only an
in-memory synthetic database and intentionally fails its timezone-preservation
assertion. It is not counted as a passing test in the shipped suite.

The backend command uses the frozen environment, a fresh short temporary root,
`--cov=app.services`, and the unchanged `--cov-fail-under=80` gate. Browser commands
are `npm run test:e2e`, `npm run test:e2e:learning-loop` and
`npm run test:e2e:misconceptions`, with headless Firefox and isolated local ports.
Root launcher tests are a separate `python -m pytest tests` run from the repository
root. No test timeout, assertion, skip or application guard was relaxed.

The additional smoke receipts are retained in
`src-main/backend/.tmp-task21/browser-1789010916566/result.json` and
`src-main/backend/.tmp-task22/browser-1789010951500/result.json`. Both record zero
axe violations and zero page errors for their tested states. Their stdout logs
are also retained as `task21-browser.log` and `task22-browser.log` in the audit root.
