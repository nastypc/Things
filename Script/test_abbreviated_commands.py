#!/usr/bin/env python3
"""
Test script to verify abbreviated commands work correctly
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from ehx_search_widget import EHXSearchWidget

def test_abbreviated_commands():
    """Test the abbreviated command functionality"""

    # Create a mock widget instance (without GUI)
    widget = EHXSearchWidget()

    # Mock some basic search data for testing
    widget.search_data = {
        'panels': {
            '05-112': {'guid': 'test-guid-112', 'bundle_guid': 'bundle-1'},
            '05-100': {'guid': 'test-guid-100', 'bundle_guid': 'bundle-2'}
        },
        'materials': {},
        'bundles': {},
        'tree': None
    }

    # Test cases for abbreviated commands
    test_cases = [
        ("112 info", "Should convert to 05-112 info and call comprehensive info"),
        ("112 fm", "Should convert to 05-112 fm and call family member analysis"),
        ("112 sub", "Should convert to 05-112 sub and call subassembly analysis"),
        ("112 poc", "Should convert to 05-112 poc and call beam pockets"),
        ("112 xstud", "Should convert to 05-112 xstud and call critical studs"),
        ("112 sheet", "Should convert to 05-112 sheet and call sheathing"),
        ("05-112 info", "Should work with already prefixed panel name"),
        ("100 fm", "Should work with different panel number")
    ]

    print("Testing abbreviated commands...")
    print("=" * 50)

    for query, description in test_cases:
        print(f"\nTesting: '{query}'")
        print(f"Expected: {description}")

        try:
            # Test the query processing (this will show if the method exists and is callable)
            result = widget._process_query(query)
            print(f"✓ Query processed successfully")
            print(f"  Result type: {type(result)}")
            if isinstance(result, str) and len(result) > 100:
                print(f"  Result preview: {result[:100]}...")
            else:
                print(f"  Result: {result}")

        except AttributeError as e:
            print(f"✗ AttributeError: {e}")
        except Exception as e:
            print(f"✗ Other error: {e}")

    print("\n" + "=" * 50)
    print("Test completed!")

if __name__ == "__main__":
    test_abbreviated_commands()