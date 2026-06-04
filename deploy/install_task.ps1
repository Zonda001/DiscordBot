# Registers the bot for 24/7 autostart via Task Scheduler.
# Run (as your user, admin not required):
#   powershell -ExecutionPolicy Bypass -File deploy\install_task.ps1
$ErrorActionPreference = 'Stop'

$TaskName = 'DiscordBot24_7'
$bat = Join-Path $PSScriptRoot 'run_24_7.bat'

if (-not (Test-Path $bat)) { throw "Not found: $bat" }

# Launch the bat minimized in a hidden-ish window
$action = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument "/c start `"`" /min `"$bat`""

# Trigger: at user logon
$trigger = New-ScheduledTaskTrigger -AtLogOn

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 999 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $TaskName `
    -Action $action -Trigger $trigger -Settings $settings `
    -Description 'Combined Discord bot: 24/7 autostart with crash restart' `
    -Force | Out-Null

Write-Host "OK: task '$TaskName' registered (starts at logon)."
Write-Host "Start now:  Start-ScheduledTask -TaskName $TaskName"
Write-Host "Stop:       Stop-ScheduledTask  -TaskName $TaskName"
Write-Host "Remove:     deploy\uninstall_task.ps1"
