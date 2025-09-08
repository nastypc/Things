import xml.etree.ElementTree as ET
from collections import defaultdict

def get_panel_junction_details(ehx_file_path, panel_label):
    """Get detailed junction information for a specific panel"""
    tree = ET.parse(ehx_file_path)
    root = tree.getroot()

    # Find the panel
    target_panel = None
    for panel in root.findall('.//Panel'):
        label = panel.find('Label')
        if label is not None and label.text == panel_label:
            target_panel = panel
            break

    if target_panel is None:
        return None, None, None

    panel_guid = target_panel.find('PanelGuid')
    if panel_guid is None or panel_guid.text is None:
        return None, None, None

    # Extract panel basic info
    panel_info = {
        'guid': panel_guid.text,
        'label': panel_label,
        'level': target_panel.find('LevelNo').text if target_panel.find('LevelNo') is not None else 'Unknown',
        'bundle': target_panel.find('BundleName').text if target_panel.find('BundleName') is not None else 'Unknown',
        'height': target_panel.find('Height').text if target_panel.find('Height') is not None else 'Unknown',
        'thickness': target_panel.find('Thickness').text if target_panel.find('Thickness') is not None else 'Unknown',
        'length': target_panel.find('WallLength').text if target_panel.find('WallLength') is not None else 'Unknown'
    }

    # Find all junctions for this panel
    junctions = []
    junction_types = defaultdict(int)

    for junction in root.findall('.//Junction'):
        j_panel_guid = junction.find('PanelGuid')
        if j_panel_guid is not None and j_panel_guid.text == panel_guid.text:
            sub_name_el = junction.find('SubAssemblyName')
            fam_name_el = junction.find('FamilyMemberName')
            label_el = junction.find('Label')

            sub_name = sub_name_el.text.strip() if sub_name_el is not None and sub_name_el.text else "Unknown"
            fam_name = fam_name_el.text.strip() if fam_name_el is not None and fam_name_el.text else "Unknown"
            connected_label = label_el.text.strip() if label_el is not None and label_el.text else "Unknown"

            junction_type = f"{sub_name} -> {fam_name}"
            junction_types[junction_type] += 1

            junctions.append({
                'type': junction_type,
                'connected_to': connected_label,
                'subassembly': sub_name,
                'family_member': fam_name
            })

    return panel_info, junctions, dict(junction_types)

# Get details for panel 05-208
panel_info, junctions, junction_types = get_panel_junction_details('Working/Test/Test 2/SNO-L2-005008.EHX', '05-208')

if panel_info is None:
    print("Panel not found!")
    exit(1)

print("=== PANEL DETAILS ===")
print(f"Panel: {panel_info['label']}")
print(f"Level: {panel_info['level']}")
print(f"Bundle: {panel_info['bundle']}")
print(f"Height: {panel_info['height']} inches")
print(f"Thickness: {panel_info['thickness']} inches")
print(f"Length: {panel_info['length']} inches")
print()

print("=== JUNCTION SUMMARY ===")
print(f"Total Junctions: {len(junctions)}")
print()

print("=== JUNCTION TYPES (with counts) ===")
for junction_type, count in sorted(junction_types.items()):
    print(f"Junction Type: {junction_type} ({count})")
print()

print("=== INDIVIDUAL JUNCTIONS ===")
for i, junction in enumerate(junctions, 1):
    print(f"Junction {i}: {junction['type']} -> Panel {junction['connected_to']}")
