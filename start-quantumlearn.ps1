[CmdletBinding()]
param(
    [switch]$NoBrowser,
    [ValidateRange(1, 3600)][int]$StartupTimeoutSeconds = 90,
    [ValidateRange(1, 3600)][int]$SetupTimeoutSeconds = 600,
    [string]$StopFile
)
$ErrorActionPreference = 'Stop'
$uv = Get-Command 'uv.exe' -ErrorAction SilentlyContinue
$npm = Get-Command 'npm.cmd' -ErrorAction SilentlyContinue
$node = Get-Command 'node.exe' -ErrorAction SilentlyContinue
if ($null -eq $uv -or $null -eq $npm -or $null -eq $node) {
    throw 'Install uv and Node.js 22 with npm before starting QuantumLearn.'
}
try {
    $python = & $uv.Source python find 3.11 --no-python-downloads 2>$null
}
catch {
    throw 'Python discovery failed. Check uv cache access and install Python with uv python install 3.11.'
}
if ($LASTEXITCODE -ne 0 -or -not $python) {
    throw 'No Python interpreter found. Run uv python install 3.11, then try again.'
}
$launcherArguments = @(
    (Join-Path $PSScriptRoot 'scripts\quantumlearn_launcher.py'),
    '--uv', $uv.Source, '--npm', $npm.Source, '--node', $node.Source,
    '--startup-timeout', $StartupTimeoutSeconds,
    '--setup-timeout', $SetupTimeoutSeconds
)
if ($NoBrowser) { $launcherArguments += '--no-browser' }
if ($StopFile) { $launcherArguments += @('--stop-file', $StopFile) }
& $python @launcherArguments
exit $LASTEXITCODE
