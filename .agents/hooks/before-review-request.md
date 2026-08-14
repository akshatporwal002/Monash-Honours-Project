# Before review request hook

Run before `gh pr ready`, reviewer assignment, or any human review request.

- Confirm the PR body mirrors the plan.
- Confirm every step acceptance line has current evidence.
- Confirm Test Judge verdict is `APPROVED`.
- Confirm Code Reviewer verdict is `APPROVED`.
- Confirm Code Quality Reviewer verdict is `APPROVED`.
- Confirm required GitHub checks pass for the current head SHA.
- Confirm failures, skipped checks, manual limits, risks, and open work are visible.

If any item fails, keep the PR draft. State the failed gate, owner, and next action.
