@echo off
:: AutoEdit-Lite Windows Installer
:: Double-click this file to install the Premiere Pro plugin and Python backend.
:: Run with --uninstall to remove it.

powershell -ExecutionPolicy Bypass -File "%~dp0install_windows.ps1" %*
pause
