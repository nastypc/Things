#!/usr/bin/env python3
"""
Test script to verify font scaling for single vs multiple bundles
"""

def test_font_scaling_scenarios():
    """Test font scaling for different bundle scenarios"""

    def calculate_font_size(displayed_cols, total_width=600):
        """Simulate the font scaling calculation"""
        cols_eff = max(1, min(8, displayed_cols))
        per_bundle_w = max(40, int((total_width - (cols_eff * 12)) / cols_eff))
        fw = max(7, min(12, per_bundle_w // 30))
        return fw, cols_eff, per_bundle_w

    print("Font scaling comparison:")
    print("=" * 50)

    # Test single bundle scenario
    fw1, cols1, width1 = calculate_font_size(1)
    print(f"Single bundle (1):")
    print(f"  cols_eff: {cols1}")
    print(f"  per_bundle_width: {width1}")
    print(f"  font_size: {fw1}")
    print()

    # Test multiple bundle scenario
    fw5, cols5, width5 = calculate_font_size(5)
    print(f"Multiple bundles (5):")
    print(f"  cols_eff: {cols5}")
    print(f"  per_bundle_width: {width5}")
    print(f"  font_size: {fw5}")
    print()

    print("Expected behavior:")
    print("- Single bundle should have larger buttons (font 12)")
    print("- Multiple bundles should have smaller buttons (font 7)")
    print("- This gives better readability for single bundle case")

if __name__ == "__main__":
    test_font_scaling_scenarios()
