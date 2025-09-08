import sys
sys.path.append('.')
from ehx_search_widget import EHXSearchWidget
import xml.etree.ElementTree as ET

# Test the search widget's panel parsing
def test_search_widget_bundle_detection():
    # Parse the problematic file
    tree = ET.parse('Working/Test/Test 2/SNO-L1-L2-005008.EHX')
    root = tree.getroot()
    
    # Simulate the search widget's panel indexing
    search_data = {
        'panels': {},
        'materials': {},
        'bundles': {},
        'tree': root,
        'ehx_version': 'legacy'
    }

    # Index panels (using the updated code)
    for panel in root.findall('.//Panel'):
        label = panel.find('Label')
        if label is not None and label.text:
            # Extract BundleName from various possible fields
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

    print(f"Indexed {len(search_data['panels'])} panels")

    # Test detect_unassigned_panels
    from ehx_search_widget import detect_unassigned_panels
    unassigned = detect_unassigned_panels(search_data['panels'])
    
    print(f"Unassigned panels: {len(unassigned)}")
    
    # Show a few panels with their bundle info
    count = 0
    for name, panel in search_data['panels'].items():
        if count < 5:
            print(f"Panel {name}: BundleName='{panel.get('BundleName', 'N/A')}', Level={panel.get('Level', 'N/A')}")
            count += 1

if __name__ == "__main__":
    test_search_widget_bundle_detection()
