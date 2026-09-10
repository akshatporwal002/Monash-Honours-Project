# Task 39 — manual validation kit delivery

Prepared 10 September 2026. Task 39 remains partial: this delivery prepares human
validation and does not supply native Safari, manual accessibility or participant
acceptance evidence.

## Delivered files and requirement preparation

| File | Purpose |
| --- | --- |
| [README](task-39-manual-validation/README.md) | Concise tester handoff, scope and fixed acceptance targets |
| [Setup](task-39-manual-validation/setup.md) | Private ports/storage, existing fixture profiles, fresh account receipts and synthetic input preparation |
| [Role matrix](task-39-manual-validation/role-matrix.md) | 27 role cases with starting states, actions, expected results, severity and blank result/evidence fields; independent action branches |
| [Accessibility](task-39-manual-validation/accessibility.md) | Keyboard/focus, actual screen-reader speech, contrast, native 200%/400% zoom, reflow, errors and circuit equivalence; authoritative WCAG mappings |
| [Native browsers](task-39-manual-validation/native-browsers.md) | Real Safari/macOS process and test-time version recording; WebKit distinction |
| [Usability](task-39-manual-validation/usability.md) | Neutral educator/student cards, milestone timing, assistance and deviation rules, explicit proposals for unspecified design choices |
| [Blank records](task-39-manual-validation/result-templates.md) | Environment/case/defect records, first-time session sheets, five educator slots, student ledger and unfilled aggregate fields |
| [Dependencies](task-39-manual-validation/dependencies.md) | Circuit-access finding, manual investigation candidate, inherited timestamp issue and named owner roles for outstanding work |
| [serve.py](../../scripts/task39_manual_validation/serve.py) | Standard-library wrapper around existing disposable fixture servers; no dependency/config changes |
| [check_kit.py](../../scripts/task39_manual_validation/check_kit.py) | Read-only local-link, route-reference, blank-matrix and Python-syntax checks |
| This delivery note | Preparation evidence and limits |

Prepared NFR1–4/18, AC17, FR14 and AT11/24 validation procedures, with adjacent
role and assessment controls traced per case. None of those requirements is marked
complete by this preparation. Existing PASS/INCOMPLETE, human confirmation,
protected history, unrestricted supported conceptual hints and separate unaided
transfer remain unchanged. No data migration or application change was made.

## Focused verification and exact commands

Run shell commands from the repository root unless a different path is stated.
Use the installed backend Python environment:

```powershell
$python = (Resolve-Path 'src-main/backend/.venv/Scripts/python.exe').Path
& $python --version
& $python scripts/task39_manual_validation/serve.py --profile standard --api-port 4490 --web-port 4491
```

Python version: **3.11.16**. In a separate terminal, the standard profile checks:

```powershell
$ErrorActionPreference = 'Stop'
Invoke-RestMethod http://127.0.0.1:4490/api/v1/health
foreach ($kind in @('assessment-review','assessment-authoring','human-workflows')) {
  $receipt = Invoke-RestMethod -Method Post "http://127.0.0.1:4490/e2e/$kind-fixture"
  $receipt | Select-Object course_id,task_id
}
```

Passed: health returned `status=ok`; all three fixture POSTs succeeded with unique
course/task records and educator credentials. Review/human receipts also contained
student credentials; authoring correctly does not. No credentials were printed
in the retained summary.

Stop the standard-profile server with Ctrl+C before running the loop profile:

```powershell
& $python scripts/task39_manual_validation/serve.py --profile loop --api-port 4490 --web-port 4491
```

Separate terminal:

```powershell
$ErrorActionPreference = 'Stop'
Invoke-RestMethod http://127.0.0.1:4490/api/v1/health
foreach ($kind in @('learning-loop','misconception')) {
  $receipt = Invoke-RestMethod -Method Post "http://127.0.0.1:4490/e2e/$kind-fixture"
  $receipt | Select-Object course_id,task_id
}
$fixture = Invoke-RestMethod -Method Post http://127.0.0.1:4490/e2e/learning-loop-fixture
$body = @{ email=$fixture.student_email; password=$fixture.student_password } | ConvertTo-Json
$login = Invoke-RestMethod -Method Post http://127.0.0.1:4490/api/v1/auth/login -ContentType application/json -Body $body -SessionVariable task39Session
$dashboard = Invoke-RestMethod http://127.0.0.1:4490/api/v1/students/me/dashboard -WebSession $task39Session
[pscustomobject]@{
  role=$login.role
  dashboard_has_task=(($dashboard | ConvertTo-Json -Depth 15) -match [regex]::Escape($fixture.task_id))
  outcome_id_present=[bool]$fixture.outcome_id
}
```

Passed: health OK; both fixture endpoints HTTP 200; new student authentication and
dashboard HTTP 200; `role=student`, `dashboard_has_task=True`,
`outcome_id_present=True`. Loop migrations reached `20260910_0044` in a new DB.
Stop the server with Ctrl+C after checking the loop profile; exit 1 after Ctrl+C
is intentional termination, not an assertion failure. This checks setup/authentication/discoverability, not a
browser interaction, complete learning loop or usability trial.

Final static checks:

```powershell
& $python scripts/task39_manual_validation/check_kit.py
& $python -m ruff check scripts/task39_manual_validation
& $python -m ruff format --check scripts/task39_manual_validation
git diff --check
```

| Check | Final result |
| --- | --- |
| `check_kit.py` | Passed: 9 documents, 57 local links, 36 UI route references, 27 blank matrix cases and both helper syntax trees; zero errors |
| Ruff lint | All checks passed |
| Ruff format check | 2 files already formatted |
| Whitespace check | Passed; staged patch also checked before commit |

The kit checker verifies local target existence and route-path declarations;
query-dependent populated states were additionally checked against progress
components and corrected to follow generated links. It does not verify spoken
announcements or external-link availability. WCAG Recommendation and linked W3C
Understanding pages were opened with the web tool, as was Apple's current Safari
Advanced settings guide. Citations are embedded in the procedures.

## Initial failures and resolutions

- Initial sandboxed standard-server launch printed its scratch path but never
  reached readiness; health/fixture probes were connection-refused and a filesystem
  inspection reported access denied on that new private temp directory. It was
  interrupted and rerun outside the sandbox using the same isolated command.
  That launch and the loop launch passed the focused checks above. No ACL, service
  safeguard or shared runtime was changed. The exact cause of the initial stall
  was not established; it is not a clean passing launch.
- During source consistency review, draft instructions used “Create user”, “Void
  attempt” and a bare progress-record route. Corrected to Add user, Void result,
  and application-generated links with scope query parameters before delivery.
- Initial helper lint found two import-order issues and the format check identified
  both files. `& $python -m ruff check --fix scripts/task39_manual_validation` and
  `& $python -m ruff format scripts/task39_manual_validation` corrected only imports
  and formatting. The subsequent lint, format and kit checks all passed.
- The first generic Apple documentation URL returned an internal fetch error;
  the Australia-localized official guide opened successfully and is the cited link.

## Open dependencies, deferred checks and human evidence

Source inspection found a keyboard target-wire asymmetry (T39-C1) and a gate-removal/CX
speech-clarity concern (T39-C2). The kit also records the Task 29 timestamp defect.
Reproductions and subsequent implementation dependencies are described in
[dependencies](task-39-manual-validation/dependencies.md).

Full backend/frontend/multi-browser suites, coverage gates, load/fault/cost campaigns,
frontend build and native UI interaction were not run for this documentation kit.
No native Safari, manual screen-reader/contrast/zoom result, first-time participant,
expert content/AI evaluator validation, ethics approval or hosted evidence was
generated. The standard fixture's security/research overrides cannot establish
production gate behaviour. Usability owner must resolve the explicitly proposed
sample/scoring decisions, obtain applicable approvals, and supply the five educator
trials, ≥80% unaided student completion and ≥7/10 actual ratings. All human result
templates remain blank.
