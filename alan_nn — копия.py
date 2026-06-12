# alan_nn.py — Alan Neural Engine v2 (трансформер + мультиязычность + датасет)
# ~530 строк. Free (CPU) / Premium (GPU). Обучение на Google Cloud.

import json, math, os, sys, re, random
from pathlib import Path
from typing import Optional, List, Tuple

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    HAVE_TORCH = True
except ImportError:
    HAVE_TORCH = False

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit,
    QPushButton, QLabel, QComboBox, QProgressBar, QApplication, QDockWidget
)


# ═══════════════════════════════════════════════════════════════════
#  1. КОНФИГУРАЦИЯ
# ═══════════════════════════════════════════════════════════════════

class AlanConfig:
    vocab_size = 256
    embed_dim = 256
    num_heads = 8
    num_layers = 6
    max_seq_len = 512
    ff_mult = 4
    dropout = 0.1
    device = 'cpu'
    premium = False


# ═══════════════════════════════════════════════════════════════════
#  2. БАЙТОВЫЙ ТОКЕНИЗАТОР (ВСЕ ЯЗЫКИ ЧЕРЕЗ UTF-8)
# ═══════════════════════════════════════════════════════════════════

class ByteTokenizer:
    def encode(self, text: str) -> list:
        return list(text.encode('utf-8'))
    def decode(self, ids: list) -> str:
        return bytes([b for b in ids if b < 256]).decode('utf-8', errors='replace')


# ═══════════════════════════════════════════════════════════════════
#  3. ДЕТЕКТОР ЯЗЫКА (HEURISTIC)
# ═══════════════════════════════════════════════════════════════════

LANG_RANGES = {
    'ru': [(0x0400, 0x04FF), (0x0500, 0x052F)],  # кириллица
    'zh': [(0x4E00, 0x9FFF), (0x3400, 0x4DBF)],  # китайский
    'ja': [(0x3040, 0x309F), (0x30A0, 0x30FF), (0x4E00, 0x9FFF)],  # японский
    'ko': [(0xAC00, 0xD7AF), (0x1100, 0x11FF)],  # корейский
    'ar': [(0x0600, 0x06FF)],                     # арабский
    'de': [], 'fr': [], 'es': [], 'pt': [], 'it': [],  # латиница
}

def detect_lang(text: str) -> str:
    """Определяет язык текста. Возвращает 'en', 'ru', 'zh', etc."""
    if not text:
        return 'en'
    # Проверяем первые 50 символов (достаточно для определения)
    sample = text[:50]
    scores = {lang: 0 for lang in LANG_RANGES}
    for ch in sample:
        cp = ord(ch)
        for lang, ranges in LANG_RANGES.items():
            for lo, hi in ranges:
                if lo <= cp <= hi:
                    scores[lang] = scores.get(lang, 0) + 1
                    break
    if not scores or max(scores.values()) == 0:
        return 'en'
    return max(scores, key=scores.get)


# ═══════════════════════════════════════════════════════════════════
#  4. МУЛЬТИЯЗЫЧНЫЙ ПРОМПТ-МЕНЕДЖЕР
# ═══════════════════════════════════════════════════════════════════

SYSTEM_PROMPTS = {
    'en': (
        "You are Alan, an AI assistant built into the Advanced Code Editor. "
        "Stack: PyQt6 + QWebEngine + QWebChannel + OrionScript. "
        "Be polite, concise, and helpful. When asked for code — provide only code. "
        "When asked a question — explain briefly. Stay in the same language as the user."
    ),
    'ru': (
        "Ты — Alan, ИИ-ассистент встроенный в Advanced Code Editor. "
        "Стек: PyQt6 + QWebEngine + QWebChannel + OrionScript. "
        "Будь вежливым, кратким и полезным. Если просят код — давай только код. "
        "Если задают вопрос — объясняй коротко. Отвечай на том же языке, что и пользователь."
    ),
    'zh': (
        "你是Alan，内置于Advanced Code Editor中的AI助手。"
        "技术栈: PyQt6 + QWebEngine + QWebChannel + OrionScript。"
        "请礼貌、简洁、有帮助。如果要求代码——只提供代码。"
        "如果问问题——简短解释。用与用户相同的语言回答。"
    ),
    'ja': (
        "あなたはAlanです。Advanced Code Editorに組み込まれたAIアシスタントです。"
        "スタック: PyQt6 + QWebEngine + QWebChannel + OrionScript。"
        "丁寧で簡潔に、役立つように振る舞ってください。コードを求められたらコードのみを。"
        "質問には簡潔に説明。ユーザーと同じ言語で応答してください。"
    ),
    'ko': (
        "당신은 Advanced Code Editor에 내장된 AI 어시스턴트 Alan입니다."
        "스택: PyQt6 + QWebEngine + QWebChannel + OrionScript. "
        "예의 바르고 간결하며 도움이 되도록 행동하세요. 코드를 요청받으면 코드만 제공하세요. "
        "질문을 받으면 짧게 설명하세요. 사용자와 동일한 언어로 응답하세요."
    ),
    'de': (
        "Du bist Alan, ein KI-Assistent im Advanced Code Editor. "
        "Stack: PyQt6 + QWebEngine + QWebChannel + OrionScript. "
        "Sei höflich, präzise und hilfreich. Wenn Code gewünscht wird — nur Code. "
        "Bei Fragen — kurz erklären. Antworte in derselben Sprache wie der Benutzer."
    ),
    'fr': (
        "Tu es Alan, un assistant IA intégré à l'Advanced Code Editor. "
        "Stack: PyQt6 + QWebEngine + QWebChannel + OrionScript. "
        "Sois poli, concis et utile. Quand on te demande du code — fournis seulement le code. "
        "Quand on te pose une question — explique brièvement. Réponds dans la même langue que l'utilisateur."
    ),
    'es': (
        "Eres Alan, un asistente de IA integrado en Advanced Code Editor. "
        "Stack: PyQt6 + QWebEngine + QWebChannel + OrionScript. "
        "Sé educado, conciso y útil. Cuando te pidan código — da solo código. "
        "Cuando pregunten — explica brevemente. Responde en el mismo idioma del usuario."
    ),
    'ar': (
        "أنت Alan، مساعد ذكاء اصطناعي مدمج في Advanced Code Editor. "
        "التقنيات: PyQt6 + QWebEngine + QWebChannel + OrionScript. "
        "كن مهذبًا وموجزًا ومفيدًا. عندما يُطلب منك كود — قدم كودًا فقط. "
        "عندما يُطرح عليك سؤال — اشرح بإيجاز. أجب بنفس لغة المستخدم."
    ),
}

GREETINGS = {
    'en': ["Hello! I'm Alan. How can I help?", "Hi there! Ask me anything about code.", "Hey! Ready to help."],
    'ru': ["Привет! Я Alan. Чем помочь?", "Здравствуй! Спрашивай что угодно о коде.", "Привет! Готов помочь."],
    'zh': ["你好！我是Alan。有什么可以帮助的吗？", "嗨！请问有什么代码问题？"],
    'ja': ["こんにちは！Alanです。何かお手伝いしましょうか？", "やあ！コードについて何でも聞いてください。"],
    'ko': ["안녕하세요! Alan입니다. 무엇을 도와드릴까요?", "안녕! 코드에 대해 뭐든 물어봐."],
    'de': ["Hallo! Ich bin Alan. Wie kann ich helfen?", "Hi! Frag mich alles über Code."],
    'fr': ["Bonjour ! Je suis Alan. Comment puis-je aider ?", "Salut ! Demande-moi tout sur le code."],
    'es': ["¡Hola! Soy Alan. ¿Cómo puedo ayudar?", "¡Hola! Pregúntame cualquier cosa sobre código."],
    'ar': ["مرحبًا! أنا Alan. كيف يمكنني المساعدة؟", "أهلًا! اسألني أي شيء عن الكود."],
}

class PromptManager:
    def __init__(self, max_history=6):
        self.history: List[Tuple[str, str]] = []  # (role, text)
        self.max_history = max_history

    def add(self, role: str, text: str):
        self.history.append((role, text))
        if len(self.history) > self.max_history:
            self.history.pop(0)

    def build(self, query: str) -> Tuple[str, str]:
        lang = detect_lang(query)
        system = SYSTEM_PROMPTS.get(lang, SYSTEM_PROMPTS['en'])
        parts = [f"<s>[SYSTEM] {system}[/SYSTEM]"]
        for role, text in self.history[-self.max_history:]:
            tag = 'USER' if role == 'user' else 'ALAN'
            parts.append(f"<{tag}> {text} </{tag}>")
        parts.append(f"<USER> {query} </USER>")
        parts.append("<ALAN>")
        return '\n'.join(parts), lang

    def extract_answer(self, raw: str, lang: str) -> str:
        for tag in ['</ALAN>', '</s>', '<USER>']:
            if tag in raw:
                raw = raw.split(tag, 1)[0]
        if '<ALAN>' in raw:
            raw = raw.split('<ALAN>', 1)[-1]
        return raw.strip()

    def greeting(self, lang: str) -> str:
        g = GREETINGS.get(lang, GREETINGS['en'])
        return random.choice(g)


# ═══════════════════════════════════════════════════════════════════
#  5. ДАТАСЕТ-БИЛДЕР (СКАНИРУЕТ ФАЙЛЫ ПРОЕКТА)
# ═══════════════════════════════════════════════════════════════════

class DatasetBuilder:
    """Собирает датасет для обучения из кода проекта: классы, функции, строки."""

    Q_TEMPLATES_RU = [
        "Что делает {name}?", "Объясни {name}", "Как работает {name}?",
        "Напиши пример {name}", "Для чего нужен {name}?"
    ]
    Q_TEMPLATES_EN = [
        "What does {name} do?", "Explain {name}", "How does {name} work?",
        "Write an example of {name}", "What is {name} for?"
    ]

    def __init__(self, project_dir: str = '.'):
        self.project_dir = Path(project_dir)

    def scan(self, lang='ru') -> List[dict]:
        """Сканирует .py, .html, .js файлы и генерирует пары вопрос-ответ."""
        samples = []
        templates = self.Q_TEMPLATES_RU if lang == 'ru' else self.Q_TEMPLATES_EN
        for ext in ['*.py', '*.html', '*.js']:
            for fp in self.project_dir.glob(ext):
                try:
                    text = fp.read_text('utf-8', errors='replace')
                except Exception:
                    continue
                # Извлекаем классы (class Foo:)
                for m in re.finditer(r'(?:^|\n)(?:class|def)\s+(\w+)', text):
                    name = m.group(1)
                    start = max(0, m.start() - 200)
                    end = min(len(text), m.end() + 600)
                    chunk = text[start:end].strip()
                    for tpl in templates:
                        q = tpl.format(name=name)
                        samples.append({"text": f"<s>[INST] {q} [/INST] {chunk[:512]} </s>"})
        return samples

    def build_json(self, lang='ru', output='dataset.json'):
        data = self.scan(lang)
        with open(output, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[Alan] Датасет сохранён: {output} ({len(data)} пар)")
        return data


# ═══════════════════════════════════════════════════════════════════
#  6. ТРАНСФОРМЕР (PyTorch)
# ═══════════════════════════════════════════════════════════════════

class RotaryEmbedding(nn.Module):
    def __init__(self, dim, max_len=512):
        super().__init__()
        inv_freq = 1.0 / (10000 ** (torch.arange(0, dim, 2, dtype=torch.float32) / dim))
        self.register_buffer('inv_freq', inv_freq, persistent=False)
    def forward(self, x, offset=0):
        bs, seq, h, d = x.shape
        t = torch.arange(offset, offset + seq, device=x.device, dtype=torch.float32)
        freqs = torch.einsum('i,j->ij', t, self.inv_freq)
        emb = torch.cat([freqs, freqs], dim=-1).view(1, seq, 1, d)
        return x * emb.cos() + self._rh(x) * emb.sin()
    def _rh(self, x):
        return torch.cat([-x[..., x.shape[-1]//2:], x[..., :x.shape[-1]//2]], dim=-1)

class Attention(nn.Module):
    def __init__(self, dim, heads):
        super().__init__()
        self.heads = heads
        self.hdim = dim // heads
        self.qkv = nn.Linear(dim, dim * 3, bias=False)
        self.proj = nn.Linear(dim, dim, bias=False)
        self.rope = RotaryEmbedding(self.hdim)
        self.drop = nn.Dropout(AlanConfig.dropout)
    def forward(self, x, mask=None):
        bs, seq, dim = x.shape
        qkv = self.qkv(x).reshape(bs, seq, 3, self.heads, self.hdim)
        q, k, v = qkv.unbind(2)
        q, k = self.rope(q), self.rope(k)
        attn = torch.einsum('bihd,bjhd->bhij', q, k) * (self.hdim ** -0.5)
        if mask is not None:
            attn = attn.masked_fill(mask[:,:,:seq,:seq]==0, float('-inf'))
        return self.proj(self.drop(F.softmax(attn, dim=-1)) @ v).reshape(bs, seq, dim)

class FF(nn.Module):
    def __init__(self, dim):
        super().__init__()
        ff = dim * AlanConfig.ff_mult
        self.net = nn.Sequential(nn.Linear(dim, ff), nn.GELU(), nn.Linear(ff, dim), nn.Dropout(AlanConfig.dropout))
    def forward(self, x): return self.net(x)

class Block(nn.Module):
    def __init__(self, dim, heads):
        super().__init__()
        self.attn = Attention(dim, heads)
        self.ff = FF(dim)
        self.n1 = nn.LayerNorm(dim)
        self.n2 = nn.LayerNorm(dim)
    def forward(self, x, mask=None):
        return self.ff(self.n2(x + self.attn(self.n1(x), mask))) + x

class AlanTransformer(nn.Module):
    """Decoder-only GPT-like. ~15M params."""
    def __init__(self):
        super().__init__()
        c = AlanConfig
        self.te = nn.Embedding(c.vocab_size, c.embed_dim)
        self.blocks = nn.ModuleList([Block(c.embed_dim, c.num_heads) for _ in range(c.num_layers)])
        self.norm = nn.LayerNorm(c.embed_dim)
        self.head = nn.Linear(c.embed_dim, c.vocab_size, bias=False)
        self.te.weight = self.head.weight
        self.drop = nn.Dropout(c.dropout)
        self.register_buffer('mask', torch.tril(torch.ones(1, 1, c.max_seq_len, c.max_seq_len)), persistent=False)
    def forward(self, x):
        x = self.drop(self.te(x))
        m = self.mask[:,:,:x.size(1),:x.size(1)]
        for b in self.blocks: x = b(x, m)
        return self.head(self.norm(x))


# ═══════════════════════════════════════════════════════════════════
#  7. ИНФЕРЕНС
# ═══════════════════════════════════════════════════════════════════

@torch.no_grad()
def generate(model, tokenizer, prompt: str, max_new=128, temp=0.8, top_k=40, top_p=0.9) -> str:
    model.eval()
    ids = torch.tensor([tokenizer.encode(prompt)], dtype=torch.long, device=next(model.parameters()).device)
    for _ in range(max_new):
        inp = ids[:, -AlanConfig.max_seq_len:]
        logits = model(inp)[0, -1, :] / max(temp, 0.01)
        if top_k > 0:
            vals, _ = torch.topk(logits, min(top_k, logits.size(-1)))
            logits[logits < vals[-1]] = float('-inf')
        if top_p < 1.0:
            sv, si = torch.sort(logits, descending=True)
            cs = torch.cumsum(F.softmax(sv, dim=-1), dim=-1)
            cut = cs > top_p
            if cut.any(): logits[si[cut.argmax().item()+1:]] = float('-inf')
        ids = torch.cat([ids, torch.multinomial(F.softmax(logits / logits.sum(), dim=-1), 1).unsqueeze(0)], dim=-1)
    return tokenizer.decode(ids[0].tolist())


# ═══════════════════════════════════════════════════════════════════
#  8. ДВИЖОК
# ═══════════════════════════════════════════════════════════════════

class AlanEngine(QObject):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    def __init__(self, weights_path=None):
        super().__init__()
        self.weights_path = weights_path
        self.tokenizer = ByteTokenizer()
        self.prompter = PromptManager()
        self.model = None
        self.premium = False
    def load(self, premium=False):
        self.premium = premium and torch.cuda.is_available()
        AlanConfig.device = 'cuda' if self.premium else 'cpu'
        AlanConfig.premium = self.premium
        self.model = AlanTransformer().to(AlanConfig.device)
        if self.weights_path and os.path.exists(self.weights_path):
            state = torch.load(self.weights_path, map_location=AlanConfig.device, weights_only=True)
            self.model.load_state_dict(state, strict=False)
        self.model.eval()
    def ask(self, query: str, max_new=128):
        prompt, lang = self.prompter.build(query)
        try:
            raw = generate(self.model, self.tokenizer, prompt, max_new)
            answer = self.prompter.extract_answer(raw, lang)
            self.prompter.add('user', query)
            self.prompter.add('alan', answer)
            self.finished.emit(answer)
        except Exception as e:
            self.error.emit(str(e))
    def greet(self) -> str:
        return self.prompter.greeting('ru' if self.prompter.history else 'en')


class AlanWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    def __init__(self, engine, query, max_new=128):
        super().__init__()
        self.engine = engine
        self.query = query
        self.max_new = max_new
    def run(self):
        try:
            prompt, lang = self.engine.prompter.build(self.query)
            raw = generate(self.engine.model, self.engine.tokenizer, prompt, self.max_new)
            answer = self.engine.prompter.extract_answer(raw, lang)
            self.engine.prompter.add('user', self.query)
            self.engine.prompter.add('alan', answer)
            self.finished.emit(answer)
        except Exception as e:
            self.error.emit(str(e))


# ═══════════════════════════════════════════════════════════════════
#  9. ПАНЕЛЬ ALAN
# ═══════════════════════════════════════════════════════════════════

STYLE = """
    QWidget#alanRoot { background:#1e1e1e; color:#d4d4d4; font-family:Consolas; font-size:12px; }
    QTextEdit { background:#252526; border:1px solid #3c3c3c; border-radius:4px; padding:6px; color:#d4d4d4; selection-background:#264f78; }
    QLineEdit { background:#252526; border:1px solid #3c3c3c; border-radius:4px; padding:6px; color:#d4d4d4; }
    QPushButton { background:#0e639c; color:#fff; border:none; border-radius:4px; padding:6px 14px; font-weight:bold; }
    QPushButton:hover { background:#1177bb; }
    QPushButton:disabled { background:#3c3c3c; color:#6e6e6e; }
    QPushButton#stopBtn { background:#c04040; } QPushButton#stopBtn:hover { background:#d05050; }
    QPushButton#buildBtn { background:#2d7d46; } QPushButton#buildBtn:hover { background:#3a9d5a; }
    QComboBox { background:#252526; border:1px solid #3c3c3c; border-radius:4px; padding:4px; color:#d4d4d4; }
    QProgressBar { background:#252526; border:1px solid #3c3c3c; border-radius:4px; height:4px; text-align:center; }
    QProgressBar::chunk { background:#0e639c; border-radius:4px; }
"""

class AlanPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('alanRoot')
        self.setStyleSheet(STYLE)
        self.engine = AlanEngine()
        self.worker = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        hdr = QHBoxLayout()
        title = QLabel("🤖 Alan AI")
        title.setStyleSheet("font-size:15px; font-weight:bold; color:#569cd6;")
        self.status = QLabel("🖥 Free (CPU)")
        self.status.setStyleSheet("font-size:11px; color:#858585;")
        hdr.addWidget(title); hdr.addStretch(); hdr.addWidget(self.status)
        layout.addLayout(hdr)

        mr = QHBoxLayout()
        mr.addWidget(QLabel("Режим:"))
        self.mode = QComboBox()
        self.mode.addItems(["Free (CPU)", "Premium (GPU)"])
        self.mode.currentIndexChanged.connect(self._on_mode)
        mr.addWidget(self.mode)
        self.build_btn = QPushButton("📦 Собрать датасет")
        self.build_btn.setObjectName("buildBtn")
        self.build_btn.clicked.connect(self._build_dataset)
        mr.addWidget(self.build_btn)
        layout.addLayout(mr)

        self.chat = QTextEdit()
        self.chat.setReadOnly(True)
        self.chat.setMinimumHeight(200)
        layout.addWidget(self.chat, stretch=1)

        self.progress = QProgressBar()
        self.progress.setMaximum(0)
        self.progress.hide()
        layout.addWidget(self.progress)

        row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("Спроси Alan… Ask Alan… 问Alan…")
        self.input.returnPressed.connect(self._ask)
        self.send = QPushButton("→"); self.send.setFixedWidth(36)
        self.send.clicked.connect(self._ask)
        self.stop = QPushButton("◼"); self.stop.setObjectName("stopBtn"); self.stop.setFixedWidth(36)
        self.stop.clicked.connect(self._stop)
        row.addWidget(self.input, stretch=1); row.addWidget(self.send); row.addWidget(self.stop)
        layout.addLayout(row)

        self._greet()

    def _greet(self):
        self.log(f"■ Alan загружен. Режим: CPU. Напиши вопрос на любом языке.", '#569cd6')

    def log(self, msg, color='#569cd6'):
        self.chat.append(f'<span style="color:{color};">{msg}</span>')

    def _on_mode(self, idx):
        premium = idx == 1
        if premium and not (HAVE_TORCH and torch.cuda.is_available()):
            self.log("■ CUDA не найден. Установи PyTorch с CUDA.", '#f85149')
            self.mode.setCurrentIndex(0)
            return
        self.engine.load(premium=premium)
        mode = "⚡ Premium (GPU)" if premium else "🖥 Free (CPU)"
        self.status.setText(mode)
        self.log(f"■ Переключено на {mode}")

    def _ask(self):
        text = self.input.text().strip()
        if not text: return
        self.input.clear()
        self.chat.append(f'<span style="color:#d4d4d4;"><b>Вы:</b> {text}</span>')
        self.progress.show(); self.send.setEnabled(False); self.input.setEnabled(False)
        self.worker = AlanWorker(self.engine, text, max_new=256)
        self.worker.finished.connect(self._on_result)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_result(self, text):
        self.progress.hide(); self.send.setEnabled(True); self.input.setEnabled(True)
        self.chat.append(f'<span style="color:#c586c0;"><b>Alan:</b></span> {text}')

    def _on_error(self, msg):
        self.progress.hide(); self.send.setEnabled(True); self.input.setEnabled(True)
        self.log(f"■ Ошибка: {msg}", '#f85149')

    def _stop(self):
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
            self.progress.hide(); self.send.setEnabled(True); self.input.setEnabled(True)

    def _build_dataset(self):
        self.log("■ Сборка датасета из файлов проекта…", '#569cd6')
        builder = DatasetBuilder(self._find_project_dir())
        data = builder.build_json()
        self.log(f"■ Датасет сохранён: dataset.json ({len(data)} пар)", '#569cd6')

    def _find_project_dir(self):
        p = __file__
        for _ in range(4):
            if any(os.path.exists(os.path.join(p, f)) for f in ['code_editor.py', 'index.html', 'transpile.py']):
                return p
            p = os.path.dirname(p)
        return '.'


# ═══════════════════════════════════════════════════════════════════
#  10. ГЕНЕРАТОР СКРИПТА ОБУЧЕНИЯ
# ═══════════════════════════════════════════════════════════════════

TRAIN_SCRIPT = '''# train_alan.py — Alan Training (Google Cloud GPU/TPU)
# python train_alan.py --data dataset.json --epochs 10 --device cuda
import json, sys, os, torch, torch.nn as nn
from torch.utils.data import Dataset, DataLoader
sys.path.insert(0, os.path.dirname(__file__))
from alan_nn import AlanTransformer, AlanConfig, ByteTokenizer

class CodeDataset(Dataset):
    def __init__(self, path, seq_len=128):
        self.tokenizer = ByteTokenizer()
        with open(path) as f: data = json.load(f)
        tokens = []
        for item in data:
            tokens.extend(self.tokenizer.encode(item['text'] + '\\n'))
            if len(tokens) > 2_000_000: break
        self.chunks = [tokens[i:i+seq_len+1] for i in range(0, len(tokens)-seq_len-1, seq_len//2)]
    def __len__(self): return len(self.chunks)
    def __getitem__(self, i):
        c = self.chunks[i]; return torch.tensor(c[:-1]), torch.tensor(c[1:])

def train():
    args = {sys.argv[i]: sys.argv[i+1] for i in range(1, len(sys.argv)-1, 2)}
    device = args.get('--device', 'cuda')
    model = AlanTransformer().to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=3e-4)
    ds = CodeDataset(args['--data']); dl = DataLoader(ds, batch_size=8, shuffle=True)
    for ep in range(int(args.get('--epochs', '10'))):
        loss_acc = 0
        for x, y in dl:
            x, y = x.to(device), y.to(device)
            loss = F.cross_entropy(model(x).reshape(-1, model(x).size(-1)), y.reshape(-1))
            opt.zero_grad(); loss.backward(); opt.step(); loss_acc += loss.item()
        print(f"Epoch {ep+1}: loss={loss_acc/len(dl):.4f}")
        torch.save(model.state_dict(), f'alan_ep{ep+1}.pt')
    from alan_nn import export_to_numpy
    export_to_numpy('alan_ep{}.pt'.format(int(args.get('--epochs','10'))), 'alan_model.npz')

if __name__ == '__main__': train()
'''

def write_train_script(path='train_alan.py'):
    with open(path, 'w', encoding='utf-8') as f: f.write(TRAIN_SCRIPT)

def export_to_numpy(pt_path, out_path):
    state = torch.load(pt_path, map_location='cpu', weights_only=True)
    np.savez(out_path, **{k: v.numpy() for k, v in state.items()})
    print(f'[Alan] {pt_path} -> {out_path}')


# ═══════════════════════════════════════════════════════════════════
#  ТЕСТ
# ═══════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    app = QApplication(sys.argv)
    w = AlanPanel()
    w.setWindowTitle("🤖 Alan AI v2 — Multilingual")
    w.resize(420, 640)
    w.show()
    app.exec()
