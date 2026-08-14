---
name: draft-pull-request
description: Draft or update a GitHub pull request from an approved implementation plan, repository diff, commits, and test evidence. Use when opening a draft PR, updating its body during implementation, checking review readiness, marking it ready, or requesting reviewers.
---

# Draft Pull Request

Make the PR an exact review record. Never write it from memory or a branch name alone.

## Gather evidence

Read:

1. The matching `docs/plans/NNN-*.md` file.
2. The base-to-head diff and commit list.
3. Changed migrations, generated contracts, tests, and docs.
4. Local test output and GitHub check results.
5. The four agent verdicts recorded in the change context.

Reject unsupported claims. A test file in the diff does not mean the test passed.

## Keep the plan and PR aligned

Use `references/pr-template.md`. Mirror every plan step, checklist item, and acceptance line in the same order. For each item, record its current state and link it to files, tests, or an open reason.

Include:

- Outcome and scope boundaries.
- Requirement IDs and source evidence.
- Current-state problem and implemented design.
- Every plan step and its acceptance result.
- Migration, compatibility, rollback, privacy, access, and audit notes.
- Exact verification commands and results.
- Manual checks and their limits.
- Risks, missing data, deferred work, and known failures.

Do not shrink a detailed plan into a short PR summary.

## Manage draft state

Open the PR as a draft while implementation is active. Update the body as evidence changes.

Do not mark it ready or request human review until all are true:

- The implementation plan exists and matches the diff.
- Every plan acceptance line is met or clearly deferred with approval.
- The Test Judge returns `APPROVED`.
- The Code Reviewer has no open blocking finding.
- The Code Quality Reviewer has no open blocking finding.
- Required local checks pass.
- Required GitHub checks pass, or the PR states why a non-required check could not run.
- No unresolved critical security, privacy, data-loss, access, or assessment-validity risk remains.

When a gate fails, keep the PR draft and list the failed gate with its owner and next action.

## Use GitHub safely

Verify the remote, base branch, current branch, and authentication before any write. The current repository default is `main`, but always check live state before opening a PR.

Never force-push, dismiss reviews, bypass branch protection, merge, or request reviewers without the authority provided by the task. Do not stage or commit unrelated files.
