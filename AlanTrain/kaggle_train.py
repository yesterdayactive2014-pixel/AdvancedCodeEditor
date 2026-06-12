"""
Alan Kaggle Training Notebook (одним файлом)
=============================================
Двухэтапное обучение: код → диалоги.
Каждый чекпоинт хранит в имени: что изучено (code / chat / full)

Загрузка на Kaggle:
  1. New Notebook → загрузить alan_nn.py и dataset.json через Add Data
  2. Вставить этот код в первую ячейку
  3. GPU Accelerator ON
  4. Run All

  alan_ep2_code.pt    — после этапа code (2 эпохи)
  alan_ep4_chat.pt    — после этапа chat (2 эпохи)
  alan_ep6_full.pt    — финальный (code + chat, 2 эпохи)
  training_log.json   — лог метрик по эпохам

Примечание: dataset.json берётся из кнопки "Собрать датасет" в AlanPanel.
Если loss падает быстрее — уменьши EPOCHS_* в настройках.
"""
import json, sys, os, torch, torch.nn as nn, torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
sys.path.insert(0, '/kaggle/working')
import alan_nn
from alan_nn import AlanTransformer, ByteTokenizer

# ─── конфиг ─────────────────────────────────────────────────────────
BATCH = 32
EPOCHS_CODE = 2
EPOCHS_CHAT = 2
EPOCHS_FULL = 2
LR = 3e-4
MAX_LEN = 512
DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'
DATA_PATH = '/kaggle/input/alan-dataset/dataset.json'  # меняй под свой dataset

# ─── датасет с loss-masking ────────────────────────────────────────
class InstructionDataset(Dataset):
    """Обучает Alan только на ответах, маскируя промпт (loss = -100)."""
    def __init__(self, path_or_data, max_len=MAX_LEN, stage='code'):
        self.tokenizer = ByteTokenizer()
        if isinstance(path_or_data, str):
            with open(path_or_data, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = path_or_data
        self.input_ids, self.labels = [], []
        inst_tag = b'[/INST]'
        for item in data:
            text = item['text']
            # Ищем конец инструкции
            inst_bytes = text.encode('utf-8')
            idx = inst_bytes.find(inst_tag)
            if idx == -1:
                continue
            end = idx + len(inst_tag)
            # Байтовое разбиение: токенизатор Alan = utf-8 bytes
            inst_tokens = list(inst_bytes[:end])
            full_tokens = list(inst_bytes[:max_len])
            # Маска: -100 на инструкцию, токены ответа как есть
            answer_tokens = full_tokens[len(inst_tokens):]
            inp = full_tokens
            lbl = [-100] * len(inst_tokens) + answer_tokens
            if len(lbl) > max_len:
                lbl = lbl[:max_len]
            if len(inp) >= 3:
                self.input_ids.append(inp)
                self.labels.append(lbl)
    def __len__(self):
        return len(self.input_ids)
    def __getitem__(self, i):
        return (torch.tensor(self.input_ids[i], dtype=torch.long),
                torch.tensor(self.labels[i], dtype=torch.long))

def collate_fn(batch):
    xs, ys = zip(*batch)
    m = max(x.size(0) for x in xs)
    xp = torch.zeros(len(xs), m, dtype=torch.long)
    yp = torch.full((len(ys), m), -100, dtype=torch.long)
    for i, (x, y) in enumerate(zip(xs, ys)):
        xp[i, :x.size(0)] = x
        yp[i, :y.size(0)] = y
    return xp, yp

# ─── генератор диалогового датасета ────────────────────────────────
# Эти пары учат Alan отвечать как ассистент, а не выдавать код.
CHAT_SEED = [
    ("Привет", "Привет! Я Alan, твой AI-ассистент в редакторе кода. Чем помочь?"),
    ("Как дела?", "Всё хорошо! Я здесь и готов помогать с кодом."),
    ("Кто ты?", "Я Alan — нейросеть (трансформер ~15M), живу внутри Advanced Code Editor."),
    ("Что ты умеешь?", "Объяснять код, SQL, Arduino, писать примеры, помогать с багами."),
    ("Спасибо", "Пожалуйста! Обращайся."),
    ("Пока", "До свидания! Буду здесь, если понадоблюсь."),
    ("Hello", "Hello! I'm Alan, your AI coding assistant."),
    ("Who are you?", "I'm Alan — a ~15M parameter transformer inside the Advanced Code Editor."),
    ("帮助我", "我是Alan，你的代码编辑助手。有什么可以帮助的吗？"),
    ("こんにちは", "こんにちは！私はAlanです。コードについて何でも聞いてください。"),
    ("Hallo", "Hallo! Ich bin Alan, dein KI-Assistent im Code-Editor."),
    ("Bonjour", "Bonjour ! Je suis Alan, assistant IA dans l'éditeur de code."),
    ("Hola", "¡Hola! Soy Alan, tu asistente de IA en el editor de código."),
    ("مرحبًا", "مرحبًا! أنا Alan، مساعدك الذكي في محرر الكود."),
]

def make_chat_dataset(pairs):
    """Преобразует список (query, answer) в формат dataset.json."""
    return [{"text": f"<s>[INST] {q} [/INST] {a} </s>"} for q, a in pairs]

# ─── обучение ──────────────────────────────────────────────────────
def train_epoch(model, loader, opt, device):
    model.train()
    total = 0
    for x, y in loader:
        x, y = x.to(device), y.to(device)
        logits = model(x)
        loss = F.cross_entropy(logits.reshape(-1, logits.size(-1)),
                               y.reshape(-1), ignore_index=-100)
        opt.zero_grad()
        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        total += loss.item()
    return total / len(loader)

def run_stage(model, opt, data, stage_name, epochs, device, start_ep=0):
    """Обучает и сохраняет чекпоинты с меткой этапа."""
    loader = DataLoader(data, batch_size=BATCH, shuffle=True, collate_fn=collate_fn)
    log = []
    for ep in range(epochs):
        loss = train_epoch(model, loader, opt, device)
        tag = f'{start_ep+ep+1}_{stage_name}'
        ckpt = f'alan_ep{tag}.pt'
        torch.save(model.state_dict(), ckpt)
        print(f'[{tag}] loss={loss:.4f} -> {ckpt}')
        log.append({"epoch": start_ep+ep+1, "stage": stage_name, "loss": round(loss, 4), "ckpt": ckpt})
    return log, start_ep + epochs

# ─── main ───────────────────────────────────────────────────────────
def main():
    print(f'[Alan] Device: {DEVICE}')
    model = AlanTransformer().to(DEVICE)
    opt = torch.optim.AdamW(model.parameters(), lr=LR)
    all_logs = []
    ep_offset = 0

    # ── ЭТАП 1: код (dataset.json с проектов) ──
    if os.path.exists(DATA_PATH):
        print(f'[Alan] Stage 1: code data from {DATA_PATH}')
        ds_code = InstructionDataset(DATA_PATH, stage='code')
        log, ep_offset = run_stage(model, opt, ds_code, 'code', EPOCHS_CODE, DEVICE, ep_offset)
        all_logs.extend(log)
    else:
        print(f'[Alan] {DATA_PATH} not found — skipping code stage')

    # ── ЭТАП 2: диалоги (conversational) ──
    print(f'[Alan] Stage 2: chat data ({len(CHAT_SEED)} seed pairs)')
    chat_data = make_chat_dataset(CHAT_SEED)
    ds_chat = InstructionDataset(chat_data, stage='chat')
    log, ep_offset = run_stage(model, opt, ds_chat, 'chat', EPOCHS_CHAT, DEVICE, ep_offset)
    all_logs.extend(log)

    # ── ЭТАП 3: совместная дообучка code+chat ──
    print('[Alan] Stage 3: full fine-tune (code + chat)')
    full_data = []
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH, 'r', encoding='utf-8') as f:
            full_data.extend(json.load(f))
    full_data.extend(chat_data)
    ds_full = InstructionDataset(full_data, stage='full')
    log, ep_offset = run_stage(model, opt, ds_full, 'full', EPOCHS_FULL, DEVICE, ep_offset)
    all_logs.extend(log)

    # ── финальный чекпоинт ──
    final = f'alan_final.pt'
    torch.save(model.state_dict(), final)
    print(f'[Alan] Final: {final}')

    # ── лог ──
    with open('training_log.json', 'w', encoding='utf-8') as f:
        json.dump(all_logs, f, indent=2)
    print(f'[Alan] Training log saved: training_log.json')
    print('[Alan] Done!')

def test(ckpt='alan_final.pt', device='cpu'):
    """Тестирование модели после обучения: вопросы из датасета + новые."""
    from alan_nn import generate
    model = AlanTransformer().to(device)
    state = torch.load(ckpt, map_location=device, weights_only=True)
    model.load_state_dict(state, strict=False)
    model.eval()
    tokenizer = ByteTokenizer()
    tests = [
        ("Привет", "приветствие"),
        ("Напиши hello world", "код"),
        ("Что такое SQL JOIN?", "из датасета"),
        ("Как открыть файл в Python?", "новый вопрос"),
        ("Напиши декоратор для замера времени", "новый код"),
    ]
    print(f'\n{"="*50}\nТестирование: {ckpt}\n{"="*50}')
    for q, tag in tests:
        prompt = f"<s>[INST] {q} [/INST]"
        raw = generate(model, tokenizer, prompt, max_new=128)
        answer = raw.split('[/INST]', 1)[-1].split('</s>')[0].strip()
        print(f'\n[{tag}] Q: {q}')
        print(f'A: {answer}')

if __name__ == '__main__':
    if '--test' in sys.argv:
        ckpt = sys.argv[sys.argv.index('--test') + 1] if '--test' in sys.argv and len(sys.argv) > sys.argv.index('--test') + 1 else 'alan_final.pt'
        test(ckpt, 'cuda' if torch.cuda.is_available() else 'cpu')
    else:
        main()
