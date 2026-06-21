"""
prepare_dataset.py — Подготовка датасета для instruction-tuning Lynx

Использование:
  1. Собрать CSV/JSON с парами вопрос-ответ (вручную или через другую LLM)
  2. Конвертировать в train-формат:  python prepare_dataset.py pairs.json -o dataset.json
  3. Обучить Lynx:                     python train_lynx.py --data dataset.json --epochs 20

Генерация датасета через другую модель:
  1. Запустите: python prepare_dataset.py --export-prompt > prompt_for_llm.txt
  2. Скопируйте prompt_for_llm.txt в Claude/GPT/DeepSeek и получите JSON-массив
  3. Сохраните ответ как pairs.json и конвертируйте: python prepare_dataset.py pairs.json -o dataset.json
"""
import json, sys, csv, os

TRAIN_FORMAT = '<s>[INST] {query} [/INST] {answer} </s>'

# Сидированные примеры для затравки (seed)
SEED_PAIRS = [
    # Русский
    ("Привет", "Привет! Я Lynx, твой AI-ассистент в редакторе кода. Чем могу помочь?"),
    ("Как дела?", "Всё отлично! Я встроен в Vela и готов помогать с кодом. Спрашивай!"),
    ("Кто ты?", "Я Lynx — нейросеть (трансформер ~15M параметров), обученная помогать с программированием. Работаю внутри Vertex Studio."),
    ("Что ты умеешь?", "Объяснять код, писать примеры, помогать с багами, SQL-запросами, Arduino, OrionScript. Спрашивай о чём угодно!"),
    ("Расскажи о себе", "Я Lynx, AI-ассистент на основе PyTorch. Использую байтовый токенизатор для работы с любым языком. Режимы: Free (CPU) и Premium (GPU)."),
    ("Спасибо", "Пожалуйста! Обращайся."),
    ("Пока", "До свидания! Буду здесь, если понадоблюсь."),
    ("Напиши hello world на Python", "print('Hello, World!')"),
    ("Как создать функцию в Python?", "def my_function(param):\n    return param * 2"),
    ("Что такое list comprehension?", "Это краткая запись создания списка:\n  squares = [x**2 for x in range(10)]"),
    ("Объясни декоратор", "Декоратор — функция, оборачивающая другую функцию:\n  @decorator\n  def foo(): pass"),
    ("Как открыть файл?", "with open('file.txt', 'r', encoding='utf-8') as f:\n    content = f.read()"),
    ("Что такое SQL JOIN?", "JOIN объединяет строки из двух таблиц по ключу:\n  SELECT * FROM users JOIN orders ON users.id = orders.user_id"),
    ("Напиши запрос SELECT", "SELECT name, age FROM users WHERE age > 18 ORDER BY name"),
    ("Как работает компилятор?", "Компилятор переводит исходный код в машинный. Этапы: лексический анализ → синтаксический → семантический → генерация кода."),

    # English
    ("Hello", "Hello! I'm Lynx, your AI assistant in the code editor. How can I help you?"),
    ("Who are you?", "I'm Lynx — a ~15M parameter transformer neural network trained to help with programming. I live inside the Vertex Studio."),
    ("Write a Fibonacci function", "def fib(n):\n    a, b = 0, 1\n    for _ in range(n):\n        yield a\n        a, b = b, a + b"),
    ("What is OOP?", "OOP (Object-Oriented Programming) is a paradigm based on objects containing data and methods. Key concepts: encapsulation, inheritance, polymorphism."),

    # Китайский
    ("你好", "你好！我是Lynx，你的代码编辑器AI助手。有什么可以帮助的吗？"),
    ("写一个Python函数", "def greet(name):\n    return f'Hello, {name}!'"),

    # Японский
    ("こんにちは", "こんにちは！私はLynx、コードエディターのAIアシスタントです。何かお手伝いしましょうか？"),

    # Корейский
    ("안녕하세요", "안녕하세요! 저는 Lynx, 코드 편집기 AI 어시스턴트입니다. 무엇을 도와드릴까요?"),

    # Немецкий
    ("Hallo", "Hallo! Ich bin Lynx, dein KI-Assistent im Code-Editor. Wie kann ich helfen?"),

    # Французский
    ("Bonjour", "Bonjour ! Je suis Lynx, ton assistant IA dans l'éditeur de code. Comment puis-je t'aider ?"),

    # Испанский
    ("Hola", "¡Hola! Soy Lynx, tu asistente de IA en el editor de código. ¿Cómo puedo ayudarte?"),

    # Арабский
    ("مرحبًا", "مرحبًا! أنا Lynx، مساعدك الذكي في محرر الكود. كيف يمكنني مساعدتك؟"),
]

PROMPT_TEMPLATE = """Ты — генератор тренировочных данных для маленькой нейросети Lynx (15M параметров, байтовый токенизатор).
Сгенерируй JSON-массив с парами "запрос-ответ" для обучения Lynx отвечать на вопросы о программировании.

Требования:
- Ответы должны быть короткими (1-3 предложения или 5-15 строк кода)
- Языки: русский (70%), английский (15%), китайский/японский/корейский/арабский/европейские (15%)
- Темы: Python, SQL, Arduino, HTML/CSS/JS, алгоритмы, структуры данных, OrionScript, Git
- Ответы на простые приветствия должны быть дружественными
- Код должен быть синтаксически корректным

Формат каждой пары:
{{"query": "вопрос пользователя", "answer": "ответ Lynx"}}

Верни ТОЛЬКО JSON-массив, без пояснений. Сгенерируй 50-100 пар.

Примеры правильных пар:
{"query": "Что такое SQL JOIN?", "answer": "JOIN объединяет строки из двух таблиц по ключу: SELECT * FROM users JOIN orders ON users.id = orders.user_id"}
{"query": "Write a Fibonacci function", "answer": "def fib(n):\\n    a, b = 0, 1\\n    for _ in range(n):\\n        yield a\\n        a, b = b, a + b"}
"""

def load_pairs(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == '.json':
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, dict) and 'pairs' in data:
            return data['pairs']
        if isinstance(data, list):
            if all(isinstance(x, dict) and 'text' in x for x in data):
                return [(x['text'].split('[/INST]')[0].split('[INST]')[-1].strip(),
                         x['text'].split('[/INST]')[-1].replace('</s>','').strip())
                        for x in data if '[/INST]' in x.get('text','')]
            if all(isinstance(x, list) and len(x) == 2 for x in data):
                return [(x[0], x[1]) for x in data]
            if all(isinstance(x, dict) and 'query' in x and 'answer' in x for x in data):
                return [(x['query'], x['answer']) for x in data]
    elif ext == '.csv':
        pairs = []
        with open(path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader, None)
            for row in reader:
                if len(row) >= 2:
                    pairs.append((row[0].strip(), row[1].strip()))
        return pairs
    elif ext == '.txt':
        pairs = []
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if '|' in line:
                    parts = line.split('|', 1)
                    pairs.append((parts[0].strip(), parts[1].strip()))
        return pairs
    raise ValueError(f'Неизвестный формат: {ext}')

def convert(pairs):
    items = [{"text": TRAIN_FORMAT.format(query=q, answer=a)} for q, a in pairs]
    return items

def export_seed(path='seed_pairs.json'):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump([{"query": q, "answer": a} for q, a in SEED_PAIRS], f, ensure_ascii=False, indent=2)
    print(f'[Lynx] Seed pairs saved: {path} ({len(SEED_PAIRS)} pairs)')

def merge_datasets(paths, output):
    all_items = []
    for p in paths:
        items = convert(load_pairs(p))
        all_items.extend(items)
        print(f'[Lynx] +{p}: {len(items)} pairs')
    with open(output, 'w', encoding='utf-8') as f:
        json.dump(all_items, f, ensure_ascii=False, indent=2)
    print(f'[Lynx] Merged dataset: {output} ({len(all_items)} total pairs)')

if __name__ == '__main__':
    if '--export-prompt' in sys.argv:
        with open('prompt_for_llm.txt', 'w', encoding='utf-8') as f:
            f.write(PROMPT_TEMPLATE)
        print('[Lynx] Prompt exported to prompt_for_llm.txt — скопируй в Claude/GPT/DeepSeek')
        sys.exit(0)

    if '--seed' in sys.argv:
        export_seed()
        sys.exit(0)

    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    if sys.argv[1] == '--merge':
        output = sys.argv[sys.argv.index('-o') + 1] if '-o' in sys.argv else 'dataset.json'
        merge_datasets(sys.argv[2:], output)
    else:
        output = sys.argv[sys.argv.index('-o') + 1] if '-o' in sys.argv else 'dataset.json'
        pairs = load_pairs(sys.argv[1])
        items = convert(pairs)
        with open(output, 'w', encoding='utf-8') as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
        print(f'[Lynx] Converted {len(items)} pairs -> {output}')
