#!/usr/bin/env python3
"""
Test script for the new FM grouped display functionality
"""

import sys
import os
import xml.etree.ElementTree as ET
from collections import defaultdict
sys.path.append(os.path.dirname(__file__))

from ehx_search_widget import EHXSearchWidget
import tkinter as tk

def test_fm_grouped_display_direct():
    """Test the new grouped FM display functionality with direct XML loading"""
    print("Testing FM grouped display functionality (direct loading)...")

    # Test EHX file path
    test_file = r"c:\Users\edward\Downloads\EHX\Working\Levels\SNO-L2-005008.EHX"

    if not os.path.exists(test_file):
        print(f"❌ Test file not found: {test_file}")
        return

    print(f"Loading test file: {test_file}")

    try:
        # Load XML directly
        tree = ET.parse(test_file)
        root = tree.getroot()

        # Create a mock search_data structure (similar to what the widget creates)
        search_data = {
            'panels': {},
            'materials': defaultdict(list),
            'bundles': {},
            'tree': root,
            'ehx_version': 'legacy'
        }

        # Index panels (copied from widget)
        for panel in root.findall('.//Panel'):
            label = panel.find('Label')
            if label is not None and label.text:
                bundle_name = None
                for field in ('BundleName', 'Bundle', 'BundleLabel'):
                    bundle_el = panel.find(field)
                    if bundle_el is not None and bundle_el.text:
                        bundle_name = bundle_el.text.strip()
                        break

                search_data['panels'][label.text] = {
                    'guid': panel.find('PanelGuid').text if panel.find('PanelGuid') is not None else '',
                    'bundle_guid': panel.find('BundleGuid').text if panel.find('BundleGuid') is not None else '',
                    'level_guid': panel.find('LevelGuid').text if panel.find('LevelGuid') is not None else '',
                    'BundleName': bundle_name or '',
                    'Level': panel.find('LevelNo').text if panel.find('LevelNo') is not None else ''
                }

        # Index materials (copied from widget)
        for board in root.findall('.//Board'):
            search_data['materials']['Board'].append({
                'type': 'Board',
                'element': board,
                'panel_guid': board.find('PanelGuid').text if board.find('PanelGuid') is not None else '',
                'guid': board.find('BoardGuid').text if board.find('BoardGuid') is not None else ''
            })

        for sheet in root.findall('.//Sheet'):
            search_data['materials']['Sheet'].append({
                'type': 'Sheet',
                'element': sheet,
                'panel_guid': sheet.find('PanelGuid').text if sheet.find('PanelGuid') is not None else '',
                'guid': sheet.find('SheetGuid').text if sheet.find('SheetGuid') is not None else ''
            })

        print("✅ EHX file loaded successfully")
        print(f"Found {len(search_data['panels'])} panels")

        # Create a minimal Tkinter root for the widget
        root = tk.Tk()
        root.withdraw()

        # Create search widget and set search_data directly
        search_widget = EHXSearchWidget(root)
        search_widget.search_data = search_data

        # Test the new grouped FM display
        result = search_widget._get_panel_fm_grouped("05-208")
        print("\n" + "="*80)
        print("TEST RESULT - Grouped FM Display for panel 05-208:")
        print("="*80)
        print(result)
        print("="*80)

        # Also test the FM query handler
        fm_query_result = search_widget._handle_fm_query("05-208 fm")
        print("\n" + "="*80)
        print("TEST RESULT - FM Query Handler for '05-208 fm':")
        print("="*80)
        print(fm_query_result)
        print("="*80)

        # Clean up
        root.destroy()

    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()

    print("\nTest completed!")

if __name__ == "__main__":
    test_fm_grouped_display_direct()