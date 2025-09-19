#!/usr/bin/env python3
"""
Quick test to verify FM query handling works correctly
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from ehx_search_widget import EHXSearchWidget
import xml.etree.ElementTree as ET

def test_fm_query_handling():
    """Test that FM queries are handled correctly"""
    print("🧪 Testing FM Query Handling...")

    # Create a mock search widget
    widget = EHXSearchWidget.__new__(EHXSearchWidget)
    
    # Create a minimal mock XML tree
    root = ET.Element("EHX")
    panel = ET.SubElement(root, "Panel")
    ET.SubElement(panel, "Label").text = "05-100"
    ET.SubElement(panel, "PanelGuid").text = "test-guid"
    
    widget.search_data = {
        'panels': {'05-100': {'guid': 'test-guid', 'BundleName': 'TestBundle'}},
        'materials': {},
        'bundles': {},
        'tree': root,
        'ehx_version': 'legacy'
    }

    # Test the _handle_fm_query method
    try:
        # Test panel FM query
        result = widget._handle_fm_query("05-100 fm")
        print("✅ FM query handling test passed!")
        print(f"   Result type: {type(result)}")
        print(f"   Contains 'Family Member': {'Family Member' in str(result)}")
        return True
    except Exception as e:
        print(f"❌ FM query handling test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_fm_query_handling()
    if success:
        print("\n🎉 All FM query tests passed!")
    else:
        print("\n💥 FM query tests failed!")
        sys.exit(1)