import math
from typing import Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F
from transformers import PreTrainedModel
from transformers.modeling_outputs import CausalLMOutputWithPast

from config import LynxConfig


class RMSNorm(nn.Module):
    """Root Mean Square Layer Normalisation (Zhang & Sennrich, 2019)."""

    def __init__(self, hidden_size: int, eps: float = 1e-6):
        super().__init__()
        self.weight = nn.Parameter(torch.ones(hidden_size))
        self.eps = eps

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        variance = x.pow(2).mean(-1, keepdim=True)
        x = x * torch.rsqrt(variance + self.eps)
        return x * self.weight


def precompute_rope_frequencies(
    dim: int, max_len: int, theta: float = 10000.0, device: torch.device = None
) -> Tuple[torch.Tensor, torch.Tensor]:
    """Precompute RoPE cos/sin tables."""
    freqs = 1.0 / (theta ** (torch.arange(0, dim, 2, device=device).float() / dim))
    t = torch.arange(max_len, device=device).float()
    angles = t[:, None] * freqs[None, :]
    return angles.cos(), angles.sin()


def apply_rotary_emb(
    xq: torch.Tensor,
    xk: torch.Tensor,
    cos: torch.Tensor,
    sin: torch.Tensor,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """Apply rotary embeddings to query and key tensors."""
    seq_len = xq.shape[2]
    cos = cos[:seq_len].unsqueeze(0).unsqueeze(1)
    sin = sin[:seq_len].unsqueeze(0).unsqueeze(1)
    xq_ = xq.float().reshape(*xq.shape[:-1], -1, 2)
    xk_ = xk.float().reshape(*xk.shape[:-1], -1, 2)
    xq_rot = torch.stack([xq_[..., 0] * cos - xq_[..., 1] * sin,
                          xq_[..., 1] * cos + xq_[..., 0] * sin], dim=-1)
    xk_rot = torch.stack([xk_[..., 0] * cos - xk_[..., 1] * sin,
                          xk_[..., 1] * cos + xk_[..., 0] * sin], dim=-1)
    return xq_rot.flatten(3), xk_rot.flatten(3)


class Attention(nn.Module):
    """Multi-Head Attention with RoPE and Grouped-Query Attention support."""

    def __init__(self, config: LynxConfig):
        super().__init__()
        self.hidden_size = config.hidden_size
        self.num_heads = config.num_attention_heads
        self.num_kv_heads = config.num_key_value_heads
        self.head_dim = config.hidden_size // config.num_attention_heads
        self.num_key_value_groups = self.num_heads // self.num_kv_heads

        self.q_proj = nn.Linear(config.hidden_size, config.num_attention_heads * self.head_dim, bias=False)
        self.k_proj = nn.Linear(config.hidden_size, config.num_kv_heads * self.head_dim, bias=False)
        self.v_proj = nn.Linear(config.hidden_size, config.num_kv_heads * self.head_dim, bias=False)
        self.o_proj = nn.Linear(config.num_attention_heads * self.head_dim, config.hidden_size, bias=False)
        self.attn_dropout = nn.Dropout(config.attention_dropout_prob)

    def forward(
        self,
        x: torch.Tensor,
        cos: torch.Tensor,
        sin: torch.Tensor,
        attention_mask: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        bsz, seq_len, _ = x.shape

        q = self.q_proj(x).view(bsz, seq_len, self.num_heads, self.head_dim).transpose(1, 2)
        k = self.k_proj(x).view(bsz, seq_len, self.num_kv_heads, self.head_dim).transpose(1, 2)
        v = self.v_proj(x).view(bsz, seq_len, self.num_kv_heads, self.head_dim).transpose(1, 2)

        q, k = apply_rotary_emb(q, k, cos, sin)

        if self.num_key_value_groups > 1:
            k = k.repeat_interleave(self.num_key_value_groups, dim=1)
            v = v.repeat_interleave(self.num_key_value_groups, dim=1)

        attn_weights = torch.matmul(q, k.transpose(-2, -1)) / math.sqrt(self.head_dim)
        if attention_mask is not None:
            attn_weights = attn_weights + attention_mask[:, :, :seq_len, :seq_len]

        attn_weights = F.softmax(attn_weights.float(), dim=-1).type_as(q)
        attn_weights = self.attn_dropout(attn_weights)

        out = torch.matmul(attn_weights, v)
        out = out.transpose(1, 2).contiguous().view(bsz, seq_len, -1)
        return self.o_proj(out)


class SwiGLU(nn.Module):
    """SwiGLU activation MLP (Noam Shazeer, 2020)."""

    def __init__(self, config: LynxConfig):
        super().__init__()
        self.gate_proj = nn.Linear(config.hidden_size, config.intermediate_size, bias=False)
        self.up_proj = nn.Linear(config.hidden_size, config.intermediate_size, bias=False)
        self.down_proj = nn.Linear(config.intermediate_size, config.hidden_size, bias=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.down_proj(F.silu(self.gate_proj(x)) * self.up_proj(x))


class TransformerLayer(nn.Module):
    """Single decoder transformer layer with Pre-RMSNorm + SwiGLU."""

    def __init__(self, config: LynxConfig):
        super().__init__()
        self.self_attn = Attention(config)
        self.mlp = SwiGLU(config)
        self.input_norm = RMSNorm(config.hidden_size, config.rms_norm_eps)
        self.post_attn_norm = RMSNorm(config.hidden_size, config.rms_norm_eps)

    def forward(
        self,
        x: torch.Tensor,
        cos: torch.Tensor,
        sin: torch.Tensor,
        attention_mask: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        residual = x
        x = self.input_norm(x)
        x = self.self_attn(x, cos, sin, attention_mask)
        x = residual + x

        residual = x
        x = self.post_attn_norm(x)
        x = self.mlp(x)
        return residual + x


class LynxModel(PreTrainedModel):
    """Lynx transformer backbone (without LM head)."""

    config_class = LynxConfig
    base_model_prefix = "model"
    supports_gradient_checkpointing = True

    def __init__(self, config: LynxConfig):
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

    def forward(
        self,
        input_ids: torch.LongTensor,
        attention_mask: Optional[torch.Tensor] = None,
        **kwargs,
    ) -> torch.Tensor:
        x = self.embed_tokens(input_ids)

        causal_mask = None
        if attention_mask is not None:
            bsz, seq_len = input_ids.shape
            causal_mask = torch.triu(
                torch.full((seq_len, seq_len), float("-inf"), device=input_ids.device),
                diagonal=1,
            )
            causal_mask = causal_mask.unsqueeze(0).unsqueeze(0)
            extended_mask = attention_mask[:, None, None, :].float()
            extended_mask = (1.0 - extended_mask) * float("-inf")
            causal_mask = causal_mask + extended_mask

        for layer in self.layers:
            if self.gradient_checkpointing and self.training:
                x = self._gradient_checkpointing_func(
                    layer, x, self.rope_cos, self.rope_sin, causal_mask
                )
            else:
                x = layer(x, self.rope_cos, self.rope_sin, causal_mask)

        return self.norm(x)


class LynxForCausalLM(PreTrainedModel):
    """Lynx model with causal LM head."""

    config_class = LynxConfig
    base_model_prefix = "model"
    supports_gradient_checkpointing = True
    _tied_weights_keys = {"lm_head.weight": "model.embed_tokens.weight"}

    def __init__(self, config: LynxConfig):
        super().__init__(config)
        self.model = LynxModel(config)
        self.lm_head = nn.Linear(config.hidden_size, config.vocab_size, bias=False)
        self.post_init()

    def get_input_embeddings(self):
        return self.model.embed_tokens

    def set_input_embeddings(self, value):
        self.model.embed_tokens = value

    def get_output_embeddings(self):
        return self.lm_head

    def set_output_embeddings(self, new_embeddings):
        self.lm_head = new_embeddings

    def forward(
        self,
        input_ids: torch.LongTensor,
        attention_mask: Optional[torch.Tensor] = None,
        labels: Optional[torch.LongTensor] = None,
        **kwargs,
    ) -> CausalLMOutputWithPast:
        hidden = self.model(input_ids, attention_mask=attention_mask)
        logits = self.lm_head(hidden)

        loss = None
        if labels is not None:
            shift_logits = logits[..., :-1, :].contiguous()
            shift_labels = labels[..., 1:].contiguous()
            loss = F.cross_entropy(
                shift_logits.view(-1, shift_logits.size(-1)),
                shift_labels.view(-1),
                ignore_index=self.config.pad_token_id,
            )

        return CausalLMOutputWithPast(
            loss=loss,
            logits=logits,
        )

    def prepare_inputs_for_generation(self, input_ids, **kwargs):
        return {"input_ids": input_ids, "attention_mask": kwargs.get("attention_mask")}
