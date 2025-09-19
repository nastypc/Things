#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(__file__))

import Vold

# Enable debug mode
Vold.debug_enabled = True

# Test the function
ehx_path = r"c:\Users\edward\Downloads\EHX\Script\EHX\07_112.EHX"
panels, materials_map = Vold.parse_panels(ehx_path)

print(f"Found {len(panels)} panels")
print(f"Materials map has {len(materials_map)} entries")

# Test the analyze_subassemblies_for_panel function on the first panel
if panels:
    first_panel = panels[0]
    panel_name = first_panel.get('Name', '')
    print(f"Testing analyze_subassemblies_for_panel on panel: {panel_name}")
    print(f"Panel data: {first_panel}")

    result = Vold.analyze_subassemblies_for_panel(ehx_path, panel_name, materials_map)
    print(f"Result: {result}")
else:
    print("No panels found to test")
