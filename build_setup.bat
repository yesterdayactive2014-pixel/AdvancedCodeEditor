@echo off
chcp 65001 >nul
title Vertex Studio — Сборка установщика

echo ═══════════════════════════════════════════
echo   Сборка Vertex Studio + Lynx AI
echo ═══════════════════════════════════════════
echo.

:: 1. Создаём exe через PyInstaller
echo [1/4] Сборка Vela.exe...
call pyinstaller --onefile --windowed --name="Vela" --distpath "dist" --add-data "assets;assets" --add-data "LynxTrain;LynxTrain" --hidden-import PyQt6.QtWebEngineWidgets --hidden-import PyQt6.QtWebChannel --hidden-import PyQt6.QtSerialPort --exclude-module torch --exclude-module torchvision --exclude-module torchaudio vela.py
if %errorlevel% neq 0 (
    echo [ОШИБКА] PyInstaller не смог собрать exe
    pause
    exit /b 1
)
echo.

:: 2. Скачиваем ollama.exe, если нет
echo [2/4] Проверка ollama.exe...
if not exist "ollama\ollama.exe" (
    echo    Скачиваю ollama.exe с GitHub...
    if not exist "ollama" mkdir ollama
    curl -L -o ollama\ollama.exe https://github.com/ollama/ollama/releases/latest/download/ollama-windows-amd64.exe
    if %errorlevel% neq 0 (
        echo [ПРЕДУПРЕЖДЕНИЕ] Не удалось скачать ollama.exe
        echo   Скачайте вручную: https://ollama.com/download/windows
        echo   и положите в папку ollama\ollama.exe
    )
)
echo.

:: 3. Собираем Inno Setup
echo [3/4] Компиляция установщика...
set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if exist %ISCC% (
    %ISCC% setup.iss
    if %errorlevel% neq 0 (
        echo [ОШИБКА] Inno Setup не смог собрать установщик
        pause
        exit /b 1
    )
) else (
    echo [ПРЕДУПРЕЖДЕНИЕ] Inno Setup не найден (%ISCC%)
    echo   Установите Inno Setup 6: https://jrsoftware.org/isdl.php
    echo   Затем откройте setup.iss вручную и нажмите F9
)
echo.

:: 4. Готово
echo ───────────────────────────────────────────
echo   ГОТОВО!
if exist "installer\Vela_Setup_*.exe" (
    for %%f in (installer\Vela_Setup_*.exe) do (
        echo   Установщик: %%f
    )
)
echo ───────────────────────────────────────────
echo.
pause
