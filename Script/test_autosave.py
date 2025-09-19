#!/usr/bin/env python3
"""
Test autosave functionality
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from ehx_search_widget import EHXSearchWidget
import xml.etree.ElementTree as ET

def test_autosave_functionality():
    """Test that autosave functionality works correctly"""
    print("🧪 Testing Autosave Functionality...")

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

    # Mock the results text widget
    class MockText:
        def get(self, start, end):
            return "Test search results for autosave functionality"

    widget.results_text = MockText()

    # Test the autosave functionality
    try:
        result = widget._auto_export_to_text()
        print("✅ Autosave functionality test passed!")
        print(f"   Result: {result}")
        print(f"   Contains 'auto-exported': {'auto-exported' in str(result)}")
        return True
    except Exception as e:
        print(f"❌ Autosave functionality test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_autosave_functionality()
    if success:
        print("\n🎉 All autosave tests passed!")
    else:
        print("\n💥 Autosave tests failed!")
        sys.exit(1)