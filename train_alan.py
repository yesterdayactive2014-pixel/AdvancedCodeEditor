# train_alan.py — Alan instruction-tuning with loss masking
# python train_alan.py --data dataset.json --epochs 20 --device cpu
import json, sys, os, torch, torch.nn as nn, torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
sys.path.insert(0, os.path.dirname(__file__))
from alan_nn import AlanTransformer, AlanConfig, ByteTokenizer

class InstructionDataset(Dataset):
    def __init__(self, path, max_len=512):
        self.tokenizer = ByteTokenizer()
        with open(path, 'r', encoding='utf-8') as f: data = json.load(f)
        self.input_ids, self.labels, self.max_len = [], [], max_len
        for item in data:
            text = item['text']
            inst_end = text.find('[/INST]')
            if inst_end == -1: continue
            inst_end += len('[/INST]')
            inst_tokens = self.tokenizer.encode(text[:inst_end])
            full_tokens = self.tokenizer.encode(text)[:max_len]
            inst_tokens = inst_tokens[:max_len]
            answer_tokens = full_tokens[len(inst_tokens):]
            inp = full_tokens
            lbl = [-100] * len(inst_tokens) + answer_tokens
            if len(lbl) > max_len: lbl = lbl[:max_len]
            if len(inp) >= 3:
                self.input_ids.append(inp); self.labels.append(lbl)
    def __len__(self): return len(self.input_ids)
    def __getitem__(self, i):
        return torch.tensor(self.input_ids[i], dtype=torch.long), torch.tensor(self.labels[i], dtype=torch.long)

def collate(batch):
    xs, ys = zip(*batch)
    m = max(x.size(0) for x in xs)
    xp = torch.zeros(len(xs), m, dtype=torch.long)
    yp = torch.full((len(ys), m), -100, dtype=torch.long)
    for i,(x,y) in enumerate(zip(xs,ys)):
        xp[i,:x.size(0)] = x; yp[i,:y.size(0)] = y
    return xp, yp

def train():
    a = {sys.argv[i]: sys.argv[i+1] for i in range(1, len(sys.argv)-1, 2)}
    device = a.get('--device', 'cuda' if torch.cuda.is_available() else 'cpu')
    model = AlanTransformer().to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=float(a.get('--lr','3e-4')))
    ds = InstructionDataset(a.get('--data','dataset.json'))
    dl = DataLoader(ds, batch_size=int(a.get('--batch','16')), shuffle=True, collate_fn=collate)
    print(f'[Alan] Data:{len(ds)} Device:{device} Params:{sum(p.numel() for p in model.parameters()):,}')
    for ep in range(int(a.get('--epochs','10'))):
        model.train(); loss_acc = 0
        for x, y in dl:
            x, y = x.to(device), y.to(device)
            loss = F.cross_entropy(model(x).reshape(-1, model(x).size(-1)), y.reshape(-1), ignore_index=-100)
            opt.zero_grad(); loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step(); loss_acc += loss.item()
        print(f'Epoch {ep+1}: loss={loss_acc/len(dl):.4f}')
        torch.save(model.state_dict(), f'alan_ep{ep+1}.pt')
    from alan_nn import export_to_numpy
    export_to_numpy(f'alan_ep{a.get("--epochs","10")}.pt', 'alan_model.npz')

if __name__ == '__main__': train()
