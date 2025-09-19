#!/usr/bin/env python3
"""Test script for panel extraction functionality"""

import os
import sys

# Add the Script directory to the path so we can import Vold
sys.path.insert(0, r'c:\Users\edward\Downloads\EHX\Script')

from Vold import extract_panel_from_ehx

def test_panel_extraction():
    """Test the panel extraction functionality"""

    # Test with the SNO file and 05-100 panel
    source_file = r"c:\Users\edward\Downloads\EHX\Working\Levels\SNO-L1-005008.EHX"
    target_panel = "05-100"
    output_file = r"c:\Users\edward\Downloads\EHX\Script\05-100_test.ehx"

    print(f"Testing panel extraction...")
    print(f"Source: {source_file}")
    print(f"Target panel: {target_panel}")
    print(f"Output: {output_file}")

    # Check if source file exists
    if not os.path.exists(source_file):
        print(f"ERROR: Source file does not exist: {source_file}")
        return False

    # Extract the panel
    result = extract_panel_from_ehx(source_file, target_panel, output_file)

    if result and os.path.exists(result):
        print(f"SUCCESS: Panel extracted to {result}")
        print(f"Output file size: {os.path.getsize(result)} bytes")
        return True
    else:
        print(f"FAILED: Panel extraction failed")
        return False

if __name__ == "__main__":
    success = test_panel_extraction()
    sys.exit(0 if success else 1)