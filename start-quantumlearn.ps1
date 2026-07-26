[CmdletBinding()]
param(
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"

$projectRoot = $PSScriptRoot
$backendRoot = Join-Path $projectRoot "src-main\backend"
$frontendRoot = Join-Path $projectRoot "src-main\frontend"

if (-not (Test-Path -LiteralPath $backendRoot)) {
    throw "Backend directory not found: $backendRoot"
}
if (-not (Test-Path -LiteralPath $frontendRoot)) {
    throw "Frontend directory not found: $frontendRoot"
}

$uv = Get-Command "uv.exe" -ErrorAction SilentlyContinue
$npm = Get-Command "npm.cmd" -ErrorAction SilentlyContinue

if ($null -eq $uv) {
    throw "uv is required. Install it from https://docs.astral.sh/uv/ and run this file again."
}
if ($null -eq $npm) {
    throw "Node.js and npm are required. Install Node.js 22 and run this file again."
}

Write-Host "Preparing QuantumLearn..." -ForegroundColor Cyan

Push-Location $backendRoot
try {
    if (-not (Test-Path -LiteralPath ".env")) {
        Copy-Item -LiteralPath ".env.example" -Destination ".env"
        Write-Host "Created backend .env from .env.example."
    }

    & $uv.Source sync --frozen --all-extras
    if ($LASTEXITCODE -ne 0) {
        throw "Backend dependency setup failed."
    }

    & $uv.Source run --frozen alembic upgrade head
    if ($LASTEXITCODE -ne 0) {
        throw "Database migration failed."
    }
}
finally {
    Pop-Location
}

Push-Location $frontendRoot
try {
    if (-not (Test-Path -LiteralPath ".env")) {
        Copy-Item -LiteralPath ".env.example" -Destination ".env"
        Write-Host "Created frontend .env from .env.example."
    }

    if (-not (Test-Path -LiteralPath "node_modules")) {
        & $npm.Source ci
        if ($LASTEXITCODE -ne 0) {
            throw "Frontend dependency setup failed."
        }
    }
}
finally {
    Pop-Location
}

function ConvertTo-SingleQuotedPowerShellLiteral {
    param([Parameter(Mandatory)][string]$Value)
    return "'" + $Value.Replace("'", "''") + "'"
}

$backendPath = ConvertTo-SingleQuotedPowerShellLiteral $backendRoot
$frontendPath = ConvertTo-SingleQuotedPowerShellLiteral $frontendRoot
$uvPath = ConvertTo-SingleQuotedPowerShellLiteral $uv.Source
$npmPath = ConvertTo-SingleQuotedPowerShellLiteral $npm.Source

$backendCommand = @"
Set-Location -LiteralPath $backendPath
Write-Host 'QuantumLearn backend — http://127.0.0.1:8000' -ForegroundColor Cyan
& $uvPath run --frozen uvicorn app.main:app --reload --no-access-log
"@

$frontendCommand = @"
Set-Location -LiteralPath $frontendPath
Write-Host 'QuantumLearn frontend — http://localhost:5173' -ForegroundColor Magenta
& $npmPath run dev
"@

$terminalArguments = @(
    "-NoLogo",
    "-NoExit",
    "-ExecutionPolicy",
    "Bypass",
    "-Command"
)

$backendProcess = Start-Process `
    -FilePath "powershell.exe" `
    -ArgumentList ($terminalArguments + $backendCommand) `
    -WorkingDirectory $backendRoot `
    -PassThru

$frontendProcess = Start-Process `
    -FilePath "powershell.exe" `
    -ArgumentList ($terminalArguments + $frontendCommand) `
    -WorkingDirectory $frontendRoot `
    -PassThru

Write-Host "Backend terminal started (PID $($backendProcess.Id))."
Write-Host "Frontend terminal started (PID $($frontendProcess.Id))."

$appUrl = "http://localhost:5173"
$apiHealthUrl = "http://127.0.0.1:8000/api/v1/health"
$ready = $false
for ($attempt = 0; $attempt -lt 60; $attempt += 1) {
    try {
        $frontendResponse = Invoke-WebRequest -UseBasicParsing -Uri $appUrl -TimeoutSec 1
        $backendResponse = Invoke-WebRequest -UseBasicParsing -Uri $apiHealthUrl -TimeoutSec 1
        if ($frontendResponse.StatusCode -eq 200 -and $backendResponse.StatusCode -eq 200) {
            $ready = $true
            break
        }
    }
    catch {
        Start-Sleep -Milliseconds 500
    }
}

if (-not $ready) {
    Write-Warning "The terminals started, but QuantumLearn did not become ready within 30 seconds. Check their output for an error."
    exit 1
}

Write-Host "QuantumLearn is ready at $appUrl" -ForegroundColor Green
Write-Host "Close the two server terminals when you want to stop the app."

if (-not $NoBrowser) {
    Start-Process $appUrl
}
