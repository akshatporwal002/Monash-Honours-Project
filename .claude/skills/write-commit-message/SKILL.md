---
name: write-commit-message
description: Write a truthful conventional commit message for LearnLens from the staged Git diff and verified test evidence. Use when preparing, revising, or checking commit subjects and bodies, including plan-only commits. Normally reached through the github-workflow subagent.
---

# Write Commit Message

**Canonical contract: `.agents/skills/write-commit-message/SKILL.md`. Read it now and follow it exactly.**

This file deliberately does not restate that contract — see the note in
`.claude/skills/draft-implementation-plan/SKILL.md`. Only Claude-specific notes belong here.

## Claude-specific notes

- **Trailer override.** The canonical contract says not to add co-author trailers unless the user asks.
  Claude Code's own operating contract requires every commit message to end with:

  ```text
  Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
  ```

  In Claude Code that trailer requirement wins; everywhere else the canonical rule stands. This is a
  deliberate divergence between the two files, not drift. Nothing else changes — no other trailers
  unless the user asks for them.
- `git commit` sits in the `ask` permission tier, and amending a commit is denied by both
  `settings.json` and `guard-bash.ps1`. Correct a bad message with a new commit, never with a rewrite.
