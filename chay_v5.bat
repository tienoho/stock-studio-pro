@echo off
title 1Click Stock Studio Pro v5.1
cd /d "%~dp0"

echo ===================================================================
echo   1CLICK STOCK STUDIO PRO v5.1 - Starting...
echo ===================================================================
echo.

python stock_preview_v5.py

if errorlevel 1 (
    echo.
    echo [ERROR] Application stopped or encountered an error.
    pause
)
