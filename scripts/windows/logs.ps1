# ==============================================================================
# Knovera Native Windows Log Viewer Script
# scripts/windows/logs.ps1
# ==============================================================================
[CmdletBinding()]
param(
    [ValidateSet("postgres", "chroma", "backend", "frontend", "all")]
    [string]$Service = "all",

    [int]$Tail = 40,

    [switch]$Follow
)

$KnoveraBase = Join-Path $env:LOCALAPPDATA "Knovera"
$LogsDir = Join-Path $KnoveraBase "logs"

if (-not (Test-Path $LogsDir)) {
    Write-Warning "No logs directory found at $LogsDir."
    return
}

function Show-ServiceLog {
    param([string]$LogName, [string]$FileTitle)
    $logPath = Join-Path $LogsDir $LogName
    Write-Host "`n--- $FileTitle ($logPath) ---" -ForegroundColor Cyan
    if (Test-Path $logPath) {
        if ($Follow) {
            Get-Content -Path $logPath -Tail $Tail -Wait
        } else {
            Get-Content -Path $logPath -Tail $Tail
        }
    } else {
        Write-Host "  (Log file not yet created)" -ForegroundColor DarkGray
    }
}

switch ($Service) {
    "postgres" { Show-ServiceLog "postgres.log" "PostgreSQL 16 Server Log" }
    "chroma"   { Show-ServiceLog "chroma.log" "ChromaDB HTTP Server Log" }
    "backend"  { Show-ServiceLog "backend.log" "FastAPI Backend Log" }
    "frontend" { Show-ServiceLog "frontend.log" "Vite Frontend Log" }
    "all" {
        Show-ServiceLog "postgres.log" "PostgreSQL 16 Server Log"
        Show-ServiceLog "chroma.log" "ChromaDB HTTP Server Log"
        Show-ServiceLog "backend.log" "FastAPI Backend Log"
        Show-ServiceLog "frontend.log" "Vite Frontend Log"
    }
}
