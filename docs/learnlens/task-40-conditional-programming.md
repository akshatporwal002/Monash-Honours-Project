# Task 40: conditional-programming reuse implementation

Status: **partial**, 9 September 2026. Starting main: `e3ce194`.
Decision: D-11, `programming-reuse-v1-selection`. This delivery implements the
independent content/configuration exercise. It does not complete Task 25 or 36,
activate a course, or demonstrate learning benefit in a second subject.

## Integrated software reuse update — 11 September 2026

The content factory now supplies `pathway_draft(...)`, a `PathwayPublish` command
for tracing, correction and fresh application. It creates no approval or database
record. After actual source/task/assessment approval, the educator can publish it
through `CurriculumService.publish`; the service freezes the reviewed versions.

```python
from app.services.curriculum import CurriculumService

pathway = content.pathway_draft(
    task_ids=tuple(task.id for task in tasks),
    expected_version=0,
    request_key="conditional-pathway-v1",
    reason="Record the actual educator approval reason here",
)
# Only after the educator has reviewed the real sources, tasks and assessment:
CurriculumService(session).publish(educator, outcome.id, pathway)
```

The existing `test_episode_freezes_conditional_evidence_and_reuses_assessment`
now traverses both practice tasks, real local feedback execution, durable worker
continuation, outcome-scoped model snapshots and accepted next-task suggestions,
then the supported/transfer episode and authorised human-assessment service.
Predictions, code text, explanation, reflection and revision stay frozen; results
remain withheld pending review. The formal episode also records a model snapshot,
and the finished pathway offers no unrelated task. The existing pass-rule checks
retain PASS only when all mandatory criteria are met and INCOMPLETE for missing
or incorrect transfer evidence. Source indexing/approvals and human decisions in
this test are explicitly synthetic.

**Core engine changes: none.** The missing integration was module pathway
configuration. Shared evidence, feedback, model, adaptation, assessment, schemas
and learner UI are unchanged. This is service-level software compatibility proof,
not an independently observed published course or a 16-hour effort measurement.
The affected integration case passed in 8.68 seconds after correcting its synthetic
learner profile and indexed-source setup. The original source helper only created
authoring approval, so assessed feedback correctly withheld unindexed sources.
Earlier validation below is historical; it is not a new broad-suite execution.

## Delivered module

`src-main/backend/app/services/conditional_programming.py` supplies ordinary
course, module, outcome and task drafts. Its original demonstration examples are:

1. Trace a program using `temperature > 20` at equality: the output is `cool`.
2. Choose `temperature >= 20` to meet “warm at 20 or above”; consider 19, 20 and 21.
3. Predict, explain corrected code, reflect and optionally link a revision to an
   earlier submission. Then trace a fresh delivery-fee example for 2, 3 and 4 items
   under `items >= 3`, with fees 5, 0 and 0 respectively, without instructional hints.

The third activity uses the existing `explanation` episode type. Code is preserved
as text, not executed or graded by substring matching. Proposed human-review
criteria cover tracing, correction and transfer; equivalent valid corrections
can meet the correction criterion. The two choice activities are practice checks,
not evidence that a formal criterion is automatically met.

Prompts describe both original branches explicitly because the existing choice and
explanation renderers do not display `starter_code`. Learners put the corrected
program in the ordinary response textarea. The existing fresh-application fields
also accept code. This avoids depending on the Qiskit-labelled code editor.

The draft course has enrolment closed. Sources are deliberately empty. Nothing
here approves sources, outcomes, tasks, assessment definitions or course publication.

## Using the existing authoring boundary

From the backend, with an existing authenticated educator and SQLAlchemy session,
create drafts through the same services used by the API:

```python
from app.services import conditional_programming as content
from app.services.lms import LmsService

lms = LmsService(session)
course = lms.create_course(educator, content.course_draft())
module = lms.create_module(educator, course.id, content.module_draft())
outcome = lms.create_outcome(educator, module.id, content.outcome_draft())
tasks = [
    lms.create_task(educator, course.id, task)
    for task in content.task_drafts(module_id=module.id, outcome_id=outcome.id)
]
```

Each invocation creates a new draft course; this is not a startup seed or an
idempotent installer. No service registration is needed. The returned Pydantic
drafts can also be serialized with `model_dump(mode="json")` for the existing
course/module/outcome/task POST routes. Keep private task criteria and the transfer
solution in staff authoring data; learner reads use the existing projection.

Before publication, an authorised educator must supply approved course-scoped
source passages and complete the normal task review. The assessor must approve
the actual outcome version, conditions, criteria and task form. `criterion_drafts()`
returns proposed `CriterionDraft` values for this workflow, with HUMAN evaluation
and empty approved anchors. Bind all three mandatory criteria through the existing
ALL_OF definition rule. These proposed values are not an approved assessment bundle.

## Reuse demonstrated and limits

| Existing capability | Demonstration |
| --- | --- |
| LMS course/module/outcome/task authoring | Real service calls create an isolated draft course and three tasks; unreviewed publication fails. |
| Task registry and current renderers | Existing multiple-choice dispatch marks tracing and correction; episode responses require criterion review. No new identifier or renderer. |
| Episode plan, checkpoint and transfer | Existing contracts require prediction, reasoning, explanation and reflection; missing fresh work blocks submission; transfer content remains private until entry. |
| Drafts and frozen response evidence | Real database round trip preserves code, prediction and transfer; replay returns the same submission; a linked revision preserves the first response; cross-course reads fail. |
| Assessment definitions | Synthetic test-only source/task/outcome approval binds this module's reviewed episode plan into the existing versioned task form. |
| Criterion evaluator and pass rule | Existing human evaluator preserves an evidence reference; synthetic criterion decisions produce PASS only when all mandatory criteria are met, and INCOMPLETE for unavailable or incorrect transfer evidence. These are adapter/engine checks, not independent human judgements. |
| Learner model and adaptation | Shared services now run through all three activities in the integrated synthetic journey above. Approved independent practical verification remains due. |

**Required core changes: none.** No existing runtime service, schema, database,
registry, frontend, evidence engine, model engine, adaptation engine or assessment
engine was modified. The addition is a content factory using existing contracts,
with automated checks and documentation. Tasks 21 and 22 were not modified or
used as prerequisites for these checks.

## Actual work record

This record describes completed work, not measured developer-hours:

| Category | Actual work |
| --- | --- |
| Setup and inspection | Inspected D-11, the task extension guide, authoring, episode, evidence, assessment and quality gates. |
| Source preparation | Authored small temperature and delivery examples. No external source selected or approved. |
| Coding | Added draft factories and proposed human criteria using existing interfaces. |
| Debugging | Corrected the test's publication-helper import, enum comparison, required synthetic approval timestamp and expected missing-transfer message. Checked the existing renderer and made the activity prompts self-contained, using the response textarea for corrected code. Diagnosed 32 regression failures/errors caused by Windows path length in nested temporary directories; all passed unchanged in shorter isolated directories. Cleared frontend failures with focused reruns after bulk jobs finished. No production constraints, assertions or timeouts were relaxed. |
| Tests | Added marking, malformed-input, publication, visibility, database episode/revision, evidence scope and assessment reuse checks. See validation below. |
| Documentation | Added this implementation/handoff record, extension-guide example and partial Task 40 status. |

No reliable category-by-category human effort measurement was captured. Agent
wall-clock time is not a substitute for the D-11 developer-hour accounting. Do not
claim the 16-hour target has been met from this record. Count work across all
contributors and report waiting separately when completing the verified effort log.

## Validation

Focused command from `src-main/backend`:

```text
python -m pytest tests/test_conditional_programming.py -q
```

The 13 focused cases pass, including the real database lifecycle. All source
approvals, identities and human criterion decisions used by these tests are
explicitly synthetic. The module itself does not make those approvals.
Frontend and browser checks are regression coverage of existing interfaces, not
independent observation of a published conditional-programming course. That
practical verification still requires the approved course and source/form versions.

Local checks on the isolated feature branch:

| Check | Actual result |
| --- | --- |
| Task 40 focused cases | 13 passed, including the final textarea response contract. |
| Backend regression and migrations | All 1,181 cases have passing results. The full run produced 1,149 passes and 32 Windows path-length failures/errors; every failed case then passed unchanged in focused short-directory reruns. |
| Coverage | 85% backend service statement coverage in the full run; the new content module has 100%. The configured 80% gate passes. |
| Frontend regression | The full run exercised 254 cases (245 passed, 9 initially failed). Every recorded failure, including additional timeouts in a focused file rerun, passed unchanged in subsequent targeted runs. The final seven individual retries all passed after bulk jobs ended. |
| Browser regression | 108 cases across Chrome, Edge, Firefox and Playwright WebKit. Two admin-route accessibility cases timed out in the full run; both passed unchanged together on the focused rerun (2 passed, 0 skipped). Native Safari and independent practical verification are not claimed. |
| Lint and formatting | Backend Ruff lint and format checks and frontend ESLint passed. |
| Contracts | OpenAPI and generated frontend contract drift checks passed. |
| Build | Production TypeScript/Vite build passed; existing large-chunk warning remains. |
| Dependencies | Locked Python/frontend installs and Python lock check passed. Python and production npm audits found no known vulnerabilities; the full npm tree has two moderate development advisories and passes the configured high-severity gate. |
| Secrets | Gitleaks found no leaks in the five deliverable files. |

Browser checks used isolated ports 4273/4280, a separate temporary database and output directories.
Only local scratch copies of test configuration/URLs changed for those ports;
no tracked browser tests, assertions or timeouts were changed.

The feature is handed off on `jordan/task40-conditional-reuse-isolated` for the
designated integration chat. It is not merged into main. Plans, scratch runners,
test databases and raw logs remain outside the commit.

## Standards review

Read-only agent review of the five-file diff against `e3ce194`: **0 findings**.
The content composes existing authoring, episode and criterion contracts; no
documented-standard breach or actionable code smell was identified.

## Spec review

Separate read-only agent review: **0 actionable findings**. The independent
implementation matches the requested scope, and the missing approvals, effort,
verifier and full integration are explicitly retained as remaining requirements.
Both reviews are agent checks, not D-11 independent human verification.

Review totals: Standards 0; Spec 0. Neither axis identified an actionable issue.

## Remaining acceptance requirements

- Task 8 / D-11: exact approved sources, module scope and named independent verifier.
- Measured setup, source preparation, coding, debugging, testing and documentation
  effort across contributors, separately reporting elapsed waiting; independently
  verify the approved scope against the 16 developer-hour target.
- Tasks 25 and 36: complete integrated learning journey and final combined checks,
  including the final source/scanner, typed-task, research and moderation changes.
- Independent practical verification, including the configured course, source and
  assessment versions, tested commit, observed journey and any further core changes.

<!-- MANUAL FILL — APPROVED SOURCES: Record exact source title, revision/passage IDs,
course scope, approver name, approval date and approval evidence link. Empty source
references in the factory are intentional; synthetic test sources do not qualify. -->
<!-- MANUAL FILL — INDEPENDENT VERIFIER: Name the independent developer, role,
independence from this implementation, agreed scope and verification date. -->
<!-- MANUAL FILL — EFFORT: Attach actual per-contributor category timings and separate
waiting durations, total developer-hours, accounting method and verifier sign-off. -->
<!-- MANUAL FILL — VERIFICATION EVIDENCE: Link the independently observed complete
journey, exact commit/course/source/form versions, model and adaptation integration
results, issues/core changes, dependency completion records and signed conclusion.
Keep Task 40 partial until all requirements are satisfied. -->
