@echo off
setlocal enabledelayedexpansion

echo.
echo ========================================
echo   Pixel Pet: Multi-Method Installer
echo ========================================
echo.

:: Detect Python
set PY_CMD=
python --version >nul 2>&1 && set PY_CMD=python
if not defined PY_CMD (
    py --version >nul 2>&1 && set PY_CMD=py
)
if not defined PY_CMD (
    set "ALT_PATH=%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe"
    if exist "!ALT_PATH!" set "PY_CMD="!ALT_PATH!""
)

if not defined PY_CMD (
    echo [ERROR] Python not found. Please install Python 3.10+
    pause
    exit /b
)

echo [INFO] Using: !PY_CMD!
echo [INFO] Installing dependencies...

!PY_CMD! -m pip install pyautogui speechrecognition pyttsx3 requests pywin32 pillow pyaudio

echo.
echo ========================================
echo   Installation complete!
echo   Run start.bat to meet Pixel.
echo ========================================
pause
