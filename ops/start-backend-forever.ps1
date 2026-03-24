param(
    [string]$PythonExe = "",
    [int]$RestartDelaySeconds = 5
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $repoRoot "backend"
$logDir = Join-Path $repoRoot "ops\logs"

if (!(Test-Path $logDir)) {
    New-Item -Path $logDir -ItemType Directory | Out-Null
}

if ([string]::IsNullOrWhiteSpace($PythonExe)) {
    $PythonExe = Join-Path $backendDir ".venv\Scripts\python.exe"
}

if (!(Test-Path $PythonExe)) {
    throw "Python executable not found: $PythonExe"
}

$stdoutLog = Join-Path $logDir "backend.out.log"
$stderrLog = Join-Path $logDir "backend.err.log"

Set-Location $backendDir
Write-Host "Starting backend watchdog from $backendDir"
Write-Host "Python: $PythonExe"

while ($true) {
    $startTs = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$startTs] Launching backend api.py"

    & $PythonExe "api.py" 1>>$stdoutLog 2>>$stderrLog

    $exitCode = $LASTEXITCODE
    $stopTs = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$stopTs] Backend exited with code $exitCode. Restarting in $RestartDelaySeconds seconds..."
    Start-Sleep -Seconds $RestartDelaySeconds
}
