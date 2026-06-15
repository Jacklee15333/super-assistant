@echo off
REM =====================================================================
REM  Chaoneng Xiaozhu - Launcher (double-click me)
REM  Calls start.ps1. All output is ASCII to avoid garbled text.
REM  This window will NOT auto-close: on error it pauses so you can read.
REM =====================================================================
chcp 65001 >nul
cd /d "%~dp0"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" %*

echo.
echo Launcher finished. If there was an error above, screenshot it.
pause
