@echo off
chcp 65001 >nul
cd /d "%~dp0"
title AutoStock Studio Launcher

if exist "AutoStockStudio\AutoStockStudio.exe" (
    start "" "%~dp0AutoStockStudio\AutoStockStudio.exe"
    exit /b 0
)

if exist "AutoStockStudio.exe" (
    start "" "%~dp0AutoStockStudio.exe"
    exit /b 0
)

echo [ERROR] Cannot find AutoStockStudio.exe
echo Please make sure this file is placed alongside AutoStockStudio.exe or in the release directory.
pause
