import sys
import os
from math import fabs


def parse_cdt(path):
    stas = []  # list of (index, x)
    gls = []   # list of dicts {start, end, tool, raw}
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        for raw in f:
            line = raw.rstrip('\n')
            s = line.strip()
            if not s:
                continue
            if s.startswith('STA:') or s.startswith('STB:'):
                parts = s.rstrip(';').split(':')
                if len(parts) >= 7:
                    try:
                        x = float(parts[4].strip())
                    except Exception:
                        x = None
                    stas.append(x)
            elif s.startswith('GL:'):
                parts = s.rstrip(';').split(':')
                if len(parts) >= 10:
                    try:
                        x1 = float(parts[1].strip())
                        x2 = float(parts[4].strip())
                        tool = int(round(float(parts[9].strip())))
                    except Exception:
                        continue
                    gls.append({'start': x1, 'end': x2, 'tool': tool, 'raw': s})
    return stas, gls


def nearest_sta_index(stas, x):
    if not stas:
        return None, None
    best = None
    best_dist = 1e12
    for i, sx in enumerate(stas, start=1):
        if sx is None:
            continue
        d = abs(sx - x)
        if d < best_dist:
            best_dist = d
            best = i
    return best, best_dist


def pair_gls(gls_a, gls_b, tol=20.0):
    # Pair gl entries by nearest start+end sum and tool
    pairs = []
    used_b = set()
    for i, ga in enumerate(gls_a):
        best_j = None
        best_score = 1e12
        for j, gb in enumerate(gls_b):
            if j in used_b:
                continue
            score = abs(ga['start'] - gb['start']) + abs(ga['end'] - gb['end']) + (0 if ga['tool']==gb['tool'] else 10000)
            if score < best_score:
                best_score = score
                best_j = j
        if best_j is not None and best_score < tol*2 + (0 if ga['tool']==gls_b[best_j]['tool'] else 10000):
            pairs.append((i, best_j))
            used_b.add(best_j)
        else:
            pairs.append((i, None))
    # any b not used
    for j in range(len(gls_b)):
        if j not in used_b:
            pairs.append((None, j))
    return pairs


def main(a_path, b_path):
    stas_a, gls_a = parse_cdt(a_path)
    stas_b, gls_b = parse_cdt(b_path)
    print(f"Parsed {len(stas_a)} STA and {len(gls_a)} GL from {a_path}")
    print(f"Parsed {len(stas_b)} STA and {len(gls_b)} GL from {b_path}")

    # annotate gls with nearest STA and offsets
    for gls, stas, label in ((gls_a, stas_a, os.path.basename(a_path)), (gls_b, stas_b, os.path.basename(b_path))):
        print(f"\nGL mapping for {label}:")
        for idx, g in enumerate(gls, start=1):
            si, sd = nearest_sta_index(stas, g['start'])
            ei, ed = nearest_sta_index(stas, g['end'])
            sta_x = stas[si-1] if si else None
            start_offset = None
            end_offset = None
            if sta_x is not None:
                start_offset = g['start'] - sta_x
            if ei:
                sta_x_e = stas[ei-1]
                end_offset = g['end'] - sta_x_e
            print(f" {idx:3}: start={g['start']:8.2f} end={g['end']:8.2f} tool={g['tool']:3} -> start_sta={si} dist={sd:.2f} offset={start_offset if start_offset is not None else 'N/A':8} | end_sta={ei} dist={ed:.2f} offset={end_offset if end_offset is not None else 'N/A':8}")

    # pair GLs between a and b
    pairs = pair_gls(gls_a, gls_b)
    print("\nPairs (mirror-only -> sheet-flip):")
    for p in pairs:
        ia, ib = p
        if ia is None:
            gb = gls_b[ib]
            print(f"  (no match in A) B#{ib+1} start={gb['start']:.2f} end={gb['end']:.2f} tool={gb['tool']}")
        elif ib is None:
            ga = gls_a[ia]
            print(f"  A#{ia+1} (no match in B) start={ga['start']:.2f} end={ga['end']:.2f} tool={ga['tool']}")
        else:
            ga = gls_a[ia]
            gb = gls_b[ib]
            sa, sd_a = nearest_sta_index(stas_a, ga['start'])
            sb, sd_b = nearest_sta_index(stas_b, gb['start'])
            sta_x_a = stas_a[sa-1] if sa else None
            sta_x_b = stas_b[sb-1] if sb else None
            off_a = ga['start'] - sta_x_a if sta_x_a is not None else None
            off_b = gb['start'] - sta_x_b if sta_x_b is not None else None
            diff = None
            if off_a is not None and off_b is not None:
                diff = off_b - off_a
            print(f"  A#{ia+1} start={ga['start']:.2f} end={ga['end']:.2f} tool={ga['tool']} -> B#{ib+1} start={gb['start']:.2f} end={gb['end']:.2f} tool={gb['tool']} | offA={off_a:.2f} offB={off_b:.2f} delta={diff:.2f}")


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print('Usage: compare_gls_by_sta.py mirror_file sheetflip_file')
        sys.exit(2)
    a = os.path.join('CDT', sys.argv[1]) if os.path.basename(sys.argv[1])==sys.argv[1] else sys.argv[1]
    b = os.path.join('CDT', sys.argv[2]) if os.path.basename(sys.argv[2])==sys.argv[2] else sys.argv[2]
    main(a, b)
