---
name: draft-implementation-plan
description: Inspect LearnLens source files, trace current behaviour, and write a numbered implementation plan under docs/plans. Use for feature work, fixes, migrations, refactors, or policy changes — any request that needs a plan before code changes begin. Normally reached through the /draft-plan command.
---

# Draft Implementation Plan

**Canonical contract: `.agents/skills/draft-implementation-plan/SKILL.md`. Read it now and follow it
exactly.** Template: `.agents/skills/draft-implementation-plan/references/plan-template.md`.

This file deliberately does not restate that contract. A second copy is how the two versions drift, and
CLAUDE.md treats drift between `.agents/` and `.claude/` as a bug. Only Claude-specific notes belong here.

## Claude-specific notes

- Reached through `/draft-plan`, which injects live `git status` and the `docs/plans` listing as command
  context. When invoked directly, gather that state yourself first.
- `docs/plans` already contains duplicated numbers (two `002-` files). Check for a collision before
  choosing `NNN`; `.claude/scripts/check-harness.ps1` reports duplicates.
- Do not implement the change while using this skill. The `plan-gate.ps1` hook will remind you if an edit
  under `src-main` happens with no plan touched on this branch, but it is advisory and will not stop you.
