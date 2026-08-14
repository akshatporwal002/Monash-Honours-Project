# GitHub MCP contract

Use a configured GitHub MCP or GitHub connector for semantic repository, pull request, review, and check operations. Prefer it over screen scraping.

## Read operations

- Resolve repository, default branch, current pull request, head SHA, checks, and review threads.
- Read changed files, commits, branch protection, and review state.
- Re-read state before any write because GitHub data may change.

## Write operations

Use only with permission from `.agents/permissions/policy.md`:

- Create or update a draft PR.
- Add a plan-matched body.
- Mark a PR ready after all gates pass.
- Request named reviewers when authorised.
- Reply to review threads after fixes are verified.

Never merge, dismiss reviews, bypass protection, or write secrets through this tool unless a separate task grants that exact authority.

If no GitHub MCP is configured, use the local `gh` connector contract. Do not pretend a remote write occurred.
