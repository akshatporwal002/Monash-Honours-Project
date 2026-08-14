---
name: write-commit-message
description: Write a truthful conventional commit message from the staged Git diff and verified test evidence. Use when preparing, revising, or checking commit subjects and bodies, including plan-only commits.
---

# Write Commit Message

Base the message on staged content, not intended work.

## Inspect first

1. Read `git status --short`.
2. Read `git diff --cached --stat` and `git diff --cached`.
3. Check recent subjects for repository conventions.
4. Separate unrelated staged changes before drafting a message.
5. Gather only tests that actually ran for this staged change.

If nothing is staged, stop and report that no commit message can be grounded yet.

## Write the subject

Use this form:

```text
type(scope): imperative summary
```

Choose from `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `ci`, `build`, `perf`, or `revert`. Use a short project area as the scope. Keep the subject under 72 characters when practical. Describe the result, not the editing action.

For a plan-only commit, use the exact contract:

```text
docs(plans): add plan NNN <slug> [skip ci]
```

## Add a body when it helps

Explain why the change exists, the key behaviour or data effect, and any migration or compatibility note. Add a `Tests:` line only for commands that completed. Use `Tests: not run (<reason>)` when the user needs that limit recorded.

Do not claim a requirement is complete from a partial test. Do not add co-author trailers unless the user asks for them.
