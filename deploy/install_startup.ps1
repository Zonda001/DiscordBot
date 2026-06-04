# Adds the bot to Windows Startup (per-user, NO admin required).
# Creates a shortcut to run_24_7.bat in the user's Startup folder so the bot
# auto-launches (with crash-restart loop) at every logon.
#   powershell -ExecutionPolicy Bypass -File deploy\install_startup.ps1
$ErrorActionPreference = 'Stop'

$bat = Join-Path $PSScriptRoot 'run_24_7.bat'
if (-not (Test-Path $bat)) { throw "Not found: $bat" }

$startup = [Environment]::GetFolderPath('Startup')
$lnkPath = Join-Path $startup 'DiscordBot24_7.lnk'

$shell = New-Object -ComObject WScript.Shell
$lnk = $shell.CreateShortcut($lnkPath)
$lnk.TargetPath = $bat
$lnk.WorkingDirectory = Split-Path $bat -Parent
$lnk.WindowStyle = 7        # minimized
$lnk.Description = 'Combined Discord bot 24/7'
$lnk.Save()

Write-Host "OK: startup shortcut created -> $lnkPath"
Write-Host "The bot will auto-start at next logon. To remove: delete that .lnk"
Write-Host "or run deploy\uninstall_startup.ps1"
