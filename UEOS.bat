@echo off
setlocal
title UEOS Launcher
cd /d "%~dp0"

:: ── First-run guard ───────────────────────────────────────────────────────────
:: If setup has never been run, hand off to SETUP.bat automatically
if not exist ".setup_complete" (
    echo.
    echo  First run detected — launching UEOS Setup...
    echo.
    call SETUP.bat
    exit /b
)

:: ── Python check ─────────────────────────────────────────────────────────────
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  ERROR: Python not found.
    echo  Please run SETUP.bat to install Python automatically.
    echo.
    pause
    exit /b 1
)

:: ── Quick dependency check ───────────────────────────────────────────────────
python -c "import mcp, aiohttp, dotenv, tkinter" >nul 2>&1
if %errorlevel% neq 0 (
    echo  Updating dependencies...
    python -m pip install -r requirements.txt --quiet
)

:: ── Launch GUI ───────────────────────────────────────────────────────────────
start "" pythonw ui\launcher.py
if %errorlevel% neq 0 (
    python ui\launcher.py
)

endlocal
