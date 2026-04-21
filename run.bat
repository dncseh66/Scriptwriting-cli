@echo off
setlocal

cd /d "%~dp0"

echo === Scriptwriter Batch CLI ===
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python is not installed or not on PATH.
    echo.
    echo Install Python 3.10+ from https://www.python.org/downloads/
    echo IMPORTANT: on the first installer screen, tick "Add Python to PATH".
    echo Then re-run this file.
    echo.
    pause
    exit /b 1
)

if not exist ".venv\" (
    echo First-time setup: creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo ERROR: failed to create virtual environment.
        pause
        exit /b 1
    )
    echo Installing dependencies...
    call ".venv\Scripts\activate.bat"
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    if errorlevel 1 (
        echo ERROR: failed to install dependencies.
        pause
        exit /b 1
    )
) else (
    call ".venv\Scripts\activate.bat"
)

if not exist "config.json" (
    echo.
    echo config.json not found — creating from template.
    copy /Y "config.example.json" "config.json" >nul
    echo.
    echo =====================================================
    echo  ACTION REQUIRED
    echo  Open config.json and paste your Anthropic API key
    echo  in place of "sk-ant-REPLACE-WITH-YOUR-KEY", then
    echo  re-run this file.
    echo =====================================================
    echo.
    notepad "config.json"
    pause
    exit /b 0
)

python generate.py

echo.
pause
