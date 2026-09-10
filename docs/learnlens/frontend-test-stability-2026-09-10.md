# Frontend test stability and development dependency patch — 10 September 2026

## Outcome

Tested baseline: `27a397a66b5fb6544ba08d9c8950fbbc8c6b4ca4`, identical to the audited main commit.

Both final complete frontend runs passed all 272 tests across 81 files with zero
skips. Lint, TypeScript/production build, full and production dependency audits,
16 browser smoke cases and the separate pathway browser journey passed.

The pathway publication/retry test now pastes fixture prose through user-event while
retaining title typing and adding a keyboard focus assertion. This reduces repeated
React form renders and user-event timer turns. Publication, error recovery and retry
remain real UI actions against the existing mocked HTTP boundary. The test additionally
checks every retained text field after failure and the complete ordered publication
payload, including support, diagnostic conditions and prerequisite links.

Vitest's default worker pool is capped at two. No timeout, retry policy, test selection,
isolation setting, accessibility assertion or product implementation was relaxed.

The direct Vitest minimum changes from `^4.1.10` to `^4.1.11`. The lockfile changes only
Vitest and its seven matching internal packages to 4.1.11; all other package records,
including optional platform packages, are preserved.

## Requirements and existing behaviour preserved

This addresses the frontend portion of Task 36 / NFR10 (reliable configured checks)
and NFR15 (development dependency findings). It preserves FR10 pathway ordering,
publication approval, NFR23 draft recovery, and existing NFR4 / AC17 keyboard and
accessibility coverage. It does not declare the broader release requirements complete.

The [baseline audit](main-audit-2026-09-10.md) records the original suite failures.
The [implementation decisions](implementation-decisions.md) also recommend bounded local test concurrency.

Owned changes are the pathway test, `vite.config.ts`, frontend `package.json` and
`package-lock.json`, and this note. Progress feature code/tests, backend source,
CI/launcher tooling, the master task list and historical audit are untouched.
No data migration or product behaviour change is involved.

## Diagnosis

The fresh original-lockfile default run reproduced the failure: 271 passed and the
pathway case timed out at 5,025.54 ms (81 files, 272 tests, 55.92 seconds total).
The same unchanged test passed alone at 3,900.22 ms. The audit had already recorded
seven default-run timeouts and one one-worker timeout, with an isolated pathway pass
at about 4.45 seconds. Neither audited full run was green.

Ranked hypotheses were per-keystroke fixture entry, worker contention, and an unresolved
request/state leak. Changing only the incidental text entry on Vitest 4.1.10 reduced
the isolated case to 1,505.35 ms, about 61% less test time, with the original publication
and retry assertions intact. The title still used `user.type`; other inputs used
`user.click` then `user.paste`. Each original text change reconstructed the controlled
pathway form and step arrays; hundreds of simulated key events were unnecessary for
the publication/retry behaviour under test.

The audit's concurrency comparison and fresh suite timings support limiting
concurrent jsdom/React workloads. Two workers
retain file isolation and useful parallel execution. Other audited cases keep all
their keyboard, focus, axe, failed-save and state-transition assertions unchanged.
There is no evidence here of a broken publication endpoint or unresolved request leak.
These elapsed times describe this local validation, not application performance.

All seven historically timed-out cases remain in the full suite:

| Case | Fresh baseline (ms) | Final run 1 (ms) | Final run 2 (ms) |
| --- | ---: | ---: | ---: |
| Pathway publication and failed-save retry | 5,026 timeout | 1,559 | 1,691 |
| E2E feedback/analytics harness | 2,401 | 1,750 | 1,882 |
| Episode authoring keyboard controls | 2,748 | 1,929 | 2,157 |
| Episode workspace keyboard controls | 2,338 | 1,719 | 1,792 |
| Assessor review focus containment / axe | 2,077 | 1,880 | 1,669 |
| Assessor review failed-save draft/filter retention | 2,094 | 1,963 | 1,539 |
| Deadline arrangement retry / stale history | 3,414 | 2,111 | 1,981 |

## Advisory and lockfile

Verified on 10 September 2026 against the
[maintainer advisory](https://github.com/vitest-dev/vitest/security/advisories/GHSA-82fw-gwwq-j7x9),
[reviewed advisory](https://github.com/advisories/GHSA-82fw-gwwq-j7x9) and
[4.1.11 release](https://github.com/vitest-dev/vitest/releases/tag/v4.1.11).
GHSA-82fw-gwwq-j7x9 / CVE-2026-84373 affects redirect mock file reads in the
development mocker. The first fixed stable release is 4.1.11 for both `vitest` and
`@vitest/mocker`. Its npm metadata accepts Node 22 and the existing Vite 8 dependency.
The application does not gain a production runtime dependency from this update.

Two npm 10.9.2 update attempts failed internally in Arborist's peer resolution with
`Cannot read properties of null (reading 'edgesOut')`; neither changed the manifests.
npm 11.6.2 successfully generated patched package records. Its unrelated
peer metadata changes, tinyrainbow update and platform-package pruning were excluded:
only its eight registry-generated Vitest package records were retained in the original
lockfile, and the direct range was set to `^4.1.11`. No integrity value was invented,
or peer dependency bypass used.

A clean `npm ci` using the original npm 10.9.2 installed 394 packages, audited 395,
and reported zero vulnerabilities. The lockfile SHA-256 before and after installation
was `51be622c882805056cf296f1a4878c77ccb15552b8fba68882d16f855d534e48`.

## Verification

All commands run from `src-main/frontend`, with Node 22.13.0 on `PATH`:

```powershell
node --version   # v22.13.0
npm.cmd --version # 10.9.2
```

Output was captured with `2>&1 | Tee-Object <log>` and the native exit code preserved. Reporter
options only save evidence; full runs do not override the committed worker limit.

| Attempt / exact command (excluding output capture) | Result |
| --- | --- |
| `npm.cmd ci --cache ../../.tmp-validation/npm-cache` (baseline) | Passed: 394 installed, 395 audited; two moderate findings |
| `npm.cmd test -- --reporter=default --reporter=json --outputFile=../../.tmp-validation/baseline-full.json` | **Failed:** 271 passed, one pathway timeout; 55.92 s |
| `npm.cmd test -- src/test/PathwayEditor.test.tsx --maxWorkers=1 --reporter=default --reporter=json --outputFile=../../.tmp-validation/baseline-pathway.json` | Passed unchanged: 1 test; 3.90 s test / 6.36 s run |
| `npm.cmd test -- src/test/PathwayEditor.test.tsx --maxWorkers=1 --reporter=default --reporter=json --outputFile=../../.tmp-validation/paste-pathway.json` | Passed with fixture-entry change only: 1 test; 1.51 s test / 4.26 s run |
| `npm.cmd install --save-dev 'vitest@^4.1.11' --cache ../../.tmp-validation/npm-cache` | **Failed:** npm 10.9.2 internal `edgesOut` error |
| `npm.cmd install --package-lock-only --save-dev vitest@4.1.11 --save-prefix='^' --prefer-dedupe --cache ../../.tmp-validation/npm-cache` | **Failed:** same npm 10.9.2 internal error |
| `npm.cmd exec --yes --cache ../../.tmp-validation/npm-cache --package=npm@11.6.2 -- npm install --package-lock-only --save-dev vitest@4.1.11 --save-prefix='^' --prefer-dedupe --cache ../../.tmp-validation/npm-cache` | Passed; generated package records minimised as described above |
| `npm.cmd ci --cache ../../.tmp-validation/npm-cache` (patched) | Passed: clean install, unchanged lock hash, zero findings |
| `npm.cmd test -- --reporter=default --reporter=json --outputFile=../../.tmp-validation/frontend-full-1.json` | Passed: all 272 tests / 81 files, zero skips, 135.46 s; pathway 1.56 s |
| `npm.cmd test -- --reporter=default --reporter=json --outputFile=../../.tmp-validation/frontend-full-2.json` | Passed again: all 272 tests / 81 files, zero skips, 164.38 s; pathway 1.69 s |
| `npm.cmd audit --json --cache ../../.tmp-validation/npm-cache` | Passed: zero findings at every severity |
| `npm.cmd audit --omit=dev --json --cache ../../.tmp-validation/npm-cache` | Passed: zero production findings |
| `npm.cmd ls vitest @vitest/mocker vite --all` | Passed: Vitest/mocker 4.1.11, Vite remains 8.1.3 and deduped |
| `npm.cmd run lint` | Passed: ESLint, zero errors/warnings |
| `npm.cmd run build` | Passed: `tsc -b && vite build`; Vite 8.1.3, 2,319 modules; existing 837.02 kB / 244.33 kB gzip main chunk advisory |

The two full runs were sequential and used the same source and lockfile. Lint and
build overlapped the later, smaller tests of the second run. No failed test was rerun
selectively to substitute for either complete green result. Bounding workers trades
full-suite elapsed time for interaction deadline margin; two runs demonstrate local
stability rather than guaranteeing timing on every host or under arbitrary load.

Browser checks used the existing locked Python environment for dependencies, with
`PYTHONPATH` pointing to the backend being tested so the isolated fixtures exercised
its source. All browsers were headless. Setup:

```powershell
$env:QUANTUMLEARN_BACKEND_PYTHON=(Resolve-Path '../backend/.venv/Scripts/python.exe').Path
$env:PYTHONPATH=(Resolve-Path '..\backend').Path
$env:QUANTUMLEARN_E2E_API_PORT='4280'
$env:QUANTUMLEARN_E2E_WEB_PORT='4273'
$env:QUANTUMLEARN_FIREFOX_HEADLESS='1'
$env:PLAYWRIGHT_JSON_OUTPUT_NAME=(Join-Path (Resolve-Path '..\..\.tmp-validation').Path 'browser-smoke.json')
npm.cmd run test:e2e -- --project=chrome-stable --project=webkit e2e/assessment-setup.e2e.ts e2e/assessment-review.e2e.ts e2e/accessibility-interactions.e2e.ts --reporter=list,json
```

Result: **16 passed, zero failed, flaky or skipped**, 79.11 seconds. This covers
rules/human assessment publication, confirm/override/withhold/return review actions,
keyboard focus, axe, reflow, login validation and preference-load recovery. The runner
also rebuilt the E2E bundle and migrated a fresh synthetic database to `20260910_0044`.

The separate existing pathway smoke script used its own fixture ports 8171/5271:

```powershell
$env:TASK21_BROWSER='chrome'
$env:TASK21_PUBLISH='1'
node e2e/task21-curriculum.local.mjs
```

Result: **passed**, including educator UI publication, diagnostic save/reload,
assessor confirmation, approved practice access and optional guidance fading;
zero axe violations and zero page errors. The 390px screenshot was inspected and
shows the pathway and saved diagnostic in a contained single-column layout.
Neither browser attempt failed or needed a retry.

## Open items and limits

These checks do not validate the separate progress timestamp repair, backend regression, live providers,
hosted deployment, native Safari, manual screen readers or user trials.
The full browser matrix, including Edge and Firefox, was not rerun in this batch;
the smoke selection is appropriate to a development-only Vitest patch and test changes.

The existing unit suite emits jsdom canvas-not-implemented messages, React `act`
warnings, and controlled/uncontrolled Select warnings. They are retained rather than
suppressed. The build's existing chunk-size advisory is recorded with the final checks.
