# Durable worker startup and readiness

Date: 2026-09-06

## Scope and base

Task 7 starts and manages the API, frontend, and existing durable worker.
It requires actual readiness and recovery of accepted work after a worker restart.

The supplied starting state was checked before editing and had changed.
The original checkout was clean on `main`, with no separate Task 6 worktree or uncommitted patch.
Task 5 and Task 6 were already merged and pushed.

- Exact Task 7 base: `5fb436f2f9ad77f8cd7f94ee029b6daa1c03412d`.
- Task 6 commit: `a6e659af29f865bb654ad5fbeff3652a226f3afd`.
- Task 6 merge: PR #6, included in the base.
- Task 7 branch: `feat/task-7-durable-worker-readiness`.
- Isolated worktree: `C:/Users/Arv/Documents/GitHub/Monash-Honours-Project/.scratch/task7-worktree`.
- Original checkout: `C:/Users/Arv/Documents/GitHub/Monash-Honours-Project`.

Remote `main` matched the base through `git ls-remote`.
[CI run 34034261696](https://github.com/akshatporwal002/Monash-Honours-Project/actions/runs/34034261696) completed successfully for that exact commit.
That result describes the base, not the uncommitted Task 7 changes.
The initial sandbox blocked remote access. The same checks succeeded with approved access.

No Task 6 patch transfer was needed because the verified base already includes it.
Fresh Task 7 checks use the isolated checkout with that combined source.
The original branch, index, and files remain untouched.
Local Git exclude entries hide the nested worktree and raw test logs from status output.

## Shared contract and ownership

Three fresh agents received separate briefs and exclusive file ownership.
The coordinator established these rules before implementation:

- Launch API, frontend, and worker with matching backend settings.
- Require `/ready`, including the durable heartbeat, before reporting readiness.
- Bound setup and startup waits and return useful, sanitized failures.
- Keep helper windows hidden and stop only owned processes.
- Preserve singleton ownership, claim expiry, replay, and fencing rules.
- Preserve research restrictions and withheld learner results.
- Keep Task 8 policy work and Task 22 adaptation out of scope.

The launcher agent owns the PowerShell entry point and supervisor helpers.
The backend agent owns template compatibility and focused backend checks.
The acceptance agent owns process recovery, launcher lifecycle tests, and operations guidance.
The coordinator owns combined verification and this handoff.

## Reproduction

The old launcher starts only API and frontend terminals, then probes `/health`.
It neither starts the durable worker nor cleans up its processes after startup failure.

A fresh Alembic-migrated disposable database reproduced the readiness gap.
The mounted health route returned HTTP 200 while readiness returned HTTP 503.
Only the worker check was `not_ready`; the database and migration checks passed.
The probe did not use a live database or a model provider.

Raw evidence is under `.scratch/task7-verification/` in this worktree.
`request.txt` preserves the task request, and `backend-absent-worker.log` records the probe.

## Changes

`start-quantumlearn.ps1` finds the required tools and invokes `scripts/quantumlearn_launcher.py`.
The supervisor starts hidden processes inside a Windows Job Object.
It assigns each child before that child can run or create descendants.
Closing the job terminates its process tree, including descendants whose direct parent has exited.
Cleanup uses owned handles, without searching for process names or killing port owners.

The launcher checks ports before setup and again before starting services.
Setup has one shared deadline, and readiness has a separate deadline.
Slow HTTP responses cannot extend the readiness deadline indefinitely.
The API must return a valid `/ready` response with every required check ready.
The frontend must also respond, and every owned service must still be running.
The supervisor remains active until Ctrl+C, a stop file, or a service exit.

API and worker load the same environment from the same backend directory.
The existing `quantumlearn-worker` console entry starts the worker.
The launcher respects a configured API prefix and leaves existing environment files unchanged.
New environment files come from the repository templates.
The backend template now declares `local` and `local-default` explicitly.
Stored administrator provider and model choices still take precedence.

Errors identify the failed setup phase, service, port, or readiness check.
Child output is discarded because raw errors can include secrets or protected learning data.
Worker startup hints identify adapter settings and a possible fresh singleton lease.

## Verification

The real PowerShell entry-point smoke test used a new disposable database.
All six readiness checks returned ready before the launcher announced success.
A stop-file request ended the launcher with exit code 0.
Ports 8000 and 5173 closed, and a separate sentinel process remained alive.

Seven Windows launcher tests passed against real child processes.
They cover port conflicts, explicit stop, service failure, unavailable readiness, supervisor death,
setup timeout, and a slow HTTP response that must respect the deadline.
The supervisor-death test also checks a grandchild process.

The recovery test submits once through the mounted LMS route.
It defers the initial API execution, then pauses a real worker after a durable claim.
A second worker must reject the fresh singleton owner.
The test kills the first worker and waits for real ownership and claim expiry.
It restarts through the console entry's import path and requires one completed workflow and feedback record.
An old execution token must fail its fenced write, and replay must not start another workflow.
Research rows must remain absent.

Initial recovery probes found three test-fixture errors, retained in the raw logs:
an unsupported module invocation, missing source context, and an incorrect research enum name.
These were corrected without changing production worker, readiness, or lease code.
The template regression also needed the existing required setting-description field.

The full backend suite passed all 735 tests in 675.96 seconds.
Service coverage was 85.35%, above the 80% gate.
This includes the actual worker interruption/restart test, migrations, research restrictions, and withheld learner-result checks.
The sole warning was a denied write to pytest's optional node-ID cache.
There were no failed tests or fixture setup errors in the final run.

The Linux frontend check passed all 178 tests across 52 files in 81.07 seconds.
Its lint, type check, and production build also passed.
It used the exact 223 tracked frontend files from this checkout, with a fresh locked install.
The source archive SHA-256 is `0a063da822424cc036a22021ba9f19c43815395db83d77f10ba668f035a1a4f4`.
The disposable image was `node:22.23.2-bookworm-slim`, digest `sha256:83f487e0a63425e5b4d146fb5e5be574bcbe1b7b843d3ebafdd95eaf7767a7e5`.
The container used no Windows timer adjustment and was removed after exit.
Its script, source archive, and log remain under the evidence directory.

The first complete browser run reported 70 passed and two Firefox failures.
One failure reported a browser-context shutdown protocol error.
All 18 Firefox checks passed in a separate fresh run, including both earlier failures.
The final complete four-browser run passed all 72 tests in 2.4 minutes.
It used the existing headless Firefox option and no timer preload.
No browser test, worker count, assertion, or timeout changed.
No earlier Task 6 test total is reused as fresh evidence.

Backend Ruff and formatting passed across 312 Python files.
The launcher helper and root tests also passed Ruff and formatting with the backend configuration.
OpenAPI and frontend contract drift checks passed without regeneration.
The frozen lock check passed with a writable local cache.
The final seven launcher checks passed in 4.39 seconds after formatting.
The backend dependency audit found no known vulnerabilities, with the editable application excluded as in CI.
The full npm dependency audit reported zero vulnerabilities.
Gitleaks found no leaks in the Task 7 patch, including added files.

| Check | Evidence file |
| --- | --- |
| Full backend, coverage, and worker recovery | `backend-full-normal-user.log` |
| Frontend lint, 178 tests, type check, and build | `frontend-container.log` |
| Seven Windows lifecycle tests | `launcher-final.log` |
| Real PowerShell startup and shutdown | `launcher-real-smoke.log`, `launcher-real-result-final.log` |
| Backend formatting and lint | `backend-format.log`, `backend-ruff.log` |
| Helper formatting and lint | `root-format-final.log`, `root-ruff-final.log` |
| Contract drift | `openapi.log`, `frontend-contracts.log` |
| Frozen lock | `lock-rerun.log` |
| Initial browser run and Firefox rerun | `browser-full.log`, `browser-firefox-rerun.log` |
| Final complete four-browser run | `browser-full-final.log` |
| Dependency audits | `pip-audit.log`, `npm-audit.log` |
| Secret scan of the delivery patch | `secret-scan-final.log` |

All filenames in this table are relative to `.scratch/task7-verification/`.

### Windows validation environment

The first backend run could not access the shared `pytest-of-Arv` directory.
It was stopped and restarted with a fresh task-owned `--basetemp` path.
A later sandbox run was stopped because of slow execution, then repeated under the normal user.
The test database remained disposable in each run.

The initial frontend run reported 166 passed and 12 failed, mainly from timeouts.
Serial execution, a thread pool, and an isolated normal-user run also hit timeouts.
The installed package versions matched the earlier successful Task 6 environment.
A direct probe found that 100 zero-delay Node timers took about 1,500 ms.
With a process-scoped timer and power-throttling adjustment, that probe took about 145 ms.

The temporary `timer-preload.cjs` calls `timeBeginPeriod(1)` and disables execution-speed
and timer-resolution throttling for that Node process. It pairs the timer request with `timeEndPeriod(1)` on exit.
This uses Windows' documented [process power-throttling controls](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-setprocessinformation).
Koffi 3.2.1 supplies the calls from an ignored validation-only directory.
No project dependency, system-wide power plan, test assertion, or test timeout changed.
The same process-scoped execution-speed setting was applied to the owned pytest processes.

The preload, install log, timing probes, and failed runs remain in `.scratch/task7-verification/`.
The adjusted Windows frontend run still hit timeouts and was stopped.
The successful full frontend result comes from the disposable Linux container, not that Windows run.
Windows frontend unit-test reliability remains an environment limit outside this launcher change.

### Repeatable commands

Use the locked Python 3.11 environment and Node 22.
The local Node installation used for these checks was 22.23.2.
On Windows, invoke npm's CLI with that Node executable when `npm.cmd` belongs to another Node installation.
Set `UV_CACHE_DIR` to a writable task-local directory if the default cache is unavailable.

From `src-main/backend`:

```powershell
uv sync --frozen --all-extras
$env:APP_ENV = 'test'
$env:DATABASE_URL = 'sqlite:///./task7-tests-unused.db'
$env:LEARNING_EVENT_PSEUDONYM_SECRET = 'task7-tests-only-pseudonym-secret-32-bytes-minimum'
.venv/Scripts/ruff.exe check .
.venv/Scripts/ruff.exe format --check .
.venv/Scripts/python.exe -m pytest --basetemp=../../.scratch/task7-verification/full-pytest-normal-user --cov=app.services --cov-report=term-missing --cov-fail-under=80
.venv/Scripts/python.exe scripts/export_openapi.py --check
.venv/Scripts/python.exe scripts/generate_frontend_contracts.py --check
uv lock --check --offline
```

From the worktree root:

```powershell
src-main/backend/.venv/Scripts/python.exe -m pytest tests/test_task7_launcher.py -q
src-main/backend/.venv/Scripts/ruff.exe check --config src-main/backend/pyproject.toml scripts tests
src-main/backend/.venv/Scripts/ruff.exe format --check --config src-main/backend/pyproject.toml scripts tests
```

From `src-main/frontend`, using Node 22:

```powershell
npm ci --audit=false
npm run lint
npm test -- --maxWorkers=1
npm run build
$env:QUANTUMLEARN_FIREFOX_HEADLESS = '1'
node e2e/run.mjs
```

For the adjusted Windows frontend run, `NODE_OPTIONS` preloads the retained `timer-preload.cjs` by absolute path.
That setting applies only to the validation command and its Node child processes.
Use a new disposable `--basetemp` directory when repeating pytest checks.

## Independent reviews

The code-review skill ran separate Standards and Spec agents with fresh contexts.
Both reviewed all nine tracked and untracked delivery files against the exact recorded base.
They found zero source or scope findings.
They also checked the operations guide, environment limits, and scoped rollback instructions.
Both reviewers confirmed the final backend, frontend, browser, launcher, and smoke-test evidence.
Standards: zero open findings. Spec: zero open findings.
Their final reports are `standards-review.txt` and `spec-review.txt` in the evidence directory.

## Boundaries and rollback

Research exports and research processing remain restricted by Task 5.
Pending learner-result policy still withholds formal result details.
No policy decision, assessment rule, migration, API contract, or stored result changed.
Task 8 and Task 22 remain outside this change.

Shutdown abandons active work through process termination and leaves durable claims intact.
A forced stop can leave a fresh heartbeat until `WORKER_STALE_SECONDS` expires.
With default settings, wait up to 120 seconds before replacing the worker.
Job claims follow their own lease expiry, normally 300 seconds.
Do not edit heartbeat rows, claim tokens, or timestamps to force recovery.

Rollback means restoring the Task 7 launcher and backend template paths from the recorded base,
removing only its added helper and test files, and reverting its operations and handoff documentation.
Review the path list before removing files. Do not reset or clean the checkout.
No database rollback is needed for this change.
Restoring the old launcher also restores its known missing-worker readiness gap.

The implementation handoff left these changes uncommitted for review.
The user then authorised committing, pushing, and merging Task 7 into `main`.
Deployment, live database operations, and the next numbered task remain outside this delivery.

A nine-file patch and SHA-256 file manifest are retained with the raw evidence.
The patch includes new files without staging or commits.
`git apply --reverse --check` verifies that it matches the reviewable worktree.
