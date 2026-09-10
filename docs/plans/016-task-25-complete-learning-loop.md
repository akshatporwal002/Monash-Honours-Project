# Task 25: complete quantum learning loop

Implementation started 9 September 2026 from local main `34d686f`.
The worktree was clean. This records the Task 25 implementation baseline.

## Scope

Prove a single learning journey across the delivered task, episode, simulation,
feedback, evidence, learner-model, continuation, tutor and human-assessment services.
Use isolated synthetic records and existing approval controls. A fixture approval
does not activate a course, study or automatic AI assessment for real learners.

## Evidence and planned work

- The older `test_mvp_learning_loop.py` exercises numeric practice tasks. It does
  not prove the current episode, model, continuation or human-assessment journey.
- Task 14 tests cover episode submission and revision. Task 16 tests cover grounded
  feedback. Task 22 tests cover continuation using prebuilt accepted feedback.
- Existing browser journeys test those pieces separately. Add a repeatable journey
  that connects them, using the shipped local providers and database worker.
- Preserve exact response versions, source links, simulation runs and revision links.
- Interrupt processing after acceptance, restart, and check that accepted work and
  downstream records survive without duplication.
- Check unaided transfer, result visibility, human confirmation and reload.
- Fix defects exposed by these checks, then update the task list with the exact
  scope and limits of passing evidence.

## Verification

Run focused backend integration and browser checks first. Then run affected
regression, formatting, lint, generated-contract, frontend and migration checks.
Record failures and successful reruns separately. No live provider, expert-content
approval, study approval, native Safari or manual accessibility claim follows
from synthetic local tests.
