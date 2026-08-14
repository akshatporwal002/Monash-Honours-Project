# Change delivery workflow

## Entry conditions

Start with a user outcome and permission to make repository changes. Record scope, affected users, and any requested GitHub action. Read `.agents/permissions/policy.md` before external writes.

## Stage 1: Ground

Use `/ground-change`.

- Inspect worktree, branches, repository layout, code, tests, docs, and CI.
- Read the three controlling root docs.
- Trace the affected behaviour from input through access, service, data, output, audit, and failure paths.
- Classify each relevant requirement as `IMPLEMENTED`, `PARTIAL`, `MISSING`, `CONFLICTING`, or `UNVERIFIED`.
- Record missing policy or evidence. Do not guess.

Exit only when current behaviour and gaps have file or runtime proof.

## Stage 2: Plan

Use `$draft-implementation-plan` and `/draft-plan`.

- Write `docs/plans/NNN-<slug>.md` before implementation.
- Give each step its own files, checklist, tests, and acceptance line.
- Map requirement IDs and failure cases.
- Commit and push the plan when the active task includes the normal Git publishing flow.

Run `.agents/hooks/before-implementation.md`. Do not continue on failure.

## Stage 3: Implement

Implement one plan step at a time.

- Keep the diff limited to the active step.
- Add tests with the behaviour.
- Use forward migrations and compatibility paths.
- Run the smallest relevant check after each edit.
- Run `.agents/hooks/after-implementation.md` after each step.

When evidence changes the design or scope, update the plan before continuing.

## Stage 4: Test

Use `/judge-tests` and `quality-checks.md`.

- Run targeted tests first.
- Run changed-area static, type, contract, migration, and build checks.
- Run the full release suite before review when the environment supports it.
- Record skipped, failed, flaky, stale, environment-blocked, and manual checks.
- Obtain the Test Judge verdict.

Return to implementation on `CHANGES_REQUESTED`. Keep the PR draft on `INSUFFICIENT_EVIDENCE`.

## Stage 5: Local review

Use `/review-change` after tests.

1. Code Reviewer checks correctness, safety, and LearnLens rules.
2. Code Quality Reviewer checks structure and static quality.
3. The implementing agent fixes findings and reruns affected tests.
4. Reviewers re-check the new head diff.

Both verdicts must be `APPROVED` for the current head.

## Stage 6: Prepare the PR

Use `$draft-pull-request` and `/prepare-pr`.

- A draft PR may be opened earlier for visibility.
- Keep its body aligned with the plan and current evidence.
- Wait for required GitHub checks on the current head SHA.
- Run `.agents/hooks/before-review-request.md`.
- Mark ready and request human review only when every hook item passes.

## Failure handling

- Missing product policy: stop at planning and request the owner decision.
- Test environment failure: record the exact failure and seek a safe alternate proof. Do not call it a pass.
- Reviewer disagreement: keep the PR draft and cite the conflicting evidence for human resolution.
- GitHub or authentication failure: preserve local commits and report the pending command.
- New changes after approval: invalidate stale test and reviewer verdicts, then rerun the affected gates.

## Completion

The workflow ends when the PR is ready for human review, not when code compiles. Merging and deployment need separate authority.
