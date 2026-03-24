param(
    [Parameter(Mandatory = $true)]
    [string]$MiniPcHost,
    [string]$MiniPcUser = "openclaw",
    [string]$RemoteBaseDir = "/home/openclaw",
    [int]$SshPort = 22,
    [switch]$InstallAndBuild
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($MiniPcHost)) {
    throw "MiniPcHost is required, e.g. -MiniPcHost 192.168.1.68"
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$projectName = Split-Path -Leaf $repoRoot
$repoParent = Split-Path -Parent $repoRoot
$archiveName = "$projectName-sync.tar.gz"
$archivePath = Join-Path $env:TEMP $archiveName

Write-Host "Preparing archive from $repoRoot"
if (Test-Path $archivePath) {
    Remove-Item -Force $archivePath
}

Push-Location $repoParent
try {
    tar -czf $archivePath `
        --exclude "$projectName/.git" `
        --exclude "$projectName/backend/.venv" `
        --exclude "$projectName/dashboard/node_modules" `
        --exclude "$projectName/dashboard/.next" `
        --exclude "$projectName/ops/logs" `
        --exclude "$projectName/*.db" `
        --exclude "$projectName/*.db-shm" `
        --exclude "$projectName/*.db-wal" `
        $projectName
}
finally {
    Pop-Location
}

if (!(Test-Path $archivePath)) {
    throw "Failed to create archive at $archivePath"
}

$remoteArchivePath = "$RemoteBaseDir/$archiveName"
$remoteProjectDir = "$RemoteBaseDir/$projectName"
$remoteBackupDir = "$remoteProjectDir/ops/backups"
$remote = "$MiniPcUser@$MiniPcHost"
$remoteScpTarget = $remote + ":" + $remoteArchivePath

Write-Host ("Copying archive to {0}:{1}" -f $remote, $remoteArchivePath)
& scp -P $SshPort $archivePath $remoteScpTarget
if ($LASTEXITCODE -ne 0) {
    throw "SCP transfer failed with exit code $LASTEXITCODE"
}

$extractCmd = (
    @(
        "set -e",
        "mkdir -p '$remoteProjectDir'",
        "mkdir -p '$remoteBackupDir'",
        "if [ -d '$remoteProjectDir/backend' ] || [ -d '$remoteProjectDir/dashboard' ]; then tar -czf '$remoteBackupDir/pre-sync-latest.tgz' -C '$remoteProjectDir' backend dashboard README.md 2>/dev/null || true; fi",
        "rm -rf '$remoteProjectDir/dashboard'",
        "tar -xzf '$remoteArchivePath' -C '$RemoteBaseDir'",
        "rm -f '$remoteArchivePath'"
    ) -join "; "
)

Write-Host "Extracting project on mini PC"
& ssh -p $SshPort $remote $extractCmd
if ($LASTEXITCODE -ne 0) {
    throw "Remote extract step failed with exit code $LASTEXITCODE"
}

if ($InstallAndBuild) {
    $setupCmd = (
        @(
            "set -e",
            "cd '$remoteProjectDir/dashboard'",
            "npm install",
            "npm run build",
            "cd '$remoteProjectDir/backend'",
            "if [ ! -d .venv ]; then python3 -m venv .venv; fi",
            ". .venv/bin/activate",
            "pip install -r requirements.txt",
            "python3 -m py_compile api.py bot.py db.py orchestrator.py risk_engine.py fair_value_engine.py simulation.py ta_scanner.py validators.py"
        ) -join "; "
    )
    Write-Host "Running remote install/build steps"
    & ssh -p $SshPort $remote $setupCmd
    if ($LASTEXITCODE -ne 0) {
        throw "Remote install/build step failed with exit code $LASTEXITCODE"
    }

    # Restart backend and dashboard in a separate SSH call.
    $restartCmd = (
        @(
            "set -e",
            "mkdir -p '$remoteProjectDir/ops'",
            "pkill -f 'python3 api.py' || true",
            "pkill -f 'next start' || true",
            "pkill -f 'next dev' || true",
            "pkill -f 'vite preview' || true",
            "pkill -f '^vite$' || true",
            "nohup '$remoteProjectDir/backend/.venv/bin/python' '$remoteProjectDir/backend/api.py' > '$remoteProjectDir/ops/backend-runtime.log' 2>&1 < /dev/null &",
            "cd '$remoteProjectDir/dashboard'",
            "nohup npm run preview -- --host 0.0.0.0 --port 3000 > '$remoteProjectDir/ops/dashboard-runtime.log' 2>&1 < /dev/null &",
            "echo RESTARTED"
        ) -join "; "
    )
    Write-Host "Restarting backend and dashboard on mini PC"
    & ssh -p $SshPort $remote $restartCmd
    Write-Host "Remote restart issued (exit: $LASTEXITCODE)"
}

Remove-Item -Force $archivePath
Write-Host "Sync complete. Remote project path: $remoteProjectDir"
