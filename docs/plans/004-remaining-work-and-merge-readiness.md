# 004: Remaining work and merge-readiness handoff

Status: current as of 2026-08-19. This is a handoff record, not an implementation plan.

## Purpose and current boundary

Plan 003 repaired the bounded assessment-definition and assessor-review integration slice. Its
available automated checks passed, and Test Judge, Code Reviewer, and Code Quality Reviewer
approved the final implementation tree.

The working tree is still unstaged. No commit, push, pull request, or merge has occurred. The
pre-existing `.tmp-step*` directories remain outside the delivery scope and must be preserved.

This branch is not pilot-ready. Plan 003 deliberately does not implement Plan 002 Steps 15 through
20. It also does not replace the external accessibility and GitHub checks listed below.

## Evidence already available

The following proof applies to the repaired Plan 003 slice on the current implementation tree:

| Gate | Result |
| --- | --- |
| Backend release suite | Passed, 592 tests and 84.97% service coverage |
| Migration suite | Passed, 26 tests |
| Frontend unit and automated Axe checks | Passed, 81 tests |
| Browser matrix | Passed, 24 tests across Chrome, Edge, Firefox, and WebKit |
| Ruff, ESLint, TypeScript, production build, and API contract drift | Passed |
| Python and npm dependency audits | Passed, no known vulnerabilities |
| Local reviews | Test Judge, Code Reviewer, and Code Quality Reviewer approved |
| `git diff --check` | Passed, with no whitespace errors |

The detailed commands, repair scope, risks, and `NOT RUN` records remain in Plan 003.

## Remaining work before this slice can be merged

These are release and evidence actions. They do not require a new product feature unless a check
finds a defect.

1. Review the exact staged file list and exclude every unrelated or pre-existing `.tmp-step*`
   directory.
2. Commit the approved Plan 003 slice with a commit message tied to its verified evidence.
3. Push the commit and create or update the required draft pull request.
4. Run GitHub CI on that exact commit. It must pass its backend, migration, contract, frontend,
   browser, dependency-audit, and Gitleaks jobs. CI uses its supported Node 22 environment. The
   local run used Node 24.18 and therefore does not prove the CI Node version.
5. Record the missing manual and external accessibility evidence before making a complete
   accessibility or release-readiness claim:
   - approved screen-reader session with observable output;
   - native Safari session, reported separately from Playwright WebKit;
   - manual 200% and 400% zoom inspection.
6. Refresh any affected test or review verdict if code changes after the current approvals.
7. Keep the pull request draft while any required gate is missing, failed, blocked, or stale.
8. Obtain the GitHub workflow owner's ready-for-review action and human review. Merge only after
   those approvals and the separate merge authority are present.

Current `NOT RUN` items are Gitleaks, GitHub CI, approved screen-reader evidence, native Safari,
and manual 200% and 400% zoom inspection. Automated 640px and 320px reflow checks passed, but
they are not a substitute for the manual checks.

## Product work still required from Plan 002

### Step 15: Learner result, explanation, and review request

Implement learner-owned result detail and review-request paths. The view must show only `PASS` or
`INCOMPLETE` when policy permits visibility, explain met criteria and missing evidence, offer the
next action, and avoid numeric grades, public `FAIL`, and colour-only meaning. It must prove AT19
and AT24.

### Step 16: Policy-bound reassessment

Implement reassessment only under an explicit policy version. It must create a fresh linked attempt
under the same standard, preserve earlier evidence and decisions, never average results, and tell
the learner whether to revise, reassess, transfer, or request human review. It must prove AT18 and
AT21.

### Step 17: Remove numeric assessment writes and shared score projections

Stop new numeric assessment-score writes. Remove score-driven completion and formal-result logic
from shared backend contracts, while retaining protected legacy compatibility reads. Keep technical,
quality, research, and optional-points metrics clearly separate from formal assessment.

### Step 18: Remove score-based frontend presentation

Remove score, average, percentage, numeric-mastery, leaderboard, and `passing_score` views from
the shared frontend. Present activity state, evidence, learner-model inference, and formal results
as separate concepts. Reject old numeric-result payloads from new APIs.

### Step 19: Complete Person B handoff and integration

Wait for Person B's approved integration manifest and isolated proof. Integrate only through the
named read-only ports, regenerate contracts, preserve the one-way formal-result boundary, and
create a named Alembic merge revision if the migration graph requires one.

### Step 20: Prove the complete assessment journey

Add and run an end-to-end learner journey from assessor assignment through publication, learner
attempt, evidence, provisional decision, assessor action, learner result, review request, and
reassessment. Record the schema, migration, recovery, assessor, learner, access, privacy, audit,
and known-limit evidence. Run current CI commands, manual accessibility checks, and fresh local
reviews on the final head.

## Product decisions and external inputs still needed

The following items need named owners. Do not guess a configuration in code.

| Missing decision or evidence | Owner | Blocking effect |
| --- | --- | --- |
| Roles allowed to receive assessor permission | Product owner | No production assignment policy or pilot-ready claim |
| Separate research-permission recipients | Product owner and research governance | No production research assignment |
| Learner visibility of provisional results | Product owner and assessors | Learner result wording and configuration remain blocked |
| Outcome criteria and evidence-sufficiency rules | Assigned assessors | Real assessed outcomes cannot publish |
| Tools, support, access conditions, and transfer rules per task | Assigned assessors | Real task forms cannot publish |
| Current-result rule after reassessment | Product owner and assessors | Reassessment cannot activate |
| Approved evaluator dataset, metrics, and release thresholds | Assessment governance | Automated evaluator release remains blocked |
| Assessment and audit retention periods | Privacy owner | Destructive cleanup and retention claims remain blocked |
| Human escalation owner and service target | Product owner and operations | Escalation service level remains blocked |
| Person B A1 approval and stable Handoff 2 manifest | Person B | Dependent evidence and shared integration remain blocked |
| Approved native Safari and screen-reader environments | Accessibility owner | Full NFR4, NFR18, and AC17 proof remains blocked |
| Legacy compatibility window and client policy | Product owner and technical owner | Final legacy-column removal and old-client shutdown remain blocked |

## Recommended order

1. Decide whether to publish the bounded Plan 003 repair now or keep it local until the wider
   product scope is ready.
2. If publishing now, complete the release actions and evidence gates above without claiming pilot
   readiness.
3. Obtain the product decisions before starting Steps 15 and 16, because result visibility and
   reassessment depend on them.
4. Complete Steps 15 through 18 with their own plans, tests, and reviews.
5. Coordinate Step 19 with Person B. Do not edit Person B-owned modules or migration revisions.
6. Complete Step 20 on the integrated head, then seek human review only after all current gates
   are present and passing.

## References

- `docs/plans/002-person-a-assessment-implementation.md`, Steps 15 to 20, product decisions, and
  final delivery gates.
- `docs/plans/003-merge-blocker-repairs.md`, bounded repair evidence and current `NOT RUN` items.
- `.github/workflows/quality.yml`, the authoritative CI check set.
