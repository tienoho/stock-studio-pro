@echo off
chcp 65001 >nul
setlocal
title Build Stock Preview v5 Release
cd /d "%~dp0"

echo.
echo ============================================================
echo   BUILD STOCK PREVIEW v5 - PORTABLE RELEASE
echo ============================================================
echo.

if not exist "stock_preview_v5.py" (
    echo [ERROR] Cannot find stock_preview_v5.py
    pause
    exit /b 1
)

echo [1/6] Checking Python...
python --version
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.10+ and tick Add to PATH.
    pause
    exit /b 1
)

echo.
echo [2/6] Installing build dependencies...
python -m pip install --upgrade pip
python -m pip install --upgrade -r requirements.txt
if errorlevel 1 (
    echo [ERROR] pip install failed
    pause
    exit /b 1
)

echo.
echo [3/6] Testing imports...
python -c "from PyQt6.QtWidgets import QApplication; from PyQt6.QtMultimedia import QMediaPlayer; from PyQt6.QtMultimediaWidgets import QVideoWidget; import PIL, requests; print('imports ok')"
if errorlevel 1 (
    echo [ERROR] Import test failed
    pause
    exit /b 1
)

echo.
echo [4/6] Cleaning old build...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "release_v5" rmdir /s /q "release_v5"
if exist "StockPreview_v5.spec" del /q "StockPreview_v5.spec"

echo.
echo [5/6] Building app folder. This can take 5-15 minutes...
python -m PyInstaller ^
    --onedir ^
    --windowed ^
    --name "StockPreview_v5" ^
    --collect-all PyQt6 ^
    --collect-data PyQt6 ^
    --hidden-import PyQt6.QtMultimedia ^
    --hidden-import PyQt6.QtMultimediaWidgets ^
    --hidden-import PyQt6.QtCore ^
    --hidden-import PyQt6.QtGui ^
    --hidden-import PyQt6.QtWidgets ^
    --noconfirm ^
    "stock_preview_v5.py"
if errorlevel 1 (
    echo [ERROR] PyInstaller failed
    pause
    exit /b 1
)

if not exist "dist\StockPreview_v5\StockPreview_v5.exe" (
    echo [ERROR] EXE not found after build
    pause
    exit /b 1
)

echo.
echo [6/6] Packaging release...
mkdir "release_v5"
xcopy "dist\StockPreview_v5" "release_v5\StockPreview_v5" /E /I /Y >nul
copy "RUN_STOCK_PREVIEW_v5.bat" "release_v5\" >nul
copy "README_RELEASE_v5.txt" "release_v5\README.txt" >nul

echo.
echo ============================================================
echo   BUILD DONE
echo ============================================================
echo Output folder:
echo   %CD%\release_v5
echo.
echo Copy the whole release_v5 folder to another Windows machine.
echo Start by double-clicking RUN_STOCK_PREVIEW_v5.bat
echo.
start "" "%CD%\release_v5"
pause
