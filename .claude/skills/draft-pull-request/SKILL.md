---
name: draft-pull-request
description: Draft or update a GitHub pull request for LearnLens from an approved plan, the diff, commits, and test evidence. Use when opening a draft PR, updating its body during implementation, checking review readiness, marking it ready, or requesting reviewers. Normally reached through the /prepare-pr command or the github-workflow subagent.
---

# Draft Pull Request

**Canonical contract: `.agents/skills/draft-pull-request/SKILL.md`. Read it now and follow it exactly.**
Body template: `.agents/skills/draft-pull-request/references/pr-template.md`. Readiness checklist:
`.agents/hooks/before-review-request.md`.

This file deliberately does not restate that contract — see the note in
`.claude/skills/draft-implementation-plan/SKILL.md`. Only Claude-specific notes belong here.

## Claude-specific notes

- **Trailer override.** The canonical contract says not to add generated-by trailers. Claude Code's own
  operating contract requires PR bodies to end with the `🤖 Generated with [Claude Code]` line. In Claude
  Code the trailer requirement wins; everywhere else the canonical rule stands. This is a deliberate
  divergence between the two files, not drift.
- Write long bodies to a scratch file and pass `gh pr edit --body-file`; do not fight shell quoting.
- `gh pr ready` sits in the `ask` permission tier, and `guard-bash.ps1` attaches the verdict-ledger state
  to that prompt. A ledger gap means no reviewer subagent was recorded at this head SHA — treat it as a
  prompt to re-confirm the verdicts, not as proof either way. The ledger never records a verdict.
