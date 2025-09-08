import xml.etree.ElementTree as ET
from collections import defaultdict

def extract_junction_types(ehx_file_path):
    """Extract all junction types from an EHX file"""
    tree = ET.parse(ehx_file_path)
    root = tree.getroot()

    junction_types = defaultdict(int)
    subassembly_names = set()
    family_member_names = set()

    # Find all Junction elements
    for junction in root.findall('.//Junction'):
        # Extract SubAssemblyName
        sub_name_el = junction.find('SubAssemblyName')
        if sub_name_el is not None and sub_name_el.text:
            subassembly_names.add(sub_name_el.text.strip())

        # Extract FamilyMemberName
        fam_name_el = junction.find('FamilyMemberName')
        if fam_name_el is not None and fam_name_el.text:
            family_member_names.add(fam_name_el.text.strip())

        # Count junction types by combining both fields
        sub_name = sub_name_el.text.strip() if sub_name_el is not None and sub_name_el.text else "Unknown"
        fam_name = fam_name_el.text.strip() if fam_name_el is not None and fam_name_el.text else "Unknown"
        junction_type = f"{sub_name} -> {fam_name}"
        junction_types[junction_type] += 1

    return junction_types, subassembly_names, family_member_names

# Extract junction types from the EHX file
junction_types, subassembly_names, family_member_names = extract_junction_types('Working/Test/Test 2/SNO-L2-005008.EHX')

print("=== JUNCTION TYPES FOUND ===")
print(f"Total unique junction type combinations: {len(junction_types)}")
print()

print("=== SUBASSEMBLY NAMES ===")
for name in sorted(subassembly_names):
    print(f"  - {name}")
print()

print("=== FAMILY MEMBER NAMES ===")
for name in sorted(family_member_names):
    print(f"  - {name}")
print()

print("=== JUNCTION TYPE COMBINATIONS (with counts) ===")
for junction_type, count in sorted(junction_types.items()):
    print(f"  {junction_type}: {count} occurrences")
