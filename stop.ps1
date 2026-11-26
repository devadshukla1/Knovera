# ==============================================================================
# Knovera — 1-Click Stop Script
# Gracefully stops all Knovera services.
# ==============================================================================
[CmdletBinding()]
param(
    [switch]$IncludePostgres
)

$ProjectRoot = (Resolve-Path $PSScriptRoot).Path
Set-Location $ProjectRoot

$stopScript = Join-Path $ProjectRoot "scripts\windows\stop.ps1"
if ($IncludePostgres) {
    powershell -ExecutionPolicy Bypass -File $stopScript -IncludePostgres
} else {
    powershell -ExecutionPolicy Bypass -File $stopScript
}
