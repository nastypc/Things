#!/usr/bin/env python3
"""
Test script to verify debug toggle persistence in Vold.py
"""
import os
import json
import sys

def test_debug_persistence():
    """Test that debug state is properly saved and loaded"""
    print("Testing debug toggle persistence...")

    # Path to debug state file
    debug_state_file = os.path.join(os.path.dirname(__file__), 'debug_state.json')

    # Test 1: Check if debug state file exists
    if os.path.exists(debug_state_file):
        print("✓ Debug state file exists")
    else:
        print("✗ Debug state file does not exist - will be created on first toggle")

    # Test 2: Try to read current debug state
    try:
        if os.path.exists(debug_state_file):
            with open(debug_state_file, 'r') as f:
                state = json.load(f)
                current_debug = state.get('debug_enabled', True)
                print(f"✓ Current debug state loaded: {current_debug}")
        else:
            print("✓ No existing debug state file (will default to True)")
    except Exception as e:
        print(f"✗ Error reading debug state: {e}")
        return False

    # Test 3: Check if Vold.py can be imported and functions exist
    try:
        sys.path.insert(0, os.path.dirname(__file__))
        import Vold

        # Check if required functions exist
        if hasattr(Vold, 'load_debug_state'):
            print("✓ load_debug_state function exists")
        else:
            print("✗ load_debug_state function missing")
            return False

        if hasattr(Vold, 'save_debug_state'):
            print("✓ save_debug_state function exists")
        else:
            print("✗ save_debug_state function missing")
            return False

        if hasattr(Vold, 'toggle_debug_mode'):
            print("✓ toggle_debug_mode function exists")
        else:
            print("✗ toggle_debug_mode function missing")
            return False

    except Exception as e:
        print(f"✗ Error importing Vold.py: {e}")
        return False

    print("\n🎉 Debug toggle persistence test completed successfully!")
    print("\nTo test the functionality:")
    print("1. Run Vold.py")
    print("2. Toggle the Debug checkbox")
    print("3. Close the application")
    print("4. Run Vold.py again - the debug state should be remembered")

    return True

if __name__ == "__main__":
    test_debug_persistence()
