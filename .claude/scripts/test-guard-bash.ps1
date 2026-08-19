<#
    Regression tests for .claude/hooks/guard-bash.ps1.

    The Bash guard is the only thing standing between an agent and an irreversible command,
    and its rules are regexes - the failure mode is a silent hole, not an error. Every rule
    gets a case that must be denied and, where a safe sibling form exists, a case that must
    still be allowed.

    Cases live in .claude/scripts/harness-tests/guard-bash-cases.txt as EXPECT_<DECISION>|<command>.
    DECISION is ALLOW, DENY, or ASK. ALLOW means the hook stays silent and the normal
    permission flow applies.

    Usage:  powershell -NoProfile -ExecutionPolicy Bypass -File .claude/scripts/test-guard-bash.ps1
    Exit 0 = all cases pass, exit 1 = at least one regression.
    ASCII only - PowerShell 5.1 parses .ps1 as ANSI.
#>
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$hook = Join-Path $root '.claude/hooks/guard-bash.ps1'
$caseFiles = @(Get-ChildItem (Join-Path $PSScriptRoot 'harness-tests') -Filter 'guard-bash-cases*.txt' |
    Sort-Object Name)

if (-not (Test-Path $hook)) { "missing hook: $hook"; exit 1 }
if ($caseFiles.Count -eq 0) { 'no case files found under harness-tests/'; exit 1 }

$env:CLAUDE_PROJECT_DIR = $root
$fail = 0
$total = 0

foreach ($line in ($caseFiles | ForEach-Object { Get-Content $_.FullName })) {
    if (-not $line -or $line.StartsWith('#')) { continue }
    $total++
    $parts = $line -split '\|', 2
    $expect = $parts[0].Replace('EXPECT_', '')
    $cmd = $parts[1]

    $payload = @{ tool_name = 'Bash'; tool_input = @{ command = $cmd } } | ConvertTo-Json -Compress
    $out = $payload | & powershell -NoProfile -ExecutionPolicy Bypass -File $hook

    $got = 'ALLOW'
    if ($out) { $got = ([string](($out | ConvertFrom-Json).hookSpecificOutput.permissionDecision)).ToUpper() }

    if ($got -ne $expect) {
        $fail++
        '{0} expect={1,-5} got={2,-5} {3}' -f 'FAIL', $expect, $got, $cmd
    }
}

''
if ($fail -eq 0) { "guard-bash: all $total case(s) PASS"; exit 0 }
"guard-bash: $fail of $total case(s) FAILED"
exit 1
