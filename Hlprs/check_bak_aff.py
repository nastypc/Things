import importlib.util
import os
import json

BAK_PATH = r"C:\Users\THOMPSON\Downloads\EHX\bak-gui_zones.py"
EHX_PATH = r"C:\Users\THOMPSON\Downloads\EHX\Working\07-103-104.EHX"

spec = importlib.util.spec_from_file_location("bak_mod", BAK_PATH)
bak = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bak)

panels, materials_map = bak.parse_panels(EHX_PATH)
print(f"Panels parsed: {len(panels)}")
# build panels map
pan_map = {p.get('Name'): p for p in panels}

# search for the provided PanelGuid and SubAssembly
target_panel = '7d173558-2f98-422e-8a52-a2734f8f8811'
target_subassembly_guid = '22ae43df-4aec-406f-ac7b-1cf09c7eafa8'
found = False
for pguid, mats in materials_map.items():
    if pguid == target_panel or any((m.get('SubAssemblyGuid') == target_subassembly_guid or m.get('SubAssembly') == '25x137-L1') for m in (mats or [])):
        print(f"Found panel: {pguid} with {len(mats or [])} materials")
        pobj = pan_map.get(pguid, {})
        for m in (mats or []):
            if m.get('SubAssemblyGuid') == target_subassembly_guid or m.get('SubAssembly') == '25x137-L1':
                print('\nMATERIAL:')
                print(json.dumps(m, indent=2))
                try:
                    aff = bak.get_aff_for_rough_opening(pobj, m)
                    print('Computed AFF:', aff)
                except Exception as e:
                    print('AFF computation error:', e)
                found = True
if not found:
    print('Target subassembly not found in materials_map')
