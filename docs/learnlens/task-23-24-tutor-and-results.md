# Tutor dialogue and learner assessment review

This delivery implements Tasks 23 and 24 from main `16db1093cf95314acdd698fe56d27d3b21e16435`.
Delivery branch: `jordan/tutor-results-governance`.

## Learner and assessor behaviour

The task workspace restores a learner-owned tutor conversation. The tutor starts
with a reasoning probe, uses educator-reviewed conceptual hints, and asks for an
explanation between hints when the reviewed plan requires it. Answer-seeking
requests redirect to reasoning without creating a misconduct finding. Current
learner-model evidence can select a reflection probe; opting out of personalisation
prevents that model read. The selected snapshot and preference revision are recorded.

Replies are bounded to reviewed hints and fixed reasoning prompts. This is an
extractive tutor, not an unrestricted model conversation. Its release check
requires the selected approved text and rejects instruction payloads. One retry
is permitted; a failed or rejected candidate produces a safe fallback. Execution
failure is separate from an APPROVED/REJECTED quality decision. Rejected text is
not stored or displayed. Accepted turns and assistance evidence commit together.

Unaided transfer hides earlier dialogue and rejects both new help and replayed
help requests. Accessibility support remains available through the episode
workspace. Reapproved teaching content cannot restore an old reply through a
retry key or conversation history. Historical records themselves are retained.

Each formal response in attempt history has a result panel containing its lifecycle,
Bloom target, public criteria, saved evidence, explanation and next action. D-01
conceals verdicts and criterion judgements until confirmation or override. Returned,
withheld and void states remain explicit. Overrides do not falsely claim that all
criteria were met. Private assessor notes, anchors and evaluator inputs stay private.

Learners can request review of their own response with a reason. Course-authorised
assessors open the existing decision workspace, record any required result action,
then resolve the request with an internal reason and a separate learner notice.
Resolution checks the decision revision and preserves the original request. A
resolution does not itself change a result. Detailed notices are only visible while
a result is released; pending and void projections use a neutral notice.

## Storage and integration

- `20260909_0034` adds immutable appeal resolutions after `20260908_0033`.
- `20260909_0035` adds scoped, immutable tutor turns after `20260909_0034`.
- Tutor revisions, retry keys and writer locking prevent duplicate concurrent turns.
- Requests use deterministic retry identities; only one request can remain pending
  for an attempt. Resolutions are immutable and checked against current assessor access.
- Populated history blocks downgrade. Use forward repair or a verified backup restore;
  do not remove learner history to force a downgrade.

Task 21/22 implementation is independent of these routes. Coordinate migration
identifiers if those branches introduce another successor to `20260908_0033`.
Task 25's complete learning loop and Task 26 reassessment remain separate work.

## Governance records

Tasks 8 and 32 retain their outstanding human decisions. Per the user's request,
the approved-selections, study-protocol and data-plan documents contain HTML
comments identifying the exact information the team must supply. These comments
do not assert institutional approval, preregistration or study activation.

## Review and validation

Independent Standards and Spec reviews of `7d2e6ff` against the starting main
reported no remaining actionable findings. Earlier findings concerning pending
notices, formative reasoning requirements, override explanations, context structure
and quality/execution status separation were resolved before that review.

The tests exercise real course/task review and assessment services, result visibility,
cookie CSRF, ownership, revoked access, replay, simultaneous messages, preference
opt-out, evidence rollback and migration preservation. Browser journeys cover both
the learner-request/assessor-resolution path and reviewed hints followed by unaided
transfer. They use newly created synthetic accounts and assessment records.

Validation on 9 September 2026:

- All 1,121 backend tests passed across four isolated batches and focused reruns.
  Combined service coverage is 87.22% (required: 80%); tutor coverage is 96.34%
  and learner-result service coverage is 91.22%. The batches include migrations.
- All 244 frontend tests passed across the full run and an isolated rerun of
  three assessor-setup tests that exceeded their 15-second limit under load.
- Ruff lint and formatting, frontend ESLint and production build, and OpenAPI
  and generated TypeScript drift checks passed.
- The patched HTTP client was exercised by all 273 tests in the 29 API/authentication
  test files, including reruns described below.

The Windows workspace path exceeded the platform's file-operation limit in the
existing document-upload test. Both learning-loop cases passed with a shorter
temporary directory. A simulation-evidence check failed during the loaded API
run; all 15 tests in that file passed in the focused rerun. These reruns changed
the execution conditions, not application behaviour or test assertions.

All 88 browser cases passed across Chrome, Edge, Firefox and WebKit in the full
run and focused reruns. An older history assertion was updated for the new
pending-result panel; a review-action timeout passed on rerun. Screenshot review
at 320 pixels found a stale request-saved message after resolution. Refresh now
clears it, and the corrected learner/assessor journey passed in all four browsers.
One Edge attempt encountered a local fetch failure before that step; its isolated
rerun passed with tracing enabled. The affected component tests, lint and build
also passed after this final correction. Gitleaks found no secrets in the delivery
diff and handoff document.

Native Safari, screen-reader evaluation, institutional decisions and the complete
Task 25 learning loop are not claimed by this delivery.

Local execution receipts are retained under the ignored `.tmp-task23-24/` directory:
`backend-batch-*.log`, `backend-regressions-final.log`, `coverage-final.txt`,
`patched-api-*.log`, `frontend-final.log`, `frontend-setup-final.log`,
`browser-final.log`, `browser-rerun-final.log`, `browser-notice-final.log` and
`browser-edge-final.log`. Browser reports retain the narrow-screen screenshots.

The dependency audit identified existing advisories in the development HTTP client.
`httpx2` and `httpcore2` are updated from 2.9.1 to 2.12.0 in a separate maintenance
change. The updated environment reports no known Python dependency vulnerabilities;
API and authentication tests passed against those patched versions. npm reports
no high or critical vulnerabilities; its two existing moderate findings remain.
