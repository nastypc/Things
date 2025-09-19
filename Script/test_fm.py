#!/usr/bin/env python3
import xml.etree.ElementTree as ET
from pathlib import Path
from collections import defaultdict

# Direct test of FM functionality without Tkinter
def test_fm_functionality():
    ehx_file = 'EHX/SNO-L1-005008.EHX'

    # Load and parse XML directly
    tree = ET.parse(ehx_file)
    root = tree.getroot()

    # Build search data like the widget does
    search_data = {'panels': {}, 'materials': defaultdict(list), 'tree': root}

    # Index panels
    for panel in root.findall('.//Panel'):
        label = panel.find('Label')
        if label is not None and label.text:
            search_data['panels'][label.text] = {
                'guid': panel.find('PanelGuid').text if panel.find('PanelGuid') is not None else '',
                'bundle_guid': panel.find('BundleGuid').text if panel.find('BundleGuid') is not None else '',
            }

    print('Loaded panels:', len(search_data['panels']))
    print('Available panels:', list(search_data['panels'].keys())[:10])

    # Test FM query for 05-111
    panel_name = '05-111'
    if panel_name not in search_data['panels']:
        print('Panel', panel_name, 'not found')
        return

    panel_info = search_data['panels'][panel_name]
    print()
    print('Testing FM analysis for panel:', panel_name)
    print('Panel GUID:', panel_info['guid'][:8] + '...')

    # Collect Family Member data (similar to _get_panel_family_members)
    family_members = defaultdict(lambda: {
        'count': 0,
        'descriptions': [],
        'labels': [],
        'types': set()
    })

    # Look for Board elements that belong to this panel
    for board_el in root.findall('.//Board'):
        # Check if this board belongs to the target panel
        panel_guid_el = board_el.find('PanelGuid')
        if panel_guid_el is not None and panel_guid_el.text == panel_info['guid']:

            # Get Family Member information
            fm_el = board_el.find('FamilyMember')
            fm_name_el = board_el.find('FamilyMemberName')
            label_el = board_el.find('Label')
            material_el = board_el.find('Material')

            fm = fm_el.text.strip() if fm_el is not None and fm_el.text else ''
            fm_name = fm_name_el.text.strip() if fm_name_el is not None and fm_name_el.text else ''
            label = label_el.text.strip() if label_el is not None and label_el.text else ''

            # Get material description
            description = ''
            if material_el is not None:
                desc_el = material_el.find('Description')
                description = desc_el.text.strip() if desc_el is not None and desc_el.text else ''

            # Skip if no Family Member info
            if not fm and not fm_name:
                continue

            # Use FM number as key, fallback to FM name
            key = fm if fm else fm_name

            family_members[key]['count'] += 1
            if description:
                family_members[key]['descriptions'].append(description)
            if label:
                family_members[key]['labels'].append(label)
            if fm_name:
                family_members[key]['types'].add(fm_name)

    if not family_members:
        print('No Family Members found for this panel')
        return

    print()
    print('Found', len(family_members), 'Family Members:')

    # Display results
    for fm_id in sorted(family_members.keys(), key=lambda x: (x.isdigit(), x)):
        info = family_members[fm_id]
        count = info['count']
        descriptions = info['descriptions']
        labels = info['labels']
        types = info['types']

        # Get FM name mapping
        fm_names = {
            '25': 'Openings',
            '32': 'LType',
            '42': 'Ladder'
        }
        fm_display_name = fm_names.get(fm_id, 'FM' + fm_id)

        print()
        print('FAMILY MEMBER', fm_id, '(' + fm_display_name + '):')
        print('  Total Parts:', count)

        # Show types
        if types:
            print('  Types:', list(types))

        # Show unique descriptions
        if descriptions:
            unique_descriptions = list(set(descriptions))
            print('  Material Descriptions (' + str(len(unique_descriptions)) + '):')
            for desc in sorted(unique_descriptions):
                desc_count = descriptions.count(desc)
                print('    •', desc + ':', desc_count, 'pieces')

        # Show labels if available
        if labels:
            unique_labels = list(set(labels))
            print('  Labels (' + str(len(unique_labels)) + '):')
            for lbl in sorted(unique_labels):
                lbl_count = labels.count(lbl)
                print('    •', lbl + ':', lbl_count, 'pieces')

if __name__ == '__main__':
    test_fm_functionality()
