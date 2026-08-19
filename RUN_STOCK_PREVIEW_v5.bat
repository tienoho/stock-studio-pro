@echo off
chcp 65001 >nul
cd /d "%~dp0"

if exist "StockPreview_v5\StockPreview_v5.exe" (
    start "" "%~dp0StockPreview_v5\StockPreview_v5.exe"
    exit /b 0
)

if exist "StockPreview_v5.exe" (
    start "" "%~dp0StockPreview_v5.exe"
    exit /b 0
)

echo [ERROR] Cannot find StockPreview_v5.exe
echo Make sure this BAT file is inside the release_v5 folder.
pause
