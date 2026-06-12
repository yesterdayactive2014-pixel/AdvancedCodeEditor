# Alan Training на Kaggle

## Как использовать kaggle_train.py

### 1. Загрузить на Kaggle

1. Открыть [Kaggle](https://kaggle.com) → New Notebook
2. File → Upload Notebook → выбрать `AlanTrain/kaggle_train.py`
3. Добавить GPU: Settings → Accelerator → GPU T4 x2
4. Добавить dataset.json: либо через Add Data → Upload, либо вставить кодом:

```python
with open('/kaggle/input/alan-dataset/dataset.json', 'w') as f:
    json.dump(data, f)
```

### 2. Что делает обучение

| Этап | Данные | Эпох | Результат |
|------|--------|------|-----------|
| code | dataset.json (1072 пары код→вопрос) | 5 | `alan_ep5_code.pt` |
| chat | 14 диалоговых пар | 10 | `alan_ep15_chat.pt` |
| full | code + chat вместе | 5 | `alan_ep20_full.pt` |

### 3. Как понять, чему научилась версия

Имя чекпойнта говорит само:
- `alan_ep5_code.pt` — знает код, но не умеет общаться
- `alan_ep15_chat.pt` — умеет отвечать на приветствия, но подзабыла код
- `alan_ep20_full.pt` — баланс кода и диалогов

Если остановил обучение на Kaggle (например, кончились часы GPU):
1. Скачай последний `.pt` файл
2. Положи в `AlanTrain/`
3. Переименуй в `alan_ep6.pt` (или измени путь в `AlanPanel`)
4. При следующем запуске `_on_mode()` загрузит эти веса

### 4. Как улучшить диалоговую часть

В `kaggle_train.py` переменная `CHAT_SEED` содержит 14 пар.
**Добавь больше пар через другую модель:**

```bash
python AlanTrain/prepare_dataset.py --export-prompt
# → промпт для Claude/GPT → полученный JSON добавить в kaggle_train.py
```

Или вставь прямо в блокнот:

```python
extra_pairs = [
    ("Напиши сортировку пузырьком", "def bubble_sort(arr):\n    n = len(arr)\n    for i in range(n):\n        for j in range(0, n-i-1):\n            if arr[j] > arr[j+1]:\n                arr[j], arr[j+1] = arr[j+1], arr[j]"),
    ("Что такое рекурсия?", "Рекурсия — когда функция вызывает саму себя. Пример:\n  def fact(n): return 1 if n <= 1 else n * fact(n-1)"),
    ("Объясни SQL индексы", "Индексы ускоряют поиск: CREATE INDEX idx_name ON users(name)"),
]
chat_data.extend(make_chat_dataset(extra_pairs))
```

### 5. Перенос весов в редактор

После скачивания чекпоинта с Kaggle:

```bash
# Положить в AlanTrain/
mv ~/Downloads/alan_final.pt AlanTrain/alan_ep6.pt
```

При следующем запуске CodeEditor выбери Free/GPU в панели Alan — `_on_mode()` вызовет `engine.load()`, который подхватит `alan_ep6.pt` (если weights_path задан).
