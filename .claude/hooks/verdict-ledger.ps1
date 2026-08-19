# SubagentStop hook: record that a reviewer subagent finished, and at which head SHA.
# The harness rule "a verdict issued against an older SHA is stale" was previously only
# agent-followed. This makes the "did a reviewer actually run at this SHA" half checkable;
# guard-bash.ps1 reads the ledger when 'gh pr ready' is attempted.
# It records only agent name + SHA + timestamp. It never records a verdict - a hook
# cannot know one - so it can prove a reviewer did NOT run, never that one approved.
# Fails open: any error exits 0 and nothing is recorded.
# ASCII only - PowerShell 5.1 parses .ps1 as ANSI.
$ErrorActionPreference = 'SilentlyContinue'
try {
    $raw = [Console]::In.ReadToEnd()
    if (-not $raw) { exit 0 }
    $payload = $raw | ConvertFrom-Json

    # The field carrying the subagent type has moved between CLI versions. Try the known
    # spellings, then fall back to 'unknown' rather than guessing wrong.
    $agent = $null
    foreach ($k in @('agent_type', 'subagent_type', 'agentType', 'subagentType', 'agent_name')) {
        if ($payload.PSObject.Properties.Name -contains $k -and $payload.$k) { $agent = [string]$payload.$k; break }
    }
    if (-not $agent -and $payload.tool_input) {
        foreach ($k in @('subagent_type', 'agent_type')) {
            if ($payload.tool_input.PSObject.Properties.Name -contains $k -and $payload.tool_input.$k) {
                $agent = [string]$payload.tool_input.$k; break
            }
        }
    }
    if (-not $agent) { $agent = 'unknown' }

    $root = $env:CLAUDE_PROJECT_DIR
    if (-not $root) { $root = (Get-Location).Path }
    $sha = (& git -C $root rev-parse HEAD) -join ''
    if (-not $sha) { exit 0 }

    $entry = [ordered]@{
        sha     = $sha
        agent   = $agent
        session = [string]$payload.session_id
        at      = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    }
    $line = ($entry | ConvertTo-Json -Depth 3 -Compress)
    Add-Content -Path (Join-Path $root '.claude/.verdict-ledger.jsonl') -Value $line -Encoding ascii
} catch { }
exit 0
