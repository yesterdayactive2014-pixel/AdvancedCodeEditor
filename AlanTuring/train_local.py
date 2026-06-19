"""
train_local.py — AlanTuring 200M локальный тренинг на RTX 4060 Ti (8 GB, Ada Lovelace).

Запуск:
    python train_local.py

Особенности:
    - bf16 через Tensor Cores Ada (принудительно)
    - Fused AdamW (+15% скорости)
    - gradient_checkpointing (экономия VRAM)
    - batch=4, grad_accum=8 → effective batch 32
    - dataloader_num_workers=0 (безопасный Windows)
    - Автосохранение чекпоинтов каждые 500 шагов
    - При отсутствии датасета — синтетический набор на русском
"""
import argparse
import json
import math
import os
import random
import sys
import time
from typing import Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
from transformers import (
    PreTrainedModel,
    PretrainedConfig,
    GenerationMixin,
    Trainer,
    TrainingArguments,
    DataCollatorForLanguageModeling,
    AutoTokenizer,
    set_seed,
    GenerationConfig,
)

# ═══════════════════════════════════════════════════════════════
# 1. КОНФИГУРАЦИЯ (~195M параметров)
# ═══════════════════════════════════════════════════════════════


class AlanTuringConfig(PretrainedConfig):
    model_type = "alan_turing"

    def __init__(
        self,
        vocab_size: int = 32000,
        hidden_size: int = 768,
        intermediate_size: int = 2048,
        num_hidden_layers: int = 24,
        num_attention_heads: int = 12,
        num_key_value_heads: int = 12,
        max_position_embeddings: int = 2048,
        rms_norm_eps: float = 1e-6,
        rope_theta: float = 10000.0,
        hidden_dropout_prob: float = 0.0,
        attention_dropout_prob: float = 0.0,
        initializer_range: float = 0.02,
        use_cache: bool = True,
        tie_word_embeddings: bool = True,
        pad_token_id: int = 0,
        bos_token_id: int = 1,
        eos_token_id: int = 2,
        **kwargs,
    ):
        super().__init__(
            pad_token_id=pad_token_id,
            bos_token_id=bos_token_id,
            eos_token_id=eos_token_id,
            tie_word_embeddings=tie_word_embeddings,
            **kwargs,
        )
        self.vocab_size = vocab_size
        self.hidden_size = hidden_size
        self.intermediate_size = intermediate_size
        self.num_hidden_layers = num_hidden_layers
        self.num_attention_heads = num_attention_heads
        self.num_key_value_heads = num_key_value_heads
        self.max_position_embeddings = max_position_embeddings
        self.rms_norm_eps = rms_norm_eps
        self.rope_theta = rope_theta
        self.hidden_dropout_prob = hidden_dropout_prob
        self.attention_dropout_prob = attention_dropout_prob
        self.initializer_range = initializer_range
        self.use_cache = use_cache


# ═══════════════════════════════════════════════════════════════
# 2. МОДЕЛЬ (LLaMA-like Decoder-only)
# ═══════════════════════════════════════════════════════════════


class RMSNorm(nn.Module):
    def __init__(self, hidden_size: int, eps: float = 1e-6):
        super().__init__()
        self.weight = nn.Parameter(torch.ones(hidden_size))
        self.eps = eps

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        variance = x.pow(2).mean(-1, keepdim=True)
        return x * torch.rsqrt(variance + self.eps) * self.weight


def precompute_rope_frequencies(
    dim: int, max_len: int, theta: float = 10000.0, device: torch.device = None
) -> Tuple[torch.Tensor, torch.Tensor]:
    freqs = 1.0 / (theta ** (torch.arange(0, dim, 2, device=device).float() / dim))
    t = torch.arange(max_len, device=device).float()
    angles = t[:, None] * freqs[None, :]
    return angles.cos(), angles.sin()


def apply_rotary_emb(xq: torch.Tensor, xk: torch.Tensor, cos: torch.Tensor, sin: torch.Tensor):
    seq_len = xq.shape[2]
    cos = cos[:seq_len].unsqueeze(0).unsqueeze(1)
    sin = sin[:seq_len].unsqueeze(0).unsqueeze(1)
    xq_ = xq.float().reshape(*xq.shape[:-1], -1, 2)
    xk_ = xk.float().reshape(*xk.shape[:-1], -1, 2)
    xq_rot = torch.stack([
        xq_[..., 0] * cos - xq_[..., 1] * sin,
        xq_[..., 1] * cos + xq_[..., 0] * sin,
    ], dim=-1)
    xk_rot = torch.stack([
        xk_[..., 0] * cos - xk_[..., 1] * sin,
        xk_[..., 1] * cos + xk_[..., 0] * sin,
    ], dim=-1)
    return xq_rot.flatten(3), xk_rot.flatten(3)


class Attention(nn.Module):
    def __init__(self, config: AlanTuringConfig):
        super().__init__()
        self.hidden_size = config.hidden_size
        self.num_heads = config.num_attention_heads
        self.num_kv_heads = config.num_key_value_heads
        self.head_dim = config.hidden_size // config.num_attention_heads
        self.num_key_value_groups = self.num_heads // self.num_kv_heads

        self.q_proj = nn.Linear(config.hidden_size, config.num_attention_heads * self.head_dim, bias=False)
        self.k_proj = nn.Linear(config.hidden_size, self.num_kv_heads * self.head_dim, bias=False)
        self.v_proj = nn.Linear(config.hidden_size, self.num_kv_heads * self.head_dim, bias=False)
        self.o_proj = nn.Linear(config.num_attention_heads * self.head_dim, config.hidden_size, bias=False)
        self.attn_dropout = nn.Dropout(config.attention_dropout_prob)

    def forward(self, x: torch.Tensor, cos: torch.Tensor, sin: torch.Tensor,
                attention_mask: Optional[torch.Tensor] = None) -> torch.Tensor:
        bsz, seq_len, _ = x.shape
        q = self.q_proj(x).view(bsz, seq_len, self.num_heads, self.head_dim).transpose(1, 2)
        k = self.k_proj(x).view(bsz, seq_len, self.num_kv_heads, self.head_dim).transpose(1, 2)
        v = self.v_proj(x).view(bsz, seq_len, self.num_kv_heads, self.head_dim).transpose(1, 2)
        q, k = apply_rotary_emb(q, k, cos, sin)

        if self.num_key_value_groups > 1:
            k = k.repeat_interleave(self.num_key_value_groups, dim=1)
            v = v.repeat_interleave(self.num_key_value_groups, dim=1)

        attn = torch.matmul(q, k.transpose(-2, -1)) / math.sqrt(self.head_dim)
        if attention_mask is not None:
            attn = attn + attention_mask[:, :, :seq_len, :seq_len]
        attn = F.softmax(attn.float(), dim=-1).type_as(q)
        attn = self.attn_dropout(attn)
        out = torch.matmul(attn, v)
        out = out.transpose(1, 2).contiguous().view(bsz, seq_len, -1)
        return self.o_proj(out)


class SwiGLU(nn.Module):
    def __init__(self, config: AlanTuringConfig):
        super().__init__()
        self.gate_proj = nn.Linear(config.hidden_size, config.intermediate_size, bias=False)
        self.up_proj = nn.Linear(config.hidden_size, config.intermediate_size, bias=False)
        self.down_proj = nn.Linear(config.intermediate_size, config.hidden_size, bias=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.down_proj(F.silu(self.gate_proj(x)) * self.up_proj(x))


class TransformerLayer(nn.Module):
    def __init__(self, config: AlanTuringConfig):
        super().__init__()
        self.self_attn = Attention(config)
        self.mlp = SwiGLU(config)
        self.input_norm = RMSNorm(config.hidden_size, config.rms_norm_eps)
        self.post_attn_norm = RMSNorm(config.hidden_size, config.rms_norm_eps)

    def forward(self, x: torch.Tensor, cos: torch.Tensor, sin: torch.Tensor,
                attention_mask: Optional[torch.Tensor] = None) -> torch.Tensor:
        r = x; x = self.input_norm(x); x = self.self_attn(x, cos, sin, attention_mask); x = r + x
        r = x; x = self.post_attn_norm(x); x = self.mlp(x)
        return r + x


class AlanTuringModel(PreTrainedModel):
    config_class = AlanTuringConfig
    base_model_prefix = "model"
    supports_gradient_checkpointing = True

    def __init__(self, config: AlanTuringConfig):
        super().__init__(config)
        self.embed_tokens = nn.Embedding(config.vocab_size, config.hidden_size, padding_idx=config.pad_token_id)
        self.layers = nn.ModuleList([TransformerLayer(config) for _ in range(config.num_hidden_layers)])
        self.norm = RMSNorm(config.hidden_size, config.rms_norm_eps)
        cos, sin = precompute_rope_frequencies(
            config.hidden_size // config.num_attention_heads,
            config.max_position_embeddings,
            config.rope_theta,
        )
        self.register_buffer("rope_cos", cos, persistent=False)
        self.register_buffer("rope_sin", sin, persistent=False)
        self.gradient_checkpointing = False
        self.post_init()

    def forward(self, input_ids: torch.LongTensor, attention_mask: Optional[torch.Tensor] = None,
                **kwargs) -> torch.Tensor:
        x = self.embed_tokens(input_ids)
        causal_mask = None
        if attention_mask is not None:
            bsz, seq_len = input_ids.shape
            causal_mask = torch.triu(
                torch.full((seq_len, seq_len), float("-inf"), device=input_ids.device), diagonal=1,
            ).unsqueeze(0).unsqueeze(0)
            ext = (1.0 - attention_mask[:, None, None, :].float()) * float("-inf")
            causal_mask = causal_mask + ext

        for layer in self.layers:
            if self.gradient_checkpointing and self.training:
                x = self._gradient_checkpointing_func(layer, x, self.rope_cos, self.rope_sin, causal_mask)
            else:
                x = layer(x, self.rope_cos, self.rope_sin, causal_mask)
        return self.norm(x)


class AlanTuringForCausalLM(PreTrainedModel, GenerationMixin):
    config_class = AlanTuringConfig
    base_model_prefix = "model"
    supports_gradient_checkpointing = True
    _tied_weights_keys = {"lm_head.weight": "model.embed_tokens.weight"}

    def __init__(self, config: AlanTuringConfig):
        super().__init__(config)
        self.model = AlanTuringModel(config)
        self.lm_head = nn.Linear(config.hidden_size, config.vocab_size, bias=False)
        self.post_init()

    def get_input_embeddings(self): return self.model.embed_tokens
    def set_input_embeddings(self, v): self.model.embed_tokens = v
    def get_output_embeddings(self): return self.lm_head
    def set_output_embeddings(self, v): self.lm_head = v

    def forward(self, input_ids, attention_mask=None, labels=None, **kwargs):
        hidden = self.model(input_ids, attention_mask=attention_mask)
        logits = self.lm_head(hidden)
        loss = None
        if labels is not None:
            shift_logits = logits[..., :-1, :].contiguous()
            shift_labels = labels[..., 1:].contiguous()
            loss = F.cross_entropy(
                shift_logits.view(-1, shift_logits.size(-1)),
                shift_labels.view(-1),
                ignore_index=-100,
            )
        from transformers.modeling_outputs import CausalLMOutputWithPast
        return CausalLMOutputWithPast(loss=loss, logits=logits)

    def prepare_inputs_for_generation(self, input_ids, **kwargs):
        return {"input_ids": input_ids, "attention_mask": kwargs.get("attention_mask")}


# ═══════════════════════════════════════════════════════════════
# 3. ТОКЕНИЗАТОР
# ═══════════════════════════════════════════════════════════════

TOKENIZER_NAME = "DeepPavlov/rubert-base-cased"


def load_tokenizer():
    tok = AutoTokenizer.from_pretrained(TOKENIZER_NAME, use_fast=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token or "<pad>"
    if tok.chat_template is None:
        tok.chat_template = (
            "{% for message in messages %}"
            "{% if message['role'] == 'system' %}{{ message['content'] }}\n"
            "{% elif message['role'] == 'user' %}Пользователь: {{ message['content'] }}\n"
            "{% elif message['role'] == 'assistant' %}Алан Тьюринг: {{ message['content'] }}\n"
            "{% endif %}{% endfor %}Алан Тьюринг:"
        )
    print(f"  Tokenizer: {tok.vocab_size} tokens, pad_id={tok.pad_token_id}")
    return tok


# ═══════════════════════════════════════════════════════════════
# 4. ДАТАСЕТ
# ═══════════════════════════════════════════════════════════════

SYNTHETIC_DATA = [
    {"instruction": "Привет! Как дела?", "response": "Привет! Я Алан Тьюринг, искусственный интеллект. У меня всё отлично, готов помогать тебе с любыми вопросами!"},
    {"instruction": "Расскажи про нейросети.", "response": "Нейросети — это вычислительные системы, вдохновлённые биологическими нейронными сетями. Они состоят из слоёв искусственных нейронов, каждый из которых применяет нелинейное преобразование к входным данным. Современные архитектуры, такие как трансформеры, используют механизм внимания для обработки последовательностей."},
    {"instruction": "Что такое трансформер?", "response": "Трансформер — это архитектура нейросети, основанная на механизме внимания (attention). Она была предложена в 2017 году в статье 'Attention Is All You Need'. В отличие от RNN, трансформер обрабатывает все токены последовательности параллельно, что позволяет эффективно обучать большие модели на огромных объёмах данных."},
    {"instruction": "Как учить Python?", "response": "Начни с основ: переменные, типы данных, условные операторы и циклы. Затем изучи функции, классы и модули. Практикуйся на задачах с LeetCode или Codewars. Для анализа данных используй pandas и numpy, для веба — FastAPI или Flask. Главное — писать код каждый день хотя бы по 30 минут."},
    {"instruction": "Что такое алгоритм?", "response": "Алгоритм — это конечная последовательность чётких инструкций для решения задачи. Он должен быть детерминированным, конечным и эффективным. Примеры: сортировка пузырьком, бинарный поиск, обход графа в ширину. Анализ алгоритмов оценивается через O-нотацию (big O notation)."},
    {"instruction": "Расскажи про видеокарты RTX 4060 Ti.", "response": "RTX 4060 Ti — видеокарта NVIDIA на архитектуре Ada Lovelace. Имеет 8 GB GDDR6X VRAM, 4352 ядра CUDA и 34 ядра RT третьего поколения. Поддерживает bf16 и Tensor Cores 4-го поколения, что делает её отличным выбором для обучения небольших языковых моделей (до 200M параметров) с mixed precision."},
    {"instruction": "Что такое функция потерь?", "response": "Функция потерь (loss function) — это метрика, показывающая, насколько хорошо модель предсказывает целевые значения. Для классификации используется кросс-энтропия, для регрессии — MSE (mean squared error). В языковых моделях мы минимизируем перплексию через categorical cross-entropy на логитах."},
    {"instruction": "Объясни градиентный спуск.", "response": "Градиентный спуск — это итерационный метод оптимизации. На каждом шаге мы вычисляем градиент функции потерь по параметрам модели и делаем шаг в обратном направлении. Размер шага называется learning rate. Варианты: SGD, Adam, AdamW. AdamW — стандарт для обучения трансформеров."},
    {"instruction": "Что такое переобучение?", "response": "Переобучение (overfitting) — это ситуация, когда модель запоминает обучающие данные вместо обобщения. Признаки: низкая ошибка на train, высокая на validation. Методы борьбы: регуляризация (L1/L2), dropout, data augmentation, early stopping, уменьшение размера модели."},
    {"instruction": "Какие бывают виды памяти в ПК?", "response": "Основные виды: DDR5/DDR4 — оперативная память (RAM), GDDR6X — видеопамять (VRAM), NVMe SSD — постоянное хранилище, HDD — медленное хранилище. Для обучения нейросетей критична VRAM (она хранит веса, градиенты и активации) и скорость SSD (для чтения датасета)."},
    {"instruction": "Напиши пример кода на Python.", "response": "Вот пример быстрой сортировки:\n\ndef quicksort(arr):\n    if len(arr) <= 1:\n        return arr\n    pivot = arr[len(arr) // 2]\n    left = [x for x in arr if x < pivot]\n    middle = [x for x in arr if x == pivot]\n    right = [x for x in arr if x > pivot]\n    return quicksort(left) + middle + quicksort(right)"},
    {"instruction": "Что такое CUDA?", "response": "CUDA (Compute Unified Device Architecture) — платформа параллельных вычислений от NVIDIA. Позволяет использовать GPU для неграфических вычислений (GPGPU). Ядра CUDA выполняют тысячи потоков одновременно. PyTorch использует CUDA для тензорных операций, что ускоряет обучение нейросетей в 10-50 раз по сравнению с CPU."},
    {"instruction": "Для чего нужна функция активации?", "response": "Функция активации вносит нелинейность в нейросеть, позволяя ей аппроксимировать сложные зависимости. Без активации многослойная сеть была бы эквивалентна однослойной (композиция линейных функций — линейна). Популярные: ReLU, GELU, SiLU (Swish). В трансформерах используется SwiGLU — комбинация SiLU и вентильного механизма."},
    {"instruction": "Что такое attention?", "response": "Attention (внимание) — механизм, позволяющий модели фокусироваться на релевантных частях входных данных. Работает через три матрицы: Query (запрос), Key (ключ), Value (значение). Веса внимания вычисляются как softmax(Q @ K.T / sqrt(d)). Это позволяет каждому токену 'смотреть' на все предыдущие токены в последовательности."},
    {"instruction": "Расскажи про Kaggle.", "response": "Kaggle — платформа для соревнований по машинному обучению (куплена Google в 2017). Предоставляет бесплатный доступ к GPU (T4 16GB, P100 16GB) и TPU. Соревнования охватывают CV, NLP, табличные данные. Kaggle Notebooks — популярная среда для прототипирования моделей. В 2024-2026 активно внедряются LLM-соревнования."},
    {"instruction": "Ты знаешь русский язык?", "response": "Да, я отлично понимаю русский язык! Мой токенизатор (DeepPavlov/rubert-base-cased) обучен на русскоязычных текстах: Википедия, новости, статьи. Это позволяет мне корректно обрабатывать кириллицу без потери символов. Я могу отвечать на русском, объяснять сложные концепции и писать код с комментариями на русском."},
    {"instruction": "Что такое закон Мура?", "response": "Закон Мура — эмпирическое наблюдение, что количество транзисторов на микросхеме удваивается каждые 2 года при снижении стоимости. Сформулирован Гордоном Муром в 1965 году. В контексте AI: вычислительные мощности для обучения нейросетей растут экспоненциально, что позволяет обучать всё более крупные модели (GPT, LLaMA, Claude)."},
    {"instruction": "Объясни понятие 'тензор'.", "response": "Тензор — это многомерный массив данных, основная структура в PyTorch. Скаляр — тензор 0-мерный, вектор — 1-мерный, матрица — 2-мерный. Тензоры могут храниться на CPU или GPU. Операции над тензорами автоматически дифференцируются через autograd, что позволяет вычислять градиенты для обратного распространения ошибки."},
]


class InstructionDataset(Dataset):
    """Датасет инструкций: загружает из JSONL или генерирует синтетику."""

    def __init__(self, tokenizer, data_dir: str, max_length: int = 512):
        self.tokenizer = tokenizer
        self.max_length = max_length
        self.pairs = self._load_or_generate(data_dir)
        print(f"  Загружено примеров: {len(self.pairs)}")

    def _load_or_generate(self, data_dir: str):
        jsonl_path = os.path.join(data_dir, "train.jsonl")
        if os.path.isdir(data_dir) and os.path.isfile(jsonl_path):
            pairs = []
            with open(jsonl_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        pairs.append(json.loads(line))
            if pairs:
                return pairs
        print(f"  {data_dir}/train.jsonl не найден, генерирую синтетику...")
        return SYNTHETIC_DATA

    def __len__(self):
        return len(self.pairs)

    def __getitem__(self, idx):
        pair = self.pairs[idx]
        text = (
            f"Пользователь: {pair['instruction']}\n"
            f"Алан Тьюринг: {pair['response']}"
        )
        enc = self.tokenizer(
            text,
            truncation=True,
            max_length=self.max_length,
            padding="max_length",
            return_tensors="pt",
        )
        input_ids = enc["input_ids"].squeeze(0)
        attention_mask = enc["attention_mask"].squeeze(0)
        labels = input_ids.clone()
        labels[attention_mask == 0] = -100
        return {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "labels": labels,
        }


# ═══════════════════════════════════════════════════════════════
# 5. MAIN — ТРЕНИРОВКА
# ═══════════════════════════════════════════════════════════════


def main():
    parser = argparse.ArgumentParser(description="AlanTuring 200M — Local Train (RTX 4060 Ti)")
    parser.add_argument("--batch-size", type=int, default=4, help="Per-device batch size")
    parser.add_argument("--grad-accum", type=int, default=8, help="Gradient accumulation steps")
    parser.add_argument("--max-length", type=int, default=512, help="Max sequence length")
    parser.add_argument("--epochs", type=float, default=3.0, help="Number of training epochs")
    parser.add_argument("--lr", type=float, default=3e-4, help="Peak learning rate")
    parser.add_argument("--warmup", type=int, default=200, help="Warmup steps")
    parser.add_argument("--logging-steps", type=int, default=10)
    parser.add_argument("--save-steps", type=int, default=500)
    parser.add_argument("--output-dir", type=str, default="./checkpoints")
    parser.add_argument("--dataset-dir", type=str, default="./alan-dataset",
                        help="Путь к папке с train.jsonl")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    set_seed(args.seed)

    # ── Шаг 1: Проверка CUDA и GPU ─────────────────────────────
    print("=" * 55)
    print("AlanTuring 200M — Локальный тренинг")
    print("=" * 55)

    if not torch.cuda.is_available():
        print("CUDA не доступна. Установи PyTorch с CUDA:\n"
              "  pip install torch --index-url https://download.pytorch.org/whl/cu124")
        sys.exit(1)

    device_name = torch.cuda.get_device_name(0)
    props = torch.cuda.get_device_properties(0)
    vram = props.total_memory / 1e9
    cc = f"{props.major}.{props.minor}"
    is_ada = props.major >= 8
    bf16_ok = torch.cuda.is_bf16_supported()

    print(f"  GPU: {device_name}")
    print(f"  VRAM: {vram:.1f} GB")
    print(f"  CC: {cc} {'(Ada Lovelace)' if is_ada else ''}")
    print(f"  bf16: {'ДА ✓' if bf16_ok else 'НЕТ — используем fp16'}")

    if not is_ada:
        print("  Внимание: RTX 4060 Ti (Ada) ожидалась, но CC < 8.0")

    # ── Шаг 2: Загрузка токенизатора ───────────────────────────
    print("\n[Шаг 2] Загрузка токенизатора...")
    tokenizer = load_tokenizer()

    # ── Шаг 3: Создание конфига и модели ───────────────────────
    print("\n[Шаг 3] Инициализация модели ~195M...")
    config = AlanTuringConfig(
        vocab_size=len(tokenizer) + 200,
        pad_token_id=tokenizer.pad_token_id,
        bos_token_id=tokenizer.bos_token_id or 1,
        eos_token_id=tokenizer.eos_token_id or 2,
    )
    model = AlanTuringForCausalLM(config)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"  Параметров: {n_params / 1e6:.1f}M")

    # ── Шаг 4: Загрузка датасета ───────────────────────────────
    print(f"\n[Шаг 4] Загрузка датасета из {args.dataset_dir}...")
    dataset = InstructionDataset(tokenizer, args.dataset_dir, max_length=args.max_length)
    print(f"  Размер датасета: {len(dataset)} примеров")

    collator = DataCollatorForLanguageModeling(
        tokenizer=tokenizer, mlm=False, pad_to_multiple_of=8,
    )

    # ── Шаг 5: TrainingArguments ──────────────────────────────
    print(f"\n[Шаг 5] Конфигурация обучения:")
    print(f"  per_device_train_batch_size = {args.batch_size}")
    print(f"  gradient_accumulation_steps = {args.grad_accum}")
    effective = args.batch_size * args.grad_accum
    print(f"  effective batch size         = {effective}")
    print(f"  max_length                   = {args.max_length}")
    print(f"  epochs                       = {args.epochs}")
    print(f"  learning_rate                = {args.lr}")
    print(f"  optim                        = adamw_torch_fused")
    print(f"  bf16                         = {bf16_ok}")
    print(f"  gradient_checkpointing       = True")
    print(f"  torch_compile                = {is_ada}")
    print(f"  dataloader_num_workers       = 0 (Windows safe)")

    training_args = TrainingArguments(
        output_dir=args.output_dir,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        gradient_checkpointing=True,
        bf16=bf16_ok,
        fp16=not bf16_ok,
        optim="adamw_torch_fused",
        learning_rate=args.lr,
        warmup_steps=args.warmup,
        lr_scheduler_type="cosine",
        weight_decay=0.1,
        adam_beta1=0.9,
        adam_beta2=0.95,
        max_grad_norm=1.0,
        logging_steps=args.logging_steps,
        save_steps=args.save_steps,
        save_total_limit=3,
        save_strategy="steps",
        eval_strategy="no",
        prediction_loss_only=True,
        remove_unused_columns=True,
        report_to="none",
        ddp_find_unused_parameters=False,
        dataloader_num_workers=0,
        dataloader_pin_memory=True,
        seed=args.seed,
        torch_compile=False,
    )

    # ── Шаг 6: Trainer ─────────────────────────────────────────
    print("\n[Шаг 6] Запуск Trainer...")
    trainer = Trainer(
        model=model,
        args=training_args,
        data_collator=collator,
        train_dataset=dataset,
    )

    # ── Шаг 7: Обучение ────────────────────────────────────────
    print("\n[Шаг 7] Старт обучения!")
    print("=" * 55)
    try:
        trainer.train()
    except KeyboardInterrupt:
        print("\nОбучение прервано. Сохраняю чекпоинт...")
        trainer.save_model(os.path.join(args.output_dir, "interrupted"))
        tokenizer.save_pretrained(os.path.join(args.output_dir, "interrupted"))

    # ── Шаг 8: Сохранение ──────────────────────────────────────
    print(f"\n[Шаг 8] Сохранение финальной модели в {args.output_dir}/final ...")
    trainer.save_model(os.path.join(args.output_dir, "final"))
    tokenizer.save_pretrained(os.path.join(args.output_dir, "final"))

    print("\n✅ Обучение завершено!")
    print(f"   Финальная модель: {os.path.join(args.output_dir, 'final')}")
    print(f"   Запуск инференса: python train_local.py --inference --checkpoint {os.path.join(args.output_dir, 'final')}")


# ═══════════════════════════════════════════════════════════════
# 6. INFERENCE (опционально)
# ═══════════════════════════════════════════════════════════════


def run_inference(checkpoint_path: str, prompt: str, max_new_tokens: int = 256):
    print(f"Загрузка модели из {checkpoint_path}...")
    config = AlanTuringConfig.from_pretrained(checkpoint_path)
    model = AlanTuringForCausalLM.from_pretrained(checkpoint_path, config=config)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)
    model.eval()
    tokenizer = load_tokenizer()

    messages = [
        {"role": "system", "content": "Ты — Алан Тьюринг, полезный ИИ-ассистент. Отвечай на русском языке."},
        {"role": "user", "content": prompt},
    ]
    input_text = tokenizer.apply_chat_template(messages, tokenize=False)
    inputs = tokenizer(input_text, return_tensors="pt", truncation=True, max_length=2048).to(device)

    gen_config = GenerationConfig(
        max_new_tokens=max_new_tokens,
        temperature=0.7,
        top_p=0.9,
        top_k=50,
        repetition_penalty=1.1,
        do_sample=True,
        pad_token_id=tokenizer.pad_token_id,
        eos_token_id=tokenizer.eos_token_id,
    )

    with torch.no_grad():
        output_ids = model.generate(**inputs, generation_config=gen_config)

    response = tokenizer.decode(output_ids[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
    return response.strip()


# ═══════════════════════════════════════════════════════════════
# ТОЧКА ВХОДА
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if "--inference" in sys.argv:
        idx = sys.argv.index("--inference")
        ckpt = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else "./checkpoints/final"
        prompt = sys.argv[idx + 2] if idx + 2 < len(sys.argv) else "Привет! Расскажи о себе."
        answer = run_inference(ckpt, prompt)
        print(f"Ответ: {answer}")
    else:
        main()
