@echo off
setlocal enabledelayedexpansion

echo.
echo ========================================
echo   Pixel Pet: Python Detection Helper
echo ========================================
echo.

:: Try 'python'
python --version >nul 2>&1
if %errorlevel% equ 0 (
    set PY_CMD=python
    goto found
)

:: Try 'py'
py --version >nul 2>&1
if %errorlevel% equ 0 (
    set PY_CMD=py
    goto found
)

:: Try 'python3'
python3 --version >nul 2>&1
if %errorlevel% equ 0 (
    set PY_CMD=python3
    goto found
)

:: Try the specific path seen in logs
set "ALT_PATH=%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe"
if exist "!ALT_PATH!" (
    set "PY_CMD="!ALT_PATH!""
    goto found
)

echo [ERROR] Could not find Python! 
echo Please make sure Python is installed and added to your 'Path'.
echo Currently searching for: python, py, python3
pause
exit /b

:found
echo [SUCCESS] Found Python using command: !PY_CMD!
echo Starting Pixel...
echo.
!PY_CMD! main.py
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] The app crashed or failed to start.
    pause
)
pause
