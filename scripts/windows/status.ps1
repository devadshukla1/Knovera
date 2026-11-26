# ==============================================================================
# Knovera Native Windows Health & Status Inspection Script
# scripts/windows/status.ps1
# ==============================================================================
[CmdletBinding()]
param()

$KnoveraBase = Join-Path $env:LOCALAPPDATA "Knovera"
$PgBinDir = Join-Path $env:LOCALAPPDATA "Programs\PostgreSQL\16\bin"
if (-not (Test-Path (Join-Path $PgBinDir "pg_isready.exe"))) {
    $sysPg = Get-Command pg_isready.exe -ErrorAction SilentlyContinue
    if ($sysPg) { $PgBinDir = Split-Path $sysPg.Source }
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   K N O V E R A  —  Native Windows System Status         " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$services = @()

$PidFile = Join-Path $KnoveraBase "runtime\pids.json"
$Pids = @{}
if (Test-Path $PidFile) {
    try { $Pids = Get-Content $PidFile -Raw | ConvertFrom-Json -AsHashtable } catch { $Pids = @{} }
}

function Get-PortConnection([int]$Port) {
    return (Get-NetTCPConnection -ErrorAction SilentlyContinue | Where-Object { $_.LocalPort -eq $Port } | Select-Object -First 1)
}

# 1. PostgreSQL (Port 5432)
$pgPort = 5432
$pgConn = Get-PortConnection $pgPort
$pgStatus = "STOPPED"
$pgLatency = "-"
if ($pgConn) {
    try {
        $sw = [System.Diagnostics.Stopwatch]::StartNew()
        & (Join-Path $PgBinDir "pg_isready.exe") -h 127.0.0.1 -p $pgPort 2>$null | Out-Null
        $sw.Stop()
        if ($LASTEXITCODE -eq 0) {
            $pgStatus = "HEALTHY"
            $pgLatency = "$([math]::Round($sw.Elapsed.TotalMilliseconds, 1)) ms"
        } else {
            $pgStatus = "RUNNING"
            $pgLatency = "$([math]::Round($sw.Elapsed.TotalMilliseconds, 1)) ms"
        }
    } catch {
        $pgStatus = "RUNNING"
    }
}
$services += [PSCustomObject]@{
    Component = "PostgreSQL 16 Database"
    Port      = $pgPort
    PID       = if ($pgConn) { $pgConn.OwningProcess } else { "-" }
    Status    = $pgStatus
    Latency   = $pgLatency
    Endpoint  = "127.0.0.1:$pgPort"
}

# 2. ChromaDB (Port 8001)
$chromaPort = 8001
$chromaConn = Get-PortConnection $chromaPort
$chromaStatus = "STOPPED"
$chromaLatency = "-"
if ($chromaConn) {
    try {
        $sw = [System.Diagnostics.Stopwatch]::StartNew()
        $hb = Invoke-RestMethod -Uri "http://127.0.0.1:$chromaPort/api/v2/heartbeat" -TimeoutSec 2 -ErrorAction Stop
        $sw.Stop()
        if ($hb) {
            $chromaStatus = "HEALTHY"
            $chromaLatency = "$([math]::Round($sw.Elapsed.TotalMilliseconds, 1)) ms"
        }
    } catch {
        $chromaStatus = "DEGRADED"
    }
}
$services += [PSCustomObject]@{
    Component = "ChromaDB Vector Store"
    Port      = $chromaPort
    PID       = if ($chromaConn) { $chromaConn.OwningProcess } else { "-" }
    Status    = $chromaStatus
    Latency   = $chromaLatency
    Endpoint  = "http://127.0.0.1:$chromaPort/api/v2/heartbeat"
}

# 3. FastAPI Backend (Port 8000)
$backendPort = 8000
$backendConn = Get-PortConnection $backendPort
$backendStatus = "STOPPED"
$backendLatency = "-"
if ($backendConn) {
    try {
        $sw = [System.Diagnostics.Stopwatch]::StartNew()
        $ready = Invoke-RestMethod -Uri "http://127.0.0.1:$backendPort/health/ready" -TimeoutSec 3 -ErrorAction Stop
        $sw.Stop()
        if ($ready.status -eq "ready") {
            $backendStatus = "HEALTHY"
            $backendLatency = "$([math]::Round($sw.Elapsed.TotalMilliseconds, 1)) ms"
        } else {
            $backendStatus = "DEGRADED ($($ready.status))"
        }
    } catch {
        try {
            $live = Invoke-RestMethod -Uri "http://127.0.0.1:$backendPort/health" -TimeoutSec 2 -ErrorAction Stop
            if ($live.status -eq "ok") { $backendStatus = "DEGRADED (Liveness OK)" }
        } catch {
            $backendStatus = "UNRESPONSIVE"
        }
    }
}
$services += [PSCustomObject]@{
    Component = "FastAPI Backend API"
    Port      = $backendPort
    PID       = if ($backendConn -and $backendConn.OwningProcess -ne 0) { $backendConn.OwningProcess } elseif ($Pids["backend"]) { $Pids["backend"] } else { "-" }
    Status    = $backendStatus
    Latency   = $backendLatency
    Endpoint  = "http://127.0.0.1:$backendPort/health/ready"
}

# 4. Vite Frontend (Port 5173)
$frontendPort = 5173
$frontendConn = Get-PortConnection $frontendPort
$frontendStatus = "STOPPED"
$frontendLatency = "-"
if ($frontendConn) {
    try {
        $sw = [System.Diagnostics.Stopwatch]::StartNew()
        $fe = Invoke-WebRequest -Uri "http://127.0.0.1:$frontendPort" -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
        $sw.Stop()
        if ($fe.StatusCode -eq 200) {
            $frontendStatus = "HEALTHY"
            $frontendLatency = "$([math]::Round($sw.Elapsed.TotalMilliseconds, 1)) ms"
        }
    } catch {
        $frontendStatus = "UNRESPONSIVE"
    }
}
$services += [PSCustomObject]@{
    Component = "React + Vite Frontend"
    Port      = $frontendPort
    PID       = if ($frontendConn) { $frontendConn.OwningProcess } else { "-" }
    Status    = $frontendStatus
    Latency   = $frontendLatency
    Endpoint  = "http://127.0.0.1:$frontendPort"
}

Write-Host ""
$services | Format-Table -Property Component, Port, PID, Status, Latency, Endpoint -AutoSize

Write-Host "`nDirectories:" -ForegroundColor DarkGray
Write-Host "  Data:    $KnoveraBase\data" -ForegroundColor DarkGray
Write-Host "  Logs:    $KnoveraBase\logs" -ForegroundColor DarkGray
Write-Host "  Runtime: $KnoveraBase\runtime" -ForegroundColor DarkGray
Write-Host "==========================================================" -ForegroundColor Cyan
