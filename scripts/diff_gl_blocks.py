from pathlib import Path
import difflib

ref = Path(r'c:/Users/edward/Downloads/ET/Sheathing/CDT/P1xx.CDT')
cur = Path(r'c:/Users/edward/Downloads/ET/Sheathing/CDT/P1x.CDT')

ref_lines = ref.read_text(encoding='utf-8').splitlines()
cur_lines = cur.read_text(encoding='utf-8').splitlines()

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
                # end of GL block
                break
    return out

rgl = extract_gl(ref_lines)
cgl = extract_gl(cur_lines)

print('Reference GL count:', len(rgl))
print('Current   GL count:', len(cgl))
print('\n--- Diff (reference -> current) ---\n')
for line in difflib.unified_diff(rgl, cgl, fromfile='P1xx.CDT(GL)', tofile='P1x.CDT(GL)', lineterm=''):
    print(line)
