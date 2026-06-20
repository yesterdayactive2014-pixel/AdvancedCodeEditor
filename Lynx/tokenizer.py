from transformers import AutoTokenizer


TOKENIZER_NAME = "DeepPavlov/rubert-base-cased"


def load_tokenizer() -> AutoTokenizer:
    """Загрузить русскоязычный токенизатор.

    Используем DeepPavlov/rubert-base-cased — BPE-токенизатор,
    обученный на русском корпусе (Wikipedia, Lenta.ru, etc.).
    Корректно обрабатывает кириллицу без кракозябр.

    Returns:
        AutoTokenizer с padding, truncation и chat_template.
    """
    tokenizer = AutoTokenizer.from_pretrained(TOKENIZER_NAME, use_fast=True)

    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token or "<pad>"

    if tokenizer.chat_template is None:
        tokenizer.chat_template = (
            "{% for message in messages %}"
            "{% if message['role'] == 'system' %}"
            "{{ message['content'] }}\n"
            "{% elif message['role'] == 'user' %}"
            "Пользователь: {{ message['content'] }}\n"
            "{% elif message['role'] == 'assistant' %}"
            "Алан Тьюринг: {{ message['content'] }}\n"
            "{% endif %}"
            "{% endfor %}"
            "Алан Тьюринг:"
        )

    return tokenizer


def format_instruction(instruction: str, response: str = "") -> str:
    """Форматировать пару instruction → response в строку для обучения."""
    parts = [
        f"Пользователь: {instruction}",
        f"Алан Тьюринг: {response}",
    ]
    return "\n".join(parts)


if __name__ == "__main__":
    tok = load_tokenizer()
    print(f"Vocab size: {tok.vocab_size}")
    print(f"Pad token: {tok.pad_token} (id={tok.pad_token_id})")
    test_text = "Привет, как дела? Нейросети — это круто!"
    ids = tok.encode(test_text)
    decoded = tok.decode(ids)
    print(f"Original: {test_text}")
    print(f"Token IDs: {ids}")
    print(f"Decoded:  {decoded}")
    assert test_text == decoded, "Кракозябры! Токенизатор портит текст."
    print("✓ Кириллица без потерь!")
