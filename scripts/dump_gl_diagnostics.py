import os
import sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.main import CDTFile, PRESETS, GLUE_EDGE, format_float

def parse_nl_groups(lines):
    horizontal_nl_groups = {}
    for raw in lines:
        s = raw.strip()
        if not s:
            continue
        if not s.startswith('NL:'):
            continue
        parts = s.rstrip(';').split(':')
        if len(parts) < 8:
            continue
        try:
            x1 = float(parts[1].strip())
            y1 = float(parts[2].strip())
            z1 = float(parts[3].strip())
            x2 = float(parts[4].strip())
            y2 = float(parts[5].strip())
            z2 = float(parts[6].strip())
        except Exception:
            continue
        # compute midpoints and segment extents
        seg_start = min(x1, x2)
        seg_end = max(x1, x2)
        y_mid = 0.5 * (y1 + y2)
        z_mid = 0.5 * (z1 + z2)
        nl_key = ('horizontal', round(y_mid, 3), round(z_mid, 3))
        info = horizontal_nl_groups.setdefault(nl_key, {'segments': [], 'min_nl': seg_start, 'max_nl': seg_end, 'y': y_mid, 'z': z_mid})
        info['segments'].append((seg_start, seg_end))
        info['min_nl'] = min(info.get('min_nl', seg_start), seg_start)
        info['max_nl'] = max(info.get('max_nl', seg_end), seg_end)
    return horizontal_nl_groups


def dump():
    p = r'CDT/P1.CDT'
    if not os.path.exists(p):
        print('CDT/P1.CDT not found')
        return
    c = CDTFile(p)
    c.parse()
    lines = c.lines
    nl_groups = parse_nl_groups(lines)

    print('--- NL Rows (horizontal) ---')
    for k, info in sorted(nl_groups.items(), key=lambda t: t[1].get('y', 0.0)):
        print(f'Row y={info.get("y")}, z={info.get("z")}, min={info.get("min_nl")}, max={info.get("max_nl")}, segments={len(info.get("segments",[]))}')

    print('\n--- Raw STA spans (parsed) ---')
    raw_spans = []
    for i, s in enumerate(c.sta_elements, 1):
        try:
            xs = float(s.x)
            xsz = float(getattr(s, 'x_size', 0.0))
        except Exception:
            continue
        raw_spans.append((xs, xs + xsz, getattr(s, 'element_type', 'STA')))
        print(f'{i:2d}: start={xs:.2f} end={xs + xsz:.2f} type={getattr(s, "element_type", None)}')

    # Dedupe exact
    unique = {}
    for s, e, t in raw_spans:
        key = (round(s,3), round(e,3))
        if key not in unique:
            unique[key] = (s, e)
    raw_unique = [unique[k] for k in sorted(unique.keys(), key=lambda kk: kk[0])]

    print('\n--- STA unique spans (dedup exact) ---')
    for i, (s,e) in enumerate(raw_unique,1):
        print(f'{i:2d}: {s:.2f} -> {e:.2f}')

    # Cluster
    CLUSTER_TOL = float(PRESETS.get('sta_cluster_tolerance', 50.0))
    clusters = []
    if raw_unique:
        cur_s, cur_e = raw_unique[0]
        for s,e in raw_unique[1:]:
            if s <= cur_e + CLUSTER_TOL:
                cur_e = max(cur_e, e)
            else:
                clusters.append((cur_s, cur_e))
                cur_s, cur_e = s, e
        clusters.append((cur_s, cur_e))

    print(f'\n--- STA clusters (tolerance={CLUSTER_TOL} mm) ---')
    for i, (s,e) in enumerate(clusters,1):
        print(f'{i:2d}: {s:.2f} -> {e:.2f}')

    # Generate GLs for three modes
    def fmt_wrapped(v,w):
        return format_float(v)

    print('\n--- GLs: per_sta_only (no NL rows) ---')
    gls_per_sta = c.generate_glue_lines({}, fmt_wrapped, 0.0, c.header.x_size if c.header else 0.0, 0.0, c.header.y_size if c.header else 0.0)
    print(f'Count: {len(gls_per_sta)}')
    for g in gls_per_sta:
        print(g)

    print('\n--- GLs: per_sta_by_row (use NL rows) ---')
    gls_by_row = c.generate_glue_lines(nl_groups, fmt_wrapped, 0.0, c.header.x_size if c.header else 0.0, 0.0, c.header.y_size if c.header else 0.0)
    print(f'Count: {len(gls_by_row)}')
    for g in gls_by_row:
        print(g)

    print('\n--- GLs: Xmain reference generator ---')
    try:
        from src import Xmain
        xinst = Xmain.CDTFile(p)
        xinst.parse()
        x_gls = xinst.generate_glue_lines(nl_groups, fmt_wrapped, 0.0, xinst.header.x_size if xinst.header else 0.0, 0.0, xinst.header.y_size if xinst.header else 0.0)
        print(f'Count: {len(x_gls)}')
        for g in x_gls:
            print(g)
    except Exception as e:
        print('Xmain generator error:', e)

if __name__ == '__main__':
    dump()
