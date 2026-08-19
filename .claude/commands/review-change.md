---
description: Run the correctness and code-quality reviewers as two independent read-only passes over the current diff
argument-hint: [plan path and test-judge verdict]
allowed-tools: Task, Agent, Bash, Read, Grep, Glob
---

Context: $ARGUMENTS

Diff scope: !`git diff --stat origin/main...HEAD`
Head SHA: !`git rev-parse HEAD`

Launch the `code-reviewer` and `code-quality-reviewer` subagents with the subagent tool — named `Task` on
older CLI builds and `Agent` on newer ones; both are allowed above, use whichever this session exposes.
Send both in a single message so they run concurrently. Give each the plan path, the head SHA, the diff scope, the test-judge verdict, and
the verification output you already have.

Keep their findings and verdicts separate — do not merge, dedupe, or summarise away a finding. Report both
verdict blocks in full, then list the blocking findings you intend to fix.

Any commit after this point invalidates both verdicts for the affected code; re-run this command on the new
head. Do not request human PR review from this command.
