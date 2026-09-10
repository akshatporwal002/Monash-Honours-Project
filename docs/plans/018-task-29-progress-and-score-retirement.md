# Task 29: progress views and legacy score retirement

10 September 2026. This plan follows the local Task 25 and Task 27 changes.
Task 27's combined and corrective checks finished before this implementation.

## Required behaviour

Replace numeric learner marks with separate activity, evidence, uncertain model
estimates and formal binary results. Both learners and course educators need
scoped history for revision, reasoning, confidence, feedback use, teaching,
independence, transfer, misconception checks and adaptation. Indicators must open
the evidence that explains them. Missing evidence is not a zero or a failed result.

Authority: FR19, FR21, FR22, FR39 and work-order Phase 10. D-10 already approves
immediate retirement under `legacy-retirement-v1`. Its approval includes active
database columns after preservation. No compatibility window needs another vote.

## Findings before implementation

- `LmsService.submit` still converts practice checks to 100 or 40 and compares
  them with `passing_score`. Formal submissions already bypass that path.
- Learner and educator dashboards expose score averages. Educator analytics
  calls averages concept mastery. The at-risk projection also uses a score threshold.
- Feedback providers and the local template read numeric marks. The template
  uses those marks to claim whether a learning outcome was met.
- Learning analytics aggregates historical event marks. Its technical retrieval
  and judge measures have separate meanings and must remain available.
- `submission_attempts.score` and `student_submissions.score` have database check
  constraints. Attempt rows have protected histories and inbound foreign keys.
- The unmounted `students.py` router and its service retain a second numeric path.
  Shared demo data must be separated before that obsolete path is removed.
- Existing learner-result, outcome-result, evidence, learner-model, misconception
  and activity-history services provide the authority and scoped records to reuse.

## Implementation order

1. Preserve original legacy values and their source IDs in an immutable migration
   archive. Add a forward migration with count, payload and foreign-key checks.
   Retain protected attempts and existing assessment archives. Test failure
   rollback before removing active columns and settings.
2. Update all active writers, schemas, feedback inputs, event capture and
   analytics together. Submission validation must still reject invalid payloads.
   Practice participation cannot create a formal PASS or replace an approved
   pathway exit rule. Keep optional participation rewards and quantum probabilities.
3. Add read-only, course-scoped individual and cohort progress projections.
   Reuse released result policy and frozen evidence scope. Do not expose a hidden
   provisional result through a count, filter or label. Preserve uncertainty and
   supporting and contradicting references for estimates and changes.
4. Replace score controls and displays, link indicators to their scoped history,
   and show explicit empty states. Regenerate contracts and remove retired readers.
5. Verify fresh, populated, formal-only and mixed databases, repeated reads,
   cross-course denial, release visibility, rollback and real browser journeys.
   Run independent Spec and Standards reviews, then the affected combined checks.

## Completion and limits

The task is complete only when all active numeric learner-result paths are gone,
legacy history remains readable, scoped progress views work and checks pass.
Technical provider scores, simulation probabilities and protected historical values
retain their own meanings. The change does not approve live migration, study
activation, deployment or an educational validity claim.

The [delivery record](../learnlens/task-29-progress-and-score-retirement.md)
records the final changes, verification and migration limits.
