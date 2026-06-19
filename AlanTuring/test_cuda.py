"""Диагностика GPU перед обучением AlanTuring 200M на RTX 4060 Ti."""
import torch, time, sys

print(f"PyTorch: {torch.__version__}")
print(f"CUDA available: {torch.cuda.is_available()}")

if not torch.cuda.is_available():
    print("CUDA НЕ ДОСТУПНА. Установи: pip install torch --index-url https://download.pytorch.org/whl/cu124")
    sys.exit(1)

print(f"GPU: {torch.cuda.get_device_name(0)}")
props = torch.cuda.get_device_properties(0)
print(f"VRAM: {props.total_mem / 1e9:.1f} GB")
print(f"SM count: {props.multi_processor_count}")
print(f"CC: {props.major}.{props.minor}")

# ── Tensor Cores ──────────────────────────────────────────────
a = torch.randn(2048, 2048, device="cuda", dtype=torch.bfloat16)
b = torch.randn(2048, 2048, device="cuda", dtype=torch.bfloat16)
torch.cuda.synchronize()
t0 = time.perf_counter()
for _ in range(100):
    c = a @ b
torch.cuda.synchronize()
t = (time.perf_counter() - t0) / 100
print(f"bf16 matmul 2048x2048: {t*1e3:.2f} ms/op  ← Tensor Cores")

# ── bf16 support ──────────────────────────────────────────────
bf16_supported = torch.cuda.is_bf16_supported()
print(f"bf16 hardware support: {bf16_supported} {'✅' if bf16_supported else '❌'}")

# Если bf16 не поддерживается — проверяем fp16
if not bf16_supported:
    a16 = a.to(torch.float16)
    b16 = b.to(torch.float16)
    torch.cuda.synchronize()
    t16 = time.perf_counter()
    for _ in range(100):
        c16 = a16 @ b16
    torch.cuda.synchronize()
    print(f"fp16 matmul: {(time.perf_counter()-t16)/100*1e3:.2f} ms/op")

# ── CUDA memory test ──────────────────────────────────────────
model_mb = 195
opt_mb = model_mb * 2 * 4  # AdamW: 2 states * fp32
total_est = model_mb + opt_mb + 200  # + activations
print(f"Mem estimate: ~{total_est} MB / {props.total_mem / 1e9:.1f} GB")

x = torch.randn(4, 512, 768, device="cuda", dtype=torch.bfloat16)
print(f"  batch 4, seq 512, hidden 768: {x.numel() * x.element_size() / 1e6:.1f} MB")
del x

print(f"Allocated: {torch.cuda.memory_allocated() / 1e6:.1f} MB")
print(f"Cached:    {torch.cuda.memory_reserved() / 1e6:.1f} MB")
print("✅ GPU готова к обучению AlanTuring 200M!")
