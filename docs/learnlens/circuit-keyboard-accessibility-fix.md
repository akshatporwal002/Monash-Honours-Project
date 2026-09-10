# Circuit keyboard placement and gate identification fix

Date: 10 September 2026. Branch: `codex/fix-circuit-keyboard`.
Clean starting commit: `27a397a66b5fb6544ba08d9c8950fbbc8c6b4ca4` from local main.
Worktree: `C:/Users/Jordan.Tran/Downloads/Honours Project/Monash-Honours-Project/.tmp-circuit/worktree`.
The completed `codex/task39-manual-validation-kit` branch at `1b9fe624` is preserved.
The coordinator's active integration checkout was not edited. No merge, push or
GitHub access was performed. Author/committer use the personal Jordan Tran identity
`226841807+jordann-trann@users.noreply.github.com`, verified before commit; global
Git settings are unchanged.

## Outcome and cause

T39-C1 is reproduced in a real isolated Chrome journey: the existing HTML5 drag
handler saved H with `targets: [1]`, whereas keyboard activation of Add H saved
`targets: [0]`. The baseline assertion compared the actual saved circuit objects
and failed on that target. This rules out backend rejection of q1 and a storage
projection problem. The palette called `addGate(gate)` with its default target 0;
the drop handler supplied the selected wire.

The palette now offers a labelled native Target qubit for H and X selector for
all wires in the current circuit. Add buttons pass that target to the existing
handler. A restored one-qubit circuit restricts the selector to q0 and still hides
CX; larger restored circuits retain their available targets. Selection alone does
not change the circuit or saved assessment evidence.

T39-C2 affects the same removal controls. Their accessible names now identify
operation position, gate, wire and (for CX) both control/target plus the wire's
role. The existing “Remove gate” title is retained. A related restored-CX display
defect was confirmed by the regression: control symbols previously assumed q0
was always the control. Symbols now follow `operation.targets[0]`, matching the
unchanged saved operation, including legal reversed `[1, 0]` CX records.

## Changed files

| File | Change |
| --- | --- |
| [TaskView.tsx](../../src-main/frontend/src/components/TaskView.tsx) | Target selector and existing-handler argument; descriptive removal names and correct restored-CX symbols |
| [CircuitKeyboard.test.tsx](../../src-main/frontend/src/test/CircuitKeyboard.test.tsx) | Four component regressions: q1 keyboard/drag equivalence with H/X and CX/remove/clear; reversed CX identification; one-qubit restriction; four-qubit target enumeration |
| [circuit-keyboard.e2e.ts](../../src-main/frontend/e2e/circuit-keyboard.e2e.ts) | One authenticated real-browser journey against existing disposable demo services, including saved circuit comparison, reload, simulation, named removal, clear and axe |
| This delivery note | Reproduction, validation, setup failures and remaining limits |

No shared fixture, browser configuration, package/lockfile, generated contract,
backend code, migration or master checklist changed. No new dependencies.

## Preserved behaviour

- H/X still support the original drag-to-wire path. Keyboard starts with q0 and
  can select any existing wire; a selection cannot introduce a new wire.
- Add CX continues to create `[0, 1]`, independent of the H/X selector. Restored
  reversed CX remains `[1, 0]`; only its displayed symbol/name is corrected.
- Removing either CX wire button removes the same complete operation. Clear
  empties the local circuit; existing safeguards continue to disable empty-circuit
  saving and simulation. This fix does not change that pre-existing empty-draft rule.
- Existing `changeOperations` invalidates stale simulation/checkpoint references.
  Persisted drafts, actual Qiskit simulation and failure recovery remain on their
  original services. No assessment/help/transfer/evaluator policy is changed.
- Approved hints, supported work and separate unaided transfer remain governed by
  existing code; the existing episode component regressions passed unchanged.

Prepared requirement coverage: keyboard circuit equivalence under FR14/AC17/NFR4
and clearer name/role information for the affected controls. This is bounded
automated evidence; it is not a WCAG conformance or manual screen-reader claim.

## Runtime and isolation

Coordinator-supplied Node: `.tmp-task23-24/tools/node-v22.13.0-win-x64/node.exe`
under the original checkout, version **22.13.0**. Python read-only reuse:
`src-main/backend/.venv/Scripts/python.exe`, version **3.11.16**. Chrome channel:
installed Chrome **152.0.7977.83** (executable product version read after the run).
The frontend dependency source is the coordinator-approved stable tree at
`.tmp-stabilise-frontend/worktree/src-main/frontend/node_modules`, Vitest **4.1.11**.
It was copied into this worktree so Vite/Vitest caches cannot modify the shared
tree. This is not a fresh baseline-lock `npm ci` claim; both red and green used
the same approved snapshot. Integration's locked install remains coordinator work.

Copy command from the original checkout (robocopy exit 1 means files copied):

```powershell
robocopy 'C:\Users\Jordan.Tran\Downloads\Honours Project\Monash-Honours-Project\.tmp-stabilise-frontend\worktree\src-main\frontend\node_modules' 'C:\Users\Jordan.Tran\Downloads\Honours Project\Monash-Honours-Project\.tmp-circuit\worktree\src-main\frontend\node_modules' /E /NFL /NDL /NJH /NJS /R:0 /W:0
```

All following commands run from this worktree's `src-main/frontend` with its own
build outputs. Before Node commands:

```powershell
$env:PATH = 'C:\Users\Jordan.Tran\Downloads\Honours Project\Monash-Honours-Project\.tmp-task23-24\tools\node-v22.13.0-win-x64;' + $env:PATH
```

For browser commands, also set:

```powershell
$env:QUANTUMLEARN_BACKEND_PYTHON = 'C:\Users\Jordan.Tran\Downloads\Honours Project\Monash-Honours-Project\src-main\backend\.venv\Scripts\python.exe'
$env:PYTHONPATH = (Resolve-Path ../backend).Path
$env:QUANTUMLEARN_E2E_API_PORT = '4590'
$env:QUANTUMLEARN_E2E_WEB_PORT = '4591'
$env:RAG_UPLOAD_DIR = (Join-Path (Resolve-Path ../backend).Path '.tmp-circuit/uploads')
$env:LLM_API_KEY = ''
$env:RESEARCH_ENABLED = 'false'
```

The existing runner creates a fresh temporary migrated SQLite DB per invocation,
starts localhost fixture/Vite services, runs one Chrome test with one worker and
stops its processes. The test uses the built-in demo account and submits its five
prerequisite activities through supported API calls to unlock the circuit. It
does not edit shared fixture data or bypass the prerequisite rule. The standard
fixture server still has its documented synthetic security/feedback overrides;
this is not evidence of production security or live provider behaviour.

## Reproduction and verification

| Exact command (after environment above) | Result |
| --- | --- |
| `node node_modules/vitest/vitest.mjs run src/test/CircuitKeyboard.test.tsx --maxWorkers=1` before fix | 3/3 red: missing target selector, missing descriptive reversed-CX names, one-qubit selector absent. Baseline duration 5.83 s. |
| `node e2e/run.mjs circuit-keyboard.e2e.ts --project=chrome-stable --workers=1` before fix | Real API drag saved H on q1; keyboard saved H on q0. Circuit equality assertion failed; test duration 6.2 s. |
| Same browser command after fix | **1 passed**, test 8.9 s / Playwright 11.4 s. Equal saved circuits on q1, reload, actual simulation, CX `[0,1]`, named CX removal, clear/empty safeguards, zero scoped axe violations and zero page errors. |
| `node node_modules/vitest/vitest.mjs run src/test/CircuitKeyboard.test.tsx src/test/Task14EpisodeWorkspace.test.tsx src/test/App.test.tsx -t 'circuit\|simulation\|exact probabilities\|transfer\|prediction\|keyboard\|qubit\|restored' --maxWorkers=1` | **9 passed**, 18 excluded by the command's name filter; 3 files, 20.49 s. The pipes here are Markdown-escaped; use literal `|` in the shell expression. No test source was skipped or weakened. |
| `node node_modules/vitest/vitest.mjs run src/test/CircuitKeyboard.test.tsx --maxWorkers=1` after final test typing correction | **4 passed**, 6.76 s. |
| `node node_modules/eslint/bin/eslint.js src/components/TaskView.tsx src/test/CircuitKeyboard.test.tsx e2e/circuit-keyboard.e2e.ts` | Passed on final files. |
| `npm.cmd run build` | Passed TypeScript and production build after test typing correction. Main JS 837.60 kB / gzip 244.50 kB; existing chunk-size advisory remains. |
| `git diff --check` and staged equivalent | Passed. |

### Initial failures retained

1. The first browser harness incorrectly expected Save draft enabled before any
   input. It timed out. Changed only the readiness check to wait for the successful
   draft GET, preserving the application's unchanged-input safeguard.
2. The next baseline browser run failed on the absent target selector after saving
   the dragged q1 circuit. The final baseline probe used the only available
   keyboard add action and captured the stronger q0-versus-q1 payload failure.
3. The first post-fix component run passed two cases but its clear assertion tried
   to save an empty circuit. Corrected the test to verify clear empties the UI and
   leaves save/simulate disabled, while separately checking persisted nonempty
   removal. The production safeguard is unchanged.
4. The first TypeScript build rejected Playwright's `exact` option mistakenly used
   in Testing Library `getByRole` calls. Removed that unsupported option from the
   component tests; string names already match exactly. Build, four tests and lint
   then passed. No production code changed in response to that typing issue.

### Retained local artifacts

Logs reside in the worktree's parent `.tmp-circuit/`:
`.tmp-circuit-component-red.log`, `.tmp-circuit-browser-red.log` (initial harness),
`.tmp-circuit-browser-red2.log` (absent control), `.tmp-circuit-browser-red3.log`
(exact payload mismatch), `.tmp-circuit-component-green.log` (empty-save test
error), `.tmp-circuit-component-green2.log`, `.tmp-circuit-browser-green.log`,
`.tmp-circuit-existing.log`, `.tmp-circuit-focused-final.log`,
`.tmp-circuit-components-final.log`, `.tmp-circuit-build.log` (initial typing
failure), `.tmp-circuit-build-final.log` and `.tmp-circuit-lint-final.log`.
Failed browser screenshots/video/error context were copied to sibling directories
`browser-initial-harness`, `browser-red-missing-control`, `browser-red-payload`
before the next runner invocation. Final screenshot:
`src-main/frontend/test-results/playwright/circuit-keyboard.e2e.ts-ke-ab093-al-and-preserved-simulation-chrome-stable/circuit-keyboard.png`.
The final screenshot was visually inspected: target field, gate controls and clear
state are visible without overlap at the tested desktop viewport. Synthetic demo
identity may appear; no live credentials/learner data are used. No debug logging
or throwaway production instrumentation remains.

## Limits and handoff

Only Chrome was run for this change; no full frontend/backend/multi-browser suite,
load campaign, native Safari or manual assistive-technology trial. HTML5 drag is
driven by browser DataTransfer events; keyboard actions use actual key events.
Accessible names and axe do not establish actual screen-reader speech or all AA
criteria. The broader T39-C2 question about all saved circuit text remains for
the human circuit-equivalence procedures; no protected snapshot was rewritten.

The coordinator should integrate this commit and rerun its combined gates against
the final dependency lock. The earlier Task 39 kit is retained as historical
preparation; its source-only C1/C2 descriptions are superseded for these controls
by this reproduction/fix evidence, not retroactively edited. No institutional,
expert or first-time participant evidence is claimed.

## T39-C2 circuit text follow-up (after `065d70a`)

The coordinator requested the remaining text-semantic change before integration.
`EpisodeSnapshot.tsx` now uses one operation description for both the live
`EpisodeCircuitText` and saved episode `Content` renderers. The duplicated generic
formatting was the cause: it listed CX qubits without naming their roles.
Stored CX targets `[0, 1]` now read `CX, control qubit 0, target qubit 1`;
`[1, 0]` reads `CX, control qubit 1, target qubit 0`. Descriptions retain stored
operation order and the existing H/X target wording. Rendering does not alter
stored operations. No schema, backend, configuration or dependency files change.

The new `src/test/EpisodeCircuitText.test.tsx` exercises ordinary and reversed CX
with H/X before and after it, live text and both supported-prediction and saved
transfer content. It checks exact text/order, unchanged input and empty live text.
Commands below ran in `src-main/frontend` with the same Node 22.13.0 and isolated
Vitest 4.1.11 dependency snapshot described above:

```powershell
node node_modules/vitest/vitest.mjs run src/test/EpisodeCircuitText.test.tsx --maxWorkers=1
node node_modules/vitest/vitest.mjs run src/test/EpisodeCircuitText.test.tsx src/test/Task14EpisodeWorkspace.test.tsx src/test/CircuitKeyboard.test.tsx --maxWorkers=1
node node_modules/eslint/bin/eslint.js src/components/EpisodeSnapshot.tsx src/test/EpisodeCircuitText.test.tsx
```

The initial sandboxed test launch could not start Vite subprocesses (`spawn
EPERM`); it did not execute tests. The authorized retry before the fix produced
two expected failures for ambiguous ordinary/reversed CX text and one passing
empty-circuit check (2.86 s). After the fix, all nine tests in the three focused
files passed (16.99 s). Changed-file ESLint passed with no output. Receipts in the
worktree parent `.tmp-circuit/`: `.tmp-circuit-text-red.log` (startup limitation),
`.tmp-circuit-text-red-retry.log`, `.tmp-circuit-text-green.log`, and
`.tmp-circuit-text-lint.log`.

This supersedes the earlier deferral of the two text renderers' CX role wording.
Manual screen-reader speech, native-browser and human usability trials remain
pending; these component checks do not establish those outcomes. The coordinator
will rerun the full frontend and browser suite centrally after integration.
