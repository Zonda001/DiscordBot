@echo off
title Discord Bot 24/7 (auto-restart)

rem Go to project root (one level up from deploy\)
cd /d "%~dp0.."

set "PYTHON=.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo [ERROR] %PYTHON% not found. Check the virtual environment.
    pause
    exit /b 1
)

rem Python writes rotated logs to discord_bot\data\bot.log
:loop
echo [%date% %time%] Starting bot...
"%PYTHON%" run_bot.py
echo [%date% %time%] Bot exited (code %errorlevel%). Restarting in 10s...
timeout /t 10 /nobreak >nul
goto loop
