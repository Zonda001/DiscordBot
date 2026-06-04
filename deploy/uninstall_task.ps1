# Removes the 24/7 autostart task.
$ErrorActionPreference = 'Stop'
$TaskName = 'DiscordBot24_7'
try {
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed task '$TaskName'."
} catch {
    Write-Host "Task '$TaskName' not found."
}
