import json
import os
from typing import Optional

import torch
from datasets import Dataset, load_dataset
from torch.utils.data import DataLoader, IterableDataset
from transformers import PreTrainedTokenizer

from tokenizer import load_tokenizer, format_instruction


def load_instruction_dataset(
    tokenizer: PreTrainedTokenizer,
    hf_path: Optional[str] = None,
    jsonl_path: Optional[str] = None,
    max_length: int = 512,
    split: str = "train",
    num_proc: int = 4,
) -> Dataset:
    """Загрузить датасет инструкций на русском языке.

    Поддерживаемые источники (по приоритету):
    1. Hugging Face датасет (hf_path) — например 'IlyaGusev/oasst1_ru'
    2. Локальный JSONL-файл (jsonl_path)
    3. Если ничего не указано — загружаем oasst1_ru по умолчанию

    Формат JSONL (каждая строка):
        {"instruction": "...", "response": "..."}

    Returns:
        Dataset с колонками ['input_ids', 'attention_mask', 'labels'].
    """
    if hf_path:
        ds = load_dataset(hf_path, split=split)
    elif jsonl_path and os.path.exists(jsonl_path):
        ds = load_dataset("json", data_files=jsonl_path, split="train")
    else:
        ds = load_dataset("IlyaGusev/oasst1_ru", split=split)

    def _convert(example):
        if "instruction" in example and "response" in example:
            text = format_instruction(example["instruction"], example["response"])
        elif "text" in example:
            text = example["text"]
        elif "messages" in example:
            text = tokenizer.apply_chat_template(example["messages"], tokenize=False)
        else:
            keys = list(example.keys())
            raise ValueError(
                f"Неизвестный формат датасета. Ключи: {keys}. "
                "Ожидаются: 'instruction'+'response', 'text' или 'messages'."
            )

        enc = tokenizer(
            text,
            truncation=True,
            max_length=max_length,
            padding="max_length",
            return_tensors=None,
        )
        enc["labels"] = enc["input_ids"].copy()
        return enc

    ds = ds.map(_convert, num_proc=num_proc, remove_columns=ds.column_names)
    ds.set_format(type="torch", columns=["input_ids", "attention_mask", "labels"])
    return ds


def create_dataloader(
    dataset: Dataset,
    batch_size: int = 8,
    shuffle: bool = True,
    num_workers: int = 2,
) -> DataLoader:
    """Создать DataLoader из Dataset."""
    return DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=shuffle,
        num_workers=num_workers,
        pin_memory=True,
    )


if __name__ == "__main__":
    tokenizer = load_tokenizer()
    ds = load_instruction_dataset(tokenizer, max_length=128)
    print(f"Датасет: {len(ds)} примеров")
    print(f"Пример: {tokenizer.decode(ds[0]['input_ids'])[:200]}...")
