# Task 18: Shared learner model from live evidence

## Outcome

The learner-model service now has one controlled `update` operation. It accepts
only scoped evidence IDs with support-or-contradiction relations from a
versioned trusted adjudicator, reads immutable Task 17 evidence, and appends a
complete learner/course/outcome snapshot when the cumulative state changes.

The returned teaching view contains the snapshot chain position, model and rule
versions, uncertainty, recency, reason code, and relation-bearing evidence
links. Rule-based outputs always state `validated=False` with the
`UNVALIDATED_RULE_ESTIMATE` classification. That label describes inference
validity; it is not an assessment result.

## Consistency and boundaries

- Snapshot and estimate IDs derive from canonical scope, predecessor, versions,
  and evidence relations. Reordered or repeated work returns the existing
  snapshot without a duplicate write.
- Repository head checks and bounded service retries preserve one linear history
  when independent workers process overlapping evidence. Stored snapshots,
  estimates, and links remain append-only.
- The rules keep understanding, possible misconception, assistance, feedback
  use, and transfer in distinct dimensions. Event occurrence alone does not
  establish understanding, improvement, dependence, or successful transfer.
- The service has no learner-controlled write route and does not implement
  recommendations, formal assessment, learner corrections, or educator views.
  Those belong to later tasks.

## Verification

`test_learner_model.py` covers trusted-adjudication controls, rule semantics,
real persisted evidence scope, cumulative snapshots, replay, two-session
concurrency, stale-head rebuilding, protected history, teaching-view safety,
and provider/review failures. The repository's existing migration test confirms
the established append-only tables remain valid; Task 18 adds no migration.

The [implementation plan](../plans/011-task-18-shared-learner-model.md)
records the rule meanings, concurrency model, and deferred Task 22/23 decision
behavior.
