#!/usr/bin/env python3
"""
Test script to verify squaring dimension parsing
"""
import xml.etree.ElementTree as ET

def inches_to_feet_inches_sixteenths(s):
    """Convert inches to feet-inches-sixteenths format"""
    try:
        inches = float(s)
        feet = int(inches // 12)
        remaining_inches = inches % 12
        sixteenths = int(round((remaining_inches % 1) * 16))
        whole_inches = int(remaining_inches)

        if sixteenths == 16:
            whole_inches += 1
            sixteenths = 0
        if whole_inches == 12:
            feet += 1
            whole_inches = 0

        if sixteenths == 0:
            return f"{feet}-{whole_inches}"
        else:
            return f"{feet}-{whole_inches}-{sixteenths}"
    except (ValueError, TypeError):
        return s

def test_squaring_parsing():
    # Parse the test EHX file
    tree = ET.parse(r'c:\Users\THOMPSON\Downloads\EHX\Working\Test\Test 2\MPO-L2-005008.EHX')
    root = tree.getroot()

    print("Testing squaring dimension parsing...")

    for panel_el in root.findall('.//Panel'):
        panel_guid = None
        panel_label = None

        # Get PanelGuid
        for t in ('PanelGuid', 'PanelID'):
            el = panel_el.find(t)
            if el is not None and el.text:
                panel_guid = el.text.strip()
                break

        # Get Label
        label_el = panel_el.find('Label')
        if label_el is not None and label_el.text:
            panel_label = label_el.text.strip()

        if not panel_label:
            panel_label = panel_guid

        print(f"\nPanel: {panel_label}")

        # Test squaring parsing
        squaring_value = None

        # Try nested structure first
        squaring_el = panel_el.find('Squaring')
        if squaring_el is not None:
            square_dim_el = squaring_el.find('SquareDimension')
            if square_dim_el is not None and square_dim_el.text:
                try:
                    square_inches = float(square_dim_el.text.strip())
                    squaring_value = inches_to_feet_inches_sixteenths(square_inches)
                    print(f"  Squaring (nested): {square_dim_el.text.strip()} in -> {squaring_value}")
                except (ValueError, TypeError):
                    squaring_value = square_dim_el.text.strip()
                    print(f"  Squaring (nested, raw): {squaring_value}")

        # Fallback to direct element
        if squaring_value is None:
            square_el = panel_el.find('SquareDimension')
            if square_el is not None and square_el.text:
                try:
                    square_inches = float(square_el.text.strip())
                    squaring_value = inches_to_feet_inches_sixteenths(square_inches)
                    print(f"  Squaring (direct): {square_el.text.strip()} in -> {squaring_value}")
                except (ValueError, TypeError):
                    squaring_value = square_el.text.strip()
                    print(f"  Squaring (direct, raw): {squaring_value}")

        if squaring_value is None:
            print("  No squaring dimension found")

        # Only show first few panels to avoid too much output
        if panel_guid and panel_guid.endswith('ff'):  # Just show a few panels
            break

if __name__ == "__main__":
    test_squaring_parsing()
