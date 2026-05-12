@echo off
:: AutoEdit-Lite — All-In-One Windows Installer
:: Double-click this file. It will install Python, FFmpeg, and all
:: Python packages automatically, then set up the Premiere Pro plugin.
::
:: Safe to re-run if something went wrong the first time.

powershell -ExecutionPolicy Bypass -File "%~dp0install_all_windows.ps1" %*
pause
