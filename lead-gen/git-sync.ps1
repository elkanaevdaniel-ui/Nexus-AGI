# Lead Gen - Auto Git Sync (Pull + Push)
# Usage:
#   .\git-sync.ps1              # One-time sync
#   .\git-sync.ps1 -Watch       # Auto-sync every 5 minutes
#   .\git-sync.ps1 -Watch -Interval 120  # Auto-sync every 2 minutes
param(
    [switch]$Watch,
    [int]$Interval = 300  # seconds between syncs (default: 5 min)
)

Set-StrictMode -Version Latest

function Sync-Repo {
    $branch = git rev-parse --abbrev-ref HEAD 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Not a git repository" -ForegroundColor Red
        return $false
    }

    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$timestamp] Syncing branch: $branch" -ForegroundColor Cyan

    # Fetch latest changes
    Write-Host "  Fetching..." -ForegroundColor Yellow
    git fetch origin $branch 2>&1

    # Check if there are remote changes
    $localHead = git rev-parse HEAD 2>&1
    $remoteHead = git rev-parse "origin/$branch" 2>&1

    if ($localHead -ne $remoteHead) {
        Write-Host "  Merging remote changes..." -ForegroundColor Yellow
        git merge "origin/$branch" --no-edit 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Host "  Merge conflict - resolve manually" -ForegroundColor Red
            git merge --abort 2>$null
            return $false
        }
    } else {
        Write-Host "  Already up to date" -ForegroundColor DarkGray
    }

    # Check for uncommitted changes
    $status = git status --porcelain
    if ($status) {
        Write-Host "  Staging changes..." -ForegroundColor Yellow

        # Stage all changes except sensitive files
        git add -A

        # Unstage sensitive files if accidentally added
        $sensitivePatterns = @("*.env", "*.env.*", "credentials*", "*.pem", "*.key")
        foreach ($pattern in $sensitivePatterns) {
            git reset HEAD -- $pattern 2>$null
        }

        # Create commit with auto-generated message
        $changedFiles = git diff --cached --name-only
        if ($changedFiles) {
            $fileCount = ($changedFiles | Measure-Object).Count
            $commitMsg = "chore: auto-sync $fileCount file(s) from local dev"
            git commit -m $commitMsg
            Write-Host "  Committed: $commitMsg" -ForegroundColor Green
        }
    } else {
        Write-Host "  No local changes" -ForegroundColor DarkGray
    }

    # Push to remote
    Write-Host "  Pushing..." -ForegroundColor Yellow
    git push origin $branch 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  Push failed - retry or check remote" -ForegroundColor Red
        return $false
    }

    Write-Host "  Sync complete!" -ForegroundColor Green
    return $true
}

# Navigate to repo root
Push-Location (git rev-parse --show-toplevel 2>$null)
if ($LASTEXITCODE -ne 0) {
    Push-Location $PSScriptRoot
    Push-Location (git rev-parse --show-toplevel)
}

try {
    if ($Watch) {
        Write-Host @"
========================================
  Git Auto-Sync (Watch Mode)
  Interval: ${Interval}s | Ctrl+C to stop
========================================
"@ -ForegroundColor Cyan

        while ($true) {
            Sync-Repo | Out-Null
            Write-Host "  Next sync in $Interval seconds..." -ForegroundColor DarkGray
            Start-Sleep -Seconds $Interval
        }
    } else {
        Sync-Repo | Out-Null
    }
} finally {
    Pop-Location
}
