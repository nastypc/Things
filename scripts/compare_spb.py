import sys
from pathlib import Path

def print_spb(path):
    p = Path(path)
    lines = []
    with p.open('r', encoding='utf-8', errors='replace') as f:
        for line in f:
            if line.strip().startswith('SPB:'):
                lines.append(line.rstrip('\n'))
    return lines

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print('Usage: compare_spb.py fileA fileB')
        sys.exit(2)
    a = sys.argv[1]
    b = sys.argv[2]
    sa = print_spb(a)
    sb = print_spb(b)
    print('SPB lines in', a)
    for l in sa:
        print('  ', l)
    print('\nSPB lines in', b)
    for l in sb:
        print('  ', l)
    print('\nDifferences:')
    for i, (la, lb) in enumerate(zip(sa, sb), start=1):
        if la != lb:
            print(f'  Line {i} differs:')
            print('    A:', la)
            print('    B:', lb)
    if len(sa) != len(sb):
        print(f'  Different counts: A={len(sa)} B={len(sb)}')
