import os
import sys

def parse_boo1(lines):
    boos = []
    for ln in lines:
        if ln.strip().startswith('BOO1:'):
            parts = [p.strip() for p in ln.split(':')]
            try:
                width = float(parts[1])
                origin_x = float(parts[4])
            except Exception:
                continue
            boos.append({'width': width, 'origin': origin_x, 'end': origin_x + width})
    # sort by origin
    boos.sort(key=lambda b: b['origin'])
    return boos

def find_sheet(boos, x):
    # return index (1-based) of sheet containing x, or None
    for i,b in enumerate(boos, start=1):
        if x >= b['origin'] - 1e-6 and x <= b['end'] + 1e-6:
            return i
    return None

def extract_lines(lines, prefix):
    return [ln for ln in lines if ln.strip().startswith(prefix+':')]

def inspect_file(path):
    print('\n===', path, '===')
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    boos = parse_boo1(lines)
    print('\nBOO1 panels:')
    for i,b in enumerate(boos, start=1):
        print(f'  {i}: origin={b["origin"]:.2f}  width={b["width"]:.2f}  end={b["end"]:.2f}')

    nls = extract_lines(lines, 'NL')
    print(f'\nNAIL LINES (count={len(nls)}):')
    for idx,ln in enumerate(nls, start=1):
        parts = [p.strip() for p in ln.split(':')]
        try:
            sx = float(parts[1]); sy = parts[2]
            ex = float(parts[4]); ey = parts[5]
        except Exception:
            print(f'  {idx:3}: parse error: {ln.strip()}')
            continue
        s_sheet = find_sheet(boos, sx)
        e_sheet = find_sheet(boos, ex)
        span = f'sheet_start={s_sheet} sheet_end={e_sheet}'
        print(f'  {idx:3}: start={sx:.2f} end={ex:.2f} -> {span}  | {ln.strip()}')

    gls = extract_lines(lines, 'GL')
    print(f'\nGLUE LINES (count={len(gls)}):')
    for idx,ln in enumerate(gls, start=1):
        parts = [p.strip() for p in ln.split(':')]
        try:
            sx = float(parts[1]); sy = parts[2]
            ex = float(parts[4]); ey = parts[5]
        except Exception:
            print(f'  {idx:3}: parse error: {ln.strip()}')
            continue
        s_sheet = find_sheet(boos, sx)
        e_sheet = find_sheet(boos, ex)
        print(f'  {idx:3}: start={sx:.2f} end={ex:.2f} -> sheet_start={s_sheet} sheet_end={e_sheet}  | {ln.strip()}')

def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cdt_dir = os.path.join(root, 'CDT')
    files = ['P1.CDT', 'P1xm.CDT', 'P1xmsf.CDT']
    for fn in files:
        path = os.path.join(cdt_dir, fn)
        if not os.path.exists(path):
            print('Missing', path)
            continue
        inspect_file(path)

if __name__ == '__main__':
    main()
