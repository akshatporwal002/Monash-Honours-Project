# Local Git connector

Use Git for status, diff, history, branches, staging, and commits.

Read before write:

```text
git status --short
git diff
git diff --cached
git log --oneline
git branch --all
git remote -v
```

Stage explicit paths. Never use broad staging when unrelated work exists. Never reset, clean, force-push, rewrite history, or discard another person's changes through this connector.

Commit messages use `$write-commit-message` and must describe the staged diff.
