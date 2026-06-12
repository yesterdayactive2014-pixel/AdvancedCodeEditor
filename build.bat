@echo off
chcp 65001 > nul
cls

echo.
echo ╔═══════════════════════════════════════════════════════════════╗
echo ║         Advanced Code Editor - Автоматическая упаковка        ║
echo ╚═══════════════════════════════════════════════════════════════╝
echo.

REM Проверка Python
python --version > nul 2>&1
if errorlevel 1 (
    echo ❌ ОШИБКА: Python не найден!
    echo    Установите Python 3.8+ с сайта https://www.python.org/
    echo    и убедитесь, что отметили "Add Python to PATH"
    pause
    exit /b 1
)

echo ✅ Python найден

REM Установка зависимостей
echo.
echo 🔧 Установка зависимостей...
echo.

pip install --upgrade pip > nul 2>&1
pip install PyQt6==6.6.1 > nul 2>&1
pip install Pygments==2.16.1 > nul 2>&1
pip install pyinstaller > nul 2>&1

echo ✅ Зависимости установлены

REM Проверка существования файла
if not exist "code_editor.py" (
    echo.
    echo ❌ ОШИБКА: Файл code_editor.py не найден!
    echo    Убедитесь, что все файлы в одной директории
    pause
    exit /b 1
)

REM Очистка старых файлов
echo.
echo 🧹 Очистка старых файлов...
if exist "build" rmdir /s /q build > nul 2>&1
if exist "dist" rmdir /s /q dist > nul 2>&1
if exist "code_editor.spec" del code_editor.spec > nul 2>&1

echo ✅ Старые файлы удалены

REM Создание exe
echo.
echo 📦 Создание exe файла (это может занять 2-5 минут)...
echo.

pyinstaller --onefile --windowed --name="CodeEditor" ^
    --distpath "dist" code_editor.py

REM Проверка результата
if exist "dist\CodeEditor.exe" (
    echo.
    echo ╔═══════════════════════════════════════════════════════════════╗
    echo ║                   ✅ УСПЕШНО СОЗДАНО!                        ║
    echo ╚═══════════════════════════════════════════════════════════════╝
    echo.
    echo 📁 Файл находится здесь:
    echo    %cd%\dist\CodeEditor.exe
    echo.
    echo 🚀 Запустить прямо сейчас? (y/n)
    set /p run="Выбор: "
    if /i "%run%"=="y" (
        start "" "dist\CodeEditor.exe"
    )
    echo.
    echo 📦 Создать zip архив? (y/n)
    set /p zipfile="Выбор: "
    if /i "%zipfile%"=="y" (
        if exist "CodeEditor.zip" del CodeEditor.zip
        cd dist
        powershell -Command "Compress-Archive -Path CodeEditor.exe -DestinationPath ..\CodeEditor.zip"
        cd ..
        echo ✅ Архив создан: CodeEditor.zip
    )
) else (
    echo.
    echo ❌ ОШИБКА при создании exe!
    echo    Проверьте консоль выше для детальной информации об ошибке
    pause
    exit /b 1
)

echo.
pause
