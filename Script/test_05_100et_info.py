#!/usr/bin/env python3
"""
Test script to demonstrate the restructured panel info display using 05-100ET.EHX
"""

import sys
import os
import time
import tkinter as tk
import math
from ehx_search_widget import EHXSearchWidget, inches_to_feet_inches_sixteenths

def main():
    # Create the main window
    root = tk.Tk()
    root.title("EHX Search Widget Test - 05-100ET.EHX")
    root.geometry("1200x800")

    # Create the widget
    widget = EHXSearchWidget(root)
    widget.pack(fill=tk.BOTH, expand=True)

    # Load the specific EHX file from Test folder
    ehx_file_path = os.path.join(os.path.dirname(__file__), "Test", "05-100ET.EHX")
    print(f"Loading: {ehx_file_path}")

    if not os.path.exists(ehx_file_path):
        print(f"ERROR: File not found: {ehx_file_path}")
        return

    # Load the file synchronously (avoid threading issues)
    try:
        # Read and parse the EHX file directly
        import xml.etree.ElementTree as ET
        
        print("Parsing EHX file...")
        tree = ET.parse(ehx_file_path)
        root_element = tree.getroot()
        
        # Initialize search_data
        widget.search_data = {
            'panels': {},
            'materials': {},
            'bundles': {},
            'tree': tree
        }
        
        # Extract panels
        for panel_el in root_element.findall('.//Panel'):
            panel_guid = panel_el.find('PanelGuid')
            panel_id = panel_el.find('PanelID')
            
            if panel_guid is not None and panel_guid.text:
                guid = panel_guid.text.strip()
                panel_name = panel_id.text.strip() if panel_id is not None and panel_id.text else guid[:8]
                
                # Extract panel info - matching the actual widget's logic
                panel_info = {
                    'guid': guid,
                    'bundle_guid': panel_el.find('BundleGuid').text if panel_el.find('BundleGuid') is not None else '',
                    'Level': panel_el.find('LevelNo').text if panel_el.find('LevelNo') is not None else '',
                    'Description': panel_el.find('Description').text if panel_el.find('Description') is not None else '',
                    'Category': 'Exterior',
                    'LoadBearing': 'YES',
                    'Weight': panel_el.find('Weight').text if panel_el.find('Weight') is not None else '',
                    'Thickness': panel_el.find('Thickness').text if panel_el.find('Thickness') is not None else '',
                    'StudSpacing': panel_el.find('StudSpacing').text if panel_el.find('StudSpacing') is not None else '',
                    'StudHeight': panel_el.find('StudHeight').text if panel_el.find('StudHeight') is not None else '',
                    'WallLength': panel_el.find('WallLength').text if panel_el.find('WallLength') is not None else '',
                    'Length': panel_el.find('WallLength').text if panel_el.find('WallLength') is not None else '',  # Alias for compatibility
                    'Height': panel_el.find('Height').text if panel_el.find('Height') is not None else '',
                    'ProductionNotes': ''
                }
                
                # Parse squaring dimension from SquareDimension element (nested under Squaring) - matching Vold script
                squaring_el = panel_el.find('Squaring')
                if squaring_el is not None:
                    square_dim_el = squaring_el.find('SquareDimension')
                    if square_dim_el is not None and square_dim_el.text:
                        try:
                            square_inches = float(square_dim_el.text.strip())
                            panel_info['Squaring_inches'] = square_inches  # Store raw inches
                            panel_info['Squaring'] = inches_to_feet_inches_sixteenths(square_inches)
                        except (ValueError, TypeError):
                            panel_info['Squaring'] = square_dim_el.text.strip()
                
                # Fallback: try direct SquareDimension element if nested structure not found
                if 'Squaring' not in panel_info:
                    square_el = panel_el.find('SquareDimension')
                    if square_el is not None and square_el.text:
                        try:
                            square_inches = float(square_el.text.strip())
                            panel_info['Squaring_inches'] = square_inches
                            panel_info['Squaring'] = inches_to_feet_inches_sixteenths(square_inches)
                        except (ValueError, TypeError):
                            panel_info['Squaring'] = square_el.text.strip()

                # Calculate squaring if not found using Pythagorean theorem (matching Vold script)
                if 'Squaring' not in panel_info:
                    if 'Height' in panel_info and 'WallLength' in panel_info:
                        try:
                            h = float(panel_info['Height']) - 1.5  # Subtract top plate
                            l = float(panel_info['WallLength'])
                            calc_inches = math.sqrt(h**2 + l**2)
                            panel_info['Squaring_inches'] = calc_inches  # Store raw inches
                            panel_info['Squaring'] = inches_to_feet_inches_sixteenths(calc_inches)
                        except (ValueError, TypeError):
                            # Fallback to a simple calculation function if available
                            try:
                                # calculate_squaring function not available, skip calculation
                                pass
                            except NameError:
                                # calculate_squaring function not available, skip calculation
                                pass
                
                widget.search_data['panels'][panel_name] = panel_info
        
        # Extract materials
        for board_el in root_element.findall('.//Board'):
            panel_guid_el = board_el.find('PanelGuid')
            material_el = board_el.find('Material')
            
            if panel_guid_el is not None and material_el is not None:
                panel_guid = panel_guid_el.text.strip()
                desc_el = material_el.find('Description')
                
                if desc_el is not None and desc_el.text:
                    desc = desc_el.text.strip()
                    
                    # Group by material type (simplified)
                    material_type = "Board"  # Default
                    
                    if not material_type in widget.search_data['materials']:
                        widget.search_data['materials'][material_type] = []
                    
                    widget.search_data['materials'][material_type].append({
                        'panel_guid': panel_guid,
                        'element': material_el
                    })
        
        print("EHX file parsed successfully")
        
    except Exception as e:
        print(f"ERROR: Failed to parse EHX file: {e}")
        return

    # Get available panels
    available_panels = list(widget.search_data['panels'].keys())
    print(f"Loaded {len(available_panels)} panels")
    print(f"All available panels: {available_panels}")

    # Find panels that match "05-100" or use the first available panel
    target_panels = [panel for panel in available_panels if '05' in panel and '100' in panel]
    if not target_panels:
        # If no panels match "05-100", use the first available panel and note this
        target_panels = available_panels[:1]
        print(f"No panels found matching '05-100', using first available panel: {target_panels[0]}")
        print("Note: This EHX file uses GUID-based panel names instead of descriptive names")
    else:
        print(f"Found target panels: {target_panels}")

    if not target_panels:
        print("No panels found in the file")
        return

    # Test the info command for the first matching panel
    test_panel = target_panels[0]
    print(f"Testing info command for panel: {test_panel}")

    # Check if panel exists in search_data
    panel_exists = test_panel in widget.search_data['panels']
    print(f"Panel exists in search_data: {panel_exists}")

    # Run the command using the actual panel name (GUID)
    command = f"{test_panel} info"
    print(f"Running command: \"{command}\"")
    print("Note: Using actual panel name from EHX file since '05-100' doesn't exist as a named panel")

    result = widget._process_query(command)

    print("=" * 100)
    print(f"PANEL INFO OUTPUT FOR {ehx_file_path}:")
    print("=" * 100)
    print(result)
    print("=" * 100)

    # Verify all sections are present
    print("\nSECTION VERIFICATION:")
    sections = [
        "Beam Pocket Details",
        "SubAssembly Details",
        "Critical Stud Details",
        "Panel Material Breakdown"
    ]

    for section in sections:
        found = section in result
        status = "✅ FOUND" if found else "❌ MISSING"
        print(f"{status} {section}")

    # Keep the window open for inspection
    print("\n" + "="*100)
    print("WINDOW IS OPEN - You can now see the GUI and test commands manually")
    print("Try typing '05-100 info' in the search box to see the restructured output")
    print("="*100)

    root.mainloop()

if __name__ == "__main__":
    main()