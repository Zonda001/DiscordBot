# Removes the panel autostart shortcut (per-user, no admin).
$ErrorActionPreference = 'Stop'
$startup = [Environment]::GetFolderPath('Startup')
$lnkPath = Join-Path $startup 'DiscordBotPanel.lnk'
if (Test-Path $lnkPath) {
    Remove-Item $lnkPath -Force
    Write-Host "Removed panel startup shortcut: $lnkPath"
} else {
    Write-Host "No panel startup shortcut found."
}
