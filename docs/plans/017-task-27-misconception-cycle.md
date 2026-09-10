# Task 27: misconception check and recovery

9 September 2026. Dependencies 18, 19, 21, 22 and 23 are on the current main.
Task 25's connected checks are being verified in the same worktree.

10 September update: implementation and independent review are complete locally.
The [delivery record](../learnlens/task-27-misconception-cycle.md) records the
behaviour, resolved findings, full regression and passing corrective checks.
Local verification is complete. Tasks 25, 27 and 29 share one delivery branch.

## Current gap

The code defines misconception states and a learner-model evidence type. It has
no learner/educator workflow for a probe, alternate explanation, revision and
fresh check. Task 28's queues cannot yet receive unresolved-cycle signals.

## Planned behaviour

- A course educator opens a possible-misconception check from scoped saved evidence.
  The educator records the hypothesis, probe, alternate explanation, fresh question
  and reason. These reviewed teaching conditions are frozen for that cycle.
- The learner records a probe response, reviews the alternate explanation, revises,
  and answers the fresh question without instructional hints in the check workspace.
- Each response is a new observation. New work never overwrites earlier responses.
- Educator reviews retain supporting and contradicting evidence, state, reason and
  version. Initial hypotheses remain uncertain; one answer cannot become a diagnosis.
- Unresolved cycles reach the existing human queue with an idempotent signal.
- Learners and educators can inspect the complete scoped history and corrections.
- Formal assessment, access standards and research participation remain separate.

## Verification

Use real service, route, persistence and browser checks. Cover cross-course and
cross-learner denial, stale writes, exact retries, stage ordering, hidden fresh
prompts, correction history, escalation replay and unchanged formal results.
Use a forward migration with protected-history downgrade guards.

This plan records implementation scope. It does not approve live teaching content,
research processing, a diagnosis or automatic assessment.
