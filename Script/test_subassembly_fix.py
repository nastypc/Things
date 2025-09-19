#!/usr/bin/env python3
"""
Test script to verify the subassembly filtering fix
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from Vold import analyze_subassemblies_for_panel, parse_panels

def test_subassembly_fix():
    """Test that the subassembly filtering fix works correctly"""

    # Find an EHX file to test with
    ehx_files = []
    for file in os.listdir('.'):
        if file.endswith('.ehx') or file.endswith('.EHX'):
            ehx_files.append(file)

    if not ehx_files:
        print("No EHX files found in current directory")
        return

    # Use the first EHX file found
    ehx_file = ehx_files[0]
    print(f"Testing with EHX file: {ehx_file}")

    # Parse the panels
    panels, materials_map = parse_panels(ehx_file)

    if not panels:
        print("No panels found in EHX file")
        return

    # Test the first panel
    first_panel = panels[0]
    panel_name = first_panel.get('Name', first_panel.get('PanelGuid', 'Unknown'))
    panel_materials = materials_map.get(panel_name, [])

    print(f"Testing panel: {panel_name}")
    print(f"Panel has {len(panel_materials)} materials")

    # Call the analyze_subassemblies_for_panel function
    result = analyze_subassemblies_for_panel(ehx_file, panel_name, panel_materials)

    print(f"\nSubAssembly analysis result:")
    print(f"Found {len(result)} subassemblies:")

    for guid, info in result.items():
        name = info.get('name', 'Unknown')
        fm_id = info.get('family_member', 'Unknown')
        materials_count = len(info.get('materials', {}))
        print(f"  - {name} (FM{fm_id}) - {materials_count} materials - GUID: {guid[:8]}...")

    # Check if our target subassemblies are included
    critical_stud_found = any('Critical Stud' in info.get('name', '') for info in result.values())
    dr_ent_found = any('DR-9-ENT-L1' in info.get('name', '') for info in result.values())

    print("\nTarget subassemblies check:")
    print(f"  - Critical Stud (FM32): {'✓ FOUND' if critical_stud_found else '✗ NOT FOUND'}")
    print(f"  - DR-9-ENT-L1 (FM25): {'✓ FOUND' if dr_ent_found else '✗ NOT FOUND'}")

    if critical_stud_found and dr_ent_found:
        print("\n✅ SUCCESS: Both target subassemblies are now included!")
    else:
        print("\n❌ ISSUE: Some target subassemblies are still missing")

if __name__ == '__main__':
    test_subassembly_fix()