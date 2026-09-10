# Integration verification — 10 September 2026

**PASS for the delivered scope at the source revisions below.** Expert validation,
human accessibility trials, research activation and hosted release remain separate
acceptance requirements. The [task list](../../LearnLens_Remaining_Tasks.md) and
[143-row requirement matrix](implementation-gap-matrix.md) track current work.

## Feature checklist

| Area | Verified implementation | Outstanding evidence or implementation |
| --- | --- | --- |
| Accounts and course access | Sign-in, role/course/learner restrictions, educator and learner views | Hosted authentication and release verification |
| Sources and authoring | Versioned sources, recoverable processing, outcome/assessment authoring and publication controls | Recoverable course-configuration revisions, upload malware policy, all required generated task types |
| Learning work | Typed evidence, drafts/revisions, saved circuits, simulation, keyboard gate placement, explicit CX text, UTC progress | Complete access-mode evidence and human accessibility trials |
| Feedback and adaptation | Complete bounded practice evidence reaches generator/judge adapters; durable execution, saved evidence/model and activity continuation | Independent quality ratings, effectiveness measurements and full operational recovery drills |
| Formal assessment | Evaluator rules, PASS/INCOMPLETE, protected histories, hidden provisional verdicts and authorized human decisions | Dialog-return focus race at this revision; evaluator approval, moderation and revalidation evidence |
| Research controls | Scoped consent/grants/withdrawal, restricted technical-pair export and authenticated governance writes | Approved study records, full learning instruments and governed activation |
| Quality and operations | Automated suites, migration/readiness checks, security gates, backup/restore fixtures and local benchmark harness | Runtime controls, complete metering/budget enforcement, representative billed load and hosted release |

## Validation receipts

| Check | Final result |
| --- | --- |
| Backend full suite | **1,475 passed**, zero failures/errors/skips; **88.73%** service coverage against the 80% gate |
| Frontend full suite | **306 passed in 84 files**, zero failures/skips; 184.63 seconds |
| Configured browser suites | **132 passed** across Chrome, Edge, Firefox and WebKit; zero failures/skips/flaky results |
| Root launcher/checker tests | 13 top-level tests and nine subtests passed: 22 JUnit cases |
| Backend lint/format | Passed; 540 files at the corrected source freeze |
| Frontend lint/type/build | Passed; existing large-chunk advisory remains |
| Python lock and frontend clean installation | Passed with Python 3.11.16 and Node 22.13.0; Vitest 4.1.11 |
| Generated contracts and migration/readiness checks | Passed |
| Dependency audits | npm full/production: zero vulnerabilities; backend pip-audit: 67 packages, zero known vulnerabilities |
| Full-history secret gate | Zero findings; synthetic positive control detected and redacted |
| Requirements and manual-kit checks | All 143 requirements represented once; source/reference and manual-kit checks passed |

Browser coverage comprises 93 Chrome/Edge/WebKit main journeys, 31 Firefox main
journeys, four complete-learning-loop journeys and four misconception journeys.
Synthetic fixtures exercise application policies; Playwright WebKit does not
establish native Safari or human screen-reader acceptance.

## Defects found and corrected

- **Progress timestamps:** explicit UTC instants survive SQLite reload and non-UTC
  rendering. See [timestamp validation](task-29-progress-timezones.md).
- **Readiness:** the expected migration was 0044 after the actual head became
  0045. The pin was corrected; 16 focused deployment/health/worker checks passed.
- **Practice feedback:** purpose separation and complete bounded typed evidence
  now reach both generator and judge. The final focused suite passed 80 cases,
  including 13 actual-input regressions. Digest, approval, transfer, cache and
  20,000-character boundaries remain enforced.
- **Governance writes:** registration of the missing rate-limit bucket corrected
  valid authenticated writes returning `403 rate_limit_policy_missing`. Real-cookie
  access and 60/minute rate-limit regressions passed 45 cases.
- **Circuits:** keyboard H/X targeting, gate-removal labels and explicit live/saved
  CX control/target text were corrected; component/browser checks passed.
- **Benchmark:** typed submission lifecycle and bounded subprocess cleanup were
  corrected. [Integration verification](task-38-integration-verification.md) reports
  54 focused passes and 35 successful local HTTP calls with complete episode input.
  Unknown actual AUD costs remain unknown; local adapters are not provider billing.
- **Validation provenance:** mandatory fingerprints now include changed practice
  input dependencies. All 44 tooling tests and 12 numerical checks passed. The
  dataset remains 108 draft cases, zero approved cases, content/feedback UNVERIFIED
  and AI assessment release PENDING.

## Failed runs and evidence limits

The first full backend run collected 1,473 cases: 1,464 passed, four failed and
five had setup errors, with 88.71% coverage. Two upload cases exceeded Windows
path limits; a fresh short temporary path resolved them without application or
assertion changes. Legacy synthetic fixtures needed their existing repository
choice passed explicitly to terminal workers. The restore test needed to verify
its current-head backup before an intentionally refused downgrade, then re-upgrade
and check preserved rows. The corrected full run is the passing receipt above.

The first complete Chrome/Edge/WebKit group had 84 passes and nine failures.
Eight failures followed shared-demo learner contamination by the new circuit
regression. A private learner fixture fixed that isolation defect and all browser
groups were rerun. The remaining WebKit assessor-resolution timeout had an empty
internal reason; repeated probes did not establish its cause.

Those probes separately reproduced a dialog-return focus race: a pending evidence
read could consume the return-focus target before opening the dialog. Correction
`b0f6f12`, following test clarification `f71b9d1`, passed 16 component and eight
browser cases on its own source. It is outside this report's validated application
revision and does not establish the cause of the earlier empty-reason timeout.
Current status is tracked in the requirement matrix.

## Reproduction and source identity

Backend application/tests: `4fe8bb8184359e1fae606bc8cdd559fe54bc4760`.
Backend tree: `5313b27b04519972ea2e4f13bbced24a4a8ef9e5`.
Frontend unit/build revision: `e93842f21fbeb14d88e3a18ac132abcec9012db0`.
Frontend application tree: `8be23f092b31318e83e6f6ddf37971cc245a6cb5`, unchanged
in the corrected backend freeze. Browser-test revision:
`ece4bedd41c36c7c37e89a10ce20fcd96a329f0f`; its later change isolates the circuit
test learner and does not alter application or unit/build inputs.

Use the frozen dependency environments. Run backend pytest with
`--cov=app.services --cov-fail-under=80` and a fresh short temporary directory;
run root checks separately with `python -m pytest tests`. From the frontend,
run the configured unit, lint, build, `test:e2e`, `test:e2e:learning-loop` and
`test:e2e:misconceptions` scripts against isolated fixture servers. Preserve failed
attempts separately from successful full-run receipts.

## Remaining external evidence and next dependencies

At this validation snapshot, 29 of 41 tasks had completed implementation,
10 were partial and two remained: **12 unfinished tasks**. Requirement counts
were 87 IMPLEMENTED, 41 PARTIAL, two MISSING and 13 UNVERIFIED.

Outstanding work includes named policy/operations owners, approved research
instruments, expert ratings and evaluator release, full recovery drills, complete
runtime metering/budget controls, representative provider load/cost measurements,
human/native accessibility and usability trials, independent reuse evidence and
hosted release validation. These are not satisfied by synthetic fixtures or the
existence of a test harness.
