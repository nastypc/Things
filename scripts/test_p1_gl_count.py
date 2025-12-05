from pathlib import Path
import sys
from src.main import process_cdt_file

# Run processing and check GL counts
base = Path('CDT') / 'P1.CDT'
if not base.exists():
    print('P1.CDT not found in CDT/ - aborting')
    sys.exit(2)

res = process_cdt_file(str(base))
print(res)

# Run diff script logic
ref = Path('CDT') / 'P1xx.CDT'
cur = Path('CDT') / 'P1x.CDT'
if not ref.exists():
    print('Reference P1xx.CDT missing; cannot compare')
    sys.exit(2)

r = ref.read_text(encoding='utf-8').splitlines()
c = cur.read_text(encoding='utf-8').splitlines()

def extract_gl(lines):
    out = []
    in_block = False
    for l in lines:
        s = l.strip()
        if s == 'GLUE_LINES;':
            in_block = True
            continue
        if in_block:
            if s.startswith('GL:'):
                out.append(l)
            elif s == 'EOF;':
                break
            elif s == '':
                continue
            else:
                break
    return out

rgl = extract_gl(r)
cgl = extract_gl(c)
print('Reference GL count:', len(rgl))
print('Current   GL count:', len(cgl))
if len(rgl) != len(cgl):
    print('GL count mismatch')
    sys.exit(1)
print('GL parity OK')
sys.exit(0)
