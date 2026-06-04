# Removes the bot from Windows Startup (per-user, no admin).
$ErrorActionPreference = 'Stop'
$startup = [Environment]::GetFolderPath('Startup')
$lnkPath = Join-Path $startup 'DiscordBot24_7.lnk'
if (Test-Path $lnkPath) {
    Remove-Item $lnkPath -Force
    Write-Host "Removed startup shortcut: $lnkPath"
} else {
    Write-Host "No startup shortcut found."
}
