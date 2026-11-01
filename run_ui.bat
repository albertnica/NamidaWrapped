@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul

:: ============================================================================
:: 2026 Wrapped - Interactive Web Studio Launcher
:: Automates execution of main.py with the --ui flag from any working directory.
:: Checks prerequisites and automatically routes to setup.bat if dependencies
:: are missing or incomplete.
:: ============================================================================

:: 1. Force working directory to the repository root where this script resides.
cd /d "%~dp0"

:: 2. Resolve Python runtime (.venv -> venv -> system PATH python -> py launcher)
set "PYTHON_EXE="

if exist "%~dp0.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
) else if exist "%~dp0venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0venv\Scripts\python.exe"
) else (
    where python >nul 2>nul
    if !errorlevel! equ 0 (
        set "PYTHON_EXE=python"
    ) else (
        where py >nul 2>nul
        if !errorlevel! equ 0 (
            set "PYTHON_EXE=py -3"
        )
    )
)

if not defined PYTHON_EXE (
    echo [ERROR] No suitable Python interpreter found in .venv, venv, or PATH.
    echo Please install Python 3.10+ or run setup.bat.
    echo.
    pause
    exit /b 1
)

:: 3. Verify core dependencies exist before launching; otherwise launch setup wizard
!PYTHON_EXE! -c "import fastapi, uvicorn, pydantic, mutagen, PIL" >nul 2>nul
if !errorlevel! neq 0 (
    echo [SETUP] Missing Python dependencies detected. Launching interactive setup wizard...
    call "%~dp0setup.bat"
    exit /b 0
)

:: 4. Launch Web Studio with --ui flag and forward any additional CLI arguments
echo ========================================================
echo  NamidaWrapped - Launching Web Studio
echo ========================================================
echo  Directory: %CD%
echo  Python:    !PYTHON_EXE!
echo ========================================================
echo.

!PYTHON_EXE! "%~dp0main.py" --ui %*

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Web Studio exited with error code %errorlevel%.
    pause
    exit /b %errorlevel%
)

endlocal
