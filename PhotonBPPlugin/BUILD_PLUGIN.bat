@echo off
echo ============================================
echo  PhotonBP Plugin Builder for UE 5.4.4
echo ============================================
echo.

:: ── Find Unreal Engine 5.4 ───────────────────────────────────────────────────
set UE_ROOT=
for %%d in (
    "C:\Program Files\Epic Games\UE_5.4"
    "C:\Program Files (x86)\Epic Games\UE_5.4"
    "D:\Program Files\Epic Games\UE_5.4"
    "D:\Epic Games\UE_5.4"
    "C:\UE_5.4"
) do (
    if exist %%d\Engine\Binaries\DotNET\UnrealBuildTool\UnrealBuildTool.exe (
        set UE_ROOT=%%~d
        goto :found_ue
    )
)

echo ERROR: Could not find UE 5.4.4 installation.
echo Please edit this .bat file and set UE_ROOT manually.
echo Example: set UE_ROOT=C:\Program Files\Epic Games\UE_5.4
pause
exit /b 1

:found_ue
echo Found UE at: %UE_ROOT%
echo.

:: ── Find the UE Project ──────────────────────────────────────────────────────
set PROJECT_FILE=
for %%f in (
    "%USERPROFILE%\OneDrive\Documents\Unreal Projects\photonbptestproject\photonbptestproject.uproject"
    "%USERPROFILE%\Documents\Unreal Projects\photonbptestproject\photonbptestproject.uproject"
    "C:\Users\AVIAT\OneDrive\Documents\Unreal Projects\photonbptestproject\photonbptestproject.uproject"
) do (
    if exist %%f (
        set PROJECT_FILE=%%~f
        goto :found_project
    )
)

echo ERROR: Could not find photonbptestproject.uproject
echo Please edit this .bat and set PROJECT_FILE manually.
pause
exit /b 1

:found_project
echo Found project at: %PROJECT_FILE%
echo.

:: ── Copy plugin into project ──────────────────────────────────────────────────
set PLUGIN_SRC=%~dp0PhotonBP
set PROJECT_DIR=%PROJECT_FILE%\..
for %%i in ("%PROJECT_FILE%") do set PROJECT_DIR=%%~dpi

set PLUGIN_DEST=%PROJECT_DIR%Plugins\PhotonBP

echo Copying plugin source to: %PLUGIN_DEST%
if not exist "%PLUGIN_DEST%" mkdir "%PLUGIN_DEST%"
xcopy /E /Y /I "%PLUGIN_SRC%" "%PLUGIN_DEST%" >nul
echo Done.
echo.

:: ── Build ────────────────────────────────────────────────────────────────────
set UBT="%UE_ROOT%\Engine\Binaries\DotNET\UnrealBuildTool\UnrealBuildTool.exe"

echo Building PhotonBP plugin...
echo This takes 1-3 minutes. Do not close this window.
echo.

%UBT% -projectfiles -project="%PROJECT_FILE%" -game -rocket -progress

%UBT% PhotonBPEditor Win64 Development -Project="%PROJECT_FILE%" -Plugin="%PLUGIN_DEST%\PhotonBP.uplugin" -Package="%~dp0Output\PhotonBP" -Rocket -TargetType=Editor

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ============================================
    echo  BUILD FAILED. See errors above.
    echo ============================================
    pause
    exit /b 1
)

echo.
echo ============================================
echo  BUILD SUCCESS
echo ============================================
echo.
echo Your compiled plugin is in:
echo   %~dp0Output\PhotonBP
echo.
echo To install:
echo   Copy the "PhotonBP" folder from Output\ into your project's Plugins\ folder
echo   Then restart Unreal Engine.
echo.
pause
