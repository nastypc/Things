import sys
sys.path.append('.')
import importlib.util
spec = importlib.util.spec_from_file_location('bak_gui_zones', 'bak-gui_zones.py')
bak_gui_zones = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bak_gui_zones)
parse_panels = bak_gui_zones.parse_panels
import xml.etree.ElementTree as ET

# Test loading the EHX file
ehx_file = r'Working\Levels\SNO-L1-L2-005008.EHX'
panels, materials = parse_panels(ehx_file)

print('Found panels:', len(panels))
print('Materials keys (first 5):', list(materials.keys())[:5])

# Check the EHX file structure for panel labels and GUIDs
tree = ET.parse(ehx_file)
root = tree.getroot()

panel_label_to_guid = {}
for panel in root.findall('.//Panel'):
    panel_guid_el = panel.find('PanelGuid')
    label_el = panel.find('Label')
    if panel_guid_el is not None and panel_guid_el.text and label_el is not None and label_el.text:
        panel_label_to_guid[label_el.text.strip()] = panel_guid_el.text.strip()

print('Panel label to GUID mapping (first 5):', dict(list(panel_label_to_guid.items())[:5]))

# Check if 05-100 is in the mapping
if '05-100' in panel_label_to_guid:
    guid = panel_label_to_guid['05-100']
    print(f'Panel 05-100 has GUID: {guid}')
    print(f'Materials for GUID {guid}: {len(materials.get(guid, []))} items')
else:
    print('Panel 05-100 not found in mapping')
