import os
import json
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader

# Локальные пути
alan_path = 'dataset.json'

print("➡️ Шаг 1: Скрипт запущен! Пытаюсь загрузить модули...")
from alan_nn import AlanTransformer, ByteTokenizer
print("➡️ Шаг 2: Модули alan_nn успешно импортированы!")

class CD(Dataset):
    def __init__(self, p, sl=128):
        print("➡️ Шаг 3: Открываю dataset.json...")
        self.tok = ByteTokenizer()
        with open(p, encoding='utf-8', errors='ignore') as f: 
            d = json.load(f)
        print("➡️ Шаг 4: Файл прочитан! Превращаю текст в числа...")
        t = []
        for i in d:
            t.extend(self.tok.encode(i['text']+'\n'))
            if len(t) > 2_000_000: break
        self.c = [t[i:i+sl+1] for i in range(0, len(t)-sl-1, sl//2)]
        print(f"➡️ Шаг 5: Датасет готов! Пакетов: {len(self.c)}")

    def __len__(self): return len(self.c)
    def __getitem__(self, i):
        c = self.c[i]
        return torch.tensor(c[:-1]), torch.tensor(c[1:])

device = 'cuda' if torch.cuda.is_available() else 'cpu'
print(f"➡️ Шаг 6: Устройство определено -> {device.upper()}")

m = AlanTransformer().to(device)
o = torch.optim.AdamW(m.parameters(), lr=3e-4)
ds = CD(alan_path)
dl = DataLoader(ds, batch_size=8, shuffle=True)

print("🔥 СТАРТ ОБУЧЕНИЯ...")
for ep in range(20):
    la = 0
    for x, y in dl:
        x, y = x.to(device), y.to(device)
        l = nn.functional.cross_entropy(m(x).reshape(-1, m(x).size(-1)), y.reshape(-1))
        o.zero_grad(); l.backward(); o.step(); la += l.item()
    print(f'Эпоха {ep+1}/20: loss = {la/len(dl):.4f}')
    torch.save(m.state_dict(), f'alan_ep{ep+1}.pt')
print("✅ ВСЁ ГОТОВО!")
