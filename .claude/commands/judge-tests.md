---
description: Get an independent test-evidence verdict on the current diff against its plan
argument-hint: [plan path, defaults to the plan matching the diff]
allowed-tools: Task, Agent, Bash, Read, Grep, Glob
---

Plan: $ARGUMENTS

Diff scope: !`git diff --stat origin/main...HEAD`
Head SHA: !`git rev-parse HEAD`

Launch the `test-judge` subagent with the subagent tool — named `Task` on older CLI builds and `Agent` on
newer ones; both are allowed above, use whichever this session exposes. Give it the plan path, the head SHA, the diff scope,
and every local command you have already run with its exact result — including the ones that failed, were
skipped, or could not run.

You must not judge your own tests here, and you must not edit code or tests while this command runs. If the
verdict is `CHANGES_REQUESTED` or `INSUFFICIENT_EVIDENCE`, report it verbatim with the missing cases; do not
argue it down, and do not treat a passing subset as coverage of the whole.

Relay the subagent's full verdict block to the user.
