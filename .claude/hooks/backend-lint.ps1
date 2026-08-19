# PostToolUse(Edit|Write) hook: run Ruff on the single backend file just edited.
# Turns the CI lint gate into immediate feedback instead of a late failure.
# Exits 2 with the Ruff output when the file fails, so the agent fixes it now.
# Calls the venv ruff.exe directly when present: two 'uv run --frozen' bootstraps per
# edited file cost seconds on Windows, and the resolved interpreter is the same one.
# Falls back to 'uv run --frozen ruff', which is what quality.yml runs.
# Fails open: missing ruff, missing venv, or any error exits 0.
# ASCII only - PowerShell 5.1 parses .ps1 as ANSI.
$ErrorActionPreference = 'SilentlyContinue'
try {
    $raw = [Console]::In.ReadToEnd()
    if (-not $raw) { exit 0 }
    $path = ($raw | ConvertFrom-Json).tool_input.file_path
    if (-not $path) { exit 0 }

    $norm = $path.Replace('\', '/')
    if ($norm -notmatch '/src-main/backend/.*\.py$') { exit 0 }
    if (-not (Test-Path $path)) { exit 0 }

    $root = $env:CLAUDE_PROJECT_DIR
    if (-not $root) { $root = (Get-Location).Path }
    $backend = Join-Path $root 'src-main/backend'
    if (-not (Test-Path $backend)) { exit 0 }

    $ruffExe = Join-Path $backend '.venv/Scripts/ruff.exe'
    $useDirect = Test-Path $ruffExe
    if (-not $useDirect -and -not (Get-Command uv -ErrorAction SilentlyContinue)) { exit 0 }

    Push-Location $backend
    if ($useDirect) {
        $check = & $ruffExe check --force-exclude --output-format concise $path
        $checkFailed = ($LASTEXITCODE -ne 0)
        & $ruffExe format --check --force-exclude $path | Out-Null
        $fmtFailed = ($LASTEXITCODE -ne 0)
    } else {
        $check = & uv run --frozen ruff check --force-exclude --output-format concise $path
        $checkFailed = ($LASTEXITCODE -ne 0)
        & uv run --frozen ruff format --check --force-exclude $path | Out-Null
        $fmtFailed = ($LASTEXITCODE -ne 0)
    }
    Pop-Location

    if ($checkFailed -or $fmtFailed) {
        $lines = @('Ruff failed on ' + $norm + ' (same gate as .github/workflows/quality.yml). Fix it before moving on.')
        if ($checkFailed) {
            $lines += 'ruff check:'
            $lines += @($check | Select-Object -First 25)
        }
        if ($fmtFailed) {
            $lines += "ruff format --check: file is not formatted. Run 'uv run --frozen ruff format <file>' from src-main/backend."
        }
        [Console]::Error.WriteLine(($lines -join "`n"))
        exit 2
    }
} catch { }
exit 0
