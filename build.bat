@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Build AutoStock Studio Release

echo.
echo ============================================================
echo   BUILD AUTOSTOCK STUDIO - STANDALONE RELEASE
echo ============================================================
echo.

python build_release.py %*
if errorlevel 1 (
    echo.
    echo [ERROR] Build failed. Check the error log above.
    pause
    exit /b 1
)
pause
