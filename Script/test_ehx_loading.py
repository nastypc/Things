#!/usr/bin/env python3
"""
Test script to check EHX file loading and panel names
"""

import sys
import os
import time
sys.path.append('.')

from ehx_search_widget import EHXSearchWidget
import tkinter as tk

def main():
    # Create widget without GUI
    root = tk.Tk()
    root.withdraw()
    widget = EHXSearchWidget(root)

    # Look for EHX files in the workspace
    ehx_files = []
    for root_dir, dirs, files in os.walk('c:/Users/edward/Downloads/EHX'):
        for file in files:
            if file.lower().endswith('.ehx'):
                ehx_files.append(os.path.join(root_dir, file))

    print(f'Found {len(ehx_files)} EHX files:')
    for f in ehx_files[:5]:  # Show first 5
        print(f'  {f}')

    if ehx_files:
        # Load the first EHX file
        test_file = ehx_files[0]
        print(f'\nLoading: {test_file}')
        success = widget.load_ehx_file(test_file)

        if success:
            # Wait a bit for loading to complete
            time.sleep(2)

            # Check what panels are loaded
            if hasattr(widget, 'search_data') and widget.search_data:
                panels = widget.search_data.get('panels', {})
                print(f'\nLoaded {len(panels)} panels:')
                for name in sorted(list(panels.keys())[:10]):  # Show first 10
                    print(f'  {name}')

                # Check if any panels contain '05-111' or '05-100'
                matching_05_111 = [name for name in panels.keys() if '05-111' in name]
                matching_05_100 = [name for name in panels.keys() if '05-100' in name]

                print(f'\nPanels containing "05-111": {len(matching_05_111)}')
                for name in matching_05_111[:5]:
                    print(f'  {name}')

                print(f'\nPanels containing "05-100": {len(matching_05_100)}')
                for name in matching_05_100[:5]:
                    print(f'  {name}')

                # Test the actual query processing
                print('\n--- Testing Query Processing ---')

                # Test "05-111 sub" query
                if matching_05_111:
                    test_panel = matching_05_111[0]
                    print(f'Testing query for panel: {test_panel}')

                    # Test the subassembly handler directly
                    result = widget._handle_subassembly_query(f'{test_panel.split("-")[1]} sub')
                    print(f'SubAssembly query result: {result[:200]}...')

                    # Test the FM handler directly
                    result = widget._handle_fm_query(f'{test_panel.split("-")[1]} fm')
                    print(f'FM query result: {result[:200]}...')

            else:
                print('No search data loaded')
        else:
            print('Failed to load EHX file')
    else:
        print('No EHX files found')

if __name__ == '__main__':
    main()
