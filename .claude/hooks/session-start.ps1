# SessionStart hook: put current worktree and plan state in front of the agent, and
# replay the delivery-state snapshot that pre-compact.ps1 leaves behind.
# Fails open: any error exits 0 with no output.
# ASCII only - PowerShell 5.1 parses .ps1 as ANSI.
# Uses --untracked-files=no: the repo carries many unreadable .tmp-* scratch dirs and a
# full untracked scan emits permission warnings and costs seconds.
$ErrorActionPreference = 'SilentlyContinue'
try {
    $root = $env:CLAUDE_PROJECT_DIR
    if (-not $root) { $root = (Get-Location).Path }
    Set-Location $root

    $branch = (git branch --show-current) -join ''
    $sha = (git rev-parse --short HEAD) -join ''
    $dirty = @(git --no-optional-locks status --porcelain --untracked-files=no)
    $plans = @(Get-ChildItem -Path (Join-Path $root 'docs/plans') -Filter '*.md' |
        Sort-Object Name | Select-Object -Last 3 -ExpandProperty Name)

    $lines = @()
    $lines += "LearnLens harness: branch '$branch' at $sha, $($dirty.Count) tracked file(s) changed in the worktree."
    if ($plans.Count -gt 0) { $lines += 'Latest plans: ' + ($plans -join ', ') + '.' }
    $lines += 'Delivery order is ground -> plan -> implement -> test -> independent review -> human PR review (see CLAUDE.md).'
    if ($dirty.Count -gt 0) {
        $lines += 'Uncommitted work exists and is user-owned: do not discard, reformat, or stage unrelated files.'
    }

    # Replay the pre-compaction snapshot when it belongs to this branch. Gate state is the
    # first thing a summary drops and the last thing that should be re-derived from memory.
    $state = Join-Path $root '.claude/.delivery-state.md'
    if (Test-Path $state) {
        $body = Get-Content $state
        if ($body -match [regex]::Escape($branch)) {
            $lines += ''
            $lines += 'Delivery state from before the last compaction (.claude/.delivery-state.md):'
            $lines += ($body | Where-Object { $_ -match '^- ' })
            $lines += 'Treat every gate above as stale until re-confirmed at the current head SHA.'
        }
    }
    $lines -join "`n"
} catch { }
exit 0
