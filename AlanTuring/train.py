"""
Тренировка AlanTuring 200M (поддержка T4 16GB + RTX 4060 Ti 8GB + Ada Lovelace).

Запуск:
    python train.py --batch-size 4 --grad-accum 8 --max-length 512 --epochs 3    # 4060 Ti
    python train.py --batch-size 8 --grad-accum 4 --max-length 512 --epochs 3    # T4

Автоопределение GPU: Ada (CC≥8.0) → bf16 + fused AdamW + compile.
Использует:
    - Hugging Face Trainer с чекпоинтами (Resume from checkpoint)
    - Mixed precision (bf16 для Ada/T4, fp16 fallback)
    - Gradient checkpointing для экономии VRAM
    - Gradient accumulation для эффективного большого батча
    - torch.compile на Ada Lovelace (Triton-кеши)
    - Fused AdamW (+10-15% скорости)
    - Автосохранение каждые N шагов (на случай сбоя Kaggle-сессии)
"""
import argparse
import math
import os
import sys

import torch
from transformers import (
    Trainer,
    TrainingArguments,
    DataCollatorForLanguageModeling,
    set_seed,
)

from config import AlanTuringConfig
from model import AlanTuringForCausalLM
from tokenizer import load_tokenizer
from dataset import load_instruction_dataset


def parse_args():
    parser = argparse.ArgumentParser(description="Train AlanTuring 200M")
    parser.add_argument("--batch-size", type=int, default=8, help="Per-device batch size")
    parser.add_argument("--grad-accum", type=int, default=4, help="Gradient accumulation steps")
    parser.add_argument("--max-length", type=int, default=512, help="Max sequence length")
    parser.add_argument("--epochs", type=float, default=3.0, help="Number of training epochs")
    parser.add_argument("--lr", type=float, default=3e-4, help="Peak learning rate")
    parser.add_argument("--warmup", type=int, default=500, help="Warmup steps")
    parser.add_argument("--logging-steps", type=int, default=10)
    parser.add_argument("--save-steps", type=int, default=500, help="Checkpoint save frequency")
    parser.add_argument("--output-dir", type=str, default="./checkpoints")
    parser.add_argument("--resume", type=str, default=None, help="Path to checkpoint to resume from")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--debug", action="store_true", help="Use tiny subset for testing")
    return parser.parse_args()


def main():
    args = parse_args()
    set_seed(args.seed)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}")
    if torch.cuda.is_available():
        print(f"GPU: {torch.cuda.get_device_name()}, VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")

    bf16_available = torch.cuda.is_bf16_supported()
    is_ada = props.major >= 8 if torch.cuda.is_available() else False
    print(f"bf16 support: {bf16_available}, Ada (CC≥8.0): {is_ada}")

    print("Loading tokenizer...")

    print("Loading tokenizer...")
    tokenizer = load_tokenizer()
    print(f"  Vocab: {tokenizer.vocab_size}")

    config = AlanTuringConfig(
        vocab_size=tokenizer.vocab_size,
        pad_token_id=tokenizer.pad_token_id,
        bos_token_id=tokenizer.bos_token_id or 1,
        eos_token_id=tokenizer.eos_token_id or 2,
    )
    print(f"  Params: {config.compute_num_params()}")
    print(f"  Total:  {config.compute_num_params()['total'] / 1e6:.1f}M")

    print("Loading model...")
    model = AlanTuringForCausalLM(config)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"  Model parameters: {n_params / 1e6:.1f}M")

    if args.debug:
        n = 100
        model = model.to(device)
        x = torch.randint(0, config.vocab_size, (2, 64), device=device)
        out = model(x)
        print(f"  Forward OK: {out.logits.shape}, loss: {out.loss}")
        if torch.cuda.is_available():
            print(f"  VRAM allocated: {torch.cuda.memory_allocated() / 1e6:.1f} MB")
        print("Debug mode passed. Exiting.")
        return

    print("Loading dataset...")
    if bf16_available:
        dataset = load_instruction_dataset(tokenizer, max_length=args.max_length)
    else:
        dataset = load_instruction_dataset(
            tokenizer, max_length=args.max_length,
            hf_path="IlyaGusev/oasst1_ru",
        )
    print(f"  Train examples: {len(dataset)}")

    if args.debug:
        dataset = dataset.select(range(100))

    collator = DataCollatorForLanguageModeling(
        tokenizer=tokenizer,
        mlm=False,
        pad_to_multiple_of=8,
    )

    training_args = TrainingArguments(
        output_dir=args.output_dir,
        overwrite_output_dir=True,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        gradient_checkpointing=True,
        bf16=bf16_available,
        fp16=not bf16_available,
        optim="adamw_torch_fused" if is_ada else "adamw_torch",
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
        eval_strategy="steps" if not args.debug else "no",
        eval_steps=args.save_steps * 2,
        prediction_loss_only=True,
        remove_unused_columns=True,
        report_to="none",
        ddp_find_unused_parameters=False,
        dataloader_num_workers=0,
        dataloader_pin_memory=True,
        seed=args.seed,
        torch_compile=is_ada,
        torch_compile_backend="inductor",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        data_collator=collator,
        train_dataset=dataset,
        tokenizer=tokenizer,
    )

    print("Starting training...")
    try:
        trainer.train(resume_from_checkpoint=args.resume)
    except KeyboardInterrupt:
        print("\nTraining interrupted. Saving checkpoint...")
        trainer.save_model(os.path.join(args.output_dir, "interrupted"))
        tokenizer.save_pretrained(os.path.join(args.output_dir, "interrupted"))

    print("Saving final model...")
    trainer.save_model(os.path.join(args.output_dir, "final"))
    tokenizer.save_pretrained(os.path.join(args.output_dir, "final"))

    print(f"Done! Model saved to {os.path.join(args.output_dir, 'final')}")


if __name__ == "__main__":
    main()
