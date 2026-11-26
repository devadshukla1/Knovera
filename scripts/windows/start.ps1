# ==============================================================================
# Knovera Native Windows Startup Script
# scripts/windows/start.ps1
# ==============================================================================
[CmdletBinding()]
param()

$ProjectRoot = (Resolve-Path "$PSScriptRoot\..\..").Path
Set-Location $ProjectRoot

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   K N O V E R A  —  Starting Native Windows Platform     " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$KnoveraBase = Join-Path $env:LOCALAPPDATA "Knovera"
$PgData = Join-Path $KnoveraBase "data\postgres"
$ChromaData = Join-Path $KnoveraBase "data\chroma"
$LogsDir = Join-Path $KnoveraBase "logs"
$RuntimeDir = Join-Path $KnoveraBase "runtime"
$PidFile = Join-Path $RuntimeDir "pids.json"

foreach ($dir in @($KnoveraBase, $PgData, $ChromaData, $LogsDir, $RuntimeDir)) {
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
}

$Pids = @{}
if (Test-Path $PidFile) {
    try { $Pids = Get-Content $PidFile -Raw | ConvertFrom-Json -AsHashtable } catch { $Pids = @{} }
}

# ------------------------------------------------------------------------------
# 1. Start PostgreSQL (Port 5432)
# ------------------------------------------------------------------------------
Write-Host "`n[1/4] Checking PostgreSQL 16 (Port 5432)..." -ForegroundColor Yellow
$PgBinDir = Join-Path $env:LOCALAPPDATA "Programs\PostgreSQL\16\bin"
if (-not (Test-Path (Join-Path $PgBinDir "postgres.exe"))) {
    $sysPg = Get-Command postgres.exe -ErrorAction SilentlyContinue
    if ($sysPg) { $PgBinDir = Split-Path $sysPg.Source } else {
        Write-Error "PostgreSQL 16 binaries not found. Run .\scripts\windows\setup.ps1 first."
    }
}

$isPgUp = $false
try {
    $null = & (Join-Path $PgBinDir "pg_isready.exe") -h 127.0.0.1 -p 5432 -U postgres 2>$null
    if ($LASTEXITCODE -eq 0) { $isPgUp = $true }
} catch {}

if (-not $isPgUp) {
    Write-Host "  Starting native PostgreSQL daemon..."
    $pgLog = Join-Path $LogsDir "postgres.log"
    $cmd = "`"$PgBinDir\pg_ctl.exe`" start -D `"$PgData`" -l `"$pgLog`" -w"
    $res = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = $cmd }
    if ($res.ReturnValue -ne 0) {
        Write-Error "Failed to spawn PostgreSQL process. Return code: $($res.ReturnValue)"
    }
    $Pids["postgres"] = $res.ProcessId
    for ($i = 0; $i -lt 15; $i++) {
        Start-Sleep -Milliseconds 800
        $null = & (Join-Path $PgBinDir "pg_isready.exe") -h 127.0.0.1 -p 5432 -U postgres 2>$null
        if ($LASTEXITCODE -eq 0) { $isPgUp = $true; break }
    }
    if (-not $isPgUp) {
        Write-Error "PostgreSQL failed to respond on 127.0.0.1:5432. Check $pgLog"
    }
    Write-Host "  PostgreSQL started successfully (PID: $($res.ProcessId))." -ForegroundColor Green
} else {
    Write-Host "  PostgreSQL is already active on 127.0.0.1:5432." -ForegroundColor Green
}

# ------------------------------------------------------------------------------
# 2. Start ChromaDB Vector Store (Port 8001)
# ------------------------------------------------------------------------------
Write-Host "`n[2/4] Checking ChromaDB HTTP Server (Port 8001)..." -ForegroundColor Yellow
$ChromaBin = Join-Path $ProjectRoot ".venv\Scripts\chroma.exe"
if (-not (Test-Path $ChromaBin)) {
    Write-Error "ChromaDB CLI not found at $ChromaBin. Run .\scripts\windows\setup.ps1 first."
}

$isChromaUp = $false
try {
    $hb = Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/v2/heartbeat" -TimeoutSec 2 -ErrorAction SilentlyContinue
    if ($hb) { $isChromaUp = $true }
} catch {}

if (-not $isChromaUp) {
    Write-Host "  Starting native ChromaDB daemon..."
    $cmd = "`"$ChromaBin`" run --host 127.0.0.1 --port 8001 --path `"$ChromaData`""
    $res = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = $cmd }
    if ($res.ReturnValue -ne 0) {
        Write-Error "Failed to spawn ChromaDB process. Return code: $($res.ReturnValue)"
    }
    $Pids["chroma"] = $res.ProcessId
    for ($i = 0; $i -lt 15; $i++) {
        Start-Sleep -Milliseconds 800
        try {
            $hb = Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/v2/heartbeat" -TimeoutSec 1 -ErrorAction Stop
            if ($hb) { $isChromaUp = $true; break }
        } catch {}
    }
    Write-Host "  ChromaDB started successfully (PID: $($res.ProcessId))." -ForegroundColor Green
} else {
    Write-Host "  ChromaDB is already active on 127.0.0.1:8001." -ForegroundColor Green
}

# ------------------------------------------------------------------------------
# 3. Start FastAPI Backend (Port 8000)
# ------------------------------------------------------------------------------
Write-Host "`n[3/4] Checking FastAPI Backend (Port 8000)..." -ForegroundColor Yellow
$PyBin = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

$isBackendUp = $false
try {
    $live = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -TimeoutSec 2 -ErrorAction SilentlyContinue
    if ($live.status -eq "ok") { $isBackendUp = $true }
} catch {}

if (-not $isBackendUp) {
    Write-Host "  Starting native FastAPI backend..."
    $cmd = "`"$PyBin`" -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000"
    $res = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ 
        CommandLine = $cmd
        CurrentDirectory = $ProjectRoot
    }
    if ($res.ReturnValue -ne 0) {
        Write-Error "Failed to spawn FastAPI backend. Return code: $($res.ReturnValue)"
    }
    $Pids["backend"] = $res.ProcessId
    for ($i = 0; $i -lt 15; $i++) {
        Start-Sleep -Milliseconds 800
        try {
            $live = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health/ready" -TimeoutSec 1 -ErrorAction Stop
            if ($live.status -eq "ready") { $isBackendUp = $true; break }
        } catch {}
    }
    Write-Host "  FastAPI backend started successfully (PID: $($res.ProcessId))." -ForegroundColor Green
} else {
    Write-Host "  FastAPI backend is already active on 127.0.0.1:8000." -ForegroundColor Green
}

# ------------------------------------------------------------------------------
# 4. Start React + Vite Frontend (Port 5173)
# ------------------------------------------------------------------------------
Write-Host "`n[4/4] Checking React/Vite Frontend (Port 5173)..." -ForegroundColor Yellow
$isFrontendUp = $false
try {
    $req = Invoke-WebRequest -Uri "http://127.0.0.1:5173" -TimeoutSec 2 -UseBasicParsing -ErrorAction SilentlyContinue
    if ($req.StatusCode -eq 200) { $isFrontendUp = $true }
} catch {}

if (-not $isFrontendUp) {
    Write-Host "  Starting native Vite development server..."
    $frontendDir = Join-Path $ProjectRoot "frontend"
    # Launch npm run dev
    $cmd = "cmd.exe /c npm run dev -- --host 127.0.0.1 --port 5173"
    $res = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ 
        CommandLine = $cmd
        CurrentDirectory = $frontendDir
    }
    if ($res.ReturnValue -ne 0) {
        Write-Error "Failed to spawn Vite frontend. Return code: $($res.ReturnValue)"
    }
    $Pids["frontend"] = $res.ProcessId
    for ($i = 0; $i -lt 25; $i++) {
        Start-Sleep -Milliseconds 800
        try {
            $req = Invoke-WebRequest -Uri "http://127.0.0.1:5173" -TimeoutSec 1 -UseBasicParsing -ErrorAction Stop
            if ($req.StatusCode -eq 200) { $isFrontendUp = $true; break }
        } catch {}
    }
    Write-Host "  Frontend started successfully (PID: $($res.ProcessId))." -ForegroundColor Green
} else {
    Write-Host "  Frontend is already active on 127.0.0.1:5173." -ForegroundColor Green
}

# Save PID registry
$Pids | ConvertTo-Json | Set-Content -Path $PidFile -Force

# ------------------------------------------------------------------------------
# Readiness Verification & Status Summary
# ------------------------------------------------------------------------------
Start-Sleep -Seconds 2
Write-Host "`n==========================================================" -ForegroundColor Green
Write-Host "   K N O V E R A  —  All Native Services Operational!     " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "  Frontend Application:   http://127.0.0.1:5173" -ForegroundColor Cyan
Write-Host "  Backend API Docs:       http://127.0.0.1:8000/docs" -ForegroundColor Cyan
Write-Host "  System Health Probe:    http://127.0.0.1:8000/health/ready" -ForegroundColor Cyan
Write-Host "  Vector Store Heartbeat: http://127.0.0.1:8001/api/v2/heartbeat" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "  Run .\scripts\windows\status.ps1 to inspect health."
Write-Host "  Run .\scripts\windows\stop.ps1 to gracefully stop."
