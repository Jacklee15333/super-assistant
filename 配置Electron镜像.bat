@echo off
REM 双击这个来运行 Electron 镜像配置（不会闪退）
chcp 65001 >nul
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0配置Electron镜像.ps1"
echo.
echo 配置脚本已执行完毕。如上面有红色错误，请截图发给开发者。
pause
