import importlib, os, sys
# Ensure project root is on sys.path so we can import top-level modules when running from scripts/
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
importlib.invalidate_caches()
try:
    b = importlib.import_module('bak-gui_zones')
except Exception as e:
    print('Failed to import bak-gui_zones:', e)
    raise
path = r'C:\Users\THOMPSON\Downloads\EHX\Working\07_112.EHX'
print('Parsing:', path)
try:
    panels, mats = b.parse_panels(path)
except Exception as e:
    print('parse_panels error:', e)
    sys.exit(1)
panels_by_name = {}
if isinstance(panels, dict):
    panels_by_name.update(panels)
else:
    from collections import OrderedDict
    panels_by_name = OrderedDict()
    for p in panels or []:
        if not p:
            continue
        name = p.get('Name') or p.get('DisplayLabel') or f"Panel_{len(panels_by_name)+1}"
        panels_by_name[name] = p
print('Total panels parsed:', len(panels_by_name))
bundle_panels = {}
for name, obj in panels_by_name.items():
    bkey = None
    if isinstance(obj, dict):
        bkey = obj.get('BundleGuid') or obj.get('BundleId') or obj.get('Bundle') or obj.get('BundleName') or obj.get('BundleLabel')
    if not bkey:
        bkey = 'Bundle'
    bundle_panels.setdefault(str(bkey), []).append(name)
print('Bundle keys and counts:')
for k, v in bundle_panels.items():
    print(f"- {k!s}: {len(v)} panels")

print('\nSample panel entries (first 10):')
for i, (n, o) in enumerate(panels_by_name.items()):
    if i >= 10:
        break
    print(n, '-->', {'DisplayLabel': o.get('DisplayLabel'), 'Bundle': o.get('Bundle') if isinstance(o, dict) else None})
