@echo off
setlocal EnableDelayedExpansion
title UEOS Setup
cd /d "%~dp0"

:: ============================================================
::  UEOS — First-Time Setup
::  Handles: Python install, pip deps, Claude config, UE check
::  Safe to re-run any time.
:: ============================================================

:: Enable ANSI colors (Windows 10 1903+)
reg query "HKCU\Console" /v VirtualTerminalLevel >nul 2>&1
if errorlevel 1 reg add "HKCU\Console" /v VirtualTerminalLevel /t REG_DWORD /d 1 /f >nul 2>&1

:: Color codes via PowerShell echo (fallback-safe)
set "ESC="
for /f %%a in ('powershell -NoProfile -Command "[char]27"') do set "ESC=%%a"
set "GREEN=%ESC%[32m"
set "YELLOW=%ESC%[33m"
set "RED=%ESC%[31m"
set "CYAN=%ESC%[36m"
set "BOLD=%ESC%[1m"
set "DIM=%ESC%[2m"
set "RESET=%ESC%[0m"

:: ── Banner ───────────────────────────────────────────────────────────────────
echo.
echo %BOLD%%CYAN%  ╔══════════════════════════════════════════════════╗%RESET%
echo %BOLD%%CYAN%  ║         UEOS — First-Time Setup                  ║%RESET%
echo %BOLD%%CYAN%  ║         Unreal Engine Operating System           ║%RESET%
echo %BOLD%%CYAN%  ╚══════════════════════════════════════════════════╝%RESET%
echo.
echo %DIM%  This script sets up everything UEOS needs.%RESET%
echo %DIM%  You only need to run this once.%RESET%
echo.

set SETUP_OK=1
set PYTHON_JUST_INSTALLED=0

:: ── Guard: re-launch in fresh shell after Python install ─────────────────────
:: If we already installed Python this session, skip the install block
if "%UEOS_RELAUNCH%"=="1" goto :check_python_version

:: ============================================================
::  STEP 1 — Python
:: ============================================================
echo %BOLD%[1/5] Checking Python...%RESET%
echo.

where python >nul 2>&1
if %errorlevel% equ 0 goto :check_python_version

:: Python not found — download and install silently
echo %YELLOW%  ! Python not found.%RESET%
echo %CYAN%  → Downloading Python 3.11.9 (this may take a minute)...%RESET%
echo.

:: Check curl is available (Windows 10 1803+)
where curl >nul 2>&1
if %errorlevel% neq 0 (
    echo %RED%  ✗ curl not found.%RESET%
    echo.
    echo %YELLOW%  Your Windows version is too old to auto-install Python.%RESET%
    echo %YELLOW%  Please install Python 3.11+ manually:%RESET%
    echo %CYAN%  https://www.python.org/downloads/%RESET%
    echo.
    echo %DIM%  After installing Python, re-run this script.%RESET%
    echo.
    pause
    exit /b 1
)

:: Download Python installer to temp
set "PY_INSTALLER=%TEMP%\python_ueos_installer.exe"
echo %DIM%  Downloading to: %PY_INSTALLER%%RESET%

curl -L --progress-bar -o "%PY_INSTALLER%" "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
if %errorlevel% neq 0 (
    echo.
    echo %RED%  ✗ Download failed. Check your internet connection.%RESET%
    echo %YELLOW%  Manual install: https://www.python.org/downloads/%RESET%
    echo.
    pause
    exit /b 1
)

echo.
echo %CYAN%  → Installing Python 3.11.9 silently...%RESET%
echo %DIM%  (This takes ~30 seconds — do not close this window)%RESET%
echo.

"%PY_INSTALLER%" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0 Include_launcher=1
if %errorlevel% neq 0 (
    echo %RED%  ✗ Python installation failed.%RESET%
    echo %YELLOW%  Try running as Administrator, or install manually:%RESET%
    echo %CYAN%  https://www.python.org/downloads/%RESET%
    echo.
    pause
    exit /b 1
)

:: Clean up installer
del "%PY_INSTALLER%" >nul 2>&1

echo %GREEN%  ✓ Python 3.11.9 installed%RESET%
set PYTHON_JUST_INSTALLED=1

:: Re-launch this script in a fresh shell so PATH is refreshed
echo.
echo %CYAN%  → Refreshing environment and continuing setup...%RESET%
echo.
set UEOS_RELAUNCH=1
start "" /wait cmd /c ""%~f0""
exit /b 0

:: ── Verify Python version ────────────────────────────────────────────────────
:check_python_version
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PY_VER=%%v
for /f "tokens=1,2 delims=." %%a in ("%PY_VER%") do (
    set PY_MAJOR=%%a
    set PY_MINOR=%%b
)

if %PY_MAJOR% LSS 3 (
    echo %RED%  ✗ Python %PY_VER% found — need 3.10 or higher%RESET%
    echo %YELLOW%  Please install Python 3.11+: https://www.python.org/downloads/%RESET%
    echo.
    pause
    exit /b 1
)
if %PY_MAJOR% EQU 3 if %PY_MINOR% LSS 10 (
    echo %RED%  ✗ Python %PY_VER% found — need 3.10 or higher%RESET%
    echo %YELLOW%  Please install Python 3.11+: https://www.python.org/downloads/%RESET%
    echo.
    pause
    exit /b 1
)

echo %GREEN%  ✓ Python %PY_VER%%RESET%
echo.

:: ============================================================
::  STEP 2 — pip dependencies
:: ============================================================
echo %BOLD%[2/5] Installing Python dependencies...%RESET%
echo.

:: Quick check first — if all already installed, skip
python -c "import mcp, aiohttp, dotenv, tkinter" >nul 2>&1
if %errorlevel% equ 0 (
    echo %GREEN%  ✓ All dependencies already installed%RESET%
    echo.
    goto :step3
)

:: Install with visible progress
echo %CYAN%  → Running: pip install -r requirements.txt%RESET%
echo.
python -m pip install --upgrade pip --quiet
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo.
    echo %RED%  ✗ Dependency installation failed%RESET%
    echo %YELLOW%  Try running as Administrator, or run manually:%RESET%
    echo %CYAN%    pip install -r requirements.txt%RESET%
    echo.
    set SETUP_OK=0
    pause
    exit /b 1
)

echo.
echo %GREEN%  ✓ All dependencies installed%RESET%
echo.

:: ============================================================
::  STEP 3 — Claude Desktop config
:: ============================================================
:step3
echo %BOLD%[3/5] Configuring Claude Desktop...%RESET%
echo.

:: Inject the UEOS MCP entry using Python (handles JSON safely)
python setup\inject_claude_config.py
if %errorlevel% equ 0 (
    echo %GREEN%  ✓ Claude Desktop config updated%RESET%
    echo %DIM%    Restart Claude Desktop to activate UEOS%RESET%
) else if %errorlevel% equ 2 (
    echo %GREEN%  ✓ UEOS already in Claude Desktop config%RESET%
) else (
    echo %YELLOW%  ! Claude Desktop not found on this machine%RESET%
    echo %DIM%    Download from: https://claude.ai/download%RESET%
    echo %DIM%    After installing, re-run this script OR use the%RESET%
    echo %DIM%    'Claude Setup' tab in the UEOS launcher.%RESET%
)
echo.

:: ============================================================
::  STEP 4 — Unreal Engine connection check
:: ============================================================
echo %BOLD%[4/5] Checking Unreal Engine connection...%RESET%
echo.

python setup\check_ue.py
if %errorlevel% equ 0 (
    echo %GREEN%  ✓ Unreal Engine 5.4 detected — Remote Control API active%RESET%
) else (
    echo %YELLOW%  ! Unreal Engine not detected (that's OK for now)%RESET%
    echo.
    echo %DIM%  When you're ready to connect UE:%RESET%
    echo %DIM%    1. Open Unreal Engine 5.4%RESET%
    echo %DIM%    2. Edit → Plugins → search "Remote Control API" → Enable → Restart%RESET%
    echo %DIM%    3. Edit → Plugins → search "Python Editor Script Plugin" → Enable → Restart%RESET%
    echo %DIM%    4. That's it — port 30010 opens automatically%RESET%
)
echo.

:: ============================================================
::  STEP 5 — Write setup marker + create .env
:: ============================================================
echo %BOLD%[5/5] Finalising...%RESET%
echo.

:: Copy .env.example → .env if it doesn't exist
if not exist ".env" (
    if exist ".env.example" (
        copy ".env.example" ".env" >nul
        echo %GREEN%  ✓ Created .env from template%RESET%
    )
)

:: Write setup complete marker
echo 1 > .setup_complete
echo %GREEN%  ✓ Setup marker written%RESET%
echo.

:: ── Summary ──────────────────────────────────────────────────────────────────
echo %BOLD%%CYAN%  ╔══════════════════════════════════════════════════╗%RESET%
echo %BOLD%%CYAN%  ║                 Setup Complete!                  ║%RESET%
echo %BOLD%%CYAN%  ╚══════════════════════════════════════════════════╝%RESET%
echo.
echo %BOLD%  What to do now:%RESET%
echo.
echo %GREEN%  1.%RESET% Restart Claude Desktop (if it's open)
echo %GREEN%  2.%RESET% Open Unreal Engine 5.4 with Remote Control plugins enabled
echo %GREEN%  3.%RESET% Double-click %BOLD%UEOS.bat%RESET% to launch the control panel
echo %GREEN%  4.%RESET% In Claude Desktop, ask: %CYAN%"run ueos_status"%RESET%
echo.
echo %DIM%  Optional: add your Tripo API key in the UEOS launcher (API Keys tab)%RESET%
echo %DIM%  for text-to-3D and image-to-3D generation.%RESET%
echo.

if %SETUP_OK% equ 1 (
    echo %GREEN%  All done! Launching UEOS in 3 seconds...%RESET%
    echo.
    timeout /t 3 /nobreak >nul
    start "" pythonw ui\launcher.py
    if %errorlevel% neq 0 start "" python ui\launcher.py
) else (
    echo %YELLOW%  Setup finished with warnings. See above for details.%RESET%
    echo.
    pause
)

endlocal
