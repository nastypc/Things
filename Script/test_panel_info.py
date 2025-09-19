#!/usr/bin/env python3
"""
Test the restructured panel info functionality
"""

import sys
sys.path.append('.')

from ehx_search_widget import EHXSearchWidget
import tkinter as tk

def test_panel_info():
    # Create root window (required for Tkinter components)
    root = tk.Tk()
    root.title("Test Panel Info")
    root.geometry("800x600")

    # Create widget
    widget = EHXSearchWidget(root)

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

                # Look for panel 05-100
                target_panel = None
                for panel_name in panels.keys():
                    if '05-100' in panel_name:
                        target_panel = panel_name
                        break

                if target_panel:
                    print(f'Found target panel: {target_panel}')

                    # Test the panel info command
                    print('\nTesting "05-100 info" command...')
                    result = widget._process_query('05-100 info')

                    print('=' * 80)
                    print('PANEL INFO RESULT:')
                    print('=' * 80)
                    print(result)
                    print('=' * 80)

                    # Check if all sections are present
                    sections = [
                        'Beam Pocket Details',
                        'SubAssembly Details',
                        'Critical Stud Details',
                        'Panel Material Breakdown'
                    ]

                    print('\nSECTION CHECK:')
                    for section in sections:
                        if section in result:
                            print(f'✅ {section}: FOUND')
                        else:
                            print(f'❌ {section}: MISSING')

                else:
                    print('Panel 05-100 not found')
                    print('Available panels:', list(panels.keys())[:10])

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
    test_panel_info()