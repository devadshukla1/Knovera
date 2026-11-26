# ==============================================================================
# Knovera Native Windows Shutdown Script
# scripts/windows/stop.ps1
# ==============================================================================
[CmdletBinding()]
param(
    [switch]$IncludePostgres
)

Write-Host "==========================================================" -ForegroundColor Yellow
Write-Host "   K N O V E R A  —  Stopping Native Windows Services     " -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Yellow

$KnoveraBase = Join-Path $env:LOCALAPPDATA "Knovera"
$RuntimeDir = Join-Path $KnoveraBase "runtime"
$PidFile = Join-Path $RuntimeDir "pids.json"

function Stop-KnoveraProcess {
    param(
        [string]$Name,
        [int]$Port,
        [string]$MatchPattern
    )

    Write-Host "Checking $Name..." -NoNewline
    $killed = $false

    # Check connection on port
    $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($conns) {
        foreach ($conn in $conns) {
            $pidToStop = $conn.OwningProcess
            if ($pidToStop -and $pidToStop -ne 0 -and $pidToStop -ne 4) {
                try {
                    $proc = Get-Process -Id $pidToStop -ErrorAction SilentlyContinue
                    if ($proc) {
                        # Verify process name / command line safety
                        if ($proc.ProcessName -match $MatchPattern -or $proc.Path -match "Knovera|node|python|chroma|postgres") {
                            Stop-Process -Id $pidToStop -Force -ErrorAction SilentlyContinue
                            Write-Host " Stopped PID $pidToStop ($($proc.ProcessName))." -ForegroundColor Green
                            $killed = $true
                        }
                    }
                } catch {}
            }
        }
    }

    if (-not $killed) {
        Write-Host " Inactive (no listening process on port $Port)." -ForegroundColor DarkGray
    }
}

# 1. Stop Frontend (Port 5173)
Stop-KnoveraProcess -Name "Frontend (Vite)" -Port 5173 -MatchPattern "node"

# 2. Stop Backend (Port 8000)
Stop-KnoveraProcess -Name "Backend (FastAPI/Uvicorn)" -Port 8000 -MatchPattern "python"

# 3. Stop ChromaDB (Port 8001)
Stop-KnoveraProcess -Name "Vector Store (ChromaDB)" -Port 8001 -MatchPattern "chroma|python"

# 4. Stop PostgreSQL (Optional, Port 5432)
if ($IncludePostgres) {
    Write-Host "Stopping PostgreSQL daemon on port 5432 as requested..."
    $PgBinDir = Join-Path $env:LOCALAPPDATA "Programs\PostgreSQL\16\bin"
    $PgData = Join-Path $KnoveraBase "data\postgres"
    if (Test-Path (Join-Path $PgBinDir "pg_ctl.exe")) {
        & (Join-Path $PgBinDir "pg_ctl.exe") -D $PgData stop -m fast 2>$null | Out-Null
    }
    Stop-KnoveraProcess -Name "Database (PostgreSQL)" -Port 5432 -MatchPattern "postgres"
} else {
    Write-Host "PostgreSQL left running on port 5432 (pass -IncludePostgres to shut down DB)." -ForegroundColor Cyan
}

# Clean PID file
if (Test-Path $PidFile) {
    Remove-Item -Force $PidFile -ErrorAction SilentlyContinue
}

Write-Host "`nAll targeted Knovera services have been stopped safely." -ForegroundColor Green
