import sys
import re
from pathlib import Path

root = Path(__file__).resolve().parent.parent
cdt_dir = root / 'CDT'
pattern = re.compile(r'^GL:\s*(.*);')
found = []
for p in sorted(cdt_dir.glob('*.CDT')):
    with p.open('r', encoding='utf-8', errors='replace') as f:
        for i, line in enumerate(f, start=1):
            s = line.strip()
            if s.startswith('GL:'):
                parts = s.rstrip(';').split(':')
                if len(parts) >= 10:
                    try:
                        tool = int(round(float(parts[9].strip())))
                    except Exception:
                        continue
                    if tool == 88:
                        found.append((p.name, i, s))

if not found:
    print('No GL with tool index 88 found in CDT/*.CDT')
else:
    for fname, lineno, line in found:
        print(f'{fname}:{lineno}: {line}')
