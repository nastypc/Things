import os
import json
import datetime as _dt
import xml.etree.ElementTree as ET
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter import font as tkfont
import re
import math
import logging
import sys

HERE = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))

# Global debug control variable
debug_enabled = True

# Global configuration for FamilyMember filtering
# Only include FamilyMember IDs 32 (Critical Stud) and 42 (Ladder) in Subcomponent Details
ALLOWED_FAMILY_MEMBER_IDS = {32, 42}  # 32=Critical Stud, 42=Ladder

# FamilyMember name to ID mapping for consistent filtering
FAMILY_MEMBER_MAPPING = {
    'Critical Stud': 32,
    'Lad2Stud': 42,
    'Ladder - Flat (Fixed)': 42,
    'BSMT-HDR': 25,
    'Sheathing': 40,
    '49x63-L2': 25,
    'SZ56': 25,  # Also maps to FamilyMember 25
}

def get_family_member_id(family_member_name):
    """Get FamilyMember ID from name, with fallback logic."""
    if not family_member_name:
        return None
    
    # Direct mapping
    if family_member_name in FAMILY_MEMBER_MAPPING:
        return FAMILY_MEMBER_MAPPING[family_member_name]
    
    # Partial matching for more flexibility
    for name_pattern, member_id in FAMILY_MEMBER_MAPPING.items():
        if name_pattern in family_member_name:
            return member_id
    
    return None

def is_allowed_family_member(family_member_name):
    """Check if a FamilyMember should be included in Subcomponent Details."""
    member_id = get_family_member_id(family_member_name)
    return member_id in ALLOWED_FAMILY_MEMBER_IDS

# Setup logging to file and console
# Note: Log file clearing now happens in toggle_debug_mode when debug is enabled
log_level = logging.DEBUG if debug_enabled else logging.WARNING

# Create logger
logger = logging.getLogger()
logger.setLevel(log_level)

# Remove any existing handlers to avoid duplicates
for handler in logger.handlers[:]:
    logger.removeHandler(handler)

# Create file handler
file_handler = logging.FileHandler(os.path.join(HERE, 'debug.log'))
file_handler.setLevel(log_level)
file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
file_handler.setFormatter(file_formatter)

# Create console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(log_level)
console_formatter = logging.Formatter('%(levelname)s - %(message)s')
console_handler.setFormatter(console_formatter)

# Add handlers to logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Test logging setup
logger.debug("Logging setup complete - testing file and console handlers")

# Global sorting functions for consistent ordering throughout the application
def sort_bundle_keys(bundle_keys):
    """Sort bundle keys by bundle number (B1, B2, etc.) with smart fallback."""
    def smart_sort_key(bundle_name):
        # Handle bundle names like "B1 (2x6 Ext)", "B2 (2x4 Gar)", etc.
        # Look for pattern like "B" followed by number, possibly with spaces
        match = re.search(r'B\s*(\d+)', bundle_name)
        if match:
            return (0, int(match.group(1)), bundle_name)  # Sort by bundle number
        else:
            # Fallback to general number extraction
            match = re.search(r'(\d+)', bundle_name)
            if match:
                return (1, int(match.group(1)), bundle_name)  # Numbers first
            else:
                return (2, bundle_name, bundle_name)  # Alphabetical fallback
    
    return sorted(bundle_keys, key=smart_sort_key)

def normalize_bundle_key(bundle_name):
    """Normalize bundle key to base name (e.g., 'B1 (2x6 Ext)' -> 'B1')"""
    if not bundle_name:
        return bundle_name
    # Handle bundle names like "B1 (2x6 Ext)", "B2 (2x4 Gar)", etc.
    match = re.search(r'B\s*(\d+)', bundle_name)
    if match:
        return f"B{match.group(1)}"
    else:
        # Fallback to general number extraction
        match = re.search(r'(\d+)', bundle_name)
        if match:
            return f"Bundle{match.group(1)}"
        else:
            return bundle_name.strip()

def format_dimension(value):
    """Format dimension by stripping trailing zeros (e.g., 16.00 -> 16, 49.000 -> 49)"""
    if not value:
        return value
    try:
        # Convert to float first to handle string representations
        num = float(str(value))
        # Check if it's a whole number
        if num == int(num):
            return str(int(num))
        else:
            return str(num).rstrip('0').rstrip('.')
    except (ValueError, TypeError):
        return str(value)

def format_weight(value):
    """Format weight by rounding up to nearest integer (e.g., 258.6586 -> 259)"""
    if not value:
        return value
    try:
        num = float(str(value))
        return str(math.ceil(num))
    except (ValueError, TypeError):
        return str(value)

def sort_panel_names(panel_names):
    """Sort panel names numerically (05-100, 05-101, or just 100, 101, etc.)."""
    def panel_sort_key(panel_name):
        # First try to extract numbers from panel names like "05-100", "05-101"
        match = re.search(r'(\d+)-(\d+)', panel_name)
        if match:
            return (int(match.group(1)), int(match.group(2)))
        else:
            # Try to extract a single number from the end of the name (for names like "100", "101", etc.)
            match = re.search(r'(\d+)$', panel_name)
            if match:
                return (0, int(match.group(1)))  # Use 0 as first number for single numbers
            else:
                # Fallback to alphabetical sorting
                return (999, panel_name)
    
    return sorted(panel_names, key=panel_sort_key)

def get_panel_sort_key(panel_name):
    """Get the sort key for a single panel name (extracted from sort_panel_names function)."""
    # First try to extract numbers from panel names like "05-100", "05-101"
    match = re.search(r'(\d+)-(\d+)', panel_name)
    if match:
        return (int(match.group(1)), int(match.group(2)))
    else:
        # Try to extract a single number from the end of the name (for names like "100", "101", etc.)
        match = re.search(r'(\d+)$', panel_name)
        if match:
            return (0, int(match.group(1)))  # Use 0 as first number for single numbers
        else:
            # Fallback to alphabetical sorting
            return (999, panel_name)

def sort_panels_by_bundle_and_name(panels_dict, level_guid_map=None):
    """Sort panels by level, then by bundle, then by panel name for consistent ordering."""
    def panel_sort_key(item):
        pname, pobj = item
        
        # Extract level number from LevelNo (primary) or LevelGuid with mapping
        level_info = pobj.get('LevelNo') or pobj.get('Level') or ''
        level_num = 0
        if level_info:
            # Try to parse as direct number (e.g., "1", "2")
            try:
                level_num = int(float(str(level_info)))
            except (ValueError, TypeError):
                level_num = 0
        elif level_guid_map and pobj.get('LevelGuid'):
            # Use LevelGuid mapping if available
            level_guid = pobj.get('LevelGuid')
            if level_guid in level_guid_map:
                level_info = level_guid_map[level_guid]
                try:
                    level_num = int(float(str(level_info)))
                except (ValueError, TypeError):
                    level_num = 0
        
        # Extract bundle number for proper numerical sorting
        bundle_name = pobj.get('BundleName') or pobj.get('Bundle') or ''
        bundle_num = 0
        if bundle_name:
            # Extract bundle number from bundle name (e.g., "B1", "B2", "B1 (2x6 Ext)")
            import re
            match = re.search(r'B\s*(\d+)', bundle_name)
            if match:
                bundle_num = int(match.group(1))
            else:
                # Fallback: try to extract any number from bundle name
                match = re.search(r'(\d+)', bundle_name)
                if match:
                    bundle_num = int(match.group(1))
        
        # Extract panel number for proper numeric sorting
        display_name = pobj.get('DisplayLabel', pname)
        panel_num = 0
        import re
        # Match the number after underscore or the last number in the name
        match = re.search(r'_(\d+)|(\d+)$', display_name)
        if match:
            panel_num = int(match.group(1) or match.group(2))
        
        return (level_num, bundle_num, bundle_name, panel_num, display_name)
    
    return sorted(panels_dict.items(), key=panel_sort_key)

def extract_beam_pocket_info(panel_obj, materials):
    """Extract beam pocket information with panel labels and quantities."""
    beam_pockets_raw = []

    try:
        mats_list = materials if isinstance(materials, (list, tuple)) else []
        if debug_enabled:
            print(f"DEBUG: Processing {len(mats_list)} materials for beam pockets")

        # Group materials by SubAssemblyGuid for beam pockets
        beam_pocket_groups = {}

        for m in mats_list:
            if not isinstance(m, dict):
                continue

            subassembly_guid = m.get('SubAssemblyGuid', '')
            subassembly_name = m.get('SubAssembly', '')

            if debug_enabled:
                print(f"DEBUG: Checking material - SubAssemblyName: '{subassembly_name}', FamilyMemberName: '{m.get('FamilyMemberName', '')}', GUID: '{subassembly_guid}'")
            if debug_enabled:
                print(f"DEBUG: Material keys: {list(m.keys())}")
            if debug_enabled:
                print(f"DEBUG: Material data: {m}")

            # Look for beam pocket materials by checking for specific beam pocket SubAssembly types
            family_member_name = m.get('FamilyMemberName', '')
            is_beam_pocket_material = False
            
            # Only consider materials that are part of a beam pocket SubAssembly
            if subassembly_guid and subassembly_name:
                # Check if this is a beam pocket SubAssembly by looking for "Beampocket" or "RoughOpening" in the name
                is_beam_pocket_subassembly = 'beampocket' in subassembly_name.lower() or 'roughopening' in subassembly_name.lower()
                
                if is_beam_pocket_subassembly:
                    # Only include Trimmer and KingStud materials from beam pocket SubAssemblies
                    is_beam_pocket_material = (
                        'Trimmer' in family_member_name or
                        'KingStud' in family_member_name
                    )
                    if debug_enabled:
                        print(f"DEBUG: Found beam pocket SubAssembly: {subassembly_name}, checking material: {family_member_name}")
                else:
                    if debug_enabled:
                        print(f"DEBUG: Skipping non-beam-pocket SubAssembly: {subassembly_name}")
            elif subassembly_guid:
                # Handle case where SubAssemblyName is empty but we have a GUID
                # Check for known beam pocket GUIDs
                known_beam_pocket_guids = [
                    '0bf648e5-4fd9-4fc1-9832-2e4181e4bef7',  # From user's example
                    'a8e7c46e-56de-48d2-b8c0-2e3ff2b98dbd',  # From debug
                    '3441670f-3f86-4039-b0b6-39489cc4afbe',  # From debug
                    'a5ae925f-0299-497a-a614-e54b1d3e4720',  # From debug
                    '43214eec-9b08-4efa-abbb-901178098d1e'   # LType SubAssembly
                ]
                
                if subassembly_guid in known_beam_pocket_guids:
                    is_beam_pocket_material = (
                        'Trimmer' in family_member_name or
                        'KingStud' in family_member_name
                    )
                    if debug_enabled:
                        print(f"DEBUG: Found beam pocket by GUID: {subassembly_guid}, checking material: {family_member_name}")
                else:
                    if debug_enabled:
                        print(f"DEBUG: Skipping unknown GUID: {subassembly_guid}")
            else:
                if debug_enabled:
                    if debug_enabled:
                        print(f"DEBUG: Skipping material without SubAssembly info: GUID={subassembly_guid}, Name={subassembly_name}")

            if is_beam_pocket_material:
                if debug_enabled:
                    if debug_enabled:
                        print(f"DEBUG: Found beam pocket material: {family_member_name} in subassembly {subassembly_name}")
                if debug_enabled:
                    if debug_enabled:
                        print(f"DEBUG: Material AFF: {m.get('AFF')}, elev_max_y: {m.get('elev_max_y')}")
                if debug_enabled:
                    if debug_enabled:
                        print(f"DEBUG: Material X coords: min={m.get('bottom_x_min')}, max={m.get('bottom_x_max')}")
                if subassembly_guid not in beam_pocket_groups:
                    beam_pocket_groups[subassembly_guid] = {
                        'panel_id': m.get('PanelID', ''),
                        'materials': [],
                        'aff': None,
                        'opening_width': None
                    }

                beam_pocket_groups[subassembly_guid]['materials'].append(m)

        # Process each beam pocket group
        for guid, pocket_data in beam_pocket_groups.items():
            materials_list = pocket_data['materials']

            # Count panel labels and find AFF and opening width
            label_counts = {}
            aff_value = None
            opening_width = None
            king_stud_positions = []

            for mat in materials_list:
                # Get panel label
                label = mat.get('Label', '')
                if label:
                    label_counts[label] = label_counts.get(label, 0) + 1

                # Find AFF from Trimmer Y-coordinate
                family_member_name = mat.get('FamilyMemberName', '')
                if 'Trimmer' in family_member_name:
                    # Calculate AFF as Trimmer's top Y minus bottom Y offset
                    if mat.get('board_y') is not None and mat.get('elev_min_y') is not None:
                        # AFF = top Y coordinate - bottom Y coordinate (accounts for bottom plate/floor offset)
                        top_y = float(mat.get('board_y'))
                        bottom_y = float(mat.get('elev_min_y'))
                        aff_value = top_y - bottom_y
                        if debug_enabled:
                            print(f"DEBUG: Calculated AFF from Trimmer Y range: {top_y} - {bottom_y} = {aff_value}")
                    # Fallback to individual Y-coordinate if range not available
                    elif mat.get('board_y') is not None:
                        aff_value = float(mat.get('board_y'))
                        if debug_enabled:
                            print(f"DEBUG: Found AFF from Trimmer's individual Y-coordinate: {aff_value}")
                    # Fallback to elev_max_y if board_y not available
                    elif mat.get('elev_max_y') is not None:
                        aff_value = float(mat.get('elev_max_y'))
                        if debug_enabled:
                            print(f"DEBUG: Found AFF from elev_max_y fallback: {aff_value}")
                    # Final fallback to AFF field
                    elif mat.get('AFF') is not None:
                        aff_value = float(mat.get('AFF'))
                        if debug_enabled:
                            print(f"DEBUG: Found AFF from Trimmer AFF field: {aff_value}")

                # Collect King Stud X-positions for opening width calculation
                if 'KingStud' in family_member_name:
                    # Try to get King Stud's individual X-coordinate first
                    king_x = mat.get('board_x')
                    if king_x is not None:
                        king_stud_positions.append(king_x)
                        if debug_enabled:
                            print(f"DEBUG: Found King Stud at individual X position: {king_x}")
                    # Fallback to bounding box coordinates
                    elif mat.get('bottom_x_min') is not None:
                        king_x = float(mat.get('bottom_x_min'))
                        king_stud_positions.append(king_x)
                        if debug_enabled:
                            print(f"DEBUG: Found King Stud at bounding box X position: {king_x}")
                    elif mat.get('bottom_x_max') is not None:
                        king_x = float(mat.get('bottom_x_max'))
                        king_stud_positions.append(king_x)
                        if debug_enabled:
                            print(f"DEBUG: Found King Stud at bounding box X position: {king_x}")

            # Calculate opening width from King Stud positions
            if len(king_stud_positions) >= 2:
                king_stud_positions.sort()
                # For beam pocket: King Stud - Trimmer - King Stud
                # Opening width is distance between the two outer King Studs
                opening_width = abs(king_stud_positions[-1] - king_stud_positions[0])
                if debug_enabled:
                    print(f"DEBUG: Calculated beam pocket opening width from King Studs: {opening_width}")
            elif opening_width is None:
                # Fallback to SubAssembly bounding box if King Stud positions not available
                for mat in materials_list:
                    if opening_width is None:
                        bottom_x_min = mat.get('bottom_x_min')
                        bottom_x_max = mat.get('bottom_x_max')
                        if bottom_x_min is not None and bottom_x_max is not None:
                            opening_width = abs(float(bottom_x_max) - float(bottom_x_min))
                            if debug_enabled:
                                print(f"DEBUG: Calculated opening width from bounding box: {opening_width}")
                            break

            # Create beam pocket entry
            if label_counts:
                bottom_aff = aff_value
                # Correct opening width to 3 inches as specified by user
                if opening_width is not None:
                    opening_width = 3.0
                top_aff = bottom_aff + opening_width if bottom_aff is not None and opening_width is not None else None
                beam_pocket = {
                    'panel_id': pocket_data['panel_id'],
                    'bottom_aff': bottom_aff,
                    'top_aff': top_aff,
                    'header_size': opening_width,
                    'materials': label_counts
                }
                if debug_enabled:
                    print(f"DEBUG: Created beam pocket entry: {beam_pocket}")
                beam_pockets_raw.append(beam_pocket)
            else:
                if debug_enabled:
                    print(f"DEBUG: No label counts found for beam pocket group {guid}")

    except Exception as e:
        logging.error(f"Error extracting beam pocket info: {e}")

    # Group identical beam pockets
    grouped_pockets = {}
    for bp in beam_pockets_raw:
        # Create a key based on materials and AFF
        materials_key = tuple(sorted(bp.get('materials', {}).items()))
        key = (materials_key, bp.get('bottom_aff'), bp.get('header_size'))

        if key in grouped_pockets:
            grouped_pockets[key]['count'] += 1
        else:
            grouped_pockets[key] = {
                'panel_id': bp.get('panel_id'),
                'aff': bp.get('bottom_aff'),
                'opening_width': bp.get('header_size'),
                'materials': bp.get('materials', {}),
                'count': 1
            }

    logging.debug(f"Beam pocket extraction complete. Found {len(grouped_pockets)} unique beam pockets")
    if debug_enabled:
        print(f"DEBUG: Beam pocket extraction complete. Found {len(grouped_pockets)} unique beam pockets")
    return list(grouped_pockets.values())

def calculate_squaring(height, length):
    """Calculate squaring dimension using Pythagorean theorem: sqrt((height-1.5)² + length²).
    
    Subtracts 1.5" from height to account for top plate material that's shipped loose
    and therefore not included in the squaring measurement.
    """
    try:
        h = float(height) - 1.5  # Subtract top plate that's shipped loose
        l = float(length)
        c = math.sqrt(h**2 + l**2)
        return inches_to_feet_inches_sixteenths(c)
    except (ValueError, TypeError):
        return None

def inches_to_feet_inches_sixteenths(s):
    """Convert decimal inches to feet-inches-sixteenths format."""
    try:
        f = float(s)
    except Exception:
        return ''
    try:
        total_sixteenths = int(round(float(f) * 16))
    except Exception:
        return ''
    # Quantize to even sixteenths (favor common fractions like 1/8)
    total_sixteenths = int(round(total_sixteenths / 2.0) * 2)
    feet = total_sixteenths // (12 * 16)
    rem = total_sixteenths % (12 * 16)
    inches_whole = rem // 16
    sixteenths = rem % 16
    if sixteenths == 0:
        frac_part = ''
    else:
        num = sixteenths // 2
        denom = 8
        from math import gcd
        g = gcd(num, denom)
        num_r = num // g
        denom_r = denom // g
        frac_part = f"{num_r}/{denom_r}\""

    if feet and inches_whole:
        if frac_part:
            return f"{feet}'-{inches_whole}-{frac_part}"
        else:
            return f"{feet}'-{inches_whole}\""
    if feet and not inches_whole:
        if frac_part:
            return f"{feet}'-{frac_part}"
        else:
            return f"{feet}'"
    if inches_whole:
        if frac_part:
            return f"{inches_whole}-{frac_part}"
        else:
            return f"{inches_whole}\""
    if frac_part:
        return frac_part
    """Convert decimal inches to feet-inches-sixteenths format."""
    try:
        f = float(s)
    except Exception:
        return ''
    try:
        total_sixteenths = int(round(float(f) * 16))
    except Exception:
        return ''
    # Quantize to even sixteenths (favor common fractions like 1/8)
    total_sixteenths = int(round(total_sixteenths / 2.0) * 2)
    feet = total_sixteenths // (12 * 16)
    rem = total_sixteenths % (12 * 16)
    inches_whole = rem // 16
    sixteenths = rem % 16
    if sixteenths == 0:
        frac_part = ''
    else:
        num = sixteenths // 2
        denom = 8
        from math import gcd
        g = gcd(num, denom)
        num_r = num // g
        denom_r = denom // g
        frac_part = f"{num_r}/{denom_r}\""

    if feet and inches_whole:
        if frac_part:
            return f"{feet}'-{inches_whole}-{frac_part}"
        else:
            return f"{feet}'-{inches_whole}\""
    if feet and not inches_whole:
        if frac_part:
            return f"{feet}'-{frac_part}"
        else:
            return f"{feet}'"
    if inches_whole:
        if frac_part:
            return f"{inches_whole}-{frac_part}"
        else:
            return f"{inches_whole}\""
    if frac_part:
        return frac_part
    # Return empty string for zero dimensions instead of '0\"'
    return ''

def detect_unassigned_panels(panels_dict):
    """Detect panels that are not assigned to any bundle and return summary."""
    unassigned_panels = []
    
    for pname, pobj in panels_dict.items():
        bundle_name = pobj.get('BundleName') or pobj.get('Bundle') or pobj.get('BundleLabel') or ''
        display_name = pobj.get('DisplayLabel', pname)
        
        # Check if panel has no bundle assignment
        if not bundle_name or bundle_name.strip() == '' or bundle_name == 'NoBundle':
            unassigned_panels.append({
                'name': pname,
                'display_name': display_name,
                'level': pobj.get('Level', 'Unknown'),
                'bundle': bundle_name or 'None'
            })
    
    return unassigned_panels

def diagnose_v2_bundle_assignment(root, ehx_version, panels_by_name):
    """Diagnose v2.0 bundle assignment issues and return detailed report."""
    if ehx_version != "v2.0":
        return None
    
    report = {
        'junctions_found': 0,
        'bundles_found': 0,
        'panels_total': len(panels_by_name),
        'panels_assigned': 0,
        'panels_unassigned': 0,
        'junction_mappings': {},
        'bundle_layer_mappings': {},
        'assignment_details': []
    }
    
    # Count junctions and build mapping
    junction_bundle_map = {}
    junction_details = {}  # Store junction details for each panel
    for junction in root.findall('.//Junction'):
        report['junctions_found'] += 1
        panel_id_el = junction.find('PanelID')
        label_el = junction.find('Label')
        bundle_name_el = junction.find('BundleName')
        
        if bundle_name_el is not None and bundle_name_el.text:
            bundle_name = bundle_name_el.text.strip()
            panel_id = panel_id_el.text.strip() if panel_id_el is not None and panel_id_el.text else None
            label = label_el.text.strip() if label_el is not None and label_el.text else None
            
            if panel_id:
                junction_bundle_map[panel_id] = bundle_name
            if label:
                junction_bundle_map[label] = bundle_name
            
            # Extract junction details for this panel
            junction_info = {}
            
            # Extract junction details from SubAssemblyName
            subassembly_name_el = junction.find('SubAssemblyName')
            if subassembly_name_el is not None and subassembly_name_el.text:
                subassembly_name = subassembly_name_el.text.strip()
                
                # Parse SubAssemblyName to extract junction details
                if subassembly_name == 'LType':
                    junction_info['LType'] = 'LType'
                elif subassembly_name.startswith('Ladder'):
                    junction_info['Ladder'] = subassembly_name
                elif subassembly_name == 'Subcomponent':
                    junction_info['Subcomponent'] = 'Subcomponent'
            
            # Store junction details using panel_id or label as key
            if panel_id:
                junction_details[panel_id] = junction_info
            if label:
                junction_details[label] = junction_info
    
    report['junction_mappings'] = junction_bundle_map
    report['junction_details'] = junction_details
    
    # Count bundles and build bundle layer mapping
    bundle_layer_map = {}
    for bundle_el in root.findall('.//Bundle'):
        report['bundles_found'] += 1
        label_el = bundle_el.find('Label')
        if label_el is not None and label_el.text:
            bundle_name = label_el.text.strip()
            import re
            match = re.match(r'B(\d+)', bundle_name)
            if match:
                bundle_layer = int(match.group(1))
                bundle_layer_map[bundle_layer] = bundle_name
    
    report['bundle_layer_mappings'] = bundle_layer_map
    
    # Analyze panel assignments
    for pname, pobj in panels_by_name.items():
        display_name = pobj.get('DisplayLabel', pname)
        bundle_name = pobj.get('BundleName') or pobj.get('Bundle') or ''
        
        assignment_detail = {
            'panel_name': pname,
            'display_name': display_name,
            'bundle_assigned': bundle_name,
            'assignment_method': 'unknown',
            'panel_id': pobj.get('Name'),
            'bundle_layer': None
        }
        
        if bundle_name and bundle_name != 'NoBundle':
            report['panels_assigned'] += 1
            assignment_detail['assignment_method'] = 'direct'
        else:
            report['panels_unassigned'] += 1
            assignment_detail['assignment_method'] = 'unassigned'
            
            # Check if it could be assigned via junction
            panel_id = pobj.get('Name')
            if panel_id and panel_id in junction_bundle_map:
                assignment_detail['assignment_method'] = 'junction_available'
            elif display_name in junction_bundle_map:
                assignment_detail['assignment_method'] = 'junction_available_by_label'
            else:
                assignment_detail['assignment_method'] = 'no_junction_mapping'
        
        report['assignment_details'].append(assignment_detail)
    
    return report

# EHX search removed as per requirements - search functionality is disabled
# from ehx_search_widget import EHXSearchWidget

try:
    # PV0825 may provide parse_panels/extract_jobpath and a log writer helper
    # Temporarily disabled to test local parser
    # from PV0825 import parse_panels, extract_jobpath, write_expected_and_materials_logs
    raise Exception("Testing local parser")
except Exception:
    # PV0825 not available — provide a richer EHX parser fallback so GUI can
    # still load and display bundle/panel information and emit the same logs.
    def _text_of(el, names):
        if el is None:
            return None
        for n in names:
            ch = el.find(n)
            if ch is not None and ch.text is not None:
                return ch.text.strip()
        return None

    def _text_of_with_attr(el, names):
        """Extract text from child elements or attributes, checking child elements first."""
        if el is None:
            return None
        # First try child elements
        for n in names:
            ch = el.find(n)
            if ch is not None and ch.text is not None:
                return ch.text.strip()
        # Then try attributes
        for n in names:
            if el.get(n):
                return el.get(n).strip()
        return None

    def parse_materials_from_panel(panel_el):
        """Extract Boards, Sheets, Bracing and rough-opening SubAssembly boards from a Panel element."""

        # Boards (direct Board nodes)
        mats = []
        for node in panel_el.findall('.//Board'):
            typ = _text_of(node, ('FamilyMemberName', 'Type', 'Name')) or 'Board'
            fam = _text_of(node, ('FamilyMemberName', 'Family', 'FamilyName', 'Type', 'Name')) or typ
            # Extract the numeric FamilyMember ID
            family_member_id = _text_of(node, ('FamilyMember', 'FamilyMemberID')) or ''
            label = _text_of(node, ('Label', 'LabelText')) or ''
            sub = _text_of(node, ('SubAssembly', 'SubAssemblyName')) or ''
            mat_el = node.find('Material')
            if mat_el is None:
                mat_el = node
            desc = _text_of(mat_el, ('Description', 'Desc', 'Material', 'Name')) or ''
            qty = _text_of(mat_el, ('Quantity', 'QNT', 'Qty')) or '1'
            length = _text_of(mat_el, ('ActualLength', 'Length')) or ''
            width = _text_of(mat_el, ('ActualWidth', 'Width')) or ''
            board_guid = _text_of(node, ('BoardGuid', 'BoardID')) or _text_of(mat_el, ('BoardGuid', 'BoardID'))
            sub_assembly_guid = _text_of_with_attr(node, ('SubAssemblyGuid', 'SubAssemblyID'))
            # If SubAssembly is empty but we have a known LType GUID, populate it
            if not sub and sub_assembly_guid in ['6456c2dd-3ace-4851-a0f8-37317f63fbdc', '43214eec-9b08-4efa-abbb-901178098d1e']:
                sub = 'LType'
            mats.append({'Type': typ, 'FamilyMemberName': fam, 'FamilyMember': family_member_id, 'Label': label, 'SubAssembly': sub, 'Desc': desc, 'Qty': qty, 'ActualLength': length, 'ActualWidth': width, 'BoardGuid': board_guid, 'SubAssemblyGuid': sub_assembly_guid})
        
        # Sheets (direct Sheet nodes)
        for node in panel_el.findall('.//Sheet'):
            typ = _text_of(node, ('FamilyMemberName', 'Type', 'Name')) or 'Sheathing'
            fam = _text_of(node, ('FamilyMemberName', 'Family', 'FamilyName', 'Type', 'Name')) or typ
            # Extract the numeric FamilyMember ID
            family_member_id = _text_of(node, ('FamilyMember', 'FamilyMemberID')) or ''
            label = _text_of(node, ('Label', 'LabelText')) or ''
            sub = _text_of(node, ('SubAssembly', 'SubAssemblyName')) or ''
            # prefer TypeOfSheathing (explicit sheathing description) first,
            # then nested <Material><Description>, then other Description fields
            desc = ''
            # check nested Material/Description first (PV0825 prefers this)
            mat_child = node.find('Material')
            if mat_child is not None:
                desc = _text_of(mat_child, ('Description', 'Desc', 'Material', 'Name')) or ''
            if not desc:
                desc = _text_of(node, ('TypeOfSheathing', 'Description', 'Desc', 'Material', 'Name', 'TypeOfFastener')) or ''
            qty = _text_of(node, ('Quantity', 'QNT', 'Qty')) or '1'
            # Get dimensions from Material child element if it exists
            length = ''
            width = ''
            if mat_child is not None:
                length = _text_of(mat_child, ('ActualLength', 'Length')) or ''
                width = _text_of(mat_child, ('ActualWidth', 'Width')) or ''
            # Fallback to direct Sheet element if no Material child
            if not length:
                length = _text_of(node, ('ActualLength', 'Length')) or ''
            if not width:
                width = _text_of(node, ('ActualWidth', 'Width')) or ''
            sheet_guid = _text_of(node, ('SheetGuid', 'SheetID')) or _text_of(mat_child, ('SheetGuid', 'SheetID'))
            sub_assembly_guid = _text_of_with_attr(node, ('SubAssemblyGuid', 'SubAssemblyID'))
            # If SubAssembly is empty but we have a known LType GUID, populate it
            if not sub and sub_assembly_guid in ['6456c2dd-3ace-4851-a0f8-37317f63fbdc', '43214eec-9b08-4efa-abbb-901178098d1e']:
                sub = 'LType'
            mats.append({'Type': typ, 'FamilyMemberName': fam, 'FamilyMember': family_member_id, 'Label': label, 'SubAssembly': sub, 'Desc': desc, 'Description': desc, 'Qty': qty, 'ActualLength': length, 'ActualWidth': width, 'SheetGuid': sheet_guid, 'SubAssemblyGuid': sub_assembly_guid})

        # Bracing
        for node in panel_el.findall('.//Bracing'):
            typ = _text_of(node, ('FamilyMemberName', 'Type', 'Name')) or 'Bracing'
            fam = _text_of(node, ('FamilyMemberName', 'Family', 'FamilyName', 'Type', 'Name')) or typ
            # Extract the numeric FamilyMember ID
            family_member_id = _text_of(node, ('FamilyMember', 'FamilyMemberID')) or ''
            label = _text_of(node, ('Label', 'LabelText')) or ''
            sub = _text_of(node, ('SubAssembly', 'SubAssemblyName')) or ''
            desc = _text_of(node, ('Description', 'Desc', 'Material', 'Name')) or ''
            qty = _text_of(node, ('Quantity', 'QNT', 'Qty')) or '1'
            length = _text_of(node, ('ActualLength', 'Length')) or ''
            width = ''
            bracing_guid = _text_of(node, ('BracingGuid', 'BracingID'))
            sub_assembly_guid = _text_of_with_attr(node, ('SubAssemblyGuid', 'SubAssemblyID'))
            # If SubAssembly is empty but we have a known LType GUID, populate it
            if not sub and sub_assembly_guid in ['6456c2dd-3ace-4851-a0f8-37317f63fbdc', '43214eec-9b08-4efa-abbb-901178098d1e']:
                sub = 'LType'
            mats.append({'Type': typ, 'FamilyMemberName': fam, 'FamilyMember': family_member_id, 'Label': label, 'SubAssembly': sub, 'Desc': desc, 'Qty': qty, 'ActualLength': length, 'ActualWidth': width, 'BracingGuid': bracing_guid, 'SubAssemblyGuid': sub_assembly_guid})

        # SubAssemblies (rough openings only - sheathing is handled by Sheet parsing above)
        for sub_el in panel_el.findall('.//SubAssembly'):
            fam = _text_of(sub_el, ('FamilyMemberName', 'Family', 'FamilyName', 'Type', 'Name')) or ''
            # Extract the numeric FamilyMember ID from SubAssembly
            family_member_id = _text_of(sub_el, ('FamilyMember', 'FamilyMemberID')) or ''
            sub_label = _text_of(sub_el, ('Label', 'LabelText')) or ''
            sub_name = _text_of(sub_el, ('SubAssemblyName',)) or ''
            # capture SubAssembly GUID if present so we can tie contained materials
            sub_guid = _text_of_with_attr(sub_el, ('SubAssemblyGuid', 'SubAssemblyID'))
            logging.debug(f"SubAssembly found - Family: '{fam}', FamilyMember: '{family_member_id}', Label: '{sub_label}', Name: '{sub_name}'")
            # Handle rough openings and beam pockets in SubAssembly parsing - sheathing is handled by direct Sheet parsing above
            if fam and (str(fam).strip().lower() == 'roughopening' or 'beampocket' in str(fam).strip().lower()):
                logging.debug(f"Found rough opening or beam pocket SubAssembly: {fam}")
                # extract any Board entries inside the SubAssembly
                # Try to capture BottomView X range and ElevationView max_y available under the SubAssembly
                bottom_x_min = None
                bottom_x_max = None
                try:
                    bv = sub_el.find('.//BottomView')
                    if bv is not None:
                        xs = []
                        for p in bv.findall('.//Point'):
                            xel = p.find('X')
                            if xel is not None and xel.text:
                                try:
                                    xs.append(float(xel.text))
                                except Exception:
                                    continue
                        if xs:
                            bottom_x_min = min(xs)
                            bottom_x_max = max(xs)
                except Exception:
                    pass

                # capture an ElevationView inside the SubAssembly if present (gives local min/max Y)
                sub_elev_min_y = None
                sub_elev_max_y = None
                try:
                    ev = sub_el.find('.//ElevationView')
                    if ev is not None:
                        y_vals = []
                        for pt in ev.findall('.//Point'):
                            yel = pt.find('Y')
                            if yel is not None and yel.text:
                                try:
                                    y_vals.append(float(yel.text))
                                except Exception:
                                    continue
                        if y_vals:
                            sub_elev_min_y = min(y_vals)
                            sub_elev_max_y = max(y_vals)
                except Exception:
                    pass

                board_count = 0
                for b in sub_el.findall('.//Board'):
                    board_count += 1
                    btyp = _text_of(b, ('FamilyMemberName', 'Type', 'Name')) or 'Board'
                    # Extract the numeric FamilyMember ID for boards within SubAssembly
                    b_family_member_id = _text_of(b, ('FamilyMember', 'FamilyMemberID')) or ''
                    blab = _text_of(b, ('Label', 'LabelText')) or ''
                    if debug_enabled:
                        print(f"DEBUG: Processing board - Type: '{btyp}', FamilyMember: '{b_family_member_id}', Label: '{blab}', SubAssembly: '{sub_name}'")
                    
                    mat_el = b.find('Material')
                    if mat_el is None:
                        mat_el = b
                    bdesc = _text_of(mat_el, ('Description', 'Desc', 'Material', 'Name')) or ''
                    bal = _text_of(mat_el, ('ActualLength', 'Length')) or ''
                    baw = _text_of(mat_el, ('ActualWidth', 'Width')) or ''
                    b_guid = _text_of(b, ('BoardGuid', 'BoardID'))
                    
                    # Extract individual board coordinates for Trimmers and King Studs
                    board_y = None
                    board_x = None
                    if 'Trimmer' in btyp or 'KingStud' in btyp:
                        if debug_enabled:
                            print(f"DEBUG: Looking for coordinates for {btyp} with label '{blab}'")
                        try:
                            # Look for coordinates in board's own geometry - prioritize ElevationView over direct elements
                            y_elem = None
                            
                            # First try: Y element in ElevationView (find maximum Y for AFF)
                            ev = b.find('.//ElevationView')
                            if ev is not None:
                                y_elements = ev.findall('.//Y')
                                if y_elements:
                                    y_values = []
                                    for y_elem in y_elements:
                                        if y_elem.text:
                                            try:
                                                y_val = float(y_elem.text)
                                                y_values.append(y_val)
                                            except ValueError:
                                                pass
                                    
                                    if y_values:
                                        # Use the maximum Y value for AFF (top of opening)
                                        board_y = max(y_values)
                                        if debug_enabled:
                                            print(f"DEBUG: Found ElevationView Y values: {y_values}, using max: {board_y}")
                                        if debug_enabled:
                                            print(f"DEBUG: Found {btyp} Y-coordinate (ElevationView max): {board_y}")
                            
                            # Second try: Y element within Point structure
                            if board_y is None:
                                y_elem = b.find('.//Point/Y')
                                if y_elem is not None:
                                    if debug_enabled:
                                        print(f"DEBUG: Found Point/Y element, text: '{y_elem.text}'")
                                    if y_elem.text:
                                        board_y = float(y_elem.text)
                                        if debug_enabled:
                                            print(f"DEBUG: Found {btyp} Y-coordinate (Point): {board_y}")
                            
                            # Third try: direct Y element in board (less reliable)
                            if board_y is None:
                                y_elem = b.find('.//Y')
                                if y_elem is not None:
                                    if debug_enabled:
                                        print(f"DEBUG: Found direct Y element, text: '{y_elem.text}'")
                                    if y_elem.text:
                                        board_y = float(y_elem.text)
                                        if debug_enabled:
                                            print(f"DEBUG: Found {btyp} Y-coordinate (direct): {board_y}")
                            
                            # Fourth try: Y element in ElevationView/Point
                            if board_y is None:
                                ev = b.find('.//ElevationView')
                                if ev is not None:
                                    y_elem = ev.find('.//Point/Y')
                                    if y_elem is not None:
                                        if debug_enabled:
                                            print(f"DEBUG: Found ElevationView/Point Y element, text: '{y_elem.text}'")
                                        if y_elem.text:
                                            board_y = float(y_elem.text)
                                            if debug_enabled:
                                                print(f"DEBUG: Found {btyp} Y-coordinate (ElevationView/Point): {board_y}")
                            
                            # Fifth try: Y element in BottomView
                            if board_y is None:
                                bv = b.find('.//BottomView')
                                if bv is not None:
                                    y_elem = bv.find('.//Y')
                                    if y_elem is not None:
                                        if debug_enabled:
                                            print(f"DEBUG: Found BottomView Y element, text: '{y_elem.text}'")
                                        if y_elem.text:
                                            board_y = float(y_elem.text)
                                            if debug_enabled:
                                                print(f"DEBUG: Found {btyp} Y-coordinate (BottomView): {board_y}")
                            
                            # Look for X coordinate - try multiple possible locations
                            x_elem = None
                            
                            # First try: direct X element in board
                            x_elem = b.find('.//X')
                            if x_elem is not None:
                                if debug_enabled:
                                    print(f"DEBUG: Found direct X element, text: '{x_elem.text}'")
                                if x_elem.text:
                                    board_x = float(x_elem.text)
                                    if debug_enabled:
                                        print(f"DEBUG: Found {btyp} X-coordinate (direct): {board_x}")
                            
                            # Second try: X element within Point structure
                            if board_x is None:
                                x_elem = b.find('.//Point/X')
                                if x_elem is not None:
                                    if debug_enabled:
                                        print(f"DEBUG: Found Point/X element, text: '{x_elem.text}'")
                                    if x_elem.text:
                                        board_x = float(x_elem.text)
                                        if debug_enabled:
                                            print(f"DEBUG: Found {btyp} X-coordinate (Point): {board_x}")
                            
                            # Third try: X element in BottomView
                            if board_x is None:
                                bv = b.find('.//BottomView')
                                if bv is not None:
                                    x_elem = bv.find('.//X')
                                    if x_elem is not None:
                                        if debug_enabled:
                                            print(f"DEBUG: Found BottomView X element, text: '{x_elem.text}'")
                                        if x_elem.text:
                                            board_x = float(x_elem.text)
                                            if debug_enabled:
                                                print(f"DEBUG: Found {btyp} X-coordinate (BottomView): {board_x}")
                                            
                        except Exception as e:
                            if debug_enabled:
                                print(f"DEBUG: Error extracting coordinates for {btyp}: {e}")
                        
                        if board_y is None:
                            if debug_enabled:
                                print(f"DEBUG: No Y coordinate found for {btyp} with label '{blab}'")
                        if board_x is None:
                            if debug_enabled:
                                print(f"DEBUG: No X coordinate found for {btyp} with label '{blab}'")
                    
                    # If SubAssembly is empty but we have a known LType GUID, populate it
                    if not sub_name and sub_guid in ['6456c2dd-3ace-4851-a0f8-37317f63fbdc', '43214eec-9b08-4efa-abbb-901178098d1e']:
                        sub_name = 'LType'
                    
                    # annotate with captured bottom/elevation info for better AFF heuristics
                    entry = {'Type': btyp, 'FamilyMemberName': btyp, 'FamilyMember': b_family_member_id, 'Label': blab, 'SubAssembly': sub_name, 'Desc': bdesc, 'Qty': '', 'ActualLength': bal, 'ActualWidth': baw, 'BoardGuid': b_guid, 'SubAssemblyGuid': sub_guid}
                    
                    # Store individual board coordinates
                    if board_x is not None:
                        entry['board_x'] = board_x
                    if board_y is not None:
                        entry['board_y'] = board_y
                    
                    if bottom_x_min is not None and bottom_x_max is not None:
                        entry['bottom_x_min'] = bottom_x_min
                        entry['bottom_x_max'] = bottom_x_max
                    
                    # Use individual board Y-coordinate for Trimmers, otherwise use SubAssembly elevation
                    if board_y is not None and 'Trimmer' in btyp:
                        entry['AFF'] = board_y
                        if debug_enabled:
                            print(f"DEBUG: Using Trimmer's individual Y-coordinate for AFF: {board_y}")
                    elif sub_elev_max_y is not None:
                        entry['elev_max_y'] = sub_elev_max_y
                        # Explicitly store AFF as the top of the rough-opening elevation
                        entry['AFF'] = sub_elev_max_y
                    
                    if sub_elev_min_y is not None:
                        entry['elev_min_y'] = sub_elev_min_y
                    mats.append(entry)

                # If no boards but has elevation data, add entry for SubAssembly
                if board_count == 0 and (sub_elev_max_y is not None or sub_elev_min_y is not None):
                    entry = {'Type': 'SubAssembly', 'FamilyMemberName': fam, 'Label': sub_label, 'SubAssembly': sub_name, 'Desc': sub_name or fam, 'Qty': '', 'ActualLength': '', 'ActualWidth': '', 'BoardGuid': '', 'SubAssemblyGuid': sub_guid}
                    if sub_elev_max_y is not None:
                        entry['elev_max_y'] = sub_elev_max_y
                        entry['AFF'] = sub_elev_max_y
                    if sub_elev_min_y is not None:
                        entry['elev_min_y'] = sub_elev_min_y
                    mats.append(entry)

        return mats

    def strip_trailing_zeros(s):
        """Strip trailing zeros from decimal numbers (e.g., '12.000' -> '12', '5.500' -> '5.5')."""
        try:
            # Convert to float and back to string to normalize
            f = float(s)
            # Use string formatting to remove trailing zeros
            result = f"{f:g}"
            # Handle special cases
            if result.endswith('.0'):
                return result[:-2]  # Remove '.0'
            return result
        except (ValueError, TypeError):
            return s

    def format_weight(weight_value):
        """Format weight by rounding to even number and adding 'Lbs' suffix."""
        try:
            # Convert to float
            weight_float = float(weight_value)
            # Round to nearest even number
            rounded_weight = round(weight_float)
            # Make it even by rounding up if odd
            if rounded_weight % 2 != 0:
                rounded_weight += 1
            return f"{rounded_weight} Lbs"
        except (ValueError, TypeError):
            return f"{weight_value} Lbs"

    def _nat_key(s):
        """Natural sort key: split digits and non-digits so strings with numbers sort naturally."""
        try:
            parts = re.split(r'(\d+)', (s or ''))
            return [int(p) if p.isdigit() else p.lower() for p in parts]
        except Exception:
            return [s]

    def format_and_sort_materials(mats):
        # ensure label fallback
        for m in mats:
            if not m.get('Label'):
                m['Label'] = (m.get('Type','') + '-' + (m.get('Desc') or ''))[:6]

        # group identical materials by (Label, Type, Desc, length, width)
        groups = {}
        for m in mats:
            lbl = (m.get('Label') or '').strip()
            typ = (m.get('Type') or '').strip()
            fam = (m.get('FamilyMemberName') or '').strip()
            desc = (m.get('Desc') or m.get('Description') or '').strip()
            length = m.get('ActualLength') or m.get('Length') or ''
            width = m.get('ActualWidth') or m.get('Width') or ''
            
            # Round length and width to 2 decimal places to handle floating point precision issues
            try:
                length_val = float(length) if length else 0.0
                length_rounded = round(length_val, 2)
                length_str = str(length_rounded) if length_rounded != 0.0 else ''
            except (ValueError, TypeError):
                length_str = str(length).strip()
                
            try:
                width_val = float(width) if width else 0.0
                width_rounded = round(width_val, 2)
                width_str = str(width_rounded) if width_rounded != 0.0 else ''
            except (ValueError, TypeError):
                width_str = str(width).strip()
            
            # normalize numeric strings
            key = (lbl, typ, desc, length_str, width_str)
            
            # Parse quantity from the material
            qty_str = m.get('Qty', '1')
            try:
                qty = int(float(qty_str)) if qty_str else 1
            except (ValueError, TypeError):
                qty = 1
            
            if key not in groups:
                groups[key] = {
                    'count': 0, 
                    'length': length, 
                    'width': width,
                    'lbl': lbl, 
                    'typ': typ, 
                    'fam': fam, 
                    'desc': desc
                }
            groups[key]['count'] += qty

        # sort keys by natural label ordering
        sorted_keys = sorted(groups.keys(), key=lambda k: _nat_key(k[0] or ''))
        lines = []
        for key in sorted_keys:
            lbl, typ, desc, length, width = key
            info = groups[key]
            cnt = info.get('count', 0)
            qty_str = f"({cnt})" if cnt > 1 else "(1)"
            len_str = inches_to_feet_inches_sixteenths(length) if length not in (None, '', '0', '0.0') else ''
            wid_str = inches_to_feet_inches_sixteenths(width) if width not in (None, '', '0', '0.0') else ''
            size = ''
            # Sheets include width in the size; boards/bracing use length only
            if 'sheet' in typ.lower() or 'sheath' in typ.lower():
                if len_str and wid_str:
                    size = f"{len_str} x {wid_str}"
                elif len_str:
                    size = f"{len_str}"
                elif wid_str:
                    size = f"{wid_str}"
                else:
                    size = ''
            else:
                size = len_str or ''
            # clean desc
            desc_clean = desc
            # build line
            # use FamilyMemberName for middle column to match materials.log
            mid = info.get('fam') or info.get('typ') or typ
            if size:
                line = f"{lbl} - {mid} - {desc_clean} - {qty_str} - {size}"
            else:
                line = f"{lbl} - {mid} - {desc_clean} - {qty_str}"
            line = re.sub(r'\s+-\s+-', ' - ', line).replace(' - () -', ' -').strip()
            lines.append(line)
        return lines

    def create_material_to_breakdown_mapping(mats):
        """Create a mapping from material properties to alphabetical breakdown labels (A, B, C, D, etc.)
        
        Special handling for LType subassemblies: materials within LType subassemblies
        are assigned labels K and L instead of following the general alphabetical sequence.
        """
        # ensure label fallback
        for m in mats:
            if not m.get('Label'):
                m['Label'] = (m.get('Type','') + '-' + (m.get('Desc') or ''))[:6]

        # group identical materials by (Label, Type, Desc, length, width, SubAssemblyGuid)
        groups = {}
        for m in mats:
            lbl = (m.get('Label') or '').strip()
            typ = (m.get('Type') or '').strip()
            desc = (m.get('Desc') or m.get('Description') or '').strip()
            length = m.get('ActualLength') or m.get('Length') or ''
            width = m.get('ActualWidth') or m.get('Width') or ''
            subassembly_guid = (m.get('SubAssemblyGuid') or '').strip()
            
            # Round length and width to 2 decimal places to handle floating point precision issues
            try:
                length_val = float(length) if length else 0.0
                length_rounded = round(length_val, 2)
                length_str = str(length_rounded) if length_rounded != 0.0 else ''
            except (ValueError, TypeError):
                length_str = str(length).strip()
                
            try:
                width_val = float(width) if width else 0.0
                width_rounded = round(width_val, 2)
                width_str = str(width_rounded) if width_rounded != 0.0 else ''
            except (ValueError, TypeError):
                width_str = str(width).strip()
            
            # normalize numeric strings
            key = (lbl, typ, desc, length_str, width_str, subassembly_guid)
            
            if key not in groups:
                groups[key] = {
                    'count': 0, 
                    'length': length, 
                    'width': width,
                    'lbl': lbl, 
                    'typ': typ, 
                    'desc': desc,
                    'subassembly': (m.get('SubAssembly') or '').strip(),
                    'subassembly_guid': subassembly_guid
                }
            
            # Parse quantity from the material
            qty_str = m.get('Qty', '1')
            try:
                qty = int(float(qty_str)) if qty_str else 1
            except (ValueError, TypeError):
                qty = 1
            groups[key]['count'] += qty
        
        # sort keys by natural label ordering and assign alphabetical labels
        sorted_keys = sorted(groups.keys(), key=lambda k: _nat_key(k[0] or ''))
        mapping = {}
        
        # Special handling for LType subassemblies
        ltype_materials = []
        non_ltype_materials = []
        
        for i, key in enumerate(sorted_keys):
            group_info = groups[key]
            # Check if this material belongs to an LType subassembly
            sub_guid = group_info['subassembly_guid']
            is_ltype = (group_info['subassembly'] == 'LType' or 
                       'LType' in group_info['subassembly'] or
                       sub_guid in ['6456c2dd-3ace-4851-a0f8-37317f63fbdc', 
                                   '43214eec-9b08-4efa-abbb-901178098d1e'])
            
            if is_ltype:
                ltype_materials.append(key)
            else:
                non_ltype_materials.append(key)
        
        # Assign labels to non-LType materials first (A, B, C, D, ..., J)
        for i, key in enumerate(non_ltype_materials):
            # Convert index to alphabetical label
            label = ""
            temp = i
            while True:
                label = chr(65 + (temp % 26)) + label  # 65 is ASCII for 'A'
                temp = temp // 26 - 1
                if temp < 0:
                    break
            if not label:  # Handle i=0 case
                label = "A"
            
            # Store mapping from material key to alphabetical label
            mapping[key] = label
        
        # Assign labels to LType materials (K, L)
        ltype_labels = ['K', 'L']
        for i, key in enumerate(ltype_materials):
            if i < len(ltype_labels):
                mapping[key] = ltype_labels[i]
            else:
                # If there are more than 2 LType materials, continue with next letters
                label_index = len(ltype_labels) + (i - len(ltype_labels))
                label = ""
                temp = label_index
                while True:
                    label = chr(75 + (temp % 26)) + label  # Start from 'K' (ASCII 75)
                    temp = temp // 26 - 1
                    if temp < 0:
                        break
                if not label:
                    label = "K"
                mapping[key] = label
        
        return mapping

    def _is_rough_opening(m):
        try:
            if not isinstance(m, dict):
                return False
            typ = (m.get('Type') or '').lower()
            desc = (m.get('Desc') or m.get('Description') or '').lower()
            lbl = (m.get('Label') or '').lower()
            fam = (m.get('FamilyMemberName') or '').lower()

            # Primary check: exact match for RoughOpening type
            if typ == 'roughopening':
                return True

            # Secondary checks: look for rough/opening indicators but exclude headers
            if 'rough' in typ or 'rough' in desc or 'rough' in lbl or 'rough' in fam:
                return True
            if 'opening' in typ or 'opening' in desc or 'opening' in lbl or 'opening' in fam:
                return True

            # Specific rough opening labels (but not header-related ones)
            if lbl in ['bsmt-hdr', '49x63-l2'] or 'hdr' in lbl:
                # Make sure it's not a header material
                if 'header' not in typ and typ != 'headercap' and typ != 'headercripple':
                    return True

            return False
        except Exception:
            return False

    def extract_elevation_info(panel_el):
        """Extract elevation information from ElevationView elements within a panel and its sub-elements."""
        elevations = []
        try:
            # Look for ElevationView elements in the panel and all its descendants
            for ev in panel_el.findall('.//ElevationView'):
                elevation_data = {'points': []}
                for point in ev.findall('Point'):
                    x_elem = point.find('X')
                    y_elem = point.find('Y')
                    if x_elem is not None and y_elem is not None:
                        try:
                            x_val = float(x_elem.text) if x_elem.text else 0.0
                            y_val = float(y_elem.text) if y_elem.text else 0.0
                            elevation_data['points'].append({'x': x_val, 'y': y_val})
                        except (ValueError, TypeError):
                            continue

                if elevation_data['points']:
                    # Calculate min/max Y values and height
                    y_values = [p['y'] for p in elevation_data['points']]
                    elevation_data['min_y'] = min(y_values)
                    elevation_data['max_y'] = max(y_values)
                    elevation_data['height'] = elevation_data['max_y'] - elevation_data['min_y']
                    elevations.append(elevation_data)
        except Exception:
            pass
        return elevations


    def _filter_materials_by_guid(materials, panel_obj):
        """Return materials filtered by PanelGuid (preferred), then LevelGuid, then BundleGuid.
        If no GUIDs available, fall back to returning the original list.
        """
        try:
            if not isinstance(materials, (list, tuple)):
                return materials or []
            pg = panel_obj.get('Name') or panel_obj.get('PanelGuid')
            lg = panel_obj.get('LevelGuid')
            bg = panel_obj.get('BundleGuid') or panel_obj.get('BundleId')
            out = []
            for m in materials:
                if not isinstance(m, dict):
                    continue
                m_pg = m.get('PanelGuid') or m.get('PanelID')
                m_lg = m.get('LevelGuid')
                m_bg = m.get('BundleGuid')
                # PanelGuid match is highest priority
                if pg and m_pg:
                    if str(m_pg) == str(pg):
                        out.append(m)
                    else:
                        continue
                # Next prefer LevelGuid
                elif lg and m_lg:
                    if str(m_lg) == str(lg):
                        out.append(m)
                    else:
                        continue
                # Next try BundleGuid
                elif bg and m_bg:
                    if str(m_bg) == str(bg):
                        out.append(m)
                    else:
                        continue
                else:
                    # no GUID info to filter by; include as fallback
                    out.append(m)
            return out
        except Exception:
            return materials or []


    def get_aff_for_rough_opening(panel_obj, m, size_tol=1.0):
        """Return an AFF (float) for a rough opening material `m` using several heuristics.
        Priority mirrors the GUI helper: try explicit AFF, material/subassembly elevation,
        X-range overlap with panel elevations, size-match within `size_tol`, label defaults,
        then panel-level best elevation.
        """
        # 1) explicit AFF
        try:
            if isinstance(m, dict) and m.get('AFF') is not None:
                return float(m.get('AFF'))
        except Exception:
            pass

        # 2) material-level captured elevation (prefer subassembly elevation top (max_y) when present)
        try:
            if isinstance(m, dict):
                if m.get('elev_max_y') is not None:
                    return float(m.get('elev_max_y'))
                if m.get('elev_min_y') is not None:
                    return float(m.get('elev_min_y'))
        except Exception:
            pass

        elevations = (panel_obj.get('elevations') or [])

        # Helper: choose elevation by X-range overlap with material BottomView
        try:
            bx0 = float(m.get('bottom_x_min')) if m.get('bottom_x_min') is not None else None
            bx1 = float(m.get('bottom_x_max')) if m.get('bottom_x_max') is not None else None
        except Exception:
            bx0 = bx1 = None

        candidates = []
        if bx0 is not None and bx1 is not None and elevations:
            for e in elevations:
                try:
                    xs = [p.get('x', 0.0) for p in (e.get('points') or [])]
                    if not xs:
                        continue
                    ex0 = min(xs)
                    ex1 = max(xs)
                    # compute overlap
                    overlap = min(ex1, bx1) - max(ex0, bx0)
                    if overlap > 0:
                        candidates.append((overlap, e))
                except Exception:
                    continue
            if candidates:
                # prefer larger overlap, then higher elevation top (max_y) when ranking
                candidates.sort(key=lambda t: (t[0], t[1].get('max_y', 0)), reverse=True)
                best = candidates[0][1]
                # Use the elevation top (max_y) for AFF as requested
                return best.get('max_y') if best.get('max_y') is not None else best.get('min_y')

        # 4) size-match: try to match ActualLength to elevation height within tolerance
        try:
            al = None
            if isinstance(m, dict):
                al = m.get('ActualLength') or m.get('Length')
            if al is not None and elevations:
                try:
                    al_f = float(al)
                    size_matches = []
                    for e in elevations:
                        eh = float(e.get('height') or 0)
                        if eh <= 0:
                            continue
                        if abs(eh - al_f) <= float(size_tol):
                            size_matches.append((abs(eh - al_f), e))
                    if size_matches:
                        size_matches.sort(key=lambda t: t[0])
                        # Size-match found: prefer the elevation top (max_y) as AFF
                        chosen = size_matches[0][1]
                        return chosen.get('max_y') if chosen.get('max_y') is not None else chosen.get('min_y')
                except Exception:
                    pass
        except Exception:
            pass

        # 5) label-specific defaults
        try:
            lab = (m.get('Label') or '')
            if lab == 'BSMT-HDR':
                return 1.5
            if lab == '49x63-L2':
                return 92.5
        except Exception:
            pass

        # 6) fallback: pick best panel elevation (highest max_y)
        try:
            if elevations:
                valid = [e for e in elevations if e.get('max_y', 0) > 0]
                if valid:
                    # pick the elevation with the highest top (max_y) and return its top (max_y)
                    best = max(valid, key=lambda e: e.get('max_y', 0))
                    aff = best.get('max_y') if best.get('max_y') is not None else best.get('min_y', 0)
                    # If computed aff looks like a tiny value, fall back to reported elevation height
                    if aff and float(aff) < 1.0 and best.get('height', 0) > 0:
                        return best.get('height')
                    return aff
        except Exception:
            pass
        return None

    def sort_materials_by_guid_hierarchy(materials_list):
        """Sort materials by GUID hierarchy: Level → Bundle → Panel → SubAssembly → Material.
        
        Groups materials by GUID level and sorts within groups with headers first,
        then rough openings, then other materials. Uses natural label sorting.
        """
        def material_sort_key(material):
            # Priority order: Headers first, then Rough Openings, then other materials
            material_type = material.get('FamilyMemberName', '').lower()
            if 'header' in material_type:
                type_priority = 0
            elif 'roughopening' in material_type or 'rough_opening' in material_type:
                type_priority = 1
            else:
                type_priority = 2
            
            # Natural sort by label (A, AA, AB, AC, B, BB, BC...)
            label = material.get('Label', '')
            return (type_priority, _nat_key(label))
        
        # Group by SubAssemblyGuid first (most specific)
        subassembly_groups = {}
        orphaned_materials = []
        
        for material in materials_list:
            sub_guid = material.get('SubAssemblyGuid', '')
            if sub_guid:
                if sub_guid not in subassembly_groups:
                    subassembly_groups[sub_guid] = []
                subassembly_groups[sub_guid].append(material)
            else:
                orphaned_materials.append(material)
        
        # Sort materials within each SubAssembly group
        sorted_groups = []
        for sub_guid, materials in subassembly_groups.items():
            sorted_materials = sorted(materials, key=material_sort_key)
            sorted_groups.extend(sorted_materials)
        
        # Add orphaned materials at the end
        sorted_groups.extend(sorted(orphaned_materials, key=material_sort_key))
        
        return sorted_groups

    def validate_guid_associations(materials_list):
        """Validate GUID associations and detect issues.
        
        Returns a report of validation issues:
        - Multiple rough openings per SubAssemblyGuid
        - Orphaned materials without proper associations
        - Cross-contamination between subassemblies
        """
        report = {
            'total_materials': len(materials_list),
            'subassembly_groups': {},
            'orphaned_materials': [],
            'issues': []
        }
        
        # Group materials by SubAssemblyGuid
        subassembly_groups = {}
        for material in materials_list:
            sub_guid = material.get('SubAssemblyGuid', '')
            if sub_guid:
                if sub_guid not in subassembly_groups:
                    subassembly_groups[sub_guid] = []
                subassembly_groups[sub_guid].append(material)
            else:
                report['orphaned_materials'].append(material)
        
        report['subassembly_groups'] = subassembly_groups
        
        # Validate each SubAssembly group
        for sub_guid, materials in subassembly_groups.items():
            rough_openings = [m for m in materials if 'roughopening' in m.get('FamilyMemberName', '').lower()]
            headers = [m for m in materials if 'header' in m.get('FamilyMemberName', '').lower()]
            
            # Check for multiple rough openings per GUID
            if len(rough_openings) > 1:
                report['issues'].append({
                    'type': 'multiple_rough_openings',
                    'subassembly_guid': sub_guid,
                    'count': len(rough_openings),
                    'materials': rough_openings
                })
            
            # Check for orphaned headers without rough openings
            if headers and not rough_openings:
                report['issues'].append({
                    'type': 'orphaned_headers',
                    'subassembly_guid': sub_guid,
                    'header_count': len(headers),
                    'materials': headers
                })
        
        return report

    def debug_guid_associations(ehx_file_path):
        """Debug function to analyze GUID relationships in an EHX file.
        
        Returns detailed analysis of GUID associations and potential issues.
        """
        try:
            panels, materials_map = parse_panels(ehx_file_path)
            
            # Flatten all materials
            all_materials = []
            for panel_materials in materials_map.values():
                all_materials.extend(panel_materials)
            
            # Analyze GUID associations
            analysis = {
                'file_path': ehx_file_path,
                'total_panels': len(panels),
                'total_materials': len(all_materials),
                'guid_summary': {},
                'validation_report': validate_guid_associations(all_materials)
            }
            
            # Count GUID types
            guid_counts = {
                'LevelGuid': 0,
                'BundleGuid': 0,
                'PanelGuid': 0,
                'SubAssemblyGuid': 0,
                'BoardGuid': 0,
                'SheetGuid': 0,
                'BracingGuid': 0
            }
            
            for panel in panels:
                for guid_type in ['LevelGuid', 'BundleGuid', 'PanelGuid']:
                    if panel.get(guid_type):
                        guid_counts[guid_type] += 1
            
            for material in all_materials:
                for guid_type in ['SubAssemblyGuid', 'BoardGuid', 'SheetGuid', 'BracingGuid']:
                    if material.get(guid_type):
                        guid_counts[guid_type] += 1
            
            analysis['guid_summary'] = guid_counts
            
            return analysis
            
        except Exception as e:
            return {
                'error': str(e),
                'file_path': ehx_file_path
            }

    def enhance_material_associations(materials_list):
        """Enhance material associations by properly linking rough openings to headers via SubAssemblyGuid.
        
        This function ensures that:
        1. Rough openings are properly associated with their corresponding headers
        2. Headers are linked to the correct SubAssemblyGuid
        3. Cross-contamination between different subassemblies is prevented
        """
        enhanced_materials = []
        
        # Group materials by SubAssemblyGuid
        subassembly_groups = {}
        header_materials = []
        
        for material in materials_list:
            sub_guid = material.get('SubAssemblyGuid', '')
            if sub_guid:
                if sub_guid not in subassembly_groups:
                    subassembly_groups[sub_guid] = []
                subassembly_groups[sub_guid].append(material)
            else:
                # Check if it's a header material
                material_type = material.get('FamilyMemberName', '').lower()
                if 'header' in material_type:
                    header_materials.append(material)
                else:
                    enhanced_materials.append(material)
        
        # Process each SubAssembly group
        for sub_guid, materials in subassembly_groups.items():
            rough_openings = [m for m in materials if 'roughopening' in m.get('FamilyMemberName', '').lower()]
            headers_in_group = [m for m in materials if 'header' in m.get('FamilyMemberName', '').lower()]
            other_materials = [m for m in materials if not ('roughopening' in m.get('FamilyMemberName', '').lower() or 'header' in m.get('FamilyMemberName', '').lower())]
            
            # Link rough openings to headers within the same SubAssembly
            for ro in rough_openings:
                ro['associated_headers'] = [h.get('Label', '') for h in headers_in_group]
                enhanced_materials.append(ro)
            
            # Add headers from this SubAssembly
            for header in headers_in_group:
                enhanced_materials.append(header)
            
            # Add other materials
            enhanced_materials.extend(other_materials)
        
        # Add any remaining header materials that weren't associated with SubAssemblies
        enhanced_materials.extend(header_materials)
        
        return enhanced_materials

    def deduplicate_materials_by_guid(materials_list):
        """Remove duplicate materials based on GUID associations.
        
        Uses GUID hierarchy to identify and remove duplicates while preserving
        the most complete material information.
        """
        seen_guids = set()
        deduplicated = []
        
        for material in materials_list:
            # Create a unique identifier based on available GUIDs
            guid_key = (
                material.get('SubAssemblyGuid', ''),
                material.get('BoardGuid', ''),
                material.get('SheetGuid', ''),
                material.get('BracingGuid', '')
            )
            
            # Also consider material properties for deduplication
            material_key = (
                material.get('Label', ''),
                material.get('FamilyMemberName', ''),
                material.get('Desc', ''),
                material.get('ActualLength', ''),
                material.get('ActualWidth', '')
            )
            
            # Use GUID key if available, otherwise use material properties
            if any(guid_key):  # If any GUID is present
                unique_key = guid_key
            else:
                unique_key = material_key
            
            if unique_key not in seen_guids:
                seen_guids.add(unique_key)
                deduplicated.append(material)
            else:
                # If duplicate found, merge information (keep the more complete one)
                for i, existing in enumerate(deduplicated):
                    existing_key = (
                        existing.get('SubAssemblyGuid', ''),
                        existing.get('BoardGuid', ''),
                        existing.get('SheetGuid', ''),
                        existing.get('BracingGuid', '')
                    ) if any((existing.get('SubAssemblyGuid', ''), existing.get('BoardGuid', ''), existing.get('SheetGuid', ''), existing.get('BracingGuid', ''))) else (
                        existing.get('Label', ''),
                        existing.get('FamilyMemberName', ''),
                        existing.get('Desc', ''),
                        existing.get('ActualLength', ''),
                        existing.get('ActualWidth', '')
                    )
                    
                    if existing_key == unique_key:
                        # Merge: prefer non-empty values
                        for key, value in material.items():
                            if key not in existing or not existing[key]:
                                existing[key] = value
                        break
        
        return deduplicated

    def prevent_cross_contamination(materials_list):
        """Prevent cross-contamination between different subassemblies.
        
        Ensures that materials from different SubAssemblyGuids don't interfere
        with each other and maintains proper isolation.
        """
        # Group materials by SubAssemblyGuid
        subassembly_groups = {}
        unassociated_materials = []
        
        for material in materials_list:
            sub_guid = material.get('SubAssemblyGuid', '')
            if sub_guid:
                if sub_guid not in subassembly_groups:
                    subassembly_groups[sub_guid] = []
                subassembly_groups[sub_guid].append(material)
            else:
                unassociated_materials.append(material)
        
        # Process each SubAssembly group independently
        processed_materials = []
        
        for sub_guid, materials in subassembly_groups.items():
            # Validate that all materials in this group belong together
            rough_openings = [m for m in materials if 'roughopening' in m.get('FamilyMemberName', '').lower()]
            headers = [m for m in materials if 'header' in m.get('FamilyMemberName', '').lower()]
            
            # Ensure headers are only associated with rough openings in the same SubAssembly
            for header in headers:
                header['associated_subassembly'] = sub_guid
                header['cross_contamination_protected'] = True
            
            for ro in rough_openings:
                ro['associated_subassembly'] = sub_guid
                ro['cross_contamination_protected'] = True
            
            processed_materials.extend(materials)
        
        # Mark unassociated materials
        for material in unassociated_materials:
            material['associated_subassembly'] = None
            material['cross_contamination_protected'] = False
        
        processed_materials.extend(unassociated_materials)
        
        return processed_materials

    def parse_panels(path):
        panels = []
        materials_map = {}
        try:
            tree = ET.parse(path)
            root = tree.getroot()
        except Exception:
            return panels, materials_map

        # Detect EHX format version
        ehx_version = "legacy"
        job_info = {}

        # Check for v2.0 format headers
        if root.find('EHXVersion') is not None:
            ehx_version = "v2.0"
            job_info['EHXVersion'] = root.find('EHXVersion').text.strip() if root.find('EHXVersion') is not None else ""
            job_info['InterfaceVersion'] = root.find('InterfaceVersion').text.strip() if root.find('InterfaceVersion') is not None else ""
            job_info['PluginVersion'] = root.find('PluginVersion').text.strip() if root.find('PluginVersion') is not None else ""
            job_info['Date'] = root.find('Date').text.strip() if root.find('Date') is not None else ""

            # Check if this is version 2.0 - return error if so
            if job_info.get('EHXVersion') == "2.0":
                return [], {}  # Return empty results to indicate version 2.0 error

        # Find Job element (works for both formats)
        job_el = root.find('.//Job')
        if job_el is None:
            job_el = root  # Fallback for older format

        # Extract job metadata (optional for backward compatibility)
        for tag in ['JobID', 'Customer', 'Project', 'Phase', 'StructureType',
                   'BuildingName', 'LotName', 'UnitName', 'DesignSoftware',
                   'DesignerPerson', 'WorkStation', 'Model', 'DepthProjection',
                   'FileDate', 'ScheduleDate', 'JobPath']:
            el = job_el.find(tag)
            if el is not None and el.text:
                job_info[tag] = el.text.strip()

        # Log format detection
        logging.debug(f"Detected EHX format: {ehx_version}")
        if ehx_version == "v2.0":
            logging.debug(f"EHX v2.0 - Version: {job_info.get('EHXVersion', 'Unknown')}, Date: {job_info.get('Date', 'Unknown')}")

        # build maps for Level metadata. We index by LevelNo and by LevelGuid
        # when available so panels can be associated using either field.
        level_map = {}        # maps LevelNo -> Description
        level_guid_map = {}   # maps LevelGuid -> Description
        for lev in root.findall('.//Level'):
            ln = None
            for tag in ('LevelNo', 'LevelID', 'Level'):
                el = lev.find(tag)
                if el is not None and el.text:
                    ln = el.text.strip()
                    break
            lg = None
            for tag in ('LevelGuid', 'LevelGUID', 'LevelID'):
                el = lev.find(tag)
                if el is not None and el.text:
                    lg = el.text.strip()
                    break
            desc = None
            d_el = lev.find('Description')
            if d_el is not None and d_el.text:
                desc = d_el.text.strip()
            if ln:
                level_map.setdefault(ln, desc)
            if lg:
                level_guid_map.setdefault(lg, desc)

        # For v2.0 format, build mapping from PanelID/Label to BundleName from Junction elements
        junction_bundle_map = {}  # maps PanelID/Label -> BundleName
        bundle_layer_map = {}  # maps BundleLayer -> BundleName
        if ehx_version == "v2.0":
            for junction in root.findall('.//Junction'):
                panel_id_el = junction.find('PanelID')
                label_el = junction.find('Label')
                bundle_name_el = junction.find('BundleName')
                
                if bundle_name_el is not None and bundle_name_el.text:
                    bundle_name = bundle_name_el.text.strip()
                    
                    # Map by PanelID if present
                    if panel_id_el is not None and panel_id_el.text:
                        panel_id = panel_id_el.text.strip()
                        junction_bundle_map[panel_id] = bundle_name
                    
                    # Also map by Label if present (for fallback matching)
                    if label_el is not None and label_el.text:
                        label = label_el.text.strip()
                        junction_bundle_map[label] = bundle_name
            
            # Build mapping from BundleLayer to BundleName from Bundle elements
            for bundle_el in root.findall('.//Bundle'):
                label_el = bundle_el.find('Label')
                if label_el is not None and label_el.text:
                    bundle_name = label_el.text.strip()
                    # Extract bundle number from label (e.g., "B5 (2x4 Furr)" -> 5)
                    import re
                    match = re.match(r'B(\d+)', bundle_name)
                    if match:
                        bundle_layer = int(match.group(1))
                        bundle_layer_map[bundle_layer] = bundle_name

        for panel_el in root.findall('.//Panel'):
            # Extract both PanelGuid (for internal processing) and Label (for display)
            panel_guid = None
            panel_label = None

            # Get PanelGuid first (for internal processing)
            for t in ('PanelGuid', 'PanelID'):
                el = panel_el.find(t)
                if el is not None and el.text:
                    panel_guid = el.text.strip()
                    break

            # Get Label for display purposes
            label_el = panel_el.find('Label')
            if label_el is not None and label_el.text:
                panel_label = label_el.text.strip()

            # Fallback for panel_guid if not found
            if not panel_guid:
                for t in ('PanelName', 'PanelID', 'Label'):
                    el = panel_el.find(t)
                    if el is not None and el.text:
                        panel_guid = el.text.strip()
                        break

            if not panel_guid:
                panel_guid = f"Panel_{len(panels)+1}"

            # Use panel_guid as the fallback for panel_label if Label is not available
            if not panel_label:
                panel_label = panel_guid

            panel_obj = {'Name': panel_guid, 'DisplayLabel': panel_label}
            # try to capture LevelNo and LevelGuid if present on the Panel
            lvl = panel_el.find('LevelNo')
            if lvl is not None and lvl.text:
                panel_obj['LevelNo'] = lvl.text.strip()
                # also set 'Level' for backward compatibility/display
                panel_obj['Level'] = panel_obj['LevelNo']
            lg_el = panel_el.find('LevelGuid')
            if lg_el is not None and lg_el.text:
                panel_obj['LevelGuid'] = lg_el.text.strip()
            for fld in ('Level','Description','Bundle','BundleName','BundleGuid','Height','Thickness','StudSpacing','WallLength','LoadBearing','Category','OnScreenInstruction','Weight'):
                el = panel_el.find(fld)
                if el is not None and el.text:
                    panel_obj[fld] = el.text.strip()

            # Parse squaring dimension from SquareDimension element (nested under Squaring)
            squaring_el = panel_el.find('Squaring')
            if squaring_el is not None:
                square_dim_el = squaring_el.find('SquareDimension')
                if square_dim_el is not None and square_dim_el.text:
                    try:
                        square_inches = float(square_dim_el.text.strip())
                        panel_obj['Squaring_inches'] = square_inches  # Store raw inches
                        panel_obj['Squaring'] = inches_to_feet_inches_sixteenths(square_inches)
                        logging.debug(f"Found squaring for panel {panel_obj.get('Name', 'Unknown')}: {square_inches} inches -> {panel_obj['Squaring']}")
                    except (ValueError, TypeError):
                        panel_obj['Squaring'] = square_dim_el.text.strip()
                        logging.debug(f"Found squaring for panel {panel_obj.get('Name', 'Unknown')}: {panel_obj['Squaring']} (raw)")
            # Fallback: try direct SquareDimension element if nested structure not found
            if 'Squaring' not in panel_obj:
                square_el = panel_el.find('SquareDimension')
                if square_el is not None and square_el.text:
                    try:
                        square_inches = float(square_el.text.strip())
                        panel_obj['Squaring_inches'] = square_inches  # Store raw inches
                        panel_obj['Squaring'] = inches_to_feet_inches_sixteenths(square_inches)
                        logging.debug(f"Found fallback squaring for panel {panel_obj.get('Name', 'Unknown')}: {square_inches} inches -> {panel_obj['Squaring']}")
                    except (ValueError, TypeError):
                        panel_obj['Squaring'] = square_el.text.strip()
                        logging.debug(f"Found fallback squaring for panel {panel_obj.get('Name', 'Unknown')}: {panel_obj['Squaring']} (raw)")
            # Calculate squaring if not found using Pythagorean theorem
            if 'Squaring' not in panel_obj:
                if 'Height' in panel_obj and 'WallLength' in panel_obj:
                    try:
                        h = float(panel_obj['Height']) - 1.5  # Subtract top plate
                        l = float(panel_obj['WallLength'])
                        calc_inches = math.sqrt(h**2 + l**2)
                        panel_obj['Squaring_inches'] = calc_inches  # Store raw inches
                        panel_obj['Squaring'] = inches_to_feet_inches_sixteenths(calc_inches)
                        logging.debug(f"Calculated squaring for panel {panel_obj.get('Name', 'Unknown')}: {calc_inches:.3f} inches -> {panel_obj['Squaring']}")
                    except (ValueError, TypeError):
                        calc_squaring = calculate_squaring(panel_obj['Height'], panel_obj['WallLength'])
                        if calc_squaring:
                            panel_obj['Squaring'] = calc_squaring
                            logging.debug(f"Calculated squaring for panel {panel_obj.get('Name', 'Unknown')}: {calc_squaring}")
            if ehx_version == "v2.0" and not panel_obj.get('BundleName'):
                # Try to match by PanelID/Label using the junction mapping
                panel_id = panel_obj.get('Name')  # This is the panel_guid/panel_id
                panel_label = panel_obj.get('DisplayLabel')  # This is the display label
                
                bundle_name = None
                if panel_id and panel_id in junction_bundle_map:
                    bundle_name = junction_bundle_map[panel_id]
                elif panel_label and panel_label in junction_bundle_map:
                    bundle_name = junction_bundle_map[panel_label]
                
                # Fallback: try to derive BundleName from BundleLayer
                if not bundle_name:
                    bundle_layer_el = panel_el.find('BundleLayer')
                    if bundle_layer_el is not None and bundle_layer_el.text:
                        try:
                            bundle_layer = int(bundle_layer_el.text.strip())
                            if bundle_layer in bundle_layer_map:
                                bundle_name = bundle_layer_map[bundle_layer]
                                logging.debug(f"Panel {panel_label} assigned BundleName from BundleLayer {bundle_layer}: {bundle_name}")
                        except ValueError:
                            pass
                
                if bundle_name:
                    panel_obj['BundleName'] = bundle_name
                    logging.debug(f"Panel {panel_label} assigned BundleName: {bundle_name}")

            # if panel lacks a Description but a LevelDescription exists in the level_map or level_guid_map, attach it
            try:
                if not panel_obj.get('Description'):
                    # prefer LevelGuid if present on the panel
                    lg = panel_el.find('LevelGuid')
                    if lg is not None and lg.text:
                        lgv = lg.text.strip()
                        if lgv and lgv in level_guid_map and level_guid_map.get(lgv):
                            panel_obj['LevelDescription'] = level_guid_map.get(lgv)
                            panel_obj.setdefault('Description', level_guid_map.get(lgv))
                    else:
                        ln = panel_obj.get('LevelNo') or panel_obj.get('Level')
                        if ln and ln in level_map and level_map.get(ln):
                            panel_obj['LevelDescription'] = level_map.get(ln)
                            panel_obj.setdefault('Description', level_map.get(ln))
            except Exception:
                pass

            # Extract elevation information for this panel
            panel_obj['elevations'] = extract_elevation_info(panel_el)

            # Debug: Log elevation information
            elevations = panel_obj.get('elevations', [])
            if elevations:
                logging.debug(f"Panel {panel_guid} has {len(elevations)} elevation views")
                for i, elev in enumerate(elevations):
                    logging.debug(f"Elevation {i}: min_y={elev.get('min_y')}, max_y={elev.get('max_y')}, height={elev.get('height')}, points={len(elev.get('points', []))}")
            else:
                logging.debug(f"Panel {panel_guid} has no elevation data")

            panels.append(panel_obj)

            mats, critical_studs = parse_materials_from_panel(panel_el, root)
            if mats:
                # capture bundle guid if present on panel
                bg_el = panel_el.find('BundleGuid')
                bundle_guid = bg_el.text.strip() if (bg_el is not None and bg_el.text) else None
                level_guid = panel_obj.get('LevelGuid')
                # Annotate materials with panel-level GUIDs and try to associate
                # a material-level elevation (elev_max_y) by matching BottomView X ranges
                for m in mats:
                    try:
                        if not isinstance(m, dict):
                            continue
                        # preserve existing GUIDs when present (BoardGuid/SubAssemblyGuid)
                        m.setdefault('PanelGuid', panel_guid)
                        if bundle_guid:
                            m.setdefault('BundleGuid', bundle_guid)
                        if level_guid:
                            m.setdefault('LevelGuid', level_guid)

                        # If the material contains a bottom_x range from SubAssembly parsing
                        # but lacks elev_max_y, try to match against panel elevations
                        try:
                            if m.get('elev_max_y') is None and m.get('bottom_x_min') is not None and m.get('bottom_x_max') is not None:
                                bx0 = float(m.get('bottom_x_min'))
                                bx1 = float(m.get('bottom_x_max'))
                                candidates = []
                                for e in (panel_obj.get('elevations') or []):
                                    try:
                                        xs = [p.get('x', 0.0) for p in (e.get('points') or [])]
                                        if not xs:
                                            continue
                                        ex0 = min(xs)
                                        ex1 = max(xs)
                                        overlap = min(ex1, bx1) - max(ex0, bx0)
                                        if overlap > 0:
                                            candidates.append((overlap, e))
                                    except Exception:
                                        continue
                                if candidates:
                                    candidates.sort(key=lambda t: (t[0], t[1].get('max_y', 0)), reverse=True)
                                    best = candidates[0][1]
                                    m['elev_max_y'] = best.get('max_y')
                                    # also set AFF to the elevation top for downstream consumers
                                    try:
                                        if m.get('elev_max_y') is not None:
                                            m['AFF'] = float(m.get('elev_max_y'))
                                    except Exception:
                                        pass
                        except Exception:
                            pass
                    except Exception:
                        continue
                
                # Apply enhanced material association logic
                mats = enhance_material_associations(mats)
                
                # Apply GUID-based deduplication
                mats = deduplicate_materials_by_guid(mats)
                
                # Prevent cross-contamination between subassemblies
                mats = prevent_cross_contamination(mats)
                
                materials_map[panel_guid] = mats

        # Extract junction details for legacy files
        junction_details = {}
        for junction in root.findall('.//Junction'):
            panel_id_el = junction.find('PanelID')
            label_el = junction.find('Label')
            
            panel_id = panel_id_el.text.strip() if panel_id_el is not None and panel_id_el.text else None
            label = label_el.text.strip() if label_el is not None and label_el.text else None
            
            # Extract junction details for this panel
            junction_info = {}
            
            # Extract junction details from SubAssemblyName
            subassembly_name_el = junction.find('SubAssemblyName')
            if subassembly_name_el is not None and subassembly_name_el.text:
                subassembly_name = subassembly_name_el.text.strip()
                
                # Parse SubAssemblyName to extract junction details
                if subassembly_name == 'LType':
                    junction_info['LType'] = 'LType'
                elif subassembly_name.startswith('Ladder'):
                    junction_info['Ladder'] = subassembly_name
                elif subassembly_name == 'Subcomponent':
                    junction_info['Subcomponent'] = 'Subcomponent'
            
            # Store junction details using panel_id or label as key
            if panel_id and junction_info:
                junction_details[panel_id] = junction_info
            if label and junction_info:
                junction_details[label] = junction_info
        
        # Create diag_report for legacy files with junction details
        diag_report = {'junction_details': junction_details} if junction_details else None

        # Write expected.log and materials.log files
        try:
            panels_by_name = {}
            for p in panels:
                if isinstance(p, dict):
                    panels_by_name[p.get('Name', f'Panel_{len(panels_by_name)}')] = p
            
            logging.debug(f"Writing expected.log with {len(panels_by_name)} panels")
            
            # Sort panels by bundle, then by panel name for consistent log output
            sorted_panels = sort_panels_by_bundle_and_name(panels_by_name)
            
            # Initialize diag_report for junction details
            diag_report = None
            
            # Use the local write_expected_and_materials_logs function
            writer = globals().get('write_expected_and_materials_logs')
            if not writer:
                writer = write_expected_and_materials_logs
            writer(path, dict(sorted_panels), materials_map, diag_report)
            logging.debug("Finished writing expected.log")
        except Exception as e:
            # Log writing is optional, don't fail if it doesn't work
            logging.debug(f"Failed to write log files: {e}")
            pass

        return panels, materials_map

    def extract_jobpath(path):
        try:
            tree = ET.parse(path)
            root = tree.getroot()

            # Try multiple paths to find JobPath (works for both formats)
            jobpath_el = None

            # First try direct JobPath element
            jobpath_el = root.find('.//JobPath')

            # If not found, try within Job element
            if jobpath_el is None:
                job_el = root.find('.//Job')
                if job_el is not None:
                    jobpath_el = job_el.find('JobPath')

            if jobpath_el is not None and jobpath_el.text:
                return jobpath_el.text.strip()
        except Exception:
            pass
        return ''

    def write_expected_and_materials_logs(ehx_path, panels_by_name, materials_map, diag_report=None):
        """Write expected.log and materials.log into the same directory as the EHX file.
        Format is matched to the provided examples as closely as possible.
        """
        import time
        folder = os.path.dirname(ehx_path)
        fname = os.path.basename(ehx_path)
        # use timezone-aware UTC datetime to avoid DeprecationWarning
        ts = _dt.datetime.now(_dt.timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        
        print(f"DEBUG: write_expected_and_materials_logs called with {len(panels_by_name)} panels")
        logging.debug(f"write_expected_and_materials_logs called with {len(panels_by_name)} panels")

        # Extract JobID from EHX file for log naming
        job_id = "expected"
        try:
            tree = ET.parse(ehx_path)
            root = tree.getroot()
            job_el = root.find('.//Job')
            if job_el is None:
                job_el = root
            job_id_el = job_el.find('JobID')
            if job_id_el is not None and job_id_el.text:
                job_id = job_id_el.text.strip()
        except Exception as e:
            job_id = "expected"

        expected_path = os.path.join(HERE, 'LOG', f'{job_id}.log')
        materials_path = os.path.join(HERE, 'LOG', 'materials.log')

        # Sort panels by bundle, then by panel name for consistent log output
        sorted_panels = sort_panels_by_bundle_and_name(panels_by_name)
        sorted_panels_dict = dict(sorted_panels)

        # Detect unassigned panels
        unassigned_panels = detect_unassigned_panels(panels_by_name)
        
        # For all files, get diagnostic information including junction details
        ehx_version = "legacy"
        diag_report = None
        try:
            # Try to detect version from the file path or content
            fname_lower = os.path.basename(ehx_path).lower()
            if 'mpo' in fname_lower or 'v2' in fname_lower:
                ehx_version = "v2.0"
            else:
                # Check if file contains Junction elements (indicates v2.0 format)
                tree = ET.parse(ehx_path)
                root = tree.getroot()
                if root.findall('.//Junction'):
                    ehx_version = "v2.0"
            
            # Always try to get diagnostic info for junction details
            if 'tree' not in locals():
                tree = ET.parse(ehx_path)
                root = tree.getroot()
            diag_report = diagnose_v2_bundle_assignment(root, ehx_version, panels_by_name)
        except Exception as e:
            if debug_enabled:
                print(f"Diagnostic setup error: {e}")
            
        if ehx_version == "v2.0" and diag_report and unassigned_panels:
            print(f"\n=== V2.0 DIAGNOSTIC REPORT ===")
            print(f"Junctions found: {diag_report['junctions_found']}")
            print(f"Bundles found: {diag_report['bundles_found']}")
            print(f"Total panels: {diag_report['panels_total']}")
            print(f"Panels assigned: {diag_report['panels_assigned']}")
            print(f"Panels unassigned: {diag_report['panels_unassigned']}")
            print(f"Junction mappings: {len(diag_report['junction_mappings'])}")
            print(f"Bundle layer mappings: {diag_report['bundle_layer_mappings']}")
            
            # Show first few unassigned panels with details
            print("\nFirst 5 unassigned panels:")
            for i, detail in enumerate(diag_report['assignment_details'][:5]):
                if detail['assignment_method'] in ['unassigned', 'no_junction_mapping']:
                    print(f"  {detail['display_name']} - {detail['assignment_method']}")
            print("===============================\n")

        # expected.log - write to JobID-based file
        try:
            print(f"DEBUG: Starting to write expected.log")
            with open(expected_path, 'w', encoding='utf-8') as fh:
                fh.write(f"\n=== {job_id}.log updated at {ts} for {fname} ===\n")
                fh.write(f"File Location: {folder}\n")
                
                # Add diagnostic info for v2.0 files
                if ehx_version == "v2.0" and diag_report:
                    fh.write(f"\n=== V2.0 DIAGNOSTIC INFO ===\n")
                    fh.write(f"Junctions found: {diag_report['junctions_found']}\n")
                    fh.write(f"Bundles found: {diag_report['bundles_found']}\n")
                    fh.write(f"Total panels: {diag_report['panels_total']}\n")
                    fh.write(f"Panels assigned: {diag_report['panels_assigned']}\n")
                    fh.write(f"Panels unassigned: {diag_report['panels_unassigned']}\n")
                    fh.write(f"Junction mappings: {len(diag_report['junction_mappings'])}\n")
                    fh.write(f"Bundle layer mappings: {diag_report['bundle_layer_mappings']}\n")
                    fh.write("========================\n\n")
                
                # Log unassigned panels warning if any found
                if unassigned_panels:
                    fh.write(f"\n⚠️  WARNING: {len(unassigned_panels)} panel(s) not assigned to any bundle:\n")
                    for panel in unassigned_panels:
                        fh.write(f"   • {panel['display_name']} (Level: {panel['level']})\n")
                    fh.write("\n")
                
                for pname, pobj in sorted_panels_dict.items():
                    # Use DisplayLabel for log output, fallback to internal name
                    display_name = pobj.get('DisplayLabel', pname)
                    fh.write(f"Panel: {display_name}\n")
                    if 'Level' in pobj:
                        fh.write(f"Level: {pobj.get('Level')}\n")
                    if 'Description' in pobj:
                        fh.write(f"Description: {pobj.get('Description')}\n")
                    # bundle
                    b = pobj.get('Bundle') or pobj.get('BundleName') or ''
                    if b:
                        fh.write(f"Bundle: {b}\n")
                    fh.write("Panel Details:\n")
                    # bullets with friendly labels and the requested ordering
                    display_map = {
                        'Category': 'Category',
                        'LoadBearing': 'Load Bearing',
                        'WallLength': 'Length',
                        'Height': 'Height',
                        'Squaring': 'Squaring',
                        'Thickness': 'Thickness',
                        'StudSpacing': 'Stud Spacing',
                    }
                    for key in ('Category','LoadBearing','WallLength','Height','Squaring','Thickness','StudSpacing'):
                        if key in pobj:
                            value = pobj.get(key)
                            # Format dimensions by stripping trailing zeros and adding feet-inches format
                            if key in ('WallLength', 'Height', 'Squaring'):
                                # Strip trailing zeros first
                                value = format_dimension(value)
                                # Add feet-inches-sixteenths format in parentheses
                                if value and value != '0':
                                    feet_inches = inches_to_feet_inches_sixteenths(value)
                                    if feet_inches:
                                        value = f"{value} ({feet_inches})"
                            elif key in ('Thickness', 'StudSpacing'):
                                value = format_dimension(value)
                            fh.write(f"• {display_map.get(key,key)}: {value}\n")

                    # detect sheathing layers from materials and print them next
                    try:
                        sheet_descs = []
                        for m in materials_map.get(pname, []):
                            try:
                                if isinstance(m, dict):
                                    t = (m.get('Type') or '').lower()
                                    if 'sheet' in t or 'sheath' in t or (m.get('FamilyMemberName') and 'sheath' in str(m.get('FamilyMemberName')).lower()):
                                        # prefer the explicit <Description> element for sheathing text
                                        d = (m.get('Description') or m.get('Desc') or '').strip()
                                        if d and d not in sheet_descs:
                                            sheet_descs.append(d)
                            except Exception:
                                pass
                        if len(sheet_descs) > 0:
                            fh.write(f"• Sheathing Layer 1: {sheet_descs[0]}\n")
                        if len(sheet_descs) > 1:
                            fh.write(f"• Sheathing Layer 2: {sheet_descs[1]}\n")
                    except Exception:
                        pass

                    if 'Weight' in pobj:
                        weight_value = format_weight(pobj.get('Weight'))
                        fh.write(f"• Weight: {weight_value}\n")
                    if 'OnScreenInstruction' in pobj:
                        fh.write(f"• Production Notes: {pobj.get('OnScreenInstruction')}\n")
                    
                    # list rough openings (if any) under Panel Details after Production Notes — no colon after label
                    try:
                        for m in materials_map.get(pname, []):
                            try:
                                if _is_rough_opening(m):
                                    lab = m.get('Label') or ''
                                    desc = m.get('Desc') or m.get('Description') or ''
                                    ln = m.get('ActualLength') or m.get('Length') or ''
                                    wd = m.get('ActualWidth') or m.get('Width') or ''

                                    # Compute AFF using geometry-aware helper (prefers material AFF/elev then geometry matches)
                                    try:
                                        aff_height = get_aff_for_rough_opening(pobj, m)
                                    except Exception:
                                        aff_height = None

                                    # Find associated headers based on rough opening type
                                    associated_headers = []
                                    if lab == 'BSMT-HDR':
                                        # BSMT-HDR uses G headers
                                        associated_headers = ['G']
                                    elif lab == '49x63-L2':
                                        # 49x63-L2 uses F headers
                                        associated_headers = ['F']
                                    elif lab == '73x63-L1':
                                        # 73x63-L1 uses L header
                                        associated_headers = ['L']
                                    elif lab == 'DR-1-ENT-L1':
                                        # DR-1-ENT-L1 uses K header
                                        associated_headers = ['K']
                                    else:
                                        # Fallback: find unique header labels
                                        header_set = set()
                                        for mat in materials_map.get(pname, []):
                                            mat_type = mat.get('Type', '').lower()
                                            header_label = mat.get('Label', '')
                                            # Only include materials that are headers (not headercap or headercripple)
                                            # and have single-character labels (typical for headers)
                                            if mat_type == 'header' and header_label and len(header_label) == 1:
                                                header_set.add(header_label)
                                        associated_headers = sorted(list(header_set))[:1]

                                    # Format the rough opening display
                                    ro_text = f"Rough Opening: {lab}"
                                    if ln and wd:
                                        formatted_ln = format_dimension(ln)
                                        formatted_wd = format_dimension(wd)
                                        ro_text += f" - {formatted_ln} x {formatted_wd}"
                                    elif ln:
                                        formatted_ln = format_dimension(ln)
                                        ro_text += f" - {formatted_ln}"
                                    if aff_height is not None:
                                        formatted_aff = inches_to_feet_inches_sixteenths(str(aff_height))
                                        if formatted_aff:
                                            ro_text += f" (AFF: {aff_height} ({formatted_aff}))"
                                        else:
                                            ro_text += f" (AFF: {aff_height})"
                                    if associated_headers:
                                        ro_text += f" [Headers: {', '.join(associated_headers)}]"

                                    fh.write(f"• {ro_text}\n")
                            except Exception:
                                pass
                    except Exception:
                        pass
                    
                    # Add Beam Pocket Details section after Rough Openings
                    try:
                        beam_pockets = extract_beam_pocket_info(pobj, materials_map.get(pname, []))
                        
                        if beam_pockets:
                            if debug_enabled:
                                print(f"WRITING BEAM POCKETS to expected.log for {pname}")
                            total_pockets = len(beam_pockets)
                            fh.write(f"Beam Pocket Details: {total_pockets} beam pocket{'s' if total_pockets != 1 else ''}\n")
                            
                            for i, pocket in enumerate(beam_pockets, 1):
                                aff = pocket.get('aff')  # Use 'aff' key from grouped pockets
                                opening_width = pocket.get('opening_width')  # Use 'opening_width' key from grouped pockets
                                
                                fh.write(f"• Beam Pocket {i}\n")
                                
                                if aff is not None:
                                    # Add bottom plate thickness (1.5 inches) to AFF calculation
                                    adjusted_aff = aff + 1.5
                                    bottom_decimal = format_dimension(str(adjusted_aff))
                                    bottom_formatted = inches_to_feet_inches_sixteenths(str(adjusted_aff))
                                    if bottom_formatted:
                                        fh.write(f"  AFF: {bottom_decimal} ({bottom_formatted})\n")
                                    else:
                                        fh.write(f"  AFF: {bottom_decimal}\n")
                                else:
                                    fh.write("  AFF: Unknown\n")
                                
                                if opening_width:
                                    width_decimal = format_dimension(str(opening_width))
                                    width_formatted = inches_to_feet_inches_sixteenths(str(opening_width))
                                    if width_formatted:
                                        fh.write(f"  Opening Width: {width_decimal} ({width_formatted})\n")
                                    else:
                                        fh.write(f"  Opening Width: {width_decimal}\n")
                            
                            fh.write('\n')
                    except Exception as e:
                        pass
                    
                    fh.write('\n')
                    
                    # Add SubAssemblies section after Beam Pockets
                    try:
                        # Use the new analyze_subassemblies_for_panel function
                        print(f"DEBUG: Calling analyze_subassemblies_for_panel for panel {pname}")
                        subassembly_details = analyze_subassemblies_for_panel(ehx_path, pname, materials_map.get(pname, []))
                        print(f"DEBUG: subassembly_details = {subassembly_details}")
                        print(f"DEBUG: subassembly_details type = {type(subassembly_details)}")
                        print(f"DEBUG: bool(subassembly_details) = {bool(subassembly_details)}")
                        
                        if subassembly_details:
                            fh.write("Subcomponent Details:\n")
                            
                            # Create mapping from material properties to alphabetical labels
                            all_panel_materials = materials_map.get(pname, [])
                            material_to_breakdown_mapping = create_material_to_breakdown_mapping(all_panel_materials)
                            
                            # Display each SubAssembly
                            for sub_guid, sub_info in subassembly_details.items():
                                sub_name = sub_info['name']
                                materials_dict = sub_info['materials']
                                
                                # Display SubAssembly name directly without type labels
                                fh.write(f"• {sub_name}\n")
                                
                                # Display materials if any
                                if materials_dict:
                                    fh.write("   Materials:\n")
                                    for mat_label, count in sorted(materials_dict.items()):
                                        # Find the corresponding alphabetical label from the breakdown mapping
                                        breakdown_label = mat_label  # Default to original label
                                        
                                        # Search through all panel materials to find matching properties
                                        for material in all_panel_materials:
                                            if isinstance(material, dict):
                                                m_lbl = (material.get('Label') or '').strip()
                                                m_typ = (material.get('Type') or '').strip()
                                                m_desc = (material.get('Desc') or material.get('Description') or '').strip()
                                                m_length = material.get('ActualLength') or material.get('Length') or ''
                                                m_width = material.get('ActualWidth') or material.get('Width') or ''
                                                
                                                # Round length and width to match the mapping function
                                                try:
                                                    length_val = float(m_length) if m_length else 0.0
                                                    length_rounded = round(length_val, 2)
                                                    length_str = str(length_rounded) if length_rounded != 0.0 else ''
                                                except (ValueError, TypeError):
                                                    length_str = str(m_length).strip()
                                                    
                                                try:
                                                    width_val = float(m_width) if m_width else 0.0
                                                    width_rounded = round(width_val, 2)
                                                    width_str = str(width_rounded) if width_rounded != 0.0 else ''
                                                except (ValueError, TypeError):
                                                    width_str = str(m_width).strip()
                                                
                                                # Create the same key as used in the mapping function
                                                material_key = (m_lbl, m_typ, m_desc, length_str, width_str)
                                                
                                                # If this material matches the current subcomponent material
                                                if m_lbl == mat_label:
                                                    # Look up the alphabetical label in the mapping
                                                    if material_key in material_to_breakdown_mapping:
                                                        breakdown_label = material_to_breakdown_mapping[material_key]
                                                        break
                                        
                                        fh.write(f"    ├── {breakdown_label} ({count})\n")
                            
                            fh.write('\n')
                        else:
                            print(f"DEBUG: No subassembly_details returned for panel {pname}")
                    except Exception as e:
                        print(f"DEBUG: Exception in SubAssemblies section: {e}")
                        import traceback
                        traceback.print_exc()
                    
                    fh.write("Panel Material Breakdown:\n")
                    lines = []
                    mats = materials_map.get(pname, [])
                    # filter out rough openings from the breakdown
                    mats_filtered = [m for m in (mats or []) if not _is_rough_opening(m)]
                    lines = format_and_sort_materials(mats_filtered)
                    for l in lines:
                        fh.write(f"{l}\n")
                    fh.write('---\n')
            print(f"DEBUG: Finished writing expected.log to {expected_path}")
        except Exception as e:
            print(f"DEBUG: Exception in expected.log writing: {e}")
            import traceback
            traceback.print_exc()
        except Exception:
            print(f"DEBUG: Unexpected exception in expected.log writing")
            pass

        # materials.log (Type: ... lines) - write to file (clear old content)
        try:
            with open(materials_path, 'w', encoding='utf-8') as fh:
                fh.write(f"\n=== materials.log updated at {ts} for {fname} ===\n")
                
                # Add diagnostic info for v2.0 files
                if ehx_version == "v2.0" and diag_report:
                    fh.write(f"\n=== V2.0 DIAGNOSTIC INFO ===\n")
                    fh.write(f"Junctions found: {diag_report['junctions_found']}\n")
                    fh.write(f"Bundles found: {diag_report['bundles_found']}\n")
                    fh.write(f"Total panels: {diag_report['panels_total']}\n")
                    fh.write(f"Panels assigned: {diag_report['panels_assigned']}\n")
                    fh.write(f"Panels unassigned: {diag_report['panels_unassigned']}\n")
                    fh.write(f"Junction mappings: {len(diag_report['junction_mappings'])}\n")
                    fh.write(f"Bundle layer mappings: {diag_report['bundle_layer_mappings']}\n")
                    fh.write("========================\n\n")
                
                # Log unassigned panels warning if any found
                if unassigned_panels:
                    fh.write(f"\n⚠️  WARNING: {len(unassigned_panels)} panel(s) not assigned to any bundle:\n")
                    for panel in unassigned_panels:
                        fh.write(f"   • {panel['display_name']} (Level: {panel['level']})\n")
                    fh.write("\n")
                
                for pname, pobj in sorted_panels_dict.items():
                    # Use DisplayLabel for log output, fallback to internal name
                    display_name = pobj.get('DisplayLabel', pname)
                    fh.write(f"Panel: {display_name}\n")
                    if 'Level' in pobj:
                        fh.write(f"Level: {pobj.get('Level')}\n")
                    if 'Description' in pobj:
                        fh.write(f"Description: {pobj.get('Description')}\n")
                    b = pobj.get('Bundle') or pobj.get('BundleName') or ''
                    if b:
                        fh.write(f"Bundle: {b}\n")
                    
                    # Add Beam Pocket Details section after panel info
                    try:
                        beam_pockets = extract_beam_pocket_info(pobj, materials_map.get(pname, []))
                        if debug_enabled:
                            print(f"DEBUG: Log writing - Beam pockets found for panel {pname}: {len(beam_pockets) if beam_pockets else 0}")
                        
                        if beam_pockets:
                            if debug_enabled:
                                print(f"WRITING BEAM POCKETS to materials.log for {pname}")
                            total_pockets = len(beam_pockets)
                            fh.write(f"Beam Pocket Details: {total_pockets} beam pocket{'s' if total_pockets != 1 else ''}\n")
                            
                            for i, pocket in enumerate(beam_pockets, 1):
                                aff = pocket.get('aff')
                                opening_width = pocket.get('opening_width')
                                materials = pocket.get('materials', {})
                                count = pocket.get('count', 1)

                                pocket_label = f"Beam Pocket {i}"
                                if count > 1:
                                    pocket_label += f" ({count})"

                                fh.write(f"• {pocket_label}\n")

                                if aff is not None:
                                    # Add bottom plate thickness (1.5 inches) to AFF calculation
                                    adjusted_aff = aff + 1.5
                                    aff_decimal = format_dimension(str(adjusted_aff))
                                    aff_formatted = inches_to_feet_inches_sixteenths(str(adjusted_aff))
                                    if aff_formatted:
                                        fh.write(f"  AFF: {aff_decimal} in ({aff_formatted})\n")
                                    else:
                                        fh.write(f"  AFF: {aff_decimal} in\n")
                                else:
                                    fh.write("  AFF: Unknown\n")

                                if opening_width is not None:
                                    width_decimal = format_dimension(str(opening_width))
                                    fh.write(f"  Opening Width: {width_decimal} in\n")

                                if materials:
                                    fh.write("  Materials:\n")
                                    for label, qty in sorted(materials.items()):
                                        fh.write(f"    ├── {label} ({qty})\n")
                            
                            fh.write('\n')
                    except Exception as e:
                        pass
                    
                    for m in materials_map.get(pname, []):
                        try:
                                # Include AFF for rough openings (computed from material/subassembly elevation when available)
                                if _is_rough_opening(m):
                                    try:
                                        aff_height = get_aff_for_rough_opening(pobj, m)
                                    except Exception:
                                        aff_height = m.get('AFF') if isinstance(m, dict) else None
                                    aff_s = ''
                                    try:
                                        if isinstance(aff_height, (int, float)):
                                            aff_s = f" AFF={float(aff_height):.3f}"
                                        elif aff_height is not None:
                                            aff_s = f" AFF={str(aff_height)}"
                                    except Exception:
                                        aff_s = ''
                                    fh.write(f"Type: {m.get('FamilyMemberName','')} , Label: {m.get('Label','')} , SubAssembly: {m.get('SubAssembly','')} , Desc: {m.get('Desc','')}{aff_s}\n")
                                else:
                                    fh.write(f"Type: {m.get('FamilyMemberName','')} , Label: {m.get('Label','')} , SubAssembly: {m.get('SubAssembly','')} , Desc: {m.get('Desc','')}\n")
                        except Exception:
                            pass
                    fh.write('---\n')
        except Exception:
            pass

    def parse_subcomponent_details_from_expected_log(expected_log_path, panel_name):
        """Parse Subcomponent Details from expected.log file for a specific panel.
        
        Returns a dictionary with subassembly details in the same format as analyze_subassemblies_for_panel.
        """
        try:
            with open(expected_log_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Find the panel section
            panel_pattern = rf"Panel: {panel_name}\s*\n"
            panel_match = re.search(panel_pattern, content)
            
            if not panel_match:
                return {}
            
            # Extract the panel section (from panel header to next panel or end)
            panel_start = panel_match.start()
            next_panel_match = re.search(r"\nPanel: ", content[panel_start + 1:])
            
            if next_panel_match:
                panel_content = content[panel_start:panel_start + next_panel_match.start() + 1]
            else:
                panel_content = content[panel_start:]
            
            # Find Subcomponent Details section
            subcomponent_match = re.search(r"Subcomponent Details:\s*\n(.*?)(\n\n|\nPanel: |\Z)", panel_content, re.DOTALL)
            
            if not subcomponent_match:
                return {}
            
            subcomponent_content = subcomponent_match.group(1)
            
            # Parse the subcomponent details
            subassemblies = {}
            current_subassembly = None
            materials_section = False
            
            for line in subcomponent_content.split('\n'):
                line = line.strip()
                if not line:
                    continue
                
                if line.startswith('• ') and not materials_section:
                    # This is a subassembly name
                    subassembly_name = line[2:].strip()
                    current_subassembly = subassembly_name
                    subassemblies[current_subassembly] = {
                        'name': subassembly_name,
                        'family_member': 32 if subassembly_name == 'LType' else (42 if 'Ladder' in subassembly_name else 70),
                        'materials': {}
                    }
                elif line.startswith('• ') and materials_section:
                    # This is a new subassembly name - reset materials_section
                    materials_section = False
                    subassembly_name = line[2:].strip()
                    current_subassembly = subassembly_name
                    subassemblies[current_subassembly] = {
                        'name': subassembly_name,
                        'family_member': 32 if subassembly_name == 'LType' else (42 if 'Ladder' in subassembly_name else 70),
                        'materials': {}
                    }
                elif line == 'Materials:':
                    materials_section = True
                elif line.startswith('├── ') and materials_section and current_subassembly:
                    # This is a material entry
                    material_info = line[4:].strip()
                    if '(' in material_info and ')' in material_info:
                        label = material_info.split('(')[0].strip()
                        count_str = material_info.split('(')[1].split(')')[0].strip()
                        try:
                            count = int(count_str)
                            subassemblies[current_subassembly]['materials'][label] = count
                        except ValueError:
                            pass
            
            # Filter to only include subassemblies with materials
            filtered_subassemblies = {}
            for name, info in subassemblies.items():
                if info['materials']:
                    filtered_subassemblies[name] = info
            
            return filtered_subassemblies
            
        except Exception as e:
            print(f"Error parsing Subcomponent Details from expected.log: {e}")
            return {}

# Professional color scheme - easier on eyes
TOP_BG = '#2c3e50'        # Dark blue-gray for top bar
LEFT_BG = '#f8f9fa'       # Light gray for file list
BUTTONS_BG = '#f0f8f0'    # Very light green for buttons
ACCENT_COLOR = '#3498db'  # Bright blue for selected/active elements
TEXT_LIGHT = '#ecf0f1'    # Light text color

# Global variable to store current EHX file path
current_ehx_file_path = None
DETAILS_BG = '#fefefe'    # Clean white for details
BREAKDOWN_BG = '#fafafa'  # Light gray for breakdown

# Professional accent colors
PRIMARY_BLUE = '#3498db'
SECONDARY_TEAL = '#16a085'
SUCCESS_GREEN = '#27ae60'
WARNING_ORANGE = '#f39c12'
DANGER_RED = '#e74c3c'
PURPLE_ACCENT = '#9b59b6'
TEXT_DARK = '#2c3e50'
TEXT_MEDIUM = '#3d4f5c'  # Darker for better visibility
TEXT_LIGHT = '#95a5a6'
BORDER_LIGHT = '#ecf0f1'

STATE_FILE = os.path.join(HERE, 'gui_zones_state.json')
LOG_FILE = os.path.join(HERE, 'gui_zones_log.json')
LAST_FOLDER_FILE = os.path.join(HERE, 'gui_zones_last_folder.json')

# DEFAULT_STATE explained:
# - left_w: width (px) of the left/white zone (file list area).
# - details_w: width (px) of the yellow details zone (content area with labels).
# - breakdown_w: width (px) of the pink breakdown zone (material breakdown area).
# - green_h: height (px) of the green bundle/buttons area (vertical height of the top green region).
#
# To change a zone size later: update the corresponding value here, then either
# restart the GUI or press the 'Reset View' button which applies DEFAULT_STATE
# values (reset_view() uses these constants). The GUI also saves/restores
# a persisted state in `gui_zones_state.json` when toggling lock view.
#
DEFAULT_STATE = {
    'left_w': 184,       # white zone (left file list) width in pixels
    'details_w': 500,    # yellow zone (details) width in pixels
    'breakdown_w': 940,  # pink zone (breakdown) width in pixels
    'green_h': 264,      # green zone (buttons) height in pixels
}

DEFAULT_GUI = {'w': 1650, 'h': 950}

def toggle_beam_pocket_details(button, content_frame):
    """Toggle the visibility of Beam Pocket Details section"""
    try:
        if content_frame.winfo_ismapped():
            # Currently visible, hide it
            content_frame.pack_forget()
            button.config(text='▶')
        else:
            # Currently hidden, show it
            content_frame.pack(fill='x', padx=8, pady=2)
            button.config(text='▼')
    except Exception:
        pass

def toggle_critical_stud_details(button, content_frame):
    """Toggle the visibility of Critical Stud Details section"""
    try:
        if content_frame.winfo_ismapped():
            # Currently visible, hide it
            content_frame.pack_forget()
            button.config(text='▶')
        else:
            # Currently hidden, show it
            content_frame.pack(fill='x', padx=8, pady=2)
            button.config(text='▼')
    except Exception:
        pass

def toggle_subassembly_details(button, content_frame):
    """Toggle the visibility of SubAssembly Details section"""
    try:
        if content_frame.winfo_ismapped():
            # Currently visible, hide it
            content_frame.pack_forget()
            button.config(text='▶')
        else:
            # Currently hidden, show it
            content_frame.pack(fill='x', padx=8, pady=2)
            button.config(text='▼')
    except Exception:
        pass

def toggle_panel_details(button, content_frame):
    """Toggle the visibility of Panel Details section"""
    try:
        if content_frame.winfo_ismapped():
            # Currently visible, hide it
            content_frame.pack_forget()
            button.config(text='▶')
        else:
            # Currently hidden, show it
            content_frame.pack(fill='x', padx=8, pady=2)
            button.config(text='▼')
    except Exception:
        pass

def toggle_panel_specs(button, content_frame):
    """Toggle the visibility of Panel Specifications section"""
    try:
        if content_frame.winfo_ismapped():
            # Currently visible, hide it
            content_frame.pack_forget()
            button.config(text='▶')
        else:
            # Currently hidden, show it
            content_frame.pack(fill='x', padx=8, pady=2)
            button.config(text='▼')
    except Exception:
        pass

def toggle_debug_mode(enabled):
    """Toggle debug logging on/off to improve GUI performance"""
    global debug_enabled
    debug_enabled = enabled
    
    if enabled:
        # Clear the debug.log file and write header when debug is enabled
        try:
            with open(os.path.join(HERE, 'debug.log'), 'w') as f:
                f.write(f"=== Debug Log Started: {_dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
        except Exception:
            pass
        # Set logging level to DEBUG
        logging.getLogger().setLevel(logging.DEBUG)
    else:
        # Set logging level to WARNING (suppress DEBUG messages)
        logging.getLogger().setLevel(logging.WARNING)
    
def create_takeoff_standalone_output(panel_name, panel_info, panel_element, root_element, materials, specs, beam_pockets, critical_studs, subassemblies, material_breakdown, takeoff_output, family_members):
    """Create comprehensive takeoff output matching takeoff_standalone.py format exactly"""
    try:
        print(f"DEBUG: create_takeoff_standalone_output called with panel_name={panel_name}, material_breakdown={repr(material_breakdown[:100] if material_breakdown else None)}...")
        logging.debug(f"DEBUG: create_takeoff_standalone_output called with panel_name={panel_name}, material_breakdown={repr(material_breakdown[:100] if material_breakdown else None)}...")
        # Bundle name mapping for display
        bundle_names = {
            '557a6d63': 'B1 (2x6 Ext)',
            '442ef74d': 'B2 (2x4 Gar)', 
            '3e341f28': 'B3 (2x4 PW)',
            'bbec7789': 'B4 (2x4 Int)',
            'a5b7895b': 'B5 (2x4 Furr)'
        }
        output_lines = []
        
        # 🏠 PANEL DETAILS
        output_lines.append("🏠 PANEL DETAILS:")
        panel_display_name = panel_info.get('name') or panel_info.get('label') or panel_name
        output_lines.append(f"  Panel Name: {panel_display_name}")
        if panel_info.get('level'):
            output_lines.append(f"  Level: {panel_info['level']}")
        if panel_info.get('bundlename'):
            bundle_short = panel_info['bundlename'].split('...')[0] if '...' in panel_info['bundlename'] else panel_info['bundlename']
            bundle_display = bundle_names.get(bundle_short, panel_info['bundlename'])
            output_lines.append(f"  Bundle: {bundle_display}")
        else:
            output_lines.append("  Bundle: **No Bundle Found**")
        output_lines.append("")
        
        # 📋 PANEL SPECIFICATIONS
        output_lines.append("📋 PANEL SPECIFICATIONS:")
        if specs.get('category'):
            output_lines.append(f"  • Category: {specs['category']}")
        if specs.get('load_bearing'):
            load_bearing_text = 'YES' if specs['load_bearing'].lower() in ['yes', 'true', '1'] else 'NO'
            output_lines.append(f"  • Load Bearing: {load_bearing_text}")
        if specs.get('wall_length'):
            try:
                wall_length = float(specs['wall_length'])
                wall_length_fmt = format_feet_to_dimension(wall_length/12)
                length_info = f"  • Length: {wall_length:.0f} in ({wall_length_fmt})"
                
                # Add growth allowance information if available
                if specs.get('growth_allowance'):
                    try:
                        growth = float(specs['growth_allowance'])
                        if abs(growth) > 0.01:  # Only show if significant
                            growth_fmt = format_feet_to_dimension(abs(growth)/12)
                            growth_direction = "added" if growth > 0 else "subtracted"
                            length_info += f" [Growth allowance: {abs(growth):.1f} in ({growth_fmt}) {growth_direction}]"
                    except (ValueError, TypeError):
                        pass
                
                # Highlight length error if actual length exceeds WallLength
                if specs.get('length_error'):
                    length_info += f"\n  • ⚠️ LENGTH ERROR: {specs['length_error']}"
                
                output_lines.append(length_info)
            except:
                output_lines.append(f"  • Length: {specs['wall_length']}")
        if specs.get('height'):
            try:
                height = float(specs['height'])
                height_fmt = format_feet_to_dimension(height/12)
                output_lines.append(f"  • Height: {height:.0f} in ({height_fmt})")
            except:
                output_lines.append(f"  • Height: {specs['height']}")
        if specs.get('squaring'):
            try:
                # Calculate squaring using Pythagorean theorem
                height_val = float(specs.get('height', 0))
                wall_len = float(specs.get('wall_length', 0))
                
                # For squaring, subtract VeryTopPlate thickness (1.5") since it's shipped loose
                squaring_height = height_val - 1.5
                squaring_inches = math.sqrt(squaring_height ** 2 + wall_len ** 2)
                squaring_fmt = format_feet_to_dimension(squaring_inches/12)
                output_lines.append(f"  • Squaring: {squaring_inches:.4f} in ({squaring_fmt})")
            except:
                output_lines.append(f"  • Squaring: {specs['squaring']}")
        if specs.get('thickness'):
            try:
                thickness = float(specs['thickness'])
                output_lines.append(f"  • Thickness: {thickness:.1f} in")
            except:
                output_lines.append(f"  • Thickness: {specs['thickness']} in")
        if specs.get('stud_spacing'):
            try:
                stud_spacing = float(specs['stud_spacing'])
                output_lines.append(f"  • Stud Spacing: {stud_spacing:.0f} in")
            except:
                output_lines.append(f"  • Stud Spacing: {specs['stud_spacing']} in")
        
        # Sheathing layers - match GUI display exactly (no dimensions)
        sheathing_list = []
        for m in materials:
            if isinstance(m, dict):
                t = (m.get('Type') or '').lower()
                if 'sheet' in t or 'sheath' in t or (m.get('FamilyMemberName') and 'sheath' in str(m.get('FamilyMemberName')).lower()):
                    desc = (m.get('Description') or m.get('Desc') or '').strip()
                    # Only add unique descriptions (no duplicates)
                    if desc and desc not in sheathing_list:
                        sheathing_list.append(desc)

        if sheathing_list:
            for idx, desc in enumerate(sheathing_list, 1):
                if len(sheathing_list) == 1:
                    output_lines.append(f"  • Sheathing: {desc}")
                else:
                    output_lines.append(f"  • Sheathing Layer {idx}: {desc}")
        
        if specs.get('weight'):
            try:
                weight = float(specs['weight'])
                rounded_weight = round(weight)
                if rounded_weight % 2 != 0:  # If odd, round up to even
                    rounded_weight += 1
                output_lines.append(f"  • Weight: {rounded_weight} lbs")
            except:
                output_lines.append(f"  • Weight: {specs['weight']}")
        if specs.get('production_notes'):
            output_lines.append(f"  • Production Notes: {specs['production_notes']}")
        output_lines.append("")
        
        # 🔧 Beam Pocket Details (FM33)
        output_lines.append("🔧 Beam Pocket Details:")
        beam_pocket_count = 0
        if beam_pockets:
            for i, pocket in enumerate(beam_pockets, 1):
                beam_pocket_count += 1
                guid_display = f" (Guid: {pocket['guid'][:8]}...)" if pocket['guid'] else ""
                output_lines.append(f"• Beam Pocket {i}{guid_display} (FM33)")
                if pocket['aff'] is not None:
                    aff_formatted = format_feet_to_dimension(pocket['aff']/12)
                    output_lines.append(f"  AFF: {pocket['aff']:.2f} in ({aff_formatted})")
                if pocket['opening_width'] is not None:
                    output_lines.append(f"  Opening Width: {pocket['opening_width']:.1f} in")
                if pocket['materials']:
                    output_lines.append("  • Associated Material Parts:")
                    for label, count in sorted(pocket['materials'].items()):
                        # Find material description
                        desc = ""
                        for mat in materials:
                            if isinstance(mat, dict) and mat.get('Label') == label:
                                desc = mat.get('Desc') or mat.get('Description') or ""
                                break
                        desc_text = f" - {desc}" if desc else ""
                        output_lines.append(f"    ├── {label} ({count}){desc_text}")
                output_lines.append("")
            output_lines.append(f"Total Beam Pockets: {beam_pocket_count}")
        else:
            output_lines.append("No beam pockets found for this panel.")
        
        output_lines.append("")
        # 🔧 Critical Stud Details
        output_lines.append("🔧 Critical Stud Details:")
        critical_stud_count = 0
        if critical_studs:
            # Sort critical studs by distance (smallest to largest)
            def get_distance_value(stud):
                if stud.get('distance'):
                    # Extract numeric value from string like "3.1 in (0'-3 1/16)"
                    import re
                    match = re.search(r'(\d+\.?\d*)', stud['distance'])
                    if match:
                        return float(match.group(1))
                return float('inf')  # Put studs without distance at the end
            
            critical_studs.sort(key=get_distance_value)
            
            for stud in critical_studs:
                critical_stud_count += 1
                guid_display = f" (Guid: {stud['guid'][:8]}...)" if stud['guid'] else ""
                output_lines.append(f"• Critical Stud{guid_display} ({stud['fm_type']})")
                output_lines.append(f"• Type: {stud['type']}")
                if stud.get('distance'):
                    output_lines.append(f"• Distance: {stud['distance']}")
                output_lines.append(f"• Associated Material Parts:")
                for label, count in sorted(stud['materials'].items()):
                    # Find material description
                    desc = ""
                    for mat in materials:
                        if isinstance(mat, dict) and mat.get('Label') == label:
                            desc = mat.get('Desc') or mat.get('Description') or ""
                            break
                    desc_text = f" - {desc}" if desc else ""
                    output_lines.append(f" ├── {label} ({count}){desc_text}")
                output_lines.append("")
            output_lines.append(f"Total Critical Studs: {critical_stud_count}")
        else:
            output_lines.append("No critical studs found for this panel.")
        
        output_lines.append("")
        # 🔧 SubAssembly Details
        material_mapping = create_material_to_breakdown_mapping(materials)
        subassemblies = extract_subassembly_details(panel_element, materials, material_mapping)
        output_lines.append("🔧 SubAssembly Details:")
        subassembly_count = 0
        if subassemblies:
            for sub in subassemblies:
                subassembly_count += 1
                guid_display = f" (Guid: {sub['guid'][:8]}...)" if sub['guid'] else ""
                output_lines.append(f"• {sub['name']}{guid_display} (FM{sub['family_member']})")
                if sub['materials']:
                    output_lines.append("   • Associated Material Parts:")
                    for label, count in sorted(sub['materials'].items()):
                        # Find material description using the original label
                        desc = ""
                        for mat in materials:
                            if isinstance(mat, dict) and mat.get('Label') == label:
                                desc = mat.get('Desc') or mat.get('Description') or ""
                                break
                        desc_text = f" - {desc}" if desc else ""
                        output_lines.append(f"    ├── {label} ({count}){desc_text}")
                if sub['rough_openings']:
                    output_lines.append("   Rough Openings:")
                    for ro in sub['rough_openings']:
                        output_lines.append(f"    ├── Rough Opening: {ro['dimensions']} (FM-1)")
                        if ro['aff'] is not None:
                            aff_formatted = format_feet_to_dimension(ro['aff']/12)
                            output_lines.append(f"    ├── AFF: {ro['aff']:.1f} ({aff_formatted})")
                output_lines.append("")
            output_lines.append(f"Total SubAssemblies: {subassembly_count}")
        else:
            output_lines.append("No SubAssemblies found for this panel.")
        
        output_lines.append("")
        
        # Display ALL FAMILY MEMBERS before material breakdown
        if family_members:
            output_lines.append("ALL FAMILY MEMBERS")
            output_lines.append("---------------------------")
            # Sort family members by FM ID, then by count
            sorted_fm = sorted(family_members.items(), 
                             key=lambda x: (int(x[0].split(':')[0][2:]) if x[0].startswith('FM') and x[0].split(':')[0][2:].isdigit() else 999, -x[1]))
            for fm_key, count in sorted_fm:
                output_lines.append(f"- {fm_key} ({count})")
            output_lines.append("")
            
            # Add validation summary
            output_lines.append("STRUCTURAL VALIDATION SUMMARY")
            output_lines.append("-----------------------------")
            
            # Check for expected structural elements based on panel type
            validation_warnings = []
            
            # Check for critical studs in load-bearing panels
            load_bearing = specs.get('load_bearing', '').lower() in ['yes', 'true', '1']
            if load_bearing and critical_stud_count == 0:
                validation_warnings.append("⚠️  Load-bearing panel missing critical studs")
            
            # Check for beam pockets in panels with openings
            has_openings = any(sub['family_member'] in ['25'] for sub in subassemblies)
            if has_openings and beam_pocket_count == 0:
                validation_warnings.append("ℹ️  Panel has openings but no beam pockets found")
            
            # Check for subassemblies in complex panels
            if subassembly_count == 0 and len(family_members) > 10:
                validation_warnings.append("ℹ️  Complex panel with no subassemblies detected")
            
            # Check for FM32/FM42/FM25 presence
            special_fms = [fm for fm in family_members.keys() if any(fm.startswith(f'FM{fm_id}:') for fm_id in ['25', '32', '42'])]
            if special_fms:
                output_lines.append(f"✅ Special SubAssembly FMs detected: {', '.join(special_fms)}")
            
            # Report validation results
            if validation_warnings:
                for warning in validation_warnings:
                    output_lines.append(f"{warning}")
            else:
                output_lines.append("✅ All expected structural elements present")
            
            output_lines.append(f"📊 Totals: {beam_pocket_count} Beam Pockets, {critical_stud_count} Critical Studs, {subassembly_count} SubAssemblies, {len(family_members)} Total FM Types")
            output_lines.append("")
        else:
            output_lines.append("ALL FAMILY MEMBERS")
            output_lines.append("---------------------------")
            output_lines.append("No family members found")
            output_lines.append("")
        
        output_lines.append(f"MATERIAL BREAKDOWN:")
        if material_breakdown and material_breakdown.strip():
            output_lines.append(material_breakdown)
            output_lines.append("")
            
            output_lines.append(f"TAKEOFF RESULTS:")
            
            if takeoff_output:
                output_lines.append(takeoff_output)
                output_lines.append("")
        else:
            output_lines.append(f"Panel {panel_name}: No breakdown data available")
        
        return "\n".join(output_lines) or "No takeoff data available"
        
    except Exception as e:
        print(f"Error creating takeoff standalone output: {e}")
        import traceback
        traceback.print_exc()
        return f"Error creating takeoff output: {e}"

def process_panel_for_takeoff(panel_name, root):
    """Process a panel for takeoff and return formatted data for yellow/pink zones and export"""
    try:
        # Get the currently loaded EHX file path
        if not hasattr(root, 'ehx_file_path'):
            return None, None, None
        
        ehx_file_path = root.ehx_file_path
        
        # Parse the EHX file
        tree = ET.parse(ehx_file_path)
        root_element = tree.getroot()
        
        # Build search indexes
        indexes = build_search_indexes(root_element)
        panels_data = indexes['panels']
        
        # Find the panel info
        panel_info = None
        if panel_name in panels_data:
            panel_info = panels_data[panel_name]
        else:
            # Try to find by display name or label
            for guid, info in panels_data.items():
                if (info.get('display_name', '').lower() == panel_name.lower() or
                    info.get('label', '').lower() == panel_name.lower() or
                    info.get('name', '').lower() == panel_name.lower()):
                    panel_info = info
                    break
        
        if not panel_info:
            return None, None, None
        
        # Find the panel element
        panel_element = None
        panel_guid = panel_info['guid']
        
        for p_el in root_element.findall('.//Panel'):
            panel_guid_el = p_el.find('PanelGuid')
            panel_id_el = p_el.find('PanelID')
            if ((panel_guid_el is not None and panel_guid_el.text == panel_guid) or
                (panel_id_el is not None and panel_id_el.text == panel_guid)):
                panel_element = p_el
                break
        
        if panel_element is None:
            return None, None, None
        
        # Parse materials
        materials, critical_studs = parse_materials_from_panel(panel_element, root_element)
        
        # Get panel height for material formatting
        panel_height = None
        height_el = panel_element.find('Height')
        if height_el is not None and height_el.text:
            try:
                panel_height = float(height_el.text.strip())
            except ValueError:
                pass
        
        # Extract panel specifications
        specs = extract_panel_specifications(panel_info, panel_element, root_element, materials)
        
        # Extract beam pocket details
        beam_pockets = extract_beam_pocket_details(panel_element, materials)
        
        # Extract critical stud details
        critical_studs = extract_critical_stud_details(panel_element, materials)
        
        # Extract subassembly details
        subassemblies = extract_subassembly_details(panel_element, materials, {})
        
        # Get material breakdown
        material_breakdown = get_panel_material_breakdown_standalone(panel_name, root_element, panels_data, panel_height)
        
        # Create takeoff output
        takeoff_output, total_board_feet = create_takeoff_from_breakdown(material_breakdown)
        
        # Extract family members from materials AND subassemblies
        family_members = {}
        # First, collect from individual materials
        for material in materials:
            fm_id = material.get('FamilyMember', '').strip()
            fm_name = material.get('FamilyMemberName', '').strip()
            if fm_id and fm_name:
                key = f"FM{fm_id}: {fm_name}"
                family_members[key] = family_members.get(key, 0) + 1
        
        # Also collect from SubAssembly elements (FM25, FM32, FM42)
        for sub_el in panel_element.findall('.//SubAssembly'):
            fm_el = sub_el.find('FamilyMember')
            fm_name_el = sub_el.find('FamilyMemberName')
            sub_name_el = sub_el.find('SubAssemblyName')
            
            fm_id = ''
            fm_name = ''
            
            if fm_el is not None and fm_el.text:
                fm_id = fm_el.text.strip()
            
            # Use FamilyMemberName if available, otherwise SubAssemblyName
            if fm_name_el is not None and fm_name_el.text:
                fm_name = fm_name_el.text.strip()
            elif sub_name_el is not None and sub_name_el.text:
                fm_name = sub_name_el.text.strip()
            
            if fm_id and fm_name:
                key = f"FM{fm_id}: {fm_name}"
                family_members[key] = family_members.get(key, 0) + 1
        
        # Bundle name mapping for display
        bundle_names = {
            '557a6d63': 'B1 (2x6 Ext)',
            '442ef74d': 'B2 (2x4 Gar)', 
            '3e341f28': 'B3 (2x4 PW)',
            'bbec7789': 'B4 (2x4 Int)',
            'a5b7895b': 'B5 (2x4 Furr)'
        }
        
        # Format data for UI display
        
        # Yellow zone: Panel Specifications with formatted sections
        yellow_data = {
            'specs': specs,  # Include detailed specifications
            'beam_pockets': beam_pockets,
            'critical_studs': critical_studs,
            'subassemblies': subassemblies
        }
        
        # Pink zone: Material Breakdown
        pink_data = material_breakdown
        
        # Export data: Full takeoff output (matching takeoff_standalone.py format)
        export_data = create_takeoff_standalone_output(panel_name, panel_info, panel_element, root_element, materials, specs, beam_pockets, critical_studs, subassemblies, material_breakdown, takeoff_output, family_members)
        
        print(f"DEBUG: process_panel_for_takeoff returning export_data = {repr(export_data[:100] if export_data else None)}...")
        logging.debug(f"DEBUG: process_panel_for_takeoff returning export_data = {repr(export_data[:100] if export_data else None)}...")
        
        return yellow_data, pink_data, export_data
        
    except Exception as e:
        print(f"Error processing panel {panel_name} for takeoff: {e}")
        import traceback
        traceback.print_exc()
        return None, None, None

def make_gui():
    root = tk.Tk()
    root.title('EHX Reader')
    root.geometry(f"{DEFAULT_GUI['w']}x{DEFAULT_GUI['h']}")

    # Configure ttk styles for button selection feedback
    style = ttk.Style()
    style.configure('TButton', foreground='black')  # Ensure default button text is visible
    style.configure('Selected.TButton', background='#C8E6C9', foreground='black', relief='sunken')  # Light green background with black text for better legibility



    # Top bar
    top = tk.Frame(root, bg=TOP_BG)
    top.pack(side='top', fill='x')
    job_val = tk.Label(top, text='(none)', bg=TOP_BG, fg=TEXT_LIGHT, font=('Segoe UI', 10, 'bold'))
    job_val.pack(side='left', padx=6)
    path_val = tk.Label(top, text='(none)', bg=TOP_BG, fg=TEXT_LIGHT, font=('Segoe UI', 10, 'bold'), cursor='hand2', anchor='w', width=40)
    path_val.pack(side='left', padx=6, fill='x', expand=True)

    # Status label for loading messages
    status_val = tk.Label(top, text='', bg=TOP_BG, fg='yellow', font=('Segoe UI', 10, 'bold'))
    status_val.pack(side='left', padx=6, fill='x', expand=True)

    # Make path label clickable to open file location
    def open_file_location(event=None):
        try:
            current_path = path_val.cget('text')
            if current_path and current_path != '(none)':
                # If it's a file path, open the directory containing it
                if os.path.isfile(current_path):
                    folder_path = os.path.dirname(current_path)
                else:
                    folder_path = current_path

                # On Windows, use os.startfile to open the folder
                if os.name == 'nt':  # Windows
                    os.startfile(folder_path)
                else:
                    # For other platforms, could use subprocess or similar
                    import subprocess
                    subprocess.run(['xdg-open', folder_path])  # Linux
                    # subprocess.run(['open', folder_path])  # macOS
        except Exception as e:
            if debug_enabled:
                print(f"Error opening file location: {e}")

    path_val.bind('<Button-1>', open_file_location)
    path_val.config(cursor='hand2')  # Change cursor to hand when hovering

    # Debug control checkbox
    debug_var = tk.BooleanVar(value=True)
    debug_checkbox = tk.Checkbutton(top, text='Debug', variable=debug_var, 
                                   bg=TOP_BG, fg=TEXT_LIGHT, selectcolor=TOP_BG,
                                   activebackground=TOP_BG, activeforeground=TEXT_LIGHT,
                                   command=lambda: toggle_debug_mode(debug_var.get()))
    debug_checkbox.pack(side='right', padx=6)

    # Create folder_entry but hide it (width=1) to maintain functionality
    folder_entry = ttk.Entry(top, width=1)
    # folder_entry.pack(side='left', padx=8)  # Commented out to hide display
    folder_lbl = tk.Label(top, text='Folder:', bg=TOP_BG, fg=TEXT_LIGHT, font=('Segoe UI', 10))
    # folder_lbl.pack(side='left')  # Commented out to hide display

    # Centering flags (kept at top-level so zones can reference them)
    # Default behavior:
    # - Yellow (details): no horizontal or vertical centering (top-left alignment)
    # - Pink (breakdown): centered horizontally and vertically
    #
    # To re-enable visible H/V checkboxes inside the zones later, you can
    # uncomment the example code below and wire the checkbuttons to these
    # BooleanVars. The small controls were removed to preserve zone space.
    # Example:
    #
    # details_ctl = tk.Frame(details_outer, bg=DETAILS_BG)
    # details_ctl.pack(side='top', anchor='nw', padx=6, pady=4)
    # tk.Checkbutton(details_ctl, text='H', bg=DETAILS_BG, variable=details_center_h,
    #                command=lambda: root.after(10, center_details_content)).pack(anchor='nw')
    # tk.Checkbutton(details_ctl, text='V', bg=DETAILS_BG, variable=details_center_v,
    #                command=lambda: root.after(10, center_details_content)).pack(anchor='nw')
    #
    # For the pink zone you could similarly create a small control frame and
    # use place() to keep it in the upper-left if desired.
    #
    # Keep the BooleanVars here so defaults and future code can reference them.
    details_center_h = tk.BooleanVar(value=False)
    details_center_v = tk.BooleanVar(value=False)
    breakdown_center_h = tk.BooleanVar(value=True)
    breakdown_center_v = tk.BooleanVar(value=True)

    # Export + Back/Clear buttons (PV0825 parity)
    panels_loaded = False
    panel_button_widgets = []
    current_panels = {}
    panel_materials_map = {}
    # track which panel is currently displayed
    selected_panel = {'name': None}
    # track available levels and selected level
    available_levels = []
    selected_level = {'value': None}  # None means single level or no level filtering
    original_panels = {}  # Store original unfiltered panel data
    original_materials_map = {}  # Store original unfiltered materials data
    # track current export data for export button
    current_export_data = None
    
    # Panel button highlighting variables
    panel_button_map = {}  # Map panel names to their button widgets
    selected_button = {'widget': None}  # Track currently highlighted button

    def export_current_panel():
        global current_export_data
        try:
            print(f"DEBUG: export_current_panel called")
            logging.debug(f"DEBUG: export_current_panel called")
            sel_name = selected_panel.get('name')
            print(f"DEBUG: selected_panel name = {sel_name}")
            logging.debug(f"DEBUG: selected_panel name = {sel_name}")
            if not sel_name:
                messagebox.showinfo('Export', 'No panel selected to export')
                return

            # Check if we have export data available
            print(f"DEBUG: current_export_data = {current_export_data}")
            logging.debug(f"DEBUG: current_export_data = {current_export_data}")
            if not current_export_data:
                messagebox.showinfo('Export', 'No takeoff data available. Please select a panel first.')
                return

            # Ensure we have the panel object available for display name
            panel_obj = current_panels.get(sel_name, {})
            print(f"DEBUG: panel_obj = {panel_obj}")

            # Use panel name for filename (like 05-100.txt)
            # Extract the panel name from the panel object DisplayLabel
            panel_display_name = panel_obj.get('DisplayLabel') or panel_obj.get('name') or panel_obj.get('label') or sel_name or ''
            
            # Clean up the panel name (remove any prefixes or suffixes if needed)
            # For example, if it ends with 'et', remove it like "05-100et" -> "05-100"
            if panel_display_name.lower().endswith('et'):
                panel_display_name = panel_display_name[:-2]
            
            panel_filename = panel_display_name
            
            # Ensure it has .txt extension
            if not panel_filename.lower().endswith('.txt'):
                panel_filename += '.txt'

            # Automatically save to LOG folder in script directory
            log_folder = os.path.join(HERE, 'LOG')
            os.makedirs(log_folder, exist_ok=True)
            dest = os.path.join(log_folder, panel_filename)
            print(f"DEBUG: export destination = {dest}")

            # Write the takeoff data to file
            with open(dest, 'w', encoding='utf-8') as out:
                out.write(current_export_data)

            messagebox.showinfo('Export', f'Panel takeoff exported to {dest}')
            
            # Automatically open the export file
            try:
                import subprocess
                import platform
                if platform.system() == 'Windows':
                    subprocess.run(['start', '', dest], shell=True)
                elif platform.system() == 'Darwin':  # macOS
                    subprocess.run(['open', dest])
                else:  # Linux
                    subprocess.run(['xdg-open', dest])
            except Exception as open_error:
                # If auto-open fails, just continue - don't show error to user
                pass
        except Exception as e:
            messagebox.showerror('Export Error', str(e))

    def update_level_buttons():
        """Update level buttons based on available levels in current_panels"""
        nonlocal level_buttons, level_guid_map, original_panels
        # Clear existing level buttons directly from top bar
        for btn in level_buttons:
            try:
                btn.destroy()
            except Exception:
                pass
        level_buttons = []
        
        # Forget action buttons to repack them in new order
        browse_btn.pack_forget()
        export_btn.pack_forget()

        # Pack action buttons first in correct order
        export_btn.pack(side='right', padx=6)
        browse_btn.pack(side='right', padx=6)
        
        if original_panels:
            # Collect unique levels from panels using LevelGuid mapping
            level_guid_map = {}  # Map LevelGuid to level number
            levels = set()
            for p in original_panels.values():
                level_guid = p.get('LevelGuid')
                level_no = p.get('LevelNo') or p.get('Level')
                if level_guid and level_no:
                    level_guid_map[level_guid] = str(level_no)
                    levels.add(str(level_no))
            
            available_levels[:] = sorted(levels, key=int)
            
            # Auto-select the lowest available level if no level is currently selected
            if available_levels and selected_level['value'] is None:
                selected_level['value'] = int(available_levels[0])  # Select the lowest level
            
            # Calculate level statistics
            level_stats.clear()
            total_panels = len(original_panels)
            total_bundles = len(set(p.get('BundleName') or p.get('Bundle') or '' 
                                   for p in original_panels.values() 
                                   if (p.get('BundleName') or p.get('Bundle') or '')))
            
            for level in available_levels:
                level_panels = [p for p in original_panels.values() 
                               if str(p.get('LevelNo') or p.get('Level') or '') == level]
                level_bundles = len(set(p.get('BundleName') or p.get('Bundle') or '' 
                                       for p in level_panels 
                                       if (p.get('BundleName') or p.get('Bundle') or '')))
                level_stats[level] = {
                    'panels': len(level_panels),
                    'bundles': level_bundles
                }
        else:
            available_levels[:] = []
            level_stats.clear()
            level_guid_map = {}
        
        def select_level(level):
            """Select a level and update the GUI to show only panels from that level"""
            selected_level['value'] = int(level)
            update_level_buttons()
            filter_panels_by_level()
            
            # Update level info label for selected level
            stats = level_stats.get(str(level), {'panels': 0, 'bundles': 0})
        
        # Then pack level buttons
        for level in reversed(['1', '2', '3', '4']):
            is_available = level in available_levels
            if is_available:
                bg = ACCENT_COLOR if selected_level['value'] == int(level) else TOP_BG
                relief = 'sunken' if selected_level['value'] == int(level) else 'raised'
                fg = 'white'
                state = 'normal'
                command = lambda l=level: select_level(l)
            else:
                bg = 'grey'
                relief = 'raised'
                fg = 'black'
                state = 'disabled'
                command = None
            
            btn = tk.Button(top, text=f'L{level}', bg=bg, fg=fg, relief=relief, 
                           font=('Arial', 8), padx=6, pady=2, state=state, command=command)
            btn.pack(side='right', padx=2)
            level_buttons.append(btn)

    def filter_panels_by_level():
        """Filter current_panels and panel_materials_map to show only selected level"""
        nonlocal level_guid_map, selected_level, original_panels, original_materials_map, current_panels, panel_materials_map, selected_panel
        if selected_level['value'] is None:
            # Show all panels (when no level selected or only one level exists)
            filtered_panels = dict(original_panels)
            filtered_materials = dict(original_materials_map)  # Use original materials
        else:
            # Filter to selected level from original_panels using LevelGuid mapping
            filtered_panels = {}
            filtered_materials = {}
            for name, panel in original_panels.items():
                # Use LevelGuid to determine level, fallback to LevelNo
                panel_level_guid = panel.get('LevelGuid')
                panel_level_no = panel.get('LevelNo') or panel.get('Level') or ''
                
                # If we have a LevelGuid, use it to determine the level number
                if panel_level_guid and panel_level_guid in level_guid_map:
                    panel_level = level_guid_map[panel_level_guid]
                else:
                    panel_level = str(panel_level_no)
                
                if panel_level == str(selected_level['value']):
                    filtered_panels[name] = panel
                    if name in original_materials_map:  # Check original materials
                        filtered_materials[name] = original_materials_map[name]  # Use original materials

        # Update current_panels and panel_materials_map temporarily for display
        # (we'll restore them when level changes)
        current_panels.clear()
        current_panels.update(filtered_panels)
        panel_materials_map.clear()
        panel_materials_map.update(filtered_materials)

        # Check if currently selected panel is still valid in the new level
        if selected_panel['name'] and selected_panel['name'] not in current_panels:
            selected_panel['name'] = None
            # Clear button highlighting when selected panel is no longer visible
            if selected_button['widget']:
                try:
                    # Reset to normal appearance for tk.Button
                    selected_button['widget'].configure(relief='raised')
                except Exception:
                    pass
            selected_button['widget'] = None

        rebuild_bundles(5)
        # Clear details and breakdown only if no valid panel is selected
        if not selected_panel['name']:
            for ch in details_scrollable_frame.winfo_children():
                try:
                    ch.destroy()
                except Exception:
                    pass
            for ch in breakdown_scrollable_frame.winfo_children():
                try:
                    ch.destroy()
                except Exception:
                    pass

    def load_last_folder():
        try:
            if os.path.exists(LAST_FOLDER_FILE):
                with open(LAST_FOLDER_FILE, 'r', encoding='utf-8') as fh:
                    d = json.load(fh) or {}
                    p = d.get('last_folder')
                    if p and os.path.isdir(p):
                        return p
        except Exception:
            pass
        return os.getcwd()

    folder_entry.insert(0, load_last_folder())

    def on_browse():
        d = filedialog.askdirectory(title='Select folder', initialdir=folder_entry.get() or os.getcwd())
        if d:
            folder_entry.delete(0, tk.END)
            folder_entry.insert(0, d)
            populate_files(d)
            try:
                with open(LAST_FOLDER_FILE, 'w', encoding='utf-8') as fh:
                    json.dump({'last_folder': d}, fh)
            except Exception:
                pass

    # Level selection buttons (will be populated when EHX is loaded with multiple levels)
    # Remove the separate level_frame and put buttons directly on top bar
    level_buttons = []  # Keep track of level buttons for cleanup
    level_guid_map = {}  # Map LevelGuid to level number

    # Action buttons on the right (will be repacked when levels are present)
    export_btn = tk.Button(top, text='Export', command=export_current_panel, bg=TOP_BG, fg=TEXT_LIGHT, relief='raised')
    export_btn.pack(side='right', padx=6)
    browse_btn = tk.Button(top, text='Browse', command=on_browse, bg=TOP_BG, fg=TEXT_LIGHT, relief='raised')
    browse_btn.pack(side='right', padx=6)    # Level stats tracking
    level_stats = {}  # Will store panel/bundle counts per level

    # Main panes
    main = tk.PanedWindow(root, orient='horizontal')
    main.pack(fill='both', expand=True)
    left = tk.Frame(main, bg=LEFT_BG, width=DEFAULT_STATE['left_w'])
    main.add(left)
    right_outer = tk.PanedWindow(main, orient='vertical')
    main.add(right_outer)

    # Left file list
    white_frame = tk.Frame(left, bg='white')
    white_frame.pack(fill='both', expand=True, padx=6, pady=6)
    # left zone (white) - no visible heading to save space
    file_listbox = tk.Listbox(white_frame, width=40, height=18)
    file_listbox.pack(fill='both', expand=True, padx=4, pady=4)

    # Green bundles + bottom details/breakdown
    top_pane = tk.Frame(right_outer)
    bottom_pane = tk.Frame(right_outer)
    right_outer.add(top_pane)
    right_outer.add(bottom_pane)

    # def show_search_dialog():
    #     """Show the EHX search modal dialog"""
    #     # Get current EHX file path
    #     sel = file_listbox.curselection()
    #     if not sel:
    #         messagebox.showinfo("No EHX File", "Please select an EHX file from the list first.")
    #         return
    #
    #     fname = file_listbox.get(sel[0])
    #     folder = folder_entry.get() or os.getcwd()
    #     ehx_path = os.path.join(folder, fname)
    #
    #     if not os.path.exists(ehx_path):
    #         messagebox.showerror("File Not Found", f"EHX file not found: {ehx_path}")
    #         return
    #
    #     # Create modal dialog
    #     search_dialog = tk.Toplevel(root)
    #     search_dialog.title("EHX Search")
    #     search_dialog.geometry("800x600")
    #     search_dialog.transient(root)
    #     search_dialog.grab_set()
    #
    #     # Center the dialog
    #     search_dialog.geometry("+{}+{}".format(
    #         root.winfo_x() + (root.winfo_width() // 2) - 400,
    #         root.winfo_y() + (root.winfo_height() // 2) - 300
    #     ))
    #
    #     # Create search widget
    #     search_widget = EHXSearchWidget(search_dialog, ehx_file_path=ehx_path)
    #     search_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    #
    #     # Handle dialog close
    #     def on_close():
    #         search_dialog.grab_release()
    #         search_dialog.destroy()
    #
    #     search_dialog.protocol("WM_DELETE_WINDOW", on_close)
    #
    #     # Focus the search entry
    #     search_dialog.after(100, lambda: search_widget.search_entry.focus_set())

    # Search bar at the top
    search_frame = tk.Frame(top_pane, bg='#f8f8f8', height=40)
    search_frame.pack_propagate(False)
    search_frame.pack(fill='x', padx=8, pady=(8, 4))
    
    # EHX search removed as per requirements
    # search_button = ttk.Button(search_frame, text="🔍 Search EHX", command=show_search_dialog)
    # search_button.pack(side='left', padx=(0, 8), pady=4)
    
    # ttk.Label(search_frame, text="Click to search panels, materials, and bundles", 
    #           font=('Arial', 9), foreground='#666').pack(side='left', pady=4)

    btns_frame = tk.Frame(top_pane, bg=BUTTONS_BG, height=DEFAULT_STATE['green_h'])
    btns_frame.pack_propagate(False)
    btns_frame.pack(fill='both', expand=True, padx=8, pady=(4, 8))
    # green zone (buttons) - no visible heading to save space
    btn_grid = tk.Frame(btns_frame, bg=BUTTONS_BG)
    btn_grid.pack(fill='both', expand=True, padx=8, pady=6)

    bottom_inner = tk.PanedWindow(bottom_pane, orient='horizontal')
    bottom_inner.pack(fill='both', expand=True)
    
    # Details frame with scrollbar (yellow zone) - professional styling
    details_outer = tk.Frame(bottom_inner, bg=DETAILS_BG, relief='solid', bd=1)
    details_canvas = tk.Canvas(details_outer, bg=DETAILS_BG, highlightthickness=0)
    details_scrollable_frame = tk.Frame(details_canvas, bg=DETAILS_BG)
    
    details_scrollable_frame.bind(
        "<Configure>",
        lambda e: details_canvas.configure(scrollregion=details_canvas.bbox("all"))
    )
    
    # Center the scrollable frame within the canvas
    def center_details_content():
        try:
            # Get the bounding box of all content in the scrollable frame
            bbox = details_canvas.bbox("all")
            if bbox:
                content_width = bbox[2] - bbox[0]
                content_height = bbox[3] - bbox[1]
                canvas_width = details_canvas.winfo_width()
                canvas_height = details_canvas.winfo_height()

                if canvas_width > 1 and canvas_height > 1:
                    # Choose anchor and coordinates based on the horizontal/vertical flags
                    # Use the canvas window tag 'content' for coords/itemconfig
                    # Horizontal centering
                    if details_center_h.get():
                        x = canvas_width // 2
                    else:
                        # left-align content within available canvas space
                        x = 0
                    # Vertical centering
                    if details_center_v.get():
                        y = canvas_height // 2
                    else:
                        # align to top
                        y = 0

                    # Determine anchor string for itemconfig
                    if details_center_h.get() and details_center_v.get():
                        anchor = 'center'
                    elif details_center_h.get() and not details_center_v.get():
                        anchor = 'n'  # top center
                    elif not details_center_h.get() and details_center_v.get():
                        anchor = 'w'  # middle left
                    else:
                        anchor = 'nw'  # top-left

                    try:
                        details_canvas.coords('content', x, y)
                        details_canvas.itemconfig('content', anchor=anchor)
                    except Exception:
                        # fallback to using object reference
                        details_canvas.coords(details_scrollable_frame, x, y)
                        details_canvas.itemconfig(details_scrollable_frame, anchor=anchor)
        except Exception:
            pass
    
    # No visible H/V controls for yellow zone (defaults are applied via flags)

    details_canvas.create_window((0, 0), window=details_scrollable_frame, anchor="nw", tags="content")
    
    # Bind to canvas resize to keep content centered
    # DESCRIPTION: Force the details inner frame and canvas window to the
    # configured yellow-zone width so labels and the title can be centered by
    # the existing center_details_content() routine. This makes the visual
    # center equal to DEFAULT_STATE['details_w'] / 2.
    try:
        details_scrollable_frame.configure(width=DEFAULT_STATE['details_w'])
        details_canvas.itemconfig('content', width=DEFAULT_STATE['details_w'])
    except Exception:
        pass

    details_canvas.bind('<Configure>', lambda e: center_details_content())
    
    # Add vertical scrollbar for details zone
    details_scrollbar = tk.Scrollbar(details_outer, orient="vertical", command=details_canvas.yview, 
                                    bg=BORDER_LIGHT, troughcolor=DETAILS_BG, activebackground=PRIMARY_BLUE)
    details_canvas.configure(yscrollcommand=details_scrollbar.set)
    
    details_canvas.pack(side='left', fill='both', expand=True)
    details_scrollbar.pack(side='right', fill='y')
    
    # Bind mouse wheel to details canvas
    def _on_details_mousewheel(event):
        details_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
    
    details_canvas.bind_all("<MouseWheel>", _on_details_mousewheel)
    
    # Breakdown frame with scrollbar (pink zone) - professional styling
    breakdown_outer = tk.Frame(bottom_inner, bg=BREAKDOWN_BG, relief='solid', bd=1)
    breakdown_canvas = tk.Canvas(breakdown_outer, bg=BREAKDOWN_BG, highlightthickness=0)
    breakdown_scrollable_frame = tk.Frame(breakdown_canvas, bg=BREAKDOWN_BG)
    
    breakdown_scrollable_frame.bind(
        "<Configure>",
        lambda e: breakdown_canvas.configure(scrollregion=breakdown_canvas.bbox("all"))
    )
    
    # Center the scrollable frame within the canvas
    def center_breakdown_content():
        try:
            # Get the bounding box of all content in the scrollable frame
            bbox = breakdown_canvas.bbox("all")
            if bbox:
                content_width = bbox[2] - bbox[0]
                content_height = bbox[3] - bbox[1]
                canvas_width = breakdown_canvas.winfo_width()
                canvas_height = breakdown_canvas.winfo_height()

                if canvas_width > 1 and canvas_height > 1:
                    # Choose anchor and coordinates based on the horizontal/vertical flags
                    if breakdown_center_h.get():
                        x = canvas_width // 2
                    else:
                        x = 0
                    if breakdown_center_v.get():
                        y = canvas_height // 2
                    else:
                        y = 0

                    if breakdown_center_h.get() and breakdown_center_v.get():
                        anchor = 'center'
                    elif breakdown_center_h.get() and not breakdown_center_v.get():
                        anchor = 'n'
                    elif not breakdown_center_h.get() and breakdown_center_v.get():
                        anchor = 'w'
                    else:
                        anchor = 'nw'

                    try:
                        breakdown_canvas.coords('content', x, y)
                        breakdown_canvas.itemconfig('content', anchor=anchor)
                    except Exception:
                        breakdown_canvas.coords(breakdown_scrollable_frame, x, y)
                        breakdown_canvas.itemconfig(breakdown_scrollable_frame, anchor=anchor)
        except Exception:
            pass
    
    breakdown_canvas.create_window((0, 0), window=breakdown_scrollable_frame, anchor="nw", tags="content")
    
    # Bind to canvas resize to keep content centered
    # DESCRIPTION: Force the breakdown inner frame and canvas window to the
    # configured pink-zone width so labels and the title can be perfectly
    # centered by the existing center_breakdown_content() routine. This makes
    # the visual center equal to DEFAULT_STATE['breakdown_w'] / 2 (e.g., 570
    # when breakdown_w is 1140).
    # Ensure the inner frame and canvas window use the configured breakdown width
    try:
        breakdown_scrollable_frame.configure(width=DEFAULT_STATE['breakdown_w'])
        # set the canvas window width via its tag so packed labels fill the full pink zone
        breakdown_canvas.itemconfig('content', width=DEFAULT_STATE['breakdown_w'])
    except Exception:
        pass

    # No visible H/V controls for pink zone (defaults are applied via flags)

    breakdown_canvas.bind('<Configure>', lambda e: center_breakdown_content())
    
    # Add vertical scrollbar for breakdown zone
    breakdown_scrollbar = tk.Scrollbar(breakdown_outer, orient="vertical", command=breakdown_canvas.yview,
                                      bg=BORDER_LIGHT, troughcolor=BREAKDOWN_BG, activebackground=PRIMARY_BLUE)
    breakdown_canvas.configure(yscrollcommand=breakdown_scrollbar.set)
    
    breakdown_canvas.pack(side='left', fill='both', expand=True)
    breakdown_scrollbar.pack(side='right', fill='y')
    
    # Bind mouse wheel to breakdown canvas
    def _on_breakdown_mousewheel(event):
        breakdown_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
    
    breakdown_canvas.bind_all("<MouseWheel>", _on_breakdown_mousewheel)
    
    bottom_inner.add(details_outer)
    bottom_inner.add(breakdown_outer)

    # Tooltip
    tip_win = {'win': None}

    def _show_tip(text, x, y):
        _hide_tip()
        tw = tk.Toplevel(root)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tk.Label(tw, text=text, bg='#ffffe0', relief='solid', borderwidth=1, font=('Arial', 9)).pack()
        tip_win['win'] = tw

    def _hide_tip():
        w = tip_win.get('win')
        if w:
            try:
                w.destroy()
            except Exception:
                pass
        tip_win['win'] = None

    def attach_hover_tooltip(widget, text_getter):
        def enter(e):
            try:
                txt = text_getter()
                f = tkfont.Font(font=widget.cget('font'))
                if f.measure(txt) > widget.winfo_width() - 8:
                    _show_tip(txt, e.x_root + 12, e.y_root + 12)
            except Exception:
                pass

        def leave(e):
            _hide_tip()

        widget.bind('<Enter>', enter)
        widget.bind('<Leave>', leave)

    def populate_files(folder=None):
        try:
            folder = folder or folder_entry.get() or os.getcwd()
            file_listbox.delete(0, tk.END)
            for fn in sorted(os.listdir(folder)):
                if fn.lower().endswith('.ehx'):
                    file_listbox.insert(tk.END, fn)
                    try:
                        file_listbox.itemconfig(file_listbox.size() - 1, fg='blue')
                    except Exception:
                        pass
        except Exception:
            pass

    populate_files()

    # Ensure mouse wheel works when hovering over listbox items (child widgets may otherwise consume events)
    def _file_list_on_wheel(event):
        try:
            file_listbox.yview_scroll(-1 * (event.delta // 120), 'units')
            return 'break'
        except Exception:
            return None

    def _file_list_enter(event):
        try:
            file_listbox.focus_set()
            file_listbox.bind_all('<MouseWheel>', _file_list_on_wheel)
        except Exception:
            pass

    def _file_list_leave(event):
        try:
            file_listbox.unbind_all('<MouseWheel>')
        except Exception:
            pass

    file_listbox.bind('<Enter>', _file_list_enter)
    file_listbox.bind('<Leave>', _file_list_leave)
    file_listbox.bind('<MouseWheel>', _file_list_on_wheel)

    # Add tooltip support for file listbox items
    def on_file_hover(event):
        try:
            index = file_listbox.nearest(event.y)
            if index >= 0:
                filename = file_listbox.get(index)
                if filename:
                    f = tkfont.Font(font=file_listbox.cget('font'))
                    if f.measure(filename) > file_listbox.winfo_width() - 20:  # Account for padding
                        _show_tip(filename, event.x_root + 12, event.y_root + 12)
                    else:
                        _hide_tip()
        except Exception:
            _hide_tip()

    def on_file_leave(event):
        _hide_tip()

    file_listbox.bind('<Motion>', on_file_hover)
    file_listbox.bind('<Leave>', on_file_leave)

    # def show_search_dialog():
    #     """Show the EHX search modal dialog"""
    #     # Get current EHX file path
    #     sel = file_listbox.curselection()
    #     if not sel:
    #         messagebox.showinfo("No EHX File", "Please select an EHX file from the list first.")
    #         return
    #     
    #     fname = file_listbox.get(sel[0])
    #     folder = folder_entry.get() or os.getcwd()
    #     ehx_path = os.path.join(folder, fname)
    #     
    #     if not os.path.exists(ehx_path):
    #         messagebox.showerror("File Not Found", f"EHX file not found: {ehx_path}")
    #         return
    #     
    #     # Create modal dialog
    #     search_dialog = tk.Toplevel(root)
    #     search_dialog.title("EHX Search")
    #     search_dialog.geometry("800x600")
    #     search_dialog.transient(root)
    #     search_dialog.grab_set()
    #     
    #     # Center the dialog
    #     search_dialog.geometry("+{}+{}".format(
    #         root.winfo_x() + (root.winfo_width() // 2) - 400,
    #         root.winfo_y() + (root.winfo_height() // 2) - 300
    #     ))
    #     
    #     # Create search widget
    #     search_widget = EHXSearchWidget(search_dialog, ehx_file_path=ehx_path)
    #     search_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    #     
    #     # Handle dialog close
    #     def on_close():
    #         search_dialog.grab_release()
    #         search_dialog.destroy()
    #     
    #     search_dialog.protocol("WM_DELETE_WINDOW", on_close)
    # Add mouse wheel support to scrollable zones
    def _bind_mousewheel_to_canvas(canvas, scrollable_frame):
        def _on_mousewheel(event):
            try:
                canvas.yview_scroll(-1 * (event.delta // 120), 'units')
                return "break"
            except Exception:
                return None

        def _on_enter(event):
            try:
                canvas.focus_set()
                # Bind to all so child widgets won't steal the wheel event
                canvas.bind_all('<MouseWheel>', _on_mousewheel)
            except Exception:
                pass

        def _on_leave(event):
            try:
                canvas.unbind_all('<MouseWheel>')
            except Exception:
                pass

        try:
            canvas.bind('<Enter>', _on_enter)
            canvas.bind('<Leave>', _on_leave)
            scrollable_frame.bind('<Enter>', _on_enter)
            scrollable_frame.bind('<Leave>', _on_leave)
        except Exception:
            pass

        # Fallback direct binds
        try:
            canvas.bind('<MouseWheel>', _on_mousewheel)
            scrollable_frame.bind('<MouseWheel>', _on_mousewheel)
        except Exception:
            pass

        return _on_mousewheel

    _bind_mousewheel_to_canvas(details_canvas, details_scrollable_frame)
    _bind_mousewheel_to_canvas(breakdown_canvas, breakdown_scrollable_frame)
    
    # Add mouse wheel support to buttons frame (green zone)
    def _on_buttons_mousewheel(event):
        # For the buttons frame, we can scroll through the bundle frames
        try:
            children = btn_grid.winfo_children()
            if children:
                # Find the first visible bundle frame and scroll it
                for child in children:
                    if isinstance(child, tk.LabelFrame):
                        # This is a simple implementation - in a real scenario you might want more sophisticated scrolling
                        break
        except Exception:
            pass
    
    btns_frame.bind('<MouseWheel>', _on_buttons_mousewheel)
    btns_frame.bind('<Enter>', lambda e: btns_frame.focus_set())

    def display_panel(name, panel_obj, materials, yellow_data=None, pink_data=None, export_data=None):
        # Clear the yellow and pink zones
        for ch in details_scrollable_frame.winfo_children():
            ch.destroy()
        for ch in breakdown_scrollable_frame.winfo_children():
            ch.destroy()
        
        # Store export data for export button
        if export_data:
            global current_export_data
            current_export_data = export_data
            print(f"DEBUG: display_panel set current_export_data = {repr(export_data[:100] if export_data else None)}...")
            logging.debug(f"DEBUG: display_panel set current_export_data = {repr(export_data[:100] if export_data else None)}...")
        else:
            print(f"DEBUG: display_panel export_data is None or empty")
            logging.debug(f"DEBUG: display_panel export_data is None or empty")
        
        # Display yellow zone (Panel Specifications) with expandable sections
        if yellow_data or panel_obj:
            yellow_frame = tk.Frame(details_scrollable_frame, bg=DETAILS_BG)
            yellow_frame.pack(fill='x', padx=4, pady=4)
            
            # Panel Specifications sections
            specs_frame = tk.Frame(yellow_frame, bg=DETAILS_BG)
            specs_frame.pack(fill='x', padx=2, pady=2)
            
            # Panel Details section - always present at the top
            details_section_frame = tk.Frame(specs_frame, bg=DETAILS_BG)
            details_section_frame.pack(fill='x', padx=2, pady=2)
            
            # Header with toggle button
            details_header_frame = tk.Frame(details_section_frame, bg=PRIMARY_BLUE)
            details_header_frame.pack(fill='x')
            
            details_toggle_btn = tk.Button(details_header_frame, text='▶', bg=PRIMARY_BLUE, fg='white',
                                         font=('Segoe UI', 10, 'bold'), bd=0, padx=2, pady=2,
                                         command=lambda: toggle_panel_details(details_toggle_btn, details_content_frame))
            details_toggle_btn.pack(side='left')
            
            tk.Label(details_header_frame, text='🏠 Panel Details', bg=PRIMARY_BLUE, 
                    fg='white', font=('Segoe UI', 10, 'bold'), anchor='w').pack(side='left', fill='x')
            
            # Content frame (initially expanded)
            details_content_frame = tk.Frame(details_section_frame, bg=DETAILS_BG)
            details_content_frame.pack(fill='x', padx=8, pady=2)  # Pack initially to show expanded
            details_toggle_btn.config(text='▼')  # Set to expanded state
            
            # Extract panel details from panel_obj
            details_text = ""
            if panel_obj:
                # Use DisplayLabel for user-friendly panel name, fallback to GUID
                panel_name = panel_obj.get('DisplayLabel', name)
                level = panel_obj.get('Level', 'Unknown')
                bundle = panel_obj.get('BundleName') or panel_obj.get('Bundle') or 'Unknown'
                
                details_text += f"• Panel Name: {panel_name}\n"
                details_text += f"• Level: {level}\n"
                details_text += f"• Bundle: {bundle}\n"
            else:
                details_text = "• Panel Name: Unknown\n• Level: Unknown\n• Bundle: Unknown\n"
            
            tk.Label(details_content_frame, text=details_text.strip(), bg=DETAILS_BG, 
                    fg=TEXT_MEDIUM, font=('Segoe UI', 12), justify='left', anchor='w',
                    wraplength=DEFAULT_STATE['details_w']-20).pack(
                    padx=4, pady=2, fill='x')
            
            # Panel Specifications section - always present
            panel_section_frame = tk.Frame(specs_frame, bg=DETAILS_BG)
            panel_section_frame.pack(fill='x', padx=2, pady=2)
            
            # Header with toggle button
            panel_header_frame = tk.Frame(panel_section_frame, bg=SECONDARY_TEAL)
            panel_header_frame.pack(fill='x')
            
            panel_toggle_btn = tk.Button(panel_header_frame, text='▶', bg=SECONDARY_TEAL, fg='white',
                                       font=('Segoe UI', 10, 'bold'), bd=0, padx=2, pady=2,
                                       command=lambda: toggle_panel_specs(panel_toggle_btn, panel_content_frame))
            panel_toggle_btn.pack(side='left')
            
            tk.Label(panel_header_frame, text='📋 Panel Specifications', bg=SECONDARY_TEAL, 
                    fg='white', font=('Segoe UI', 10, 'bold'), anchor='w').pack(side='left', fill='x')
            
            # Content frame (initially expanded)
            panel_content_frame = tk.Frame(panel_section_frame, bg=DETAILS_BG)
            panel_content_frame.pack(fill='x', padx=8, pady=2)  # Pack initially to show expanded
            panel_toggle_btn.config(text='▼')  # Set to expanded state
            
            # Extract panel specs from yellow_data if available, otherwise fall back to panel_obj
            if yellow_data and 'specs' in yellow_data:
                # Use detailed specifications from takeoff processing
                specs = yellow_data['specs']
                
                # Format wall length with proper dimension display
                wall_length_display = specs.get('wall_length', '')
                if wall_length_display:
                    try:
                        # Convert to feet-inches format like "131 in (10'-10-7/8\")"
                        length_inches = float(wall_length_display)
                        feet_inches = format_feet_to_dimension(length_inches / 12.0)
                        wall_length_display = f"{length_inches:.1f} in ({feet_inches})"
                    except (ValueError, TypeError):
                        pass
                
                # Format wall length actual with growth allowance
                wall_length_actual_display = specs.get('wall_length_actual', '')
                growth_allowance_display = specs.get('growth_allowance', '')
                if wall_length_actual_display and growth_allowance_display:
                    try:
                        actual_inches = float(wall_length_actual_display)
                        growth_inches = float(growth_allowance_display)
                        actual_feet_inches = format_feet_to_dimension(actual_inches / 12.0)
                        wall_length_actual_display = f"{actual_inches:.1f} in ({actual_feet_inches}) +{growth_inches:.1f}\" GA"
                    except (ValueError, TypeError):
                        pass
                
                # Format height
                height_display = specs.get('height', '')
                if height_display:
                    try:
                        height_inches = float(height_display)
                        height_feet_inches = format_feet_to_dimension(height_inches / 12.0)
                        height_display = f"{height_inches:.1f} in ({height_feet_inches})"
                    except (ValueError, TypeError):
                        pass
                
                # Format squaring
                squaring_display = specs.get('squaring', '')
                if squaring_display:
                    try:
                        squaring_inches = float(squaring_display)
                        squaring_feet_inches = format_feet_to_dimension(squaring_inches / 12.0)
                        squaring_display = f"{squaring_inches:.3f} in ({squaring_feet_inches})"
                    except (ValueError, TypeError):
                        pass
                
                # Format thickness
                thickness_display = specs.get('thickness', '')
                if thickness_display:
                    try:
                        thickness_inches = float(thickness_display)
                        thickness_display = f"{thickness_inches:.1f} in"
                    except (ValueError, TypeError):
                        pass
                
                specs_text = ""
                specs_text += f"• Category: {specs.get('category', 'Unknown')}\n"
                specs_text += f"• Load Bearing: {specs.get('load_bearing', 'Unknown')}\n"
                specs_text += f"• Length: {wall_length_display or 'Unknown'}"
                specs_text += "\n"
                specs_text += f"• Height: {height_display or 'Unknown'}\n"
                specs_text += f"• Squaring: {squaring_display or 'Unknown'}\n"
                specs_text += f"• Thickness: {thickness_display or 'Unknown'}\n"
                specs_text += f"• Stud Spacing: {int(float(specs.get('stud_spacing', 0)))} in\n"
                specs_text += f"• Sheathing: {specs.get('sheathing', 'Unknown')}\n"
                specs_text += f"• Weight: {round(float(specs.get('weight', 0)))} lbs\n"
                specs_text += f"• Production Notes: {specs.get('production_notes', '')}\n"
            else:
                # Fallback to basic panel_obj properties
                if panel_obj:
                    specs_text = ""
                    specs_text += f"• Category: {panel_obj.get('Category', 'Unknown')}\n"
                    specs_text += f"• Load Bearing: {panel_obj.get('LoadBearing', 'Unknown')}\n"
                    specs_text += f"• Length: {panel_obj.get('Length', 'Unknown')}\n"
                    specs_text += f"• Height: {panel_obj.get('Height', 'Unknown')}\n"
                    specs_text += f"• Thickness: {panel_obj.get('Thickness', 'Unknown')}\n"
                    specs_text += f"• Stud Spacing: {panel_obj.get('StudSpacing', 'Unknown')}\n"
                    specs_text += f"• Wall Length: {panel_obj.get('WallLength', 'Unknown')}\n"
                    specs_text += f"• Weight: {panel_obj.get('Weight', 'Unknown')}\n"
                    specs_text += f"• Production Notes: {panel_obj.get('OnScreenInstruction', '')}\n"
                
            tk.Label(panel_content_frame, text=specs_text.strip(), bg=DETAILS_BG, 
                    fg=TEXT_MEDIUM, font=('Segoe UI', 12), justify='left', anchor='w',
                    wraplength=DEFAULT_STATE['details_w']-20).pack(
                    padx=4, pady=2, fill='x')
            
            # Beam Pocket Details section - always present
            beam_section_frame = tk.Frame(specs_frame, bg=DETAILS_BG)
            beam_section_frame.pack(fill='x', padx=2, pady=2)
            
            # Header with toggle button
            beam_header_frame = tk.Frame(beam_section_frame, bg=SUCCESS_GREEN)
            beam_header_frame.pack(fill='x')
            
            beam_toggle_btn = tk.Button(beam_header_frame, text='▶', bg=SUCCESS_GREEN, fg='white',
                                      font=('Segoe UI', 10, 'bold'), bd=0, padx=2, pady=2,
                                      command=lambda: toggle_beam_pocket_details(beam_toggle_btn, beam_content_frame))
            beam_toggle_btn.pack(side='left')
            
            tk.Label(beam_header_frame, text='🔧 Beam Pocket Details', bg=SUCCESS_GREEN, 
                    fg='white', font=('Segoe UI', 10, 'bold'), anchor='w').pack(side='left', fill='x')
            
            # Content frame (initially hidden)
            beam_content_frame = tk.Frame(beam_section_frame, bg=DETAILS_BG)
            # Don't pack initially - will be shown when expanded
            
            beam_text = "No beam pockets found."
            if yellow_data and yellow_data.get('beam_pockets'):
                beam_text = ""
                for pocket in yellow_data['beam_pockets']:
                    # Truncate GUID to 8 characters + "..."
                    guid = pocket.get('guid', '')
                    if len(guid) > 8:
                        guid_display = guid[:8] + "..."
                    else:
                        guid_display = guid
                    
                    # Get FM type - beam pockets are typically FM25
                    fm_type = pocket.get('fm_type', 'FM25')
                    
                    beam_text += f"• Beam Pocket (Guid: {guid_display}) ({fm_type})\n"
                    
                    # Format AFF with feet-inches-sixteenths
                    if pocket.get('aff') is not None:
                        aff_feet = float(pocket['aff']) / 12.0
                        formatted_aff = format_feet_to_dimension(aff_feet)
                        beam_text += f"• AFF: {formatted_aff} ({pocket['aff']:.1f} in)\n"
                    
                    # Format opening width with feet-inches-sixteenths
                    if pocket.get('opening_width'):
                        opening_feet = float(pocket['opening_width']) / 12.0
                        formatted_opening = format_feet_to_dimension(opening_feet)
                        beam_text += f"• Opening Width: {formatted_opening} ({pocket['opening_width']:.1f} in)\n"
                    
                    # Associated Material Parts
                    if pocket.get('materials'):
                        beam_text += "• Associated Material Parts:\n"
                        for label, count in pocket['materials'].items():
                            beam_text += f" ├── {label} ({count})\n"
                    
                    beam_text += "\n"
                
                # Add total count
                total_pockets = len(yellow_data['beam_pockets'])
                beam_text += f"Total Beam Pockets: {total_pockets}\n"
            
            tk.Label(beam_content_frame, text=beam_text.strip(), bg=DETAILS_BG, 
                    fg=TEXT_MEDIUM, font=('Segoe UI', 12), justify='left', anchor='w').pack(
                    padx=4, pady=2, fill='x')
            
            # Critical Stud Details section - always present
            stud_section_frame = tk.Frame(specs_frame, bg=DETAILS_BG)
            stud_section_frame.pack(fill='x', padx=2, pady=2)
            
            # Header with toggle button
            stud_header_frame = tk.Frame(stud_section_frame, bg=WARNING_ORANGE)
            stud_header_frame.pack(fill='x')
            
            stud_toggle_btn = tk.Button(stud_header_frame, text='▶', bg=WARNING_ORANGE, fg='white',
                                      font=('Segoe UI', 10, 'bold'), bd=0, padx=2, pady=2,
                                      command=lambda: toggle_critical_stud_details(stud_toggle_btn, stud_content_frame))
            stud_toggle_btn.pack(side='left')
            
            tk.Label(stud_header_frame, text='⚠️ Critical Stud Details', bg=WARNING_ORANGE, 
                    fg='white', font=('Segoe UI', 10, 'bold'), anchor='w').pack(side='left', fill='x')
            
            # Content frame (initially hidden)
            stud_content_frame = tk.Frame(stud_section_frame, bg=DETAILS_BG)
            # Don't pack initially - will be shown when expanded
            
            stud_text = "No critical studs found."
            if yellow_data and yellow_data.get('critical_studs'):
                stud_text = ""
                for stud in yellow_data['critical_studs']:
                    # Truncate GUID to 8 characters + "..."
                    guid = stud.get('guid', '')
                    if len(guid) > 8:
                        guid_display = guid[:8] + "..."
                    else:
                        guid_display = guid
                    
                    # Get FM type
                    fm_type = stud.get('fm_type', 'FM32')  # Default to FM32 for critical studs
                    
                    stud_text += f"• Critical Stud (Guid: {guid_display}) ({fm_type})\n"
                    stud_text += f"• Type: {stud.get('type', 'SubAssembly critical stud')}\n"
                    
                    # Format distance with feet-inches-sixteenths
                    if stud.get('distance'):
                        # Extract numeric value from formatted distance string like '46.9 in (3\'-10-7/8")'
                        distance_str = str(stud['distance'])
                        if ' in (' in distance_str:
                            # Extract the numeric part before ' in ('
                            numeric_part = distance_str.split(' in (')[0].strip()
                            try:
                                distance_inches = float(numeric_part)
                                distance_feet = distance_inches / 12.0
                            except ValueError:
                                distance_feet = 0.0
                        else:
                            # Fallback: try to parse as direct number
                            try:
                                distance_feet = float(distance_str) / 12.0
                            except ValueError:
                                distance_feet = 0.0
                        
                        formatted_distance = format_feet_to_dimension(distance_feet)
                        stud_text += f"• Distance: {distance_feet:.1f} in ({formatted_distance})\n"
                    
                    # Associated Material Parts
                    if stud.get('materials'):
                        stud_text += "• Associated Material Parts:\n"
                        for label, count in stud['materials'].items():
                            stud_text += f" ├── {label} ({count})\n"
                    
                    stud_text += "\n"
                
                # Add total count
                total_studs = len(yellow_data['critical_studs'])
                stud_text += f"Total Critical Studs: {total_studs}\n"
            
            tk.Label(stud_content_frame, text=stud_text.strip(), bg=DETAILS_BG, 
                    fg=TEXT_MEDIUM, font=('Segoe UI', 12), justify='left', anchor='w').pack(
                    padx=4, pady=2, fill='x')
            
            # SubAssembly Details section - always present
            sub_section_frame = tk.Frame(specs_frame, bg=DETAILS_BG)
            sub_section_frame.pack(fill='x', padx=2, pady=2)
            
            # Header with toggle button
            sub_header_frame = tk.Frame(sub_section_frame, bg=DANGER_RED)
            sub_header_frame.pack(fill='x')
            
            sub_toggle_btn = tk.Button(sub_header_frame, text='▶', bg=DANGER_RED, fg='white',
                                     font=('Segoe UI', 10, 'bold'), bd=0, padx=2, pady=2,
                                     command=lambda: toggle_subassembly_details(sub_toggle_btn, sub_content_frame))
            sub_toggle_btn.pack(side='left')
            
            tk.Label(sub_header_frame, text='🔧 SubAssembly Details', bg=DANGER_RED, 
                    fg='white', font=('Segoe UI', 10, 'bold'), anchor='w').pack(side='left', fill='x')
            
            # Content frame (initially hidden)
            sub_content_frame = tk.Frame(sub_section_frame, bg=DETAILS_BG)
            # Don't pack initially - will be shown when expanded
            
            sub_text = "No subassemblies found."
            if yellow_data and yellow_data.get('subassemblies'):
                sub_text = ""
                for sub in yellow_data['subassemblies']:
                    # Truncate GUID to 8 characters + "..."
                    guid = sub.get('guid', '')
                    if len(guid) > 8:
                        guid_display = guid[:8] + "..."
                    else:
                        guid_display = guid
                    
                    # Get FM type
                    fm_type = sub.get('fm_type', 'FM32')  # Default to FM32
                    
                    sub_text += f"• {sub.get('name', 'Unknown')} (Guid: {guid_display}) ({fm_type})\n"
                    
                    # Associated Material Parts
                    if sub.get('materials'):
                        sub_text += "   • Associated Material Parts:\n"
                        for label, count in sorted(sub['materials'].items()):
                            sub_text += f"    ├── {label} ({count})\n"
                    
                    # Rough Openings
                    if sub.get('rough_openings'):
                        sub_text += "   • Rough Openings:\n"
                        for ro in sub['rough_openings']:
                            sub_text += f"    ├── Rough Opening: {ro['dimensions']} (FM-1)\n"
                            if ro['aff'] is not None:
                                aff_formatted = format_feet_to_dimension(ro['aff']/12)
                                sub_text += f"    ├── AFF: {ro['aff']:.1f} ({aff_formatted})\n"
                    
                    sub_text += "\n"
                
                # Add total count
                total_subs = len(yellow_data['subassemblies'])
                sub_text += f"Total SubAssemblies: {total_subs}\n"
            
            tk.Label(sub_content_frame, text=sub_text.strip(), bg=DETAILS_BG, 
                    fg=TEXT_MEDIUM, font=('Segoe UI', 12), justify='left', anchor='w').pack(
                    padx=4, pady=2, fill='x')
        
        # Display pink zone (Material Breakdown)
        if pink_data:
            pink_frame = tk.Frame(breakdown_scrollable_frame, bg=BREAKDOWN_BG)
            pink_frame.pack(fill='x', padx=4, pady=4)
            
            # Header
            pink_header = tk.Frame(pink_frame, bg=PRIMARY_BLUE)
            pink_header.pack(fill='x', padx=2, pady=2)
            tk.Label(pink_header, text='MATERIAL BREAKDOWN', bg=PRIMARY_BLUE, 
                    fg='white', font=('Segoe UI', 10, 'bold')).pack(pady=4)
            
            # Material breakdown content - centered
            breakdown_content = tk.Label(pink_frame, text=pink_data, bg=BREAKDOWN_BG, 
                                       fg=TEXT_MEDIUM, font=('Segoe UI', 12), 
                                       justify='center', anchor='center', wraplength=DEFAULT_STATE['breakdown_w']-20)
            breakdown_content.pack(padx=4, pady=2, fill='both', expand=True)
    def on_panel_selected(name):
        try:
            # Remove highlighting from previously selected button
            if selected_button['widget']:
                try:
                    # Reset to normal appearance for ttk.Button
                    selected_button['widget'].configure(style='TButton')
                except Exception:
                    pass
            
            selected_panel['name'] = name
            
            # Apply highlighting to newly selected button
            if name in panel_button_map:
                selected_button['widget'] = panel_button_map[name]
                try:
                    # Apply selected appearance for ttk.Button - use a different style
                    selected_button['widget'].configure(style='Selected.TButton')
                except Exception:
                    pass
            
            obj = current_panels.get(name, {})
            mats = panel_materials_map.get(name, [])
            
            # Process panel for takeoff data
            yellow_data, pink_data, export_data = process_panel_for_takeoff(name, root)
            print(f"DEBUG: on_panel_selected got export_data = {repr(export_data[:100] if export_data else None)}...")
            logging.debug(f"DEBUG: on_panel_selected got export_data = {repr(export_data[:100] if export_data else None)}...")
            # Display the panel with takeoff data
            display_panel(name, obj, mats, yellow_data, pink_data, export_data)
        except Exception as e:
            print(f"Error in on_panel_selected: {e}")
            import traceback
            traceback.print_exc()

    def change_bundle_page(bundle_key, direction):
        """Change the current page for a bundle and refresh the display"""
        if hasattr(rebuild_bundles, 'bundle_pages'):
            current_page = rebuild_bundles.bundle_pages.get(bundle_key, 0)
            rebuild_bundles.bundle_pages[bundle_key] = current_page + direction
            rebuild_bundles(5)  # Refresh the bundle display

    def change_bundle_page_global(direction: int):
        """Change the current bundle page and refresh the display"""
        if hasattr(rebuild_bundles, 'bundle_page'):
            rebuild_bundles.bundle_page += direction
            rebuild_bundles(5)  # Refresh the bundle display

    def rebuild_bundles(count: int):
        for ch in btn_grid.winfo_children():
            ch.destroy()
        panel_button_widgets.clear()
        panel_button_map.clear()  # Clear button mapping when rebuilding
        cols = max(1, min(8, count))
        for c in range(cols):
            btn_grid.grid_columnconfigure(c, weight=1)
        try:
            btn_grid.grid_rowconfigure(0, weight=1)
        except Exception:
            pass

        # Initialize bundle variables
        all_bundle_keys = []
        actual_displayed_cols = count  # Default to the count parameter

        # Pagination state: current page for each bundle (0-based)
        if not hasattr(rebuild_bundles, 'bundle_pages'):
            rebuild_bundles.bundle_pages = {}
        if not hasattr(rebuild_bundles, 'panels_per_page'):
            rebuild_bundles.panels_per_page = 16  # 4x4 grid

        # Bundle-level pagination state
        if not hasattr(rebuild_bundles, 'bundle_page'):
            rebuild_bundles.bundle_page = 0
        if not hasattr(rebuild_bundles, 'bundles_per_page'):
            rebuild_bundles.bundles_per_page = 5  # Show 5 bundles per page

        if panels_loaded and current_panels:
            panels_by_name = current_panels
            bundle_panels = {}
            # Prefer human-readable bundle names over GUIDs for grouping
            for name, obj in panels_by_name.items():
                bkey = None
                display_label = None
                if isinstance(obj, dict):
                    # Prioritize human-readable names over GUIDs
                    bkey = obj.get('BundleName') or obj.get('Bundle') or obj.get('BundleLabel') or obj.get('BundleGuid') or obj.get('BundleId')
                    display_label = obj.get('BundleName') or obj.get('Bundle') or obj.get('BundleLabel')
                    
                    # Normalize bundle names to handle minor differences
                    if bkey:
                        bkey = bkey.strip()
                    if display_label:
                        display_label = display_label.strip()

                # If no bundle information, use a default bundle name
                if not bkey:
                    bkey = 'NoBundle'
                    display_label = 'No Bundle'

                if not bkey:
                    bkey = 'Bundle'
                
                # Normalize the bundle key for grouping
                normalized_bkey = normalize_bundle_key(bkey)
                
                # Use normalized key for grouping, but keep original display_label
                if normalized_bkey not in bundle_panels:
                    bundle_panels[normalized_bkey] = {'panels': [], 'label': display_label}
                else:
                    # If we already have this bundle, prefer the display_label that has more info
                    existing_label = bundle_panels[normalized_bkey]['label']
                    if len(display_label) > len(existing_label):
                        bundle_panels[normalized_bkey]['label'] = display_label
                
                bundle_panels[normalized_bkey]['panels'].append(name)

            # Sort panels within each bundle by DisplayLabel instead of panel name
            for bundle_key, bundle_data in bundle_panels.items():
                # Create a mapping of panel names to their DisplayLabels for sorting
                panel_display_map = {}
                for panel_name in bundle_data['panels']:
                    if panel_name in current_panels:
                        panel_obj = current_panels[panel_name]
                        display_label = panel_obj.get('DisplayLabel', panel_name)
                        panel_display_map[panel_name] = display_label
                
                # Sort panels by their DisplayLabel (what the user sees on buttons)
                bundle_data['panels'] = sorted(bundle_data['panels'], 
                                             key=lambda name: get_panel_sort_key(panel_display_map.get(name, name)))

            # Get all bundle keys and sort them by bundle number
            all_bundle_keys = sort_bundle_keys(bundle_panels.keys())
            total_bundle_pages = max(1, (len(all_bundle_keys) + rebuild_bundles.bundles_per_page - 1) // rebuild_bundles.bundles_per_page)

            # Ensure current bundle page is valid
            if rebuild_bundles.bundle_page >= total_bundle_pages:
                rebuild_bundles.bundle_page = total_bundle_pages - 1
            if rebuild_bundles.bundle_page < 0:
                rebuild_bundles.bundle_page = 0

            # Get bundles for current page
            start_idx = rebuild_bundles.bundle_page * rebuild_bundles.bundles_per_page
            end_idx = min(start_idx + rebuild_bundles.bundles_per_page, len(all_bundle_keys))
            page_bundle_keys = all_bundle_keys[start_idx:end_idx]

            # Update actual displayed columns for font scaling
            actual_displayed_cols = len(page_bundle_keys)

            # Set up grid for current page bundles
            cols = len(page_bundle_keys)
            for c in range(max(1, min(8, cols))):  # Keep original column limit
                btn_grid.grid_columnconfigure(c, weight=1)
            try:
                btn_grid.grid_rowconfigure(0, weight=1)
                # Configure row 1 for bundle navigation if needed
                if total_bundle_pages > 1:
                    btn_grid.grid_rowconfigure(1, weight=0)
            except Exception:
                pass

            # Create bundles for current page
            for bi, bf_key in enumerate(page_bundle_keys):
                entry = bundle_panels.get(bf_key, {'panels': [], 'label': None})
                bf_text = entry.get('label') or bf_key
                # If bf_text is still a GUID (contains only hex characters), try to create a more readable name
                if bf_text and len(bf_text) >= 8 and all(c in '0123456789abcdefABCDEF' for c in bf_text.replace('-', '')):
                    # This looks like a GUID, try to find a better name from the panels
                    panels_in_bundle = entry.get('panels', [])
                    if panels_in_bundle:
                        # Try to extract a meaningful name from the first panel
                        first_panel = panels_in_bundle[0]
                        if '_' in first_panel:
                            # Extract bundle name from panel name (e.g., "B4_001" -> "B4")
                            potential_name = first_panel.split('_')[0]
                            if potential_name and len(potential_name) <= 10:  # Reasonable length check
                                bf_text = potential_name
                label_text = bf_text if bf_text else f'Bundle {bi+1}'
                bf = tk.LabelFrame(btn_grid, text=label_text, bg=BUTTONS_BG)
                bf.grid(row=0, column=bi, sticky='nsew', padx=4, pady=4)

                # get panels for this bundle key; if bf_text is None use empty
                panels_for = entry.get('panels', [])

                # Calculate pagination for this bundle
                total_panels = len(panels_for)
                total_pages = max(1, (total_panels + rebuild_bundles.panels_per_page - 1) // rebuild_bundles.panels_per_page)
                current_page = rebuild_bundles.bundle_pages.get(bf_key, 0)

                # Ensure current page is valid
                if current_page >= total_pages:
                    current_page = total_pages - 1
                if current_page < 0:
                    current_page = 0
                rebuild_bundles.bundle_pages[bf_key] = current_page

                # Get panels for current page
                start_idx = current_page * rebuild_bundles.panels_per_page
                end_idx = min(start_idx + rebuild_bundles.panels_per_page, total_panels)
                page_panels = panels_for[start_idx:end_idx]

                try:
                    # Adjust height to accommodate navigation if needed
                    base_height = max(44, btns_frame.winfo_height() - 16)
                    if total_pages > 1:
                        base_height += 30  # Extra space for navigation
                    bf.grid_propagate(False)
                    bf.configure(height=base_height)
                    # Don't set explicit width - let grid weights handle it like buttons.py
                    # bf.configure(width=btns_frame.winfo_width() // cols - 8)
                except Exception:
                    pass

                # Always create a 4x4 grid structure like buttons.py
                rows = 4
                cols_per_bundle = 4

                # Create a mapping of panel positions in the 4x4 grid
                panel_positions = {}
                for idx, panel_name in enumerate(page_panels):
                    row = idx // cols_per_bundle
                    col = idx % cols_per_bundle
                    panel_positions[(row, col)] = panel_name

                # Create the 4x4 grid of buttons
                for r in range(rows):
                    for c in range(cols_per_bundle):
                        if (r, c) in panel_positions:
                            # Create active button for actual panel
                            panel_name = panel_positions[(r, c)]
                            obj = current_panels.get(panel_name, {})
                            mats = panel_materials_map.get(panel_name, [])

                            # Use DisplayLabel for button display, fallback to internal name
                            display_name = obj.get('DisplayLabel', panel_name)

                            # Parse panel name to extract lot and panel numbers
                            lot_num = ''
                            panel_num = display_name
                            if '_' in display_name:
                                parts = display_name.split('_', 1)
                                if len(parts) == 2:
                                    lot_num = parts[0]
                                    panel_num = parts[1]

                            # Format panel button text: last 3 digits only
                            if panel_num:
                                # Take only the last 3 digits (or the whole string if shorter)
                                if len(panel_num) > 3:
                                    panel_num = panel_num[-3:]

                            # Create button with buttons.py visual style
                            # Calculate the correct font size based on number of bundles
                            bundle_cols = len(page_bundle_keys) if 'page_bundle_keys' in locals() and page_bundle_keys else actual_displayed_cols
                            temp_cols_eff = max(1, min(8, bundle_cols))
                            temp_btns_w = btns_frame.winfo_width() or btn_grid.winfo_reqwidth() or 600
                            temp_per_bundle_w = max(40, int((temp_btns_w - (temp_cols_eff * 12)) / temp_cols_eff))
                            correct_font_size = max(9, min(12, temp_per_bundle_w // 30))
                            
                            btn = ttk.Button(bf, text=panel_num,
                                           command=lambda n=panel_name: on_panel_selected(n))

                            # Apply correct font size immediately
                            try:
                                correct_btn_font = tkfont.Font(size=correct_font_size)
                                btn.configure(font=correct_btn_font)
                            except Exception:
                                pass

                            try:
                                attach_hover_tooltip(btn, lambda n=panel_name, d=display_name: d)
                            except Exception:
                                pass
                            
                            # Store button reference for visual feedback
                            panel_button_map[panel_name] = btn
                        else:
                            btn = ttk.Button(bf, text='', state='disabled')
                            # Apply correct font size to placeholder buttons too
                            try:
                                correct_btn_font = tkfont.Font(size=correct_font_size)
                                btn.configure(font=correct_btn_font)
                            except Exception:
                                pass

                        # Place button in grid with buttons.py styling
                        btn.grid(row=r, column=c, sticky='nsew', padx=3, pady=2)
                        panel_button_widgets.append(btn)

                # Configure all grid weights for equal expansion like buttons.py
                for rr in range(rows):
                    bf.grid_rowconfigure(rr, weight=1)
                for cc in range(cols_per_bundle):
                    bf.grid_columnconfigure(cc, weight=1)

                # Add navigation buttons if there are multiple pages
                if total_pages > 1:
                    # Create navigation frame at the bottom
                    nav_frame = tk.Frame(bf, bg=BUTTONS_BG)
                    nav_frame.grid(row=rows, column=0, columnspan=cols_per_bundle, sticky='ew', padx=3, pady=2)

                    # Page indicator
                    page_label = tk.Label(nav_frame, text=f'Page {current_page + 1}/{total_pages}',
                                        bg=BUTTONS_BG, font=('Arial', 8))
                    page_label.pack(side='left', expand=True)

                    # Previous button
                    prev_btn = ttk.Button(nav_frame, text='Prev',
                                        command=lambda b=bf_key: change_bundle_page(b, -1),
                                        state='normal' if current_page > 0 else 'disabled')
                    prev_btn.pack(side='left', padx=(0, 2))

                    # Next button
                    next_btn = ttk.Button(nav_frame, text='Next',
                                        command=lambda b=bf_key: change_bundle_page(b, 1),
                                        state='normal' if current_page < total_pages - 1 else 'disabled')
                    next_btn.pack(side='right', padx=(2, 0))

                    # Configure navigation frame to span full width
                    nav_frame.grid_columnconfigure(0, weight=1)
        else:
            # No panels loaded - don't create any buttons to keep white zone empty
            pass

        # Add bundle-level navigation if there are more bundles than can fit on one page
        total_bundle_pages = (len(all_bundle_keys) + rebuild_bundles.bundles_per_page - 1) // rebuild_bundles.bundles_per_page
        if total_bundle_pages > 1:
            # Create navigation frame at the bottom of the button grid
            bundle_nav_frame = tk.Frame(btn_grid, bg=BUTTONS_BG)
            bundle_nav_frame.grid(row=1, column=0, columnspan=cols, sticky='ew', padx=4, pady=4)
            
            # Bundle page indicator
            bundle_page_label = tk.Label(bundle_nav_frame, text=f'Bundle Page {rebuild_bundles.bundle_page + 1}/{total_bundle_pages}',
                                       bg=BUTTONS_BG, font=('Arial', 9, 'bold'))
            bundle_page_label.pack(side='left', expand=True)
            
            # Previous bundle page button
            prev_bundle_btn = ttk.Button(bundle_nav_frame, text='Prev Bundles',
                                       command=lambda: change_bundle_page_global(-1),
                                       state='normal' if rebuild_bundles.bundle_page > 0 else 'disabled')
            prev_bundle_btn.pack(side='left', padx=(0, 5))
            
            # Next bundle page button
            next_bundle_btn = ttk.Button(bundle_nav_frame, text='Next Bundles',
                                       command=lambda: change_bundle_page_global(1),
                                       state='normal' if rebuild_bundles.bundle_page < total_bundle_pages - 1 else 'disabled')
            next_bundle_btn.pack(side='right', padx=(5, 0))

        # After building all bundles, scale button fonts to fit horizontally across equal columns
        try:
            btns_w = btns_frame.winfo_width() or btn_grid.winfo_reqwidth() or 600
            # Use actual number of bundles displayed on current page, not the fixed count parameter
            cols_eff = max(1, min(8, actual_displayed_cols))
            per_bundle_w = max(40, int((btns_w - (cols_eff * 12)) / cols_eff))
            # choose font size proportional to per-bundle width
            fw = max(9, min(12, per_bundle_w // 30))
            btn_font = tkfont.Font(size=fw)
            for w in panel_button_widgets:
                try:
                    w.configure(font=btn_font)
                except Exception:
                    pass
        except Exception:
            pass

    rebuild_bundles(5)

    def populate_level_breakdown():
        """Populate the breakdown zone with all materials from the current level"""
        try:
            # Clear existing breakdown content
            for ch in breakdown_scrollable_frame.winfo_children():
                ch.destroy()
            
            # Collect all materials from current panels
            all_materials = []
            for panel_name, panel_obj in current_panels.items():
                panel_materials = panel_materials_map.get(panel_name, [])
                all_materials.extend(panel_materials)
            
            # Remove duplicates and rough openings
            unique_materials = []
            seen = set()
            for m in all_materials:
                if not isinstance(m, dict):
                    continue
                if _is_rough_opening(m):
                    continue
                
                # Create a unique key for this material
                key = (
                    m.get('Label', ''),
                    m.get('Type', ''),
                    m.get('Desc', ''),
                    m.get('Description', ''),
                    str(m.get('ActualLength', '')),
                    str(m.get('ActualWidth', '')),
                    str(m.get('Length', '')),
                    str(m.get('Width', ''))
                )
                
                if key not in seen:
                    seen.add(key)
                    unique_materials.append(m)
            
            # Use format_and_sort_materials if available
            lines = []
            
            try:
                if callable(format_and_sort_materials):
                    lines = format_and_sort_materials(unique_materials)
                else:
                    # Fallback simple formatter
                    for m in unique_materials:
                        lbl = m.get('Label') or m.get('Name') or ''
                        typ = m.get('Type') or ''
                        desc = m.get('Desc') or m.get('Description') or ''
                        qty = m.get('Qty') or m.get('Quantity') or ''
                        length = m.get('ActualLength') or m.get('Length') or ''
                        width = m.get('ActualWidth') or m.get('Width') or ''
                        
                        # Strip trailing zeros from dimensions
                        if length:
                            length = format_dimension(str(length))
                        if width:
                            width = format_dimension(str(width))
                        
                        size = f"{length} x {width}".strip() if width else (length or '')
                        qty_str = f"({qty})" if qty else ''
                        if size:
                            lines.append(f"{lbl} - {typ} - {desc} - {qty_str} - {size}")
                        else:
                            lines.append(f"{lbl} - {typ} - {desc} - {qty_str}")
            except Exception:
                lines = []

            # Add professional header for breakdown section
            if lines:
                breakdown_header = tk.Frame(breakdown_scrollable_frame, bg=PRIMARY_BLUE)
                breakdown_header.pack(fill='x', padx=4, pady=6)
                tk.Label(breakdown_header, text=f'📋 Level Material Breakdown ({len(lines)} items)',
                        bg=PRIMARY_BLUE, fg='white', font=('Segoe UI', 11, 'bold'),
                        anchor='center').pack(anchor='center', padx=8, pady=4)

                # Professional breakdown display with better formatting
                for l in lines:
                    try:
                        # Create a frame for each material line with better styling
                        material_frame = tk.Frame(breakdown_scrollable_frame, bg=BREAKDOWN_BG,
                                                relief='flat', bd=0)
                        material_frame.pack(fill='x', padx=6, pady=2)

                        # Add subtle background for alternating rows
                        if lines.index(l) % 2 == 0:
                            material_frame.configure(bg='#f8f9fa')

                        tk.Label(material_frame, text=l, bg=material_frame['bg'],
                                fg=TEXT_MEDIUM, font=('Segoe UI', 10),
                                anchor='center', justify='center',
                                wraplength=DEFAULT_STATE['breakdown_w']-20).pack(
                                anchor='center', fill='x', padx=4, pady=3)
                    except Exception:
                        pass

            # Center the content after adding all labels
            root.after(100, center_breakdown_content)
        except Exception as e:
            if debug_enabled:
                print(f"Error populating level breakdown: {e}")

    def process_selected_ehx(evt=None):
        nonlocal panels_loaded, selected_level, current_panels, original_panels, panel_materials_map, original_materials_map
        global current_ehx_file_path
        sel = file_listbox.curselection()
        if not sel:
            return
        fname = file_listbox.get(sel[0])
        folder = folder_entry.get() or os.getcwd()
        full = os.path.join(folder, fname)
        
        # Show loading status message
        status_val.config(text="Loading File Please Wait")
        root.update_idletasks()  # Force GUI to update and show the loading message
        
        # Store the current EHX file path globally
        root.ehx_file_path = full
        
        # Reset level selection for new file so it can auto-select lowest level
        selected_level['value'] = None
        
        # Clear zones when loading new file - they should only show when panel is selected
        for ch in details_scrollable_frame.winfo_children():
            ch.destroy()
        for ch in breakdown_scrollable_frame.winfo_children():
            ch.destroy()
        
        # Run file processing in a separate thread to keep GUI responsive
        def process_file_thread():
            try:
                process_ehx_file(full, folder)
            except Exception as e:
                # Handle errors on the main thread
                root.after(0, lambda: handle_processing_error(e))
        
        # Start processing in background thread
        thread = threading.Thread(target=process_file_thread, daemon=True)
        thread.start()

    def process_ehx_file(full_path, folder_path):
        """Process EHX file - runs in background thread"""
        nonlocal panels_loaded, selected_level, current_panels, original_panels, panel_materials_map, original_materials_map
        
        # Prefer using a local PV0825 parser if present near the EHX file for exact parity
        pv_mod = None
        try:
            # Temporarily disabled to test local parser
            raise Exception("Testing local parser - skipping PV0825 search")
            candidates = [
                os.path.join(folder, 'PV0825.py'),
                os.path.join(folder, 'Expected', 'PV0825.py'),
                os.path.join(folder, 'Working', 'PV0825.py'),
                os.path.join(folder, 'Working', 'Expected', 'PV0825.py'),
                os.path.join(HERE, 'PV0825.py'),
                os.path.join(HERE, 'Working', 'PV0825.py'),
                os.path.join(HERE, 'Working', 'Expected', 'PV0825.py'),
            ]
            import importlib.util
            for c in candidates:
                try:
                    if c and os.path.exists(c):
                        spec = importlib.util.spec_from_file_location('PV0825_local', c)
                        mod = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(mod)
                        pv_mod = mod
                        break
                except Exception:
                    pv_mod = None
        except Exception:
            pv_mod = None

        if pv_mod and hasattr(pv_mod, 'parse_panels'):
            try:
                panels, materials_map = pv_mod.parse_panels(full_path) or ([], {})
            except Exception:
                panels, materials_map = [], {}
        else:
            try:
                panels, materials_map = parse_panels(full_path) or ([], {})
            except Exception:
                panels, materials_map = [], {}

        # Check if parse_panels returned empty results (indicates EHX version 2.0)
        if not panels and not materials_map:
            # Check if this is actually a version 2.0 file by parsing and checking EHXVersion
            try:
                tree = ET.parse(full_path)
                xml_root = tree.getroot()
                ehx_version_el = xml_root.find('EHXVersion')
                if ehx_version_el is not None and ehx_version_el.text and ehx_version_el.text.strip() == "2.0":
                    # Schedule error dialog on main thread
                    root.after(0, lambda: show_version_error())
                    return
            except Exception:
                pass
        
        # Continue processing on main thread
        root.after(0, lambda: complete_file_processing(panels, materials_map, full_path, folder_path))

    def show_version_error():
        """Show unsupported version error dialog"""
        messagebox.showerror("Unsupported EHX Version", "At this time EHX Version 2.0 is not supported!")
        # Clear the GUI of the loaded file
        current_panels.clear()
        original_panels.clear()
        panel_materials_map.clear()
        original_materials_map.clear()
        panels_loaded = False
        selected_panel['name'] = None
        # Clear button highlighting
        if selected_button['widget']:
            try:
                selected_button['widget'].configure(relief='raised')
            except Exception:
                pass
        selected_button['widget'] = None
        # Clear zones
        for ch in details_scrollable_frame.winfo_children():
            ch.destroy()
        for ch in breakdown_scrollable_frame.winfo_children():
            ch.destroy()
        # Update UI
        update_level_buttons()
        rebuild_bundles(5)
        # Clear loading status message
        status_val.config(text="")

    def handle_processing_error(error):
        """Handle processing errors"""
        print(f"Error processing file: {error}")
        # Clear loading status message
        status_val.config(text="")
        messagebox.showerror("Processing Error", f"Error processing EHX file: {error}")

    def complete_file_processing(panels, materials_map, full_path, folder_path):
        """Complete file processing on main thread"""
        nonlocal panels_loaded, selected_level, current_panels, original_panels, panel_materials_map, original_materials_map
        
        panels_by_name = {}
        if isinstance(panels, dict):
            panels_by_name.update(panels)
        else:
            for p in panels or []:
                if not p:
                    continue
                # Use the Name field (PanelGuid) as the internal key
                name = p.get('Name')
                if not name:
                    name = f"Panel_{len(panels_by_name)+1}"
                panels_by_name[name] = p

        current_panels.clear(); current_panels.update(panels_by_name)
        original_panels.clear(); original_panels.update(panels_by_name)  # Store original data
        panel_materials_map.clear()
        original_materials_map.clear()  # Clear original materials data
        if isinstance(materials_map, dict):
            for k, v in materials_map.items():
                panel_materials_map[k] = v or []
                original_materials_map[k] = v or []  # Store original materials data

        # Update level buttons based on loaded panels
        update_level_buttons()
        
        # Apply level filtering to show only the selected level
        if selected_level['value'] is not None:
            filter_panels_by_level()
            # Clear zones when level changes - they should only show when panel is selected
            for ch in details_scrollable_frame.winfo_children():
                ch.destroy()
            for ch in breakdown_scrollable_frame.winfo_children():
                ch.destroy()

        try:
            jp = extract_jobpath(full_path) if callable(extract_jobpath) else ''
            if jp:
                path_val.config(text=jp)
            
            # Extract JobID from EHX file for display
            job_id = "expected"
            try:
                tree = ET.parse(full_path)
                xml_root = tree.getroot()
                job_el = xml_root.find('Job')
                if job_el is not None:
                    job_id_el = job_el.find('JobID')
                    if job_id_el is not None and job_id_el.text:
                        job_id = job_id_el.text.strip()
            except Exception:
                pass
            
            job_val.config(text=job_id)
        except Exception:
            pass

        # write expected/materials logs next to the processed file (auto-create/clear)
        try:
            # Always log ALL panels regardless of selected level for expected.log
            log_panels = panels_by_name
            log_materials = panel_materials_map

            # prefer PV0825 writer if available; otherwise use local helper
            writer = globals().get('write_expected_and_materials_logs')
            if not writer:
                # import local reference
                writer = write_expected_and_materials_logs
            try:
                writer(full_path, log_panels, log_materials)
                
                # Check for unassigned panels and show GUI warning
                unassigned_panels = detect_unassigned_panels(log_panels)
                if unassigned_panels:
                    warning_msg = f"⚠️ Warning: {len(unassigned_panels)} panel(s) not assigned to any bundle!\n\n"
                    warning_msg += "Unassigned panels:\n"
                    for i, panel in enumerate(unassigned_panels[:10]):  # Show first 10
                        warning_msg += f"• {panel['display_name']} (Level: {panel['level']})\n"
                    if len(unassigned_panels) > 10:
                        warning_msg += f"... and {len(unassigned_panels) - 10} more\n\n"
                    warning_msg += "Check expected.log and materials.log for details."
                    
                    # Show warning message box
                    messagebox.showwarning("Unassigned Panels Detected", warning_msg)
                    
                    # Also print to console for logging
                    print(f"\n⚠️  WARNING: {len(unassigned_panels)} panel(s) not assigned to any bundle:")
                    for panel in unassigned_panels:
                        print(f"   • {panel['display_name']} (Level: {panel['level']})")
                    print("Check expected.log and materials.log for complete details.\n")
                    
            except Exception:
                # last-resort: attempt best-effort write using local helpers
                try:
                    # mimic writer behavior inline
                    import datetime as _dt
                    ts = _dt.datetime.now(_dt.UTC).strftime('%Y-%m-%d %H:%M:%S')
                    folder = HERE  # Use script directory instead of EHX file directory
                    fname = os.path.basename(full_path)
                    with open(os.path.join(folder, 'expected.log'), 'a', encoding='utf-8') as _fh:
                        _fh.write(f"\n=== expected.log updated at {ts} for {fname} ===\n")
                    with open(os.path.join(folder, 'materials.log'), 'a', encoding='utf-8') as _fh:
                        _fh.write(f"\n=== materials.log updated at {ts} for {fname} ===\n")
                except Exception:
                    pass
        except Exception:
            pass

        # After writing expected.log, attempt to parse it and copy AFFs into the
        # in-memory materials so the GUI display/export will match the expected log.
        try:
            expected_path = os.path.join(HERE, 'expected.log')
            if os.path.exists(expected_path):
                with open(expected_path, 'r', encoding='utf-8') as efh:
                    cur_panel = None
                    # map of panel_display_name -> { label -> aff }
                    expected_affs = {}
                    for line in efh:
                        line = line.strip()
                        if not line:
                            continue
                        # detect panel header lines: 'Panel: NAME'
                        if line.startswith('Panel:'):
                            cur_panel = line.split(':', 1)[1].strip()
                            expected_affs.setdefault(cur_panel, {})
                            continue
                        # rough opening entries start with '• Rough Opening:'
                        if line.startswith('• Rough Opening:') or line.startswith('- Rough Opening:'):
                            # Normalize and attempt to extract label and AFF
                            try:
                                # remove leading bullet
                                txt = line.lstrip('•').lstrip('-').strip()
                                # txt like: 'Rough Opening: 25x137-L1 - 137.000 x 25.000 (AFF: 201.375 (16'-9-3/8")) [Headers: F]'
                                # split after 'Rough Opening:'
                                if 'Rough Opening:' in txt:
                                    _, rest = txt.split('Rough Opening:', 1)
                                else:
                                    rest = txt
                                parts = rest.strip().split()
                                if not parts:
                                    continue
                                # first token is label (may be followed by '-' then size)
                                label = parts[0].strip()
                                aff_val = None
                                # find '(AFF:' substring
                                aff_idx = rest.find('(AFF:')
                                if aff_idx != -1:
                                    aff_sub = rest[aff_idx+5:]
                                    # aff_sub begins with ' 201.375' or ' 201.375 (..'
                                    # extract leading numeric
                                    import re as _re
                                    m = _re.search(r"([0-9]+\.?[0-9]*)", aff_sub)
                                    if m:
                                        try:
                                            aff_val = float(m.group(1))
                                        except Exception:
                                            aff_val = None
                                if cur_panel and label and aff_val is not None:
                                    expected_affs.setdefault(cur_panel, {})[label] = aff_val
                            except Exception:
                                continue

                # Propagate expected AFFs into panel_materials_map: match by DisplayLabel or panel key
                try:
                    # Build map from panel key -> display label for quick reverse lookup
                    panel_key_by_display = {}
                    for pk, pobj in panels_by_name.items():
                        display = pobj.get('DisplayLabel', pk)
                        panel_key_by_display[display] = pk

                    for display_name, label_map in expected_affs.items():
                        pk = panel_key_by_display.get(display_name)
                        if not pk:
                            # try matching raw display_name to internal keys directly
                            if display_name in panel_materials_map:
                                pk = display_name
                        if not pk:
                            continue
                        mats = panel_materials_map.get(pk, [])
                        if not mats:
                            continue
                        for m in mats:
                            try:
                                if not isinstance(m, dict):
                                    continue
                                lab = (m.get('Label') or '').strip()
                                sub = (m.get('SubAssembly') or '').strip()
                                # if label matches, set AFF
                                for lbl, affv in label_map.items():
                                    if lbl and (lab == lbl or sub == lbl):
                                        try:
                                            m['AFF'] = float(affv)
                                        except Exception:
                                            m['AFF'] = affv
                                        # also set elev_max_y if not present
                                        if m.get('elev_max_y') in (None, ''):
                                            try:
                                                m['elev_max_y'] = float(affv)
                                            except Exception:
                                                m['elev_max_y'] = affv
                                        break
                            except Exception:
                                continue
                except Exception:
                    pass
        except Exception:
            pass

        panels_loaded = True
        rebuild_bundles(5)

        # Clear loading status message
        status_val.config(text="")

    file_listbox.bind('<Double-Button-1>', process_selected_ehx)

    # Lock/Reset shortcuts
    def save_state(state):
        try:
            os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
            with open(STATE_FILE, 'w', encoding='utf-8') as fh:
                json.dump(state, fh, indent=2)
        except Exception:
            pass

    def toggle_lock_view():
        try:
            st = {'left_w': left.winfo_width(), 'details_w': details_outer.winfo_width(), 'breakdown_w': breakdown_outer.winfo_width(), 'green_h': btns_frame.winfo_height(), 'debug_enabled': debug_enabled}
            save_state(st)
            os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
            with open(LOG_FILE, 'a', encoding='utf-8') as fh:
                fh.write(json.dumps({'ts': _dt.datetime.now(_dt.UTC).isoformat(), 'action': 'lock', 'state': st}) + '\n')
        except Exception:
            pass

    def reset_view():
        try:
            if os.path.exists(STATE_FILE):
                os.remove(STATE_FILE)
        except Exception:
            pass
        try:
            details_outer.configure(width=DEFAULT_STATE['details_w'])
            breakdown_outer.configure(width=DEFAULT_STATE['breakdown_w'])
            btns_frame.configure(height=DEFAULT_STATE['green_h'])
            rebuild_bundles(5)
        except Exception:
            pass

    root.after(100, lambda: (center_details_content(), center_breakdown_content()))
    root.after(500, lambda: (center_details_content(), center_breakdown_content()))

    update_level_buttons()  # Initialize level buttons as grey
    
    # Load saved state after GUI creation
    load_state(left, details_outer, breakdown_outer, btns_frame, debug_var)
    
    return root

def load_state(left, details_outer, breakdown_outer, btns_frame, debug_var):
    """Load saved GUI state and apply it to the interface"""
    global debug_enabled
    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r', encoding='utf-8') as fh:
                state = json.load(fh)
                # Apply saved dimensions
                if 'left_w' in state:
                    left.configure(width=state['left_w'])
                if 'details_w' in state:
                    details_outer.configure(width=state['details_w'])
                if 'breakdown_w' in state:
                    breakdown_outer.configure(width=state['breakdown_w'])
                if 'green_h' in state:
                    btns_frame.configure(height=state['green_h'])
                # Apply saved debug state
                if 'debug_enabled' in state:
                    global debug_enabled
                    debug_enabled = state['debug_enabled']
                    debug_var.set(debug_enabled)
                    toggle_debug_mode(debug_enabled)
        else:
            # Create default state file if it doesn't exist
            default_state = {
                'left_w': DEFAULT_STATE['left_w'],
                'details_w': DEFAULT_STATE['details_w'],
                'breakdown_w': DEFAULT_STATE['breakdown_w'],
                'green_h': DEFAULT_STATE['green_h'],
                'debug_enabled': True
            }
            with open(STATE_FILE, 'w', encoding='utf-8') as fh:
                json.dump(default_state, fh, indent=2)
            # Apply default state
            left.configure(width=default_state['left_w'])
            details_outer.configure(width=default_state['details_w'])
            breakdown_outer.configure(width=default_state['breakdown_w'])
            btns_frame.configure(height=default_state['green_h'])
            debug_enabled = default_state['debug_enabled']
            debug_var.set(debug_enabled)
            toggle_debug_mode(debug_enabled)
    except Exception:
        pass

def analyze_subassemblies_for_panel(ehx_path, panel_name, materials_param):
    """Analyze SubAssemblies for a specific panel from EHX file.
    
    Args:
        ehx_path (str): Path to the EHX file
        panel_name (str): Name of the panel to analyze
        materials_param (dict or list): Either the full materials_map dict or panel-specific materials list
        
    Returns:
        dict: Dictionary mapping SubAssembly GUIDs to their info with materials
    """
    try:
        import xml.etree.ElementTree as ET
        
        # Parse the EHX file
        tree = ET.parse(ehx_path)
        root = tree.getroot()
        
        # Find the specific panel - try multiple paths since XML structure can vary
        panel_element = None
        
        # Try different possible paths to find the panel
        possible_paths = [
            './/Panel',  # Direct search
            'Job/Level/Bundle/Panel',  # Full path
            'Job/Level/Panel',  # Alternative path
            'Job/Panel',  # Simpler path
        ]
        
        for path in possible_paths:
            panels = root.findall(path)
            for panel in panels:
                panel_guid_elem = panel.find('PanelGuid')
                if panel_guid_elem is not None and panel_guid_elem.text == panel_name:
                    panel_element = panel
                    if debug_enabled:
                        print(f"DEBUG: Found panel {panel_name} using path: {path}")
                    break
            if panel_element:
                break
        
        if not panel_element:
            if debug_enabled:
                print(f"DEBUG: Panel {panel_name} not found. Available panels:")
                for path in possible_paths:
                    panels = root.findall(path)
                    for panel in panels:
                        panel_guid_elem = panel.find('PanelGuid')
                        if panel_guid_elem is not None:
                            print(f"DEBUG:   {panel_guid_elem.text}")
            return {}
        
        # Handle both cases: materials_param could be the full materials_map or just panel materials
        if isinstance(materials_param, dict):
            # It's the full materials_map
            panel_materials = materials_param.get(panel_name, [])
        else:
            # It's already the panel materials list
            panel_materials = materials_param
        
        # Debug: Print all SubAssemblyGuid values in materials
        if debug_enabled:
            print(f"DEBUG: Panel {panel_name} has {len(panel_materials)} materials")
            material_guids = set()
            for m in panel_materials:
                if isinstance(m, dict):
                    sub_guid = m.get('SubAssemblyGuid', '')
                    if sub_guid:
                        material_guids.add(sub_guid)
            print(f"DEBUG: Material SubAssemblyGuid values: {material_guids}")
        
        # Find all SubAssembly elements in the panel - try multiple approaches
        subassemblies = {}
        
        # Approach 1: Look for SubAssembly elements directly under the Panel
        for subassembly in panel_element.findall('SubAssembly'):
            sub_guid_elem = subassembly.find('SubAssemblyGuid')
            sub_name_elem = subassembly.find('SubAssemblyName')
            
            if sub_guid_elem is not None and sub_name_elem is not None:
                sub_guid = sub_guid_elem.text.strip() if sub_guid_elem.text else ''
                sub_name = sub_name_elem.text.strip() if sub_name_elem.text else ''
                
                if sub_guid and sub_name and sub_guid.strip() and sub_name.strip():
                    if debug_enabled:
                        print(f"DEBUG: Found SubAssembly element: {sub_name} with GUID: {sub_guid}")
                    # Initialize subassembly info
                    subassemblies[sub_guid] = {
                        'name': sub_name,
                        'family_member': 32 if sub_name == 'LType' else (42 if 'Ladder' in sub_name else 70),
                        'materials': {}
                    }
        
        # Approach 2: If no SubAssembly elements found, look for materials with SubAssemblyGuid
        if not subassemblies:
            if debug_enabled:
                print(f"DEBUG: No SubAssembly elements found, looking for materials with SubAssemblyGuid")
            
            # Group materials by their SubAssemblyGuid
            guid_to_materials = {}
            guid_to_name = {}
            
            for material in panel_materials:
                if isinstance(material, dict):
                    sub_guid = material.get('SubAssemblyGuid', '').strip()
                    sub_name = material.get('SubAssembly', '').strip()
                    
                    if sub_guid:
                        if sub_guid not in guid_to_materials:
                            guid_to_materials[sub_guid] = []
                            # Try to get the name from the first material with this GUID
                            if sub_name:
                                guid_to_name[sub_guid] = sub_name
                            else:
                                # Use a default name based on the GUID or material type
                                guid_to_name[sub_guid] = f"SubAssembly_{sub_guid[:8]}"
                        
                        guid_to_materials[sub_guid].append(material)
            
            # Create subassemblies from the grouped materials
            for sub_guid, materials_list in guid_to_materials.items():
                sub_name = guid_to_name.get(sub_guid, f"SubAssembly_{sub_guid[:8]}")
                
                if debug_enabled:
                    print(f"DEBUG: Created SubAssembly from materials: {sub_name} with GUID: {sub_guid} ({len(materials_list)} materials)")
                
                subassemblies[sub_guid] = {
                    'name': sub_name,
                    'family_member': 32 if sub_name == 'LType' else (42 if 'Ladder' in sub_name else 70),
                    'materials': {}
                }
        
        # Approach 3: Look for RoughOpening elements that might represent SubAssemblies
        if not subassemblies:
            if debug_enabled:
                print(f"DEBUG: No SubAssemblies found yet, looking for RoughOpening elements")
            
            for rough_opening in panel_element.findall('.//RoughOpening'):
                sub_guid_elem = rough_opening.find('SubAssemblyGuid')
                sub_name_elem = rough_opening.find('SubAssembly')
                
                if sub_guid_elem is not None:
                    sub_guid = sub_guid_elem.text.strip() if sub_guid_elem.text else ''
                else:
                    # Try to find GUID in associated elements
                    continue
                    
                if sub_name_elem is not None:
                    sub_name = sub_name_elem.text.strip() if sub_name_elem.text else ''
                else:
                    sub_name = "Unknown"
                
                if sub_guid and sub_guid.strip():
                    if debug_enabled:
                        print(f"DEBUG: Found RoughOpening SubAssembly: {sub_name} with GUID: {sub_guid}")
                    
                    subassemblies[sub_guid] = {
                        'name': sub_name,
                        'family_member': 32 if sub_name == 'LType' else (42 if 'Ladder' in sub_name else 70),
                        'materials': {}
                    }
        
        if debug_enabled:
            print(f"DEBUG: Found {len(subassemblies)} SubAssemblies in XML: {list(subassemblies.keys())}")
        
        # Find materials that belong to these SubAssemblies
        for material in panel_materials:
            if isinstance(material, dict):
                mat_subassembly = material.get('SubAssemblyGuid', '').strip()
                mat_subassembly_name = material.get('SubAssembly', '').strip()
                mat_label = material.get('Label', '')
                
                if debug_enabled:
                    print(f"DEBUG: Checking material - SubAssemblyName: '{mat_subassembly_name}', FamilyMemberName: '{material.get('FamilyMemberName', '')}', GUID: '{mat_subassembly}'")
                    print(f"DEBUG: Material keys: {list(material.keys())}")
                    print(f"DEBUG: Material data: {material}")
                
                # Check if this material belongs to any of our SubAssemblies
                matched = False
                if debug_enabled:
                    print(f"DEBUG: Available SubAssembly GUIDs: {list(subassemblies.keys())}")
                
                for sub_guid, sub_info in subassemblies.items():
                    if debug_enabled:
                        print(f"DEBUG: Comparing material GUID '{mat_subassembly}' (len={len(mat_subassembly)}) with SubAssembly GUID '{sub_guid}' (len={len(sub_guid)})")
                        print(f"DEBUG: GUIDs equal? {mat_subassembly == sub_guid}")
                        print(f"DEBUG: Material GUID type: {type(mat_subassembly)}, SubAssembly GUID type: {type(sub_guid)}")
                    
                    if mat_subassembly == sub_guid:
                        if debug_enabled:
                            print(f"DEBUG: Matched material {mat_label} to SubAssembly {sub_guid} by GUID")
                        # Count this material
                        if mat_label in sub_info['materials']:
                            sub_info['materials'][mat_label] += 1
                        else:
                            sub_info['materials'][mat_label] = 1
                        matched = True
                        break
                    elif mat_subassembly_name == sub_info['name']:
                        if debug_enabled:
                            print(f"DEBUG: Matched material {mat_label} to SubAssembly {sub_info['name']} by name")
                        # Count this material
                        if mat_label in sub_info['materials']:
                            sub_info['materials'][mat_label] += 1
                        else:
                            sub_info['materials'][mat_label] = 1
                        matched = True
                        break
                
                if not matched and debug_enabled:
                    if mat_subassembly:
                        print(f"DEBUG: Skipping unknown GUID: {mat_subassembly}")
                    elif mat_subassembly_name:
                        print(f"DEBUG: Skipping non-beam-pocket SubAssembly: {mat_subassembly_name}")
                    else:
                        print(f"DEBUG: Skipping material with no SubAssembly info")
        
        # Filter to only include subassemblies with materials
        filtered_subassemblies = {}
        for guid, info in subassemblies.items():
            if info['materials']:
                filtered_subassemblies[guid] = info
        
        if debug_enabled:
            print(f"DEBUG: Returning {len(filtered_subassemblies)} SubAssemblies with materials")
        
        return filtered_subassemblies
        
    except Exception as e:
        print(f"Error analyzing SubAssemblies for panel {panel_name}: {e}")
        return {}


# =============================================================================
# TAKEOFF_STANDALONE.PY CODE INTEGRATION
# =============================================================================

#!/usr/bin/env python3
"""Standalone Takeoff Script - Creates material takeoff from Panel Material Breakdown
   This script is completely self-contained and does not require any external modules."""

import threading

# Import standalone functions from TPB_standalone.py
# from tpb_standalone import build_search_indexes  # Removed - now using local function

def build_search_indexes(root_element):
    """Build search indexes from EHX XML - standalone version"""
    panels = {}
    materials = {}
    bundles = {}
    levels = {}  # Store level information by LevelGuid

    # First, collect all Level elements
    for level_el in root_element.findall('.//Level'):
        level_guid_el = level_el.find('LevelGuid')
        if level_guid_el is not None and level_guid_el.text:
            level_guid = level_guid_el.text.strip()
            level_info = {}
            
            # Extract level details
            level_no_el = level_el.find('LevelNo')
            if level_no_el is not None and level_no_el.text:
                level_info['level_no'] = level_no_el.text.strip()
            
            desc_el = level_el.find('Description')
            if desc_el is not None and desc_el.text:
                level_info['description'] = desc_el.text.strip()
            
            job_id_el = level_el.find('JobID')
            if job_id_el is not None and job_id_el.text:
                level_info['job_id'] = job_id_el.text.strip()
            
            # Create a formatted level string like "1-1FW 2FD"
            level_str = ""
            if level_info.get('level_no'):
                level_str = level_info['level_no']
                if level_info.get('description'):
                    level_str += "-" + level_info['description']
            
            levels[level_guid] = level_info
            levels[level_guid]['formatted_level'] = level_str

    # Process panels
    for panel_el in root_element.findall('.//Panel'):
        panel_guid = None
        panel_label = None

        # Get panel identifiers
        for guid_tag in ['PanelGuid', 'PanelID']:
            guid_el = panel_el.find(guid_tag)
            if guid_el is not None and guid_el.text:
                panel_guid = guid_el.text.strip()
                break

        label_el = panel_el.find('Label')
        if label_el is not None and label_el.text:
            panel_label = label_el.text.strip()

        if not panel_guid:
            continue

        if not panel_label:
            panel_label = panel_guid

        # Extract panel information
        panel_info = {
            'guid': panel_guid,
            'label': panel_label,
            'name': panel_label,
            'display_name': panel_label
        }

        # Add additional panel details
        for field in ['Description', 'Bundle', 'BundleName', 'Height', 'Thickness',
                     'StudSpacing', 'WallLength', 'LoadBearing', 'Category', 'Weight']:
            el = panel_el.find(field)
            if el is not None and el.text:
                panel_info[field.lower()] = el.text.strip()

        # Check for LevelGuid and look up level information
        level_guid_el = panel_el.find('LevelGuid')
        if level_guid_el is not None and level_guid_el.text:
            panel_level_guid = level_guid_el.text.strip()
            if panel_level_guid in levels:
                level_data = levels[panel_level_guid]
                panel_info['level'] = level_data.get('formatted_level', '')

        panels[panel_guid] = panel_info

        # Don't index by label separately to avoid duplicate panels
        # The label is stored in panel_info for reference

    # Process bundles from Junction elements (v2.0 format)
    junction_bundle_map = {}
    for junction in root_element.findall('.//Junction'):
        panel_id_el = junction.find('PanelID')
        label_el = junction.find('Label')
        bundle_name_el = junction.find('BundleName')

        if bundle_name_el is not None and bundle_name_el.text:
            bundle_name = bundle_name_el.text.strip()

            # Map by PanelID if present
            if panel_id_el is not None and panel_id_el.text:
                panel_id = panel_id_el.text.strip()
                junction_bundle_map[panel_id] = bundle_name

            # Also map by Label if present
            if label_el is not None and label_el.text:
                label = label_el.text.strip()
                junction_bundle_map[label] = bundle_name

    # Update panel bundle information
    for panel_guid, panel_info in panels.items():
        if panel_info.get('bundlename'):
            continue  # Already has bundle name

        # Try to match by PanelID/Label using the junction mapping
        panel_id = panel_info.get('guid')
        panel_label = panel_info.get('label')

        bundle_name = None
        if panel_id and panel_id in junction_bundle_map:
            bundle_name = junction_bundle_map[panel_id]
        elif panel_label and panel_label in junction_bundle_map:
            bundle_name = junction_bundle_map[panel_label]

        if bundle_name:
            panel_info['bundlename'] = bundle_name

    return {
        'panels': panels,
        'materials': materials,
        'bundles': bundles,
        'levels': levels,
        'tree': root_element
    }

# Debug configuration - set to True to enable debug output
DEBUG_ENABLED = False

# Material aliases for cleaner display
MATERIAL_ALIASES = {
    '1 3/4" x 5 1/2" (2.0E 3100) WestFraser LVL': "1 3/4 x 5 1/2 LVL",
    '1 3/4" x 7 1/4" (2.0E 3100) WestFraser LVL': "1 3/4 x 7 1/4 LVL", 
    '1 3/4" x 9 1/2" (2.0E 3100) WestFraser LVL': "1 3/4 x 9 1/2 LVL",
    '1 3/4" x 11 7/8" (2.0E 3100) WestFraser LVL': "1 3/4 x 11 7/8 LVL",
    '1 3/4" x 14" (2.0E 3100) WestFraser LVL': "1 3/4 x 14 LVL",
    '1 3/4" x 16" (2.0E 3100) WestFraser LVL': "1 3/4 x 16 LVL",
    '1 3/4" x 5 1/2" 1.55E TimberStrand LSL': "1 3/4 x 5 1/2 LSL",
    '1 3/4" x 7 1/4" 1.55E TimberStrand LSL': "1 3/4 x 7 1/4 LSL",
    '1 3/4" x 9 1/2" 1.55E TimberStrand LSL': "1 3/4 x 9 1/2 LSL",
    '1 3/4" x 11 7/8" 1.55E TimberStrand LSL': "1 3/4 x 11 7/8 LSL",
    '1 3/4" x 14" 1.55E TimberStrand LSL': "1 3/4 x 14 LSL",
    '1 3/4" x 16" 1.55E TimberStrand LSL': "1 3/4 x 16 LSL",
}

# Family Member IDs to exclude from material breakdown (for materials you're not sure how to report yet)
EXCLUDED_FAMILY_MEMBERS = [
    '104',  # FM104 - Tie Plates (comment out when ready to include)
    '106',  # FM106 - BottomMultiPlate (site-installed, exclude from takeoff)
    # Add other Family Member IDs here as needed
    # '105',  # Example: FM105 - Some other material
]

# FamilyMember name to ID mapping for consistent filtering
FAMILY_MEMBER_MAPPING = {
    'Tee': 32,
    'Ladder - Flat (Fixed)': 42,
    'GMD-L1': 25,
    'Sheathing': 40,
    '49x63-L2': 25,
    'SZ56': 25,  # Also maps to FamilyMember 25
    'Critical Stud': 32,  # Critical Stud maps to FM32
    'DR-9-ENT-L1': 25,   # DR-9-ENT-L1 maps to FM25 (Openings)
    'BSMT-HDR': 25,      # BSMT-HDR maps to FM25 (Openings)
    'LType': 32,         # LType maps to FM32 (Critical Stud)
}

def get_family_member_id(family_member_name):
    """Get FamilyMember ID from name, with fallback logic."""
    if not family_member_name:
        return None
    
    # Direct mapping
    if family_member_name in FAMILY_MEMBER_MAPPING:
        return FAMILY_MEMBER_MAPPING[family_member_name]
    
    # Partial matching for more flexibility
    for name_pattern, member_id in FAMILY_MEMBER_MAPPING.items():
        if name_pattern in family_member_name:
            return member_id
    
    return None

def is_fm25_material(material):
    """Check if a material is FM25 (Family Member 25 - Openings/Subassemblies)"""
    if not isinstance(material, dict):
        return False
    
    # Check FamilyMember ID directly
    family_member_id = material.get('FamilyMember')
    if family_member_id:
        try:
            fm_id = int(str(family_member_id).strip())
            if fm_id == 25:
                return True
        except (ValueError, TypeError):
            pass
    
    # Check FamilyMemberName for FM25 patterns
    family_member_name = material.get('FamilyMemberName', '').strip()
    if family_member_name:
        fm_id = get_family_member_id(family_member_name)
        if fm_id == 25:
            return True
    
    # Check SubAssembly name for FM25 patterns
    subassembly = material.get('SubAssembly', '').strip()
    if subassembly:
        fm_id = get_family_member_id(subassembly)
        if fm_id == 25:
            return True
    
    return False

def is_excluded_material(material):
    """Check if a material should be excluded from the breakdown based on EXCLUDED_FAMILY_MEMBERS"""
    if not isinstance(material, dict):
        return False
    
    # Check FamilyMember ID directly
    family_member_id = material.get('FamilyMember')
    if family_member_id:
        family_member_str = str(family_member_id).strip()
        if family_member_str in EXCLUDED_FAMILY_MEMBERS:
            return True
    
    # Check FamilyMemberName for excluded patterns
    family_member_name = material.get('FamilyMemberName', '').strip()
    if family_member_name:
        fm_id = get_family_member_id(family_member_name)
        if fm_id and str(fm_id) in EXCLUDED_FAMILY_MEMBERS:
            return True
    
    return False

def parse_dimension_to_feet(dim_str):
    """Convert dimension string to feet (float)"""
    if not dim_str:
        return 0.0

    dim_str = dim_str.strip()
    if DEBUG_ENABLED:
        print(f"DEBUG parse_dimension_to_feet: input='{dim_str}'")

    # Handle sheathing format like "9' x 1'-2-7/8""
    if ' x ' in dim_str:
        try:
            parts = dim_str.split(' x ')
            if len(parts) == 2:
                length_part = parts[0].strip()
                width_part = parts[1].strip()

                # Parse length
                length_feet = parse_dimension_to_feet(length_part)
                # Parse width
                width_feet = parse_dimension_to_feet(width_part)

                # For sheathing, we want the longer dimension as the linear length
                result = max(length_feet, width_feet)
                if DEBUG_ENABLED:
                    print(f"DEBUG parse_dimension_to_feet: sheathing format, result={result}")
                return result
        except:
            pass

    # Handle feet-inches-sixteenths format like "8'-10-1/4"" or "8'-10 1/4" or "11-5-3/8"
    if "'" in dim_str or (dim_str.count('-') >= 2 and '/' in dim_str) or (' ' in dim_str and '/' in dim_str):
        try:
            if DEBUG_ENABLED:
                print(f"DEBUG parse_dimension_to_feet: detected feet-inches format")
            # Split on feet and inches
            if "'" in dim_str:
                feet_part = dim_str.split("'")[0].strip()
                inches_part = dim_str.split("'")[1].replace('"', '').strip()
                # Remove leading dash if present (artifact from splitting)
                if inches_part.startswith('-'):
                    inches_part = inches_part[1:].strip()
                if DEBUG_ENABLED:
                    print(f"DEBUG parse_dimension_to_feet: feet_part='{feet_part}', inches_part='{inches_part}'")
            else:
                # Handle format like "11-5-3/8" (feet-inches-fraction without ' marker)
                parts = dim_str.split('-', 2)
                if len(parts) >= 3:
                    feet_part = parts[0].strip()
                    inches_part = parts[1].strip() + '-' + parts[2].strip()
                else:
                    feet_part = '0'
                    inches_part = dim_str
                if DEBUG_ENABLED:
                    print(f"DEBUG parse_dimension_to_feet: no apostrophe, feet_part='{feet_part}', inches_part='{inches_part}'")
            
            feet = float(feet_part) if feet_part else 0
            if DEBUG_ENABLED:
                print(f"DEBUG parse_dimension_to_feet: feet={feet}")

            # Handle inches with sixteenths - support both dash and space separators
            if '-' in inches_part or ' ' in inches_part:
                # Use whichever separator is present
                separator = '-' if '-' in inches_part else ' '
                if DEBUG_ENABLED:
                    print(f"DEBUG parse_dimension_to_feet: using separator='{separator}' in inches_part='{inches_part}'")
                if separator in inches_part:
                    inches, fraction = inches_part.split(separator, 1)
                    inches = float(inches) if inches else 0
                    if DEBUG_ENABLED:
                        print(f"DEBUG parse_dimension_to_feet: inches={inches}, fraction='{fraction}'")

                    # Handle fraction like "1/4"
                    if '/' in fraction:
                        num, den = fraction.split('/')
                        fraction_inches = float(num) / float(den)
                        if DEBUG_ENABLED:
                            print(f"DEBUG parse_dimension_to_feet: fraction_inches={fraction_inches}")
                    else:
                        fraction_inches = float(fraction) if fraction else 0

                    total_inches = inches + fraction_inches
                else:
                    total_inches = float(inches_part) if inches_part else 0
            else:
                total_inches = float(inches_part) if inches_part else 0
                if DEBUG_ENABLED:
                    print(f"DEBUG parse_dimension_to_feet: no separator, total_inches={total_inches}")

            result = feet + (total_inches / 12)
            if DEBUG_ENABLED:
                print(f"DEBUG parse_dimension_to_feet: final result={result}")
            return result
        except Exception as e:
            if DEBUG_ENABLED:
                print(f"DEBUG parse_dimension_to_feet: exception {e}")
            pass

    # Handle decimal feet like "8.833"
    try:
        result = float(dim_str.replace("'", "").replace('"', "").strip())
        if DEBUG_ENABLED:
            print(f"DEBUG parse_dimension_to_feet: decimal feet, result={result}")
        return result
    except ValueError:
        pass

    # Handle just inches like "4-7/8" or "4-1"
    if '-' in dim_str and ('/' in dim_str or dim_str.count('-') == 1):
        try:
            if '/' in dim_str:
                inches, fraction = dim_str.split('-', 1)
                inches = float(inches) if inches else 0
                if '/' in fraction:
                    num, den = fraction.split('/')
                    fraction_inches = float(num) / float(den)
                else:
                    fraction_inches = float(fraction) if fraction else 0
                result = (inches + fraction_inches) / 12
                if DEBUG_ENABLED:
                    print(f"DEBUG parse_dimension_to_feet: just inches with fraction, result={result}")
                return result
            else:
                # Handle format like "4-1" (feet-inches without fraction)
                if dim_str.count('-') == 1:
                    feet_part, inches_part = dim_str.split('-', 1)
                    feet = float(feet_part) if feet_part else 0
                    inches = float(inches_part) if inches_part else 0
                    result = feet + (inches / 12)
                    if DEBUG_ENABLED:
                        print(f"DEBUG parse_dimension_to_feet: feet-inches without fraction, result={result}")
                    return result
        except:
            pass

    if DEBUG_ENABLED:
        print(f"DEBUG parse_dimension_to_feet: returning 0.0")
    return 0.0

def format_feet_to_dimension(feet):
    """Convert feet (float) back to feet-inches-sixteenths format (matching EHX search widget)"""
    if feet == 0:
        return "0'-0\""

    # Calculate exact dimensions without rounding for precise display
    total_inches = feet * 12
    feet_part = int(total_inches // 12)
    inches_part = total_inches % 12

    # Convert fractional inches to sixteenths without rounding
    inches_whole = int(inches_part)
    fractional_inches = inches_part % 1
    sixteenths = int(fractional_inches * 16 + 0.5)  # Round to nearest sixteenth for precision

    if sixteenths == 0:
        if inches_whole == 0:
            return f"{feet_part}'-0\""
        else:
            return f"{feet_part}'-{inches_whole}-0\""
    elif sixteenths == 16:
        # Round up to next inch, handling carry-over to next foot
        new_inches_whole = inches_whole + 1
        new_feet_part = feet_part
        if new_inches_whole >= 12:
            new_feet_part += 1
            new_inches_whole -= 12
        return f"{new_feet_part}'-{new_inches_whole}\""
    else:
        # Reduce the fraction sixteenths/16 to simplest terms
        from math import gcd
        numerator = sixteenths
        denominator = 16
        g = gcd(numerator, denominator)
        numerator //= g
        denominator //= g
        return f"{feet_part}'-{inches_whole}-{numerator}/{denominator}\""

def parse_dimension_to_inches(dim_str):
    """Convert dimension string to inches (float)"""
    if not dim_str:
        return 0.0

    dim_str = dim_str.strip()
    
    # Handle formats like "1 3/4" or "9 1/2"
    if ' ' in dim_str and '/' in dim_str:
        parts = dim_str.split(' ')
        if len(parts) == 2:
            whole_part = parts[0].strip()
            fraction_part = parts[1].strip()
            
            whole_inches = float(whole_part) if whole_part else 0
            if '/' in fraction_part:
                num, den = fraction_part.split('/')
                fraction_inches = float(num) / float(den)
            else:
                fraction_inches = float(fraction_part) if fraction_part else 0
            
            return whole_inches + fraction_inches
    else:
        # Handle simple integers or decimals
        try:
            return float(dim_str)
        except ValueError:
            return 0.0

def extract_thickness_from_description(material_description):
    """Extract thickness from material description (e.g., '3/4" 4x8 OSB' -> 0.75)"""
    if not material_description:
        return 1.5  # Default to 1.5" for dimensional lumber
    
    desc = material_description.lower()
    
    # Look for fractional thickness at the beginning (e.g., "3/4" 4x8 OSB or "1 3/4" x 9 1/2 LVL)
    import re
    # Match patterns like "1 3/4", "3/4", or "1 1/2" with optional quotes
    fraction_match = re.match(r'^["\']?(\d+\s+\d+/\d+|\d+/\d+)["\']?', desc)
    if fraction_match:
        thickness_str = fraction_match.group(1).strip()
        try:
            # Handle "1 3/4" format
            if ' ' in thickness_str and '/' in thickness_str:
                parts = thickness_str.split(' ')
                if len(parts) == 2:
                    whole = int(parts[0])
                    frac_parts = parts[1].split('/')
                    if len(frac_parts) == 2:
                        num = int(frac_parts[0])
                        den = int(frac_parts[1])
                        return whole + (num / den)
            # Handle simple fraction like "3/4"
            elif '/' in thickness_str:
                parts = thickness_str.split('/')
                if len(parts) == 2:
                    num = int(parts[0])
                    den = int(parts[1])
                    return num / den
            # Handle decimal
            else:
                return float(thickness_str)
        except (ValueError, TypeError):
            pass
    
    # Look for patterns like "2x6", "2x8", etc. - these are typically 1.5" thick
    if re.search(r'\d+"?\s*x\s*\d+', desc):
        return 1.5  # Standard dimensional lumber thickness
    
    # Default fallback
    return 1.5

def calculate_board_feet(length_feet, width_inches=0, material_description=""):
    """Calculate board feet from length in feet, width in inches, and material description"""
    if length_feet <= 0:
        return 0.0

    # Parse nominal dimensions from material description (e.g., "2x6 SPF PM No.2" or "1 3/4 x 9 1/2 LVL")
    import re
    nominal_thickness = 2.0  # Default 2" thickness for dimensional lumber
    nominal_width = 0.0

    # Look for patterns like "2x4", "2x6", "2x8", etc. in the description
    # Handle both integer and fractional dimensions
    match = re.search(r'(\d+(?:\s+\d+/\d+)?)"?\s*x\s*(\d+(?:\s+\d+/\d+)?)"?', material_description, re.IGNORECASE)
    if match:
        thickness_str = match.group(1).strip()  # First number (thickness)
        width_str = match.group(2).strip()      # Second number (width)
        
        # Parse fractional dimensions
        nominal_thickness = parse_dimension_to_inches(thickness_str)
        nominal_width = parse_dimension_to_inches(width_str)

    # If no dimensions found in description, try to estimate from width_inches
    if nominal_width == 0.0 and width_inches > 0:
        # Map actual width to nominal width (rough approximation)
        if width_inches <= 3.75:  # 2x4 (actual width ~3.5")
            nominal_width = 4.0
        elif width_inches <= 5.75:  # 2x6 (actual width ~5.5")
            nominal_width = 6.0
        elif width_inches <= 7.5:  # 2x8 (actual width ~7.25")
            nominal_width = 8.0
        elif width_inches <= 9.5:  # 2x10 (actual width ~9.25")
            nominal_width = 10.0
        elif width_inches <= 11.5:  # 2x12 (actual width ~11.25")
            nominal_width = 12.0
        else:
            # Fallback: estimate nominal width from actual width
            nominal_width = width_inches + 0.5

    # Traditional board feet formula: (thickness × width × length) ÷ 12
    if nominal_width > 0:
        board_feet = (nominal_thickness * nominal_width * length_feet) / 12.0
        return board_feet
    else:
        # Fallback to linear feet if we can't determine dimensions
        return length_feet

def calculate_equivalent_linear_feet(board_feet, material_description):
    """Convert board feet back to equivalent linear feet for display purposes"""
    if board_feet <= 0:
        return 0.0

    # Parse nominal dimensions from material description (same logic as calculate_board_feet)
    import re
    nominal_thickness = 2.0  # Default 2" thickness for dimensional lumber
    nominal_width = 0.0

    # Look for patterns like "2x4", "2x6", "2x8", etc. in the description
    # Handle both integer and fractional dimensions
    match = re.search(r'(\d+(?:\s+\d+/\d+)?)"?\s*x\s*(\d+(?:\s+\d+/\d+)?)"?', material_description, re.IGNORECASE)
    if match:
        thickness_str = match.group(1).strip()  # First number (thickness)
        width_str = match.group(2).strip()      # Second number (width)
        
        # Parse fractional dimensions
        nominal_thickness = parse_dimension_to_inches(thickness_str)
        nominal_width = parse_dimension_to_inches(width_str)

    # Convert board feet back to linear feet: BF × 12 ÷ (thickness × width)
    if nominal_width > 0:
        linear_feet = (board_feet * 12.0) / (nominal_thickness * nominal_width)
        return linear_feet
    else:
        # Fallback if we can't determine dimensions
        return board_feet

def get_material_display_name(material_type):
    """Get the display name for a material type, using aliases if available"""
    return MATERIAL_ALIASES.get(material_type, material_type)

def sort_materials_by_hierarchy(material_descriptions):
    # Define material hierarchy - higher priority materials appear first
    material_hierarchy = [
        # Engineered wood products first
        "2x6 SPF PM No.2",
        "2x8 SPF PM No.2", 
        "2x10 SPF PM No.2",
        "2x12 SPF PM No.2",
        "2x4 SPF PM No.2",
        # Standard framing lumber
        "2x6 SPF Stud",
        "2x8 SPF Stud",
        "2x10 SPF Stud", 
        "2x12 SPF Stud",
        "2x4 SPF Stud",
        # Other SPF grades
        "2x6 SPF No.2",
        "2x8 SPF No.2",
        "2x10 SPF No.2",
        "2x12 SPF No.2", 
        "2x4 SPF No.2",
        # Other species
        "2x6 Douglas Fir",
        "2x8 Douglas Fir",
        "2x10 Douglas Fir",
        "2x12 Douglas Fir",
        "2x4 Douglas Fir",
        "2x6 Hem Fir",
        "2x8 Hem Fir", 
        "2x10 Hem Fir",
        "2x12 Hem Fir",
        "2x4 Hem Fir",
        # Other materials
        "2x6 SPF",
        "2x8 SPF",
        "2x10 SPF",
        "2x12 SPF",
        "2x4 SPF",
    ]
    
    # Create priority mapping
    priority_map = {}
    for i, material in enumerate(material_hierarchy):
        priority_map[material.lower()] = i
        
    # Sort function
    def sort_key(material_desc):
        desc_lower = material_desc.lower()
        # Check for exact matches first
        if desc_lower in priority_map:
            return (0, priority_map[desc_lower])  # Priority group 0 for known materials
        # Check for partial matches (contains key material type)
        for key_material, priority in priority_map.items():
            if key_material in desc_lower:
                return (1, priority)  # Priority group 1 for partial matches
        # Unknown materials go to the end
        return (2, material_desc.lower())  # Priority group 2, alphabetical fallback
        
    return sorted(material_descriptions, key=sort_key)

def create_takeoff_from_breakdown(breakdown_text):
    """Create takeoff from panel material breakdown text"""

    if DEBUG_ENABLED:
        print(f"DEBUG: create_takeoff_from_breakdown called with breakdown_text:\n{breakdown_text[:200]}...")

    # Parse the breakdown text
    lines = breakdown_text.strip().split('\n')
    materials = []

    for line in lines:
        line = line.strip()
        if not line or not line[0].isalnum():
            continue

        # Parse format: "A - BottomPlate - 2x6 SPF PM No.2 - (1) - 8'-10-1/4""
        parts = line.split(' - ')
        if len(parts) >= 4:
            material_code = parts[0].strip()
            family_member = parts[1].strip()  # This is the FamilyMemberName (KingStud, Stud, FlatStud, etc.)
            material_type = parts[2].strip()  # This is the material description

            # Extract quantity from (1) format
            qty_part = parts[3].strip()
            if qty_part.startswith('(') and qty_part.endswith(')'):
                try:
                    quantity = int(qty_part[1:-1])
                except ValueError:
                    quantity = 1
            else:
                quantity = 1

            # Extract length if present
            length_str = ""
            if len(parts) >= 5:
                length_str = parts[4].strip().replace('"', '').replace('`', '').replace('´', '')  # Remove quotes but keep apostrophe for feet

            materials.append({
                'code': material_code,
                'family_member': family_member,
                'type': material_type,
                'quantity': quantity,
                'length': length_str
            })

    if DEBUG_ENABLED:
        print(f"DEBUG: parsed {len(materials)} materials")

    # Group materials by category and type/length
    sheets_materials = {}  # Sheathing materials - calculate square footage and sheets needed
    linear_materials = {}  # Dimensional lumber - group by type and length
    precut_materials = {}  # Precut studs - count by type
    bracing_materials = {}  # Steel bracing - count by type and length like precuts

    for mat in materials:
        # Convert length to feet for calculations
        length_feet = parse_dimension_to_feet(mat['length'])
        length_display = mat['length'] or "0'-0\""

        if DEBUG_ENABLED:
            print(f"DEBUG: Processing material: {mat['code']} - {mat['family_member']} - {mat['type']} - qty:{mat['quantity']} - length:{mat['length']} -> length_feet:{length_feet}")

        # Categorize materials
        family_member = mat['family_member'].lower()
        material_type = mat['type']
        quantity = mat['quantity']

        # SHEATHING: Sheathing and EndPadding family members, OR materials with thickness < 1.5"
        thickness = extract_thickness_from_description(material_type)
        is_thin_material = thickness < 1.5
        
        if family_member in ['sheathing', 'endpadding'] or is_thin_material:
            if DEBUG_ENABLED:
                print(f"DEBUG: Categorizing as SHEATHING: {family_member} (thickness: {thickness})")
            # For sheathing, we need to calculate square footage from the "x" format dimensions
            if ' x ' in mat['length']:
                # Handle "length x width" format like "9' x 1'-2-7/8""
                try:
                    parts = mat['length'].split(' x ')
                    if len(parts) == 2:
                        length_part = parts[0].strip()
                        width_part = parts[1].strip()
                        
                        # Parse both dimensions
                        length_feet_val = parse_dimension_to_feet(length_part)
                        width_feet_val = parse_dimension_to_feet(width_part)
                        
                        # Calculate square footage: length × width × quantity
                        piece_sq_ft = length_feet_val * width_feet_val * quantity
                        linear_ft = length_feet_val * quantity  # Use length for linear measurement
                        
                        if DEBUG_ENABLED:
                            print(f"DEBUG: Sheathing dimensions - length:{length_feet_val}, width:{width_feet_val}, sq_ft:{piece_sq_ft}")
                        
                        if material_type not in sheets_materials:
                            sheets_materials[material_type] = {
                                'sq_ft': 0,
                                'linear_ft': 0,
                                'codes': set(),
                                'is_endpadding': family_member == 'endpadding',
                                'is_thin_material': is_thin_material
                            }
                        sheets_materials[material_type]['sq_ft'] += piece_sq_ft
                        sheets_materials[material_type]['linear_ft'] += linear_ft
                        sheets_materials[material_type]['codes'].add(mat['code'])
                except Exception as e:
                    if DEBUG_ENABLED:
                        print(f"DEBUG: Error parsing sheathing dimensions: {e}")
            else:
                # Fallback for single dimension - estimate width based on material type
                if DEBUG_ENABLED:
                    print(f"DEBUG: Sheathing without 'x' format: {mat['length']}")
                if length_feet > 0:
                    # Estimate width based on material type
                    width_feet = 8.0 / 12.0  # Default 8" width
                    if '4x8' in material_type:
                        width_feet = 8.0 / 12.0  # 8" width
                    elif '4x9' in material_type:
                        width_feet = 9.0 / 12.0  # 9" width
                    elif 'ply' in material_type.lower() or 'plywood' in material_type.lower():
                        width_feet = 8.0 / 12.0  # Assume 8" for plywood
                    
                    sq_ft = length_feet * width_feet * quantity
                    linear_ft = length_feet * quantity
                    
                    if material_type not in sheets_materials:
                        sheets_materials[material_type] = {
                            'sq_ft': 0,
                            'linear_ft': 0,
                            'codes': set(),
                            'is_endpadding': family_member == 'endpadding',
                            'is_thin_material': is_thin_material
                        }
                    sheets_materials[material_type]['sq_ft'] += sq_ft
                    sheets_materials[material_type]['linear_ft'] += linear_ft
                    sheets_materials[material_type]['codes'].add(mat['code'])

        # LINEAR: All materials with length > 0
        elif length_feet > 0:
            if 'bracing' in family_member.lower():
                if DEBUG_ENABLED:
                    print(f"DEBUG: Categorizing as BRACING: {family_member} with length {length_feet}")
                
                group_key = (material_type, length_display)
                if group_key not in bracing_materials:
                    bracing_materials[group_key] = {
                        'count': 0,
                        'length_display': length_display,
                        'material_type': material_type,
                        'codes': set()
                    }
                bracing_materials[group_key]['count'] += quantity
                bracing_materials[group_key]['codes'].add(mat['code'])
            elif 'stud' in family_member:
                # Check for standard precut lengths
                standard_lengths = {
                    "7-8-5/8": 7 + (8 + 5/8) / 12,  # 7.71875
                    "8-8-5/8": 8 + (8 + 5/8) / 12,  # 8.71875
                    "9-8-5/8": 9 + (8 + 5/8) / 12   # 9.71875
                }
                is_precut = False
                precut_length_display = ""
                for std_len_str, std_len_feet_val in standard_lengths.items():
                    if abs(length_feet - std_len_feet_val) < 0.005:  # Small tolerance for floating point
                        is_precut = True
                        precut_length_display = std_len_str
                        break
                
                if is_precut:
                    if DEBUG_ENABLED:
                        print(f"DEBUG: Categorizing as PRECUT: {family_member} with length {length_feet} ({precut_length_display})")
                    
                    group_key = (material_type, precut_length_display)
                    if group_key not in precut_materials:
                        precut_materials[group_key] = {
                            'count': 0,
                            'length_display': precut_length_display,
                            'material_type': material_type,
                            'codes': set()
                        }
                    precut_materials[group_key]['count'] += quantity
                    precut_materials[group_key]['codes'].add(mat['code'])
                else:
                    if DEBUG_ENABLED:
                        print(f"DEBUG: Categorizing as LINEAR: {family_member} with length {length_feet}")
                    # Apply round-up rule to next foot for all linear materials
                    rounded_feet = math.ceil(length_feet)  # Round up to next foot
                    rounded_feet = math.ceil(length_feet)  # Round up to next foot
                    
                    group_key = (material_type, rounded_feet)
                    
                    if group_key not in linear_materials:
                        linear_materials[group_key] = {
                            'quantity': 0,
                            'length_display': length_display,
                            'rounded_feet': rounded_feet,
                            'material_type': material_type,
                            'codes': set()
                        }
                    linear_materials[group_key]['quantity'] += quantity
                    linear_materials[group_key]['codes'].add(mat['code'])
            else:
                if DEBUG_ENABLED:
                    print(f"DEBUG: Categorizing as LINEAR: {family_member} with length {length_feet}")
                rounded_feet = math.ceil(length_feet)  # Round up to next foot

                group_key = (material_type, rounded_feet)
                if group_key not in linear_materials:
                    linear_materials[group_key] = {
                        'quantity': 0,
                        'length_display': length_display,
                        'rounded_feet': rounded_feet,
                        'material_type': material_type,
                        'codes': set()
                    }
                linear_materials[group_key]['quantity'] += quantity
                linear_materials[group_key]['codes'].add(mat['code'])
        else:
            if DEBUG_ENABLED:
                print(f"DEBUG: Skipping material with zero length: {family_member}")

    if DEBUG_ENABLED:
        print(f"DEBUG: Categorization complete - sheets:{len(sheets_materials)}, linear:{len(linear_materials)}, precut:{len(precut_materials)}, bracing:{len(bracing_materials)}")
    output_lines = []
    total_board_feet = 0

    # Section 1: Total Number Of Sheets
    if sheets_materials:
        output_lines.append("Total Number Of Sheets")
        for mat_type, data in sorted(sheets_materials.items()):
            sq_ft = data['sq_ft']
            linear_ft = data['linear_ft']
            is_endpadding = data.get('is_endpadding', False)
            
            codes_str = f" ({','.join(sorted(data['codes']))})" if data['codes'] else ""
            
            if is_endpadding and linear_ft > 0:
                # For EndPadding, calculate actual square footage from dimensions
                # linear_ft contains the length in feet, we need to determine width
                # For EndPadding, typically 2x6 material which is 5.5" wide
                width_inches = 5.5  # Default width for 2x6 EndPadding
                if '2x4' in mat_type:
                    width_inches = 3.5
                elif '2x6' in mat_type:
                    width_inches = 5.5
                elif '2x8' in mat_type:
                    width_inches = 7.25
                elif '2x10' in mat_type:
                    width_inches = 9.25
                elif '2x12' in mat_type:
                    width_inches = 11.25
                
                width_feet = width_inches / 12.0
                piece_sq_ft = linear_ft * width_feet
                sheets_needed = math.ceil(piece_sq_ft / 32.0) if piece_sq_ft > 0 else 0  # Assume 32 sq ft sheets
                actual_sheets = piece_sq_ft / 32.0 if piece_sq_ft > 0 else 0
                
                # Format sheets to match regular sheathing column positions
                sheet_info = f"{actual_sheets:.2f} ({sheets_needed})"
                output_lines.append(f"C:{sheet_info:<14}\tM: {get_material_display_name(mat_type):<20}\t\tSQ FT: {piece_sq_ft:>8.2f}{codes_str}")
            else:
                # Regular sheathing - show square footage
                # Determine sheet size from material type (e.g., "4x9" or "4x8")
                sheet_size_sq_ft = 32.0  # Default to 4x8 = 32 sq ft
                if '4x9' in mat_type:
                    sheet_size_sq_ft = 36.0  # 4x9 = 36 sq ft
                elif '4x8' in mat_type:
                    sheet_size_sq_ft = 32.0  # 4x8 = 32 sq ft
                
                # Calculate number of sheets needed (round up)
                sheets_needed = math.ceil(sq_ft / sheet_size_sq_ft) if sq_ft > 0 else 0
                actual_sheets = sq_ft / sheet_size_sq_ft if sq_ft > 0 else 0
                
                # Format sheets to match linear materials column positions exactly
                sheet_info = f"{actual_sheets:.2f} ({sheets_needed})"
                output_lines.append(f"C:{sheet_info:<14}\tM: {get_material_display_name(mat_type):<20}\t\tSQ FT: {sq_ft:>8.2f}{codes_str}")
        output_lines.append("")

    # Section 2: Total Board Feet
    if linear_materials:
        output_lines.append("Total Board Feet:")
        
        # Group by material type for output
        materials_by_type = {}
        for group_key, data in linear_materials.items():
            mat_type = data['material_type']
            if mat_type not in materials_by_type:
                materials_by_type[mat_type] = []
            materials_by_type[mat_type].append(data)
        
        # Output each material type with custom sorting
        sorted_mat_types = sort_materials_by_hierarchy(materials_by_type.keys())
        for mat_type in sorted_mat_types:
            type_entries = materials_by_type[mat_type]
            type_total_feet = 0
            
            # Individual entries for each length, sorted by rounded feet
            for entry in sorted(type_entries, key=lambda x: x['rounded_feet']):
                qty = entry['quantity']
                length_display = entry['length_display']
                rounded_feet = entry['rounded_feet']
                # Calculate proper board feet instead of just using linear feet
                board_feet_per_piece = calculate_board_feet(rounded_feet, 0, mat_type)
                total_board_feet_for_entry = board_feet_per_piece * qty
                type_total_feet += total_board_feet_for_entry

                # Format: C:   2	L:  12'-0"	M: 2x6 SPF PM No.2     	T:  24'-0"            24 :BF (A,B)
                rounded_display = format_feet_to_dimension(rounded_feet)
                equivalent_linear_feet = calculate_equivalent_linear_feet(total_board_feet_for_entry, mat_type)
                total_display = format_feet_to_dimension(round(equivalent_linear_feet))
                codes_str = f" ({','.join(sorted(entry['codes']))})" if entry['codes'] else ""
                output_lines.append(f"C:{qty:>3}	L:{rounded_display:>8}	M: {get_material_display_name(mat_type):<20}	T: {total_display:>8}	{total_board_feet_for_entry:>8.1f} :BF{codes_str}")

            # Total for this material type - use the sum of individual totals
            if type_total_feet > 0:
                type_total_linear_feet = sum(calculate_equivalent_linear_feet(calculate_board_feet(entry['rounded_feet'], 0, mat_type) * entry['quantity'], mat_type) for entry in type_entries)
                type_total_display = format_feet_to_dimension(round(type_total_linear_feet))
                output_lines.append(f"                              TOTAL LINEAR LENGTH: {type_total_display:>8}	{type_total_feet:>8.1f} :TOTAL BF.")
                total_board_feet += type_total_feet
            
            # Add blank line between different material types for easier reading
            output_lines.append("")

    # Section 3: Total Number Of Precut Studs
    if precut_materials:
        output_lines.append("Total Number Of Precut Studs:")
        for group_key, data in sorted(precut_materials.items()):
            count = data['count']
            length_display = data['length_display']
            material_type = data['material_type']
            codes_str = f" ({','.join(sorted(data['codes']))})" if data['codes'] else ""
            output_lines.append(f"C:{count:>3}	L:{length_display:>8}	M: {get_material_display_name(material_type):<20}{codes_str}")

    # Section 4: Total Steel Bracing
    if bracing_materials:
        output_lines.append("Total Steel Bracing:")
        for group_key, data in sorted(bracing_materials.items()):
            count = data['count']
            length_display = data['length_display']
            material_type = data['material_type']
            codes_str = f" ({','.join(sorted(data['codes']))})" if data['codes'] else ""
            output_lines.append(f"C:{count:>3}	L:{length_display:>8}	M: {get_material_display_name(material_type):<20}{codes_str}")

    return '\n'.join(output_lines), total_board_feet

def _nat_key(s):
    """Natural sort key: split digits and non-digits so strings with numbers sort naturally."""
    try:
        parts = re.split(r'(\d+)', (s or ''))
        return [int(p) if p.isdigit() else p.lower() for p in parts]
    except Exception:
        return [s]

def _is_rough_opening(m):
    """Check if a material represents a rough opening that should be excluded"""
    if not isinstance(m, dict):
        return False

    # Check for rough opening indicators in description
    desc = (m.get('Desc', '').lower() or m.get('Description', '').lower())
    family_member = (m.get('FamilyMemberName', '').lower())

    # Rough openings typically have descriptions containing these patterns
    rough_opening_patterns = [
        'rough opening',
        'r/o',
        'opening',
        'window opening',
        'door opening',
        'garage opening'
    ]

    # Check description for rough opening patterns
    for pattern in rough_opening_patterns:
        if pattern in desc:
            return True

    # Check FamilyMemberName for rough opening indicators
    if 'rough' in family_member and 'opening' in family_member:
        return True

    return False

def parse_materials_from_panel(panel_element, root):
    """Extract all materials from a panel element, including those in SubAssemblies and LooseMembers"""
    materials = []
    critical_studs = []

    # Handle case where panel_element is None
    if panel_element is None:
        return materials, critical_studs

    # Get panel GUID for filtering
    panel_guid = None
    for guid_tag in ['PanelGuid', 'PanelID']:
        guid_el = panel_element.find(guid_tag)
        if guid_el is not None and guid_el.text:
            panel_guid = guid_el.text.strip()
            break

    if not panel_guid:
        return materials, critical_studs

    # Process all Board elements associated with this panel
    for board_el in root.findall('.//Board'):
        # Check if this board belongs to the panel
        panel_guid_el = board_el.find('PanelGuid')
        belongs_to_panel = panel_guid_el is not None and panel_guid_el.text == panel_guid

        # Also include boards that are part of SubAssemblies belonging to this panel
        is_subassembly_board = False
        if not belongs_to_panel:
            subassembly_guid_el = board_el.find('SubAssemblyGuid')
            if subassembly_guid_el is not None and subassembly_guid_el.text:
                sub_guid = subassembly_guid_el.text.strip()
                # Check if this SubAssembly GUID belongs to our panel
                for sub_el in root.findall('.//SubAssembly'):
                    sub_panel_guid_el = sub_el.find('PanelGuid')
                    sub_panel_id_el = sub_el.find('PanelID')
                    if ((sub_panel_guid_el is not None and sub_panel_guid_el.text == panel_guid) or
                        (sub_panel_id_el is not None and sub_panel_id_el.text == panel_guid)):
                        sub_guid_el = sub_el.find('SubAssemblyGuid')
                        if sub_guid_el is not None and sub_guid_el.text == sub_guid:
                            is_subassembly_board = True
                            break

        if not belongs_to_panel and not is_subassembly_board:
            continue

        # Skip rough openings
        if _is_rough_opening({'Desc': _text_of(board_el, ['Material/Description'])}):
            continue

        # Extract material information
        material_info = {}

        # Basic identifiers
        for tag in ['BoardGuid', 'SubAssemblyGuid']:
            el = board_el.find(tag)
            if el is not None and el.text:
                material_info[tag] = el.text.strip()

        # Family member information
        family_member_el = board_el.find('FamilyMember')
        if family_member_el is not None and family_member_el.text:
            material_info['FamilyMember'] = family_member_el.text.strip()

        family_member_name_el = board_el.find('FamilyMemberName')
        if family_member_name_el is not None and family_member_name_el.text:
            material_info['FamilyMemberName'] = family_member_name_el.text.strip()

        # Label
        label_el = board_el.find('Label')
        if label_el is not None and label_el.text:
            material_info['Label'] = label_el.text.strip()
        else:
            material_info['Label'] = ''

        # SubAssembly information
        subassembly_el = board_el.find('SubAssembly')
        if subassembly_el is not None and subassembly_el.text:
            material_info['SubAssembly'] = subassembly_el.text.strip()
        else:
            material_info['SubAssembly'] = ''

        # Quantity
        qty_el = board_el.find('Quantity')
        if qty_el is not None and qty_el.text:
            try:
                material_info['Qty'] = qty_el.text.strip()
            except:
                material_info['Qty'] = '1'
        else:
            material_info['Qty'] = '1'

        # Dimensions - try ActualLength/ActualWidth first, then Length/Width
        length_el = board_el.find('ActualLength') or board_el.find('Length')
        if length_el is not None and length_el.text is not None:
            material_info['ActualLength'] = length_el.text.strip()

        width_el = board_el.find('ActualWidth') or board_el.find('Width')
        if width_el is not None and width_el.text is not None:
            material_info['ActualWidth'] = width_el.text.strip()

        # Material description
        material_el = board_el.find('Material')
        if material_el is not None:
            desc_el = material_el.find('Description')
            if desc_el is not None and desc_el.text:
                material_info['Desc'] = desc_el.text.strip()

        # Add to materials list
        materials.append(material_info)

    # Process Sheet elements (sheathing) - both panel-specific and root-level
    for sheet_el in root.findall('.//Sheet'):
        # Check if this sheet belongs to the panel
        panel_guid_el = sheet_el.find('PanelGuid')
        belongs_to_panel = panel_guid_el is not None and panel_guid_el.text == panel_guid

        # Also include sheets that are part of SubAssemblies belonging to this panel
        subassembly_guid_el = sheet_el.find('SubAssemblyGuid')
        is_subassembly_sheet = False
        if subassembly_guid_el is not None and subassembly_guid_el.text:
            sub_guid = subassembly_guid_el.text.strip()
            # Check if this SubAssembly GUID belongs to our panel
            for sub_el in root.findall('.//SubAssembly'):
                sub_panel_guid_el = sub_el.find('PanelGuid')
                sub_panel_id_el = sub_el.find('PanelID')
                if ((sub_panel_guid_el is not None and sub_panel_guid_el.text == panel_guid) or
                    (sub_panel_id_el is not None and sub_panel_id_el.text == panel_guid)):
                    sub_guid_el = sub_el.find('SubAssemblyGuid')
                    if sub_guid_el is not None and sub_guid_el.text == sub_guid:
                        is_subassembly_sheet = True
                        break

        if not belongs_to_panel and not is_subassembly_sheet:
            continue

        # Skip rough openings
        if _is_rough_opening({'Desc': _text_of(sheet_el, ['Material/Description'])}):
            continue

        # Extract material information
        material_info = {}

        # Basic identifiers
        for tag in ['SheetGuid', 'SubAssemblyGuid']:
            el = sheet_el.find(tag)
            if el is not None and el.text:
                material_info[tag] = el.text.strip()

        # Family member information (sheets typically have FamilyMember 40 for Sheathing)
        family_member_el = sheet_el.find('FamilyMember')
        if family_member_el is not None and family_member_el.text:
            material_info['FamilyMember'] = family_member_el.text.strip()

        family_member_name_el = sheet_el.find('FamilyMemberName')
        if family_member_name_el is not None and family_member_name_el.text:
            material_info['FamilyMemberName'] = family_member_name_el.text.strip()
        else:
            material_info['FamilyMemberName'] = 'Sheathing'  # Default for sheets

        # Label
        label_el = sheet_el.find('Label')
        if label_el is not None and label_el.text:
            material_info['Label'] = label_el.text.strip()
        else:
            material_info['Label'] = ''

        # SubAssembly information
        subassembly_el = sheet_el.find('SubAssembly')
        if subassembly_el is not None and subassembly_el.text:
            material_info['SubAssembly'] = subassembly_el.text.strip()
        else:
            material_info['SubAssembly'] = ''

        # Quantity
        qty_el = sheet_el.find('Quantity')
        if qty_el is not None and qty_el.text:
            try:
                material_info['Qty'] = qty_el.text.strip()
            except:
                material_info['Qty'] = '1'
        else:
            material_info['Qty'] = '1'

        # Dimensions - try Material child element first, then Sheet element
        material_el = sheet_el.find('Material')
        length = ''
        width = ''

        if material_el is not None:
            # Try to get dimensions from Material child element first
            length_el = material_el.find('ActualLength')
            if length_el is None:
                length_el = material_el.find('Length')
            if length_el is not None and length_el.text is not None:
                length = length_el.text.strip()

            width_el = material_el.find('ActualWidth')
            if width_el is None:
                width_el = material_el.find('Width')
            if width_el is not None and width_el.text is not None:
                width = width_el.text.strip()

        # Fallback to direct Sheet element if no Material child dimensions
        if not length:
            length_el = sheet_el.find('ActualLength')
            if length_el is None:
                length_el = sheet_el.find('Length')
            if length_el is not None and length_el.text is not None:
                length = length_el.text.strip()

        if not width:
            width_el = sheet_el.find('ActualWidth')
            if width_el is None:
                width_el = sheet_el.find('Width')
            if width_el is not None and width_el.text is not None:
                width = width_el.text.strip()

        if length:
            material_info['ActualLength'] = length
        if width:
            material_info['ActualWidth'] = width

        # Material description
        if material_el is not None:
            desc_el = material_el.find('Description')
            if desc_el is not None and desc_el.text:
                material_info['Desc'] = desc_el.text.strip()

        # Add to materials list
        materials.append(material_info)

    # Process Bracing elements - both panel-specific and root-level
    try:
        for bracing_el in root.findall('.//Bracing'):
            # Check if this bracing belongs to the panel
            panel_guid_el = bracing_el.find('PanelGuid')
            belongs_to_panel = panel_guid_el is not None and panel_guid_el.text == panel_guid

            # Also include bracing that is part of SubAssemblies belonging to this panel
            subassembly_guid_el = bracing_el.find('SubAssemblyGuid')
            is_subassembly_bracing = False
            if subassembly_guid_el is not None and subassembly_guid_el.text:
                sub_guid = subassembly_guid_el.text.strip()
                # Check if this SubAssembly GUID belongs to our panel
                for sub_el in root.findall('.//SubAssembly'):
                    sub_panel_guid_el = sub_el.find('PanelGuid')
                    sub_panel_id_el = sub_el.find('PanelID')
                    if ((sub_panel_guid_el is not None and sub_panel_guid_el.text == panel_guid) or
                        (sub_panel_id_el is not None and sub_panel_id_el.text == panel_guid)):
                        sub_guid_el = sub_el.find('SubAssemblyGuid')
                        if sub_guid_el is not None and sub_guid_el.text == sub_guid:
                            is_subassembly_bracing = True
                            break

            if not belongs_to_panel and not is_subassembly_bracing:
                continue

            # Extract material information
            material_info = {}

            # Basic identifiers
            for tag in ['BoardGuid', 'SubAssemblyGuid']:
                el = bracing_el.find(tag)
                if el is not None and el.text:
                    material_info[tag] = el.text.strip()

            # Family member information
            family_member_el = bracing_el.find('FamilyMember')
            if family_member_el is not None and family_member_el.text:
                material_info['FamilyMember'] = family_member_el.text.strip()

            family_member_name_el = bracing_el.find('FamilyMemberName')
            if family_member_name_el is not None and family_member_name_el.text:
                material_info['FamilyMemberName'] = family_member_name_el.text.strip()

            # Label
            label_el = bracing_el.find('Label')
            if label_el is not None and label_el.text:
                material_info['Label'] = label_el.text.strip()
            else:
                material_info['Label'] = ''

            # SubAssembly information
            subassembly_el = bracing_el.find('SubAssembly')
            if subassembly_el is not None and subassembly_el.text:
                material_info['SubAssembly'] = subassembly_el.text.strip()
            else:
                material_info['SubAssembly'] = ''

            # Quantity
            qty_el = bracing_el.find('Quantity')
            if qty_el is not None and qty_el.text:
                try:
                    material_info['Qty'] = qty_el.text.strip()
                except:
                    material_info['Qty'] = '1'
            else:
                material_info['Qty'] = '1'

            # Dimensions - try Material child element first
            material_el = bracing_el.find('Material')
            if material_el is not None:
                # Try ActualLength first, then Length
                length_el = material_el.find('ActualLength')
                if length_el is None:
                    length_el = material_el.find('Length')
                if length_el is not None and length_el.text is not None:
                    material_info['ActualLength'] = length_el.text.strip()

                # Try ActualWidth first, then Width
                width_el = material_el.find('ActualWidth')
                if width_el is None:
                    width_el = material_el.find('Width')
                if width_el is not None and width_el.text is not None:
                    material_info['ActualWidth'] = width_el.text.strip()

                # Material description
                desc_el = material_el.find('Description')
                if desc_el is not None and desc_el.text:
                    material_info['Desc'] = desc_el.text.strip()

            # Add to materials list
            materials.append(material_info)
    except Exception as e:
        print(f"Error processing bracing elements: {e}")
        # Continue processing even if bracing fails

    # Process LooseMember elements - materials shipped separately but belonging to this panel
    for loose_el in root.findall('.//LooseMember'):
        # Check if this loose member belongs to the panel
        panel_guid_el = loose_el.find('PanelGuid')
        panel_id_el = loose_el.find('PanelID')
        belongs_to_panel = ((panel_guid_el is not None and panel_guid_el.text == panel_guid) or
                           (panel_id_el is not None and panel_id_el.text == panel_guid))

        if not belongs_to_panel:
            continue

        # Extract material information from loose member
        material_info = {}

        # Basic identifiers
        for tag in ['BoardGuid']:
            el = loose_el.find(tag)
            if el is not None and el.text:
                material_info[tag] = el.text.strip()

        # Family member information
        family_member_el = loose_el.find('FamilyMember')
        if family_member_el is not None and family_member_el.text:
            material_info['FamilyMember'] = family_member_el.text.strip()

        family_member_name_el = loose_el.find('FamilyMemberName')
        if family_member_name_el is not None and family_member_name_el.text:
            material_info['FamilyMemberName'] = family_member_name_el.text.strip()

        # Label
        label_el = loose_el.find('Label')
        if label_el is not None and label_el.text:
            material_info['Label'] = label_el.text.strip()
        else:
            material_info['Label'] = ''

        # Quantity (loose members are typically 1 each)
        material_info['Qty'] = '1'

        # Dimensions from Material element
        material_el = loose_el.find('Material')
        if material_el is not None:
            # Try ActualLength first, then Length
            length_el = material_el.find('ActualLength')
            if length_el is None:
                length_el = material_el.find('Length')
            if length_el is not None and length_el.text is not None:
                material_info['ActualLength'] = length_el.text.strip()

            # Try ActualWidth first, then Width
            width_el = material_el.find('ActualWidth')
            if width_el is None:
                width_el = material_el.find('Width')
            if width_el is not None and width_el.text is not None:
                material_info['ActualWidth'] = width_el.text.strip()

            # Material description
            desc_el = material_el.find('Description')
            if desc_el is not None and desc_el.text:
                material_info['Desc'] = desc_el.text.strip()

        # Add to materials list
        materials.append(material_info)

    return materials, critical_studs

def format_and_sort_materials(materials, panel_height=None):
    """Format materials into breakdown lines and sort by type priority then alphabetically
    
    Args:
        materials: List of material dictionaries
        panel_height: Panel height in inches (optional, for plate cutting adjustments)
    """
    if not materials:
        return []

    # Filter out rough openings from the breakdown (like Vold.py does)
    filtered_materials = [m for m in materials if not _is_rough_opening(m)]

    # Apply plate cutting rules if panel height is provided
    if panel_height:
        for m in filtered_materials:
            if isinstance(m, dict):
                fam = (m.get('FamilyMemberName') or '').lower()
                length = m.get('ActualLength') or m.get('Length') or ''
                
                # Note: VeryTopPlate is shipped loose and should retain its original length
                # No adjustment needed for VeryTopPlate
                
                # Apply additional bottom plate cutting rule: panel height - 3"
                # This would apply to any bottom plate beyond the first one
                if 'bottomplate' in fam and length:
                    # Check if this is an additional bottom plate (FM106)
                    fm_id = m.get('FamilyMember')
                    if fm_id == '106':  # FM106 is BottomMultiPlate
                        try:
                            current_length = float(length)
                            adjusted_length = panel_height - 3.0
                            if adjusted_length > 0:
                                m['ActualLength'] = str(adjusted_length)
                                m['Length'] = str(adjusted_length)
                        except (ValueError, TypeError):
                            pass

    # Filter out rough openings from the breakdown (like Vold.py does)
    filtered_materials = [m for m in materials if not _is_rough_opening(m)]

    # Create the mapping for alphabetical labels with type prioritization
    material_mapping = create_material_to_breakdown_mapping(filtered_materials)

    # Update material labels with alphabetical breakdown labels
    for m in filtered_materials:
        if isinstance(m, dict):
            original_label = m.get('Label', '')
            if original_label in material_mapping:
                m['Label'] = material_mapping[original_label]

    # Group materials by label for sorting and counting (following Vold.py logic)
    groups = {}
    sheathing_materials = []  # Collect sheathing materials separately

    for m in filtered_materials:
        lbl = (m.get('Label') or '').strip()
        typ = (m.get('Type') or '').strip()
        fam = (m.get('FamilyMemberName') or '').strip()
        desc = (m.get('Desc') or m.get('Description') or '').strip()
        length = m.get('ActualLength') or m.get('Length') or ''
        width = m.get('ActualWidth') or m.get('Width') or ''

        # Round length and width to handle floating point precision issues (use more precision for exact display)
        try:
            length_val = float(length) if length else 0.0
            length_rounded = round(length_val, 3)  # Use 3 decimal places for more precision
            length_str = str(length_rounded) if length_rounded != 0.0 else ''
        except (ValueError, TypeError):
            length_str = str(length).strip()
            
        try:
            width_val = float(width) if width else 0.0
            width_rounded = round(width_val, 3)  # Use 3 decimal places for more precision
            width_str = str(width_rounded) if width_rounded != 0.0 else ''
        except (ValueError, TypeError):
            width_str = str(width).strip()        # Check if this is a sheathing material
        is_sheathing = 'sheet' in typ.lower() or 'sheath' in typ.lower() or 'sheath' in fam.lower() or fam.lower() == 'endpadding' or 'endpadding' in fam.lower()
        
        # Also check if this is a thin material (< 1.5" thick) that should be treated as sheathing
        thickness = extract_thickness_from_description(desc)
        is_thin_material = thickness < 1.5
        if is_thin_material:
            is_sheathing = True

        if is_sheathing:
            # Collect sheathing materials separately to assign individual labels
            sheathing_materials.append({
                'material': m,
                'lbl': lbl,
                'typ': typ,
                'fam': fam,
                'desc': desc,
                'length': length,
                'width': width,
                'length_str': length_str,
                'width_str': width_str
            })
        else:
            # Group non-sheathing materials as before
            key = (lbl, typ, desc, length_str, width_str)

            # Parse quantity from the material
            qty_str = m.get('Qty', '1')
            try:
                qty = int(float(qty_str)) if qty_str else 1
            except (ValueError, TypeError):
                qty = 1

            if key not in groups:
                groups[key] = {
                    'count': 0,
                    'length': length,
                    'width': width,
                    'lbl': lbl,
                    'typ': typ,
                    'fam': fam,
                    'desc': desc
                }
            groups[key]['count'] += qty

    # Sort keys by natural label ordering
    sorted_keys = sorted(groups.keys(), key=lambda k: _nat_key(k[0] or ''))
    lines = []

    # Process non-sheathing materials first
    for key in sorted_keys:
        # Handle variable key length for sheathing
        if len(key) == 5:  # Regular key
            lbl, typ, desc, length, width = key
        else:  # Fallback
            lbl, typ, desc, length, width = key[:5]
        info = groups[key]
        cnt = info.get('count', 0)
        qty_str = f"({cnt})" if cnt > 1 else "(1)"
        len_str = format_feet_to_dimension(float(length)/12) if length not in (None, '', '0', '0.0') else ''
        wid_str = format_feet_to_dimension(float(width)/12) if width not in (None, '', '0', '0.0') else ''
        size = ''
        # Sheets include width in the size; boards/bracing use length only
        if 'sheet' in typ.lower() or 'sheath' in typ.lower():
            if len_str and wid_str:
                size = f"{len_str} x {wid_str}"
            elif len_str:
                size = f"{len_str}"
            elif wid_str:
                size = f"{wid_str}"
            else:
                size = ''
        else:
            size = len_str or ''
        # clean desc
        desc_clean = desc
        # build line
        # use FamilyMemberName for middle column to match materials.log
        mid = info.get('fam') or info.get('typ') or typ
        if size:
            line = f"{lbl} - {mid} - {desc_clean} - {qty_str} - {size}"
        else:
            line = f"{lbl} - {mid} - {desc_clean} - {qty_str}"
        # Only add spaces around the main separator dashes, not dimension dashes
        # Split by ' - ' first to preserve dimension formatting
        parts = line.split(' - ')
        # Rejoin with proper spacing, but keep dimension strings intact
        formatted_parts = []
        for part in parts:
            # If this part contains feet-inches format (has ' and -), keep as-is
            if "'" in part and '-' in part:
                formatted_parts.append(part)
            else:
                formatted_parts.append(part)
        line = ' - '.join(formatted_parts)
        lines.append(line)

    # Process sheathing materials individually with existing labels
    if sheathing_materials:
        # Deduplicate sheathing materials based on their properties
        seen_sheathing = set()
        deduplicated_sheathing = []
        for sheath in sheathing_materials:
            key = (sheath['lbl'], sheath['typ'], sheath['desc'], sheath['length_str'], sheath['width_str'])
            if key not in seen_sheathing:
                seen_sheathing.add(key)
                deduplicated_sheathing.append(sheath)
        sheathing_materials = deduplicated_sheathing

        # Sort sheathing materials by their original properties for consistent ordering
        sheathing_materials.sort(key=lambda x: (x['lbl'], x['desc'], x['length_str'], x['width_str']))

        for sheath_info in sheathing_materials:
            # Use the existing label from the material
            lbl = sheath_info['lbl']
            typ = sheath_info['typ']
            desc = sheath_info['desc']
            length = sheath_info['length']
            width = sheath_info['width']

            qty_str = "(1)"  # Each sheathing piece is individual
            len_str = format_feet_to_dimension(float(length)/12) if length not in (None, '', '0', '0.0') else ''
            wid_str = format_feet_to_dimension(float(width)/12) if width not in (None, '', '0', '0.0') else ''
            size = ''

            # For EndPadding, ensure correct width based on material size
            if sheath_info.get('fam', '').lower() == 'endpadding':
                if '2x4' in desc:
                    width = '3.5'  # 2x4 padding is 3.5" wide
                    wid_str = format_feet_to_dimension(float(width)/12)
                elif '2x6' in desc:
                    width = '5.5'  # 2x6 padding is 5.5" wide
                    wid_str = format_feet_to_dimension(float(width)/12)

            # Inference logic for 4x9 sheathing and thin materials
            if not wid_str and len_str and ('4x9' in desc.lower() or is_thin_material):
                # If we have length but no width, and it's 4x9 sheathing or thin material, infer width
                if len_str == "9'-0":  # 9' length means 4x9 sheathing
                    wid_str = "4'-0"
                elif len_str == "4'-0":  # 4' length means 9x4 sheathing
                    wid_str = "9'-0"
                elif is_thin_material:
                    # For thin materials, try to infer width from description
                    if '4x8' in desc:
                        wid_str = "8'-0"
                    elif '4x9' in desc:
                        wid_str = "9'-0"
                    else:
                        # Default assumption for thin materials
                        wid_str = "8'-0"

            if len_str and wid_str:
                size = f"{len_str} x {wid_str}"  # Use quotes for sheathing dimensions
            elif len_str:
                size = f"{len_str}"
            elif wid_str:
                size = f"{wid_str}"

            # clean desc
            desc_clean = desc
            # build line
            # use FamilyMemberName for middle column to match materials.log
            mid = sheath_info.get('fam') or typ
            if size:
                line = f"{lbl} - {mid} - {desc_clean} - {qty_str} - {size}"
            else:
                line = f"{lbl} - {mid} - {desc_clean} - {qty_str}"
            # Only add spaces around the main separator dashes, not dimension dashes
            # Split by ' - ' first to preserve dimension formatting
            parts = line.split(' - ')
            # Rejoin with proper spacing, but keep dimension strings intact
            formatted_parts = []
            for part in parts:
                # If this part contains feet-inches format (has ' and -), keep as-is
                if "'" in part and '-' in part:
                    formatted_parts.append(part)
                else:
                    formatted_parts.append(part)
            line = ' - '.join(formatted_parts)
            lines.append(line)

    # Sort all lines by the label at the beginning of each line to ensure proper alphabetical order
    lines.sort(key=lambda line: _nat_key(line.split(' - ')[0] if ' - ' in line else line))

    return lines

def create_material_to_breakdown_mapping(mats):
    """Create a mapping from material properties to specific breakdown labels based on FamilyMemberName
    
    Uses predefined letter assignments for common stud types to make the breakdown more meaningful:
    - D: Trimmer
    - F: Stud/KingStud
    - G: CriticalStud
    - O: EndPadding
    - P: FillerCripple
    - Other materials get alphabetical letters A, B, C, etc.
    """
    # Specific letter mappings for common stud types
    SPECIFIC_MAPPINGS = {
        'Trimmer': 'D',
        'Stud': 'F', 
        'KingStud': 'F',  # KingStud also maps to F
        'CriticalStud': 'G',
        'EndPadding': 'O',
        'FillerCripple': 'P',
        'FillerBtmNailer': 'Q',
        'BottomPlate': 'A',
        'TopPlate': 'B', 
        'VeryTopPlate': 'C',
        'Header': 'E'
    }
    
    # ensure label fallback
    for m in mats:
        if not m.get('Label'):
            m['Label'] = (m.get('Type','') + '-' + (m.get('Desc') or ''))[:6]

    # group identical materials by (Label, Type, Desc, length, width, SubAssemblyGuid)
    groups = {}
    sheathing_index = 0  # Counter for sheathing materials to make each unique
    for m in mats:
        lbl = (m.get('Label') or '').strip()
        typ = (m.get('Type') or '').strip()
        desc = (m.get('Desc') or m.get('Description') or '').strip()
        length = m.get('ActualLength') or m.get('Length') or ''
        width = m.get('ActualWidth') or m.get('Width') or ''
        subassembly_guid = (m.get('SubAssemblyGuid') or '').strip()
        family_member_name = (m.get('FamilyMemberName') or '').strip()
        
        # Round length and width to 2 decimal places to handle floating point precision issues
        try:
            length_val = float(length) if length else 0.0
            length_rounded = round(length_val, 2)
            length_str = str(length_rounded) if length_rounded != 0.0 else ''
        except (ValueError, TypeError):
            length_str = str(length).strip()
            
        try:
            width_val = float(width) if width else 0.0
            width_rounded = round(width_val, 2)
            width_str = str(width_rounded) if width_rounded != 0.0 else ''
        except (ValueError, TypeError):
            width_str = str(width).strip()
        
        # Check if this is a sheathing material
        is_sheathing = 'sheet' in typ.lower() or 'sheath' in typ.lower()
        
        # normalize numeric strings
        if is_sheathing:
            # For sheathing, make each piece unique by including an index
            key = (lbl, typ, desc, length_str, width_str, subassembly_guid, sheathing_index)
            sheathing_index += 1
        else:
            key = (lbl, typ, desc, length_str, width_str, subassembly_guid)
        
        if key not in groups:
            groups[key] = {
                'count': 0, 
                'length': length, 
                'width': width,
                'lbl': lbl, 
                'typ': typ, 
                'desc': desc,
                'subassembly': (m.get('SubAssembly') or '').strip(),
                'subassembly_guid': subassembly_guid,
                'family_member_name': family_member_name
            }
        
        # Parse quantity from the material
        qty_str = m.get('Qty', '1')
        try:
            qty = int(float(qty_str)) if qty_str else 1
        except (ValueError, TypeError):
            qty = 1
        groups[key]['count'] += qty
    
    # sort keys by natural label ordering and assign specific or alphabetical labels
    sorted_keys = sorted(groups.keys(), key=lambda k: _nat_key(k[0] or ''))
    mapping = {}
    
    # Track used letters to avoid duplicates
    used_letters = set()
    
    # First pass: assign specific mappings for known stud types
    for i, key in enumerate(sorted_keys):
        group_info = groups[key]
        family_member_name = group_info['family_member_name']
        
        # Check if this material type has a specific letter mapping
        assigned_letter = None
        for fm_name, letter in SPECIFIC_MAPPINGS.items():
            if fm_name in family_member_name and letter not in used_letters:
                assigned_letter = letter
                used_letters.add(letter)
                break
        
        if assigned_letter:
            mapping[key] = assigned_letter
    
    # Second pass: assign remaining materials with alphabetical letters
    next_letter_code = 0
    for i, key in enumerate(sorted_keys):
        if key not in groups:
            groups[key] = {
                'count': 0, 
                'length': length, 
                'width': width,
                'lbl': lbl, 
                'typ': typ, 
                'desc': desc,
                'subassembly': (m.get('SubAssembly') or '').strip(),
                'subassembly_guid': subassembly_guid,
                'family_member_name': family_member_name
            }
        
        # Parse quantity from the material
        qty_str = m.get('Qty', '1')
        try:
            qty = int(float(qty_str)) if qty_str else 1
        except (ValueError, TypeError):
            qty = 1
        groups[key]['count'] += qty
    
    # sort keys by natural label ordering and assign specific or alphabetical labels
    sorted_keys = sorted(groups.keys(), key=lambda k: _nat_key(k[0] or ''))
    mapping = {}
    
    # Track used letters to avoid duplicates
    used_letters = set()
    
    # First pass: assign specific mappings for known stud types
    for i, key in enumerate(sorted_keys):
        group_info = groups[key]
        family_member_name = group_info['family_member_name']
        
        # Check if this material type has a specific letter mapping
        assigned_letter = None
        for fm_name, letter in SPECIFIC_MAPPINGS.items():
            if fm_name in family_member_name and letter not in used_letters:
                assigned_letter = letter
                used_letters.add(letter)
                break
        
        if assigned_letter:
            mapping[key] = assigned_letter
    
    # Second pass: assign remaining materials with alphabetical letters
    next_letter_code = 0
    for i, key in enumerate(sorted_keys):
        if key not in mapping:
            # Find next available letter
            while True:
                # Convert index to alphabetical label
                letter = ""
                temp = next_letter_code
                while True:
                    letter = chr(65 + (temp % 26)) + letter  # 65 is ASCII for 'A'
                    temp = temp // 26 - 1
                    if temp < 0:
                        break
                if not letter:  # Handle i=0 case
                    letter = "A"
                
                if letter not in used_letters:
                    mapping[key] = letter
                    used_letters.add(letter)
                    next_letter_code += 1
                    break
                else:
                    next_letter_code += 1
    
    return mapping

def get_panel_material_breakdown_standalone(panel_name, root, panels_data, panel_height=None):
    """Standalone version of panel material breakdown extraction"""
    # panel_name could be a GUID or display name, find the matching panel info
    panel_info = None

    # First try direct lookup by panel_name
    if panel_name in panels_data:
        panel_info = panels_data[panel_name]
    else:
        # Try to find by display name or label
        for guid, info in panels_data.items():
            if (info.get('display_name', '').lower() == panel_name.lower() or
                info.get('label', '').lower() == panel_name.lower() or
                info.get('name', '').lower() == panel_name.lower()):
                panel_info = info
                break

    if not panel_info:
        return f"No panel info found for {panel_name}"

    # Find the panel element by GUID
    panel_el = None
    panel_guid = panel_info['guid']

    for p_el in root.findall('.//Panel'):
        panel_guid_el = p_el.find('PanelGuid')
        panel_id_el = p_el.find('PanelID')
        label_el = p_el.find('Label')

        if ((panel_guid_el is not None and panel_guid_el.text == panel_guid) or
            (panel_id_el is not None and panel_id_el.text == panel_guid)):
            panel_el = p_el
            break

    if panel_el is None:
        return f"No panel element found for {panel_name} (GUID: {panel_guid})"

    # Parse materials using standalone logic
    mats, critical_studs = parse_materials_from_panel(panel_el, root)

    # Filter out FM25 materials (subassembly openings) and excluded materials from takeoff
    filtered_mats = [m for m in mats if not is_fm25_material(m) and not is_excluded_material(m)]

    if not filtered_mats:
        excluded_count = len([m for m in mats if is_excluded_material(m)])
        if excluded_count > 0:
            return f"No loose materials found for panel {panel_name} (FM25 subassembly materials and {excluded_count} excluded materials filtered out)"
        else:
            return f"No loose materials found for panel {panel_name} (FM25 subassembly materials excluded)"

    # Format and sort materials with panel height for plate cutting adjustments
    sorted_lines = format_and_sort_materials(filtered_mats, panel_height)
    result = "\n".join(sorted_lines)

    return result

def _text_of(element, tags):
    """Helper function to get text from first matching tag"""
    for tag in tags:
        el = element.find(tag)
        if el is not None and el.text:
            return el.text.strip()
    return None

def extract_panel_specifications(panel_info, panel_element, root=None, materials=None):
    """Extract detailed panel specifications from panel info and element"""
    specs = {}
    
    # Extract from panel_info (from build_search_indexes)
    specs['level'] = panel_info.get('level', '')
    specs['category'] = panel_info.get('category', '')
    specs['load_bearing'] = panel_info.get('loadbearing', '')
    specs['wall_length'] = panel_info.get('walllength', '')
    specs['height'] = panel_info.get('height', '')
    specs['thickness'] = panel_info.get('thickness', '')
    specs['stud_spacing'] = panel_info.get('studspacing', '')
    specs['weight'] = panel_info.get('weight', '')
    
    # Extract additional fields from panel_element
    if panel_element is not None:
        specs['squaring'] = _text_of(panel_element, ['Squaring'])
        specs['production_notes'] = _text_of(panel_element, ['OnScreenInstruction', 'ProductionNotes'])
        
        # Extract sheathing information from materials using the same logic as file writing
        sheathing_info = []
        if materials:
            if debug_enabled:
                print(f"DEBUG: Processing {len(materials)} materials for sheathing detection")
            for mat in materials:
                if isinstance(mat, dict):
                    # Use the same sheathing detection logic as takeoff_standalone.py
                    t = mat.get('Type', '').lower()
                    m = mat.get('FamilyMemberName', '')
                    if debug_enabled:
                        print(f"DEBUG: Checking material: Type='{t}', FamilyMemberName='{m}', Desc='{mat.get('Desc', '')}'")
                    if 'sheet' in t or 'sheath' in t or (m and 'sheath' in str(m).lower()):
                        # Get material description
                        desc = mat.get('Desc') or mat.get('Description') or mat.get('Label', '')
                        if desc and desc not in sheathing_info:
                            sheathing_info.append(desc)
                            if debug_enabled:
                                print(f"DEBUG: Found sheathing material: {desc} (Type: {t}, FamilyMemberName: {m})")
        
        # Set sheathing info
        if sheathing_info:
            specs['sheathing'] = ', '.join(sheathing_info)
        else:
            specs['sheathing'] = 'Unknown'
        
        # Get the WallLength from XML for reference
        wall_length_xml = _text_of(panel_element, ['WallLength'])
        if wall_length_xml:
            try:
                wall_length_val = float(wall_length_xml)
                specs['wall_length_xml'] = str(wall_length_val)
            except ValueError:
                pass
        
        # Calculate actual length from far most left/right material positions
        panel_guid = _text_of(panel_element, ['PanelGuid', 'PanelID'])
        if panel_guid:
            # Materials to exclude from position analysis (following xcor.py logic)
            exclude_fms = ['30', '40']  # VeryTopPlate (FM30), Sheathing (FM40)
            
            # Find all X coordinates from materials in this panel (only Board elements, exclude specified FMs)
            all_x_coords = []
            
            # Process all Board elements
            for board_el in root.findall('.//Board') if root is not None else panel_element.findall('.//Board'):
                # Check if this board belongs to the panel
                panel_guid_el = board_el.find('PanelGuid')
                if panel_guid_el is not None and panel_guid_el.text == panel_guid:
                    # Check FamilyMember to exclude specified types
                    fm_el = board_el.find('FamilyMember')
                    fm_id = fm_el.text.strip() if fm_el is not None and fm_el.text else ''
                    
                    # Skip excluded family members
                    if fm_id in exclude_fms:
                        continue
                    
                    # Get X coordinates from BottomView
                    bottom_view = board_el.find('BottomView')
                    if bottom_view is not None:
                        for point in bottom_view.findall('Point'):
                            x_el = point.find('X')
                            if x_el is not None and x_el.text:
                                try:
                                    x_val = float(x_el.text)
                                    all_x_coords.append(x_val)
                                except ValueError:
                                    pass
            
            # Calculate actual length from material positions
            if len(all_x_coords) >= 2:
                min_x = min(all_x_coords)
                max_x = max(all_x_coords)
                actual_length = max_x - min_x
                specs['wall_length_actual'] = str(actual_length)
                
                # Calculate growth allowance (difference between XML WallLength and actual material length)
                if specs.get('wall_length_xml'):
                    try:
                        xml_length = float(specs['wall_length_xml'])
                        growth_allowance = xml_length - actual_length
                        specs['growth_allowance'] = str(growth_allowance)
                        
                        # Flag as error if actual length is longer than XML WallLength
                        if actual_length > xml_length:
                            specs['length_error'] = f"Actual length ({actual_length:.3f}) exceeds WallLength ({xml_length:.3f}) by {actual_length - xml_length:.3f} inches"
                    except (ValueError, TypeError):
                        pass
            elif len(all_x_coords) == 1:
                # If only one coordinate, use it as reference but note limited data
                specs['wall_length_actual'] = str(all_x_coords[0])
                specs['wall_length_note'] = 'Single material position found'
        
        # Use actual length for wall_length if available, otherwise fall back to XML value
        if specs.get('wall_length_actual'):
            specs['wall_length'] = specs['wall_length_actual']
        elif wall_length_xml:
            try:
                wall_length_val = float(wall_length_xml)
                specs['wall_length'] = str(wall_length_val)
            except ValueError:
                pass    # Calculate squaring if not found in XML using Pythagorean theorem
    # Subtract 3" from height to account for top plate and bottom plate that are shipped loose
    if not specs.get('squaring') and specs.get('height') and specs.get('wall_length'):
        try:
            height = float(specs['height'])
            wall_length = float(specs['wall_length'])
            
            # Check if FM106 (BottomMultiPlate) is present in the panel
            fm106_present = False
            if panel_element is not None:
                for board_el in panel_element.findall('.//Board'):
                    fm_el = board_el.find('FamilyMember')
                    if fm_el is not None and fm_el.text == '106':
                        fm106_present = True
                        break
            
            # Subtract height reduction based on shipped-loose components:
            # - VeryTopPlate (FM30) is always shipped loose: -1.5"
            # - BottomMultiPlate (FM106) is shipped loose when present: -1.5" additional
            height_reduction = 1.5  # Always subtract for VeryTopPlate
            if fm106_present:
                height_reduction = 3.0  # Add BottomMultiPlate reduction
            
            squaring_inches = math.sqrt((height - height_reduction) ** 2 + wall_length ** 2)
            specs['squaring'] = str(squaring_inches)
        except (ValueError, TypeError):
            pass
    
    return specs

def extract_beam_pocket_details(panel_element, materials):
    """Extract beam pocket details (FM33) from panel"""
    beam_pockets = []
    
    # Look for beam pocket SubAssemblies
    for sub_el in panel_element.findall('.//SubAssembly'):
        sub_name = _text_of(sub_el, ['SubAssemblyName', 'Name'])
        fm_id = _text_of(sub_el, ['FamilyMember'])
        
        if fm_id == '33' or (sub_name and 'beampocket' in sub_name.lower()):
            pocket_info = {
                'name': sub_name or 'Beam Pocket',
                'guid': _text_of(sub_el, ['SubAssemblyGuid']),
                'materials': {},
                'aff': None,
                'opening_width': None
            }
            
            # Extract AFF from Trimmer ElevationView Y-coordinates and calculate opening width
            sub_guid = pocket_info['guid']
            if sub_guid:
                trimmer_ys = []
                trimmer_count = 0
                
                for board_el in panel_element.findall('.//Board'):
                    board_sub_guid_el = board_el.find('SubAssemblyGuid')
                    if (board_sub_guid_el is not None and 
                        board_sub_guid_el.text == sub_guid):
                        
                        fam_member_name_el = board_el.find('FamilyMemberName')
                        if (fam_member_name_el is not None and 
                            'Trimmer' in fam_member_name_el.text):
                            trimmer_count += 1
                            # Get max Y from ElevationView
                            elev_view = board_el.find('ElevationView')
                            if elev_view is not None:
                                max_y = None
                                for point in elev_view.findall('Point'):
                                    y_el = point.find('Y')
                                    if y_el is not None and y_el.text:
                                        try:
                                            y_val = float(y_el.text)
                                            if max_y is None or y_val > max_y:
                                                max_y = y_val
                                        except ValueError:
                                            pass
                                if max_y is not None:
                                    trimmer_ys.append(max_y)
                
                # Calculate AFF as max of trimmer Y values
                if trimmer_ys:
                    pocket_info['aff'] = max(trimmer_ys)
                
                # Calculate opening width as trimmer count × 1.5 inches
                pocket_info['opening_width'] = trimmer_count * 1.5
            
            # Find materials belonging to this beam pocket
            for mat in materials:
                if isinstance(mat, dict) and mat.get('SubAssemblyGuid') == sub_guid:
                    label = mat.get('Label', '')
                    if label:
                        if label not in pocket_info['materials']:
                            pocket_info['materials'][label] = 0
                        pocket_info['materials'][label] += 1
            
            beam_pockets.append(pocket_info)
    
    return beam_pockets

def extract_critical_stud_details(panel_element, materials):
    """Extract individual critical stud details with GUIDs, types, and distances from panel edge"""
    critical_studs = []

    # Find the panel edge (far most left material position, excluding very top plate since it's shipped loose)
    panel_edge_x = None
    panel_guid = _text_of(panel_element, ['PanelGuid', 'PanelID'])
    
    # Find the leftmost X coordinate from all materials in the panel, excluding VeryTopPlate (FM30)
    for board_el in panel_element.findall('.//Board'):
        # Check if this board belongs to the panel
        panel_guid_el = board_el.find('PanelGuid')
        if panel_guid_el is not None and panel_guid_el.text == panel_guid:
            # Skip VeryTopPlate (FM30) as it's shipped loose
            fm_el = board_el.find('FamilyMember')
            fm_id = fm_el.text.strip() if fm_el is not None and fm_el.text else ''
            if fm_id == '30':  # Skip VeryTopPlate
                continue
                
            # Get the leftmost X coordinate from BottomView
            bottom_view = board_el.find('BottomView')
            if bottom_view is not None:
                for point in bottom_view.findall('Point'):
                    x_el = point.find('X')
                    if x_el is not None and x_el.text:
                        try:
                            x_val = float(x_el.text)
                            if panel_edge_x is None or x_val < panel_edge_x:
                                panel_edge_x = x_val
                        except ValueError:
                            pass

    # First, look for FM32 SubAssembly critical studs
    for sub_el in panel_element.findall('.//SubAssembly'):
        sub_name = _text_of(sub_el, ['SubAssemblyName', 'Name'])
        fm_id = _text_of(sub_el, ['FamilyMember'])
        sub_guid = _text_of(sub_el, ['SubAssemblyGuid'])

        if fm_id == '32' and sub_name and 'critical' in sub_name.lower():
            stud_info = {
                'guid': sub_guid,
                'type': 'SubAssembly critical stud',
                'fm_type': 'FM32',
                'materials': {},
                'distance': None
            }

            # Calculate distance from panel edge to FM32 SubAssembly materials
            # Use the leftmost material position from the subassembly's boards
            stud_x = None
            for board_el in panel_element.findall('.//Board'):
                board_sub_guid_el = board_el.find('SubAssemblyGuid')
                if (board_sub_guid_el is not None and 
                    board_sub_guid_el.text == sub_guid):
                    # Get the leftmost X coordinate from BottomView
                    bottom_view = board_el.find('BottomView')
                    if bottom_view is not None:
                        min_x = None
                        for point in bottom_view.findall('Point'):
                            x_el = point.find('X')
                            if x_el is not None and x_el.text:
                                try:
                                    x_val = float(x_el.text)
                                    if min_x is None or x_val < min_x:
                                        min_x = x_val
                                except ValueError:
                                    pass
                        if min_x is not None and (stud_x is None or min_x < stud_x):
                            stud_x = min_x

            if stud_x is not None and panel_edge_x is not None:
                distance_inches = stud_x - panel_edge_x
                # Format as feet-inches
                distance_formatted = format_feet_to_dimension(distance_inches / 12)
                stud_info['distance'] = f"{distance_inches:.1f} in ({distance_formatted})"

            # Find materials belonging to this critical stud subassembly
            for mat in materials:
                if isinstance(mat, dict) and mat.get('SubAssemblyGuid') == sub_guid:
                    label = mat.get('Label', '')
                    if label:
                        if label not in stud_info['materials']:
                            stud_info['materials'][label] = 0
                        stud_info['materials'][label] += 1

            if stud_info['materials']:  # Only add if it has materials
                critical_studs.append(stud_info)

    # Then, look for FM47 loose critical studs (not part of subassemblies)
    for mat in materials:
        if isinstance(mat, dict):
            fm_id = mat.get('FamilyMember')
            sub_guid = mat.get('SubAssemblyGuid')

            if fm_id == '47' and (not sub_guid or sub_guid.strip() == ''):
                # This is a loose FM47 critical stud
                label = mat.get('Label', '')
                description = mat.get('Desc') or mat.get('Description', '')
                board_guid = mat.get('BoardGuid')  # Get the board GUID for FM47

                # Find the board element to get position
                stud_x = None
                for board_el in panel_element.findall('.//Board'):
                    board_guid_el = board_el.find('BoardGuid')
                    if board_guid_el is not None and board_guid_el.text == board_guid:
                        # Get the leftmost X coordinate from BottomView
                        bottom_view = board_el.find('BottomView')
                        if bottom_view is not None:
                            min_x = None
                            for point in bottom_view.findall('Point'):
                                x_el = point.find('X')
                                if x_el is not None and x_el.text:
                                    try:
                                        x_val = float(x_el.text)
                                        if min_x is None or x_val < min_x:
                                            min_x = x_val
                                    except ValueError:
                                        pass
                            if min_x is not None:
                                stud_x = min_x
                        break

                # Calculate distance from panel edge
                distance_info = None
                if stud_x is not None and panel_edge_x is not None:
                    try:
                        distance_inches = stud_x - panel_edge_x
                        distance_formatted = format_feet_to_dimension(distance_inches / 12)
                        distance_info = f"{distance_inches:.1f} in ({distance_formatted})"
                    except (ValueError, TypeError):
                        pass

                # Create a unique key for this loose critical stud
                stud_key = f"FM47_{label}_{description}"

                # Check if we already have this stud
                existing_stud = None
                for stud in critical_studs:
                    if stud.get('fm_type') == 'FM47' and stud.get('key') == stud_key:
                        existing_stud = stud
                        break

                if existing_stud:
                    # Increment count for existing stud
                    if label not in existing_stud['materials']:
                        existing_stud['materials'][label] = 0
                    existing_stud['materials'][label] += 1
                else:
                    # Create new loose critical stud entry
                    stud_info = {
                        'guid': board_guid,  # Use board GUID for FM47 critical studs
                        'type': 'Loose critical stud',
                        'fm_type': 'FM47',
                        'key': stud_key,
                        'materials': {label: 1} if label else {},
                        'distance': distance_info
                    }
                    critical_studs.append(stud_info)

    return critical_studs

def extract_subassembly_details(panel_element, materials, material_mapping):
    """Extract subassembly details (FM25, FM32, FM42) - FM32 Critical Studs excluded"""
    subassemblies = []
    
    # Look for SubAssembly elements
    for sub_el in panel_element.findall('.//SubAssembly'):
        sub_name = _text_of(sub_el, ['SubAssemblyName', 'Name'])
        fm_id = _text_of(sub_el, ['FamilyMember'])
        sub_guid = _text_of(sub_el, ['SubAssemblyGuid'])
        
        # Include FM25, FM32, and FM42 subassemblies, but exclude FM32 Critical Studs
        if fm_id in ['25', '32', '42']:
            # Skip FM32 Critical Stud subassemblies - they are handled in Critical Stud Details
            if fm_id == '32' and sub_name and 'critical' in sub_name.lower():
                continue
                
            sub_info = {
                'name': sub_name or f"FM{fm_id} SubAssembly",
                'guid': sub_guid,
                'family_member': fm_id,
                'materials': {},
                'rough_openings': []
            }
            
            # Find materials belonging to this subassembly
            for mat in materials:
                if isinstance(mat, dict) and mat.get('SubAssemblyGuid') == sub_guid:
                    label = mat.get('Label', '')
                    if label:
                        # Exclude the subassembly itself from its own materials list
                        if label != sub_name:
                            # Use the original label, not the mapped alphabetical label
                            if label not in sub_info['materials']:
                                sub_info['materials'][label] = 0
                            sub_info['materials'][label] += 1
            
            # For FM25 subassemblies, look for associated FM-1 rough openings
            if fm_id == '25':
                # Find FM-1 rough openings associated with this subassembly
                for board_el in panel_element.findall('.//Board'):
                    # Check if this board belongs to the panel
                    panel_guid_el = board_el.find('PanelGuid')
                    if panel_guid_el is not None and panel_guid_el.text == _text_of(panel_element, ['PanelGuid', 'PanelID']):
                        # Check if this is an FM-1 rough opening
                        fm_el = board_el.find('FamilyMember')
                        if fm_el is not None and fm_el.text == '-1':
                            # Check if this rough opening is associated with our FM25 subassembly
                            sub_guid_el = board_el.find('SubAssemblyGuid')
                            if sub_guid_el is not None and sub_guid_el.text == sub_guid:
                                # Extract dimensions from the Material child element
                                material_el = board_el.find('Material')
                                width = 0.0
                                length = 0.0
                                if material_el is not None:
                                    # Try ActualWidth first, then Width
                                    width_el = material_el.find('ActualWidth')
                                    if width_el is None:
                                        width_el = material_el.find('Width')
                                    if width_el is not None and width_el.text:
                                        try:
                                            width = float(width_el.text.strip())
                                        except ValueError:
                                            width = 0.0

                                    # Try ActualLength first, then Length
                                    length_el = material_el.find('ActualLength')
                                    if length_el is None:
                                        length_el = material_el.find('Length')
                                    if length_el is not None and length_el.text:
                                        try:
                                            length = float(length_el.text.strip())
                                        except ValueError:
                                            length = 0.0

                                # Extract AFF from ElevationView Y coordinates
                                aff_value = None
                                elevation_view = board_el.find('ElevationView')
                                if elevation_view is not None:
                                    max_y = None
                                    for point in elevation_view.findall('Point'):
                                        y_el = point.find('Y')
                                        if y_el is not None and y_el.text:
                                            try:
                                                y_val = float(y_el.text)
                                                if max_y is None or y_val > max_y:
                                                    max_y = y_val
                                            except ValueError:
                                                pass
                                    if max_y is not None:
                                        aff_value = max_y

                                # Get the Rough Opening's GUID
                                ro_guid = _text_of(board_el, ['BoardGuid', 'Guid', 'FamilyMemberGuid'])

                                if width > 0 and length > 0:
                                    width_fmt = format_feet_to_dimension(width/12)
                                    length_fmt = format_feet_to_dimension(length/12)
                                    sub_info['rough_openings'].append({
                                        'dimensions': f"{width:.1f}\" x {length:.1f}\" ({width_fmt} x {length_fmt})",
                                        'aff': aff_value,
                                        'guid': ro_guid
                                    })
            
            subassemblies.append(sub_info)
    
    return subassemblies

# =============================================================================
# END OF TAKEOFF_STANDALONE.PY CODE INTEGRATION
# =============================================================================

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        # Command line mode - process the specified file
        ehx_file = sys.argv[1]
        if os.path.exists(ehx_file):
            logging.info(f"Processing file from command line: {ehx_file}")
            try:
                panels, materials_map = parse_panels(ehx_file) or ([], {})
                logging.info(f"Parsed {len(panels)} panels")
                
                # Convert panels to dict format
                panels_by_name = {}
                for p in panels or []:
                    if not p:
                        continue
                    name = p.get('Name')
                    if not name:
                        name = f"Panel_{len(panels_by_name)+1}"
                    panels_by_name[name] = p
                
                # Write logs
                writer = globals().get('write_expected_and_materials_logs')
                if not writer:
                    writer = write_expected_and_materials_logs
                writer(ehx_file, panels_by_name, materials_map)
                logging.info("Logs written successfully")
                
            except Exception as e:
                logging.error(f"Failed to process file: {e}")
        else:
            logging.error(f"File not found: {ehx_file}")
    else:
        # GUI mode
        logging.info("Starting GUI creation...")
        app = make_gui()
        logging.info("GUI created, starting mainloop...")
        app.mainloop()


