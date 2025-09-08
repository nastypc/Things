import importlib.util, json, pprint, os
MODULE_PATH = r'C:\Users\THOMPSON\Downloads\EHX\bak-gui_zones.py'
EHX_PATH = r'C:\Users\THOMPSON\Downloads\EHX\Working\07_112.EHX'

spec = importlib.util.spec_from_file_location('bg', MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

panels, mats_map = mod.parse_panels(EHX_PATH)

# find panel with DisplayLabel '07_112' or PanelID match
panel_obj = None
panel_name = None
for p in panels:
    label = p.get('DisplayLabel') or p.get('Name')
    if label == '07_112' or p.get('Name') == '07_112' or p.get('Name') == '50e38fea-d8b3-4716-9c0c-996935136dff' :
        panel_obj = p
        panel_name = p.get('Name')
        break

if not panel_obj:
    print('Panel 07_112 not found; panels discovered:')
    for p in panels:
        print(' -', p.get('DisplayLabel'), p.get('Name'))
    raise SystemExit(1)

print('\n=== PANEL OBJECT ===')
print(json.dumps(panel_obj, indent=2, default=str))

mats = mats_map.get(panel_name, [])
print(f"\n=== MATERIALS for panel {panel_name} (count: {len(mats)}) ===\n")
for i, m in enumerate(mats, 1):
    print(f"--- material #{i} ---")
    pprint.pprint(m)
    print()

print('\n=== END ===')
