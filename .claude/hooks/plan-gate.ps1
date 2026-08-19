# PreToolUse(Edit|Write|NotebookEdit) hook: advisory plan gate for product code.
# Implements .agents/hooks/before-implementation.md - no implementation before a durable
# plan exists. Advisory by design: it injects a reminder, it does not deny the edit,
# because a legitimate hotfix or plan revision must not be wedged by a script.
# Caches the positive answer per branch: once a plan is touched on this branch the answer
# cannot flip back, and the git calls were re-running on every single edit.
# Fails open: any error exits 0 with no output.
# ASCII only - PowerShell 5.1 parses .ps1 as ANSI.
$ErrorActionPreference = 'SilentlyContinue'
try {
    $raw = [Console]::In.ReadToEnd()
    if (-not $raw) { exit 0 }
    $payload = $raw | ConvertFrom-Json
    $path = $payload.tool_input.file_path
    if (-not $path) { exit 0 }

    $norm = $path.Replace('\', '/')
    if ($norm -notmatch '/src-main/') { exit 0 }

    $root = $env:CLAUDE_PROJECT_DIR
    if (-not $root) { $root = (Get-Location).Path }

    $branch = (& git -C $root branch --show-current) -join ''
    $cache = Join-Path $root '.claude/.plan-gate-cache'
    if ($branch -and (Test-Path $cache)) {
        if ((Get-Content $cache) -contains $branch) { exit 0 }
    }

    # A plan is "active" if a plan file is modified in the worktree or added on this branch.
    $touched = @(& git -C $root --no-optional-locks status --porcelain --untracked-files=no -- docs/plans)
    if ($touched.Count -eq 0) {
        $base = $null
        foreach ($candidate in @('origin/main', 'main')) {
            & git -C $root rev-parse --verify --quiet $candidate > $null 2> $null
            if ($LASTEXITCODE -eq 0) { $base = $candidate; break }
        }
        # No resolvable base branch: cannot judge, so stay silent.
        if (-not $base) { exit 0 }
        $touched = @(& git -C $root diff --name-only "$base...HEAD" -- docs/plans)
    }
    if ($touched.Count -gt 0) {
        if ($branch) { Add-Content -Path $cache -Value $branch -Encoding ascii }
        exit 0
    }

    $msg = 'Plan gate: no plan under docs/plans is modified in this worktree or added on this branch, but you are editing product code (' + $norm + '). .agents/hooks/before-implementation.md requires a grounded, durable plan first. If this edit belongs to an approved plan on another branch, or the user explicitly asked for a direct fix, continue and say so; otherwise stop and run /draft-plan.'
    $out = @{ hookSpecificOutput = @{
        hookEventName = 'PreToolUse'
        additionalContext = $msg
    } }
    $out | ConvertTo-Json -Depth 5 -Compress
} catch { }
exit 0
