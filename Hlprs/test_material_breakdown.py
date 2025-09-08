#!/usr/bin/env python3
"""
Test script to verify material breakdown functionality when switching levels.
"""

import os
import sys
import tkinter as tk

# Add the current directory to the path so we can import the main module
sys.path.insert(0, os.path.dirname(__file__))

def test_material_breakdown():
    """Test that material breakdown works correctly when switching levels"""

    # Import the main GUI module
    import oldd

    # Create a test root window
    root = tk.Tk()
    root.title("Material Breakdown Test")
    root.geometry("1200x800")

    # Initialize the GUI (this will create all the necessary variables and functions)
    oldd.init_gui(root)

    # Load a test file that has multiple levels
    test_file = r"c:\Users\THOMPSON\Downloads\EHX\Working\Test\Test 2\MPO-L1-L2-005008.EHX"

    if os.path.exists(test_file):
        print(f"Loading test file: {test_file}")
        oldd.load_ehx_file(test_file)

        # Wait a bit for the file to load
        root.after(2000, lambda: test_level_switching(root))
    else:
        print(f"Test file not found: {test_file}")

    # Start the GUI event loop
    root.mainloop()

def test_level_switching(root):
    """Test switching between levels and check material breakdown"""

    print("Testing level switching...")

    # Get current state
    print(f"Current level: {oldd.selected_level['value']}")
    print(f"Current panels count: {len(oldd.current_panels)}")
    print(f"Current materials count: {len(oldd.panel_materials_map)}")

    # Try to switch to level 1
    if oldd.selected_level['value'] != 1:
        print("Switching to level 1...")
        oldd.select_level(1)
        root.after(1000, lambda: check_level_1(root))
    else:
        check_level_1(root)

def check_level_1(root):
    """Check the state after switching to level 1"""

    print("Level 1 state:")
    print(f"Current level: {oldd.selected_level['value']}")
    print(f"Current panels count: {len(oldd.current_panels)}")
    print(f"Current materials count: {len(oldd.panel_materials_map)}")

    # Try to select the first panel and check materials
    if oldd.current_panels:
        first_panel_name = list(oldd.current_panels.keys())[0]
        print(f"Selecting first panel: {first_panel_name}")

        # Simulate panel selection
        oldd.on_panel_selected(first_panel_name)

        # Check if materials are available
        materials = oldd.panel_materials_map.get(first_panel_name, [])
        print(f"Materials for {first_panel_name}: {len(materials)} items")

        if materials:
            print("First few materials:")
            for i, mat in enumerate(materials[:3]):
                print(f"  {i+1}: {mat.get('Label', 'N/A')} - {mat.get('Type', 'N/A')}")

    # Switch to level 2
    root.after(1000, lambda: switch_to_level_2(root))

def switch_to_level_2(root):
    """Switch to level 2 and test"""

    print("Switching to level 2...")
    oldd.select_level(2)
    root.after(1000, lambda: check_level_2(root))

def check_level_2(root):
    """Check the state after switching to level 2"""

    print("Level 2 state:")
    print(f"Current level: {oldd.selected_level['value']}")
    print(f"Current panels count: {len(oldd.current_panels)}")
    print(f"Current materials count: {len(oldd.panel_materials_map)}")

    # Try to select the first panel in level 2
    if oldd.current_panels:
        first_panel_name = list(oldd.current_panels.keys())[0]
        print(f"Selecting first panel in level 2: {first_panel_name}")

        # Simulate panel selection
        oldd.on_panel_selected(first_panel_name)

        # Check if materials are available
        materials = oldd.panel_materials_map.get(first_panel_name, [])
        print(f"Materials for {first_panel_name}: {len(materials)} items")

        if materials:
            print("First few materials:")
            for i, mat in enumerate(materials[:3]):
                print(f"  {i+1}: {mat.get('Label', 'N/A')} - {mat.get('Type', 'N/A')}")
        else:
            print("WARNING: No materials found for panel in level 2!")
    else:
        print("WARNING: No panels found in level 2!")

    # Switch back to level 1
    root.after(1000, lambda: switch_back_to_level_1(root))

def switch_back_to_level_1(root):
    """Switch back to level 1 and verify materials are still there"""

    print("Switching back to level 1...")
    oldd.select_level(1)
    root.after(1000, lambda: check_level_1_return(root))

def check_level_1_return(root):
    """Check that materials are still available when returning to level 1"""

    print("Back to level 1 state:")
    print(f"Current level: {oldd.selected_level['value']}")
    print(f"Current panels count: {len(oldd.current_panels)}")
    print(f"Current materials count: {len(oldd.panel_materials_map)}")

    if oldd.current_panels:
        first_panel_name = list(oldd.current_panels.keys())[0]
        print(f"Re-checking first panel: {first_panel_name}")

        # Check if materials are still available
        materials = oldd.panel_materials_map.get(first_panel_name, [])
        print(f"Materials for {first_panel_name} (after returning): {len(materials)} items")

        if materials:
            print("SUCCESS: Materials are preserved when switching levels!")
        else:
            print("ERROR: Materials were lost when switching levels!")
    else:
        print("ERROR: No panels found when returning to level 1!")

    # Close the test
    root.after(2000, root.quit)

if __name__ == "__main__":
    test_material_breakdown()
