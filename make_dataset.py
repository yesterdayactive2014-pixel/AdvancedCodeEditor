import json, re, glob as g

data = []
templates = ["Что делает {name}?", "Объясни {name}", "Как работает {name}?", "Для чего нужен {name}?"]
for ext in ['*.py', '*.html', '*.js']:
    for fp in g.glob(ext):
        text = open(fp, encoding='utf-8', errors='replace').read()
        for m in re.finditer(r'(?:^|\n)\s*(class|def)\s+(\w+)', text):
            name = m.group(2)
            start, end = max(0, m.start()-150), min(len(text), m.end()+500)
            chunk = text[start:end].strip()[:500]
            for tpl in templates:
                data.append({"text": f"<s>[INST] {tpl.format(name=name)} [/INST] {chunk} </s>"})
json.dump(data, open('dataset.json','w',encoding='utf-8'), ensure_ascii=False, indent=2)
print(f"Готово: dataset.json ({len(data)} пар)")