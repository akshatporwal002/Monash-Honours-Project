# /prepare-pr

Input: plan, current diff, commits, verification output, three reviewer verdicts, and current GitHub checks.

Invoke `$draft-pull-request` through the GitHub Workflow Agent. Open or update a draft PR. Mark it ready and request human review only after `.agents/hooks/before-review-request.md` passes.

Return the PR link, head SHA, check state, and any open gate.
