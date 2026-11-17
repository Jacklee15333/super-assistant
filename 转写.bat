@echo off
chcp 65001 >nul
cd /d "%~dp0backend"
set "PYTHONUTF8=1"
set "LINK=%~1"
if not defined LINK set /p LINK=粘贴抖音分享链接后回车:
python cli_transcribe.py "%LINK%" --open
pause
