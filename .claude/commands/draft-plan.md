---
description: Write the next numbered implementation plan under docs/plans from a grounded change record
argument-hint: <requested outcome, or the grounding record>
allowed-tools: Read, Grep, Glob, Bash, Write, Edit, Skill
---

Requested outcome: $ARGUMENTS

Existing plans: !`ls docs/plans`
Worktree: !`git status --short`

Invoke the `draft-implementation-plan` skill and follow it. The skill points at the canonical contract in
`.agents/skills/draft-implementation-plan/SKILL.md` and the template beside it — read both there rather
than from a summary here, because a summary is how this command and the contract drift apart.

Two things this command adds beyond the contract:

- The live state above is already gathered. Do not re-run it.
- Report back: the plan path, mapped requirement IDs, open decisions with owners, and whether the plan was
  committed or pushed (only if the task authorised Git writes).

Do not implement the change in this command.
