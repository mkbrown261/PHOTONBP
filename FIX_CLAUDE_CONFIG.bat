@echo off
setlocal
title Fix Claude Desktop Config
cd /d "%~dp0"

echo.
echo  Fixing Claude Desktop config...
echo.

:: Run the inject script — it uses paths relative to its own location,
:: so it will write the correct Windows paths automatically.
python setup\inject_claude_config.py
set RC=%errorlevel%

if %RC% equ 0 (
    echo.
    echo  [OK] Config written with correct paths.
    echo.
    echo  What to do now:
    echo    1. Fully quit Claude Desktop ^(right-click tray icon → Quit^)
    echo    2. Reopen Claude Desktop
    echo    3. Ask Claude: "run ueos_status"
    echo.
) else if %RC% equ 2 (
    echo.
    echo  [OK] Config is already correct.
    echo.
    echo  If it still isn't working:
    echo    1. Fully quit Claude Desktop ^(right-click tray icon → Quit^)
    echo    2. Reopen Claude Desktop
    echo    3. Ask Claude: "run ueos_status"
    echo.
) else (
    echo.
    echo  [ERROR] Could not find Claude Desktop.
    echo  Make sure Claude Desktop is installed from https://claude.ai/download
    echo  Then run this script again.
    echo.
)

pause
endlocal
