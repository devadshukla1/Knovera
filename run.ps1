# ==============================================================================
# Knovera — 1-Click Launch Script
# Starts all native services, verifies health, and opens the frontend in browser.
# ==============================================================================
[CmdletBinding()]
param()

$ProjectRoot = (Resolve-Path $PSScriptRoot).Path
Set-Location $ProjectRoot

# 1. Start all 4 native services (PostgreSQL, ChromaDB, FastAPI, React/Vite)
powershell -ExecutionPolicy Bypass -File (Join-Path $ProjectRoot "scripts\windows\start.ps1")

# 2. Actively poll until Backend and Frontend are fully ready
Write-Host "`nWaiting for Frontend (5173) and Backend (8000) to be fully ready..." -ForegroundColor Cyan
$maxAttempts = 30
$frontendReady = $false
$backendReady = $false

for ($i = 1; $i -le $maxAttempts; $i++) {
    if (-not $backendReady) {
        try {
            $b = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health/ready" -TimeoutSec 1 -ErrorAction Stop
            if ($b.status -eq "ready") { $backendReady = $true }
        } catch {}
    }
    if (-not $frontendReady) {
        try {
            $f = Invoke-WebRequest -Uri "http://127.0.0.1:5173" -TimeoutSec 1 -UseBasicParsing -ErrorAction Stop
            if ($f.StatusCode -eq 200) { $frontendReady = $true }
        } catch {}
    }
    if ($backendReady -and $frontendReady) {
        break
    }
    Start-Sleep -Milliseconds 800
}

# 3. Print verified status table
powershell -ExecutionPolicy Bypass -File (Join-Path $ProjectRoot "scripts\windows\status.ps1")

# 4. Open default web browser safely to the active Knovera app root
Write-Host "`nOpening Knovera in browser..." -ForegroundColor Green
Start-Process "http://127.0.0.1:5173/app"
