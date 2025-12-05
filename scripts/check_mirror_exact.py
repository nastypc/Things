from pathlib import Path
import re

def parse_header_span(path):
    for line in Path(path).read_text(encoding='utf-8', errors='replace').splitlines():
        s=line.strip()
        if s.startswith('ELM:'):
            parts=s.rstrip(';').split(':')
            try:
                return float(parts[1].strip())
            except Exception:
                continue
    return None

def parse_sta(path):
    out=[]
    for line in Path(path).read_text(encoding='utf-8', errors='replace').splitlines():
        s=line.strip()
        if s.startswith('STA:') or s.startswith('STB:'):
            parts=s.rstrip(';').split(':')
            # some files have variable spacing, try to parse numerics
            try:
                x_size=float(parts[1].strip())
                y_size=float(parts[2].strip())
                z_size=float(parts[3].strip())
                x=float(parts[4].strip())
                y=float(parts[5].strip())
                z=float(parts[6].strip())
            except Exception:
                # fallback: find first 6 numeric tokens
                nums=[float(t) for t in re.findall(r'-?\d+(?:\.\d+)?', s)[:6]]
                if len(nums)>=6:
                    x_size,y_size,z_size,x,y,z=nums[:6]
                else:
                    continue
            out.append({'x_size':x_size,'y_size':y_size,'z_size':z_size,'x':x,'y':y,'z':z,'raw':s})
    return out


def parse_gl(path):
    out=[]
    for line in Path(path).read_text(encoding='utf-8', errors='replace').splitlines():
        s=line.strip()
        if s.startswith('GL:'):
            parts=s.rstrip(';').split(':')
            try:
                xs=float(parts[1].strip()); ys=float(parts[2].strip()); zs=float(parts[3].strip())
                xe=float(parts[4].strip()); ye=float(parts[5].strip()); ze=float(parts[6].strip())
                tool=int(round(float(parts[9-1].strip())))
            except Exception:
                nums=[float(t) for t in re.findall(r'-?\d+(?:\.\d+)?', s)[:9]]
                if len(nums)>=9:
                    xs,ys,zs,xe,ye,ze,amp,wave,tool=nums[:9]
                else:
                    continue
            out.append({'x_start':xs,'y_start':ys,'z_start':zs,'x_end':xe,'y_end':ye,'z_end':ze,'tool':int(tool),'raw':s})
    return out


def compare_mirror(orig_path, mirror_path, tol=0.5):
    span=parse_header_span(orig_path)
    if span is None:
        print('Could not find ELM span in', orig_path); return 2
    sta_orig=parse_sta(orig_path)
    sta_m=parse_sta(mirror_path)
    gl_orig=parse_gl(orig_path)
    gl_m=parse_gl(mirror_path)

    print(f'ELM span (orig): {span}')
    print(f'Parsed STA orig {len(sta_orig)}, STA mirror {len(sta_m)}')
    print(f'Parsed GL orig {len(gl_orig)}, GL mirror {len(gl_m)}')

    sta_errors=[]
    for i,so in enumerate(sta_orig):
        if i>=len(sta_m): break
        expected_x = round(span - (so['x'] + so['x_size']), 6)
        actual_x = round(sta_m[i]['x'],6)
        delta = actual_x - expected_x
        if abs(delta)>tol:
            sta_errors.append((i+1, expected_x, actual_x, delta, so['raw'], sta_m[i]['raw']))
    if sta_errors:
        print('\nSTA mismatches (index, expected_x, actual_x, delta):')
        for e in sta_errors:
            print(e[0], e[1], e[2], e[3])
            print('  orig:', e[4])
            print('  mirror:', e[5])
    else:
        print('\nAll STA entries match expected mirror positions (within tol).')

    gl_errors=[]
    for i,go in enumerate(gl_orig):
        if i>=len(gl_m): break
        exp_xs = round(span - go['x_end'],6)
        exp_xe = round(span - go['x_start'],6)
        act_xs = round(gl_m[i]['x_start'],6)
        act_xe = round(gl_m[i]['x_end'],6)
        dxs = act_xs - exp_xs
        dxe = act_xe - exp_xe
        if abs(dxs)>tol or abs(dxe)>tol:
            gl_errors.append((i+1, (exp_xs,exp_xe),(act_xs,act_xe),(dxs,dxe),go['raw'],gl_m[i]['raw']))
    if gl_errors:
        print('\nGL mismatches (index, expected(xs,xe), actual(xs,xe), deltas):')
        for g in gl_errors:
            print(g[0], g[1], g[2], g[3])
            print('  orig:', g[4])
            print('  mirror:', g[5])
    else:
        print('\nAll GL entries match expected mirror positions (within tol).')

    return 0

if __name__=='__main__':
    import sys
    orig='CDT/P1.CDT'
    mirror='CDT/P1xm.CDT'
    if len(sys.argv)>1:
        orig=sys.argv[1]
    if len(sys.argv)>2:
        mirror=sys.argv[2]
    sys.exit(compare_mirror(orig, mirror))
