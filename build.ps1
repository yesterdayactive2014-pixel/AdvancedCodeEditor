# Advanced Code Editor - PowerShell Builder
# Скрипт для создания exe приложения

param(
    [switch]$SkipZip = $false
)

Write-Host "`n"
Write-Host "╔═══════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║    Advanced Code Editor - Создание exe приложения             ║" -ForegroundColor Cyan
Write-Host "╚═══════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host "`n"

# Проверка Python
Write-Host "🔍 Проверка Python..." -ForegroundColor Yellow
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ ОШИБКА: Python не найден!" -ForegroundColor Red
    Write-Host "   Установите Python 3.8+ с https://www.python.org/" -ForegroundColor Red
    Write-Host "   И убедитесь, что отметили 'Add Python to PATH'" -ForegroundColor Red
    exit 1
}
Write-Host "✅ $pythonVersion найден" -ForegroundColor Green
Write-Host ""

# Установка зависимостей
Write-Host "🔧 Установка зависимостей..." -ForegroundColor Yellow
pip install --upgrade pip -q
pip install PyQt6==6.6.1 -q
pip install Pygments==2.16.1 -q
pip install pyinstaller -q
Write-Host "✅ Зависимости установлены" -ForegroundColor Green
Write-Host ""

# Проверка файла
if (-not (Test-Path "code_editor.py")) {
    Write-Host "❌ ОШИБКА: Файл code_editor.py не найден!" -ForegroundColor Red
    Write-Host "   Убедитесь, что все файлы в одной директории" -ForegroundColor Red
    exit 1
}

# Очистка старых файлов
Write-Host "🧹 Очистка старых файлов..." -ForegroundColor Yellow
if (Test-Path "build") { Remove-Item -Recurse -Force "build" -ErrorAction SilentlyContinue }
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" -ErrorAction SilentlyContinue }
if (Test-Path "code_editor.spec") { Remove-Item "code_editor.spec" -ErrorAction SilentlyContinue }
Write-Host "✅ Старые файлы удалены" -ForegroundColor Green
Write-Host ""

# Создание exe
Write-Host "📦 Создание exe файла (это может занять 2-5 минут)..." -ForegroundColor Yellow
Write-Host "   (Это нормально, если видите несколько сообщений ниже)" -ForegroundColor Gray
Write-Host ""

pyinstaller `
    --onefile `
    --windowed `
    --name="CodeEditor" `
    --distpath "dist" `
    code_editor.py 2>&1 | Where-Object { $_ -match "INFO|warning|Creating|Compiling" }

Write-Host ""

# Проверка результата
if (Test-Path "dist\CodeEditor.exe") {
    Write-Host "╔═══════════════════════════════════════════════════════════════╗" -ForegroundColor Green
    Write-Host "║                  ✅ УСПЕШНО СОЗДАНО!                         ║" -ForegroundColor Green
    Write-Host "╚═══════════════════════════════════════════════════════════════╝" -ForegroundColor Green
    Write-Host ""
    Write-Host "📁 Файл находится здесь:" -ForegroundColor Cyan
    Write-Host "   $(Get-Location)\dist\CodeEditor.exe" -ForegroundColor White
    Write-Host ""
    
    $exeSize = (Get-Item "dist\CodeEditor.exe").Length / 1MB
    Write-Host "📊 Размер файла: $([Math]::Round($exeSize, 1)) MB" -ForegroundColor Gray
    Write-Host ""
    
    # Запуск приложения
    $response = Read-Host "🚀 Запустить приложение? (y/n)"
    if ($response -eq "y") {
        Start-Process "dist\CodeEditor.exe"
        Write-Host "✅ Приложение запущено!" -ForegroundColor Green
    }
    Write-Host ""
    
    # Создание архива
    if (-not $SkipZip) {
        $zipResponse = Read-Host "📦 Создать zip архив? (y/n)"
        if ($zipResponse -eq "y") {
            Write-Host "   Упаковка в архив..." -ForegroundColor Yellow
            if (Test-Path "CodeEditor.zip") { Remove-Item "CodeEditor.zip" }
            
            Add-Type -AssemblyName System.IO.Compression.FileSystem
            [System.IO.Compression.ZipFile]::CreateFromDirectory(
                "$(Get-Location)\dist",
                "$(Get-Location)\CodeEditor.zip"
            )
            
            $zipSize = (Get-Item "CodeEditor.zip").Length / 1MB
            Write-Host "✅ Архив создан: $(Get-Location)\CodeEditor.zip" -ForegroundColor Green
            Write-Host "   Размер архива: $([Math]::Round($zipSize, 1)) MB" -ForegroundColor Gray
        }
    }
    
    Write-Host ""
    Write-Host "📝 Что дальше:" -ForegroundColor Cyan
    Write-Host "   1. CodeEditor.exe - готов к распространению" -ForegroundColor Gray
    Write-Host "   2. Скопируйте файл на любой компьютер и запустите" -ForegroundColor Gray
    Write-Host "   3. Не требуется установка или зависимости" -ForegroundColor Gray
    Write-Host ""
    
} else {
    Write-Host "❌ ОШИБКА при создании exe!" -ForegroundColor Red
    Write-Host "   Проверьте сообщения об ошибках выше" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Нажмите Enter для выхода..." -ForegroundColor Gray
Read-Host
