# Lead Gen - One-Click Setup for Windows
# Run this after cloning the repo: .\workdir\lead-gen\setup.ps1
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host @"
========================================
  NEXUS Lead Gen - Setup
========================================
"@ -ForegroundColor Cyan

Push-Location $PSScriptRoot

try {
    # Check Python
    Write-Host "[1/5] Checking Python..." -ForegroundColor Yellow
    $pythonVersion = python --version 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Python not found. Install Python 3.11+ from https://python.org" -ForegroundColor Red
        exit 1
    }
    Write-Host "  Found: $pythonVersion" -ForegroundColor Green

    # Check Node.js
    Write-Host "[2/5] Checking Node.js..." -ForegroundColor Yellow
    $nodeVersion = node --version 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Node.js not found. Install from https://nodejs.org" -ForegroundColor Red
        exit 1
    }
    Write-Host "  Found: Node.js $nodeVersion" -ForegroundColor Green

    # Setup Python venv + deps
    Write-Host "[3/5] Setting up Python backend..." -ForegroundColor Yellow
    if (-not (Test-Path ".venv")) {
        python -m venv .venv
    }
    & .venv\Scripts\Activate.ps1
    pip install -r requirements.txt --quiet
    Write-Host "  Backend dependencies installed" -ForegroundColor Green

    # Setup frontend
    Write-Host "[4/5] Setting up Next.js frontend..." -ForegroundColor Yellow
    Push-Location frontend
    npm install
    Pop-Location
    Write-Host "  Frontend dependencies installed" -ForegroundColor Green

    # Create .env if missing
    Write-Host "[5/5] Checking .env configuration..." -ForegroundColor Yellow
    if (-not (Test-Path ".env")) {
        @"
# Lead Gen Environment Variables
# Fill in your API keys below

# Required for AI features (lead scoring, ICP parsing, outreach generation)
ANTHROPIC_API_KEY=your-key-here

# Required for lead search
APOLLO_API_KEY=your-key-here

# Optional
LEAD_GEN_PORT=8082
API_KEY=your-api-key-for-auth
"@ | Set-Content ".env"
        Write-Host "  Created .env file - EDIT IT with your API keys!" -ForegroundColor Red
    } else {
        Write-Host "  .env already exists" -ForegroundColor Green
    }

    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  Setup Complete!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Yellow
    Write-Host "  1. Edit .env with your API keys (ANTHROPIC_API_KEY, APOLLO_API_KEY)"
    Write-Host "  2. Run: .\start-all.ps1   (starts backend + frontend)"
    Write-Host "  3. Open: http://localhost:3000"
    Write-Host ""
} finally {
    Pop-Location
}
