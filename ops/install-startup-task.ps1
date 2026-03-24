param(
    [string]$TaskName = "TradingBotStack"
)

$ErrorActionPreference = "Stop"
$stackScript = Join-Path $PSScriptRoot "start-stack.ps1"

if (!(Test-Path $stackScript)) {
    throw "Missing script: $stackScript"
}

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$stackScript`""
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1)
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERNAME" -LogonType Interactive -RunLevel Highest

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force

Write-Host "Scheduled task '$TaskName' installed. It will launch stack watchdogs at startup."
