@echo off
chcp 65001 >nul
cd /d "%~dp0"
title AutoStock Studio

echo.
echo ============================================================
echo   AUTOSTOCK STUDIO - Starting...
echo ============================================================
echo.

python main.py
if errorlevel 1 (
    echo.
    echo [ERROR] Application exited with an error.
    pause
)
