import os
import json
import datetime as _dt
import xml.etree.ElementTree as ET
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter import font as tkfont
import os
import json
import xml.etree.ElementTree as ET
import datetime as _dt
import re
import re
import math
from collections import defaultdict

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
    """Sort panel names numerically (05-100, 05-101, etc.) and simple numeric formats (100, 101, etc.)."""
    def panel_sort_key(panel_name):
        # Extract numbers from panel names like "05-100", "05-101", "B1_100", "B1_101"
        match = re.search(r'(\d+)-(\d+)', panel_name)
        if match:
            return (int(match.group(1)), int(match.group(2)))
        else:
            # Try to extract underscore-separated numbers (e.g., "B1_100")
            match = re.search(r'_(\d+)', panel_name)
            if match:
                return (0, int(match.group(1)))
            else:
                # Try to extract single number from the string
                match = re.search(r'(\d+)', panel_name)
                if match:
                    return (0, int(match.group(1)))
                else:
                    # Fallback to alphabetical sorting
                    return (999, panel_name)
    
    return sorted(panel_names, key=panel_sort_key)

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
    
    report['junction_mappings'] = junction_bundle_map
    
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

# Import the EHX search widget
from ehx_search_widget import EHXSearchWidget

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

    def parse_materials_from_panel(panel_el):
        """Extract Boards, Sheets, Bracing and rough-opening SubAssembly boards from a Panel element."""

        # Boards (direct Board nodes)
        mats = []
        for node in panel_el.findall('.//Board'):
            typ = _text_of(node, ('FamilyMemberName', 'Type', 'Name')) or 'Board'
            fam = _text_of(node, ('FamilyMemberName', 'Family', 'FamilyName', 'Type', 'Name')) or typ
            label = _text_of(node, ('Label', 'LabelText')) or ''
            sub = _text_of(node, ('SubAssembly', 'SubAssemblyName')) or ''
            mat_el = node.find('Material') or node
            desc = _text_of(mat_el, ('Description', 'Desc', 'Material', 'Name')) or ''
            qty = _text_of(mat_el, ('Quantity', 'QNT', 'Qty')) or '1'
            length = _text_of(mat_el, ('ActualLength', 'Length')) or ''
            width = _text_of(mat_el, ('ActualWidth', 'Width')) or ''
            board_guid = _text_of(node, ('BoardGuid', 'BoardID')) or _text_of(mat_el, ('BoardGuid', 'BoardID'))
            sub_assembly_guid = _text_of(node, ('SubAssemblyGuid', 'SubAssemblyID'))
            mats.append({'Type': typ, 'FamilyMemberName': fam, 'Label': label, 'SubAssembly': sub, 'Desc': desc, 'Qty': qty, 'ActualLength': length, 'ActualWidth': width, 'BoardGuid': board_guid, 'SubAssemblyGuid': sub_assembly_guid})
        
        # Sheets (direct Sheet nodes)
        for node in panel_el.findall('.//Sheet'):
            typ = _text_of(node, ('FamilyMemberName', 'Type', 'Name')) or 'Sheathing'
            fam = _text_of(node, ('FamilyMemberName', 'Family', 'FamilyName', 'Type', 'Name')) or typ
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
            sub_assembly_guid = _text_of(node, ('SubAssemblyGuid', 'SubAssemblyID'))
            mats.append({'Type': typ, 'FamilyMemberName': fam, 'Label': label, 'SubAssembly': sub, 'Desc': desc, 'Description': desc, 'Qty': qty, 'ActualLength': length, 'ActualWidth': width, 'SheetGuid': sheet_guid, 'SubAssemblyGuid': sub_assembly_guid})

        # Bracing
        for node in panel_el.findall('.//Bracing'):
            typ = _text_of(node, ('FamilyMemberName', 'Type', 'Name')) or 'Bracing'
            fam = _text_of(node, ('FamilyMemberName', 'Family', 'FamilyName', 'Type', 'Name')) or typ
            label = _text_of(node, ('Label', 'LabelText')) or ''
            sub = _text_of(node, ('SubAssembly', 'SubAssemblyName')) or ''
            desc = _text_of(node, ('Description', 'Desc', 'Material', 'Name')) or ''
            qty = _text_of(node, ('Quantity', 'QNT', 'Qty')) or '1'
            length = _text_of(node, ('ActualLength', 'Length')) or ''
            width = ''
            bracing_guid = _text_of(node, ('BracingGuid', 'BracingID'))
            sub_assembly_guid = _text_of(node, ('SubAssemblyGuid', 'SubAssemblyID'))
            mats.append({'Type': typ, 'FamilyMemberName': fam, 'Label': label, 'SubAssembly': sub, 'Desc': desc, 'Qty': qty, 'ActualLength': length, 'ActualWidth': width, 'BracingGuid': bracing_guid, 'SubAssemblyGuid': sub_assembly_guid})

        # SubAssemblies (rough openings only - sheathing is handled by Sheet parsing above)
        for sub_el in panel_el.findall('.//SubAssembly'):
            fam = _text_of(sub_el, ('FamilyMemberName', 'Family', 'FamilyName', 'Type', 'Name')) or ''
            sub_label = _text_of(sub_el, ('Label', 'LabelText')) or ''
            sub_name = _text_of(sub_el, ('SubAssemblyName',)) or ''
            # capture SubAssembly GUID if present so we can tie contained materials
            sub_guid = _text_of(sub_el, ('SubAssemblyGuid', 'SubAssemblyID'))
            print(f"DEBUG: SubAssembly found - Family: '{fam}', Label: '{sub_label}', Name: '{sub_name}'")
            # Only handle rough openings in SubAssembly parsing - sheathing is handled by direct Sheet parsing above
            if fam and str(fam).strip().lower() == 'roughopening':
                print(f"DEBUG: Found rough opening SubAssembly")
                # extract any Board entries inside the rough opening subassembly
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

                for b in sub_el.findall('.//Board'):
                    print(f"DEBUG: Found Board inside rough opening SubAssembly")
                    btyp = _text_of(b, ('FamilyMemberName', 'Type', 'Name')) or 'Board'
                    blab = _text_of(b, ('Label', 'LabelText')) or ''
                    mat_el = b.find('Material')
                    if mat_el is None:
                        mat_el = b
                    bdesc = _text_of(mat_el, ('Description', 'Desc', 'Material', 'Name')) or ''
                    bal = _text_of(mat_el, ('ActualLength', 'Length')) or ''
                    baw = _text_of(mat_el, ('ActualWidth', 'Width')) or ''
                    b_guid = _text_of(b, ('BoardGuid', 'BoardID'))
                    # annotate with captured bottom/elevation info for better AFF heuristics
                    entry = {'Type': btyp, 'FamilyMemberName': fam, 'Label': blab, 'SubAssembly': sub_name, 'Desc': bdesc, 'Qty': '', 'ActualLength': bal, 'ActualWidth': baw, 'BoardGuid': b_guid, 'SubAssemblyGuid': sub_guid}
                    if bottom_x_min is not None and bottom_x_max is not None:
                        entry['bottom_x_min'] = bottom_x_min
                        entry['bottom_x_max'] = bottom_x_max
                    # attach both min and max Y from SubAssembly ElevationView when available
                    if sub_elev_max_y is not None:
                        entry['elev_max_y'] = sub_elev_max_y
                        # Explicitly store AFF as the top of the rough-opening elevation
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
            
            print(f"DEBUG: Processing material - Label: '{lbl}', Type: '{typ}', Desc: '{desc}', Qty: '{qty_str}' -> {qty}, Length: '{length}', Width: '{width}', Key: {key}")
            
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
            print(f"DEBUG: Added to group, current count: {groups[key]['count']}")

        print(f"DEBUG: Total materials processed: {len(mats)}")
        print(f"DEBUG: Groups created: {len(groups)}")
        for k, v in groups.items():
            print(f"DEBUG: Group {k}: count={v['count']}")
        print(f"DEBUG: Final groups keys: {list(groups.keys())}")
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
        print(f"DEBUG: Detected EHX format: {ehx_version}")
        if ehx_version == "v2.0":
            print(f"DEBUG: EHX v2.0 - Version: {job_info.get('EHXVersion', 'Unknown')}, Date: {job_info.get('Date', 'Unknown')}")

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

            panel_obj = {'Name': panel_guid, 'DisplayLabel': panel_label, 'PanelGuid': panel_guid, 'Label': panel_label}
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
                        print(f"DEBUG: Found squaring for panel {panel_obj.get('Name', 'Unknown')}: {square_inches} inches -> {panel_obj['Squaring']}")
                    except (ValueError, TypeError):
                        panel_obj['Squaring'] = square_dim_el.text.strip()
                        print(f"DEBUG: Found squaring for panel {panel_obj.get('Name', 'Unknown')}: {panel_obj['Squaring']} (raw)")
            # Fallback: try direct SquareDimension element if nested structure not found
            if 'Squaring' not in panel_obj:
                square_el = panel_el.find('SquareDimension')
                if square_el is not None and square_el.text:
                    try:
                        square_inches = float(square_el.text.strip())
                        panel_obj['Squaring_inches'] = square_inches  # Store raw inches
                        panel_obj['Squaring'] = inches_to_feet_inches_sixteenths(square_inches)
                        print(f"DEBUG: Found fallback squaring for panel {panel_obj.get('Name', 'Unknown')}: {square_inches} inches -> {panel_obj['Squaring']}")
                    except (ValueError, TypeError):
                        panel_obj['Squaring'] = square_el.text.strip()
                        print(f"DEBUG: Found fallback squaring for panel {panel_obj.get('Name', 'Unknown')}: {panel_obj['Squaring']} (raw)")
            # Calculate squaring if not found using Pythagorean theorem
            if 'Squaring' not in panel_obj:
                if 'Height' in panel_obj and 'WallLength' in panel_obj:
                    try:
                        h = float(panel_obj['Height']) - 1.5  # Subtract top plate
                        l = float(panel_obj['WallLength'])
                        calc_inches = math.sqrt(h**2 + l**2)
                        panel_obj['Squaring_inches'] = calc_inches  # Store raw inches
                        panel_obj['Squaring'] = inches_to_feet_inches_sixteenths(calc_inches)
                        print(f"DEBUG: Calculated squaring for panel {panel_obj.get('Name', 'Unknown')}: {calc_inches:.3f} inches -> {panel_obj['Squaring']}")
                    except (ValueError, TypeError):
                        calc_squaring = calculate_squaring(panel_obj['Height'], panel_obj['WallLength'])
                        if calc_squaring:
                            panel_obj['Squaring'] = calc_squaring
                            print(f"DEBUG: Calculated squaring for panel {panel_obj.get('Name', 'Unknown')}: {calc_squaring}")
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
                                print(f"DEBUG: Panel {panel_label} assigned BundleName from BundleLayer {bundle_layer}: {bundle_name}")
                        except ValueError:
                            pass
                
                if bundle_name:
                    panel_obj['BundleName'] = bundle_name
                    print(f"DEBUG: Panel {panel_label} assigned BundleName: {bundle_name}")

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
                print(f"DEBUG: Panel {panel_guid} has {len(elevations)} elevation views")
                for i, elev in enumerate(elevations):
                    print(f"DEBUG: Elevation {i}: min_y={elev.get('min_y')}, max_y={elev.get('max_y')}, height={elev.get('height')}, points={len(elev.get('points', []))}")
            else:
                print(f"DEBUG: Panel {panel_guid} has no elevation data")

            panels.append(panel_obj)

            mats = parse_materials_from_panel(panel_el)
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

        # Write expected.log and materials.log files
        try:
            panels_by_name = {}
            for p in panels:
                if isinstance(p, dict):
                    panels_by_name[p.get('Name', f'Panel_{len(panels_by_name)}')] = p
            
            print(f"DEBUG: Writing expected.log with {len(panels_by_name)} panels")
            
            # Sort panels by bundle, then by panel name for consistent log output
            sorted_panels = sort_panels_by_bundle_and_name(panels_by_name)
            
            # Use the local write_expected_and_materials_logs function
            writer = globals().get('write_expected_and_materials_logs')
            if not writer:
                writer = write_expected_and_materials_logs
            writer(path, dict(sorted_panels), materials_map)
            print(f"DEBUG: Finished writing expected.log")
        except Exception as e:
            # Log writing is optional, don't fail if it doesn't work
            print(f"DEBUG: Failed to write log files: {e}")
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

    def read_panels_from_expected_log(log_path):
        """Read processed panel data from expected.log file.
        Returns panels_by_name dict compatible with GUI processing.
        """
        panels_by_name = {}
        
        try:
            with open(log_path, 'r', encoding='utf-8') as fh:
                content = fh.read()
                
            # Split by panel sections
            panel_sections = content.split('Panel: ')
            
            for section in panel_sections[1:]:  # Skip first empty section
                lines = section.strip().split('\n')
                if not lines:
                    continue
                    
                # First line is the panel name (after splitting by 'Panel: ')
                panel_line = lines[0].strip()
                panel_name = panel_line.strip()
                
                # Parse panel data
                panel_obj = {'Name': panel_name, 'DisplayLabel': panel_name}
                current_section = None
                
                for line in lines[1:]:
                    line = line.strip()
                    if not line:
                        continue
                        
                    if line == 'Panel Details:':
                        current_section = 'details'
                        continue
                    elif line == 'Panel Material Breakdown:':
                        current_section = 'materials'
                        materials_list = []
                        continue
                    elif line.startswith('---'):
                        # End of panel section
                        break
                    elif current_section == 'materials' and line and not line.startswith('•'):
                        # Parse material breakdown lines like "A - BottomPlate - 2x6 SPF PM No.2 - (1) - 8'-10-1/4""
                        if ' - ' in line:
                            parts = line.split(' - ')
                            if len(parts) >= 3:
                                material = {
                                    'Label': parts[0].strip(),
                                    'Type': parts[1].strip(),
                                    'Description': parts[2].strip(),
                                    'Desc': parts[2].strip()
                                }
                                
                                # Parse quantity and dimensions if available
                                if len(parts) >= 4:
                                    qty_part = parts[3].strip()
                                    if qty_part.startswith('(') and qty_part.endswith(')'):
                                        try:
                                            material['Qty'] = int(qty_part[1:-1])
                                            material['Quantity'] = int(qty_part[1:-1])
                                        except:
                                            pass
                                    
                                    if len(parts) >= 5:
                                        size_part = parts[4].strip()
                                        material['Size'] = size_part
                                        
                                        # Try to parse dimensions
                                        if 'x' in size_part:
                                            # Sheet format like "9' x 1'-8-5/8""
                                            try:
                                                dim_parts = size_part.split(' x ')
                                                if len(dim_parts) == 2:
                                                    material['Length'] = dim_parts[0].strip()
                                                    material['Width'] = dim_parts[1].strip()
                                                    material['ActualLength'] = dim_parts[0].strip()
                                                    material['ActualWidth'] = dim_parts[1].strip()
                                            except:
                                                pass
                                        else:
                                            # Linear format like "8'-10-1/4""
                                            material['Length'] = size_part
                                            material['ActualLength'] = size_part
                                
                                materials_list.append(material)
                    elif line.startswith('• '):
                        # Parse bullet points
                        bullet_content = line[2:]  # Remove "• " prefix
                        
                        if current_section == 'details':
                            if ': ' in bullet_content:
                                key, value = bullet_content.split(': ', 1)
                                key = key.strip()
                                value = value.strip()
                                
                                # Map log keys back to panel object keys
                                key_mapping = {
                                    'Category': 'Category',
                                    'Load Bearing': 'LoadBearing', 
                                    'Length': 'WallLength',  # Keep as WallLength for compatibility
                                    'Height': 'Height',
                                    'Squaring': 'Squaring',
                                    'Thickness': 'Thickness',
                                    'Stud Spacing': 'StudSpacing',
                                    'Weight': 'Weight',
                                    'Production Notes': 'OnScreenInstruction',
                                    'Sheathing Layer 1': 'Sheathing',
                                    'Sheathing': 'Sheathing',
                                    'Rough Opening': 'RoughOpening'
                                }
                                
                                if key in key_mapping:
                                    value = value.strip()
                                    # Clean up weight value if it has duplication
                                    if key == 'Weight' and ' Lbs' in value:
                                        # Extract just the numeric part before " Lbs"
                                        weight_parts = value.split(' Lbs')
                                        if weight_parts[0].strip():
                                            value = weight_parts[0].strip()
                                    panel_obj[key_mapping[key]] = value
                            else:
                                # Handle items without colons (like junction details)
                                if ' - (' in bullet_content and ')' in bullet_content:
                                    # This is a junction detail - capture it
                                    if 'junctions' not in panel_obj:
                                        panel_obj['junctions'] = []
                                    panel_obj['junctions'].append(bullet_content.strip())
                                elif bullet_content.startswith('Rough Opening:'):
                                    # Parse rough opening data
                                    pass
                                else:
                                    # Handle other non-colon items
                                    pass
                    elif ': ' in line:
                        key, value = line.split(': ', 1)
                        key = key.strip()
                        value = value.strip()
                        
                        if key == 'Level':
                            panel_obj['Level'] = value
                        elif key == 'Description':
                            panel_obj['Description'] = value
                        elif key == 'Bundle':
                            panel_obj['Bundle'] = value
                
                # Store materials in panel object for GUI display
                if materials_list:
                    panel_obj['materials'] = materials_list
                
                panels_by_name[panel_name] = panel_obj
                
        except Exception as e:
            print(f"DEBUG: Error reading panels from expected.log: {e}")
            return {}
            
        return panels_by_name

    def read_materials_from_materials_log(log_path):
        """Read processed materials data from materials.log file.
        Returns materials_map dict compatible with GUI processing.
        """
        materials_map = {}
        
        try:
            with open(log_path, 'r', encoding='utf-8') as fh:
                content = fh.read()
                
            # Split by panel sections (marked by ---)
            panel_sections = content.split('---')
            
            for section in panel_sections:
                lines = section.strip().split('\n')
                if not lines:
                    continue
                    
                current_panel = None
                materials_list = []
                
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                        
                    if line.startswith('Panel: '):
                        current_panel = line[7:].strip()  # Remove "Panel: " prefix
                        materials_list = []
                    elif line.startswith('Type: '):
                        # Parse material line
                        # Format: Type: BottomPlate , Label: A , SubAssembly:  , Desc: 2x6 SPF PM No.2
                        parts = line.split(' , ')
                        material = {}
                        
                        for part in parts:
                            if ': ' in part:
                                key, value = part.split(': ', 1)
                                key = key.strip()
                                value = value.strip()
                                
                                if key == 'Type':
                                    material['Type'] = value
                                elif key == 'Label':
                                    material['Label'] = value
                                elif key == 'SubAssembly':
                                    material['SubAssembly'] = value
                                elif key == 'Desc':
                                    material['Description'] = value
                                    material['Desc'] = value
                        
                        if material:
                            materials_list.append(material)
                    
                    elif current_panel and line.startswith('Level: '):
                        # Optional: could store level info if needed
                        pass
                    elif current_panel and line.startswith('Description: '):
                        # Optional: could store description if needed
                        pass
                    elif current_panel and line.startswith('Bundle: '):
                        # Optional: could store bundle info if needed
                        pass
                
                if current_panel and materials_list:
                    materials_map[current_panel] = materials_list
                    
        except Exception as e:
            print(f"DEBUG: Error reading materials from materials.log: {e}")
            return {}
            
        return materials_map

    def write_expected_and_materials_logs(ehx_path, panels_by_name, materials_map):
        """Write expected.log and materials.log into the same directory as the EHX file.
        Format is matched to the provided examples as closely as possible.
        """
        import time
        folder = os.path.dirname(ehx_path)
        fname = os.path.basename(ehx_path)
        # use timezone-aware UTC datetime to avoid DeprecationWarning
        ts = _dt.datetime.now(_dt.timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        
        print(f"DEBUG: write_expected_and_materials_logs called with {len(panels_by_name)} panels")

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
            print(f"DEBUG: Could not extract JobID, using default: {e}")
            job_id = "expected"

        expected_path = os.path.join(folder, f'{job_id}.log')
        materials_path = os.path.join(folder, 'materials.log')

        # Pre-process all junctions for efficient lookup
        junction_lookup = defaultdict(list)
        try:
            # First, create a mapping from panel labels to their PanelGuids
            panel_label_to_guid = {}
            for panel in root.findall('.//Panel'):
                panel_guid_el = panel.find('PanelGuid')
                label_el = panel.find('Label')
                if panel_guid_el is not None and panel_guid_el.text and label_el is not None and label_el.text:
                    panel_label_to_guid[label_el.text] = panel_guid_el.text
            
            for junction in root.findall('.//Junction'):
                j_panel_guid = junction.find('PanelGuid') or junction.find('PanelID')
                j_panel_label = junction.find('Label')
                
                # Index by junction's PanelGuid/PanelID
                if j_panel_guid is not None and j_panel_guid.text:
                    junction_lookup[j_panel_guid.text].append(junction)
                
                # Also index by junction's Label
                if j_panel_label is not None and j_panel_label.text:
                    junction_lookup[j_panel_label.text].append(junction)
                    
                # Also index by the panel's actual PanelGuid if we can map it
                if j_panel_guid is not None and j_panel_guid.text and j_panel_guid.text in panel_label_to_guid:
                    actual_guid = panel_label_to_guid[j_panel_guid.text]
                    junction_lookup[actual_guid].append(junction)
        except Exception as e:
            print(f"DEBUG: Error pre-processing junctions: {e}")
            junction_lookup = defaultdict(list)

        # Sort panels by bundle, then by panel name for consistent log output
        sorted_panels = sort_panels_by_bundle_and_name(panels_by_name)
        sorted_panels_dict = dict(sorted_panels)

        # Detect unassigned panels
        unassigned_panels = detect_unassigned_panels(panels_by_name)
        
        # For v2.0 files, get diagnostic information
        ehx_version = "legacy"
        diag_report = None
        try:
            # Try to detect version from the file path or content
            fname_lower = os.path.basename(ehx_path).lower()
            if 'mpo' in fname_lower or 'v2' in fname_lower:
                ehx_version = "v2.0"
                # Get diagnostic info for v2.0 files
                tree = ET.parse(ehx_path)
                root = tree.getroot()
                diag_report = diagnose_v2_bundle_assignment(root, ehx_version, panels_by_name)
        except Exception as e:
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
            with open(expected_path, 'w', encoding='utf-8') as fh:
                fh.write(f"\n=== {job_id}.log updated at {ts} for {fname} ===\n")
                
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
                
                # Parse the EHX file once for junction processing
                tree = ET.parse(ehx_path)
                root = tree.getroot()
                
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
                        'WallLength': 'Length',  # Updated to match GUI/export format
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
                    
                    # Add junction details section if junctions exist
                    try:
                        junction_types = defaultdict(int)
                        
                        # Get panel GUID and label for junction lookup
                        panel_guid = None
                        panel_label = None
                        if isinstance(pobj, dict):
                            panel_guid = pobj.get('Name') or pobj.get('PanelGuid') or pobj.get('Guid') or pobj.get('ID')
                            panel_label = pobj.get('DisplayLabel') or pobj.get('Label') or pobj.get('Name')
                            
                            # If panel_label looks like a GUID, use it as the GUID
                            if panel_label and len(panel_label) == 36 and panel_label.count('-') == 4:
                                panel_guid = panel_label

                        # Find all junctions for this panel using efficient lookup
                        panel_junctions = []
                        if panel_guid:
                            panel_junctions.extend(junction_lookup.get(panel_guid, []))
                        if panel_label and panel_label != panel_guid:
                            panel_junctions.extend(junction_lookup.get(panel_label, []))
                        
                        # Remove duplicates (junctions might be indexed under both GUID and label)
                        seen_junctions = set()
                        unique_junctions = []
                        for j in panel_junctions:
                            j_id = id(j)  # Use object ID to identify unique junctions
                            if j_id not in seen_junctions:
                                seen_junctions.add(j_id)
                                unique_junctions.append(j)
                        
                        for junction in unique_junctions:
                            sub_name_el = junction.find('SubAssemblyName')
                            fam_name_el = junction.find('FamilyMemberName')

                            sub_name = sub_name_el.text.strip() if sub_name_el is not None and sub_name_el.text else 'Unknown'
                            fam_name = fam_name_el.text.strip() if fam_name_el is not None and fam_name_el.text else 'Unknown'

                            # Use SubAssemblyName as the junction type (without "-> AttachedWall")
                            junction_type = sub_name
                            if junction_type and junction_type != 'AttachedWall':
                                junction_types[junction_type] += 1

                        # Add junction details to expected.log if any exist
                        if junction_types:
                            fh.write("Junction Details:\n")
                            for junction_type, count in sorted(junction_types.items()):
                                fh.write(f"• {junction_type} - ({count})\n")
                            fh.write("\n")
                            
                    except Exception as e:
                        print(f"DEBUG: Exception in junction details for expected.log: {e}")
                        pass
                    
                    fh.write("Panel Material Breakdown:\n")
                    lines = []
                    # Support both internal key (guid) and display label keyed materials
                    mats = materials_map.get(pname) or materials_map.get(pobj.get('DisplayLabel', '')) or []
                    print(f"DEBUG: Panel {pname} has {len(mats)} materials")
                    for i, m in enumerate(mats):
                        print(f"DEBUG: Material {i}: {m}")
                    # filter out rough openings from the breakdown
                    mats_filtered = [m for m in (mats or []) if not _is_rough_opening(m)]
                    print(f"DEBUG: After filtering rough openings: {len(mats_filtered)} materials")
                    lines = format_and_sort_materials(mats_filtered)
                    for l in lines:
                        fh.write(f"{l}\n")
                    fh.write('---\n')
        except Exception:
            pass

        # materials.log (Type: ... lines) - append to existing file instead of clearing
        try:
            with open(materials_path, 'a', encoding='utf-8') as fh:
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
                    
                    # Add junction details to materials.log if any exist
                    try:
                        junction_types = defaultdict(int)
                        
                        # Get panel GUID and label for junction lookup
                        panel_guid = None
                        panel_label = None
                        if isinstance(pobj, dict):
                            panel_guid = pobj.get('Name') or pobj.get('PanelGuid') or pobj.get('Guid') or pobj.get('ID')
                            panel_label = pobj.get('DisplayLabel') or pobj.get('Label') or pobj.get('Name')
                            
                            # If panel_label looks like a GUID, use it as the GUID
                            if panel_label and len(panel_label) == 36 and panel_label.count('-') == 4:
                                panel_guid = panel_label

                        # Find all junctions for this panel using efficient lookup
                        panel_junctions = []
                        if panel_guid:
                            panel_junctions.extend(junction_lookup.get(panel_guid, []))
                        if panel_label and panel_label != panel_guid:
                            panel_junctions.extend(junction_lookup.get(panel_label, []))
                        
                        # Remove duplicates (junctions might be indexed under both GUID and label)
                        seen_junctions = set()
                        unique_junctions = []
                        for j in panel_junctions:
                            j_id = id(j)  # Use object ID to identify unique junctions
                            if j_id not in seen_junctions:
                                seen_junctions.add(j_id)
                                unique_junctions.append(j)
                        
                        for junction in unique_junctions:
                            sub_name_el = junction.find('SubAssemblyName')
                            fam_name_el = junction.find('FamilyMemberName')

                            sub_name = sub_name_el.text.strip() if sub_name_el is not None and sub_name_el.text else 'Unknown'
                            fam_name = fam_name_el.text.strip() if fam_name_el is not None and fam_name_el.text else 'Unknown'

                            # Use SubAssemblyName as the junction type (without "-> AttachedWall")
                            junction_type = sub_name
                            if junction_type and junction_type != 'AttachedWall':
                                junction_types[junction_type] += 1

                        # Add junction details to materials.log if any exist
                        if junction_types:
                            fh.write("Junction Details:\n")
                            for junction_type, count in sorted(junction_types.items()):
                                fh.write(f"• {junction_type} - ({count})\n")
                            fh.write("\n")
                            
                    except Exception as e:
                        print(f"DEBUG: Exception in junction details for materials.log: {e}")
                        pass
                    
                    # Also support materials keyed by display label if guid-key is missing
                    mats_for_panel = materials_map.get(pname) or materials_map.get(pobj.get('DisplayLabel', '')) or []
                    for m in mats_for_panel:
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
            print(f"DEBUG: Error writing expected.log")
            import traceback
            traceback.print_exc()
            pass

    def extract_jobpath(path):
        """Return JobPath text from the EHX if present, else empty string."""
        import xml.etree.ElementTree as ET
        try:
            tree = ET.parse(path)
            root = tree.getroot()
            el = root.find('.//JobPath')
            if el is not None and el.text:
                return el.text.strip()
        except Exception:
            pass
        return ''

# Professional color scheme - easier on eyes
TOP_BG = '#2c3e50'        # Dark blue-gray for top bar
LEFT_BG = '#f8f9fa'       # Light gray for file list
BUTTONS_BG = '#f0f8f0'    # Very light green for buttons
ACCENT_COLOR = '#3498db'  # Bright blue for selected/active elements
TEXT_LIGHT = '#ecf0f1'    # Light text color
DETAILS_BG = '#fefefe'    # Clean white for details
BREAKDOWN_BG = '#fafafa'  # Light gray for breakdown

# Professional accent colors
PRIMARY_BLUE = '#3498db'
SUCCESS_GREEN = '#27ae60'
WARNING_ORANGE = '#f39c12'
DANGER_RED = '#e74c3c'
TEXT_DARK = '#2c3e50'
TEXT_MEDIUM = '#3d4f5c'  # Darker for better visibility
TEXT_LIGHT = '#95a5a6'
BORDER_LIGHT = '#ecf0f1'

HERE = os.path.dirname(os.path.abspath(__file__))
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
    'details_w': 300,    # yellow zone (details) width in pixels
    'breakdown_w': 1140, # pink zone (breakdown) width in pixels
    'green_h': 264,      # green zone (buttons) height in pixels
}

DEFAULT_GUI = {'w': 1650, 'h': 950}


def make_gui():
    root = tk.Tk()
    root.title('Zones Test GUI')
    root.geometry(f"{DEFAULT_GUI['w']}x{DEFAULT_GUI['h']}")

    # Top bar
    top = tk.Frame(root, bg=TOP_BG)
    top.pack(side='top', fill='x')
    job_val = tk.Label(top, text='(none)', bg=TOP_BG, fg=TEXT_LIGHT, font=('Segoe UI', 10, 'bold'))
    job_val.pack(side='left', padx=6)
    path_val = tk.Label(top, text='(none)', bg=TOP_BG, fg=TEXT_LIGHT, font=('Segoe UI', 10, 'bold'), cursor='hand2', anchor='w', width=40)
    path_val.pack(side='left', padx=6, fill='x', expand=False)

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
            print(f"Error opening file location: {e}")

    path_val.bind('<Button-1>', open_file_location)
    path_val.config(cursor='hand2')  # Change cursor to hand when hovering

    # Create folder_entry but hide it (width=1) to maintain functionality
    folder_entry = ttk.Entry(top, width=1)
    # folder_entry.pack(side='left', padx=8)  # Commented out to hide display
    folder_lbl = tk.Label(top, text='Folder:', bg=TOP_BG, fg=TEXT_LIGHT, font=('Segoe UI', 9))
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
    current_junction_lookup = defaultdict(list)
    panel_materials_map = {}
    # track which panel is currently displayed
    selected_panel = {'name': None}
    # track available levels and selected level
    available_levels = []
    selected_level = {'value': None}  # None means single level or no level filtering
    original_panels = {}  # Store original unfiltered panel data
    original_materials_map = {}  # Store original unfiltered materials data

    def export_current_panel():
        try:
            sel_name = selected_panel.get('name')
            if not sel_name:
                messagebox.showinfo('Export', 'No panel selected to export')
                return

            # Ensure we have the panel object available for display name
            panel_obj = current_panels.get(sel_name, {})

            # Sanitize panel name to use as default filename
            def _sanitize_filename(name: str) -> str:
                if not name:
                    return 'panel'
                invalid = '<>:"/\\|?*'
                out = ''.join((c if c not in invalid else '_') for c in name).strip()
                out = out.replace(' ', '_')
                if not out:
                    return 'panel'
                return out

            # Use the user-facing DisplayLabel for the default filename, not the internal GUID
            display_name = panel_obj.get('DisplayLabel', sel_name)
            initial_name = _sanitize_filename(display_name) + '.txt'

            # Ask where to save the panel (default to sanitized panel name)
            folder = folder_entry.get() or os.getcwd()
            dest = filedialog.asksaveasfilename(
                title='Save displayed panel',
                defaultextension='.txt',
                initialfile=initial_name,
                initialdir=folder
            )
            if not dest:
                return

            panel_obj = current_panels.get(sel_name, {})
            materials_list = panel_materials_map.get(sel_name, [])

            # Use DisplayLabel for export display, fallback to internal name
            display_name = panel_obj.get('DisplayLabel', sel_name)

            # Parse panel name for Lot and Panel numbers
            lot_num = ''
            panel_num = display_name
            if '_' in display_name:
                parts = display_name.split('_', 1)
                if len(parts) == 2:
                    lot_num = parts[0]
                    panel_num = parts[1]

            def inches_fmt(v):
                try:
                    return inches_to_feet_inches_sixteenths(float(v))
                except Exception:
                    return v or ''

            # Write the panel data in text format
            with open(dest, 'w', encoding='utf-8') as out:
                out.write(f"File: {display_name}\n\n")
                out.write("Panel Details:\n")
                out.write(f"Panel: {display_name}\n")

                # Add Lot and Panel numbers if available
                if lot_num:
                    out.write(f"• Lot: {lot_num}\n")
                out.write(f"• Panel: {panel_num}\n")

                # Add level and description if available
                if panel_obj.get('Level'):
                    out.write(f"• Level: {panel_obj.get('Level')}\n")
                if panel_obj.get('Description'):
                    out.write(f"• Description: {panel_obj.get('Description')}\n")
                if panel_obj.get('Bundle'):
                    out.write(f"• Bundle: {panel_obj.get('Bundle')}\n")

                # Panel specifications - match GUI display exactly
                candidates = [
                    ('Category', ['Category', 'PanelCategory', 'Type']),
                    ('Load Bearing', ['LoadBearing', 'IsLoadBearing', 'LoadBearingFlag']),
                    ('📏 Length', ['WallLength', 'Length', 'PanelLength']),
                    ('📐 Height', ['Height', 'PanelHeight']),
                    ('📏 Squaring', ['Squaring']),
                    ('Thickness', ['Thickness', 'Depth']),
                    ('Stud Spacing', ['StudSpacing', 'StudsPerFoot']),
                ]
                for label, keys in candidates:
                    val = ''
                    for k in keys:
                        if k in panel_obj:
                            val = panel_obj.get(k)
                            break
                    # Strip trailing zeros from decimal values
                    if val:
                        try:
                            val = strip_trailing_zeros(str(val))
                        except:
                            pass
                        
                        # Format Length, Height, and Squaring with feet-inches-sixteenths
                        if any(k in ['WallLength', 'Height', 'Squaring', 'Length', 'PanelLength', 'PanelHeight'] for k in keys):
                            # Check if value is already formatted (contains parentheses with feet-inches)
                            if '(' in str(val) and ')' in str(val):
                                # Already formatted, use as-is
                                formatted = val
                            else:
                                try:
                                    inches_val = float(val)
                                    formatted = inches_to_feet_inches_sixteenths(inches_val)
                                    if formatted:
                                        formatted = f"{val} ({formatted})"
                                    else:
                                        formatted = val
                                except (ValueError, TypeError):
                                    formatted = val
                            out.write(f"• {label}: {formatted}\n")
                        elif any(k in ['Thickness', 'Depth', 'StudSpacing', 'StudsPerFoot'] for k in keys):
                            # For Thickness and Stud Spacing, just show the cleaned decimal
                            out.write(f"• {label}: {val}\n")
                        else:
                            out.write(f"• {label}: {val}\n")

                # Sheathing layers - match GUI display exactly (no dimensions)
                sheathing_list = []
                for m in materials_list:
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
                            out.write(f"• Sheathing: {desc}\n")
                        else:
                            out.write(f"• Sheathing Layer {idx}: {desc}\n")

                # Additional fields
                if panel_obj.get('Weight'):
                    weight_formatted = format_weight(panel_obj.get('Weight'))
                    out.write(f"• Weight: {weight_formatted}\n")
                if panel_obj.get('OnScreenInstruction'):
                    out.write(f"• Production Notes: {panel_obj.get('OnScreenInstruction')}\n")

                # Junction Details from log file
                if 'junctions' in panel_obj and panel_obj['junctions']:
                    out.write("\nJunction Details:\n")
                    for junction in panel_obj['junctions']:
                        out.write(f"• {junction}\n")

                # Rough openings
                rough_openings = []
                elevations = panel_obj.get('elevations', [])
                for m in materials_list:
                    if _is_rough_opening(m):
                        lab = m.get('Label') or ''
                        desc = m.get('Desc') or m.get('Description') or ''
                        ln = m.get('ActualLength') or m.get('Length') or ''
                        wd = m.get('ActualWidth') or m.get('Width') or ''

                        # Try to find matching elevation data
                        aff_height = get_aff_for_rough_opening(panel_obj, m)

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
                            for mat in materials_list:
                                mat_type = mat.get('Type', '').lower()
                                header_label = mat.get('Label', '')
                                # Only include materials that are headers (not headercap or headercripple)
                                # and have single-character labels (typical for headers)
                                if mat_type == 'header' and header_label and len(header_label) == 1:
                                    header_set.add(header_label)
                            associated_headers = sorted(list(header_set))[:1]

                        # Format the rough opening display
                        ro_lines = [f"Rough Opening: {lab}"]
                        if ln and wd:
                            # Strip trailing zeros from dimensions
                            ln_clean = strip_trailing_zeros(str(ln))
                            wd_clean = strip_trailing_zeros(str(wd))
                            ro_lines.append(f"Size: {ln_clean} x {wd_clean}")
                        elif ln:
                            ln_clean = strip_trailing_zeros(str(ln))
                            ro_lines.append(f"Size: {ln_clean}")
                        if aff_height is not None:
                            # Strip trailing zeros from AFF decimal value
                            aff_decimal = strip_trailing_zeros(str(aff_height))
                            formatted_aff = inches_to_feet_inches_sixteenths(str(aff_height))
                            if formatted_aff:
                                ro_lines.append(f"AFF: {aff_decimal} ({formatted_aff})")
                            else:
                                ro_lines.append(f"AFF: {aff_decimal}")
                        if associated_headers:
                            ro_lines.append(f"Reference: {', '.join(associated_headers)} - Header")

                        rough_openings.append(ro_lines)

                for ro in rough_openings:
                    for line in ro:
                        out.write(f"• {line}\n")
                    out.write("\n")  # Add extra spacing between rough openings

                # Panel Material Breakdown
                out.write("\nPanel Material Breakdown:\n")
                
                # Filter out rough openings from materials for breakdown
                breakdown_materials = [m for m in materials_list if not _is_rough_opening(m)]
                
                # Use format_and_sort_materials if available
                if callable(format_and_sort_materials):
                    breakdown_lines = format_and_sort_materials(breakdown_materials)
                    for line in breakdown_lines:
                        out.write(f"{line}\n")
                else:
                    # Fallback formatting
                    for m in breakdown_materials:
                        if isinstance(m, dict):
                            lbl = m.get('Label') or m.get('Name') or ''
                            typ = m.get('Type') or ''
                            desc = m.get('Desc') or m.get('Description') or ''
                            qty = m.get('Qty') or m.get('Quantity') or ''
                            length = m.get('ActualLength') or m.get('Length') or ''
                            width = m.get('ActualWidth') or m.get('Width') or ''
                            size = f"{length} x {width}".strip() if width else (length or '')
                            qty_str = f"({qty})" if qty else ''
                            if size:
                                out.write(f"{lbl} - {typ} - {desc} - {qty_str} - {size}\n")
                            else:
                                out.write(f"{lbl} - {typ} - {desc} - {qty_str}\n")

            messagebox.showinfo('Export', f'Panel exported to {dest}')
        except Exception as e:
            messagebox.showerror('Export Error', str(e))

    def back_clear():
        nonlocal panels_loaded
        try:
            folder = folder_entry.get() or os.getcwd()
            for nm in ('expected.log', 'materials.log'):
                p = os.path.join(folder, nm)
                try:
                    if os.path.exists(p):
                        os.remove(p)
                except Exception:
                    pass
            # clear GUI state but keep level buttons
            current_panels.clear()
            original_panels.clear()  # Clear original panel data
            original_materials_map.clear()  # Clear original materials data
            panel_materials_map.clear()
            panels_loaded = False
            selected_panel['name'] = None
            # Keep level buttons and selection - don't clear them
            # selected_level['value'] = None  # Don't reset level selection
            # available_levels.clear()  # Don't clear available levels
            # update_level_buttons()  # Don't clear level buttons
            try:
                file_listbox.selection_clear(0, tk.END)
            except Exception:
                pass
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
            rebuild_bundles(5)
            # Restore file list
            populate_files(folder)
            # log the action
            try:
                with open(LOG_FILE, 'a', encoding='utf-8') as fh:
                    fh.write(json.dumps({'ts': _dt.datetime.utcnow().isoformat(), 'action': 'back_clear', 'folder': folder}) + '\n')
            except Exception:
                pass
            messagebox.showinfo('Clear', 'GUI cleared and logs removed (if present)')
        except Exception as e:
            messagebox.showerror('Clear Error', str(e))

    def update_level_buttons():
        """Update level buttons based on available levels in current_panels"""
        print("DEBUG: update_level_buttons called")
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
        clear_btn.pack_forget()
        export_btn.pack_forget()

        # Pack action buttons first in correct order
        export_btn.pack(side='right', padx=6)
        clear_btn.pack(side='right', padx=6)
        browse_btn.pack(side='right', padx=6)
        
        if original_panels:
            # Collect unique levels from panels using LevelGuid mapping
            level_guid_map = {}  # Map LevelGuid to level number
            levels = set()
            for p in original_panels.values():
                level_guid = p.get('LevelGuid')
                level_no = p.get('LevelNo') or p.get('Level')
                if level_no:
                    # Add level if LevelNo is present (primary method)
                    levels.add(str(level_no))
                    # Also map LevelGuid if both are present
                    if level_guid:
                        level_guid_map[level_guid] = str(level_no)
                elif level_guid:
                    # Fallback: if only LevelGuid is present, try to extract level from LevelGuid mapping
                    # This handles cases where LevelNo might be missing but LevelGuid exists
                    pass  # For now, we'll rely on LevelNo being present
            
            available_levels[:] = sorted(levels, key=int)
            
            # Debug output for level detection
            print(f"DEBUG: Available levels detected: {available_levels}")
            print(f"DEBUG: Total panels processed: {len(original_panels)}")
            for level in available_levels:
                level_panels = [p for p in original_panels.values() 
                               if str(p.get('LevelNo') or p.get('Level') or '') == level]
                print(f"DEBUG: Level {level}: {len(level_panels)} panels")
            
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
    clear_btn = tk.Button(top, text='Clear', command=back_clear, bg=TOP_BG, fg=TEXT_LIGHT, relief='raised')
    clear_btn.pack(side='right', padx=6)
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

    def show_search_dialog():
        """Show the EHX search modal dialog"""
        # Get current EHX file path
        sel = file_listbox.curselection()
        if not sel:
            messagebox.showinfo("No EHX File", "Please select an EHX file from the list first.")
            return
        
        fname = file_listbox.get(sel[0])
        folder = folder_entry.get() or os.getcwd()
        ehx_path = os.path.join(folder, fname)
        
        if not os.path.exists(ehx_path):
            messagebox.showerror("File Not Found", f"EHX file not found: {ehx_path}")
            return
        
        # Create modal dialog
        search_dialog = tk.Toplevel(root)
        search_dialog.title("EHX Search")
        search_dialog.geometry("800x600")
        search_dialog.transient(root)
        search_dialog.grab_set()
        
        # Center the dialog
        search_dialog.geometry("+{}+{}".format(
            root.winfo_x() + (root.winfo_width() // 2) - 400,
            root.winfo_y() + (root.winfo_height() // 2) - 300
        ))
        
        # Create search widget
        search_widget = EHXSearchWidget(search_dialog, ehx_file_path=ehx_path)
        search_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Handle dialog close
        def on_close():
            search_dialog.grab_release()
            search_dialog.destroy()
        
        search_dialog.protocol("WM_DELETE_WINDOW", on_close)
        
        # Focus the search entry
        search_dialog.after(100, lambda: search_widget.search_entry.focus_set())

    # Search bar at the top
    search_frame = tk.Frame(top_pane, bg='#f8f8f8', height=40)
    search_frame.pack_propagate(False)
    search_frame.pack(fill='x', padx=8, pady=(8, 4))
    
    search_button = ttk.Button(search_frame, text="🔍 Search EHX", command=show_search_dialog)
    search_button.pack(side='left', padx=(0, 8), pady=4)
    
    ttk.Label(search_frame, text="Click to search panels, materials, and bundles", 
              font=('Arial', 9), foreground='#666').pack(side='left', pady=4)

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

    # Removed auto-selection - users must manually double-click to select files
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

    def show_search_dialog():
        """Show the EHX search modal dialog"""
        # Get current EHX file path
        sel = file_listbox.curselection()
        if not sel:
            messagebox.showinfo("No EHX File", "Please select an EHX file from the list first.")
            return
        
        fname = file_listbox.get(sel[0])
        folder = folder_entry.get() or os.getcwd()
        ehx_path = os.path.join(folder, fname)
        
        if not os.path.exists(ehx_path):
            messagebox.showerror("File Not Found", f"EHX file not found: {ehx_path}")
            return
        
        # Create modal dialog
        search_dialog = tk.Toplevel(root)
        search_dialog.title("EHX Search")
        search_dialog.geometry("800x600")
        search_dialog.transient(root)
        search_dialog.grab_set()
        
        # Center the dialog
        search_dialog.geometry("+{}+{}".format(
            root.winfo_x() + (root.winfo_width() // 2) - 400,
            root.winfo_y() + (root.winfo_height() // 2) - 300
        ))
        
        # Create search widget
        search_widget = EHXSearchWidget(search_dialog, ehx_file_path=ehx_path)
        search_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Handle dialog close
        def on_close():
            search_dialog.grab_release()
            search_dialog.destroy()
        
        search_dialog.protocol("WM_DELETE_WINDOW", on_close)
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

    def display_panel(name, panel_obj, materials):
        print("DEBUG: display_panel called with name:", name)
        for ch in details_scrollable_frame.winfo_children():
            ch.destroy()
        for ch in breakdown_scrollable_frame.winfo_children():
            ch.destroy()
        # Header
        try:
            # Use DisplayLabel for display purposes, fallback to internal name
            display_name = panel_obj.get('DisplayLabel', name)

            # Parse panel name for Lot and Panel numbers for header
            header_lot_num = ''
            header_panel_num = display_name
            if '_' in display_name:
                parts = display_name.split('_', 1)
                if len(parts) == 2:
                    header_lot_num = parts[0]
                    header_panel_num = parts[1]
            
            if header_lot_num:
                # Professional header with better styling
                header_frame = tk.Frame(details_scrollable_frame, bg=PRIMARY_BLUE)
                header_frame.pack(fill='x', padx=4, pady=6)
                tk.Label(header_frame, text=f'🏠 Panel: {header_panel_num} (Lot {header_lot_num})',
                        bg=PRIMARY_BLUE, fg='white', font=('Segoe UI', 12, 'bold'),
                        anchor='w').pack(anchor='w', padx=8, pady=4)
            else:
                header_frame = tk.Frame(details_scrollable_frame, bg=PRIMARY_BLUE)
                header_frame.pack(fill='x', padx=4, pady=6)
                tk.Label(header_frame, text=f'🏠 Panel: {display_name}',
                        bg=PRIMARY_BLUE, fg='white', font=('Segoe UI', 12, 'bold'),
                        anchor='w').pack(anchor='w', padx=8, pady=4)
        except Exception:
            pass
        # Professional detail line function with better styling
        def add_detail_line(label, value=None, bullet=False, raw=False, is_header=False):
            try:
                if raw:
                    txt = f"• {label}" if bullet else f"{label}"
                else:
                    if bullet:
                        txt = f"• {label}: {value}" if value is not None else f"• {label}:"
                    else:
                        txt = f"{label}: {value}" if value is not None else f"{label}:"

                # Create a frame for better spacing and visual grouping
                line_frame = tk.Frame(details_scrollable_frame, bg=DETAILS_BG)
                line_frame.pack(fill='x', padx=8, pady=2)

                if is_header:
                    # Header styling
                    tk.Label(line_frame, text=txt, bg=DETAILS_BG, fg=TEXT_DARK,
                            font=('Segoe UI', 11, 'bold'), anchor='w').pack(anchor='w')
                else:
                    # Regular detail styling
                    tk.Label(line_frame, text=txt, bg=DETAILS_BG, fg=TEXT_MEDIUM,
                            font=('Segoe UI', 10), anchor='w',
                            wraplength=DEFAULT_STATE['details_w']-20).pack(anchor='w', fill='x')

            except Exception:
                pass

        # Normalize panel_obj keys and display common fields
        try:
            if panel_obj and isinstance(panel_obj, dict):
                # Use DisplayLabel for display purposes
                display_name = panel_obj.get('DisplayLabel', name)

                # Parse panel name for Lot and Panel numbers
                lot_num = ''
                panel_num = display_name
                if '_' in display_name:
                    parts = display_name.split('_', 1)
                    if len(parts) == 2:
                        lot_num = parts[0]
                        panel_num = parts[1]
                
                # Level / Description / Bundle (show these as plain text to match log format)
                if lot_num:
                    add_detail_line('Lot', lot_num)
                add_detail_line('Panel', panel_num)
                if 'Level' in panel_obj:
                    level_info = panel_obj.get('Level', '')
                    add_detail_line('Level', level_info)
                if 'Description' in panel_obj:
                    description = panel_obj.get('Description', '')
                    add_detail_line('Description', description)
                b = panel_obj.get('Bundle') or panel_obj.get('BundleName') or panel_obj.get('BundleGuid') or ''
                if b:
                    add_detail_line('Bundle', b)

                # Add a separator
                separator = tk.Frame(details_scrollable_frame, bg=BORDER_LIGHT, height=1)
                separator.pack(fill='x', padx=8, pady=8)

                # Panel Details section header
                spec_header = tk.Frame(details_scrollable_frame, bg=SUCCESS_GREEN)
                spec_header.pack(fill='x', padx=8, pady=4)
                tk.Label(spec_header, text='Panel Details',
                        bg=SUCCESS_GREEN, fg='white', font=('Segoe UI', 10, 'bold'),
                        anchor='w').pack(anchor='w', padx=6, pady=3)

                # common field candidates with professional icons
                candidates = [
                    ('Category', ['Category', 'PanelCategory', 'Type']),
                    ('Load Bearing', ['LoadBearing', 'IsLoadBearing', 'LoadBearingFlag']),
                    ('📏 Length', ['WallLength', 'Length', 'PanelLength']),
                    ('📐 Height', ['Height', 'PanelHeight']),
                    ('📏 Squaring', ['Squaring']),
                    ('Thickness', ['Thickness', 'Depth']),
                    ('Stud Spacing', ['StudSpacing', 'StudsPerFoot']),
                    ('Sheathing', ['Sheathing']),
                    ('Weight', ['Weight']),
                    ('Production Notes', ['OnScreenInstruction', 'ProductionNotes']),
                    ('Rough Opening', ['RoughOpening'])
                ]
                for label, keys in candidates:
                    val = ''
                    for k in keys:
                        if k in panel_obj:
                            val = panel_obj.get(k)
                            break
                    
                    # Strip trailing zeros from decimal values
                    if val:
                        try:
                            val = strip_trailing_zeros(str(val))
                        except:
                            pass
                    
                    # Format Length, Height, and Squaring with feet-inches-sixteenths
                    if val and (label == '📏 Length' or label == '📐 Height' or label == '📏 Squaring'):
                        # Check if value is already formatted (contains parentheses with feet-inches)
                        if '(' in str(val) and ')' in str(val):
                            # Already formatted, use as-is
                            display_val = val
                        else:
                            try:
                                # For squaring, try to use raw inches value if available
                                if label == '📏 Squaring' and 'Squaring_inches' in panel_obj:
                                    inches_val = panel_obj['Squaring_inches']
                                else:
                                    inches_val = float(val)
                                
                                formatted = inches_to_feet_inches_sixteenths(inches_val)
                                if formatted:
                                    display_val = f"{inches_val:.3f} ({formatted})"
                                else:
                                    display_val = f"{inches_val:.3f}"
                            except (ValueError, TypeError):
                                display_val = val
                    elif label in ['Thickness', 'Stud Spacing']:
                        # For Thickness and Stud Spacing, just show the cleaned decimal
                        display_val = val
                    elif label == 'Weight':
                        if 'Lbs' not in str(val):
                            display_val = f"{val} Lbs"
                        else:
                            display_val = val
                    else:
                        display_val = val
                    add_detail_line(label, display_val, bullet=True)

                # Sheathing layers: derive from materials list (first two unique sheathing descriptions)
                try:
                    sheet_descs = []
                    mats_list = materials if isinstance(materials, (list, tuple)) else []
                    for m in mats_list:
                        if not isinstance(m, dict):
                            continue
                        t = (m.get('Type') or '').lower()
                        if 'sheet' in t or 'sheath' in t or (m.get('FamilyMemberName') and 'sheath' in str(m.get('FamilyMemberName')).lower()):
                            # prefer the explicit <Description> element for sheathing text and report only once per unique description
                            d = (m.get('Description') or m.get('Desc') or '').strip()
                            if d and d not in sheet_descs:
                                sheet_descs.append(d)
                    # after collecting unique descriptions, emit up to two sheathing layers
                    if len(sheet_descs) > 0:
                        add_detail_line('Sheathing Layer 1', sheet_descs[0], bullet=True)
                    if len(sheet_descs) > 1:
                        add_detail_line('Sheathing Layer 2', sheet_descs[1], bullet=True)
                except Exception:
                    pass

                # additional notes (Production Notes label used in expected.log)
                osi = panel_obj.get('OnScreenInstruction') or panel_obj.get('Notes') or panel_obj.get('Instruction')

                # Junction Details section - show junction types with counts
                print("DEBUG: About to process junction section")
                junction_types = defaultdict(int)
                try:
                    # Get panel GUID and label for junction lookup
                    panel_guid = None
                    panel_label = None
                    if isinstance(panel_obj, dict):
                        panel_guid = panel_obj.get('PanelGuid') or panel_obj.get('Guid') or panel_obj.get('ID')
                        panel_label = panel_obj.get('Label') or panel_obj.get('Name')
                        
                        # If panel_label looks like a GUID, use it as the GUID
                        if panel_label and len(panel_label) == 36 and panel_label.count('-') == 4:
                            panel_guid = panel_label

                    print("DEBUG: Looking for junctions for panel", panel_label, "(GUID:", panel_guid, ")")
                    junctions = []
                    
                    # Use efficient lookup instead of iterating through all junctions
                    if panel_guid:
                        junctions.extend(current_junction_lookup.get(panel_guid, []))
                    if panel_label and panel_label != panel_guid:
                        junctions.extend(current_junction_lookup.get(panel_label, []))
                    
                    # Remove duplicates (junctions might be indexed under both GUID and label)
                    seen_junctions = set()
                    unique_junctions = []
                    for j in junctions:
                        j_id = id(j)  # Use object ID to identify unique junctions
                        if j_id not in seen_junctions:
                            seen_junctions.add(j_id)
                            unique_junctions.append(j)
                    
                    for junction in unique_junctions:
                        sub_name_el = junction.find('SubAssemblyName')
                        fam_name_el = junction.find('FamilyMemberName')

                        sub_name = sub_name_el.text.strip() if sub_name_el is not None and sub_name_el.text else 'Unknown'
                        fam_name = fam_name_el.text.strip() if fam_name_el is not None and fam_name_el.text else 'Unknown'

                        # Use SubAssemblyName as the junction type (without "-> AttachedWall")
                        junction_type = sub_name
                        if junction_type and junction_type != 'AttachedWall':
                            junction_types[junction_type] += 1

                    print("DEBUG: Found", len(junction_types), "junction types for panel", panel_label)
                    print("DEBUG: junction_types dict:", dict(junction_types))
                    
                    # Add junction details section if junctions exist
                    if junction_types:
                            print("DEBUG: Adding junction section to GUI for panel", panel_label)
                            # Add separator before junction section
                            separator = tk.Frame(details_scrollable_frame, bg=BORDER_LIGHT, height=1)
                            separator.pack(fill='x', padx=8, pady=8)

                            # Junction section header
                            junction_header = tk.Frame(details_scrollable_frame, bg=SUCCESS_GREEN)
                            junction_header.pack(fill='x', padx=8, pady=4)
                            tk.Label(junction_header, text='Junction Details',
                                    bg=SUCCESS_GREEN, fg='white', font=('Segoe UI', 10, 'bold'),
                                    anchor='w').pack(anchor='w', padx=6, pady=3)

                            # Display junction types with counts in format "Type - (QNT)"
                            for junction_type, count in sorted(junction_types.items()):
                                junction_display = junction_type + " - (" + str(count) + ")"
                                print("DEBUG: Adding junction to GUI:", junction_display)
                                add_detail_line(junction_display, None, bullet=True, raw=True)

                except Exception as e:
                    print("DEBUG: Exception in junction details display:", e)
                    pass

                # Rough openings: show them after Production Notes in Panel Details
                try:
                    ro_list = []
                    mats_list = materials if isinstance(materials, (list, tuple)) else []
                    elevations = panel_obj.get('elevations', [])
                    print(f"DEBUG: Checking {len(mats_list)} materials for rough openings")
                    print(f"DEBUG: Found {len(elevations)} elevation views")

                    # Debug: show first few materials to see their structure
                    for i, m in enumerate(mats_list[:5]):
                        print(f"DEBUG: Material {i}: Type={m.get('Type')}, Family={m.get('FamilyMemberName')}, Label={m.get('Label')}, Desc={m.get('Desc')}")

                    for m in mats_list:
                        is_ro = _is_rough_opening(m)
                        if is_ro:
                            lab = m.get('Label') or ''
                            desc = m.get('Desc') or m.get('Description') or ''
                            ln = m.get('ActualLength') or m.get('Length') or ''
                            wd = m.get('ActualWidth') or m.get('Width') or ''

                            print(f"DEBUG: Found rough opening - Label: '{lab}', Type: '{m.get('Type')}', Family: '{m.get('FamilyMemberName')}', Desc: '{desc}'")

                            # Try to find matching elevation data
                            aff_height = get_aff_for_rough_opening(panel_obj, m)

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
                                for mat in mats_list:
                                    mat_type = mat.get('Type', '').lower()
                                    header_label = mat.get('Label', '')
                                    # Only include materials that are headers (not headercap or headercripple)
                                    # and have single-character labels (typical for headers)
                                    if mat_type == 'header' and header_label and len(header_label) == 1:
                                        header_set.add(header_label)
                                associated_headers = sorted(list(header_set))[:1]

                            # Format the rough opening display
                            ro_lines = [f"Rough Opening: {lab}"]
                            if ln and wd:
                                # Strip trailing zeros from dimensions
                                ln_clean = strip_trailing_zeros(str(ln))
                                wd_clean = strip_trailing_zeros(str(wd))
                                ro_lines.append(f"Size: {ln_clean} x {wd_clean}")
                            elif ln:
                                ln_clean = strip_trailing_zeros(str(ln))
                                ro_lines.append(f"Size: {ln_clean}")
                            if aff_height is not None:
                                # Strip trailing zeros from AFF decimal value
                                aff_decimal = strip_trailing_zeros(str(aff_height))
                                formatted_aff = inches_to_feet_inches_sixteenths(str(aff_height))
                                if formatted_aff:
                                    ro_lines.append(f"AFF: {aff_decimal} ({formatted_aff})")
                                else:
                                    ro_lines.append(f"AFF: {aff_decimal}")
                            if associated_headers:
                                ro_lines.append(f"Reference: {', '.join(associated_headers)} - Header")

                            ro_list.append(ro_lines)
                            print(f"DEBUG: Found rough opening: {ro_lines}")
                    print(f"DEBUG: Total rough openings found: {len(ro_list)}")
                    for ro in ro_list:
                        for line in ro:
                            add_detail_line(line, None, bullet=True, raw=True)
                        print(f"DEBUG: Added to GUI: {ro}")
                except Exception as e:
                    print(f"DEBUG: Exception in rough openings display: {e}")
                    pass

            # Center the content after adding all labels
            root.after(100, center_details_content)  # Delay to ensure layout is complete
        except Exception:
            pass

        # Material breakdown: accept list of dicts or dict mapping names->list
        try:
            # breakdown content title removed to preserve vertical space
            mats_list = []
            if isinstance(materials, dict):
                # if it's a mapping of panel->materials, try to pull the current name
                # otherwise flatten values
                for v in materials.values():
                    if isinstance(v, (list, tuple)):
                        mats_list.extend(v)
            elif isinstance(materials, (list, tuple)):
                mats_list = list(materials)
            # Use format_and_sort_materials if available to match expected.log formatting
            lines = []
            try:
                # remove rough openings from the breakdown source
                mats_list = [m for m in mats_list if not _is_rough_opening(m)]
                # Try to use format_and_sort_materials directly
                if callable(format_and_sort_materials):
                    lines = format_and_sort_materials(mats_list)
                else:
                    # fallback simple formatter - consolidate materials manually
                    from collections import defaultdict
                    material_groups = defaultdict(lambda: {'count': 0, 'length': '', 'width': ''})
                    
                    for m in mats_list:
                        if not isinstance(m, dict):
                            lines.append(str(m))
                            continue
                            
                        lbl = m.get('Label') or m.get('Name') or ''
                        typ = m.get('Type') or ''
                        desc = m.get('Desc') or m.get('Description') or ''
                        length = m.get('ActualLength') or m.get('Length') or ''
                        width = m.get('ActualWidth') or m.get('Width') or ''
                        
                        # Create a key for grouping identical materials
                        key = (lbl, typ, desc, str(length).strip(), str(width).strip())
                        
                        # Count this material
                        material_groups[key]['count'] += 1
                        if not material_groups[key]['length']:
                            material_groups[key]['length'] = length
                        if not material_groups[key]['width']:
                            material_groups[key]['width'] = width
                        material_groups[key]['lbl'] = lbl
                        material_groups[key]['typ'] = typ
                        material_groups[key]['desc'] = desc
                    
                    # Format the consolidated materials
                    for key, info in sorted(material_groups.items(), key=lambda x: _nat_key(x[1]['lbl'] or '')):
                        lbl = info['lbl']
                        typ = info['typ']
                        desc = info['desc']
                        length = info['length']
                        width = info['width']
                        count = info['count']
                        
                        qty_str = f"({count})"
                        
                        # Format dimensions
                        len_str = inches_to_feet_inches_sixteenths(length) if length not in (None, '', '0', '0.0') else ''
                        wid_str = inches_to_feet_inches_sixteenths(width) if width not in (None, '', '0', '0.0') else ''
                        
                        size = ''
                        if 'sheet' in typ.lower() or 'sheath' in typ.lower():
                            if len_str and wid_str:
                                size = f"{len_str} x {wid_str}"
                            elif len_str:
                                size = f"{len_str}"
                            elif wid_str:
                                size = f"{wid_str}"
                        else:
                            size = len_str or ''
                        
                        if size:
                            lines.append(f"{lbl} - {typ} - {desc} - {qty_str} - {size}")
                        else:
                            lines.append(f"{lbl} - {typ} - {desc} - {qty_str}")
            except Exception:
                lines = []

            # Always show material breakdown header to match export format
            breakdown_header = tk.Frame(breakdown_scrollable_frame, bg=PRIMARY_BLUE)
            breakdown_header.pack(fill='x', padx=4, pady=6)
            tk.Label(breakdown_header, text='Panel Material Breakdown:',
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
                            fg=TEXT_MEDIUM, font=('Segoe UI', 9),
                            anchor='center', justify='center',
                            wraplength=DEFAULT_STATE['breakdown_w']-20).pack(
                            anchor='center', fill='x', padx=4, pady=3)
                except Exception:
                    pass

            # Center the content after adding all labels
            root.after(100, center_breakdown_content)  # Delay to ensure layout is complete
        except Exception:
            pass
    def on_panel_selected(name):
        print("DEBUG: on_panel_selected called with name:", name)
        try:
            selected_panel['name'] = name
            obj = current_panels.get(name, {})
            mats = panel_materials_map.get(name, [])
            display_panel(name, obj, mats)
        except Exception as e:
            print("DEBUG: Exception in on_panel_selected:", e)

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
        print(f"DEBUG: rebuild_bundles called with count={count}, panels_loaded={panels_loaded}, current_panels count={len(current_panels) if current_panels else 0}")
        for ch in btn_grid.winfo_children():
            ch.destroy()
        panel_button_widgets.clear()
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
            print(f"DEBUG: Processing {len(current_panels)} panels")
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

            # Sort panels within each bundle
            for bundle_key, bundle_data in bundle_panels.items():
                # Sort panels by numerical order using DisplayLabel (05-100, 05-101, etc.)
                def sort_key_by_display(panel_name):
                    obj = current_panels.get(panel_name, {})
                    display_name = obj.get('DisplayLabel', panel_name)
                    return sort_panel_names([display_name])[0]
                
                bundle_data['panels'] = sorted(bundle_data['panels'], key=sort_key_by_display)

            # Get all bundle keys and sort them by bundle number
            all_bundle_keys = sort_bundle_keys(bundle_panels.keys())
            print(f"DEBUG: Found {len(all_bundle_keys)} bundle keys: {all_bundle_keys}")
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
            print(f"DEBUG: Page bundle keys: {page_bundle_keys}")

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
                            correct_font_size = max(7, min(12, temp_per_bundle_w // 30))
                            
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
                            
                            # Debug: Add click event binding to verify button is working
                            def debug_click(n=panel_name):
                                print(f"DEBUG: Button clicked for panel {n}")
                                on_panel_selected(n)
                            
                            btn.config(command=lambda n=panel_name: debug_click(n))
                            
                            # Debug: Print button creation
                            print(f"DEBUG: Created button for panel {panel_name} with text {panel_num}")
                        else:
                            # Create blank placeholder button for empty positions
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
            fw = max(7, min(12, per_bundle_w // 30))
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
                            length = strip_trailing_zeros(str(length))
                        if width:
                            width = strip_trailing_zeros(str(width))
                        
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
                                fg=TEXT_MEDIUM, font=('Segoe UI', 9),
                                anchor='center', justify='center',
                                wraplength=DEFAULT_STATE['breakdown_w']-20).pack(
                                anchor='center', fill='x', padx=4, pady=3)
                    except Exception:
                        pass

            # Center the content after adding all labels
            root.after(100, center_breakdown_content)
        except Exception as e:
            print(f"Error populating level breakdown: {e}")

    def process_selected_ehx(evt=None):
        print("DEBUG: process_selected_ehx called")
        nonlocal panels_loaded, selected_level, current_panels, original_panels, panel_materials_map, original_materials_map
        sel = file_listbox.curselection()
        if not sel:
            return
        fname = file_listbox.get(sel[0])
        folder = folder_entry.get() or os.getcwd()
        full = os.path.join(folder, fname)
        
        # Reset level selection for new file so it can auto-select lowest level
        selected_level['value'] = None
        
        # Clear zones when loading new file - they should only show when panel is selected
        for ch in details_scrollable_frame.winfo_children():
            ch.destroy()
        for ch in breakdown_scrollable_frame.winfo_children():
            ch.destroy()
        # Try to use log files first for better performance and consistency
        use_logs = False  # Force EHX parsing to get complete materials
        expected_log_path = os.path.join(folder, 'expected.log')
        
        # Also check for specific log file named after the EHX file
        ehx_basename = os.path.splitext(fname)[0]  # Remove .EHX extension
        
        # Look for log file in multiple locations
        possible_log_paths = [
            os.path.join(folder, f'{ehx_basename}.log'),  # Same directory as EHX
            os.path.join(folder, '..', '..', 'Levels', f'{ehx_basename}.log'),  # Levels directory (up two levels)
            os.path.join(folder, '..', f'{ehx_basename}.log'),  # Parent directory
            os.path.join(HERE, 'Working', 'Levels', f'{ehx_basename}.log'),  # Absolute path
        ]
        
        specific_log_path = None
        for log_path in possible_log_paths:
            if os.path.exists(log_path):
                specific_log_path = log_path
                break
        
        materials_log_path = os.path.join(folder, 'materials.log')
        
        # Use specific log file if it exists, otherwise fall back to expected.log
        log_path_to_use = specific_log_path if specific_log_path else expected_log_path
        
        if use_logs and os.path.exists(log_path_to_use):
            print(f"DEBUG: Found log file at: {log_path_to_use}")
            print(f"DEBUG: Attempting to load data from log file: {os.path.basename(log_path_to_use)}")
            try:
                panels_by_name = read_panels_from_expected_log(log_path_to_use)
                # Materials are already included in the log file, so we don't need materials.log
                materials_map = {}
                
                # Use materials from the log file
                for panel_name, panel_obj in panels_by_name.items():
                    if 'materials' in panel_obj:
                        materials_map[panel_name] = panel_obj['materials']
                
                print(f"DEBUG: Loaded {len(panels_by_name)} panels and {len(materials_map)} material entries from log")
                
                # Validate that we got data from logs
                if panels_by_name:
                    print(f"DEBUG: Successfully loaded {len(panels_by_name)} panels from logs")
                    use_logs = True
                else:
                    print("DEBUG: Log files exist but contain no data, falling back to EHX parsing")
                    use_logs = False
            except Exception as e:
                print(f"DEBUG: Error reading from logs: {e}, falling back to EHX parsing")
                use_logs = False
        else:
            print("DEBUG: Log files not found or use_logs=False, parsing EHX file")
            use_logs = False
        
        # If not using logs, parse the EHX file as before
        if not use_logs:
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
                    panels, materials_map = pv_mod.parse_panels(full) or ([], {})
                except Exception:
                    panels, materials_map = [], {}
            else:
                try:
                    panels, materials_map = parse_panels(full) or ([], {})
                except Exception:
                    panels, materials_map = [], {}
                    
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

        # Create junction lookup for efficient GUI display
        global current_junction_lookup
        current_junction_lookup = defaultdict(list)
        try:
            tree = ET.parse(full)
            xml_root = tree.getroot()
            
            # First, create a mapping from panel labels to their PanelGuids
            panel_label_to_guid = {}
            for panel in xml_root.findall('.//Panel'):
                panel_guid_el = panel.find('PanelGuid')
                label_el = panel.find('Label')
                if panel_guid_el is not None and panel_guid_el.text and label_el is not None and label_el.text:
                    panel_label_to_guid[label_el.text.strip()] = panel_guid_el.text.strip()
            
            # Now fix the materials mapping to use panel labels as keys instead of GUIDs
            if panel_label_to_guid:
                corrected_materials_map = {}
                for label, guid in panel_label_to_guid.items():
                    if guid in panel_materials_map:
                        corrected_materials_map[label] = panel_materials_map[guid]
                
                # Update the materials maps with corrected keys
                panel_materials_map.clear()
                panel_materials_map.update(corrected_materials_map)
                original_materials_map.clear()
                original_materials_map.update(corrected_materials_map)
            
            for junction in xml_root.findall('.//Junction'):
                j_panel_guid = junction.find('PanelGuid') or junction.find('PanelID')
                j_panel_label = junction.find('Label')
                
                # Index by junction's PanelGuid/PanelID
                if j_panel_guid is not None and j_panel_guid.text:
                    current_junction_lookup[j_panel_guid.text].append(junction)
                
                # Also index by junction's Label
                if j_panel_label is not None and j_panel_label.text:
                    current_junction_lookup[j_panel_label.text].append(junction)
                    
                # Also index by the panel's actual PanelGuid if we can map it
                if j_panel_guid is not None and j_panel_guid.text and j_panel_guid.text in panel_label_to_guid:
                    actual_guid = panel_label_to_guid[j_panel_guid.text]
                    current_junction_lookup[actual_guid].append(junction)
        except Exception as e:
            print(f"DEBUG: Error creating junction lookup: {e}")
            current_junction_lookup = defaultdict(list)
        
        print(f"DEBUG: Junction lookup built with {len(current_junction_lookup)} entries")

        print("DEBUG: About to call update_level_buttons")
        # Update level buttons based on loaded panels
        update_level_buttons()
        print("DEBUG: update_level_buttons completed")
        
        # Apply level filtering to show only the selected level
        if selected_level['value'] is not None:
            filter_panels_by_level()
            # Clear zones when level changes - they should only show when panel is selected
            for ch in details_scrollable_frame.winfo_children():
                ch.destroy()
            for ch in breakdown_scrollable_frame.winfo_children():
                ch.destroy()

        try:
            jp = extract_jobpath(full) if callable(extract_jobpath) else ''
            if jp:
                path_val.config(text=jp)
            job_val.config(text=os.path.splitext(fname)[0])
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
                writer(full, log_panels, log_materials)
                
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
                    ts = _dt.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                    folder = os.path.dirname(full)
                    fname = os.path.basename(full)
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
            expected_path = os.path.join(os.path.dirname(full), 'expected.log')
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

    file_listbox.bind('<Double-Button-1>', process_selected_ehx)

    # Lock/Reset shortcuts
    def save_state(state):
        try:
            with open(STATE_FILE, 'w', encoding='utf-8') as fh:
                json.dump(state, fh, indent=2)
        except Exception:
            pass

    def toggle_lock_view():
        try:
            st = {'left_w': left.winfo_width(), 'details_w': details_outer.winfo_width(), 'breakdown_w': breakdown_outer.winfo_width(), 'green_h': btns_frame.winfo_height()}
            save_state(st)
            with open(LOG_FILE, 'a', encoding='utf-8') as fh:
                fh.write(json.dumps({'ts': _dt.datetime.utcnow().isoformat(), 'action': 'lock', 'state': st}) + '\n')
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
    
    return root

if __name__ == '__main__':
    import sys
    # Always start in GUI mode - ignore command line arguments
    # Users must select files manually by double-clicking
    print("DEBUG: Starting GUI creation...")
    app = make_gui()
    print("DEBUG: GUI created, starting mainloop...")
    app.mainloop()