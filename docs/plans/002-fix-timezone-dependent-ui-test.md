# 002: Fix timezone-dependent attempt-history UI test

Status: proposed

Owner: Codex

Created: 2026-08-14

Target branch: `codex/fix-ui-timezone-test`

## Outcome

The frontend unit/accessibility job passes in GitHub Actions and on developer machines in different
time zones while preserving the current user-facing behaviour: attempt timestamps are rendered in
the viewer's local time with the `en-AU` locale and retain the exact UTC timestamp in the semantic
HTML `datetime` attribute.

This plan does not introduce a product-wide timezone policy, change API timestamps, alter stored
data, or change Person A/Person B assessment behaviour.

## Source evidence

| Claim or rule | Evidence | Requirement |
| --- | --- | --- |
| The current pushed UI gate fails in one test. | GitHub Actions run `31786552556`, job `94723650210`, `Unit and accessibility tests`: `src/test/App.test.tsx > shows retained student attempt history and the latest existing feedback`; 1 failed and 58 passed. | NFR10, AC9 |
| The failure is caused by the runner timezone. | The fixture timestamp is `2026-07-26T08:30:00Z`; Ubuntu renders `26 July 2026, 8:30 am`, while line 488 expects `26 July 2026, 6:30 pm`. | NFR19, AC9 |
| The UI intentionally uses the viewer's local timezone. | `src-main/frontend/src/components/TaskView.tsx`, attempt-history `<time>` rendering calls `Date.toLocaleString('en-AU', { dateStyle: 'medium', timeStyle: 'short' })` without a `timeZone` override. | NFR19 |
| The assertion predates the Person B merge. | The same hard-coded expectation exists at baseline commit `52d4582`, and GitHub run `31773752771` failed the same frontend job. | NFR10 |
| CI's authoritative frontend commands are known. | `.github/workflows/quality.yml`, job `Frontend / Node 22`: `npm ci`, `npm run lint`, `npm test`, `npm run build`, Playwright browser installation, and `npm run test:e2e`. | NFR10, NFR18, AC9 |

## Current-state trace

1. The submissions API returns an ISO-8601 UTC `submitted_at` timestamp.
2. `TaskView` places the unchanged value in `<time dateTime={item.submitted_at}>`.
3. `TaskView` converts the timestamp to a viewer-local `en-AU` label with `toLocaleString`.
4. `App.test.tsx` supplies the UTC fixture but asserts one Australia/Sydney rendering.
5. The local Windows run passes in Australia/Sydney; the GitHub Ubuntu runner uses UTC and fails.
6. The failed unit step prevents build and browser E2E steps from running, even though lint passes.

Authentication, access checks, persistence, audit, learner data, and API contracts are unaffected.
The current behaviour is `CONFLICTING` with portable test execution because the assertion treats a
machine-local presentation as a fixed product value.

## Proposed design

Keep `TaskView` unchanged because no controlling requirement specifies a fixed timezone for attempt
history and viewer-local presentation is coherent with its existing implementation. Change only the
test fixture/assertion:

- Store the latest fixture timestamp in a named constant.
- Derive its expected display label with the same public locale/options contract used by the UI,
  allowing the runtime timezone to supply the local offset.
- Assert that the rendered `<time>` has both the environment-correct label and the exact original
  ISO timestamp in its `datetime` attribute.

This verifies both presentation and machine-readable timestamp semantics without setting CI to a
specific developer timezone or weakening the assertion to accept arbitrary text.

## Step 1: Make the attempt-history assertion timezone-independent

Files:

- `src-main/frontend/src/test/App.test.tsx`

Changes:

- [x] Reproduce the existing assertion failure under `TZ=UTC` before editing.
- [x] Name the latest submitted-at fixture value so the response and assertion use the same exact
  timestamp.
- [x] Derive the expected `en-AU` local display string from that timestamp using `dateStyle:
  'medium'` and `timeStyle: 'short'`.
- [x] Assert the rendered `<time>` contains the derived local label and preserves the exact ISO
  value in its `datetime` attribute.
- [x] Leave `TaskView`, API contracts, CI timezone, and product code unchanged.

Edge and failure cases:

- UTC must produce `26 July 2026, 8:30 am` and pass.
- Australia/Sydney must produce the applicable local value and pass, including daylight-saving
  offsets when the fixture date changes.
- The assertion must still fail if the UI renders the wrong instant or drops the semantic timestamp.
- Locale punctuation/casing remains governed by the same `en-AU` formatter contract as the UI.

**Acceptance:** With `TZ=UTC`, the named `App.test.tsx` test passes and its selected `<time>` has
`datetime="2026-07-26T08:30:00Z"`; the full App test file also passes in the normal local timezone.

Verification (2026-08-14): PASS. Before editing, Node 22.13.0/npm 10.9.0 with `TZ=UTC` reproduced
the GitHub failure as 1 failed and 14 passed: the test expected the Australia/Sydney label while
the semantic `<time datetime="2026-07-26T08:30:00Z">` correctly rendered the UTC label. After the
focused assertion change, the complete App test file reported 15 passed under UTC and 15 passed in
the normal Australia/Sydney environment. The selected element must now have both the runtime's
`en-AU` local label and the exact original ISO `datetime` attribute. The existing non-failing jsdom
canvas diagnostic remains outside this fix.

Requirements: NFR10, NFR19, AC9.

## Step 2: Verify the complete frontend gate and publish CI evidence

Files:

- `docs/plans/002-fix-timezone-dependent-ui-test.md`
- GitHub Actions evidence for the pushed fix commit

Changes:

- [x] Run frontend lint, the full unit/accessibility suite under `TZ=UTC`, and the production build
  using the repository's Node 22 toolchain.
- [x] Run the configured Playwright E2E suite if the installed browser environment remains
  available; report an environment failure as `NOT RUN`, not a pass.
- [x] Run `git diff --check` and confirm the diff contains only this plan and the focused test fix.
- [ ] Commit and push the branch only after local checks pass.
- [ ] Inspect the resulting GitHub Actions run and record whether the frontend unit, build, and
  browser steps pass; do not claim the fix complete while the current-head UI job is failing.

Edge and failure cases:

- A new failure outside the timestamp assertion is reported separately and not hidden with retries
  or relaxed expectations.
- A GitHub runner or browser installation failure remains environment evidence, not application
  success.
- CI must execute the same `npm test` command; no workflow timezone override is added.

**Acceptance:** The complete local frontend gate passes under UTC and the GitHub Actions
`Frontend / Node 22` job passes on the pushed fix commit, including unit/accessibility tests,
production build, and configured browser E2E.

Local verification (2026-08-14): PARTIAL pending current-head GitHub proof. With Node 22.13.0,
npm 10.9.0, and `TZ=UTC`, ESLint passed, all 8 Vitest files/59 tests passed, and the production
build transformed 284 modules successfully. The complete local Playwright invocation passed all
five scenarios in Chrome Stable, Edge Stable, and WebKit (15 passed) but the installed Firefox
runtime failed all five before application navigation at `browserContext.newPage` with
`Cannot read properties of undefined (reading '_page')`. A one-test Firefox rerun without `TZ`
failed identically, and a forced refresh of the exact Playwright 1.61.1 Firefox 151.0 managed
runtime did not change the pre-page failure, proving the error is independent of this timezone
assertion. This local Firefox result is an environment failure, not a product pass; the workflow's
fresh Ubuntu Playwright installation and four-browser run remain required for acceptance.

Requirements: NFR10, NFR18, NFR19, AC9.

## Full verification

From `src-main/frontend` with the Node version in `src-main/.nvmrc`:

```powershell
$env:TZ = 'UTC'
npm test -- --run src/test/App.test.tsx
npm run lint
npm test
npm run build
npm run test:e2e
Remove-Item Env:TZ
```

Repository checks:

```powershell
git diff --check
git status --short
```

After push, inspect the current-head run with `gh run view` and save the exact run/job result in
this plan. Backend, migration, contract, dependency-audit, and secret-scan jobs remain GitHub's
release authority because this test-only change does not affect their code paths.

## Migration and rollback

Not applicable. No database, API, persisted timestamp, product runtime, dependency, generated file,
or CI workflow changes. Rollback is the single test-source commit; the product behaviour is
unchanged.

## Risks and controls

| Risk | Impact | Control and proof |
| --- | --- | --- |
| The test is weakened to accept any timestamp. | A real wrong-instant regression could pass. | Assert both the formatter-derived label and the exact ISO `datetime` attribute. |
| CI is forced to Australia/Sydney. | Portability defect is hidden and other timezones remain untested. | Do not set a workflow timezone; reproduce and verify under UTC. |
| Product behaviour changes without a timezone policy. | Learners see an unexpected fixed zone. | Do not edit `TaskView`; preserve viewer-local display. |
| Locale output differs across Node/ICU versions. | A string-only assertion becomes brittle again. | Use the runtime's `en-AU` formatter and separately assert the exact semantic timestamp. |
| A broader frontend failure is mistaken for this fix. | CI remains red after a narrow local pass. | Run the complete frontend gate and inspect the current-head GitHub job. |

## Missing-data report

No product-policy decision blocks this test repair. A future product-wide decision may choose
course-local, viewer-local, or explicit-zone timestamp presentation; that decision is outside this
plan because the current failure is solely a test portability defect and the product code already
defines viewer-local behaviour.

## PR mapping

The implementation change must contain only this plan and the focused `App.test.tsx` assertion.
The handoff must cite GitHub Actions run `31786552556` as the reproduced failure, local UTC and full
frontend results, the pushed fix commit, and the current-head Actions result. No human review is
requested while the current-head frontend job is missing or failed.
