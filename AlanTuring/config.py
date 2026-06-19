from transformers import PretrainedConfig


class AlanTuringConfig(PretrainedConfig):
    """Конфигурация AlanTuring — компактный LLaMA-like трансформер ~200M параметров.

    Архитектура:
        - Decoder-only transformer (GPT/LLaMA style)
        - Pre-RMSNorm + SwiGLU MLP + RoPE
        - Tied embeddings (input / lm_head shared)

    Memory fit (T4 16GB):
        - Параметры (fp32):   ~780 MB
        - Параметры (bf16):   ~390 MB
        - Оптимизатор AdamW:  ~2.3 GB (fp32)
        - Градиенты (fp32):   ~780 MB
        - Активации (bs=8, seq=512): ~200 MB
        → Итого: ~3.7 GB — запас >12 GB под батч и seq_len
    """

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

    def compute_num_params(self) -> dict:
        """Приблизительный подсчёт параметров."""
        h = self.hidden_size
        v = self.vocab_size
        i = self.intermediate_size
        n = self.num_hidden_layers

        embed = v * h
        per_layer = (
            3 * h * h           # Q, K, V projections
            + h * h             # Wo output projection
            + 3 * h * i         # SwiGLU MLP (gate, up, down)
        )
        total = embed + n * per_layer + h  # final norm
        return {
            "embedding": embed,
            "per_layer": per_layer,
            "total_layers": n * per_layer,
            "total": total,
        }
