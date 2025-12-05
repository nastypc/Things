import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.main import CDTFile, format_float
import src.glue as glue


def build_nl_groups_from_lines(lines):
    groups = {}
    for raw in lines:
        sline = raw.strip()
        if not sline:
            continue
        if not sline.startswith('NL:'):
            continue
        parts = sline.rstrip(';').split(':')
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
        seg_start = min(x1, x2)
        seg_end = max(x1, x2)
        y_mid = 0.5 * (y1 + y2)
        z_mid = 0.5 * (z1 + z2)
        nl_key = ('horizontal', round(y_mid, 3), round(z_mid, 3))
        info = groups.setdefault(nl_key, {'segments': [], 'min_nl': seg_start, 'max_nl': seg_end, 'y': y_mid, 'z': z_mid})
        info['segments'].append((seg_start, seg_end))
        info['min_nl'] = min(info.get('min_nl', seg_start), seg_start)
        info['max_nl'] = max(info.get('max_nl', seg_end), seg_end)
    return groups


def main():
    fp = os.path.join('CDT', 'P1.CDT')
    if not os.path.exists(fp):
        print('Missing CDT/P1.CDT')
        return
    cdt = CDTFile(fp)
    cdt.parse()
    # determine wall bounds like writer
    sheathing = cdt.get_sheathing_elements()
    if sheathing:
        first_sheet = min(sheathing, key=lambda e: e.x)
        last_sheet = max(sheathing, key=lambda e: e.x + e.x_size)
        wall_start = first_sheet.x
        wall_end = last_sheet.x + last_sheet.x_size
        wall_bottom = min(elem.y for elem in sheathing)
        wall_top = max(elem.y + elem.y_size for elem in sheathing)
    else:
        wall_start = 0.0
        wall_end = cdt.header.x_size if cdt.header else 0.0
        wall_bottom = 0.0
        wall_top = cdt.header.y_size if cdt.header else 0.0

    groups = build_nl_groups_from_lines(cdt.lines)
    print(f"NL groups parsed from {fp}: {len(groups)} keys")
    for k, v in groups.items():
        print(k, '->', v.get('min_nl'), v.get('max_nl'), 'rows:', len(v.get('segments', [])))

    def fmt_value(v, w):
        return format_float(v)

    gl_lines = glue.generate_glue_lines_from_cdt(cdt, groups, fmt_value, wall_start, wall_end, wall_bottom, wall_top)
    print('\nGenerated GL lines (count={}):'.format(len(gl_lines)))
    for g in gl_lines:
        print(g)

if __name__ == '__main__':
    main()
