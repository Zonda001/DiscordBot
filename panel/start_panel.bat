@echo off
rem Launch the control panel without a console window.
cd /d "%~dp0.."
start "" ".venv\Scripts\pythonw.exe" "panel\app.py" %*
