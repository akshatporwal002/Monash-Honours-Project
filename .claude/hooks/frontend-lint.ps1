# PostToolUse(Edit|Write) hook: run ESLint on the single frontend file just edited.
# Mirrors backend-lint.ps1 so the frontend gets the same immediate feedback the backend
# has; .github/workflows/quality.yml runs 'npm run lint' and used to fail late here.
# Exits 2 with the ESLint output when the file fails, so the agent fixes it now.
# Fails open: missing npm, missing node_modules, or any error exits 0.
# ASCII only - PowerShell 5.1 parses .ps1 as ANSI.
$ErrorActionPreference = 'SilentlyContinue'
try {
    $raw = [Console]::In.ReadToEnd()
    if (-not $raw) { exit 0 }
    $path = ($raw | ConvertFrom-Json).tool_input.file_path
    if (-not $path) { exit 0 }

    $norm = $path.Replace('\', '/')
    if ($norm -notmatch '/src-main/frontend/.*\.(ts|tsx|js|jsx)$') { exit 0 }
    if ($norm -match '/node_modules/|/dist/') { exit 0 }
    if (-not (Test-Path $path)) { exit 0 }

    $root = $env:CLAUDE_PROJECT_DIR
    if (-not $root) { $root = (Get-Location).Path }
    $frontend = Join-Path $root 'src-main/frontend'
    if (-not (Test-Path (Join-Path $frontend 'node_modules'))) { exit 0 }

    # Windows blocks the bare 'npx' shim often enough that quality-checks.md documents it.
    $runner = $null
    foreach ($c in @('npx.cmd', 'npx')) {
        if (Get-Command $c -ErrorAction SilentlyContinue) { $runner = $c; break }
    }
    if (-not $runner) { exit 0 }

    Push-Location $frontend
    # Default formatter on purpose: ESLint 9 removed the 'compact' formatter from core, and
    # asking for it makes eslint exit non-zero with no findings - a false failure on every file.
    $out = & $runner eslint $path 2>&1
    $failed = ($LASTEXITCODE -ne 0)
    Pop-Location

    if ($failed) {
        $lines = @('ESLint failed on ' + $norm + ' (same gate as .github/workflows/quality.yml). Fix it before moving on.')
        $lines += @($out | Select-Object -First 25)
        [Console]::Error.WriteLine(($lines -join "`n"))
        exit 2
    }
} catch { }
exit 0
