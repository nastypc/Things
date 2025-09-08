import xml.etree.ElementTree as ET
from collections import defaultdict

def extract_junction_types(ehx_path):
    """Extract all junction types from an EHX file"""
    try:
        tree = ET.parse(ehx_path)
        root = tree.getroot()
    except Exception as e:
        print(f"Error parsing {ehx_path}: {e}")
        return

    junction_types = set()
    junction_details = []

    # Find all Junction elements
    for junction in root.findall('.//Junction'):
        subassembly_names = []

        # Extract all SubAssemblyName elements
        for sub_name in junction.findall('SubAssemblyName'):
            if sub_name is not None and sub_name.text:
                subassembly_names.append(sub_name.text.strip())

        if subassembly_names:
            # Create a key from all subassembly names
            junction_type = ' | '.join(subassembly_names)
            junction_types.add(junction_type)

            # Store detailed info
            junction_details.append({
                'type': junction_type,
                'subassemblies': subassembly_names,
                'panel_id': junction.find('PanelID').text if junction.find('PanelID') is not None else '',
                'label': junction.find('Label').text if junction.find('Label') is not None else '',
                'bundle_name': junction.find('BundleName').text if junction.find('BundleName') is not None else ''
            })

    return junction_types, junction_details

if __name__ == "__main__":
    ehx_file = "Working/Test/Test 2/SNO-L1-L2-005008.EHX"
    junction_types, junction_details = extract_junction_types(ehx_file)

    print(f"Found {len(junction_types)} unique junction types in {ehx_file}:")
    print("=" * 60)

    for i, jtype in enumerate(sorted(junction_types), 1):
        print(f"{i:2d}. {jtype}")

    print(f"\nTotal junctions: {len(junction_details)}")
    print("\nDetailed breakdown:")
    print("-" * 40)

    # Group by type for better overview
    type_counts = defaultdict(int)
    for detail in junction_details:
        type_counts[detail['type']] += 1

    for jtype, count in sorted(type_counts.items()):
        print(f"{jtype}: {count} junctions")
