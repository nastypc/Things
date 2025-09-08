import xml.etree.ElementTree as ET
import uuid

# Create root
root = ET.Element("EHX")
ET.SubElement(root, "JobPath").text = "C:\\Test\\DummyJob"

# Add levels
levels = []
for i in range(1, 5):
    level = ET.SubElement(root, "Level")
    ET.SubElement(level, "LevelGuid").text = str(uuid.uuid4())
    ET.SubElement(level, "LevelNo").text = str(i)
    ET.SubElement(level, "Description").text = f"Level {i}"
    levels.append(level)

# Add bundles
bundles = []
for i in range(1, 11):
    bundle = ET.SubElement(root, "Bundle")
    bundle_guid = str(uuid.uuid4())
    ET.SubElement(bundle, "BundleGuid").text = bundle_guid
    ET.SubElement(bundle, "BundleName").text = f"B{i}"
    ET.SubElement(bundle, "Type").text = "Wall Panel Bundle"
    bundles.append((bundle_guid, f"B{i}"))

# Generate panels
panel_count = 0
bundle_panel_counts = [5, 8, 12, 18, 20, 15, 22, 10, 25, 30]  # Some >16

for level_idx, level in enumerate(levels, 1):
    level_no = level_idx
    level_guid = level.find("LevelGuid").text
    
    # Distribute bundles across levels
    for bundle_idx, (bundle_guid, bundle_name) in enumerate(bundles):
        num_panels = bundle_panel_counts[bundle_idx] // 4 + (1 if level_idx <= bundle_panel_counts[bundle_idx] % 4 else 0)
        
        for p in range(num_panels):
            panel = ET.SubElement(root, "Panel")
            panel_count += 1
            ET.SubElement(panel, "PanelGuid").text = str(uuid.uuid4())
            ET.SubElement(panel, "Label").text = f"{level_no:02d}_{panel_count:03d}"
            ET.SubElement(panel, "LevelGuid").text = level_guid
            ET.SubElement(panel, "LevelNo").text = str(level_no)
            ET.SubElement(panel, "Description").text = f"Panel {panel_count}"
            ET.SubElement(panel, "Height").text = "216.5"
            ET.SubElement(panel, "Thickness").text = "5.5"
            ET.SubElement(panel, "WallLength").text = "120.0"
            ET.SubElement(panel, "LoadBearing").text = "YES"
            ET.SubElement(panel, "Category").text = "Exterior"
            ET.SubElement(panel, "OnScreenInstruction").text = "Standard construction"
            ET.SubElement(panel, "Weight").text = "500.0"
            
            # Add bundle reference
            bundle_ref = ET.SubElement(panel, "Bundle")
            ET.SubElement(bundle_ref, "BundleGuid").text = bundle_guid
            ET.SubElement(bundle_ref, "BundleName").text = bundle_name
            ET.SubElement(bundle_ref, "BundleLayer").text = "1"
            
            # Add some basic board
            board = ET.SubElement(panel, "Board")
            ET.SubElement(board, "FamilyMemberName").text = "BottomPlate"
            ET.SubElement(board, "Label").text = "A"
            material = ET.SubElement(board, "Material")
            ET.SubElement(material, "Description").text = "2x6 SPF PM No.2"

# Write to file
tree = ET.ElementTree(root)
tree.write("dummy_multi_level.EHX", encoding="utf-8", xml_declaration=True)
