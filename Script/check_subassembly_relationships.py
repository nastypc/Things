#!/usr/bin/env python3
"""
Check SubAssembly-Board relationships
"""

import xml.etree.ElementTree as ET

def main():
    # Check the relationship between SubAssembly and Board PanelGuids
    test_file = 'c:/Users/edward/Downloads/EHX/Script/EHX/SNO-L1-005008.EHX'
    print(f'Checking SubAssembly-Board relationships in: {test_file}')

    tree = ET.parse(test_file)
    root = tree.getroot()

    # Get panel 05-111 GUID
    panels_05_111 = [p for p in root.findall('.//Panel') if p.find('Label') is not None and '05-111' in p.find('Label').text]
    if panels_05_111:
        panel = panels_05_111[0]
        panel_guid_el = panel.find('PanelGuid')
        if panel_guid_el is not None:
            target_panel_guid = panel_guid_el.text.strip()
            print(f'Target panel 05-111 GUID: {target_panel_guid}')

            # Find SubAssemblies that belong to this panel
            panel_subassemblies = []
            for sub_el in root.findall('.//SubAssembly'):
                sub_panel_guid_el = sub_el.find('PanelGuid')
                sub_panel_id_el = sub_el.find('PanelID')

                if sub_panel_guid_el is not None and sub_panel_guid_el.text == target_panel_guid:
                    fm_el = sub_el.find('FamilyMember')
                    if fm_el is not None and fm_el.text in ['25', '32', '42']:
                        sub_guid_el = sub_el.find('SubAssemblyGuid')
                        sub_name_el = sub_el.find('SubAssemblyName')

                        sub_guid = sub_guid_el.text if sub_guid_el is not None else ''
                        sub_name = sub_name_el.text if sub_name_el is not None else ''
                        fm = fm_el.text

                        panel_subassemblies.append({
                            'guid': sub_guid,
                            'name': sub_name,
                            'fm': fm
                        })

            print(f'\nFound {len(panel_subassemblies)} SubAssemblies for panel 05-111 with FM 25/32/42:')
            for sub in panel_subassemblies:
                print(f'  {sub["name"]} (FM{sub["fm"]}) - GUID: {sub["guid"][:8]}...')

            # For each SubAssembly, find its Board elements
            for sub in panel_subassemblies:
                print(f'\nSubAssembly: {sub["name"]} (FM{sub["fm"]})')

                # Find Board elements with this SubAssemblyGuid
                sub_boards = []
                for board_el in root.findall('.//Board'):
                    board_sub_guid_el = board_el.find('SubAssemblyGuid')
                    if board_sub_guid_el is not None and board_sub_guid_el.text == sub['guid']:
                        # Check if this board belongs to the target panel
                        board_panel_guid_el = board_el.find('PanelGuid')
                        board_panel_guid = board_panel_guid_el.text if board_panel_guid_el is not None else 'None'

                        sub_boards.append({
                            'panel_guid': board_panel_guid,
                            'belongs_to_target': board_panel_guid == target_panel_guid
                        })

                print(f'  Found {len(sub_boards)} Board elements with this SubAssemblyGuid')
                target_boards = [b for b in sub_boards if b['belongs_to_target']]
                print(f'  {len(target_boards)} belong to target panel 05-111')

                if sub_boards and not target_boards:
                    print(f'  WARNING: Boards found but none belong to target panel!')
                    for i, board in enumerate(sub_boards[:3]):
                        print(f'    Board {i+1} PanelGuid: {board["panel_guid"][:8]}...')

if __name__ == '__main__':
    main()
