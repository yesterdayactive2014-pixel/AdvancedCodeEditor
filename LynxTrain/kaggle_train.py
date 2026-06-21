"""
Lynx Kaggle Training Notebook v2.5 (Монолитный файл)
======================================================
Двухэтапное обучение с loss-masking, сдвигом токенов,
защитой от взрыва градиентов и автоматическим построением графиков.

Инструкция:
  1. Создай новый Notebook на Kaggle.
  2. Справа нажмите "+ Add Input" -> "Your Datasets" -> добавь свой датасет.
  3. Включи GPU (Settings -> Accelerator -> GPU T4 x2 или P100).
  4. Вставь этот код в первую ячейку и нажмите "Run All".
"""
import json
import sys
import os
import math
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
import matplotlib.pyplot as plt

# Подключаем рабочую директорию, где лежит оригинальный lynx_nn.py
sys.path.insert(0, '/kaggle/working')
import lynx_nn
from lynx_nn import LynxTransformer, ByteTokenizer

# ─── КОНФИГ ОБУЧЕНИЯ ─────────────────────────────────────────────────
BATCH = 32
EPOCHS_CODE = 2
EPOCHS_CHAT = 2
EPOCHS_FULL = 2
LR = 3e-4
MAX_LEN = 512
DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'

# Автоматический поиск путей (на случай, если папка датасета называется иначе)
DATA_PATH = '/kaggle/input/alan-dataset/dataset.json'
for root, _, files in os.walk('/kaggle/input'):
    for f in files:
        if f == 'dataset.json':
            DATA_PATH = os.path.join(root, f)
            print(f"🎯 Найдена актуальная точка датасета: {DATA_PATH}")

# ─── ДАТАСЕТ С LOSS-MASKING ──────────────────────────────────────────
class InstructionDataset(Dataset):
    """Обучает Lynx только на ответах, маскируя промпт (loss = -100)."""
    def __init__(self, path_or_data, max_len=MAX_LEN):
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
            inst_bytes = text.encode('utf-8')
            idx = inst_bytes.find(inst_tag)
            if idx == -1:
                continue
            end = idx + len(inst_tag)
            
            inst_tokens = list(inst_bytes[:end])
            full_tokens = list(inst_bytes[:max_len])
            
            answer_tokens = full_tokens[len(inst_tokens):]
            inp = full_tokens
            lbl = [-100] * len(inst_tokens) + answer_tokens
            
            if len(lbl) > max_len:
                lbl = lbl[:max_len]
            if len(inp) >= 3:
                self.input_ids.append(inp)
                self.labels.append(lbl)

    def __len__(self): return len(self.input_ids)
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

# ─── ГЕНЕРАТОР ДИАЛОГОВОГО ДАТАСЕТА ─────────────────────────────────
CHAT_SEED = [
    ("Привет", "Привет! Я Lynx, твой AI-ассистент в редакторе кода. Чем помочь?"),
    ("Как дела?", "Всё хорошо! Я здесь и готов помогать с кодом."),
    ("Кто ты?", "Я Lynx — нейросеть (трансформер ~15M), живу внутри Vertex Studio."),
    ("Что ты умеешь?", "Объяснять код, SQL, Arduino, писать примеры, помогать с багами."),
    ("Спасибо", "Пожалуйста! Обращайся."),
    ("Пока", "До свидания! Буду здесь, если понадоблюсь."),
    ("Hello", "Hello! I'm Lynx, your AI coding assistant."),
    ("Who are you?", "I'm Lynx — a ~15M parameter transformer inside the Vertex Studio."),
    ("帮助我", "我是Lynx，你的代码编辑助手。有什么可以帮助的吗？"),
    ("こんにちは", "こんにちは！私はLynxです。コードについて何でも聞いてください。"),
    ("Hallo", "Hallo! Ich bin Lynx, dein KI-Assistent im Code-Editor."),
    ("Bonjour", "Bonjour ! Je suis Lynx, assistant IA dans l'éditeur de code."),
    ("Hola", "¡Hola! Soy Lynx, tu asistente de IA en el editor de código."),
    ("مرحبًا", "مرحبًا! أنا Lynx، مساعدك الذكي في محرر الكود."),
]

def make_chat_dataset(pairs):
    return [{"text": f"<s>[INST] {q} [/INST] {a} </s>"} for q, a in pairs]

# ─── УСТОЙЧИВЫЙ ЦИКЛ ОБУЧЕНИЯ (Causal Shift + Grad Clip) ───────────
def train_epoch(model, loader, opt, device):
    model.train()
    total = 0
    for x, y in loader:
        x, y = x.to(device), y.to(device)
        logits = model(x)
        
        # 🌟 СДВИГ ТОКЕНОВ ДЛЯ CAUSAL LM: предсказываем токен t+1 по логиту t
        shift_logits = logits[..., :-1, :].contiguous()
        shift_labels = y[..., 1:].contiguous()
        
        loss = F.cross_entropy(
            shift_logits.reshape(-1, shift_logits.size(-1)),
            shift_labels.reshape(-1), 
            ignore_index=-100
        )
        
        opt.zero_grad()
        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), 1.0) # Защита от взрыва градиентов
        opt.step()
        total += loss.item()
    return total / len(loader)

def run_stage(model, opt, data, stage_name, epochs, device, start_ep=0):
    loader = DataLoader(data, batch_size=BATCH, shuffle=True, collate_fn=collate_fn)
    stage_logs = []
    for ep in range(epochs):
        loss = train_epoch(model, loader, opt, device)
        curr_ep = start_ep + ep + 1
        tag = f'{curr_ep}_{stage_name}'
        ckpt = f'lynx_ep{tag}.pt'
        torch.save(model.state_dict(), ckpt)
        print(f'[{tag}] loss={loss:.4f} -> {ckpt}')
        stage_logs.append({"epoch": curr_ep, "stage": stage_name, "loss": round(loss, 4), "ckpt": ckpt})
    return stage_logs, start_ep + epochs

# ─── ЛОКАЛЬНЫЙ НЕУБИВАЕМЫЙ ИНФЕРЕНС (ГЕНЕРАЦИЯ) ────────────────────
def local_generate(model, prompt, max_len=128, device='cpu'):
    """Улучшенная функция генерации с защитой от NaN/Inf и точным отбором."""
    model.eval()
    tokenizer = ByteTokenizer()
    in_ids = tokenizer.encode(prompt)
    x = torch.tensor([in_ids]).to(device)
    
    generated = []
    with torch.no_grad():
        for _ in range(max_len):
            logits = model(x)
            logits = torch.nan_to_num(logits, nan=0.0, posinf=0.0, neginf=0.0) # Фикс NaN ошибок
            next_token_logits = logits[:, -1, :]
            next_id = torch.argmax(next_token_logits, dim=-1).item()
            
            if next_id == tokenizer.encode('\n')[-1] and len(generated) > 5:
                break
            generated.append(next_id)
            x = torch.cat([x, torch.tensor([[next_id]]).to(device)], dim=1)
            if x.size(1) >= MAX_LEN: break
            
    return tokenizer.decode(generated)

# ─── ПОСТРОЕНИЕ ГРАФИКОВ ОБУЧЕНИЯ ──────────────────────────────────
def plot_training_results(logs):
    """Строит красивый график изменения loss по этапам."""
    epochs = [item['epoch'] for item in logs]
    losses = [item['loss'] for item in logs]
    stages = [item['stage'] for item in logs]
    
    plt.figure(figsize=(10, 5))
    colors = {'code': '#1f77b4', 'chat': '#ff7f0e', 'full': '#2ca02c'}
    
    for i in range(len(epochs)):
        plt.scatter(epochs[i], losses[i], color=colors[stages[i]], s=100, zorder=3)
        
    plt.plot(epochs, losses, color='#7f7f7f', linestyle='--', alpha=0.6, zorder=2)
    plt.title('Vertex Studio: Траектория обучения ИИ Lynx', fontsize=14, fontweight='bold')
    plt.xlabel('Общая Эпоха', fontsize=12)
    plt.ylabel('Значение Loss (Ошибка)', fontsize=12)
    plt.grid(True, linestyle=':', alpha=0.6)
    
    # Кастомная легенда
    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], marker='o', color='w', label='Этап 1: Код', markerfacecolor=colors['code'], markersize=10),
        Line2D([0], [0], marker='o', color='w', label='Этап 2: Диалог', markerfacecolor=colors['chat'], markersize=10),
        Line2D([0], [0], marker='o', color='w', label='Этап 3: Совместный', markerfacecolor=colors['full'], markersize=10)
    ]
    plt.legend(handles=legend_elements, loc='upper right')
    plt.savefig('alan_training_chart.png', dpi=300)
    plt.show()

# ─── MAIN ───────────────────────────────────────────────────────────
def main():
    print(f'🚀 [Lynx System] Запуск на устройстве: {DEVICE.upper()}')
    model = LynxTransformer().to(DEVICE)
    opt = torch.optim.AdamW(model.parameters(), lr=LR)
    all_logs = []
    ep_offset = 0

    # ── ЭТАП 1: код (dataset.json с проектов) ──
    if os.path.exists(DATA_PATH):
        print(f'\n🔥 [Этап 1/3] Запуск обучения на коде из {DATA_PATH}')
        ds_code = InstructionDataset(DATA_PATH)
        log, ep_offset = run_stage(model, opt, ds_code, 'code', EPOCHS_CODE, DEVICE, ep_offset)
        all_logs.extend(log)
    else:
        print(f'\n⚠️ [Этап 1/3] Файл {DATA_PATH} не обнаружен — пропускаем код-фазу')

    # ── ЭТАП 2: диалоги (conversational) ──
    print(f'\n🔥 [Этап 2/3] Запуск диалогового обучения ({len(CHAT_SEED)} seed-пар)')
    chat_data = make_chat_dataset(CHAT_SEED)
    ds_chat = InstructionDataset(chat_data)
    log, ep_offset = run_stage(model, opt, ds_chat, 'chat', EPOCHS_CHAT, DEVICE, ep_offset)
    all_logs.extend(log)

    # ── ЭТАП 3: совместная дообучка code+chat ──
    print('\n🔥 [Этап 3/3] Финальная полировка: совместное обучение (код + чат)')
    full_data = []
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH, 'r', encoding='utf-8') as f:
            full_data.extend(json.load(f))
    full_data.extend(chat_data)
    ds_full = InstructionDataset(full_data)
    log, ep_offset = run_stage(model, opt, ds_full, 'full', EPOCHS_FULL, DEVICE, ep_offset)
    all_logs.extend(log)

    # ── Сохранение финальных весов и логов ──
    final_ckpt = 'lynx_final.pt'
    torch.save(model.state_dict(), final_ckpt)
