# Reviewed learning-progress indicators

Progress keeps recorded observations, uncertain model interpretations and released
assessment results separate. This update adds two tools for educator inspection.

Feedback indicators join acknowledgement evidence to a later revision or transfer
through the original response's `DERIVES_FROM` lineage, within one learner, course
and outcome. Time proximity or acknowledgement alone is insufficient. The record
links to all contributing evidence and remains `REVIEW_REQUIRED` with uncertainty
1: it does not establish that feedback caused improvement.

Question indicators identify explicit question-clarification language in the
learner's original tutor message. Scope and artifact digests are checked before
inspection. The cue may be a false positive; educators inspect the source wording
and context before interpreting it. The service does not infer a learner trait or
declare a defective question.

Indicators inspect the most recent 200 observations per learner and outcome.
Truncation is visible; missing older links do not become negative effectiveness
findings. Existing paged evidence views retain the full history. Rule version is
`progress-indicators.v1`.

Course owners can record an interpretation from the progress page, citing supporting
and contradicting observations, a reason and uncertainty. The model can represent
useful explanation forms, successful and unsuccessful strategies, and support needs,
alongside the existing outcome dimensions. The reason identifies the particular
strategy or form and its evidence. These are revisable, outcome-specific judgments,
not learning-style or fixed-ability labels.

`POST /api/v1/progress/{course_id}/learners/{learner_id}/outcomes/{outcome_id}/reviews`
requires an active course owner, an actively enrolled learner, CSRF
protection, exact in-scope evidence, an expected snapshot version and an idempotency
key. Stale versions and changed-key replays are rejected. A supported feedback-use
interpretation must cite acknowledgement, original response and a linked later
revision or transfer. The system does not supply that judgment automatically.

Each review appends a snapshot and correlated audit with the educator, reason,
request digest, evidence time, uncertainty and version. Existing dimensions and
snapshots remain available. Rule updates retain reviewed interpretations without
reusing human dimension-specific relations as unrelated rule adjudications. New
rule evidence does not silently replace a human interpretation. Existing learner
annotation and educator correction history remain available from progress.

Migration `20260911_0052` extends the learner-dimension constraint, preserves populated
snapshots, links and triggers, supports replay and refuses destructive downgrade.
The review path does not update assessment decisions, numerical scores, research
measures, or approved assessment standards. Statistical validity and pedagogical
effectiveness still require actual study and educator acceptance evidence.
