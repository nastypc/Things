#!/usr/bin/env python3
"""
Test the search widget with target panels
"""

import sys
sys.path.append('.')

from ehx_search_widget import EHXSearchWidget
import tkinter as tk
import time
import threading

def main():
    # Test with a file that has the target panels
    test_file = 'c:/Users/edward/Downloads/EHX/Script/EHX/SNO-L1-005008.EHX'
    print(f'Testing with file containing target panels: {test_file}')

    # Create widget with GUI but don't show it
    root = tk.Tk()
    root.withdraw()
    widget = EHXSearchWidget(root)

    # Load the file
    print('Loading EHX file...')
    success = widget.load_ehx_file(test_file)

    if success:
        # Start the main loop in a separate thread to handle GUI updates
        def run_mainloop():
            try:
                root.mainloop()
            except:
                pass

        mainloop_thread = threading.Thread(target=run_mainloop, daemon=True)
        mainloop_thread.start()

        # Wait for loading to complete
        time.sleep(5)

        # Check if data was loaded
        if hasattr(widget, 'search_data') and widget.search_data:
            panels = widget.search_data.get('panels', {})
            print(f'Successfully loaded {len(panels)} panels')

            # Check for our target panels
            target_panels = [name for name in panels.keys() if '05-111' in name or '05-100' in name]
            print(f'Target panels found: {target_panels}')

            if target_panels:
                # Test the queries
                print('\n--- Testing Queries ---')

                # Test SubAssembly query
                print('Testing "05-111 sub" query...')
                result = widget._process_query('05-111 sub')
                print(f'Result: {result[:300]}...')

                # Test FM query
                print('\nTesting "05-100 fm" query...')
                result = widget._process_query('05-100 fm')
                print(f'Result: {result[:300]}...')

            else:
                print('Target panels not found in loaded data')
        else:
            print('No search data loaded')

        # Stop the main loop
        root.quit()
    else:
        print('Failed to load EHX file')

if __name__ == '__main__':
    main()
