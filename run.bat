@echo off
title AutoEdit-Lite

echo.
echo ============================================================
echo   AutoEdit-Lite - AI Video Editor
echo ============================================================
echo.
echo   Drag your video file into this window and press Enter,
echo   OR type the full path to your video file below.
echo.

set /p INPUT="  Video path: "

if "%INPUT%"=="" (
    echo.
    echo   [ERROR] No input provided. Please run again and enter a path.
    pause
    exit /b 1
)

echo.
echo   Running with: model=medium, quality=balanced
echo   Press Ctrl+C to cancel at any time.
echo.

python main.py --input "%INPUT%" --model medium --quality balanced

echo.
pause
