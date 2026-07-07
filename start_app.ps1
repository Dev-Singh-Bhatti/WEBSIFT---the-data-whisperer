param(
    [int]$Port = 8502,
    [bool]$Headless = $true,
    [switch]$InstallDependencies
)

$ErrorActionPreference = "Stop"

function Invoke-Step {
    param(
        [string]$Exe,
        [string[]]$CommandArgs
    )
    & $Exe @CommandArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed: $Exe $($CommandArgs -join ' ')"
    }
}

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$venvDir = Join-Path $root ".venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"
$requirementsFile = Join-Path $root "requirements.txt"
$seleniumCache = Join-Path $root ".tmp\selenium-cache"

New-Item -ItemType Directory -Force -Path $seleniumCache | Out-Null
$env:SE_CACHE_PATH = $seleniumCache

if (-not $env:DATABASE_URL) {
    $env:DATABASE_URL = "sqlite:///./app.db"
}

if (-not (Test-Path $venvPython)) {
    Write-Host "Creating virtual environment at .venv ..."
    if (Get-Command py -ErrorAction SilentlyContinue) {
        Invoke-Step -Exe "py" -CommandArgs @("-3", "-m", "venv", $venvDir)
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        Invoke-Step -Exe "python" -CommandArgs @("-m", "venv", $venvDir)
    } else {
        throw "Python launcher not found. Install Python 3.13+ and retry."
    }
}

if (-not (Test-Path $venvPython)) {
    throw "Failed to create .venv. Expected python at: $venvPython"
}

$needsInstall = $InstallDependencies
if (-not $needsInstall) {
    & $venvPython -m pip show streamlit *> $null
    if ($LASTEXITCODE -ne 0) {
        $needsInstall = $true
    }
}

if ($needsInstall) {
    Write-Host "Installing dependencies from requirements.txt ..."
    Invoke-Step -Exe $venvPython -CommandArgs @("-m", "pip", "install", "--upgrade", "pip")
    Invoke-Step -Exe $venvPython -CommandArgs @("-m", "pip", "install", "-r", $requirementsFile)
}

$headlessArg = if ($Headless) { "true" } else { "false" }

Write-Host "Starting app at http://localhost:$Port"
Write-Host "Press Ctrl+C to stop."
Invoke-Step -Exe $venvPython -CommandArgs @(
    "-m", "streamlit", "run", (Join-Path $root "app.py"),
    "--server.port", "$Port",
    "--server.headless", $headlessArg,
    "--browser.gatherUsageStats", "false"
)
