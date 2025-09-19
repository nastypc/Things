#!/usr/bin/env python3
"""
Test the search widget in proper GUI context
"""

import sys
sys.path.append('.')

from ehx_search_widget import EHXSearchWidget
import tkinter as tk
import time

def test_widget():
    # Create root window
    root = tk.Tk()
    root.title("Test EHX Widget")
    root.geometry("800x600")

    # Create widget
    widget = EHXSearchWidget(root)
    widget.pack(fill=tk.BOTH, expand=True)

    # Load test file
    test_file = 'c:/Users/edward/Downloads/EHX/Script/EHX/SNO-L1-005008.EHX'
    print(f'Loading: {test_file}')

    success = widget.load_ehx_file(test_file)

    if success:
        print('File loaded successfully, waiting for processing...')

        # Wait for loading to complete
        def check_loaded():
            if hasattr(widget, 'search_data') and widget.search_data:
                panels = widget.search_data.get('panels', {})
                print(f'Loaded {len(panels)} panels')

                target_panels = [name for name in panels.keys() if '05-111' in name or '05-100' in name]
                print(f'Target panels: {target_panels}')

                if target_panels:
                    # Test queries
                    print('\nTesting queries...')

                    # Test SubAssembly
                    result = widget._process_query('05-111 sub')
                    print(f'SubAssembly result: {result[:200]}...')

                    # Test FM
                    result = widget._process_query('05-100 fm')
                    print(f'FM result: {result[:200]}...')

                # Close after testing
                root.after(1000, root.quit)
            else:
                # Check again in 1 second
                root.after(1000, check_loaded)

        root.after(2000, check_loaded)
    else:
        print('Failed to load file')
        root.after(1000, root.quit)

    # Start main loop
    root.mainloop()

if __name__ == '__main__':
    test_widget()
