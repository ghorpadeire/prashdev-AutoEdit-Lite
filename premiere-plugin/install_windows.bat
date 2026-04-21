@echo off
setlocal EnableExtensions DisableDelayedExpansion

echo.
echo ================================================================
echo   AutoEdit for Premiere Pro - Windows Installer
echo ================================================================
echo.

:: Determine the folder this .bat file lives in
set "INSTALLER_DIR=%~dp0"
:: Remove trailing backslash
if "%INSTALLER_DIR:~-1%"=="\" set "INSTALLER_DIR=%INSTALLER_DIR:~0,-1%"

set "EXTENSION_SRC=%INSTALLER_DIR%\com.autoedit.premiere"
set "BACKEND_PATH=%INSTALLER_DIR%\.."

:: Resolve to absolute path
pushd "%BACKEND_PATH%"
set "BACKEND_PATH=%CD%"
popd

set "CEP_DIR=%COMMONPROGRAMFILES(X86)%\Adobe\CEP\extensions"
set "EXTENSION_DST=%CEP_DIR%\com.autoedit.premiere"
set "SETTINGS_DIR=%APPDATA%\AutoEdit"

:: ── Step 1: Enable CEP debug mode ─────────────────────────────────────────
echo [1/4] Enabling CEP debug mode...
for %%v in (9 10 11 12) do (
  reg add "HKCU\Software\Adobe\CSXS.%%v" /v PlayerDebugMode /t REG_SZ /d 1 /f >nul 2>&1
)
echo       Done.

:: ── Step 2: Install extension ─────────────────────────────────────────────
echo [2/4] Installing extension...
if not exist "%CEP_DIR%" mkdir "%CEP_DIR%"
if exist "%EXTENSION_DST%" rd /s /q "%EXTENSION_DST%"
xcopy /e /i /q "%EXTENSION_SRC%" "%EXTENSION_DST%" >nul
if %errorlevel% neq 0 (
  echo.
  echo ERROR: Could not copy files to:
  echo   %EXTENSION_DST%
  echo.
  echo Please right-click install_windows.bat and choose "Run as administrator".
  echo.
  pause
  exit /b 1
)
echo       Installed to: %EXTENSION_DST%

:: ── Step 3: Save backend path ─────────────────────────────────────────────
echo [3/4] Saving backend path...
if not exist "%SETTINGS_DIR%" mkdir "%SETTINGS_DIR%"
(
  echo {
  echo   "backendPath": "%BACKEND_PATH:\=\\%",
  echo   "pythonPath": ""
  echo }
) > "%SETTINGS_DIR%\settings.json"
echo       Saved to: %SETTINGS_DIR%\settings.json

:: ── Step 4: Detect Python ─────────────────────────────────────────────────
echo [4/4] Checking Python...
set "PYTHON_BIN="
for %%p in (
  "C:\Program Files\Python312\python.exe"
  "C:\Program Files\Python311\python.exe"
  "C:\Program Files\Python310\python.exe"
) do (
  if exist %%p (
    set "PYTHON_BIN=%%~p"
    goto :found_python
  )
)

:: Fallback: try py launcher
py -3.12 --version >nul 2>&1
if %errorlevel%==0 (
  for /f "tokens=*" %%i in ('py -3.12 -c "import sys; print(sys.executable)"') do set "PYTHON_BIN=%%i"
  goto :found_python
)

echo       WARNING: Python 3.12 not found.
echo       Install from: https://www.python.org/downloads/release/python-31210/
echo       Tick "Add python.exe to PATH" during install.
goto :after_python

:found_python
echo       Found: %PYTHON_BIN%
:: Update settings with detected python path
(
  echo {
  echo   "backendPath": "%BACKEND_PATH:\=\\%",
  echo   "pythonPath": "%PYTHON_BIN:\=\\%"
  echo }
) > "%SETTINGS_DIR%\settings.json"

:after_python

echo.
echo ================================================================
echo   INSTALLATION COMPLETE
echo ================================================================
echo.
echo Next steps:
echo   1. Install Python dependencies (run once in Command Prompt):
echo      cd "%BACKEND_PATH%"
echo      pip install -r requirements.txt
echo.
echo   2. Copy .env.example to .env and add your ANTHROPIC_API_KEY
echo.
echo   3. Close Premiere Pro if it is open, then relaunch it.
echo.
echo   4. In Premiere Pro: Window ^> Extensions ^> AutoEdit
echo.
pause
