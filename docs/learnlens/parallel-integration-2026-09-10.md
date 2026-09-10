# Parallel delivery integration — 10 September 2026

Status: **PASS for the current delivered scope**. The corrected source and all
final automated receipts are recorded below. This does not approve research, AI
assessment, institutional hosting, or participant recruitment.

## Feature checklist

This checklist describes the integrated delivery. The final validation receipts
below determine its automated test status; the complete clause-by-clause record
is the [143-row requirement matrix](implementation-gap-matrix.md).

| Area | Implemented behavior | Still incomplete or unverified |
| --- | --- | --- |
| Accounts and course access | Sign-in, role/course/learner restrictions, educator and learner views | Hosted authentication/release verification |
| Sources and authoring | Versioned source evidence, recoverable material processing, outcome/assessment authoring and review restrictions | Recoverable course-configuration revisions, upload malware policy, generation across all required new task types |
| Learning work | Typed evidence, drafts/revisions, saved circuits/simulation, keyboard gate placement, explicit CX text, UTC progress | Complete per-type access-mode evidence and human accessibility trials |
| Feedback and adaptation | Bounded full practice evidence reaches actual local generator/judge adapters; validation, durable execution, saved evidence/model/continuation paths | Independent content/feedback quality ratings, representative effectiveness evidence and full operational recovery drill |
| Formal assessment | Real evaluator rules, PASS/INCOMPLETE, protected histories, hidden provisional verdicts and authorized human decisions | Known dialog-return focus race assigned to the next integration; separate evaluator approval, moderation and broader revalidation evidence |
| Research controls | Scoped consent/grants/withdrawal, restricted technical-pair export, authenticated governance writes, closed production release gate | Approved study records, complete learning instruments/UI/exports and governed activation |
| Quality and operations | Automated suites, migration/readiness checks, dependency/security gates, backup/restore fixtures and local benchmark harness | Runtime controls in the next branch batch, complete metering/budget enforcement, representative billed load/cost tests and hosted release |

Confirmed defects from this integration were repaired before the corrected full
run: readiness migration pin, practice purpose/input loss, benchmark typed
submissions, circuit keyboard/text controls, governance rate-limit registration
and the legacy/rollback test fixtures. Failures and successful reruns are retained
below; a completed owner task alone was not treated as proof.

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
typed episode evidence. The corrected lifecycle and real-route regression are
integrated in the owned benchmark commits be3e92a, 9239dc1 and 0bbf95e.

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
material standards defect. The final adapter receipt records 54 focused passes,
35 successful real local HTTP calls, three submissions, three feedback workflows
and three model snapshots. Both actual local generator/judge inputs retain the
episode evidence. Six usage rows have unknown actual AUD cost, and no human
assessment decision was made. API background execution performed the observed
work; a worker heartbeat alone does not prove crash recovery.

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

## Failures found by combined validation

The first complete combined backend run at application revision 0bbf95e collected
1,473 tests: **1,464 passed, four failed and five setup errors**, with **88.71%**
service coverage against the unchanged 80% minimum. Its original XML, coverage,
command and log are preserved under `.tmp-integration-20260910/first-full/`.
It is not a passing result. All its failures were diagnosed before the next run:

- Two MVP upload cases hit the Windows path limit under the long repository-local
  pytest directory. An isolated diagnostic recorded a 281-character destination
  and WinError 3; the unchanged cases both passed with a short disposable OS-temp
  path. The final runner uses a fresh short path. No upload code, assertion or
  machine registry setting was changed.
- Person4 and the browser fixture used opaque synthetic submissions with the
  legacy research repository elsewhere, but their terminal workers inherited
  the newly governed production repository. Real study/participant records are
  intentionally absent in those mechanics fixtures. Commits 0d89160 and 22670fa
  make their existing repository choice explicit at the worker seam. All
  outbox/count/role assertions remain intact, and production governance stays the
  default. The focused browser/governance batch passed 38 tests after a confirmed
  startup failure; the Person4/outbox/continuation batch passed six.
- The reminder restore test deliberately attempted a downgrade before checking
  its current-head backup. SQLite had correctly removed newer empty revision
  0045 before the populated-history guard refused 0044. Commit 076e5e8 verifies
  backup/restore first, retains the rollback-refusal assertion, and adds
  re-upgrade-to-head, schema, preserved-row and immutable-history checks. Four
  reminder/governance migration tests passed. The independent standards review
  found no weakened assertion or production change.

Separate actual-auth testing found a real Task 33 defect: the governance route
used a missing rate-limit bucket and valid authenticated/CSRF-protected writes
returned `403 rate_limit_policy_missing`. Commit 4dd7d36 registers the existing
write policy (60/minute) and adds real-cookie regressions for role/consent-owner
boundaries, 60 accepted retries then 429 with Retry-After, and actor isolation.
The focused governance/security batch passed 45 tests after reproducing the
defect. Production research remains closed. An AST inventory finds all 28 literal
route uses registered and no dynamic bucket uses. Independent review found no
remaining actionable issue in these fixes.

The corrected combined source is frozen at
`4fe8bb8184359e1fae606bc8cdd559fe54bc4760`; the final run collects 1,475 backend
tests, all of which passed in the corrected full run. A premature isolated rerun was stopped when the rate-limit defect was
confirmed; its partial receipts are retained and never counted as a pass.

The subsequent Chrome/Edge/WebKit run finished with **84 passed and nine failed**.
It found a separate test-isolation defect: the
new circuit regression submitted prerequisites and saved work for the shared demo
learner. Later Person4 navigation/keyboard and student accessibility cases then
opened the correctly advanced circuit instead of their expected first activity.
The isolated cross-file reproduction confirms that ordering, and the first full
Chrome/Edge/WebKit attempt is retained. The correction provisions a private learner
through the existing authenticated administrator and owning-educator enrolment
APIs and keeps all circuit/navigation/keyboard assertions. It changes only browser
test setup; application code and backend/unit/build inputs remain unchanged.
The corrective commit c81b027, integrated at ece4bed, passed its three-case
cross-file sequence in all four browser engines (12 checks). Eight failures in
the first complete group came from this contamination. The ninth was a WebKit
assessor-resolution timeout with an empty internal reason; its separate timing
investigation is recorded below rather than attributed to learner state.
All configured browser groups were rerun after that correction and passed. The source identity section records backend, frontend and browser-test
revisions separately.

The isolated empty-reason investigation did not establish its cause: eight
WebKit repetitions passed, and a controlled late requests/detail-response probe
retained both fields after the responses were released. Focus/input observations
showed stable textarea nodes. The initial timeout's cause remains unconfirmed.
Intermediate test-only follow-up f71b9d1 explicitly waits for dialog dismissal/focus return and
the two actual reads, and asserts both field values and the enabled resolution
button. It retains all journey assertions and the original 60-second timeout.
That additional focus assertion exposed a separate concern. Two deterministic
component cases reproduce a real focus-return race: a pending evidence read can
change the selected decision during asynchronous access checking and consume the
return-focus target before the dialog opens. Both Cancel and Confirm then fail
to return focus. Correction b0f6f12, following f71b9d1, records the target only
after the dialog opens. All 16 component tests and eight tutor/results browser
cases pass at that exact branch source; independent review cleared the change.
These commits belong to the next integration; this current source retains that known accessibility
gap, consistent with Task 39/NFR4/AT24 remaining partial. The failed first browser
attempt and separate probes are retained. None of these probes proves that the
focus race caused the earlier WebKit empty-reason timeout.

## Validation receipts

Raw logs and structured results are kept in the ignored
`.tmp-integration-20260910/` directory. Commands use the existing Python 3.11.16
environment and the Node 22.13.0 runtime selected explicitly for this repository.

- Frozen Python lock verification: passed, 69 resolved packages.
- Clean frontend lock installation: passed, Vitest 4.1.11.
- Backend lint/formatting: passed, 540 files at the corrected source freeze.
- OpenAPI and generated frontend contract drift: passed after all eight merges.
- Root launcher/checker tests: 13 top-level tests plus nine subtests passed (22 JUnit cases).
- Current documentation checker: all 143 requirements once, 903 valid local
  links/anchors and 198 source/path/named-case references. The preserved baseline
  checker also passes its historical 143 rows and 446 references.
- Manual-kit checker: links/routes/blank cases and helper syntax passed.
- Frontend lint and production build: passed; existing large-chunk advisory remains.
- Complete frontend suite after all circuit corrections: 306 passed across 84
  files, no failures or skips, in 184.63 seconds. Its tested frontend tree at
  e93842f is unchanged in the corrected source freeze.
- Fresh full and production npm audits: zero vulnerabilities.
- Isolated pip-audit of the backend environment: 67 packages, zero known vulnerabilities.
- Complete corrected backend suite: 1,475 passed, zero failures/errors/skips; 88.73% service coverage against the unchanged 80% minimum.
- Configured browser suites: 132 passed in Chrome, Edge, Firefox and WebKit, covering the main journeys, complete learning loop and misconceptions. No failures, skips or flaky results.
- Full-history secret gate: passed; zero findings and the synthetic positive control was detected and redacted. The final post-commit scan includes all reachable refs; see its structured coverage receipt.

The first backend run collected 1,438 cases but was deliberately stopped after
the readiness defect was confirmed, so that the final suite can run against the
corrected code. It is not a complete passing run. The first sandboxed frontend
build failed with native-helper `spawn EPERM`; the unchanged approved-process
rerun passed. The first isolated audit-tool bootstrap selected an unavailable
Python runtime; retry explicitly selecting the existing Python 3.11 succeeded
without changing the running backend environment.

## Remaining external evidence and next dependencies

The task ledger has **29 completed implementations, 10 partial tasks and two
remaining tasks**. The 143-row requirement matrix has **87 IMPLEMENTED, 41
PARTIAL, two MISSING and 13 UNVERIFIED**. These are different levels of scope;
neither set of counts certifies a live pilot.

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

The coordinator has assigned the [next parallel work batch](next-parallel-wave-2026-09-10.md)
through two existing tasks (Task 34A research instruments and Task 38A runtime
controls) and a Task 37 recovery subagent. Each uses its own worktree and personal
Git identity.
They remain separate from the source being validated here; branch-level results
do not count as integration. Task 34A owns the next migration, Task 38A uses
existing settings storage, and the isolated Task 37 drill completed after the central
backend suite, alongside browsers with independent data/processes and no listener.
Its seven cases passed in 45.86 seconds on its separate branch, including restored
history, source hashes and withdrawal/revocation restrictions.
Canonical ledgers and final generated-contract reconciliation remain with the
coordinator.

## Reproduction and source identity

Application/test revision: `4fe8bb8184359e1fae606bc8cdd559fe54bc4760`. Backend tree: `5313b27b04519972ea2e4f13bbced24a4a8ef9e5`. Frontend application source tree: `8be23f092b31318e83e6f6ddf37971cc245a6cb5`, unchanged from the complete frontend run at `e93842f21fbeb14d88e3a18ac132abcec9012db0`. The only later frontend change is the circuit browser regression's private learner setup; unit/build inputs remain unchanged. All browser groups are rerun at `ece4bedd41c36c7c37e89a10ce20fcd96a329f0f`. Later coordinator commits change documentation only.

The ignored `.tmp-integration-20260910/verification-summary.json` validates the final JUnit/coverage/Vitest/Playwright/audit/secret receipts before producing PASS. `final-checks.json` contains the exact backend and six browser commands and exit codes; `source-freeze.json` records source trees; `first-full/` preserves the failed complete run. The final runner uses Python 3.11.16, Node 22.13.0 and a fresh short Windows OS-temp base. It uses the clean isolated Firefox browser bundle while leaving the shared browser cache unchanged. `task35-corrected-report.json` confirms no stale fingerprint blocker while keeping expert validation UNVERIFIED and AI release PENDING.
