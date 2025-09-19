#!/usr/bin/env python3
"""
Direct test of search logic
"""

import sys
sys.path.append('.')
import xml.etree.ElementTree as ET
from collections import defaultdict

def main():
    # Direct test of the search logic without GUI
    test_file = 'c:/Users/edward/Downloads/EHX/Script/EHX/SNO-L1-005008.EHX'
    print(f'Direct testing with: {test_file}')

    # Parse XML directly
    tree = ET.parse(test_file)
    root = tree.getroot()

    # Build search data manually (similar to widget's _build_search_indexes)
    search_data = {
        'panels': {},
        'materials': defaultdict(list),
        'bundles': {},
        'tree': root,
        'ehx_version': 'legacy'
    }

    # Index panels
    for panel in root.findall('.//Panel'):
        label = panel.find('Label')
        if label is not None and label.text:
            search_data['panels'][label.text] = {
                'guid': panel.find('PanelGuid').text if panel.find('PanelGuid') is not None else '',
                'bundle_guid': panel.find('BundleGuid').text if panel.find('BundleGuid') is not None else '',
                'level_guid': panel.find('LevelGuid').text if panel.find('LevelGuid') is not None else '',
                'BundleName': panel.find('BundleName').text if panel.find('BundleName') is not None else '',
                'Level': panel.find('LevelNo').text if panel.find('LevelNo') is not None else ''
            }

    print(f'Loaded {len(search_data["panels"])} panels')

    # Check for target panels
    target_panels = [name for name in search_data['panels'].keys() if '05-111' in name or '05-100' in name]
    print(f'Target panels found: {target_panels}')

    if target_panels:
        # Test panel matching logic
        print('\n--- Testing Panel Matching ---')

        # Simulate the _handle_subassembly_query logic
        query = '05-111 sub'
        panel_part = query.replace('sub', '').replace('subassembly', '').replace('sub assembly', '').strip()
        print(f'Query: {query}')
        print(f'Extracted panel part: {panel_part}')

        matching_panels = [name for name in search_data['panels'].keys() if panel_part in name.lower()]
        print(f'Matching panels: {matching_panels}')

        if matching_panels:
            panel_name = matching_panels[0]
            print(f'Using panel: {panel_name}')

            # Check if panel exists in search_data
            if panel_name in search_data['panels']:
                print('Panel found in search data ✓')
            else:
                print('Panel NOT found in search data ✗')

if __name__ == '__main__':
    main()
