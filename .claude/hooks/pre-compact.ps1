# PreCompact hook: persist delivery-stage state before the transcript is summarised.
# Which gate passed at which SHA is exactly what a summary drops, and it is the state
# the whole change-delivery workflow depends on. session-start.ps1 reads this back.
# Fails open: any error exits 0 with no output.
# ASCII only - PowerShell 5.1 parses .ps1 as ANSI.
$ErrorActionPreference = 'SilentlyContinue'
try {
    $root = $env:CLAUDE_PROJECT_DIR
    if (-not $root) { $root = (Get-Location).Path }

    $branch = (& git -C $root branch --show-current) -join ''
    $sha = (& git -C $root rev-parse HEAD) -join ''
    $dirty = @(& git -C $root --no-optional-locks status --porcelain --untracked-files=no)
    $plans = @(& git -C $root --no-optional-locks status --porcelain --untracked-files=no -- docs/plans)

    $ledger = Join-Path $root '.claude/.verdict-ledger.jsonl'
    $atHead = @()
    if ($sha -and (Test-Path $ledger)) {
        foreach ($line in (Get-Content $ledger)) {
            if (-not $line) { continue }
            $e = $line | ConvertFrom-Json
            if ($e -and $e.sha -eq $sha) { $atHead += $e.agent }
        }
    }
    $atHead = @($atHead | Sort-Object -Unique)

    $lines = @()
    $lines += '# Delivery state snapshot (written by .claude/hooks/pre-compact.ps1)'
    $lines += ''
    $lines += ('- Branch: ' + $branch)
    $lines += ('- Head SHA at compact: ' + $sha)
    $lines += ('- Tracked files changed: ' + $dirty.Count)
    if ($plans.Count -gt 0) { $lines += ('- Plans touched in worktree: ' + (($plans | ForEach-Object { ($_ -split '\s+')[-1] }) -join ', ')) }
    if ($atHead.Count -gt 0) {
        $lines += ('- Reviewer subagents recorded at this SHA: ' + ($atHead -join ', '))
    } else {
        $lines += '- Reviewer subagents recorded at this SHA: none'
    }
    $lines += '- Ledger records only that a reviewer ran, never its verdict. Re-confirm verdicts after compaction.'
    $lines += ('- Written: ' + (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ'))

    Set-Content -Path (Join-Path $root '.claude/.delivery-state.md') -Value $lines -Encoding ascii
    'Delivery state saved to .claude/.delivery-state.md - read it after compaction before claiming any gate.'
} catch { }
exit 0
