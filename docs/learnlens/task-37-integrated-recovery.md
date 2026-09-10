# Task 37 — integrated local recovery and restore

Status: **PASS for this synthetic local recovery slice: 7 passed in 45.86 seconds**
on 10 September 2026. This is not a hosted-release, institutional-approval, or
complete Task 37 sign-off.

Application baseline: `4fe8bb8184359e1fae606bc8cdd559fe54bc4760`.
Tested source: `e795bda6b64be581f9af625978dec49d85e79266`.
Branch: `codex/task37-integrated-recovery`.
Only this note and three new Task 37 test/helper files differ from the baseline.
Production code, migrations, shared configuration and the master ledger are unchanged.
The delivery commit updates this note after the tested source revision.

## Verified journey and fault boundary

The assignment selected the authenticated submission API, durable worker
claim/crash/restart, actual persisted results, and shipped database/source backup
interfaces. One synthetic typed assessed episode completes prediction checkpoints
and real local quantum simulations, then is accepted through the cookie/CSRF API.

Both post-acceptance background dispatches are deliberately lost. The initial
API feedback claim uses a **1 ms injected lease** to reach the crash scenario
quickly. The accepted assessment job and real worker feedback/ownership leases
use the supported **30-second setting**. No stored timestamps or counters are rewritten.
The first owned worker pauses after its durable feedback claim. The test kills
it, waits 31 real seconds, and starts another worker without a second submission POST.

The successful run verifies:

- One accepted response, workflow, feedback record, learner snapshot, progress
  receipt, next-activity suggestion, continuation job and continuation outbox.
- Three feedback execution claims: API, killed worker, replacement worker.
  The killed worker's old execution token cannot modify the completed result.
- Validated feedback, the same frozen episode and 12 preserved learning-evidence
  IDs spanning response, prediction, reasoning, explanation, reflection and transfer.
- Recovered assessment lifecycle `review_required`, with no learner result until
  the synthetic authorised assessor acts through the shipped human-review service.
- One idempotent human action, three immutable criterion decisions and one PASS
  decision. This fixture action is not real expert validation or institutional approval.
- One learning feedback-view record and one audit view record, preserved across
  repeated reads and restoration. Both API event/audit factories use private
  storage; cached audit dependencies are cleared on setup, restore and cleanup.

After human review, the existing release-context check deliberately withholds
cached assessed feedback whose saved human-action ID is stale. The expected API
state is `fallback`, while the formal result remains PASS. The test compares this
same post-review view immediately before backup and after restore, retaining the
earlier validated-recovery assertion and original persisted feedback.

Both workers stop before backup. The shipped bundle/restore interfaces verify the
database, current and historical source bytes, all-table row digests, IDs, schema
and migration head. Explicit checks cover foreign keys, assessor/evidence/view
IDs and five rejection guards: unauthorised result transitions, human-action
deletion, criterion-history edits, governance deletion and source-history edits.

The same synthetic learner/course has consent, eligibility and a research grant,
followed by withdrawal and grant revocation. All seven governance events survive
restore; access still fails with `consent_inactive` and `grant_inactive`. Learning
proceeds despite withdrawal. The production research gate stays **false**, with
zero research evaluations or research outbox entries.

## Exact final evidence

Final private base: `%LOCALAPPDATA%/Temp/ll-t37-210543-7be6ac`.
Its `recovery0` directory retains the marker, worker logs, database, uploads,
bundle and restored database. Copied receipts/manifests plus every pytest log
and JUnit report remain in the worktree's ignored `.tmp-task37-receipts/`
directory, outside pytest's private base.

| Evidence | Final value |
| --- | --- |
| Accepted response | `b4f87ee6-957e-4596-ac4d-62385baad765` |
| Workflow | `731a83ee-d250-40eb-8e17-ca2ef6a5e510` |
| Learner snapshot | `3bbbe15f-c996-5a91-b110-667e8d3322af` |
| Human decision | `7c63a564-0d45-48b9-b967-cdf452093bf4` |
| Migration head | `20260910_0045` |
| Accepted UTC | `2026-09-10T11:05:52.453893+00:00` |
| Worker claim UTC | `2026-09-10T11:05:54.342920+00:00` |
| Replacement claim UTC | `2026-09-10T11:06:27.440742+00:00` |
| Completed UTC | `2026-09-10T11:06:27.572854+00:00` |
| Bundled database SHA-256 | `fa4f7c2fbd7832e6d3bf91cd830279394219fd78f606edbc6f2fe4d2bee9737b` |
| Historical source SHA-256 | `12887ec29208bf86f4553eb060302b6effddf3e99431fda7f12c737f7f85d517` |
| Current source SHA-256 | `04ca54029cc7823ad0eee178919fbd61034986219298781671c9d49f66f54dd4` |

The [final receipt](../../.tmp-task37-receipts/task37-receipt-final.json) records
all preserved evidence, action, criterion, learning-view and audit-view IDs.
The [bundle manifest](../../.tmp-task37-receipts/task37-bundle-manifest-final.json)
records every table digest and source reference.

| Retained artifact | SHA-256 |
| --- | --- |
| [Final log](../../.tmp-task37-receipts/task37-drill-fifth.log) | `665a8ec57521c66195b6d781bf5cba9fe546b3397e6e6c3a2b6167a1ae76fea5` |
| [Final JUnit](../../.tmp-task37-receipts/task37-drill-fifth.xml) | `ac15c9594b6bcfdec3379d17ad538beac1d79c71c52250765aeec26d4d878a0e` |
| Final receipt | `1df87f9da7f45778579550ea6a49876aa7228980abfd963790fa3666acbc6f35` |
| Bundle manifest | `4d8a9ce1f79a79b5c52206db482ceac94c780084189bd0a417fa7c4fa4ec368f` |

## Environment and retained diagnostic runs

Windows AMD64; Python 3.11.16; pytest 9.1.1; FastAPI 0.140.0; SQLAlchemy 2.0.51;
Alembic 1.18.5; Qiskit 2.5.1. Execution used the root backend virtual environment
with this worktree's backend and tests explicitly on `PYTHONPATH`. Ruff lint and
format checks pass for all three new Python files. Six lightweight isolation
checks passed before worker execution (`6 passed, 1 deselected in 1.51s`).

| Run/source | Result | Finding |
| --- | --- | --- |
| 1 / `c85b77b` | 6 passed, 1 failed; 90.97 s | Fixture left the API assessment claim at its normal 300 s lease and its executor on a separate default factory. Feedback and continuation had recovered. |
| 2 / `9fe5c1d` | 6 passed, 1 failed; 64.46 s | Fixture expected `immutable`; the correct result-transition guard requires a matching assessor review. |
| 3 / `6652da3` | 6 passed, 1 failed; 60.61 s | Fixture compared pre-review feedback to post-review feedback. Read-only inspection confirmed identical post-review views before/after restore. |
| 4 / `1497258` | 7 passed; 48.79 s | Complete journey passed; final review then tightened cached audit-factory isolation and added persisted audit-ID assertions. |
| 5 / `e795bda` | **7 passed; 45.86 s** | Final source, including private audit storage and audit-preservation assertions. |

All runs used fresh short OS-temporary paths. First/second logs and JUnit retain
their `.tmp-task37-drill-first.*` / `.tmp-task37-drill-second.*` names inside
the receipts directory; later runs use `task37-drill-third.*`, `-fourth.*`, and
`-fifth.*`. No production fix was inferred from these fixture failures.
Initial sandboxed lightweight attempts failed during pytest directory setup
because of Windows ACL handling; authorised execution outside the sandbox resolved it.

Repeat from this worktree's `src-main/backend`, using the root backend virtual
environment and a scheduled free subprocess slot:

```powershell
$task37Base = Join-Path ([IO.Path]::GetTempPath()) ('ll-t37-' + (Get-Date -Format HHmmss) + '-' + [guid]::NewGuid().ToString('N').Substring(0,6))
$env:PYTHONPATH = (Get-Location).Path + [IO.Path]::PathSeparator + (Join-Path (Get-Location).Path 'tests')
New-Item -ItemType Directory -Path ../../.tmp-task37-receipts -Force | Out-Null
python -m pytest tests/test_task37_integrated_recovery.py -q -p no:cacheprovider --basetemp=$task37Base --junitxml=../../.tmp-task37-receipts/task37-repeat.xml 2>&1 | Tee-Object -FilePath ../../.tmp-task37-receipts/task37-repeat.log
```

## Isolation and limits

FastAPI's TestClient uses origin `http://127.0.0.1:4710` without opening a network
listener. Workers use shipped local adapters, empty provider keys, an unusable
loopback provider endpoint, private uploads, synthetic accounts and fresh
process-local session/pseudonym secrets. Only owned process handles are stopped.
Cleanup attempts every process/log, with bounded terminate/kill fallback.

This is one synthetic local crash/restart/restore scenario on the frozen
application revision, separate from the central full-suite run. It does not
establish live-provider recovery, hosted TLS/availability, workload capacity,
manual/native browser readiness, institutional approval or release authority.
This task has not merged or pushed its branch.

A backup created before a later withdrawal cannot know that future event.
Operational restoration must reconcile authoritative later governance records
before research use. This drill preserves withdrawal/revocation already present
in the backed-up state; it does not reconstruct unknown future decisions.
