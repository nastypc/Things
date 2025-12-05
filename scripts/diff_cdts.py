import sys
from pathlib import Path
import difflib

def extract_sections(path):
    lines = []
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        for raw in f:
            line = raw.rstrip('\n')
            l = line.strip()
            if l.startswith('BOO1:') or l.startswith('NL:') or l.startswith('GL:') or l.startswith('GLUE'):
                lines.append(line)
    return lines

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print('Usage: diff_cdts.py <fileA> <fileB>')
        sys.exit(2)
    a = Path(sys.argv[1])
    b = Path(sys.argv[2])
    sa = extract_sections(a)
    sb = extract_sections(b)
    print(f'Comparing sections from:\n  {a}\n  {b}\n')
    diff = difflib.unified_diff(sa, sb, fromfile=str(a), tofile=str(b), lineterm='')
    printed = False
    for row in diff:
        printed = True
        print(row)
    if not printed:
        print('No differences found in BOO1/NL/GL extracted lines.')
