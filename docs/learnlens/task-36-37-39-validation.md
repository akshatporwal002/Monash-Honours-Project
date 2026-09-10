# Tasks 36, 37 and 39: validation batch

Date: 9 September 2026. All three tasks remain partial.

## Isolation and boundaries

Tested baseline: `e3ce194`. Tasks 21, 22 and 40 are excluded from these implementation changes.

## Gaps, changes and evidence

Existing coverage already exercises feedback-worker termination after API acceptance,
material-processing termination, duplicate claims, provider errors, scoped access and source
backup restoration. The batch adds distinct formal-assessment boundaries rather than copying
those scenarios.

`src-main/backend/tests/test_assessment_evaluation_jobs.py` now covers:

- A subprocess is killed only after its formal-assessment claim commits. An injected clock
  expires the lease without rewriting history; the recovery worker creates one decision and
  a second recovery pass finds no work. Acceptance here uses the existing persisted assessment
  fixture, not a new HTTP submission or the complete adaptive worker.
- Timeout and malformed evaluator evidence cause a scheduled retry, no partial result and no
  response change; recovery with a valid evaluator creates one decision and criterion record.
- A real SQLite writer lock prevents a claim without consuming an attempt; recovery succeeds
  after release. A separate lock after decision commit prevents job completion, then recovery
  reuses the exact original decision and criterion IDs.
- A migrated database containing the recovered assessment is bundled and restored into a new
  directory. Response text/digest, decision ID, completed job, foreign keys and the immutable
  decision guard survive. Existing backup tests separately exercise current/historical uploads,
  corruption and path boundaries.

Confirmed UI defects and fixes:

- Failed preference loads displayed an endless loading message in both the page and dashboard
  summary. They now expose an alert and keyboard retry on the page; focus moves to Presentation pace after successful retry.
- Preference save calls included read-only fields and were rejected by the closed API schema.
  The shared API method serializes exactly the eight writable fields, covering both preference
  editors. The component assertion now checks the exact outgoing contract.
- Login overflowed at 320 CSS pixels with enlarged text. Responsive padding, intrinsic sizing
  and text wrapping keep fields/actions inside the viewport.

`accessibility-interactions.e2e.ts` asserts keyboard tab order, native required-field focus,
login error announcement, preference load failure/retry/focus and real API save, 320px reflow,
200% CSS text enlargement on login, and zero WCAG-tagged axe violations in the tested states.
CSS text enlargement is not native browser zoom or a screen-reader trial. Existing role-route
and assessor keyboard checks remain regression evidence. The browser runner, proxy and fixture
URLs now share optional `QUANTUMLEARN_E2E_API_PORT` and `QUANTUMLEARN_E2E_WEB_PORT` values;
default ports remain unchanged. This batch uses 4380 and 4373, separate databases and output folders.

The existing assessor reason-validation test reproducibly timed out when isolated: it grouped
five independent dialogs under one default test deadline. It is now five separate cases, each
with fresh fixtures and the same disabled/enabled/cleared-reason and cancellation assertions.
The timeout is unchanged.

## Validation record

The code commits are listed below; documentation records the results without changing application behavior.

| Commit | Change |
| --- | --- |
| `7427a1e` | Assessment interruption, provider faults, real contention and restore coverage |
| `a18b4a2` | Preference error/save fixes, login reflow and browser coverage/port isolation |
| `4957998` | Require the exact restored append-only guard error |
| `64d1a2e` | Restore preference spies between cases |
| `4445c13` | Isolate the five assessor validation journeys |
| `d53fa5d` | Compare reflow with the actual layout viewport, including scrollbar space |
| `dc6a7d0` | Include shared browser URL configuration in type checking |
| `d5d90b3` | Isolate course-editor spies and use paste in the persistence scenario |

| Check | Result and scope |
| --- | --- |
| Added recovery cases | All 5 passed together on committed code; all 17 assessment-job cases also passed in broad regression. |
| Backend regression/coverage | 1,173 unique cases have passing results across the broad run and focused reruns. The broad run recorded 1,147 passes, 8 failures and 18 setup errors; all 26 affected cases then passed with the 5 added recovery cases under a short temporary root (31/31). Combined service coverage: 87.50%, above the 80% gate. |
| Frontend regression | 255 cases executed in the first run: 248 passed, 7 failed; one additional file could not start its worker. Focused reruns covered all failed/unstarted files and changed preference cases. The final logical set contains 260 cases in 77 files, including the four extra independently isolated assessor cases and the previously unstarted ErrorState case. |
| Frontend reruns | All 24 targeted cases have passing focused results: 23 passed together, then the remaining course-editor case and its companion passed after the persistence-test input/spying correction. No assertion or timeout was relaxed. |
| Browsers | 116 unique journeys have passing results: 29 Chrome, 29 Edge, 29 Firefox and 29 Playwright WebKit. This includes all 8 new accessibility cases (two journeys per browser). |
| Formatting/lint/contracts/build | Ruff lint and format passed (459 Python files); OpenAPI and generated frontend contracts are current. Frontend lint, type checking and production build passed after adding the shared URL file to the config project. The build retains the existing chunk-size advisory. |
| Migration head | One head: `20260909_0039`. All 31 cases in `test_migrations.py` passed within backend regression. |
| Dependencies | Python lock verified and audit found no known vulnerabilities. npm production audit: zero; full tree: two moderate development advisories (`@vitest/mocker` and dependent `vitest`, GHSA-82fw-gwwq-j7x9), no high/critical findings. |
| Secrets | Implementation-branch scan found no secrets. The full 167-commit history scan flagged six older synthetic test-fixture idempotency keys. No scanner rules or history were suppressed or rewritten. |

Execution qualifications:

- Existing frontend timeouts and one worker-start failure were retained in the raw log, not counted as passes.
  The assessor loop also timed out when isolated; separating independent cases fixed it at the
  same timeout. Course persistence also timed out on rerun; using one user paste preserves its
  value/reload/delete assertions without measuring each keystroke. Dedicated keyboard tests still
  exercise real tab/arrow/Enter interactions.
- The headed Firefox run lost browser control during clicks, including a closed-browser error.
  Its artifacts were retained. All Firefox journeys and the remaining WebKit project then passed
  using `QUANTUMLEARN_FIREFOX_HEADLESS=1`; Chrome/Edge results came from the completed first run.
- The 26 broad-run failures/errors were in upload, material recovery, grounding, source-history
  and canonical-loop cases. A controlled long-root probe reproduced `WinError 3` at the
  immutable-source file move; all 26 unchanged cases passed under `.tmp-v/r2`. The first
  short-root launch failed before fixture setup because its parent directory had not yet been
  created; that setup was corrected and the failed log retained. Machine settings and source
  storage assertions remain unchanged. This is not validation of arbitrary Windows path lengths.

## Integration and remaining acceptance

Task 36 still needs every expanded FR/PD/BP/NFR/AC/AT row reconciled and combined validation after
outstanding features. Task 37 still needs complete-system adaptation/research, live-provider,
termination and release-environment security/restore drills. Task 39 still needs native Safari,
manual screen-reader and browser zoom checks, usability averaging at least 7/10, five first-time
educator trials within 20 minutes and at least 80% first-time learner completion within 15 minutes.
No study validity, live approval, manual accessibility or full-system completion is claimed.
