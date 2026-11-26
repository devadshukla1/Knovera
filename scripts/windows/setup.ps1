# ==============================================================================
# Knovera Native Windows Setup Script
# scripts/windows/setup.ps1
# ==============================================================================
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path "$PSScriptRoot\..\..").Path
Set-Location $ProjectRoot

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   K N O V E R A  —  Native Windows Environment Setup     " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. System Inventory
Write-Host "`n[1/7] Inspecting Operating System & Hardware..." -ForegroundColor Yellow
$os = Get-CimInstance Win32_OperatingSystem
$cpu = Get-CimInstance Win32_Processor
Write-Host "  OS:           $($os.Caption) ($($os.OSArchitecture), Build $($os.Version))"
Write-Host "  CPU:          $($cpu.Name)"
Write-Host "  Memory:       $([math]::Round($os.TotalVisibleMemorySize / 1MB, 1)) GB RAM"

# 2. Python Environment Check
Write-Host "`n[2/7] Checking Python Environment..." -ForegroundColor Yellow
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Error "Virtual environment not found at $VenvPython. Please initialize .venv first."
}
$pyVer = & $VenvPython --version
Write-Host "  Python:       $pyVer ($VenvPython)"

# 3. Node & NPM Check
Write-Host "`n[3/7] Checking Node.js & npm..." -ForegroundColor Yellow
$nodeCmd = Get-Command node -ErrorAction SilentlyContinue
$npmCmd = Get-Command npm -ErrorAction SilentlyContinue
if (-not $nodeCmd -or -not $npmCmd) {
    Write-Error "Node.js or npm not found in system PATH."
}
$nodeVer = & node --version
$npmVer = & npm --version
Write-Host "  Node.js:      $nodeVer"
Write-Host "  npm:          $npmVer"

# 4. Local Runtime Directories
Write-Host "`n[4/7] Preparing Local Knovera Directories..." -ForegroundColor Yellow
$KnoveraBase = Join-Path $env:LOCALAPPDATA "Knovera"
$PgData = Join-Path $KnoveraBase "data\postgres"
$ChromaData = Join-Path $KnoveraBase "data\chroma"
$LogsDir = Join-Path $KnoveraBase "logs"
$RuntimeDir = Join-Path $KnoveraBase "runtime"

foreach ($dir in @($KnoveraBase, "$KnoveraBase\data", $PgData, $ChromaData, $LogsDir, $RuntimeDir)) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
    }
}
Write-Host "  Base:         $KnoveraBase"
Write-Host "  PostgreSQL:   $PgData"
Write-Host "  ChromaDB:     $ChromaData"
Write-Host "  Logs:         $LogsDir"
Write-Host "  Runtime:      $RuntimeDir"

# 5. Native PostgreSQL Installation & Cluster
Write-Host "`n[5/7] Verifying Native PostgreSQL 16..." -ForegroundColor Yellow
$PgBinDir = Join-Path $env:LOCALAPPDATA "Programs\PostgreSQL\16\bin"
if (-not (Test-Path (Join-Path $PgBinDir "postgres.exe"))) {
    # Check system PATH fallback
    $sysPg = Get-Command postgres.exe -ErrorAction SilentlyContinue
    if ($sysPg) {
        $PgBinDir = Split-Path $sysPg.Source
    } else {
        Write-Error "PostgreSQL 16 binaries not found in $PgBinDir or system PATH."
    }
}
$pgVersion = & (Join-Path $PgBinDir "postgres.exe") --version
Write-Host "  PostgreSQL:   $pgVersion ($PgBinDir)"

# Initialize cluster if empty
if (-not (Test-Path (Join-Path $PgData "PG_VERSION"))) {
    Write-Host "  Initializing new PostgreSQL cluster in $PgData..."
    & (Join-Path $PgBinDir "initdb.exe") -D $PgData -U postgres -E UTF8 --locale=C -A trust | Out-Null
    Write-Host "  PostgreSQL cluster initialized."
} else {
    Write-Host "  Existing cluster found at $PgData."
}

# 6. Environment File Validation
Write-Host "`n[6/7] Validating .env Configuration..." -ForegroundColor Yellow
$envPath = Join-Path $ProjectRoot ".env"
if (-not (Test-Path $envPath)) {
    Write-Host "  Creating .env from .env.example..."
    Copy-Item (Join-Path $ProjectRoot ".env.example") $envPath
}
Write-Host "  .env file present."

# 7. Database Migrations (Alembic)
Write-Host "`n[7/7] Verifying Database Connectivity & Running Migrations..." -ForegroundColor Yellow
$AlembicExe = Join-Path $ProjectRoot ".venv\Scripts\alembic.exe"
$AlembicIni = Join-Path $ProjectRoot "backend\alembic.ini"

# Ensure postgres is running for migration check
$pgReady = & (Join-Path $PgBinDir "pg_isready.exe") -h 127.0.0.1 -p 5432 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "  Starting temporary PostgreSQL instance for migrations..."
    $cmd = "`"$PgBinDir\postgres.exe`" -D `"$PgData`""
    $res = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = $cmd }
    Start-Sleep -Seconds 3
}

# Provision role and database if missing
& (Join-Path $PgBinDir "psql.exe") -U postgres -h 127.0.0.1 -p 5432 -c "DO \$\$ BEGIN IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'knovera_app') THEN CREATE ROLE knovera_app WITH LOGIN SUPERUSER PASSWORD 'change_me_locally'; END IF; END \$\$;" 2>$null | Out-Null
& (Join-Path $PgBinDir "createdb.exe") -U postgres -h 127.0.0.1 -p 5432 -O knovera_app knovera 2>$null | Out-Null

Write-Host "  Applying Alembic migrations to head..."
& $AlembicExe -c $AlembicIni upgrade head
$currentRev = & $AlembicExe -c $AlembicIni current
Write-Host "  Alembic Migration State: $currentRev"

Write-Host "`n==========================================================" -ForegroundColor Green
Write-Host "  Knovera Native Windows Setup: COMPLETED SUCCESSFULLY!  " -ForegroundColor Green
Write-Host "  Run .\scripts\windows\start.ps1 to launch all services. " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
