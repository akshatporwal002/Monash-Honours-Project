# Defects, dependencies and scope of evidence

Integration follow-up, 10 September 2026: commit `065d70a` fixes T39-C1 and the
related gate-identification portion of T39-C2. The real Chrome regression proves
matching keyboard/drag placement on q1, persistence/reload, simulation, and named
removal. It is merged into the coordinator's integration branch. See the
[fix and verification record](../circuit-keyboard-accessibility-fix.md).
Follow-up commit `0d6e1b7` also makes live and saved circuit text explicitly name
the CX control and target, including reversed operands. Its normal/reversed CX,
H/X order and saved/live text regressions pass. The original findings below
describe the preparation baseline. Native assistive technology trials remain
outstanding.

## T39-C1 — keyboard placement cannot select the second wire

Source-confirmed implementation asymmetry; manual/native reproduction is still
required. Proposed severity High, or Critical if an assigned key task requires a
second-wire gate and offers no equivalent permitted response mode.

At the prepared revision, `TaskView.tsx:349` defines `addGate(gate, target = 0)`;
the palette's click handler at line 657 calls `addGate(gate)` with no target.
The drop handler at line 356 passes the chosen wire to `addGate`, and wire rows
at line 673 accept drops. Therefore H/X can be dragged onto q1 but their keyboard
add controls create them only on q0. There is no wire-selection control in that
palette. See [TaskView source](../../../src-main/frontend/src/components/TaskView.tsx).

Reproduction for a separate fix: use a synthetic two-qubit circuit task (C03).
With keyboard only activate Add H gate and try to place H on q1; inspect resulting
operation/wire. Reset the disposable circuit and drag H to q1; compare operations.
Expected: same allowed placement without dragging (FR14, AC17, WCAG 2.1.1 and
2.5.7). Actual source path: keyboard default `[0]`, drop-to-q1 `[1]`. Record real
browser/AT behaviour before classifying the user impact as reproduced.

Proposed change for coordinator/frontend owner: add an accessible target-qubit
selector or per-wire add controls that call the existing handler with the selected
target, preserve the current CX convention and all circuit validation, and add
focused keyboard equivalence coverage. No production change is included here.

## T39-C2 — inspect gate identification and CX semantics

Manual investigation candidate, not a confirmed accessibility defect. Gate removal
buttons in [TaskView](../../../src-main/frontend/src/components/TaskView.tsx) lines
680–689 contain H/X or graphical CX symbols and the same “Remove gate” title.
Check whether screen readers distinguish gate type, order and wire. Saved episode
text in [EpisodeSnapshot](../../../src-main/frontend/src/components/EpisodeSnapshot.tsx)
lines 3–6/20–22 lists targets; verify that the ordered CX operands are understandable
as control and target. Proposed follow-up if confirmed: derive explicit accessible
labels/semantic text from the same saved circuit, without revealing hidden answers.

## T39-D1 — inherited timestamp defect

Already reproduced by the main audit; not reproduced anew here. The audit records
offset-free UTC SQLite timestamps displayed as browser-local time, ten hours early
in Sydney at the audited instant. Source references:
[learning_progress.py](../../../src-main/backend/app/services/learning_progress.py)
line 298, [progress schema](../../../src-main/backend/app/schemas/progress.py) line 47,
[LearningProgress](../../../src-main/frontend/src/features/progress/LearningProgress.tsx)
line 11. Another assignment owns the fix. In S06 record expected local timestamp,
actual display, browser timezone and raw timestamp; do not adjust saved history.
Coordinator must integrate/retest before final chronological-evidence acceptance.

## External and coordinator dependencies

| Dependency | Owner role | Needed next action |
| --- | --- | --- |
| Exact integrated revision, locked runtime and final suite gates | Coordinator | Prepare supported Node/Python/dependencies and test the integrated commit; retain initial failures and final receipts. |
| Native Safari / macOS | Native tester + coordinator | Supply a Mac/local fixture or approved synthetic host, browser version and actual manual records. Playwright WebKit is insufficient. |
| Screen readers, native zoom and contrast | Accessibility reviewer | Assign human tester/tool combinations and evaluate all applicable A/AA criteria, including complete processes. |
| First-time educator/student trials | Usability lead | Resolve proposed sampling/timing/rating choices, recruit real first-time participants, record all started trials and missingness. |
| Ethics/consent/recording and retention | Study/privacy owner where applicable | Provide required approval and participant evidence arrangements before research recruitment/capture. No application research gate is enabled by this kit. |
| Exact source, outcome, access equivalence and fresh task forms | Course lead / content experts | Approve the trial inputs and their construct equivalence; fixture approvals do not activate a live course. |
| Task 35 AI criterion suggestion release | Expert validation owner | Supply separate validation/approval; human confirmation remains mandatory and operational AI suggestions stay disabled until released. |
| D-09 operational response ownership | Operations and assessor leads | Name primary/backup staff and staffed calendar; synthetic queue tests establish no service promise. |
| Release environment, live-provider and load evidence | Coordinator / operations | Run combined suites, fault drills and performance/cost campaigns after integration; not part of this assignment. |

This assignment leaves production code, browser specs/config, dependencies,
migrations, shared fixtures, the master checklist and historical audit untouched.
The original uncommitted audit was read at
`C:/Users/Jordan.Tran/Downloads/Honours Project/Monash-Honours-Project/docs/learnlens/main-audit-2026-09-10.md`.
It is not copied into this branch. The historical
[Tasks 36/37/39 note](../task-36-37-39-validation.md) records earlier automation;
it does not fill this kit's blank human-result fields.
