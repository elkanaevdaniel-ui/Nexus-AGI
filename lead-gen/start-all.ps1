# Lead Gen - Start Backend + Frontend in parallel
# Usage: .\start-all.ps1
Set-StrictMode -Version Latest

Write-Host @"
========================================
  NEXUS Lead Gen - AI SDR OS
========================================
Starting backend (port 8082) and frontend (port 3000)...
"@ -ForegroundColor Cyan

# Start backend in a new PowerShell window
Start-Process powershell -ArgumentList "-NoExit", "-File", "$PSScriptRoot\start-backend.ps1" -WindowStyle Normal

# Small delay to let backend start first
Start-Sleep -Seconds 3

# Start frontend in a new PowerShell window
Start-Process powershell -ArgumentList "-NoExit", "-File", "$PSScriptRoot\start-frontend.ps1" -WindowStyle Normal

Write-Host ""
Write-Host "Both services starting in separate windows!" -ForegroundColor Green
Write-Host "  Backend:  http://localhost:8082" -ForegroundColor Yellow
Write-Host "  Frontend: http://localhost:3000" -ForegroundColor Yellow
Write-Host "  API Docs: http://localhost:8082/docs" -ForegroundColor Yellow
Write-Host ""
