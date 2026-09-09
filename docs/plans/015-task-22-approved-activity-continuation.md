# Task 22 plan and contract audit

Scope: Task 22 only. Work alone. All changes stay uncommitted.
Base: 65a9457d27e849465e7f227471336552bb22b8b4 plus 60 inherited Task 21 files.
The dependency receipt records SHA256 hashes. Task 20's 38 inherited hashes match its original worktree.
Both source worktrees remain untouched. Available disk at start: 74,720,645,120 bytes.
No repository AGENTS.md files were found. The user-provided writing rules apply.

## Contracts and boundaries

The feedback transaction stores terminal output and a continuation outbox intent.
The outbox creates one ContinuationJob per workflow. Feedback remains available if later work fails.
Only completed accepted or regenerated feedback with an accepted record and approved judge is eligible.
Safe fallback and failed feedback never establish learning success or trigger model inference.
Judge approval checks feedback quality, not learner mastery. New observations must remain uncertain.

ProgressUpdate and NextTaskRequest will carry the execution token. Each adapter obtains the database write lock,
checks the token and unexpired lease, verifies the authoritative workflow/submission scope, and checks again before commit.
The model repository gains an explicit caller-owned transaction mode, preserving standalone behavior.
A workflow-keyed progress receipt and its model snapshot commit together. Replays return that receipt.
A separate workflow-keyed suggestion commits with approved candidates and its frozen decision context.
This permits restart between model update and recommendation without duplicate state.
Model head checks and the existing Task 19 correction consumer remain authoritative.

A nullable next-task reference represents a completed decision with no activity.
The decision records its reason, uncertainty, evidence IDs, model snapshot, rule version, preferences, and pathway version.
Insufficient/conflicting evidence, opt-out, stale approval, and no eligible activity are explicit states.
Learner actions use expected history version and request key. Educator overrides require course ownership and a reason.
All action candidates are revalidated against current scope, approval, and existing Task 21 prerequisite rules.
No action changes assessment conditions, results, or diagnostic bypass authority.

## Implementation and tests

1. Add protected progress receipts, suggestions, and action history with replay-safe additive migration.
   Test atomic rollback, migration replay, immutable history, concurrency, and populated downgrade denial.
2. Implement deterministic adapters and replace shipped worker placeholders.
   Test actual wiring, checked-state eligibility, duplicate delivery, restart, expired claims, and stale workers.
3. Add scoped read/action routes and mounted learner and educator controls.
   Test strict DTOs, revoked access, changed approvals, choice history, reload, and failed-save draft retention.
4. Run authenticated UI/API feedback-to-choice journey and required local quality checks.
5. Perform separate Standards, Spec, and Test Judge self-reviews, fix blockers, and record exact results.
   Update task list, requirement matrix, coordinator record, and Task 22 handoff. Stop before Task 23.
