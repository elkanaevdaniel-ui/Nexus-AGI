# Lead Gen Frontend - PowerShell Startup Script
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Push-Location "$PSScriptRoot\frontend"

try {
    # Install dependencies if node_modules doesn't exist
    if (-not (Test-Path "node_modules")) {
        Write-Host "Installing frontend dependencies..." -ForegroundColor Cyan
        npm install
    }

    Write-Host "Starting Lead Gen frontend on port 3000..." -ForegroundColor Green
    npm run dev
} finally {
    Pop-Location
}
