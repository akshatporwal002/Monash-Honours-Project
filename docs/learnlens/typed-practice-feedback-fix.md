# Typed practice feedback purpose boundary

Branch: `codex/fix-typed-practice-feedback`  
Base: coordinator commit `0eaf467025591e75814dc590c6c35ea936bbc506`

## Failure and change

A real unassessed explanation submission with an `EpisodePayloadV1` was accepted by
`LmsService.submit`, then failed in the offline database worker with
`context_integrity_error`. Submission classified every episode as
`assessment.response.v2`; the assessment context provider correctly refused an
assessment-labelled response without an `AssessmentAttempt`.

New unassessed typed responses now use the internal envelope version
`practice.response.v1`. Formal typed responses retain `assessment.response.v2`;
formal scalar responses retain `assessment.response.v1`; scalar practice is
unchanged. The public episode payload remains `learnlens.episode.v1`. There are no
API model, database schema, migration, frontend, governance, or provider changes.

Canonical typed digests include the version, full episode, lossless response
content, and binding fields. The practice version requires an episode and null
formal work, task-form, and conditions fields. Both historical assessment hashing
algorithms remain byte-for-byte compatible; regression vectors were calculated
using the implementation at the base commit. Every new typed-practice response
stores its digest, including submissions without an idempotency key. A missing or
mismatched digest blocks feedback; existing records are never backfilled.

Retries hash against the version and binding information already stored on the
response. Exact retries return the original response; changed episode content,
whitespace, removed episodes, and foreign work references conflict with HTTP 409.
Later task edits do not change replay identity. No replay rewrites the stored
response or creates a duplicate workflow.

## Complete bounded model input

The purpose correction also requires fixing a second defect: the old submission
adapter chose only answer, code, or a generic multipart label. Episode-only
explanations and accompanying reasoning/reflection never reached the model even
when the worker stored accepted feedback. A regression inspecting the actual
generator and judge requests reproduced this loss before the follow-up fix.

`practice_evidence.py` now encodes all response content and the complete supported
episode as `practice.feedback-evidence.v1` JSON in the existing `submitted_answer`
field. Both real model adapters receive that same lossless envelope, including
whitespace, prediction content, explanation, reasoning, reflection, revision
reason/reference, and simulation reference metadata. References remain learner
claims; they are not converted to verified source/simulation results or used to
fetch another response's content. Episode reference ownership is rechecked.

The existing **20,000-character model-input limit is unchanged**, including the
envelope overhead. Exact-bound evidence reaches both adapters intact. Beyond that
bound, the full submission and digest remain saved but the worker fails closed
with `context_integrity_error` / `PRACTICE_RESPONSE_INVALID`, makes no model calls
for that response, and stores no accepted feedback. No field is silently dropped,
summarised, or truncated, and no provider budget is increased.

The practice prompt versions are `feedback-practice-episode-v1` and
`quality-judge-practice-episode-v1`. Both receive static instructions to address
reasoning/process with the least revealing support, invite reflection/revision,
and avoid transfer solutions or formal grades. All nested learner strings remain
in the untrusted JSON user input; embedded instructions never enter the system
prompt. Generic scalar and formal assessment prompt behavior remains unchanged.

Practice feedback requires a currently approved task. A task with a formal episode
plan cannot send its private transfer solution through the generic feedback route.
An active assessed transfer elsewhere in the same course or a fresh misconception
check on the practice task withholds practice feedback. The same resolver guards
cached-feedback release. Exact retries remain stable after task edits, but an
unreviewed edited task cannot release feedback.

## Formal and historical boundaries

The formal frozen response reader explicitly requires a supported assessment
version, even though the shared hash utility now understands practice. Missing
assessment attempts still fail closed when a response has an assessment version,
task form, or work-start anchor. Real formal submissions with a missing attempt,
corrupt digest, or a practice-labelled envelope remain unavailable to feedback.

Historical unbound `assessment.response.v2` rows are ambiguous: absence of an
attempt alone cannot prove that the response was practice rather than a damaged
formal record. They are deliberately not relabelled or repaired. An identical
retry retains the original ID and digest and remains blocked with
`ASSESSMENT_ATTEMPT_MISSING`. Recovery needs a separate provenance-backed decision;
this patch performs no migration or historical replay/reset.

Integrate both commits together. The intermediate purpose-only commit could create
no-key practice responses without digests; any such records are also withheld by
the complete fix. They are not silently repaired.

## Verification

The initial service-to-worker reproduction failed before the fix with the reported
`context_integrity_error`, then passed after the purpose boundary was corrected.
The new regression module covers the HTTP route with real authentication and
SQLite persistence, deferring only API background execution so the actual offline
database worker must recover the accepted submission. It verifies accepted
feedback, completed continuation, a next approved activity, preserved explanation
evidence in the progress receipt, repeat execution without duplicate records, and
no `AssessmentAttempt` or `AssessmentDecision`. It also covers episode-only content
without an idempotency key.

The model-input regression uses the actual worker composition and real LLM
generator/judge adapters with a recording transport returning synthetic structured
outputs. Assertions inspect both requests, not merely the accepted status. Cases
include empty answer, code-only and mixed responses, injection-shaped learner
strings, revisions, exact/over-bound input, missing/corrupt digests, foreign revision
references, unreviewed tasks, unauthorised transfer content, private episode plans,
active course transfer, and cached release. No external model was called. Formal
frozen-response extraction and historical hashes remain unchanged.

Initial purpose fix: **114 focused tests passed** in 270.95 seconds, including the 15 new
regression cases. The two final retry cases also passed after adding a later task
edit to the fixture. Ruff lint and formatting passed for all five changed Python
files; `git diff --check` passed.

Complete follow-up: **80 tests passed** in 61.65 seconds, including all 15 original
practice regressions and 13 additional actual-model-input cases. The remaining
modules exercise the existing generator, judge, formal context/release and offline
worker. A revision fixture's serialization warning was corrected and that case
rerun separately. Ruff lint/format passed for all eight changed Python files.

```text
python -m pytest tests/test_typed_practice_model_input.py tests/test_typed_practice_feedback.py tests/test_feedback_agent.py tests/test_quality_judge.py tests/test_assessment_feedback_context.py tests/test_task16_feedback_release.py tests/test_assessed_feedback_integration.py tests/test_local_worker_template.py -q --basetemp=C:/Users/Jordan.Tran/AppData/Local/Temp/ll-typed-input-final --tb=short
```

The focused run used Python 3.11.16 from the existing root backend virtual
environment, `PYTHONPATH=.`, and a fresh short Windows temporary directory:

```text
python -m pytest tests/test_typed_practice_feedback.py tests/test_task14_lifecycle.py tests/test_assessment_feedback_context.py tests/test_activity_continuation.py tests/test_live_evidence.py tests/test_lms_core_api.py tests/test_local_worker_template.py tests/test_task16_feedback_context.py -q --basetemp=C:/Users/Jordan.Tran/AppData/Local/Temp/ll-typed-focused --tb=short
```

No full backend suite or remote provider calls are part of this delegated fix.
The research runtime switch remains off. The governance branch is preserved;
this branch is ready for coordinator integration, with no merge or push performed.
