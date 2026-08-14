# GitHub CLI connector

Use `gh` only when authenticated for the intended repository.

Useful read operations:

```text
gh repo view
gh pr status
gh pr view --json state,isDraft,headRefOid,statusCheckRollup,reviews
gh pr checks
```

Allowed writes depend on the active permission:

```text
gh pr create --draft
gh pr edit
gh pr ready
gh pr edit --add-reviewer <name>
```

Check the base branch and current head SHA before every write. Keep the PR draft when any harness gate is not approved. Do not merge, close, or alter reviews through this connector without separate authority.
