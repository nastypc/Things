import sys
from pathlib import Path

def parse_nl_lines(path):
    nl_list = []
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        for raw in f:
            line = raw.strip()
            if line.startswith('NL:'):
                parts = line.rstrip(';').split(':')
                if len(parts) >= 9:
                    try:
                        x1 = float(parts[1].strip())
                        y1 = float(parts[2].strip())
                        z1 = float(parts[3].strip())
                        x2 = float(parts[4].strip())
                        y2 = float(parts[5].strip())
                        z2 = float(parts[6].strip())
                        spacing = float(parts[7].strip())
                        tool = int(round(float(parts[8].strip())))
                        nl_list.append({'x1':x1,'y1':y1,'z1':z1,'x2':x2,'y2':y2,'z2':z2,'spacing':spacing,'tool':tool,'raw':line})
                    except Exception:
                        pass
    return nl_list

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print('Usage: analyze_nl_offset.py fileA fileB')
        sys.exit(1)
    a = Path(sys.argv[1])
    b = Path(sys.argv[2])
    na = parse_nl_lines(a)
    nb = parse_nl_lines(b)
    print(f'Found {len(na)} NL in {a.name}, {len(nb)} in {b.name}')
    # For each NL in a, find closest in b by y1,y2,spacing
    matches = []
    for entry in na:
        candidates = [e for e in nb if abs(e['y1']-entry['y1'])<2.0 and abs(e['y2']-entry['y2'])<2.0 and abs(e['spacing']-entry['spacing'])<2.0]
        if not candidates:
            continue
        # pick candidate with closest x2
        cand = min(candidates, key=lambda e: abs(e['x2']-entry['x2']))
        matches.append((entry, cand))
    print(f'Paired {len(matches)} NLs by y/sp/close x2')
    deltas = []
    for a_e, b_e in matches:
        deltas.append(b_e['x1'] - a_e['x1'])
    if deltas:
        avg = sum(deltas)/len(deltas)
        print(f'Average delta (generated - manual) for x1: {avg:.2f} mm')
        # Show per-pair for first 20
        print('\nSamples:')
        for i, (a_e,b_e) in enumerate(matches[:20], start=1):
            print(f'{i}: manual x1={a_e["x1"]} gen x1={b_e["x1"]} delta={b_e["x1"]-a_e["x1"]:.2f} y1={a_e["y1"]} y2={a_e["y2"]} spacing={a_e["spacing"]}')
    else:
        print('No matched NL pairs found')
