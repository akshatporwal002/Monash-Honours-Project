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
using the implementation at the base commit. Existing behavior that only stores a
submission digest when an idempotency key is supplied is unchanged.

Retries hash against the version and binding information already stored on the
response. Exact retries return the original response; changed episode content,
whitespace, removed episodes, and foreign work references conflict with HTTP 409.
Later task edits do not change replay identity. No replay rewrites the stored
response or creates a duplicate workflow.

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

Practice feedback keeps the existing offline generator and context projection;
this patch does not add a semantic assessment of typed explanation content. Full
episode evidence continues into the learning-evidence and continuation readers.
Formal frozen-response extraction and evidence references are unchanged.

Validation: **114 focused tests passed** in 270.95 seconds, including the 15 new
regression cases. The two final retry cases also passed after adding a later task
edit to the fixture. Ruff lint and formatting passed for all five changed Python
files; `git diff --check` passed.

The focused run used Python 3.11.16 from the existing root backend virtual
environment, `PYTHONPATH=.`, and a fresh short Windows temporary directory:

```text
python -m pytest tests/test_typed_practice_feedback.py tests/test_task14_lifecycle.py tests/test_assessment_feedback_context.py tests/test_activity_continuation.py tests/test_live_evidence.py tests/test_lms_core_api.py tests/test_local_worker_template.py tests/test_task16_feedback_context.py -q --basetemp=C:/Users/Jordan.Tran/AppData/Local/Temp/ll-typed-focused --tb=short
```

No full backend suite or remote provider calls are part of this delegated fix.
The research runtime switch remains off. The governance branch is preserved;
this branch is ready for coordinator integration, with no merge or push performed.
