---
description: Open or update the draft PR, then check review readiness against every gate
argument-hint: [plan path and the three reviewer verdicts]
allowed-tools: Task, Agent, Bash, Read, Grep, Glob, Write
---

Context: $ARGUMENTS

Branch: !`git branch --show-current`
Head SHA: !`git rev-parse HEAD`
PR state: !`gh pr status 2>&1 | head -20`

Launch the `github-workflow` subagent with the subagent tool — named `Task` on older CLI builds and `Agent`
on newer ones; both are allowed above, use whichever this session exposes. Give it the plan path, the head SHA, the commit
list, the verification output, and all three reviewer verdicts (test-judge, code-reviewer,
code-quality-reviewer) with the head SHA each verdict applies to.

The subagent uses the `draft-pull-request` skill, keeps the PR a draft while any gate is open, and marks it
ready only when every item in `.agents/hooks/before-review-request.md` passes for the current head SHA.

A verdict issued against an older SHA is stale, not passing. Report the PR link, draft or ready state, head
SHA, check state, and every open gate with its owner and next action.
