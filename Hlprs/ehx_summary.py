import importlib, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
importlib.invalidate_caches()
import importlib
try:
    b = importlib.import_module('bak-gui_zones')
except Exception:
    b = importlib.import_module('bak_gui_zones')
from collections import OrderedDict
wdir = os.path.join(ROOT, 'Working')
print('Scanning:', wdir)
for fn in sorted(os.listdir(wdir)):
    if not fn.lower().endswith('.ehx'):
        continue
    path = os.path.join(wdir, fn)
    try:
        panels, mats = b.parse_panels(path)
    except Exception as e:
        print(fn, 'parse error:', e)
        continue
    if isinstance(panels, dict):
        panels_by_name = panels
    else:
        panels_by_name = OrderedDict()
        for p in panels or []:
            if not p: continue
            name = p.get('Name') or p.get('DisplayLabel') or f'Panel_{len(panels_by_name)+1}'
            panels_by_name[name] = p
    bundle_panels = {}
    for name, obj in panels_by_name.items():
        bkey = None
        if isinstance(obj, dict):
            bkey = obj.get('BundleGuid') or obj.get('BundleId') or obj.get('Bundle') or obj.get('BundleName') or obj.get('BundleLabel')
        if not bkey:
            bkey = 'Bundle'
        bundle_panels.setdefault(str(bkey), []).append(name)
    print(f"{fn}: panels={len(panels_by_name)}, bundle_keys={len(bundle_panels)}")
    for k,v in bundle_panels.items():
        print('  ', k, len(v))
    print()
