# Task 17: Live learning evidence

## Outcome

The learner workflow now writes append-only learning evidence alongside the
authoritative action that created it. It covers prediction checkpoints, approved
support use, submitted responses, episode reasoning, explanation, reflection,
transfer, revisions, referenced simulations, terminal simulation faults, and an
explicit learner acknowledgement of validated feedback.

The learner task evidence endpoint returns metadata only. Protected content and
frozen provenance remain in authorised evidence artifacts. It does not expose an
assessment result, source passage, peer data, model estimate, or correction.

## Boundaries

- Task 17 connects real learner actions to the existing evidence store. It does
  not build a learner model, recommendations, corrections, educator evidence
  views, research processing, or formal-result changes.
- The evidence repository can now flush without committing when called from a
  source command. A failed evidence write therefore rolls back that source
  command; existing standalone callers retain their atomic commit behaviour.
- Feedback use is recorded only after a learner deliberately selects “I've
  reviewed this feedback.” Polling or rendering feedback creates no evidence
  record.
- A supported-stage hint applies only to actions in that stage and before the
  action's timestamp. Accessibility support remains a separate condition.

## Provenance and recovery

Each record has server-derived learner, course, outcome, task, activity, source
interaction, response, frozen task-form/review context, conditions, timestamp,
content digest, and opaque audit reference. Revision and explicitly referenced
simulation records use immutable evidence links. The original records and
artifacts are never modified.

Simulation terminal evidence is written in the outcome transaction. A capture
failure rolls back that outcome and its evidence together. The durable recovery
worker can later record one terminal fault observation after the run expires.

## Verification

Focused Task 17 tests cover ordered capture, replay, submission failure rollback,
support and accessibility separation, pagination, metadata-only reads, learner
scope denial, revision links, optional-prediction simulations, simulation
recovery, explicit simulation references, feedback acknowledgement, and
concurrent replay.

Repository migration checks, contracts, lint, format, backend, frontend, and
browser checks are recorded only after their final commands finish. This document
does not make a hosted, manual accessibility, learning-validity, or release-ready
claim.

## Follow-on work

Task 18 may consume the scoped ordered observations to build a separately
versioned, uncertainty-aware learner model. Task 19 owns model correction and
educator-facing evidence views.
