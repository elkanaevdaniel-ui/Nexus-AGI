# Lead Gen Backend - PowerShell Startup Script
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Push-Location $PSScriptRoot

try {
    # Create virtual environment if it doesn't exist
    if (-not (Test-Path ".venv")) {
        Write-Host "Creating virtual environment..." -ForegroundColor Cyan
        python -m venv .venv
        & .venv\Scripts\Activate.ps1
        pip install -r requirements.txt
    } else {
        & .venv\Scripts\Activate.ps1
    }

    $port = if ($env:LEAD_GEN_PORT) { $env:LEAD_GEN_PORT } else { "8082" }
    Write-Host "Starting Lead Gen backend on port $port..." -ForegroundColor Green
    uvicorn src.main:app --host 0.0.0.0 --port $port --reload
} finally {
    Pop-Location
}
