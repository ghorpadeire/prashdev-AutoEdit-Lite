@echo off
title AutoEdit-Lite Setup
color 0A

echo.
echo ============================================================
echo   AutoEdit-Lite - First Time Setup (Windows)
echo ============================================================
echo   This script will automatically install everything you need.
echo   It only needs to run ONCE.
echo ============================================================
echo.
pause

:: Force CPU-only mode for this session so verification step works
:: on machines without CUDA 12 installed
set CUDA_VISIBLE_DEVICES=-1

:: ── STEP 1: Check Python ─────────────────────────────────────────────────
echo.
echo [1/6] Checking Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo   [ERROR] Python is not installed or not found on PATH.
    echo.
    echo   Please do this:
    echo     1. Open your browser and go to: https://www.python.org/downloads/
    echo     2. Download Python 3.10 or newer
    echo     3. Run the installer
    echo     4. IMPORTANT: Tick the box that says "Add Python to PATH"
    echo     5. After installing, close this window and double-click setup_windows.bat again
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version 2^>^&1') do set PYVER=%%i
echo   OK - Found: %PYVER%

:: ── STEP 2: Install FFmpeg via winget ────────────────────────────────────
echo.
echo [2/6] Checking FFmpeg...
ffmpeg -version >nul 2>&1
if %errorlevel% equ 0 (
    echo   OK - FFmpeg is already installed.
    goto :ffmpeg_done
)

echo   FFmpeg not found. Attempting to install via Windows Package Manager...
echo.
winget --version >nul 2>&1
if %errorlevel% neq 0 (
    echo   [NOTE] Windows Package Manager (winget) is not available on this PC.
    echo          This usually means you are on an older version of Windows.
    echo.
    echo   Please install FFmpeg manually:
    echo     1. Go to: https://github.com/BtbN/FFmpeg-Builds/releases
    echo     2. Download: ffmpeg-master-latest-win64-gpl.zip
    echo     3. Unzip it and find the 'bin' folder inside
    echo     4. Copy the path to that 'bin' folder
    echo     5. Search Windows for "Environment Variables"
    echo     6. Edit the PATH variable and add the 'bin' folder path
    echo     7. Restart this setup script
    echo.
    pause
    exit /b 1
)

echo   Installing FFmpeg via winget (this may take a few minutes)...
winget install --id Gyan.FFmpeg --accept-source-agreements --accept-package-agreements
if %errorlevel% neq 0 (
    echo.
    echo   [WARNING] Automatic FFmpeg install may have had an issue.
    echo   Checking if it worked anyway...
)

:: Refresh PATH in current session so ffmpeg is found immediately
for /f "tokens=2*" %%a in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v PATH 2^>nul') do set SYSPATH=%%b
for /f "tokens=2*" %%a in ('reg query "HKCU\Environment" /v PATH 2^>nul') do set USRPATH=%%b
set PATH=%SYSPATH%;%USRPATH%;%PATH%

ffmpeg -version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo   [ACTION REQUIRED] FFmpeg was installed but needs a restart to be recognised.
    echo.
    echo   Please:
    echo     1. Close this window
    echo     2. Restart your computer  (or just close and reopen Command Prompt)
    echo     3. Double-click setup_windows.bat again to continue
    echo.
    pause
    exit /b 1
)
echo   OK - FFmpeg installed successfully.

:ffmpeg_done

:: ── STEP 3: Install Python packages ──────────────────────────────────────
echo.
echo [3/6] Installing Python packages...
echo   (This downloads faster-whisper, anthropic, ffmpeg-python, dotenv)
echo   Please wait...
echo.
python -m pip install --upgrade pip --quiet
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo.
    echo   [ERROR] Package installation failed.
    echo   Make sure you have an internet connection and try again.
    pause
    exit /b 1
)
echo.
echo   OK - All packages installed.

:: ── STEP 4: Fix CUDA compatibility ───────────────────────────────────────
echo.
echo [4/6] Checking GPU/CUDA compatibility...
python -c "import os; os.environ['CUDA_VISIBLE_DEVICES']=''; from faster_whisper import WhisperModel" >nul 2>&1
if %errorlevel% neq 0 (
    echo   Detected a CUDA compatibility issue (cublas64_12.dll or similar).
    echo   Installing CPU-compatible ctranslate2 build...
    echo.
    python -m pip install "ctranslate2>=3.20.0,<4.0.0" --force-reinstall --quiet
    if %errorlevel% neq 0 (
        echo.
        echo   [ERROR] Could not fix the CUDA issue automatically.
        echo   Please run this manually and try again:
        echo     pip install "ctranslate2>=3.20.0,<4.0.0" --force-reinstall
        pause
        exit /b 1
    )
    echo   OK - ctranslate2 fixed. No CUDA required.
) else (
    echo   OK - faster-whisper loads correctly on this machine.
)

:: ── STEP 5: Set up API key ────────────────────────────────────────────────
echo.
echo [5/6] Setting up your Anthropic API key...
echo.

if exist .env (
    echo   Found existing .env file. Skipping creation.
    goto :env_done
)

copy .env.example .env >nul
echo   Created your .env file from the template.
echo.
echo   ============================================================
echo   IMPORTANT: You need to add your Anthropic API key now.
echo   ============================================================
echo.
echo   1. A Notepad window is about to open with your .env file
echo   2. Replace  your_key_here  with your real API key
echo   3. Get your key at: https://console.anthropic.com/
echo   4. Save the file (Ctrl+S) and close Notepad
echo   5. Come back to this window and press any key to continue
echo.
pause
notepad .env
echo.
echo   If you have added your key, press any key to continue.
echo   If you skipped it, you can edit .env manually later.
pause

:env_done

:: ── STEP 6: Verify full setup ──────────────────────────────────────────────────
echo.
echo [6/6] Verifying setup...
python -c "import os; os.environ['CUDA_VISIBLE_DEVICES']=''; import faster_whisper, anthropic, ffmpeg, dotenv; print('   All packages OK')"
if %errorlevel% neq 0 (
    echo.
    echo   [ERROR] Some packages did not install correctly.
    echo   Try running setup again or run:  pip install -r requirements.txt
    pause
    exit /b 1
)

:: ── Done ──────────────────────────────────────────────────────────────────
echo.
echo ============================================================
echo   SETUP COMPLETE!
echo ============================================================
echo.
echo   You are ready to use AutoEdit-Lite.
echo.
echo   HOW TO USE:
echo     - Double-click  run_windows.bat  to edit a video
echo     - OR run:  python main.py --input input\video.mp4
echo.
echo   FIRST TIME TIP:
echo     Test with a short video (under 2 minutes) first.
echo     Drop it in the  input\  folder, then run the tool.
echo.
echo ============================================================
echo.
pause
