# PreToolUse(Bash) hook: deny irreversible or authority-exceeding commands, block secret
# reads that the Read-tool deny rules cannot see, and attach verdict evidence to PR-ready.
# Catches compound commands that prefix-matched permission rules miss.
# Mirrors .agents/permissions/policy.md "requires separate explicit authority".
# Tiers: $blocked -> deny, secret reads -> deny, 'gh pr ready' -> ask with ledger state.
# Fails open: any error exits 0 and the normal permission flow applies.
# Note: this hook matches on the whole command string, so a Bash heredoc that merely
# quotes a blocked command is denied too. Edit this file with the Write/Edit tools.
# ASCII only - PowerShell 5.1 parses .ps1 as ANSI and smart punctuation breaks strings.
$ErrorActionPreference = 'SilentlyContinue'

function Write-Decision {
    param([string]$Decision, [string]$Reason)
    $out = @{ hookSpecificOutput = @{
        hookEventName            = 'PreToolUse'
        permissionDecision       = $Decision
        permissionDecisionReason = $Reason
    } }
    $out | ConvertTo-Json -Depth 5 -Compress
}

try {
    $raw = [Console]::In.ReadToEnd()
    if (-not $raw) { exit 0 }
    $cmd = ($raw | ConvertFrom-Json).tool_input.command
    if (-not $cmd) { exit 0 }

    # --- Tier 1: deny. Irreversible, or needs separate explicit authority. ---
    $blocked = @(
        @{ p = 'git\s+push\b[^|;&]*(--force(?!-with-lease)|\s-f\b)'; why = 'force-push rewrites published history' },
        @{ p = 'git\s+push\b[^|;&]*--delete';                        why = 'deleting a remote branch is irreversible' },
        @{ p = 'git\s+reset\s+--hard';                               why = 'discards user-owned worktree changes' },
        @{ p = 'git\s+clean\s+-[a-z]*f';                             why = 'deletes untracked user files' },
        @{ p = 'git\s+checkout\s+--\s';                              why = 'discards user-owned changes to those paths' },
        @{ p = 'git\s+restore\b(?![^|;&]*--staged\b)';               why = 'git restore overwrites user-owned worktree changes' },
        @{ p = 'git\s+restore\b[^|;&]*--worktree';                   why = 'git restore --worktree overwrites user-owned changes' },
        @{ p = 'git\s+switch\b[^|;&]*--discard-changes';             why = 'discards user-owned worktree changes' },
        @{ p = 'git\s+stash\s+(drop|clear)';                         why = 'destroys stashed user-owned work' },
        @{ p = 'git\s+branch\s+([^|;&]*-D\b|[^|;&]*--delete[^|;&]*--force)'; why = 'force-deleting a branch can orphan unmerged commits' },
        @{ p = 'git\s+worktree\s+remove\b[^|;&]*(--force|\s-f\b)';   why = 'force-removing a worktree deletes uncommitted work' },
        @{ p = 'git\s+update-ref\s+-d';                              why = 'deleting a ref can orphan commits' },
        @{ p = 'git\s+(rebase|filter-branch|commit\s+--amend)';      why = 'rewrites existing history' },
        @{ p = '(^|[|;&`]\s*)\s*(sudo\s+)?rm\s+-[a-zA-Z]*r[a-zA-Z]*f|(^|[|;&`]\s*)\s*(sudo\s+)?rm\s+-[a-zA-Z]*f[a-zA-Z]*r'; why = 'recursive force delete can destroy user-owned files' },
        @{ p = 'Remove-Item[^|;&]*(-Recurse[^|;&]*-Force|-Force[^|;&]*-Recurse)'; why = 'recursive force delete can destroy user-owned files' },
        @{ p = 'gh\s+pr\s+merge';                                    why = 'merging needs separate explicit authority' },
        @{ p = 'gh\s+pr\s+close';                                    why = 'closing a PR needs separate explicit authority' },
        @{ p = 'gh\s+pr\s+review\s+[^|;&]*--(approve|dismiss)';      why = 'the harness forbids self-approval and review dismissal' },
        @{ p = 'gh\s+api\s+[^|;&]*(branch_protection|branches/[^|;&/\s]+/protection)'; why = 'branch protection changes need separate explicit authority' }
    )

    foreach ($b in $blocked) {
        if ($cmd -match $b.p) {
            Write-Decision 'deny' ('Blocked by the LearnLens harness: ' + $b.why + '. See .agents/permissions/policy.md - this needs separate explicit authority from the user. Ask for it, or use a non-destructive alternative (note that --force-with-lease is still a rewrite; prefer a new commit).')
            exit 0
        }
    }

    # --- Tier 1b: secret reads. settings.json denies these paths for the Read tool, but
    # permission rules are per-tool, so Bash would otherwise walk straight past that deny. ---
    # Checked per command segment, and only where the secret path is an ARGUMENT to the read
    # verb: '[^>]*' stops the match at a redirect, so writing a file whose body merely mentions
    # a secret path ("cat > msg <<EOF ... .env ...") is not treated as reading one.
    $verbs = 'cat|bat|tac|less|more|head|tail|sed|awk|strings|xxd|od|cp|scp|curl|type|Get-Content|gc|grep|rg|findstr|Copy-Item'
    $secretPat = '(?<![\w.-])(\.env(\.[A-Za-z0-9_-]+)?|[\w./\\-]*\.pem|[\w./\\-]*id_rsa[\w.-]*|[\w./\\-]*\.key)(?![\w-])'
    $readsSecret = '^\s*(sudo\s+)?(' + $verbs + ')\b[^>]*' + $secretPat
    foreach ($seg in ($cmd -split '(\r?\n|&&|\|\||[|;&])')) {
        if (-not $seg) { continue }
        if (($seg -match $readsSecret) -and ($seg -notmatch '\.env\.example')) {
            Write-Decision 'deny' 'Blocked by the LearnLens harness: this reads a secret-bearing file (.env, .env.*, *.pem, id_rsa*, *.key). settings.json denies those paths for the Read tool; permission rules are per-tool, so Bash is denied here for the same reason. CLAUDE.md forbids secrets in logs, PR bodies, and memory. Use .env.example, or ask the user for the specific value you need.'
            exit 0
        }
    }

    # --- Tier 2: ask, with ledger state attached. 'gh pr ready' is the moment the three
    # independent verdicts stop being a rule and start mattering. ---
    if ($cmd -match 'gh\s+pr\s+ready') {
        $root = $env:CLAUDE_PROJECT_DIR
        if (-not $root) { $root = (Get-Location).Path }
        $sha = (& git -C $root rev-parse HEAD) -join ''
        $ledger = Join-Path $root '.claude/.verdict-ledger.jsonl'
        $needed = @('test-judge', 'code-reviewer', 'code-quality-reviewer')
        $seen = @()
        if ($sha -and (Test-Path $ledger)) {
            foreach ($line in (Get-Content $ledger)) {
                if (-not $line) { continue }
                $e = $line | ConvertFrom-Json
                if ($e -and $e.sha -eq $sha -and $needed -contains $e.agent) { $seen += $e.agent }
            }
        }
        $missing = @($needed | Where-Object { $seen -notcontains $_ })
        if ($missing.Count -gt 0) {
            Write-Decision 'ask' ('Review-readiness check: the verdict ledger records no reviewer run at head ' + $sha + ' for: ' + ($missing -join ', ') + '. The ledger records only THAT a reviewer subagent ran, never its verdict, and it cannot see runs from earlier sessions - so treat this as evidence, not proof. Confirm each missing verdict was actually obtained at this head SHA before marking the PR ready. See .agents/hooks/before-review-request.md.')
            exit 0
        }
    }
} catch { }
exit 0
