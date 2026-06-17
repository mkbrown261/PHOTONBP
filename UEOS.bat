@echo off
setlocal EnableDelayedExpansion
title UEOS Launcher
cd /d "%~dp0"

:: ── First-run guard ─────────────────────────────────────────────────────────
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
    echo  ERROR: Python not found. Please run SETUP.bat first.
    echo.
    pause
    exit /b 1
)

:: ── Silent auto-fix: re-inject configs on every launch (safe / idempotent) ──
::
::    Both scripts exit 0 (changed) or 2 (already correct) — never destructive.
::    This means users NEVER have to manually run anything after Claude Desktop
::    is installed post-setup, or after adding a new UE project.
::
echo  Checking configuration...
python setup\inject_claude_config.py >nul 2>&1
set CLAUDE_RC=%errorlevel%

python setup\inject_ue_settings.py >nul 2>&1
set UE_RC=%errorlevel%

:: If Claude Desktop was newly detected this run, show a one-time notice
if %CLAUDE_RC% equ 0 (
    echo.
    echo  ✓ UEOS added to Claude Desktop — please restart Claude Desktop.
    echo.
)

:: ── Quick dependency check ───────────────────────────────────────────────────
python -c "import mcp, aiohttp, dotenv, tkinter" >nul 2>&1
if %errorlevel% neq 0 (
    echo  Updating dependencies...
    python -m pip install -r requirements.txt --quiet
)

:: ── Launch GUI ───────────────────────────────────────────────────────────────
echo  Starting UEOS...
start "" python ui\launcher.py
if %errorlevel% neq 0 (
    echo.
    echo  ERROR: Could not launch UEOS launcher.
    echo.
    echo  Check ui\launcher_crash.log for details.
    echo.
    pause
)

endlocal
