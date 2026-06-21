"""
Инференс Lynx 261M — запуск обученной модели и генерация ответов.

Поддерживает:
    - Загрузку чекпоинта (финального или промежуточного)
    - Диалоговый режим (интерактивный чат)
    - Однострочный режим (question → answer)
    - Правильное декодирование через tokenizer.decode (строка целиком, без кракозябр)

Примеры:
    python inference.py --checkpoint ./checkpoints/final --interactive
    python inference.py --checkpoint ./checkpoints/final --question "Что такое нейросеть?"
"""
import argparse
import os
import sys

import torch
from transformers import GenerationConfig

from config import LynxConfig
from model import LynxForCausalLM
from tokenizer import load_tokenizer


def parse_args():
    parser = argparse.ArgumentParser(description="Lynx Inference")
    parser.add_argument("--checkpoint", type=str, default="./checkpoints/final",
                        help="Path to model checkpoint")
    parser.add_argument("--interactive", action="store_true",
                        help="Run in interactive chat mode")
    parser.add_argument("--question", type=str, default=None,
                        help="Single question to answer")
    parser.add_argument("--max-new-tokens", type=int, default=256,
                        help="Maximum tokens to generate")
    parser.add_argument("--temperature", type=float, default=0.7,
                        help="Sampling temperature")
    parser.add_argument("--top-p", type=float, default=0.9,
                        help="Top-p nucleus sampling")
    parser.add_argument("--top-k", type=int, default=50,
                        help="Top-k sampling")
    parser.add_argument("--repetition-penalty", type=float, default=1.1,
                        help="Repetition penalty")
    return parser.parse_args()


def load_model(checkpoint_path: str, device: str):
    """Загрузить модель и токенизатор из чекпоинта."""
    if not os.path.exists(checkpoint_path):
        print(f"Ошибка: чекпоинт {checkpoint_path} не найден.")
        print("Сначала запустите train.py для обучения модели.")
        sys.exit(1)

    print(f"Загрузка модели из {checkpoint_path}...")
    tokenizer = load_tokenizer()

    config = LynxConfig.from_pretrained(checkpoint_path)
    model = LynxForCausalLM.from_pretrained(checkpoint_path, config=config)
    model.to(device)
    model.eval()

    print(f"Загружено: {sum(p.numel() for p in model.parameters()) / 1e6:.1f}M параметров")
    return model, tokenizer


def generate_answer(
    model: LynxForCausalLM,
    tokenizer,
    prompt: str,
    args: argparse.Namespace,
    device: str,
) -> str:
    """Сгенерировать ответ на prompt и декодировать целиком."""
    messages = [
        {"role": "system", "content": "Ты — Lynx, полезный ИИ-ассистент. Отвечай на русском языке."},
        {"role": "user", "content": prompt},
    ]

    input_text = tokenizer.apply_chat_template(messages, tokenize=False)

    inputs = tokenizer(
        input_text,
        return_tensors="pt",
        truncation=True,
        max_length=2048,
    ).to(device)

    generation_config = GenerationConfig(
        max_new_tokens=args.max_new_tokens,
        temperature=args.temperature,
        top_p=args.top_p,
        top_k=args.top_k,
        repetition_penalty=args.repetition_penalty,
        do_sample=args.temperature > 0,
        pad_token_id=tokenizer.pad_token_id,
        eos_token_id=tokenizer.eos_token_id,
    )

    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            generation_config=generation_config,
        )

    generated = output_ids[0][inputs["input_ids"].shape[1]:]
    response = tokenizer.decode(generated, skip_special_tokens=True)

    return response.strip()


def run_interactive(model, tokenizer, args, device):
    """Интерактивный чат."""
    print("\n=== Lynx 261M — Интерактивный чат ===")
    print("Введите 'exit' или 'quit' для выхода.\n")

    history = []

    while True:
        try:
            prompt = input("Вы: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nДо свидания!")
            break

        if prompt.lower() in ("exit", "quit", "выход"):
            print("До свидания!")
            break

        response = generate_answer(model, tokenizer, prompt, args, device)
        print(f"Lynx: {response}\n")


def main():
    args = parse_args()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}")

    model, tokenizer = load_model(args.checkpoint, device)

    if args.interactive:
        run_interactive(model, tokenizer, args, device)
    elif args.question:
        answer = generate_answer(model, tokenizer, args.question, args, device)
        print(f"Вопрос: {args.question}")
        print(f"Ответ: {answer}")
    else:
        print("Укажите --interactive или --question '...'")
        print(f"Пример: python inference.py --checkpoint {args.checkpoint} --question 'Привет!'")


if __name__ == "__main__":
    main()
