# Autostart the control PANEL at logon (no admin). The panel supervises the bot.
# Replaces the old bat-based bot autostart to avoid two launch mechanisms.
#   powershell -ExecutionPolicy Bypass -File deploy\install_startup_panel.ps1
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$pyw = Join-Path $root '.venv\Scripts\pythonw.exe'
$app = Join-Path $root 'panel\app.py'
if (-not (Test-Path $pyw)) { throw "Not found: $pyw" }
if (-not (Test-Path $app)) { throw "Not found: $app" }

$startup = [Environment]::GetFolderPath('Startup')

# Remove old bot-only autostart shortcut to avoid double launch
$old = Join-Path $startup 'DiscordBot24_7.lnk'
if (Test-Path $old) { Remove-Item $old -Force; Write-Host "Removed old startup: DiscordBot24_7.lnk" }

$lnkPath = Join-Path $startup 'DiscordBotPanel.lnk'
$shell = New-Object -ComObject WScript.Shell
$lnk = $shell.CreateShortcut($lnkPath)
$lnk.TargetPath = $pyw
$lnk.Arguments = '"' + $app + '" --autostart'
$lnk.WorkingDirectory = $root
$lnk.WindowStyle = 7        # minimized
$lnk.Description = 'Discord Bot control panel (supervises the bot)'
$lnk.Save()

Write-Host "OK: panel startup shortcut created -> $lnkPath"
Write-Host "At logon the panel opens (minimized) and auto-starts the bot."
Write-Host "Remove with: deploy\uninstall_startup_panel.ps1"
