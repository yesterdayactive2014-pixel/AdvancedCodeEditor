"""
Alan v2.5 — локальный instruction-tuning (CPU/GPU)
Двухэтапное обучение, loss-masking, фикс сдвига токенов, графики matplotlib.
"""
import json, sys, os, torch, torch.nn as nn, torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
from alan_nn import AlanTransformer, ByteTokenizer

# ─── пути ───────────────────────────────────────────────────────────
DATA_PATH = "AlanTrain/dataset.json"
MODELS_DIR = "AlanTrain/models"
os.makedirs(MODELS_DIR, exist_ok=True)

# ─── конфиг ─────────────────────────────────────────────────────────
BATCH = 32
EPOCHS_CODE = 2
EPOCHS_CHAT = 2
EPOCHS_FULL = 2
LR = 3e-4
MAX_LEN = 512
DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'

# ─── датасет с loss-masking + фикс сдвига токенов ──────────────────
class InstructionDataset(Dataset):
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
            if len(answer_tokens) < 1:
                continue
            # Фикс сдвига: метка на позиции i — это full_tokens[i+1]
            # Маскируем все позиции инструкции, КРОМЕ последней (она должна предсказать a0)
            inp = full_tokens
            lbl = [-100] * (len(inst_tokens) - 1) + answer_tokens
            # Метка последнего токена — -100 (нечего предсказывать)
            if len(lbl) < len(inp):
                lbl.append(-100)
            lbl = lbl[:len(inp)]
            if len(inp) >= 2:
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

# ─── диалоговый датасет ─────────────────────────────────────────────
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
    loader = DataLoader(data, batch_size=BATCH, shuffle=True, collate_fn=collate_fn)
    log = []
    for ep in range(epochs):
        loss = train_epoch(model, loader, opt, device)
        ep_num = start_ep + ep + 1
        ckpt = os.path.join(MODELS_DIR, f'alan_ep{ep_num}_{stage_name}.pt')
        torch.save(model.state_dict(), ckpt)
        print(f'[{stage_name} ep{ep_num}] loss={loss:.4f} -> {ckpt}')
        log.append({"epoch": ep_num, "stage": stage_name, "loss": round(loss, 4), "ckpt": ckpt})
    return log, start_ep + epochs

# ─── графики matplotlib ─────────────────────────────────────────────
def plot_loss(log, save_path=os.path.join(MODELS_DIR, 'loss_plot.png')):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        epochs = [e['epoch'] for e in log]
        losses = [e['loss'] for e in log]
        stages = [e['stage'] for e in log]
        colors = {'code': '#569cd6', 'chat': '#c586c0', 'full': '#6a9955'}
        fig, ax = plt.subplots(figsize=(10, 5))
        prev_stage = None
        for i, (ep, loss, stage) in enumerate(zip(epochs, losses, stages)):
            color = colors.get(stage, '#d4d4d4')
            ax.scatter(ep, loss, c=color, s=50, zorder=5)
            if stage != prev_stage and i > 0:
                ax.axvline(x=ep - 0.5, color='#555', linestyle='--', alpha=0.5)
            prev_stage = stage
        ax.plot(epochs, losses, color='#d4d4d4', linewidth=1, alpha=0.6)
        ax.set_xlabel('Epoch', color='#d4d4d4')
        ax.set_ylabel('Loss', color='#d4d4d4')
        ax.set_title('Alan Training Loss', color='#d4d4d4')
        ax.tick_params(colors='#d4d4d4')
        for spine in ax.spines.values():
            spine.set_color('#555')
        ax.set_facecolor('#1e1e1e')
        fig.patch.set_facecolor('#1e1e1e')
        handles = [plt.Line2D([0], [0], marker='o', color='w', markerfacecolor=c,
                              markersize=8, label=s.capitalize())
                   for s, c in colors.items() if s in stages]
        ax.legend(handles=handles, facecolor='#252526', labelcolor='#d4d4d4',
                  loc='upper right')
        fig.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close(fig)
        print(f'[Alan] Loss plot saved: {save_path}')
    except ImportError:
        print('[Alan] matplotlib not installed — skipping plot')

# ─── тест ───────────────────────────────────────────────────────────
def test(ckpt, device='cpu'):
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

# ─── main ───────────────────────────────────────────────────────────
def main(resume_ckpt=None, start_ep=0):
    print(f'[Alan v2.5] Device: {DEVICE} | Data: {DATA_PATH} | Models: {MODELS_DIR}')
    model = AlanTransformer().to(DEVICE)
    opt = torch.optim.AdamW(model.parameters(), lr=LR)
    all_logs = []
    ep_offset = start_ep

    if resume_ckpt and os.path.exists(resume_ckpt):
        state = torch.load(resume_ckpt, map_location=DEVICE, weights_only=True)
        model.load_state_dict(state, strict=False)
        print(f'[Alan] Resumed from: {resume_ckpt} (starting ep {start_ep+1})')

    # ЭТАП 1: код
    if os.path.exists(DATA_PATH):
        print(f'[Alan] Stage 1: code data from {DATA_PATH}')
        ds_code = InstructionDataset(DATA_PATH)
        log, ep_offset = run_stage(model, opt, ds_code, 'code', EPOCHS_CODE, DEVICE, ep_offset)
        all_logs.extend(log)
    else:
        print(f'[Alan] {DATA_PATH} not found — skipping code stage')

    # ЭТАП 2: диалоги
    print(f'[Alan] Stage 2: chat ({len(CHAT_SEED)} pairs)')
    chat_data = make_chat_dataset(CHAT_SEED)
    ds_chat = InstructionDataset(chat_data)
    log, ep_offset = run_stage(model, opt, ds_chat, 'chat', EPOCHS_CHAT, DEVICE, ep_offset)
    all_logs.extend(log)

    # ЭТАП 3: совместная дообучка
    print('[Alan] Stage 3: full fine-tune')
    full_data = []
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH, 'r', encoding='utf-8') as f:
            full_data.extend(json.load(f))
    full_data.extend(chat_data)
    ds_full = InstructionDataset(full_data)
    log, ep_offset = run_stage(model, opt, ds_full, 'full', EPOCHS_FULL, DEVICE, ep_offset)
    all_logs.extend(log)

    # финал
    final = os.path.join(MODELS_DIR, 'alan_final.pt')
    torch.save(model.state_dict(), final)
    print(f'[Alan] Final checkpoint: {final}')

    # лог
    log_path = os.path.join(MODELS_DIR, 'training_log.json')
    with open(log_path, 'w', encoding='utf-8') as f:
        json.dump(all_logs, f, indent=2)
    print(f'[Alan] Log saved: {log_path}')

    # график
    plot_loss(all_logs)

if __name__ == '__main__':
    if '--test' in sys.argv:
        idx = sys.argv.index('--test')
        ckpt = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else os.path.join(MODELS_DIR, 'alan_final.pt')
        test(ckpt, 'cuda' if torch.cuda.is_available() else 'cpu')
    elif '--resume' in sys.argv:
        idx = sys.argv.index('--resume')
        ckpt = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else None
        start = int(sys.argv[sys.argv.index('--start-ep') + 1]) if '--start-ep' in sys.argv else 0
        main(resume_ckpt=ckpt, start_ep=start)
    else:
        main()
