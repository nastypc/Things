import sys
sys.path.append('.')
from oldd import parse_panels, detect_unassigned_panels

# Parse the problematic file
panels, materials_map = parse_panels('Working/Test/Test 2/SNO-L1-L2-005008.EHX')

# Create panels_by_name dict
panels_by_name = {}
for p in panels:
    if isinstance(p, dict):
        panels_by_name[p.get('Name', f'Panel_{len(panels_by_name)}')] = p

print(f'Total panels: {len(panels_by_name)}')

# Check a few panels
count = 0
for name, panel in panels_by_name.items():
    if count < 5:
        bundle_name = panel.get('BundleName') or panel.get('Bundle') or panel.get('BundleLabel') or ''
        print(f'Panel {name}: BundleName="{bundle_name}", Level={panel.get("Level", "Unknown")}')
        count += 1

# Run detect_unassigned_panels
unassigned = detect_unassigned_panels(panels_by_name)
print(f'Unassigned panels: {len(unassigned)}')
for u in unassigned[:5]:
    print(f'Unassigned: {u["name"]} - {u["bundle"]}')
