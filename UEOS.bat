@echo off
title UEOS Launcher
cd /d "%~dp0"

:: Check Python is available
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found in PATH.
    echo Please install Python 3.11+ from https://python.org and re-run.
    pause
    exit /b 1
)

:: Check dependencies installed (fast check)
python -c "import tkinter, aiohttp, dotenv" >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing UEOS dependencies ...
    python -m pip install -r requirements.txt --quiet
    if %errorlevel% neq 0 (
        echo ERROR: Dependency installation failed.
        echo Run manually: pip install -r requirements.txt
        pause
        exit /b 1
    )
)

:: Launch the GUI (pythonw hides the console window on Windows)
start "" pythonw ui\launcher.py

:: If pythonw isn't available, fall back to python (shows console briefly)
if %errorlevel% neq 0 (
    python ui\launcher.py
)
