<#
    Harness consistency check.

    CLAUDE.md says: "When this file and .agents/ disagree, .agents/ wins and the drift is a bug."
    Nothing used to detect that. This does, cheaply:

      1. Every .claude/ projection cites its .agents/ canonical contract.
      2. Every .claude/agents/*.md cites its matching .agents/agents/*-agent.md.
      3. Every hook script referenced by settings.json exists on disk.
      4. docs/plans has no duplicated NNN prefix.

    It checks that the pointer exists, not that the prose agrees - a pointer is what keeps the
    contract single-sourced in the first place.

    Usage:  powershell -NoProfile -ExecutionPolicy Bypass -File .claude/scripts/check-harness.ps1
    Exit 0 = clean, exit 1 = at least one problem. Not wired into CI; see .claude/README.md.
    ASCII only - PowerShell 5.1 parses .ps1 as ANSI.
#>
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$problems = @()
$checks = 0

function Test-Cites {
    param([string]$File, [string]$Canonical)
    $script:checks++
    $full = Join-Path $root $File
    if (-not (Test-Path $full)) { $script:problems += "missing file: $File"; return }
    if (-not (Test-Path (Join-Path $root $Canonical))) {
        $script:problems += "$File cites a canonical file that does not exist: $Canonical"; return
    }
    $body = (Get-Content $full -Raw).Replace('\', '/')
    if ($body -notmatch [regex]::Escape($Canonical)) {
        $script:problems += "$File does not cite its canonical contract $Canonical"
    }
}

# 1 + 2: projections cite their canonical contracts.
foreach ($dir in (Get-ChildItem (Join-Path $root '.claude/skills') -Directory -ErrorAction SilentlyContinue)) {
    Test-Cites ".claude/skills/$($dir.Name)/SKILL.md" ".agents/skills/$($dir.Name)/SKILL.md"
}
foreach ($f in (Get-ChildItem (Join-Path $root '.claude/agents') -Filter '*.md' -ErrorAction SilentlyContinue)) {
    $stem = [System.IO.Path]::GetFileNameWithoutExtension($f.Name)
    Test-Cites ".claude/agents/$($f.Name)" ".agents/agents/$stem-agent.md"
}

# 3: every hook command in settings.json points at a script that exists.
$checks++
$settingsPath = Join-Path $root '.claude/settings.json'
if (-not (Test-Path $settingsPath)) {
    $problems += 'missing file: .claude/settings.json'
} else {
    $settings = Get-Content $settingsPath -Raw | ConvertFrom-Json
    foreach ($event in $settings.hooks.PSObject.Properties) {
        foreach ($group in $event.Value) {
            foreach ($h in $group.hooks) {
                if ($h.command -match '\.claude/hooks/([\w.-]+\.ps1)') {
                    $checks++
                    $hookFile = Join-Path $root ".claude/hooks/$($Matches[1])"
                    if (-not (Test-Path $hookFile)) {
                        $problems += "settings.json registers a missing hook: $($Matches[1]) (event $($event.Name))"
                    }
                }
            }
        }
    }
}

# 4: plan numbering collisions.
$checks++
$plans = Get-ChildItem (Join-Path $root 'docs/plans') -Filter '*.md' -ErrorAction SilentlyContinue
$dupes = $plans | Group-Object { ($_.Name -split '-')[0] } | Where-Object { $_.Count -gt 1 }
foreach ($d in $dupes) {
    $problems += ("docs/plans has " + $d.Count + " files numbered " + $d.Name + ": " + (($d.Group.Name) -join ', '))
}

if ($problems.Count -eq 0) {
    "harness check: $checks check(s) PASS"
    exit 0
}
"harness check: $($problems.Count) problem(s) across $checks check(s)"
foreach ($p in $problems) { "  - $p" }
exit 1
