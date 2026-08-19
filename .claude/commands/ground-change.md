---
description: Ground a requested change in current files, tests, CI, and product rules before any planning or code
argument-hint: <requested outcome and optional scope>
allowed-tools: Read, Grep, Glob, Bash, Write, Task, Agent
---

Requested outcome: $ARGUMENTS

Current worktree state:
- Branch: !`git branch --show-current`
- Status: !`git status --short`
- Recent commits: !`git log --oneline -5`
- Existing plans: !`ls docs/plans`

Follow `.agents/commands/ground-change.md`. Produce a grounded change record using the structure in
`.agents/context/change-record-template.md`.

Do this:

1. Read the controlling docs for the affected requirement, in order:
   `docs/01-implementation-requirements.md`, `docs/02-pass-incomplete-bloom-assessment-spec.md`,
   `docs/03-codex-implementation-work-order.md`.
2. Locate every affected path under `src-main` — frontend, backend, data, contracts, tests — plus the
   relevant jobs in `.github/workflows/quality.yml`.
3. Trace current behaviour end to end: input, permission and scope checks, services, storage, output,
   audit, failure handling.
4. Classify each relevant requirement as `IMPLEMENTED`, `PARTIAL`, `MISSING`, `CONFLICTING`, or `UNVERIFIED`,
   each with `path:line`, symbol, or test evidence.
5. List missing data, policy conflicts, and unverified claims with owner and blocking effect. Do not guess
   a product rule, and do not let a filename or route name stand in for behaviour.

Do not edit implementation files in this command. Output the change record in chat; write it to a file only
if the user asks. End by stating whether grounding is sufficient to plan, or what is still missing.
