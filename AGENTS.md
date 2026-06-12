# AGENTS.md — Мультиязычная IDE-Полиглот (Релизная Сборка)

## 1. Общие параметры дистрибутива
- **Исполняемый файл:** `dist\CodeEditor.exe` (201 МБ, полностью автономный).
- **Окружение:** PyQt6 6.11.0 + встроенный модуль `PyQt6.QtWebEngineCore/Widgets` (Chromium вшит внутрь).
- **Поддерживаемые языки:** 46 языков программирования + встроенные инструменты управления.
- **Интерфейс Scratch:** Кнопка "Scratch IDE" в тулбаре (всегда видна) с иконкой (`Scratch3-original.png`) запускает встроенный `QWebEngineView`, полностью изолированный от внешних браузеров.
- **Data Bridge:** Двусторонний `QWebChannel`. Передача бинарных проектов `.sb3` упакована в Base64 (`BASE64:`) во избежание порчи ZIP-архива UTF-8 кодировкой.
- **Фронтенд-компилятор:** JSZip распаковывает `project.json` на лету, маппит 55 опкодов Scratch 3.0, шедулер с `AbortController`.
- **Number()-коэрция**: математические операторы обёрнуты в `Number()` в обоих транспляторах.

## 2. Архитектура

```
code_editor.py  (PyQt6 десктоп — бэкенд, ~4193 строк, 17 классов)
     │
     │  QWebChannel (Python ↔ JS мост)
     │  - ScratchBridge: sendCodeToWeb(), sendJsonToWeb(), sendSb3ToWeb(), logFromJs()
     │
     ▼
index.html  (QWebEngineView — фронтенд в вкладке "Scratch IDE", ~2140 строк)
     │
     ├── ScratchRuntime + Scheduler  (Scratch → JS рантайм)
     ├── Transpiler (JS)            (Scratch JSON → JS код)
     ├── C++ transpileToIno()       (Scratch JSON → Arduino .ino)
     ├── StepPlayer + VizDraw       (пошаговая визуализация)
     └── .sb3 parser (JSZip)       (Scratch 3.0 проекты)

transpile.py  (Python-трансплятор, дублирует JS-трансплятор, ~771 строка)
     ├── transpile(), transpile_project()  → JS
     ├── transpile_to_ino()                → Arduino C++
     └── convert_sb3_blocks()              → .sb3 → наш формат
```

## 3. Интерактивный Терминал (🌌 OrionScript Terminal)

- **Управление процессами:** Класс `TerminalProcessManager` асинхронно управляет `QProcess` с каскадным автодекодированием (`utf-8` -> `cp866` -> `cp1251`) для корректного вывода кириллицы.
- **Компоненты UI:**
  - Стильная шапка `🌌 OrionScript Terminal`.
  - Квадратный компактный виджет движка `ose_combo` (42x24, синий фон `#0e639c`, текст "OSE", Tooltip: `OSE (OrionScript Engine)`).
  - Выпадающий список `mode_combo` для выбора активного режима.
  - Красная кнопка экстренной остановки (`#c04040`), вызывающая принудительный `.kill()` текущего процесса.
  - Интерактивная строка ввода `QLineEdit` с историей команд (Вверх/Вниз).
- **Режимы работы (3 режима):**
  1. `System Shell` — Интерактивный PowerShell (Windows) / Bash (Linux) с префиксом `powershell >`.
  2. `Language REPL` — Интерактивный запуск `python -i` или `node` под язык активного файла с префиксом `repl >>>`.
  3. `IDE Commands` — Текстовое управление средой (префикс `ide $`): `clear` (очистка), `run` (запуск открытого файла по матрице 46 языков), `stop` (убить процесс), `scratch` (фокус на веб-сцену), `ports` (вывод доступных COM-портов через `QSerialPortInfo`).

## 4. Железо и Визуализация (VizDraw)

- **Hardware Control:** Поддержка профилей оборудования (Arduino, ESP32, E3-RCU). Фоновый вызов `arduino-cli` через `QProcess` с построчным чтением логов сборки.
- **StepPlayer Canvas:** Пошаговая инфографика на базе JSON Snapshot-пакетов для 4 областей: сортировки (`array`), базы данных (`sql` SELECT/WHERE построчно), связные списки (`linkedlist`), бинарные деревья поиска (`tree`).

## 5. Ключевые файлы

| Файл | Строк | Описание |
|------|-------|----------|
| `code_editor.py` | ~4193 | Главное приложение PyQt6 (17 классов) |
| `index.html` | ~2140 | Фронтенд в QWebEngineView |
| `transpile.py` | ~771 | Python-трансплятор (JS + C++ + .sb3) |
| `build.ps1` | — | Сборка exe через PyInstaller |
| `AGENTS.md` | — | Этот файл (контекст проекта) |

## 6. Основные классы code_editor.py

| Класс | Назначение |
|-------|------------|
| `PygmentsHighlighter` | Подсветка синтаксиса 46 языков через Pygments |
| `FirebaseRulesHighlighter` | Кастомная подсветка `.rules` (Dracula, 15 паттернов) |
| `FileLoaderThread` | Фоновый поток загрузки >5MB файлов |
| `CodeEditor` (QPlainTextEdit) | Редактор: нумерация строк, IntelliSense, сниппеты |
| `CompletionEngine` | Статический движок: 46 языков, lazy `_build_maps()`, кэш `QStringListModel` |
| `FileTreeWidget` (QTreeWidget) | Файловый менеджер с lazy-загрузкой, иконки по расширению |
| `ImageViewer` (QGraphicsView) | Просмотр изображений (SVG/PNG/JPG) |
| `Node` / `TreeNode` | Вспомогательные классы для алгоритмов (LL, BST) |
| `BackendAlgorithmTracer` | Генератор snapshot-шагов (5 сортировок, LL, BST) |
| `SQLWhereParser` | Парсер WHERE (AND/OR/NOT, LIKE, IN, BETWEEN, IS NULL), 2 таблицы |
| `ScratchBridge` (QObject) | Мост QWebChannel: 4 слота/сигнала |
| `TerminalConsole` (QPlainTextEdit) | Read-only консоль с цветным выводом |
| `TerminalProcessManager` (QObject) | QProcess-менеджер 3 режимов, декодинг, IDE-парсер |
| `TerminalWidget` (QWidget) | UI терминала: шапка OSE, комбобокс, история, ввод |
| `CodeEditorApp` (QMainWindow) | Главное окно: UI, меню, тулбар, Arduino, Scratch, терминал |

## 7. Форматы данных

### Snapshot-пакеты для StepPlayer
```json
{"type":"array","step":5,"array":[34,12,67,3],"active":[2,3],"sorted":[0],"operation":"compare"}
{"type":"sql","columns":["id","name","age"],"rows":[[1,"Alice",25]],"activeRow":0,"filterStatus":"checking"}
{"type":"linkedlist","nodes":[{"id":1,"value":5,"next":2}],"active":[1],"operation":"append"}
{"type":"tree","nodes":[{"id":1,"value":10,"left":2,"right":null}],"active":[1],"operation":"insert"}
```

### Scratch JSON (входной формат блоков)
```json
{"type":"event_when_flag_clicked","children":[{"type":"motion_move","steps":10}]}
{"type":"arduino_set_pin_mode","pin":13,"mode":"OUTPUT"}
```

## 8. Функции моста (QWebChannel)

| Функция JS | Вызывается из Python | Назначение |
|---|---|---|
| `window.receiveFromPython(code)` | `bridge.sendCodeToWeb()` / `sendSb3ToWeb()` | JSON блоки / raw JS / `BASE64:` .sb3 |
| `window.receiveSnapshots(json, mode)` | `bridge.sendJsonToWeb()` | Snapshot-шаги визуализации |
| `bridge.logFromJs(level, msg)` | Из `runtime._onLog` | Логи из JS в Python |

## 9. Состояние реализации

### ✅ Полностью работает
- 46 языков: подсветка Pygments, IntelliSense (QCompleter), сниппеты
- Файловый менеджер (ленивая загрузка, иконки, цвета)
- ImageViewer (SVG/PNG/JPG, QGraphicsView + zoom)
- Scratch→JS трансляция (index.html + transpile.py) — 55 опкодов
- .sb3 парсинг (Base64 → JSZip → convertSb3Blocks)
- QWebChannel мост (ScratchBridge) с Base64-упаковкой
- COM-порты (QSerialPortInfo + arduino-cli compile/upload)
- StepPlayer + VizDraw (array/sql/linkedlist/tree)
- BackendAlgorithmTracer (5 сортировок, LL, BST)
- SQLWhereParser (WHERE: AND/OR/NOT, LIKE, IN, BETWEEN, IS NULL)
- Number()-коэрция в обоих транспляторах
- 🌌 OrionScript Terminal (3 режима: System Shell, REPL, IDE Commands)

### ⚠️ Требует внешних зависимостей (не вшиваются)
- **arduino-cli** — для компиляции/прошивки Arduino (должен быть на PATH)
- **Web Serial API** — для реального подключения платы (в браузере)

### 🔧 Известные ограничения
- `QTextCharFormat::setBold()` отсутствует в PyQt6 6.11 → `setFontWeight(QFont.Weight.Bold)`
- `QSvgRenderer.render()` возвращает None при успехе в PyQt6 6.11
- SQL парсер не поддерживает JOIN, GROUP BY, ORDER BY
- QProcess не прерывается при закрытии вкладки с логом компиляции

## 10. Сборка exe
```powershell
python -m pip install PyQt6==6.11.0 PyQt6-WebEngine==6.11.0 Pygments pyinstaller -q
python -m PyInstaller --onefile --windowed --name="CodeEditor" --distpath "dist" `
    --add-data "assets;assets" `
    --hidden-import "PyQt6.QtWebEngineWidgets" `
    --hidden-import "PyQt6.QtWebChannel" `
    --hidden-import "PyQt6.QtSerialPort" `
    code_editor.py
# Выход: dist/CodeEditor.exe ~201 MB
```

## 11. Команды для проверки
```powershell
python -c "import ast; ast.parse(open('code_editor.py','r',encoding='utf-8').read()); print('Python: OK')"
python -c "from transpile import transpile_to_ino, transpile_project; print('transpile: OK')"
python -c "from PyQt6.QtWebEngineWidgets import QWebEngineView; from PyQt6.QtSerialPort import QSerialPortInfo; print('Imports: OK')"
```

## 12. Встроенный ИИ-ассистент "Alan"

Ассистент "Alan" встроен в правую панель редактора (QDockWidget). Использует **Ollama + llama3:8b** как бэкенд — локальный трансформер больше не применяется.

### Техническая спецификация Alan (`alan_nn.py`)

| Параметр | Значение |
|----------|----------|
| Файл | `alan_nn.py` (~900 строк) |
| Бэкенд | Ollama (llama3:8b) через HTTP API |
| Движок | Устанавливается отдельно (встроен в установщик) |
| Альтернатива | Локальный AlanTransformer 15M params (не используется) |

### Режимы работы

| Режим | Движок | Требования |
|-------|--------|-----------|
| **Alan + Llama** | Ollama llama3:8b | `ollama serve` + `ollama pull llama3:8b` |
| **CPU Fallback** | — | Планируется |

### Компоненты `alan_nn.py`

| Класс/Функция | Назначение |
|---------------|-----------|
| `LlamaWorker(QThread)` | Асинхронный вызов Ollama с историей диалога |
| `DownloadWorker(QThread)` | Скачивание модели через `ollama pull` с прогрессом |
| `AlanPanel(QWidget)` | Панель чата с кнопками, историей, действиями |
| `AlanEngine` | (устарел) |
| `AlanWorker` | (устарел) |

### Форматирование кода в чате

Alan подсвечивает блоки кода в ответах с помощью Pygments:

- Блоки ```lang … ``` обнаруживаются и обрабатываются `_format_code_blocks()`
- `_highlight_code()` использует Pygments `get_lexer_by_name()` с fallback на `guess_lexer()`
- Стиль: Monokai, `noclasses=True` (inline-стили)
- Вёрстка: `<table>` с тёмным фоном (`#1e1e1e`), шапкой с названием языка (`📄 PYTHON`) и `<pre>` с кодом
- Если Pygments не установлен — возвращается чистый текст с заменой `\n` на `<br>`

### Действия Alan (AI → Editor)

Alan может выполнять действия в редакторе через XML-блоки в ответе:

```xml
<action type="create_file" path="main.py">содержимое файла</action>
<action type="open_file" path="путь/к/файлу" />
<action type="run_code" />
<action type="save" />
```

Эти блоки парсятся в `AlanPanel._execute_actions()` и выполняются через ссылку на `CodeEditorApp`.

### История диалога

- Хранится в `AlanPanel.history` (макс. 20 сообщений, 10 пар)
- Передаётся в `LlamaWorker._build_full_prompt()` как предыдущие реплики
- Если пользователь не здоровается — Alan не приветствует в ответ

### Интеграция в `CodeEditorApp`

```python
from alan_nn import AlanPanel

self.alan_panel = AlanPanel(main_app=self)  # main_app для действий
self.alan_dock.setWidget(self.alan_panel)
```

### Установка

1. Установщик кладёт `ollama.exe` в `{app}\ollama\`
2. При первом запуске Alan проверяет наличие модели через `ollama list`
3. Если модели нет — показывает кнопку "Скачать модель (llama3:8b, ~4 GB)"
4. Прогресс-бар отслеживает `ollama pull`
5. После скачивания — чат активируется

## 13. Система автообновлений

Редактор автоматически проверяет новую версию через 3 секунды после старта.

### Компоненты

| Компонент | Файл |
|-----------|------|
| Версия | `VERSION = "1.0.0"` в code_editor.py:77 |
| URL проверки | `raw.githubusercontent.com/.../main/version.json` |
| `UpdateChecker` | QThread: GET → сравнение версий → сигнал |
| Ручная проверка | Справка → Проверить обновления |
| Скачивание | `.exe` в `%TEMP%`, запуск `/SILENT`, выход |

### `version.json`
```json
{"version":"1.1.0","url":"https://github.com/.../releases/download/v1.1.0/setup.exe"}
```

## 14. Сборка установщика

1. `build_setup.bat` — автоматическая сборка:
   - PyInstaller → `CodeEditor.exe`
   - Скачивает `ollama.exe` с GitHub
   - Компилирует `setup.iss` через Inno Setup
2. `setup.iss` — Inno Setup 6+
   - Windows 7 SP1 / 10 / 11
   - Десктопный ярлык (опционально)
   - Встроенный `ollama.exe`
   - `/SILENT` для автообновлений
```
