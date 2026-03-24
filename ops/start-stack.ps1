$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot

$backendScript = Join-Path $PSScriptRoot "start-backend-forever.ps1"
$dashboardScript = Join-Path $PSScriptRoot "start-dashboard-forever.ps1"

Start-Process powershell -ArgumentList @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    $backendScript
) -WorkingDirectory $repoRoot

Start-Process powershell -ArgumentList @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    $dashboardScript
) -WorkingDirectory $repoRoot

Write-Host "Backend and dashboard watchdog processes launched."
