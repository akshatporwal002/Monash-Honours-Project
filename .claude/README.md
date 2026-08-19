# Claude Code harness

This is the Claude Code projection of the harness in `.agents/`. Same contract, native mechanisms.
`.agents/` stays the single source of truth for rules and role definitions; the files here are thin and
point back to it, so a rule is changed in one place.

| `.agents/` concept | Claude Code mechanism | Where |
| --- | --- | --- |
| `AGENTS.md`, `instructions/core.md` | Auto-loaded project memory | `CLAUDE.md` (repo root) |
| `agents/*.md` | Subagents with restricted tools | `.claude/agents/*.md` |
| `commands/*.md` | Slash commands with live `!` context | `.claude/commands/*.md` |
| `skills/*/SKILL.md` | Skills (model-invoked) | `.claude/skills/*/SKILL.md` |
| `hooks/*.md` (checklists) | Executable hooks | `.claude/hooks/*.ps1` + `settings.json` |
| `permissions/policy.md` | Permission rules | `.claude/settings.json` |
| `rules/`, `guardrails/`, `memory/`, `workflows/`, `tools/` | Referenced from the above | unchanged in `.agents/` |

`.agents/harness.yaml` describes states and gates for readers and for other harnesses. Nothing in
Claude Code consumes it; it is documentation, not configuration.

## Thin means thin

The files under `.claude/skills/` and `.claude/agents/` carry frontmatter, a pointer to their canonical
`.agents/` contract, and Claude-specific notes only. They deliberately do **not** restate the contract:
a second copy is exactly how the two versions drift, and CLAUDE.md calls that drift a bug.

Run `.claude/scripts/check-harness.ps1` to verify it. It checks that every projection cites its canonical file,
that every hook registered in `settings.json` exists on disk, and that `docs/plans` has no duplicated
`NNN` prefix. It is not wired into `.github/workflows/quality.yml` — adding a CI job is a separate,
authorised change. Run it by hand after touching the harness.

`.claude/scripts/test-guard-bash.ps1` is the regression suite for the Bash guard, with cases in
`.claude/scripts/harness-tests/guard-bash-cases.txt`. The guard's rules are regexes, so its failure mode is a
silent hole rather than an error: every destructive rule has a case that must be denied, and every safe
sibling form a case that must still be allowed. Run it after any edit to `guard-bash.ps1`.

Two divergences are deliberate and are labelled as such in the files that carry them: Claude Code's own
operating contract requires the `Co-Authored-By` commit trailer and the generated-by PR footer, which the
tool-neutral canonical skills tell you to omit. In Claude Code the trailer requirement wins.

## Subagents

`test-judge`, `code-reviewer`, and `code-quality-reviewer` have no `Edit` or `Write` tool. The harness rule
"the implementing agent cannot approve its own work" is therefore enforced by tool configuration, not by
good intentions. `github-workflow` can write, but cannot merge, force-push, or dismiss reviews — that is
denied in `settings.json` and again in the Bash hook.

The three reviewers run on the session model (`model: inherit`); their judgement is the product.
`github-workflow` is pinned to `model: sonnet` — it fills a PR template and calls `gh`, and paying Opus
rates for that on every delivery cycle buys nothing.

## Commands

`/ground-change`, `/draft-plan`, `/quality-checks`, `/judge-tests`, `/review-change`, `/prepare-pr`.
Each injects live git state via `!` backtick execution so the agent starts from real state, not memory.

The commands that spawn subagents list both `Task` and `Agent` in `allowed-tools`. The subagent tool was
renamed between CLI versions, and a command that names only the old one silently loses subagent access —
which would quietly disable exactly the three independent verdicts this harness exists to enforce.

## Hooks

| Hook | Event | Behaviour |
| --- | --- | --- |
| `session-start.ps1` | SessionStart | Injects branch, head SHA, dirty-file count, latest plans, and the delivery order. Replays `.delivery-state.md` when it belongs to this branch. |
| `guard-bash.ps1` | PreToolUse(Bash) | **Denies** force-push, remote-branch deletion, hard reset, clean, checkout/restore over the worktree, discard-changes, stash destruction, forced branch/worktree deletion, ref deletion, history rewrites, recursive force deletes, `gh pr merge`/`close`, review dismissal, and branch-protection edits. Also **denies** secret-file reads. **Asks** on `gh pr ready`, with ledger state attached. |
| `plan-gate.ps1` | PreToolUse(Edit\|Write\|NotebookEdit) | **Advisory.** When product code under `src-main` is edited with no plan touched in the worktree or on the branch, injects a reminder pointing at `/draft-plan`. Caches the positive answer per branch. |
| `backend-lint.ps1` | PostToolUse(Edit\|Write\|NotebookEdit) | Runs `ruff check` and `ruff format --check` on the single edited backend `.py` file; exit 2 feeds failures straight back for a fix. |
| `frontend-lint.ps1` | PostToolUse(Edit\|Write\|NotebookEdit) | The same, with ESLint, for edited files under `src-main/frontend`. |
| `verdict-ledger.ps1` | SubagentStop | Appends `{agent, sha, session, at}` to `.claude/.verdict-ledger.jsonl` when a subagent finishes. |
| `pre-compact.ps1` | PreCompact | Writes branch, head SHA, plans touched, and recorded reviewer runs to `.claude/.delivery-state.md` before the transcript is summarised. |

Every hook fails open: a missing `uv`, a detached head, or a malformed payload exits 0 and changes nothing.
The plan gate is advisory on purpose — a hard block would wedge legitimate hotfixes and plan revisions.

`backend-lint.ps1` calls `src-main/backend/.venv/Scripts/ruff.exe` directly when it exists, falling back to
`uv run --frozen ruff`. Two `uv` bootstraps per edited file cost seconds on Windows for an identical result.

### What the ledger is and is not

`verdict-ledger.ps1` records that a reviewer subagent *ran* at a given head SHA. It cannot record a
*verdict* — a hook never sees one. So the ledger can prove a reviewer did not run at this SHA; it can
never prove one approved. `guard-bash.ps1` surfaces it as an `ask` on `gh pr ready` rather than a deny,
because a verdict obtained in an earlier session is legitimate and invisible to the ledger.

The field naming the subagent type has moved between CLI versions, so the hook tries several spellings and
records `unknown` rather than guessing. If entries come back as `unknown`, the readiness prompt degrades to
uninformative — it never wrongly blocks.

## Known limits

- **Bash-based edits skip the gates.** `plan-gate.ps1` and the two lint hooks fire on `Edit`/`Write`/
  `NotebookEdit`. An in-place edit through Bash (`sed -i`, a heredoc, `python -c`) is invisible to all
  three. Only the read-only `sed -n` form is allowlisted, but nothing stops the rest.
- **`guard-bash.ps1` matches the whole command string.** A heredoc that merely *quotes* a blocked command
  is denied along with one that runs it, so this file and `settings.json` cannot be rewritten through Bash.
  That is deliberate — a heredoc can write a script that is executed later — so edit them with the
  `Write`/`Edit` tools.
- **The verdicts themselves are still agent-followed.** Nothing here can stop the model from claiming a
  verdict it never got; the ledger narrows the gap without closing it.
  `.github/workflows/quality.yml` and branch protection remain the only real enforcement. Treat this
  harness as a strong default, and keep CI as the thing that actually says no.
