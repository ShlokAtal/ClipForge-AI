@echo off
setlocal
title ClipForge AI

cd /d "%~dp0"

echo.
echo ==========================================
echo          Starting ClipForge AI
echo ==========================================
echo.

if not exist "app.py" (
    echo ERROR: app.py was not found.
    pause
    exit /b 1
)

if not exist "config.json" (
    echo ERROR: config.json was not found.
    pause
    exit /b 1
)

echo Checking Streamlit...
python -m streamlit --version
if errorlevel 1 (
    echo.
    echo ERROR: Streamlit is unavailable in this Python environment.
    echo Run diagnose.bat to inspect your installation.
    pause
    exit /b 1
)

echo.
echo Launching ClipForge AI...
echo Your browser should open automatically.
echo Keep this window open while using the app.
echo.

python -m streamlit run app.py

echo.
echo ClipForge AI has stopped.
pause