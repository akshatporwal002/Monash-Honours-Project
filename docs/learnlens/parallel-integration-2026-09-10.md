# Parallel delivery integration — 10 September 2026

Status: **VALIDATION_IN_PROGRESS**. This coordinator record will be completed with
the final combined receipts before handoff. It does not approve research, AI
assessment, institutional hosting, or participant recruitment.

## Baseline and delivery inventory

The audited/fetched main baseline is
`27a397a66b5fb6544ba08d9c8950fbbc8c6b4ca4`. The integration branch is
`codex/integrate-parallel-20260910`. Fetch used the repository's personal
`jordann-trann` credential username; all integration commits use Jordan Tran
`<226841807+jordann-trann@users.noreply.github.com>`. No global Git identity was
changed. Original delivery branches and worktrees are retained.

| Delivery | Original commit | Integration scope |
| --- | --- | --- |
| Task 29 timestamps | `9f4e0c7` | Explicit UTC instants after SQLite reload and non-UTC display regressions |
| Frontend reliability | `101edcc` | Bounded test concurrency, preserved publication/retry assertions, Vitest 4.1.11 |
| Secret-scan gate | `7eea899` | Exact reviewed synthetic fingerprints, complete traversal checks, positive control |
| Task 33 governance | `6731634` | Scoped study/consent/grants/withdrawal/export controls behind the closed release gate |
| Task 35 preparation | `769b803` | Offline validation harness, 108 draft cases, reviewer/import records |
| Task 36 reconciliation | `e65853d` | Baseline mapping of all 143 requirements and 446 references |
| Task 38 preparation | `9eb6d06` | Bounded benchmark adapter and latency/cost reporting tools |
| Task 39 preparation | `1b9fe62` | Manual/native accessibility and first-time usability procedures with blank results |

All eight original deliveries merged without textual conflicts. Generated
OpenAPI/frontend contracts preserve both the progress and research additions.
The audit and assignment prompts are committed as historical context.

## Standards review

The independent standards review compared `27a397a...d30570e` against the
implementation work order, assessment requirements, approved policy selections,
and documented code conventions. It found no confirmed material standards
breach. It confirmed a stale Task 35 fingerprint for
`app/services/feedback/runtime.py` after governance integration.

The draft manifest, dependent bundle/forms, and numerical evidence were refreshed
in `0eaf467`. All 44 validation tests and 12 numerical checks passed afterward.
The runner reports 108 cases, zero approved cases, `UNVERIFIED` content/feedback
validation and `PENDING` AI assessment release; it no longer reports the stale
runtime fingerprint. These remain draft mathematical/technical checks.

## Spec review and additional real-system findings

The independent requirements review compared the same integrated revision with
the exact assignments and controlling specifications. It reproduced a Task 38
adapter defect through actual API routes and an offline worker: a plain-answer
next-activity submission was rejected because the supplied EXPLANATION task needs
typed episode evidence. The owner is adding that lifecycle and a real-route
regression rather than relying on the permissive fake transport.

The subsequent real-server checks identified two further integration issues:

- Readiness expected migration `0044` after the actual head became `0045`. The
  existing `test_readiness_migration_pin_matches_the_alembic_head` failed before
  correction. Commit `a38e6af` updates the pin; all 16 deployment/health/worker
  checks passed afterward.
- Typed unassessed practice was stored with an assessment response marker, which
  made its feedback worker reject the missing formal assessment. Commits
  `0b43220` and `af7bfb8`, integrated together at `fa0c6ee`, distinguish new
  practice responses while retaining formal failure boundaries and historical
  response digests. The first focused suite passed 114 cases; the final focused
  suite passed 80, including 13 actual model-input regressions.

Follow-up Spec review also demonstrated content loss after enabling practice:
an episode-only explanation/reasoning response reached the generic feedback
provider as the literal `Frozen multipart response`. FR16 requires feedback to
address reasoning and process. `af7bfb8` preserves exact typed content and episode
fields in an untrusted JSON input, within the existing 20,000-character limit.
Both actual generator and judge requests are asserted. Oversized, missing-digest,
corrupt, unavailable, unauthorized-transfer and restricted cached evidence is
withheld; stored responses and retry identity remain intact. Separate practice
prompt versions record the new instructions. The independent Spec recheck found
no remaining material defect in this correction.

Follow-up Standards review identified a subprocess cleanup timeout that could
leave the benchmark worker running. `45f43cb` adds per-process bounded cleanup
and two failure-path regressions. Its observation wrappers delegate unchanged
to the actual local adapters. The independent delta review found no remaining
material standards defect; the final real adapter receipt is still pending.

Task 39's source finding was also reproduced in Chrome. Commit `065d70a`, merged
at `c61e841`, adds keyboard target selection for H/X and explicit gate-removal
names, preserving CX operands, drag, saving, reloading, and actual simulation.
The before/after browser regression and focused component checks passed.
`0d6e1b7`, integrated at `131df17`, additionally makes live and saved CX text
explicitly name control and target; all nine focused cases passed after the two
ambiguous-order regressions failed on the prior code. Human screen-reader/native
Safari/usability evidence remains outstanding.

Because the practice fix changes validation-relevant input behavior, `0af4873`
adds the new helper, episode contracts/digest/readers and assessment context to
Task 35's mandatory fingerprints and refreshes dependent draft artifacts. All
44 tooling tests and 12 numerical checks pass. The final draft report has no
stale-artifact blocker and still has 108 draft cases, zero approved cases,
`UNVERIFIED` content/feedback validation and `PENDING` AI release.

## Validation receipts so far

Raw logs and structured results are kept in the ignored
`.tmp-integration-20260910/` directory. Commands use the existing Python 3.11.16
environment and the Node 22.13.0 runtime selected explicitly for this repository.

- Frozen Python lock verification: passed, 69 resolved packages.
- Clean frontend lock installation: passed, Vitest 4.1.11.
- Backend lint/formatting: passed, 535 files at the initial integrated revision.
- OpenAPI and generated frontend contract drift: passed after all eight merges.
- Root launcher/checker tests: 13 passed, including nine subtests.
- Traceability checker: all 143 requirements once, 446 valid repository references.
- Manual-kit checker: links/routes/blank cases and helper syntax passed.
- Frontend lint and production build: passed; existing large-chunk advisory remains.
- Complete frontend suite after circuit integration: 303 passed across 83 files,
  no failures or skips, in 156.87 seconds.
- Fresh full and production npm audits: zero vulnerabilities.
- Isolated pip-audit of the backend environment: 67 packages, zero known vulnerabilities.
- Full backend/browser and final secret-scan receipts: pending final fixes.

The first backend run collected 1,438 cases but was deliberately stopped after
the readiness defect was confirmed, so that the final suite can run against the
corrected code. It is not a complete passing run. The first sandboxed frontend
build failed with native-helper `spawn EPERM`; the unchanged approved-process
rerun passed. The first isolated audit-tool bootstrap selected an unavailable
Python runtime; retry explicitly selecting the existing Python 3.11 succeeded
without changing the running backend environment.

## Remaining external evidence and next dependencies

Task 33 implementation does not activate a study. Task 34 still needs approved
instruments and the reviewed governance contracts. Task 35 needs actual expert
ratings, approved immutable sources, model outputs, and the separate evaluator
release decision. Task 38 needs real provider/environment/budget records and a
reviewed campaign, including currently missing runtime timeout/retry/budget and
complete metering interfaces. Task 39 needs native/manual and real first-time
trials. Tasks 8/28/32/40 need their named owners, approvals, and independent reuse
evidence. Final Task 37 recovery and Task 41 hosted release follow the integrated
features and applicable approvals. These conditions are not satisfied by fixtures
or by the preparation of a test harness.
