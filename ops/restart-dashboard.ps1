param(
    [string]$MiniPcHost = "192.168.1.68",
    [string]$MiniPcUser = "openclaw",
    [int]$SshPort = 22,
    [string]$RemoteDir = "/home/openclaw/trading-bot/dashboard"
)

$remote = "${MiniPcUser}@${MiniPcHost}"

# Write remote restart script to a temp file, scp it, run it
$bashScript = @'
#!/bin/bash
pkill -f "next start" 2>/dev/null || true
sleep 1
cd REMOTE_DIR
nohup npm start > /home/openclaw/dashboard.log 2>&1 </dev/null &
echo "Dashboard restarted (PID: $!)"
'@

$bashScript = $bashScript -replace "REMOTE_DIR", $RemoteDir
$tmpScript = "$env:TEMP\restart-dashboard.sh"
# Force Unix line endings (LF only) to avoid \r issues on Linux
$unixContent = $bashScript -replace "`r`n", "`n" -replace "`r", "`n"
[System.IO.File]::WriteAllText($tmpScript, $unixContent, [System.Text.Encoding]::UTF8)

Write-Host "Uploading restart script..."
& scp -P $SshPort $tmpScript "${remote}:/tmp/restart-dashboard.sh"

Write-Host "Running restart script on mini PC..."
& ssh -p $SshPort $remote "bash /tmp/restart-dashboard.sh; rm /tmp/restart-dashboard.sh"

Write-Host "Restart complete (exit: $LASTEXITCODE)"
