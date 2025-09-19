#!/usr/bin/env python3
"""
Test script to verify dynamic prefix extraction and abbreviated commands
"""

import tkinter as tk
from ehx_search_widget import EHXSearchWidget
import time

def test_prefix_extraction():
    """Test that prefix extraction works correctly"""
    root = tk.Tk()
    root.title("EHX Search Widget Test")

    # Create the widget
    widget = EHXSearchWidget(root)

    # Test prefix extraction logic directly
    test_files = [
        ("07_112.EHX", "07"),
        ("08_100.EHX", "08"),
        ("05_200.EHX", "05"),
        ("test.EHX", "05"),  # Should default to 05
    ]

    print("Testing prefix extraction:")
    for filename, expected_prefix in test_files:
        # Simulate the extraction logic
        if '_' in filename:
            prefix_part = filename.split('_')[0]
            if prefix_part.isdigit() and len(prefix_part) == 2:
                extracted_prefix = prefix_part
            else:
                extracted_prefix = '05'
        else:
            extracted_prefix = '05'

        status = "✓" if extracted_prefix == expected_prefix else "✗"
        print(f"  {status} {filename} -> {extracted_prefix} (expected: {expected_prefix})")

    # Test loading the actual file
    ehx_path = r"c:\Users\edward\Downloads\EHX\Script\EHX\07_112.EHX"
    print(f"\nLoading EHX file: {ehx_path}")

    success = widget.load_ehx_file(ehx_path)
    if success:
        print("✓ File loaded successfully")

        # Wait for loading to complete
        root.update()
        time.sleep(2)  # Give time for background loading
        root.update()

        # Check if prefix was extracted correctly
        if hasattr(widget, 'panel_prefix'):
            print(f"✓ Extracted prefix: {widget.panel_prefix} (expected: 07)")
            if widget.panel_prefix == "07":
                print("✓ Prefix extraction working correctly!")
            else:
                print("✗ Prefix extraction failed!")
        else:
            print("✗ panel_prefix attribute not found")

        # Test abbreviated command
        print("\nTesting abbreviated command '112 info':")
        widget.search_var.set("112 info")
        widget._perform_search()
        root.update()

        # Check results
        results_text = widget.results_text.get(1.0, tk.END)
        if "07-112" in results_text or "07_112" in results_text:
            print("✓ Abbreviated command '112 info' worked correctly!")
        else:
            print("✗ Abbreviated command '112 info' failed")
            print("Results preview:", results_text[:500])

    else:
        print("✗ Failed to load EHX file")

    root.destroy()

if __name__ == "__main__":
    test_prefix_extraction()