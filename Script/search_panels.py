#!/usr/bin/env python3
"""
Search for EHX files containing specific panel names
"""

import os
import xml.etree.ElementTree as ET

def main():
    # Search for EHX files containing panels with '05-111' or '05-100'
    target_panels = ['05-111', '05-100']

    print('Searching for EHX files containing panels with 05-111 or 05-100...')

    found_files = []
    for root_dir, dirs, files in os.walk('c:/Users/edward/Downloads/EHX'):
        for file in files:
            if file.lower().endswith('.ehx'):
                file_path = os.path.join(root_dir, file)
                try:
                    tree = ET.parse(file_path)
                    root = tree.getroot()

                    panels = root.findall('.//Panel')
                    file_panels = []

                    for panel in panels:
                        label = panel.find('Label')
                        if label is not None and label.text:
                            panel_name = label.text.strip()
                            file_panels.append(panel_name)

                            # Check if this panel matches our targets
                            for target in target_panels:
                                if target in panel_name:
                                    found_files.append({
                                        'file': file_path,
                                        'panel': panel_name,
                                        'target': target
                                    })

                    # If we found target panels, show some info
                    if found_files and found_files[-1]['file'] == file_path:
                        print(f'\nFound in {file}:')
                        for fp in file_panels[:5]:  # Show first 5 panels
                            print(f'  {fp}')

                except Exception as e:
                    pass  # Skip files that can't be parsed

    if found_files:
        print('\n=== TARGET PANELS FOUND ===')
        for item in found_files:
            print(f'File: {item["file"]}')
            print(f'Panel: {item["panel"]} (contains {item["target"]})')
            print()
    else:
        print('\nNo EHX files found containing panels with 05-111 or 05-100')

        # Show what panels we DID find
        print('\n=== SAMPLE PANELS FOUND ===')
        sample_files = []
        for root_dir, dirs, files in os.walk('c:/Users/edward/Downloads/EHX'):
            for file in files:
                if file.lower().endswith('.ehx'):
                    file_path = os.path.join(root_dir, file)
                    try:
                        tree = ET.parse(file_path)
                        root = tree.getroot()

                        panels = root.findall('.//Panel')
                        if panels:
                            sample_panels = []
                            for panel in panels[:3]:  # First 3 panels
                                label = panel.find('Label')
                                if label is not None and label.text:
                                    sample_panels.append(label.text.strip())

                            if sample_panels:
                                sample_files.append({
                                    'file': file_path,
                                    'panels': sample_panels
                                })

                    except:
                        pass

                    if len(sample_files) >= 5:  # Show 5 sample files
                        break

            if len(sample_files) >= 5:
                break

        for item in sample_files:
            print(f'File: {item["file"]}')
            print(f'Panels: {item["panels"]}')
            print()

if __name__ == '__main__':
    main()
