# Integration verification — 11 September 2026

The six deliveries merged at `46aebb3` now share migration head `20260911_0051`,
registered models and regenerated API/TypeScript contracts. This receipt covers
the first integration batch and the compatibility corrections described below.
Further generated-task, formative-support, integrity-cue and assessor-editor
work is separate and requires its own affected checks.

## Recorded checks

**139 distinct backend cases pass across the recorded focused runs.** This is
not a complete application suite or a new coverage measurement. Case identities
were reconciled from JUnit reports, retaining the latest result for each case:

| Scope | Recorded result |
| --- | --- |
| Scanner-aware conditional reuse | 1 passed |
| Operational exports, canonical choices, structured tasks and moderation | 40 passed, 3 fixture failures; those cases passed after correction |
| Corrected moderation and refreshed validation tooling | 44 passed, including four moderation cases overlapping the preceding run |
| Combined migrations, protected history, replay, backup and metadata | 52 passed, 3 fixture failures; the three corrected cases passed on their own rerun |
| Shared course editor, study pages and app routing | 31 passed, 1 accessible-label failure; the corrected case passed on its own rerun, accounting for all 32 distinct frontend cases |

Backend Ruff checks and formatting pass across 540 files. Frontend TypeScript
and lint pass; the changed course editor also passed its subsequent scoped lint
and type check. Canonical OpenAPI and generated TypeScript drift checks pass.
The requirement matrix validator accepts all 143 rows. These checks retain
the existing production gates and use synthetic local data with no paid calls.

## Integration corrections

- Ordered the independently developed migrations 0047 through 0051, updated
  readiness and table inventory, and made new budget/moderation DDL replay-safe.
  Historical downgrade tests still exercise their original guards; current-head
  tests verify refusal before protected intake history changes.
- Added explicit synthetic scanning opt-ins to the new sourced test modules.
  Shared written-explanation fixtures now use `short_answer`, matching their
  actual content, instead of a quiz without declared choices.
- Exercised the study collector against the real provider ledger and moderation
  tables: exact response/course/task joins, nullable actual billing, reconciliation,
  multiple moderation cycles, pseudonymization and source-change invalidation.
- Corrected migration fixtures to supply a matching assessor review when testing
  the separate immutable-evidence guard, record normal course creation history,
  and explicitly assign the synthetic moderation policy owner assessor access.
- Made the indexed-material button's accessible name match “Reprocess and scan”;
  failed-material recovery retains “Retry processing”.

The validation manifest now includes the new moderation, provider, source-scan,
generation, typed-response and support dependencies. All 12 numerical fixture
distributions match. The 108 cases remain **DRAFT**, with zero expert-approved
cases, content/feedback/judge quality **UNVERIFIED** and AI release **PENDING**.
Numerical matches do not establish human or operational acceptance.

## Limits and remaining work

The prior 1,607-backend/319-frontend/132-browser receipt applies to its dated
source, not automatically to this integration. A full browser suite, actual
scanner/container execution, approved hosted deployment, representative paid
load/cost campaign and human/expert study/accessibility acceptance were not run
in this batch. The [task ledger](../../LearnLens_Remaining_Tasks.md) retains
12 unfinished numbered tasks and separates software from acceptance records.
The [operational checklist](operational-acceptance-checklist.md) identifies the
actual owner records still required.

## Follow-up integration

Source `72392d9` includes practice representations (`70ea786`, `c26bcae`),
submission review cues (`ba95955`, `99becc1`), multipart generation (`7f12e3e`,
`95b66a3`) and versioned assessor editing (`067f476`, `daed691`). These deliveries
add no migration beyond head 0051. Their delivery notes retain their scoped
owner checks; overlapping reruns are not added to the first-batch counts.

Independent review identified and corrected cross-task instructional support
during active transfer, fresh-input disclosure in generated public criteria,
scaffolding false positives in review cues, wrong-course editor access checks,
and obsolete generated-save callbacks. Each correction has a focused regression.
The editor owner records 28 passing affected UI cases and six backend checks.

Three additional checks passed against the integrated source:

| Integration boundary | Result |
| --- | --- |
| Course-wide transfer: instruction and replay blocked, approved access preserved | 1 passed, 5.32 seconds |
| Submission review cues against migrated immutable storage | 1 passed, 8.48 seconds |
| Generated-draft bridge with final authoring response | 1 passed, 3.81 seconds |

Canonical OpenAPI/TypeScript contracts and draft validation fingerprints were
refreshed. Ruff check/format passes across 607 files, the 143-row matrix is valid,
and frontend TypeScript, production build and lint pass. The build first found
invalid Windows-encoded ellipses in two study pages; those characters are now
UTF-8. Two Python files received formatting-only corrections. The build retains
a non-blocking large-bundle warning.

The draft report remains **108 DRAFT, zero approved, quality UNVERIFIED and AI
release PENDING**. The numerical receipt is deliberately retained from `fbf9ca6`:
its 12 matches belong to that recorded manifest. Quantum implementation and
scenario fixtures are unchanged; no new numerical execution is claimed and its
manifest digest has not been rewritten to imply one.

The full application/coverage/browser suite is delegated to the repository's
Quality and release gate on the pushed source. **CI result: pending.** The duplicate
standalone migration invocation was removed from CI because the full backend
suite already includes that file; all migration tests and the 80% service coverage
gate remain. This avoids an extra full local run followed by identical CI work.
Actual hosted, paid-provider, expert and human accessibility acceptance remains
outside these synthetic checks.
