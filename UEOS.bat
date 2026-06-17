@echo off
setlocal
title UEOS
cd /d "%~dp0"

:: First run — go through setup
if not exist ".setup_complete" (
    call SETUP.bat
    exit /b
)

:: Python check
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found. Run SETUP.bat first.
    pause
    exit /b 1
)

:: Silent auto-fix on every launch (idempotent — safe to run every time)
python setup\inject_claude_config.py >nul 2>&1
if %errorlevel% equ 0 (
    echo UEOS added to Claude Desktop — restart Claude Desktop.
)
python setup\inject_ue_settings.py >nul 2>&1

:: Quick dependency check
python -c "import mcp, aiohttp, dotenv, tkinter" >nul 2>&1
if %errorlevel% neq 0 (
    python -m pip install -r requirements.txt --quiet
)

:: Launch dashboard
start "" python ui\launcher.py

endlocal
