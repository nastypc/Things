#!/usr/bin/env python3
"""
Test script to verify button font scaling for different bundle counts
"""

def test_font_scaling():
    """Test the font scaling logic for different numbers of bundles"""

    def calculate_font_size(displayed_cols, total_width=600):
        """Simulate the font scaling calculation"""
        cols_eff = max(1, min(8, displayed_cols))
        per_bundle_w = max(40, int((total_width - (cols_eff * 12)) / cols_eff))
        fw = max(7, min(12, per_bundle_w // 30))
        return fw

    print("Font scaling test for different bundle counts:")
    print("Bundles | Columns | Per-bundle width | Font size")
    print("--------|---------|------------------|-----------")

    for bundles in [1, 2, 3, 4, 5, 6]:
        cols_eff = max(1, min(8, bundles))
        per_bundle_w = max(40, int((600 - (cols_eff * 12)) / cols_eff))
        font_size = max(7, min(12, per_bundle_w // 30))
        print(f"{bundles:5d}   |   {cols_eff:5d}   |      {per_bundle_w:5d}      |    {font_size:5d}")

    print("\nThis shows that fewer bundles = larger buttons = larger font")
    print("So page 2 with 1 bundle should have the largest font size!")

if __name__ == "__main__":
    test_font_scaling()
