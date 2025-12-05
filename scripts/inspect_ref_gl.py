from pathlib import Path
p=Path(r'c:/Users/edward/Downloads/ET/Sheathing/CDT/P1xx.CDT')
s=p.read_text(encoding='utf-8').splitlines()
ins=False
out=[]
for l in s:
    t=l.strip()
    if t=='GLUE_LINES;':
        ins=True
        continue
    if ins:
        if t=='EOF;':
            break
        if t.startswith('GL:'):
            parts=[pp.strip() for pp in t.rstrip(';').split(':')]
            try:
                vals=list(map(float,parts[1:9]))
            except Exception:
                vals=parts[1:9]
            out.append(vals)
for i,v in enumerate(out,1):
    print(i, v)
print('count',len(out))
