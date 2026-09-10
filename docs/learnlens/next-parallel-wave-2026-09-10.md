# Next parallel work after the delivery integration

Task 34A and Task 38A start from application freeze
`0bbf95e25e4124f7484944c9493d1165d7b8023b`; the recovery drill starts from its
corrected successor `4fe8bb8184359e1fae606bc8cdd559fe54bc4760`.
They are a new work batch, separate
from the eight original deliveries and corrections being verified in the
[integration report](parallel-integration-2026-09-10.md). Assignment does not mean
implementation, approval or integration is complete.

| Slice | Existing task | Branch | Owned scope | Dependency boundary |
| --- | --- | --- | --- | --- |
| Task 34A | Implement research governance | `codex/task34-governed-instruments` | Versioned research instrument/forms, research-only responses and stage links, deviations/missingness/attrition, scoped services/exports and tests | Sole migration author in this batch; synthetic draft instruments and closed production gate; approved content and UI follow later |
| Task 38A | Build load cost harness | `codex/task38-runtime-controls` | Administrator timeout/retry settings and UI, existing SystemSetting persistence, request/worker propagation, benchmark settings probe and focused tests | No migration; keep infrastructure retries distinct from the fixed quality-regeneration policy; no budget-enforcement claim |
| Task 37 | Coordinator recovery subagent | `codex/task37-integrated-recovery` | Isolated typed-workflow crash/restart and database/source/history restore drill | No migration or shared-data writes; execute after the central backend run, alongside browsers with separate data and no listener |

The coordinator owns integration, final generated-contract reconciliation, and
the canonical task/requirement ledgers. Every slice uses an isolated worktree,
the personal `jordann-trann` Git identity, focused verification and a separate
commit handoff. Original delivery branches remain available. None of these
assignments authorizes a push, paid provider run, participant study or production
research activation.

## Branch handoffs and review status

- **Task 34A:** owner handoff is c627c7a (POST streaming body replay correction)
  followed by 3a0aecd (instrument foundation), based on 0bbf95e. The owner reports
  135 focused tests, 18 changed Python files lint/format clean and branch-local
  OpenAPI/TypeScript checks passing. Independent requirements review found that
  formal-stage missingness/attrition/deviation records incorrectly required an
  existing submission. Commit 3702df8 fixes that case while keeping actual
  response observations linked and optional-link ownership/course/consent-time
  checks intact. Six absence cases failed before correction; the corrected
  instrument/API batch passed 67 tests. Independent review cleared this finding.
  Migration 0046 adds five append-only research tables with no learner backfill.
  The original 34 technical-pair processing fields remain separate. Forms are
  synthetic drafts, and the production release gate stays closed. UI, approved
  instruments, reviewer packets/ratings, allocation, outcomes and full research
  exports remain later work. This handoff is not integrated into the current
  validation candidate. A follow-up readiness check found its pin still at 0045
  despite migration 0046. Commit 686e300 corrects the pin; the existing pin test
  failed first, then all 16 health/deployment/worker checks passed. The reviewed
  branch is queued with migration and readiness aligned at 0046.
- **Task 38A:** backend handoff 27087ff has 55 focused passes. Independent review
  reproduced stranded assessment, continuation and terminal-outbox retries at a
  configured or lowered limit of one. Corrective commit bb503db terminalizes
  exhausted due retries while preserving live leases, fenced updates and human
  assessment history. Four red cases became seven passing regressions; 46 related
  queue/fencing checks passed. Independent correction review found no remaining
  issue in that scope. Follow-up edaedcd adds the administrator UI, settings
  contracts and four-setting authority/bounds/readback/restoration probe. Its owner
  reports 42 harness/probe checks, 11 administrator component checks, type/lint/
  contract/build checks passing; 21 existing App tests passed in an earlier scoped
  run. Independent review cleared the exact delta, including partial saves,
  failure/pending state and preservation of other settings. Probe cleanup is
  explicitly best-effort if its target becomes unavailable. The clean branch is
  reviewed and queued; combined migration/worker/browser checks still follow.
- **Task 37:** the original recipient returned twice without a branch or usable
  handoff and was told to stand down. A coordinator subagent now owns the isolated
  drill from corrected candidate 4fe8bb8. Preparation is committed at c85b77b:
  four new files and six passing lightweight isolation checks, plus lint/format.
  Independent source review found no execution blocker. After the central backend
  completed 1,475 tests with 88.73% coverage, the coordinator released the drill to
  run alongside browsers: it opens no listener and owns separate data/processes.
  Final handoff fefbd99 contains the complete drill tested at e795bda: all seven
  cases passed in 45.86 seconds, followed by a documentation-only receipt commit. It proves
  one accepted typed submission survives a committed worker claim, process death,
  lease expiry and restart, followed by a fresh restore of database and source
  bytes. Exactly-once feedback/model/continuation records, human assessment and
  API-view history, source hashes and withdrawal/revocation denials are checked.
  Initial failed runs exposed fixture database bindings and comparisons made at
  different human-review states; their receipts are retained. Independent review
  cleared the corrected fixture delta. This is synthetic local operational proof;
  hosted/provider recovery and later-withdrawal reconciliation remain separate.
  Use a fresh short OS-temp directory for the drill because long Windows pytest
  paths failed in the current validation.

The existing task **Reconcile requirements with evidence** has been assigned the
next integration in a new isolated worktree on
`codex/integrate-next-wave-20260910`, starting from ece4bed. It may reconcile these
reviewed branches, contracts and Task 35 provenance now. Its complete suites wait
for the coordinator's final current-batch source and release signal; it must
include any final browser correction before freezing its own test source.

The next integration has also reproduced and corrected an API feedback exception
path that reloaded retry policy instead of retaining the executing snapshot
(64 focused runtime checks passed). It removed an identical duplicate governance
bucket introduced by the merge. Its draft provenance now fingerprints the new
runtime-policy, transport, executor, repository and worker dependencies. These
preparation receipts still need combined validation.

A separate assessor focus correction is reviewed and ready at
`b0f6f122691b73e74310985c8c701158df258755`, following required browser-readiness
commit `f71b9d18dfc6f339a45a495d8f4b04acee7a41c4` in the coordinator's browser
worktree. Two deterministic component regressions reproduce premature
consumption of the return-focus target when a pending evidence read finishes
during asynchronous access checking. Cancel and Confirm both lose return focus.
The complete 16-case assessor component file and all eight tutor/results browser
cases pass at b0f6f12, with TypeScript and changed-file ESLint clean. The next
integration must include both commits and complete frontend/browser validation;
intermediate test-only f71b9d1 is not a completed fix by itself.
The original WebKit empty-reason timeout remains unconfirmed and is recorded
separately in the current integration report.

## Integration order and acceptance

1. Finish the current frozen-code suites and record their real receipts.
2. Review each new slice against its exact scope and controlling requirements.
   Keep its passing branch-level tests separate from combined integration proof.
3. Integrate Task 34A's migration before assigning the next durable-storage
   migration. Reconcile readiness with migration head 0046 and run the existing
   pin/migration/readiness regressions. Check that instrument fields do not
   silently expand existing technical-pair processing/export permissions.
4. Integrate Task 38A's runtime settings with regenerated contracts and prove
   that a persistent worker uses changed settings for subsequent logical work.
   Its changes to fingerprinted feedback runtime require a Task 35 manifest and
   dependent draft-bundle/forms/numerical-evidence refresh, followed by provenance
   checks. All cases remain drafts without independent expert approval.
5. Execute the Task 37 drill on disposable data, then repeat relevant recovery
   checks after the new feature migrations are integrated. A backup predating a
   withdrawal requires an authoritative reconciliation source to restore current
   eligibility; old data alone cannot prove it.
6. Assign Task 38B after the migration slot is available: immutable usage and
   reservation/reconciliation records, concurrent budget enforcement, failed or
   unknown usage, currency/provenance, and restart-safe accounting. Use synthetic
   transports and price fixtures before any approved live campaign.

## Actions requiring people or external records

- The study lead and relevant institutional owners must supply the actual
  protocol/instrument, consent, purpose/field, retention and release records.
  Draft fixtures do not supply these approvals.
- Quantum/assessment experts must review the prepared Task 35 cases and record
  independent judgments, sources, actual outputs and the separate evaluator
  release decision. All 108 prepared cases are still drafts.
- Operations must supply an approved host/provider/model/budget and pricing
  assumptions before representative load and billed-cost testing. Current local
  usage has no measured external AUD cost.
- Named human testers must perform native Safari, assistive-technology and
  first-time educator/learner trials using the Task 39 kit.
- The reuse verifier must provide the approved second-domain source/module and
  independently observed contributor effort against the selected 16 developer-hour
  target. Hosted release remains Task 41 after its prerequisites.

The existing Task 8 policy selections remain settled. These are requests for
concrete records, evidence and execution, not a request to repeat those choices.
