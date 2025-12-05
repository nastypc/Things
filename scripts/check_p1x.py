from pathlib import Path
import re

p = Path(r'c:/Users/edward/Downloads/ET/Sheathing/CDT/P1x.CDT')
text = p.read_text(encoding='utf-8')
lines = [l.rstrip('\n') for l in text.splitlines()]
header = None
spb = None
stas = []
boos = []
nails = []

for line in lines:
    s = line.strip()
    if s.startswith('ELM:'):
        parts = [p.strip() for p in s.rstrip(';').split(':')]
        header = {
            'x_size': float(parts[1]),
            'y_size': float(parts[2]),
            'z_size': float(parts[3])
        }
    if s.startswith('SPB:'):
        parts = [p.strip() for p in s.rstrip(';').split(':')]
        spb = {'x': float(parts[1]), 'y': float(parts[2]), 'z': float(parts[3])}
    if s.startswith('STA:') or s.startswith('STB:'):
        parts = [p.strip() for p in s.rstrip(';').split(':')]
        try:
            x_size = float(parts[1])
            y_size = float(parts[2])
            z_size = float(parts[3])
            x = float(parts[4])
            y = float(parts[5])
            z = float(parts[6]) if len(parts) > 6 else 0.0
            stas.append({'x': x, 'x_size': x_size, 'y': y, 'y_size': y_size, 'z_size': z_size, 'z': z, 'raw': s})
        except Exception:
            pass
    if s.startswith('BOO') or s.startswith('BOI'):
        parts = [p.strip() for p in s.rstrip(';').split(':')]
        try:
            x_size = float(parts[1])
            y_size = float(parts[2])
            z_size = float(parts[3])
            x = float(parts[4])
            y = float(parts[5])
            boos.append({'x': x, 'x_size': x_size, 'y': y, 'y_size': y_size, 'z_size': z_size, 'raw': s})
        except Exception:
            pass
    if s.startswith('NL:'):
        parts = [p.strip() for p in s.rstrip(';').split(':')]
        try:
            z1 = float(parts[3])
            z2 = float(parts[6])
            nails.append({'raw': s, 'z1': z1, 'z2': z2})
        except Exception:
            pass

# compute extents
max_sta_end = max((st['x'] + st['x_size'] for st in stas), default=0.0)
min_sta = min((st['x'] for st in stas), default=0.0)
sta_span = max_sta_end - min_sta
max_boo_end = max((b['x'] + b['x_size'] for b in boos), default=0.0)
min_boo = min((b['x'] for b in boos), default=0.0)
boo_span = max_boo_end - min_boo

max_sta_y_end = max((st['y'] + st['y_size'] for st in stas), default=0.0)
min_sta_y = min((st['y'] for st in stas), default=0.0)
sta_y_span = max_sta_y_end - min_sta_y

max_boo_y_end = max((b['y'] + b['y_size'] for b in boos), default=0.0)
min_boo_y = min((b['y'] for b in boos), default=0.0)
boo_y_span = max_boo_y_end - min_boo_y

# top surface z
header_z = header['z_size'] if header else None
max_sta_z = max((st['z_size'] for st in stas), default=0.0)
max_boo_z = max((b['z_size'] for b in boos), default=0.0)

print('Header ELM:', header)
print('SPB:', spb)
print('\nSTA count:', len(stas))
print(f"STA X span from {min_sta:.2f} to {max_sta_end:.2f} -> span {sta_span:.2f}")
print(f"BOO X span from {min_boo:.2f} to {max_boo_end:.2f} -> span {boo_span:.2f}")
print(f"Header.x_size = {header['x_size']:.2f}")
print('Suggested XSize (max of BOO/STA ends):', max(max_boo_end, max_sta_end))

print(f"\nSTA Y span from {min_sta_y:.2f} to {max_sta_y_end:.2f} -> span {sta_y_span:.2f}")
print(f"BOO Y span from {min_boo_y:.2f} to {max_boo_y_end:.2f} -> span {boo_y_span:.2f}")
print(f"Header.y_size = {header['y_size']:.2f}")
print('Suggested YSize (max of BOO/STA):', max(max_boo_y_end, max_sta_y_end))

print(f"\nHeader.z_size = {header_z}")
print('Max STA z_size =', max_sta_z)
print('Max BOO z_size =', max_boo_z)
print('Suggested ZSize (max of STA/BOO/header):', max(header_z or 0.0, max_sta_z, max_boo_z))

# nails checks
if nails:
    # compute top surface: use header z + max Boo z_size? But in file NL z was set to 260 earlier.
    # We'll compute expected nail z as header.z_size + max_boo_z
    expected_top = (header_z or 0.0) + max_boo_z
    print(f"\nComputed top-surface Z (header.z + max BOO z): {expected_top:.2f}")
    for i,nl in enumerate(nails[:10], start=1):
        dz1 = nl['z1'] - expected_top
        dz2 = nl['z2'] - expected_top
        if abs(dz1) > 0.5 or abs(dz2) > 0.5:
            print(f"NL {i} mismatch: {nl['raw']} -> z1 dz={dz1:.2f}, z2 dz={dz2:.2f}")
else:
    print('\nNo NL entries found')

# exit code

