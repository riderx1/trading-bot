param(
    [int]$Port = 3000,
    [int]$RestartDelaySeconds = 5
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$dashboardDir = Join-Path $repoRoot "dashboard"
$logDir = Join-Path $repoRoot "ops\logs"

if (!(Test-Path $logDir)) {
    New-Item -Path $logDir -ItemType Directory | Out-Null
}

$npmCmd = (Get-Command npm -ErrorAction Stop).Source
$stdoutLog = Join-Path $logDir "dashboard.out.log"
$stderrLog = Join-Path $logDir "dashboard.err.log"

Set-Location $dashboardDir

Write-Host "Installing dashboard dependencies if needed..."
& $npmCmd install

Write-Host "Building dashboard for production..."
& $npmCmd run build

Write-Host "Starting dashboard watchdog from $dashboardDir"

while ($true) {
    $startTs = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$startTs] Launching Next.js server on 0.0.0.0:$Port"

    & $npmCmd run start:lan -- --port $Port 1>>$stdoutLog 2>>$stderrLog

    $exitCode = $LASTEXITCODE
    $stopTs = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$stopTs] Dashboard exited with code $exitCode. Restarting in $RestartDelaySeconds seconds..."
    Start-Sleep -Seconds $RestartDelaySeconds
}
