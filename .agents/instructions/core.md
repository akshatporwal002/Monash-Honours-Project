# Core operating instructions

## Use the mandatory sequence

Work in this order:

1. Ground the request in current files, tests, runtime evidence, and product rules.
2. Write the implementation plan to `docs/plans/NNN-<slug>.md`.
3. Implement only approved plan steps.
4. Test each step, then run the required release checks.
5. Obtain independent Test Judge, Code Reviewer, and Code Quality Reviewer verdicts.
6. Let the GitHub Workflow Agent mark the PR ready and request human review.

Never collapse grounding into planning or implementation. Never use implementation as a way to discover an unstated product rule.

## Use the right source order

Read these controlling files in order:

1. `docs/01-implementation-requirements.md`
2. `docs/02-pass-incomplete-bloom-assessment-spec.md`
3. `docs/03-codex-implementation-work-order.md`

Then inspect the actual implementation and tests under `src-main`. Use `.github/workflows/quality.yml` for current CI commands. When docs and code conflict, report the conflict and follow the controlling docs for planned behaviour.

## Preserve current work

Inspect the worktree before editing. Treat existing changes as user-owned. Do not discard, overwrite, stage, commit, or reformat unrelated files. Use forward migrations and keep old data readable until conversion proof exists.

## Report exact proof

Use file paths, symbols, requirement IDs, commands, test names, and results. State `NOT RUN`, `UNVERIFIED`, or `BLOCKED` when proof is absent. A build, route name, HTTP 200 response, or passing unit test proves only its own scope.

## Keep decisions visible

Do not hide product policy in prompts, constants, fixtures, or default branches. Record missing decisions in the plan with an owner and blocking effect.
