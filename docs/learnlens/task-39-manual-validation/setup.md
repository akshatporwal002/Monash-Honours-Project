# Facilitator setup and reset

Run from a fresh isolated checkout of the recorded test commit. The coordinator
owns dependency installation: use its frozen Python 3.11 environment including dev
and quantum extras, Node `>=22.13 <23`, and matching frontend `node_modules` in this
checkout. Do not change packages, locks or shared runtime configuration. Record
absolute executable paths and versions. Never start against an existing learner DB.

The optional [server helper](../../../scripts/task39_manual_validation/serve.py)
uses only the standard library and existing fixture servers. It rejects a backend
`.env`, allocates scratch storage, clears live LLM credentials for its own process,
and binds localhost. Use a short checkout path on Windows: earlier audits found
immutable-source storage failures under very long paths. No dependency installation
is performed by the helper. Its API port must be free; Vite also fails on a busy
web port. Coordinate different ports for simultaneous sessions.

## Start the two terminals

Commands use PowerShell from the checkout root. Replace `python` and `node` with
the coordinator's absolute executable paths if PATH is not the supported runtime.
For macOS use the same Python and Node commands, `cd` in place of `Set-Location`,
and `export NAME=value` for the two frontend environment assignments.

Terminal A:

```powershell
python --version
python scripts/task39_manual_validation/serve.py --profile standard --api-port 4490 --web-port 4491
```

Terminal B (these commands build the existing E2E application without running tests):

```powershell
node --version
$env:QUANTUMLEARN_E2E_API_PORT = '4490'
$env:QUANTUMLEARN_E2E_WEB_PORT = '4491'
Set-Location src-main/frontend
node node_modules/vite/bin/vite.js build --config vite.e2e.config.ts
node node_modules/vite/bin/vite.js preview --config vite.e2e.config.ts
```

Check `http://127.0.0.1:4490/api/v1/health` then open
`http://127.0.0.1:4491/login`. Use `/login`, not `/e2e.html`: the latter is a
separate feedback/analytics harness. Keep the web host as `127.0.0.1` for cookies
and origin checks. Capture startup logs and source commit in the environment record.

Stop only these two terminals with Ctrl+C. Restart Terminal A for a new disposable
DB and fresh cookies (close private windows). Keep receipts before stopping: standard
DB storage is temporary; loop storage remains under this checkout's
`src-main/backend/.tmp-q25/b-*`. The helper's standard scratch is `.tmp-task39/manual-*`.
Do not run database cleanup or migrations on another checkout. No reset endpoint
edits old histories; create another fixture instead.

## Profiles and fixture receipts

`standard` reuses [browser_e2e_server.py](../../../src-main/backend/tests/browser_e2e_server.py).
It seeds reviewed demo content and exposes the following POST endpoints, without
`/api/v1` in the path. Every fixture POST creates fresh records. In Terminal C:

```powershell
$review = Invoke-RestMethod -Method Post http://127.0.0.1:4490/e2e/assessment-review-fixture
$authoring = Invoke-RestMethod -Method Post http://127.0.0.1:4490/e2e/assessment-authoring-fixture
$human = Invoke-RestMethod -Method Post http://127.0.0.1:4490/e2e/human-workflows-fixture
```

On macOS: `curl -f -X POST http://127.0.0.1:4490/e2e/assessment-review-fixture`
(repeat with the required endpoint). Give each tester the returned `student_email`,
`student_password`, `educator_email`, `educator_password`, `task_id`, `course_id`
and relevant response/attempt/decision IDs privately. Do not hard-code a generated ID.
Store the full credential receipt privately; redact passwords and cookies from defects.
Sign in as **Educator** for the returned assessor account: Assessor is a scoped
permission, not a login radio option. General Educator/Admin accounts do not imply it.

| State code | Supported starting state |
| --- | --- |
| B | Standard server; `/login` → select Student, Educator or Admin → Load demo workspace. Built-in emails are `student@quantumlearn.demo`, `educator@quantumlearn.demo`, `admin@quantumlearn.demo`; password `quantumlearn-demo`, as used by App.tsx. Demo setup is synthetic only. |
| R | A fresh `$review` receipt; one already submitted response and provisional decision. New receipt for each confirm/override/withhold/return/void branch. |
| A | A fresh `$authoring` receipt; course/outcome/task and scoped assessor for setup. |
| H | A fresh `$human` receipt; confirmed INCOMPLETE, fresh equivalent form, tutor and human queues. |
| L | Loop server and fresh learning-loop receipt, below; unstarted supported circuit episode, transfer, worker and next activity. |
| M | Loop server and misconception receipt, below; hypothesis and probe workflow. |

For L/M stop Terminal A; restart with `--profile loop` using the same reserved ports.
The frontend can stay running; discard all old browser sessions and IDs.

```powershell
python scripts/task39_manual_validation/serve.py --profile loop --api-port 4490 --web-port 4491
```

Then in Terminal C:

```powershell
$loop = Invoke-RestMethod -Method Post http://127.0.0.1:4490/e2e/learning-loop-fixture
$misconception = Invoke-RestMethod -Method Post http://127.0.0.1:4490/e2e/misconception-fixture
```

The [loop server](../../../src-main/backend/tests/learning_loop_browser_server.py)
has real authentication and a worker using offline adapters. Synthetic approvals
and fixed content do not prove expert validity. The standard server overrides the
request security guard, selected feedback/analytics access, and a research gate;
it is suitable for component/process accessibility preparation, not production
authorization, research export, live provider or security acceptance. Use L for
the persisted student feedback journey. Native testing of either remains fixture
evidence; the coordinator must repeat applicable paths on the approved release build.

## Minimal educator resource and student trial readiness

Facilitator, before participant arrival: prepare a small valid DOCX/PDF/PPTX with
selectable text using an existing office tool. Suggested synthetic content:
“Hadamard practice. A Hadamard gate applied to the zero input gives equal
measurement probabilities for zero and one. Sampled counts can vary between runs.
Two consecutive Hadamard gates restore the input state.” Record filename, byte
size and SHA-256 (`Get-FileHash -Algorithm SHA256 <path>`). This is proposed fixture
content, not an expert-approved course source. The trial owner must approve the
exact material and outcome before counted trials. Keep a harmless invalid `.txt`
file for separate negative accessibility checks; do not run that check mid-trial.

For each educator trial use a fresh standard server and a new synthetic educator
account created through Admin → Users → Add user, or the reset demo educator
if the trial owner accepts its existing demo courses. Record the choice. Leave
the target course uncreated and give the participant their account card/resource.
For each student trial use a new L receipt and the task title obtained by opening
that task in a separate facilitator-only session; confirm it is assigned and
visible on the student's dashboard without starting the participant's attempt.
Use a separate disposable rehearsal fixture to verify worker feedback. Do not
pre-submit, expose transfer answers, or change the participant's fixture to
make the timings pass. If a suitable task is not discoverable, record a setup
blocker instead of silently handing out a direct task URL during the trial.

Full browser/backend/frontend suites, load tests and shared runtime setup are
deferred to the coordinator. These launch commands are not such a suite.
