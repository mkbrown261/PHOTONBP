@echo off
setlocal EnableDelayedExpansion
title UEOS Setup
cd /d "%~dp0"

:: ── Banner ────────────────────────────────────────────────────────────────────
echo.
echo  ╔══════════════════════════════════════════════════╗
echo  ║         UEOS — First-Time Setup                  ║
echo  ║         Unreal Engine Operating System           ║
echo  ╚══════════════════════════════════════════════════╝
echo.
echo  Setting up everything UEOS needs...
echo.

:: ============================================================
::  STEP 1 — Python
:: ============================================================
echo [1/5] Checking Python...

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  Python not found. Downloading Python 3.11.9...
    echo.
    where curl >nul 2>&1
    if %errorlevel% neq 0 (
        echo  ERROR: curl not found. Install Python manually:
        echo  https://www.python.org/downloads/
        pause
        exit /b 1
    )
    set "PY_INSTALLER=%TEMP%\python_ueos_installer.exe"
    curl -L --progress-bar -o "%PY_INSTALLER%" "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
    if %errorlevel% neq 0 (
        echo  Download failed. Install Python manually: https://www.python.org/downloads/
        pause
        exit /b 1
    )
    "%PY_INSTALLER%" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0 Include_launcher=1
    del "%PY_INSTALLER%" >nul 2>&1
    echo  Python installed. Restarting setup in new shell...
    set UEOS_RELAUNCH=1
    start "" /wait cmd /c "%~f0"
    exit /b 0
)

for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PY_VER=%%v
echo  OK: Python %PY_VER%
echo.

:: ============================================================
::  STEP 2 — pip dependencies
:: ============================================================
echo [2/5] Installing dependencies...

python -c "import mcp, aiohttp, dotenv, tkinter, fastapi, uvicorn" >nul 2>&1
if %errorlevel% equ 0 (
    echo  OK: All dependencies already installed
) else (
    python -m pip install --upgrade pip --quiet
    python -m pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo  ERROR: pip install failed. Try running as Administrator.
        pause
        exit /b 1
    )
    echo  OK: Dependencies installed
)
echo.

:: ============================================================
::  STEP 3 — Claude Desktop config
:: ============================================================
echo [3/5] Configuring Claude Desktop...

python setup\inject_claude_config.py
set CLAUDE_RC=%errorlevel%
if %CLAUDE_RC% equ 0 (
    echo  OK: Claude Desktop config written. Restart Claude Desktop.
) else if %CLAUDE_RC% equ 2 (
    echo  OK: Claude Desktop already configured.
) else (
    echo  NOTE: Claude Desktop not found. Install from https://claude.ai/download
    echo  UEOS will configure it automatically next launch.
)
echo.

:: ============================================================
::  STEP 4 — UE project settings
:: ============================================================
echo [4/5] Configuring Unreal Engine projects...

python setup\inject_ue_settings.py
set UE_RC=%errorlevel%
if %UE_RC% equ 0 (
    echo  OK: UE project settings patched. Restart UE5.
) else if %UE_RC% equ 2 (
    echo  OK: UE projects already configured.
) else (
    echo  NOTE: No UE projects found. Will auto-patch when you open one.
)
echo.

:: ============================================================
::  STEP 5 — Finalise
:: ============================================================
echo [5/5] Finalising...

if not exist ".env" (
    if exist ".env.example" (
        copy ".env.example" ".env" >nul
        echo  OK: Created .env
    )
)

:: Write setup complete marker
echo 1>.setup_complete
echo  OK: Setup complete
echo.

:: ── Done ─────────────────────────────────────────────────────────────────────
echo  ╔══════════════════════════════════════════════════╗
echo  ║              Setup Complete!                     ║
echo  ╚══════════════════════════════════════════════════╝
echo.
echo  Next steps:
echo  1. Restart Claude Desktop
echo  2. Open Unreal Engine 5.4 with Remote Control plugins enabled
echo  3. In Claude Desktop ask: "run ueos_status"
echo.
echo  Launching dashboard in 3 seconds...
echo.
timeout /t 3 /nobreak >nul

start "" python ui\launcher.py

endlocal
