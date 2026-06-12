"""
train_alan.py — Alan instruction-tuning with loss masking
Usage:
    python train_alan.py --data dataset.json --epochs 20 --device cpu
    python train_alan.py --data dataset.json --epochs 20 --device cuda

Dataset format: JSON array of {"text": "<s>[INST] query [/INST] answer </s>"}
"""
import json, sys, os, torch, torch.nn as nn, torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
sys.path.insert(0, os.path.dirname(__file__))
from alan_nn import AlanTransformer, AlanConfig, ByteTokenizer

class InstructionDataset(Dataset):
    def __init__(self, path, max_len=512):
        self.tokenizer = ByteTokenizer()
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self.input_ids = []
        self.labels = []
        self.max_len = max_len
        for item in data:
            text = item['text']
            inst_end = text.find('[/INST]')
            if inst_end == -1:
                continue
            inst_end += len('[/INST]')
            inst_text = text[:inst_end]
            full_text = text
            inst_tokens = self.tokenizer.encode(inst_text)
            full_tokens = self.tokenizer.encode(full_text)
            if len(full_tokens) > max_len:
                full_tokens = full_tokens[:max_len]
                inst_tokens = inst_tokens[:max_len]
            answer_tokens = full_tokens[len(inst_tokens):]
            inp = full_tokens
            lbl = [-100] * len(inst_tokens) + answer_tokens
            if len(lbl) > max_len:
                lbl = lbl[:max_len]
            if len(inp) < 3:
                continue
            self.input_ids.append(inp)
            self.labels.append(lbl)
    def __len__(self):
        return len(self.input_ids)
    def __getitem__(self, i):
        return torch.tensor(self.input_ids[i], dtype=torch.long), torch.tensor(self.labels[i], dtype=torch.long)

def collate(batch):
    xs, ys = zip(*batch)
    max_len = max(x.size(0) for x in xs)
    xs_pad = torch.zeros(len(xs), max_len, dtype=torch.long)
    ys_pad = torch.full((len(ys), max_len), -100, dtype=torch.long)
    for i, (x, y) in enumerate(zip(xs, ys)):
        xs_pad[i, :x.size(0)] = x
        ys_pad[i, :y.size(0)] = y
    return xs_pad, ys_pad

def train():
    args = {sys.argv[i]: sys.argv[i+1] for i in range(1, len(sys.argv)-1, 2)}
    data_path = args.get('--data', 'dataset.json')
    epochs = int(args.get('--epochs', '10'))
    device = args.get('--device', 'cuda' if torch.cuda.is_available() else 'cpu')
    lr = float(args.get('--lr', '3e-4'))
    batch_size = int(args.get('--batch', '16'))
    model = AlanTransformer().to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=lr)
    ds = InstructionDataset(data_path, max_len=512)
    dl = DataLoader(ds, batch_size=batch_size, shuffle=True, collate_fn=collate)
    print(f'[Alan] Data: {len(ds)} samples | Device: {device} | Params: {sum(p.numel() for p in model.parameters()):,}')
    for ep in range(epochs):
        model.train()
        total_loss = 0
        for x, y in dl:
            x, y = x.to(device), y.to(device)
            logits = model(x)
            loss = F.cross_entropy(logits.reshape(-1, logits.size(-1)), y.reshape(-1), ignore_index=-100)
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            total_loss += loss.item()
        avg_loss = total_loss / len(dl)
        print(f'Epoch {ep+1}/{epochs}  loss={avg_loss:.4f}')
        torch.save(model.state_dict(), f'alan_ep{ep+1}.pt')
        print(f'  -> Saved alan_ep{ep+1}.pt')
    from alan_nn import export_to_numpy
    export_to_numpy(f'alan_ep{epochs}.pt', 'alan_model.npz')

if __name__ == '__main__':
    train()
