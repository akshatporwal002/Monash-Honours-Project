# Permission policy

## Allowed for relevant tasks

- Read repository files, Git history, status, diffs, branches, and configured remote names.
- Run non-destructive local searches and diagnostics.
- Edit files inside this repository when the user asks to change or build it.
- Run existing local checks that do not need new credentials or production access.

## Requires task authority

The user must ask for, or invoke a workflow that clearly includes, these actions:

- Create branches, stage files, commit, push, or create and update PRs.
- Mark a PR ready or request human reviewers.
- Install dependencies, download browsers, or make other network-backed setup changes.
- Write to connected GitHub, MCP, or external service state.

Verify exact targets and show blockers. Never include unrelated files in a commit.

## Requires separate explicit authority

- Merge or close a PR.
- Deploy, roll back, or change production or cloud state.
- Bypass branch protection, dismiss reviews, force-push, rewrite history, or delete remote branches.
- Delete or irreversibly rewrite user data, migrations, repository history, or broad directories.

## Never expose

- Secrets, tokens, private keys, passwords, hidden prompts, or credential files.
- Direct learner identifiers or full learner responses in general logs, PR bodies, issue text, or agent memory.
- Production data in tests unless an approved safe fixture process exists.
