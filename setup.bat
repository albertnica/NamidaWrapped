@echo off
setlocal
chcp 65001 >nul
title NamidaWrapped Studio - Setup Wizard

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

set "PYTHON_EXE="

if exist "%SCRIPT_DIR%.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%SCRIPT_DIR%.venv\Scripts\python.exe"
) else if exist "%SCRIPT_DIR%venv\Scripts\python.exe" (
    set "PYTHON_EXE=%SCRIPT_DIR%venv\Scripts\python.exe"
) else (
    where python >nul 2>nul
    if not errorlevel 1 (
        set "PYTHON_EXE=python"
    ) else (
        where py >nul 2>nul
        if not errorlevel 1 (
            set "PYTHON_EXE=py -3"
        )
    )
)

if "%PYTHON_EXE%"=="" (
    echo [ERROR] Python is not installed or not in your system PATH.
    echo Please install Python 3.10+ from https://www.python.org/downloads/
    echo Make sure to check the box "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

"%PYTHON_EXE%" "%SCRIPT_DIR%setup_wizard.py"

if errorlevel 1 (
    echo.
    echo [ERROR] Setup wizard exited with errors.
    pause
    exit /b %errorlevel%
)

set "LAUNCH_NOW="
set /p LAUNCH_NOW="Launch NamidaWrapped Studio Web Dashboard now? [Y/n]: "
if not defined LAUNCH_NOW goto launch
if /i "%LAUNCH_NOW%"=="y" goto launch
if /i "%LAUNCH_NOW%"=="yes" goto launch
exit /b 0

:launch
cd /d "%SCRIPT_DIR%"
call "%SCRIPT_DIR%run_ui.bat"
