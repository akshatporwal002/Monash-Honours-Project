# Harness decisions

Recorded: 2026-08-14

1. Every repository change follows evidence, plan, implementation, tests, local reviews, then human PR review.
2. Plans live under `docs/plans/NNN-<slug>.md` and use step-level checklists plus acceptance lines.
3. Draft PRs may exist during work. They are not marked ready and reviewers are not requested until all gates pass.
4. The GitHub Workflow Agent manages Git and PR state.
5. The Test Judge, Code Reviewer, and Code Quality Reviewer issue separate read-only verdicts.
6. Skills cover implementation plans, pull requests, commit messages, and future skill creation.
7. A new head diff makes affected test and reviewer evidence stale.
