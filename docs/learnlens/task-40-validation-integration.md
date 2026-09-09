# Task 40 and Tasks 36/37/39 integration

9 September 2026. Integrated sequentially onto fetched `origin/main` at
`1f39448e022fc6e37d062950e7dd99e0faf40809`:

- `jordan/task40-conditional-reuse-isolated`, delivery `b3164a8`, merge `ecd6a1d`.
- `jordan/validation-36-37-39-20260909`, nine commits from `7427a1e` to `f1b01eb`.

All three worktrees were clean before integration. Existing ignored scratch files,
environments and other worktrees were preserved. No stash, reset, clean or force push
was used. Authentication verified `jordann-trann` and repository push permission;
author and committer were Jordan Tran, `226841807+jordann-trann@users.noreply.github.com`.
Global Git settings were unchanged.

## Review and compatibility

Separate standards and specification reviews found no blocking findings. Both
features merged automatically, preserving the task-list additions and both changes
to `api.ts`. The preference write allowlist matches the published closed schema;
the newer support-preference endpoint still shares the protected revision history.
Task 40 remains a draft content factory using existing authoring/evidence/assessment
contracts. Neither feature changes migrations, dependencies or generated contracts.
Migration head remains `20260909_0042`.

Tasks 21 and 22 were already merged on the fetched remote: `5a25ae4` and `8602fb3`
are ancestors of `1f39448`. Their earlier implementation handoffs are historical;
[the main integration record](task-22-main-integration.md) describes current storage
and migration compatibility. The remaining-task summary now reflects that state.

## Validation scope

Reused verified broad results for unchanged code from the three delivery records:
[Task 40](task-40-conditional-programming.md),
[validation batch](task-36-37-39-validation.md), and
[main integration](task-22-main-integration.md). These contain actual failures and
successful reruns, not claims of single clean full-suite executions. Backend service
coverage in those runs was 85%, 87.50% and 87.66%, respectively (required: 80%).
The dependency locks are identical to fetched main; its verified Python and npm
audit results are reused. Two moderate development advisories remain, with no
production or high/critical findings in those audit receipts.

New integration checks target changed dependencies rather than repeating full suites.
Raw local logs are under `src-main/backend/.tmp-i/`, excluded from commits.

- Task 40: all 13 cases passed against current main. Two earlier launches failed
  on temporary-directory setup/access; creating the parent and running outside the
  Windows sandbox resolved them. All 13 were rerun, with no test changes.
- Frontend: all 31 targeted tests in eight files passed, including course persistence,
  both preference interfaces, curriculum/activity controls and assessor validation.
- Browser: all 12 preference/accessibility journeys passed across Chrome, Edge,
  headless Firefox and Playwright WebKit, using isolated ports 4473/4480.
- Ruff lint and formatting (483 files), Python lock check, OpenAPI/generated contract
  drift, frontend lint/type checking and production build passed.
- Both feature commit ranges passed Gitleaks without suppressions.
- Backend integration: all 136 cases passed in 480.13 seconds. This includes all
  assessment-job recovery and migration cases plus shared preference history,
  learner preferences, activity continuation, curriculum diagnostics and episode
  lifecycle checks. No application assertion failed and no tests were weakened.
  Together with Task 40's 13 cases, 149 backend cases were freshly verified.

## Remaining acceptance

Tasks 36, 37, 39 and 40 remain partial. Approved sources/criteria, independent
verification and measured effort for Task 40, complete-system/research and live-provider
drills, native Safari, manual accessibility/zoom and first-time usability trials remain
open. This integration does not constitute deployment, study approval or independent
human validation. Existing large frontend chunks and the historical synthetic-key
secret-scan findings recorded in the batch handoff remain disclosed; no scanner rules
or history were changed. Review also noticed pre-existing duplicate `task-response`
IDs in `TaskView.tsx`; that unrelated accessibility issue remains open.
