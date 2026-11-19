@echo off
setlocal
title ClipForge AI - Setup

cd /d "%~dp0"

echo.
echo ==========================================
echo          ClipForge AI - Setup
echo ==========================================
echo.

echo [1/5] Checking Python 3.14.7...
python -c "import sys; print('Python:', sys.version.split()[0]); sys.exit(0 if sys.version_info[:3] == (3,14,7) else 1)"
if errorlevel 1 (
    echo ERROR: Python 3.14.7 was not detected.
    echo Install or select Python 3.14.7 before continuing.
    pause
    exit /b 1
)
echo.

echo [2/5] Checking required Python packages...
python -c "import streamlit, faster_whisper, cv2; print('Streamlit:', streamlit.__version__); print('faster-whisper:', faster_whisper.__version__); print('OpenCV:', cv2.__version__)"
if errorlevel 1 (
    echo ERROR: A required Python package is unavailable.
    echo Install project dependencies with: python -m pip install -r requirements.txt
    echo Then rerun setup.bat.
    pause
    exit /b 1
)
echo.

echo [3/5] Checking FFmpeg...
where ffmpeg
if errorlevel 1 (
    echo ERROR: FFmpeg was not found on PATH.
    pause
    exit /b 1
)
echo.

echo [4/5] Checking yt-dlp...
where yt-dlp
if errorlevel 1 (
    echo ERROR: yt-dlp was not found on PATH.
    pause
    exit /b 1
)
echo.

echo [5/5] Checking project files...
if not exist "app.py" (
    echo ERROR: app.py is missing.
    pause
    exit /b 1
)
if not exist "config.json" (
    echo ERROR: config.json is missing.
    pause
    exit /b 1
)

python -c "import json; c=json.load(open('config.json', encoding='utf-8')); print('Configuration:', c['app_name'])"
if errorlevel 1 (
    echo ERROR: config.json could not be read.
    pause
    exit /b 1
)

echo.
echo ==========================================
echo Setup checks passed!
echo You can now launch run.bat.
echo ==========================================
echo.
pause