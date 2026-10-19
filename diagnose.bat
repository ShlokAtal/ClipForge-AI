@echo off
setlocal
title ClipForge AI - Environment Diagnostics
cd /d "%~dp0"

echo.
echo ==========================================
echo     ClipForge AI - Diagnostics
echo ==========================================
echo.

echo [1/6] Checking Python...
python --version
python -c "import sys; print('Executable:', sys.executable); print('Expected version:', sys.version_info[:3] == (3,14,7))"
if errorlevel 1 echo ERROR: Python check failed.
echo.

echo [2/6] Checking Streamlit...
python -c "import streamlit; print('Streamlit:', streamlit.__version__)"
if errorlevel 1 echo ERROR: Streamlit is unavailable.
echo.

echo [3/6] Checking faster-whisper...
python -c "import faster_whisper; print('faster-whisper:', faster_whisper.__version__)"
if errorlevel 1 echo ERROR: faster-whisper is unavailable.
echo.

echo [4/6] Checking FFmpeg...
where ffmpeg
if errorlevel 1 echo ERROR: FFmpeg was not found on PATH.
if exist "%SystemRoot%\System32\where.exe" ffmpeg -version 2>nul | findstr /B /C:"ffmpeg version"
echo.

echo [5/6] Checking yt-dlp...
where yt-dlp
if errorlevel 1 echo ERROR: yt-dlp was not found on PATH.
yt-dlp --version
if errorlevel 1 echo ERROR: yt-dlp could not run.
echo.

echo [6/6] Checking config.json...
python -c "import json; c=json.load(open('config.json', encoding='utf-8')); print('Configuration JSON: Valid'); print('App:', c['app_name'])"
if errorlevel 1 echo ERROR: config.json could not be validated.
echo.

echo ==========================================
echo Diagnostics finished.
echo Review any ERROR messages above.
echo ==========================================
echo.
pause