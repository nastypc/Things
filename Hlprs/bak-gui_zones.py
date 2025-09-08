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
def _nat_key(s):
    """Natural sort key: split digits and non-digits so strings with numbers sort naturally."""
    try:
        parts = re.split(r'(\d+)', (s or ''))
        return [int(p) if p.isdigit() else p.lower() for p in parts]
    except Exception:
        return [s]
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
    # Return empty string for zero dimensions instead of '0"'
    return ''


# Top-level helper: parse materials from a Panel element (lightweight copy of fallback parser)
def parse_materials_from_panel(panel_el):
    try:
        def _text_of(el, names):
            if el is None:
                return None
            for n in names:
                ch = el.find(n)
                if ch is not None and ch.text is not None:
                    return ch.text.strip()
            return None

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

        for node in panel_el.findall('.//Sheet'):
            typ = _text_of(node, ('FamilyMemberName', 'Type', 'Name')) or 'Sheathing'
            fam = _text_of(node, ('FamilyMemberName', 'Family', 'FamilyName', 'Type', 'Name')) or typ
            label = _text_of(node, ('Label', 'LabelText')) or ''
            sub = _text_of(node, ('SubAssembly', 'SubAssemblyName')) or ''
            mat_child = node.find('Material')
            desc = ''
            if mat_child is not None:
                desc = _text_of(mat_child, ('Description', 'Desc', 'Material', 'Name')) or ''
            if not desc:
                desc = _text_of(node, ('TypeOfSheathing', 'Description', 'Desc', 'Material', 'Name', 'TypeOfFastener')) or ''
            qty = _text_of(node, ('Quantity', 'QNT', 'Qty')) or '1'
            length = ''
            width = ''
            if mat_child is not None:
                length = _text_of(mat_child, ('ActualLength', 'Length')) or ''
                width = _text_of(mat_child, ('ActualWidth', 'Width')) or ''
            if not length:
                length = _text_of(node, ('ActualLength', 'Length')) or ''
            if not width:
                width = _text_of(node, ('ActualWidth', 'Width')) or ''
            sheet_guid = _text_of(node, ('SheetGuid', 'SheetID')) or (_text_of(mat_child, ('SheetGuid', 'SheetID')) if mat_child is not None else None)
            sub_assembly_guid = _text_of(node, ('SubAssemblyGuid', 'SubAssemblyID'))
            mats.append({'Type': typ, 'FamilyMemberName': fam, 'Label': label, 'SubAssembly': sub, 'Desc': desc, 'Description': desc, 'Qty': qty, 'ActualLength': length, 'ActualWidth': width, 'SheetGuid': sheet_guid, 'SubAssemblyGuid': sub_assembly_guid})

        for node in panel_el.findall('.//Bracing'):
            typ = _text_of(node, ('FamilyMemberName', 'Type', 'Name')) or 'Bracing'
            fam = _text_of(node, ('FamilyMemberName', 'Family', 'FamilyName', 'Type', 'Name')) or typ
            label = _text_of(node, ('Label', 'LabelText')) or ''
            sub = _text_of(node, ('SubAssembly', 'SubAssemblyName')) or ''
            desc = _text_of(node, ('Description', 'Desc', 'Material', 'Name')) or ''
            qty = _text_of(node, ('Quantity', 'QNT', 'Qty')) or '1'
            length = _text_of(node, ('ActualLength', 'Length')) or ''
            bracing_guid = _text_of(node, ('BracingGuid', 'BracingID'))
            sub_assembly_guid = _text_of(node, ('SubAssemblyGuid', 'SubAssemblyID'))
            mats.append({'Type': typ, 'FamilyMemberName': fam, 'Label': label, 'SubAssembly': sub, 'Desc': desc, 'Qty': qty, 'ActualLength': length, 'ActualWidth': '', 'BracingGuid': bracing_guid, 'SubAssemblyGuid': sub_assembly_guid})

        for sub_el in panel_el.findall('.//SubAssembly'):
            fam = _text_of(sub_el, ('FamilyMemberName', 'Family', 'FamilyName', 'Type', 'Name')) or ''
            sub_label = _text_of(sub_el, ('Label', 'LabelText')) or ''
            sub_name = _text_of(sub_el, ('SubAssemblyName',)) or ''
            sub_guid = _text_of(sub_el, ('SubAssemblyGuid', 'SubAssemblyID'))
            if fam and str(fam).strip().lower() == 'roughopening':
                for b in sub_el.findall('.//Board'):
                    btyp = _text_of(b, ('FamilyMemberName', 'Type', 'Name')) or 'Board'
                    blab = _text_of(b, ('Label', 'LabelText')) or ''
                    mat_el = b.find('Material') or b
                    bdesc = _text_of(mat_el, ('Description', 'Desc', 'Material', 'Name')) or ''
                    bal = _text_of(mat_el, ('ActualLength', 'Length')) or ''
                    baw = _text_of(mat_el, ('ActualWidth', 'Width')) or ''
                    b_guid = _text_of(b, ('BoardGuid', 'BoardID'))
                    mats.append({'Type': btyp, 'FamilyMemberName': fam, 'Label': blab, 'SubAssembly': sub_name, 'Desc': bdesc, 'Qty': '', 'ActualLength': bal, 'ActualWidth': baw, 'BoardGuid': b_guid, 'SubAssemblyGuid': sub_guid})

        return mats
    except Exception:
        return []


# Top-level GUID-first filter used by GUI and exporters
def _filter_materials_by_guid(materials, panel_obj):
    try:
        if not isinstance(materials, (list, tuple)):
            return materials
        out = []
        panel_guid = None
        if isinstance(panel_obj, dict):
            panel_guid = panel_obj.get('Name') or panel_obj.get('PanelGuid') or panel_obj.get('GUID')
        for m in materials:
            try:
                if not isinstance(m, dict):
                    out.append(m)
                    continue
                mg = m.get('PanelGuid') or m.get('PanelId') or m.get('ParentGuid') or m.get('ParentId') or m.get('Panel')
                if panel_guid and mg and str(mg) == str(panel_guid):
                    out.append(m)
                    continue
                panels_field = m.get('Panels') or m.get('PanelGuids')
                if isinstance(panels_field, (list, tuple)) and panel_guid in panels_field:
                    out.append(m)
                    continue
                out.append(m)
            except Exception:
                out.append(m)
        return out
    except Exception:
        try:
            return list(materials)
        except Exception:
            return materials


# Top-level panel sort key (numeric trailing segment preferred)
def _panel_sort_key(panel_name):
    try:
        display = str(panel_name or '')
        seg = display.split('_')[-1]
        try:
            return (0, int(seg))
        except Exception:
            return (1, _nat_key(display))
    except Exception:
        return (1, str(panel_name))

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
        # normalize numeric strings
        key = (lbl, typ, desc, str(length).strip(), str(width).strip())
        groups.setdefault(key, {'count': 0, 'length': length, 'width': width}).update({'lbl': lbl, 'typ': typ, 'fam': fam, 'desc': desc})
        groups[key]['count'] += 1

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


def get_aff_for_rough_opening(panel_obj, m, size_tol=1.0):
    """Return an AFF (float) for a rough opening material `m` using
    the following priority:
      1) explicit material-level AFF tag
      2) material-level elev_max_y
      3) an elevation whose X-range overlaps the material BottomView
      4) an elevation whose height matches the material ActualLength
      5) label-specific defaults
      6) panel-level fallback (best elevation max_y)
    """
    # 1) explicit AFF
    try:
        if isinstance(m, dict) and m.get('AFF') is not None:
            return float(m.get('AFF'))
    except Exception:
        pass

    # 2) material-level captured elevation
    try:
        if isinstance(m, dict) and m.get('elev_max_y') is not None:
            return float(m.get('elev_max_y'))
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
            # prefer the elevation with largest horizontal overlap, then highest max_y
            candidates.sort(key=lambda t: (t[0], t[1].get('max_y', 0)), reverse=True)
            best = candidates[0][1]
            return best.get('max_y')

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
                    return size_matches[0][1].get('max_y')
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
                best = max(valid, key=lambda e: e.get('max_y', 0))
                aff = best.get('max_y', 0)
                if aff and aff < 1.0 and best.get('height', 0) > 0:
                    return best.get('height')
                return aff
    except Exception:
        pass
    return None

def parse_panels(path):
    panels = []
    materials_map = {}
    try:
        try:
            # Diagnostic: record attempt to parse and file info
            exists = os.path.exists(path)
            size = None
            try:
                if exists:
                    size = os.path.getsize(path)
            except Exception:
                size = None
            log_debug(f"parse_panels called path={path} exists={exists} size={size}")
        except Exception:
            pass
        tree = ET.parse(path)
        root = tree.getroot()
        try:
            # Remove namespace prefixes from tags so subsequent .find/.findall
            # calls that use local tag names work regardless of XML namespaces.
            for el in list(root.iter()):
                try:
                    if isinstance(el.tag, str) and '}' in el.tag:
                        el.tag = el.tag.split('}', 1)[1]
                except Exception:
                    pass
        except Exception:
            pass
    except Exception as e:
        try:
            log_debug(f"parse_panels failed to parse {path} exception={e}")
            # attempt to read small sample for debugging
            try:
                with open(path, 'rb') as fh:
                    sample = fh.read(256)
                    log_debug(f"parse_panels sample={sample[:200]!r}")
            except Exception:
                pass
        except Exception:
            pass
        return panels, materials_map

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

    # diagnostic: count Panel elements using both namespaced and local-name approaches
    try:
        ns_count = 0
        try:
            ns_count = len(root.findall('.//{*}Panel'))
        except Exception:
            ns_count = 0
        local_count = len(root.findall('.//Panel'))
        log_debug(f"panel element counts ns_count={ns_count} local_count={local_count}")
        if local_count == 0 and ns_count > 0:
            # try to normalize tags by stripping namespace prefixes (we already attempted this earlier),
            # but if we still have only namespaced tags attempt the text fallback later.
            log_debug("parse_panels detected only namespaced Panel elements; continuing but will fallback if none parsed")
    except Exception:
        pass

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
        # attach LevelGuid to panel_obj if present so callers can access it
        lg_el = panel_el.find('LevelGuid')
        if lg_el is not None and lg_el.text:
            panel_obj['LevelGuid'] = lg_el.text.strip()
        # try to capture LevelNo if present on the Panel
        lvl = panel_el.find('LevelNo')
        if lvl is not None and lvl.text:
            panel_obj['LevelNo'] = lvl.text.strip()
            # also set 'Level' for backward compatibility/display
            panel_obj['Level'] = panel_obj['LevelNo']
        for fld in ('Level','Description','Bundle','BundleName','BundleGuid','Height','Thickness','StudSpacing','WallLength','LoadBearing','Category','OnScreenInstruction','Weight'):
            el = panel_el.find(fld)
            if el is not None and el.text:
                panel_obj[fld] = el.text.strip()

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
            log_debug(f"Panel {panel_guid} has {len(elevations)} elevation views")
            for i, elev in enumerate(elevations):
                log_debug(f"Elevation {i}: min_y={elev.get('min_y')}, max_y={elev.get('max_y')}, height={elev.get('height')}, points={len(elev.get('points', []))}")
        else:
            log_debug(f"Panel {panel_guid} has no elevation data")

        panels.append(panel_obj)

        # parse materials for this panel and annotate each material with
        # the panel-level GUIDs (PanelGuid, BundleGuid, LevelGuid) so
        # downstream consumers can perform GUID-first filtering.
        mats = parse_materials_from_panel(panel_el)
        if mats:
            # capture bundle guid if present on panel
            bg_el = panel_el.find('BundleGuid')
            bundle_guid = bg_el.text.strip() if (bg_el is not None and bg_el.text) else None
            level_guid = panel_obj.get('LevelGuid')
            for m in mats:
                try:
                    if isinstance(m, dict):
                        # don't overwrite if the material already has a PanelGuid
                        m.setdefault('PanelGuid', panel_guid)
                        if bundle_guid:
                            m.setdefault('BundleGuid', bundle_guid)
                        if level_guid:
                            m.setdefault('LevelGuid', level_guid)
                except Exception:
                    pass
            materials_map[panel_guid] = mats

    try:
        found = len(root.findall('.//Panel')) if root is not None else 0
        log_debug(f"parse_panels returning panels_count={len(panels)} found_in_xml={found}")
        # show up to 6 display labels for diagnostics
        try:
            sample_labels = [p.get('DisplayLabel') for p in panels[:6]]
            log_debug(f"parse_panels sample_labels={sample_labels}")
        except Exception:
            pass
    except Exception:
        pass
    return panels, materials_map

    def extract_jobpath(path):
        try:
            tree = ET.parse(path)
            root = tree.getroot()
            el = root.find('.//JobPath')
            if el is not None and el.text:
                return el.text.strip()
        except Exception:
            pass
        return ''

    def write_expected_and_materials_logs(ehx_path, panels_by_name, materials_map):
        """Write expected.log and materials.log into the same directory as the EHX file.
        Format is matched to the provided examples as closely as possible.
        """
        import time
        folder = os.path.dirname(ehx_path)
        fname = os.path.basename(ehx_path)
        # use timezone-aware UTC datetime to avoid DeprecationWarning
        ts = _dt.datetime.now(_dt.timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

        expected_path = os.path.join(folder, 'expected.log')
        materials_path = os.path.join(folder, 'materials.log')

        # expected.log
        try:
            with open(expected_path, 'w', encoding='utf-8') as fh:
                fh.write(f"=== expected.log cleared at {ts} for {fname} ===\n")
                for pname, pobj in panels_by_name.items():
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
                        'WallLength': 'Wall Length',
                        'Height': 'Height',
                        'Thickness': 'Thickness',
                        'StudSpacing': 'Stud Spacing',
                    }
                    for key in ('Category','LoadBearing','WallLength','Height','Thickness','StudSpacing'):
                        if key in pobj:
                            fh.write(f"• {display_map.get(key,key)}: {pobj.get(key)}\n")

                    # also print Level {LevelNo}: {Description} inside Panel Details if available
                    try:
                        level_no = pobj.get('LevelNo') or pobj.get('Level')
                        desc_txt = pobj.get('Description') or ''
                        if level_no and desc_txt:
                            fh.write(f"• Level {level_no}: {desc_txt}\n")
                    except Exception:
                        pass

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
                        fh.write(f"• Weight: {pobj.get('Weight')}\n")
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
                                    aff_height = get_aff_for_rough_opening(pobj, m)

                                    # Find associated headers based on rough opening type
                                    associated_headers = []
                                    # Prefer material-level ReferenceHeader if provided
                                    try:
                                        if isinstance(m, dict) and m.get('ReferenceHeader'):
                                            associated_headers = [str(m.get('ReferenceHeader'))]
                                    except Exception:
                                        associated_headers = []

                                    if not associated_headers:
                                        if lab == 'BSMT-HDR':
                                            # BSMT-HDR uses G headers
                                            associated_headers = ['G']
                                        elif lab == '49x63-L2':
                                            # 49x63-L2 uses F headers
                                            associated_headers = ['F']
                                        else:
                                            # Fallback: find unique header labels (only header-type materials)
                                            header_set = set()
                                            for mat in materials_map.get(pname, []):
                                                if mat.get('Type', '').lower() == 'header':
                                                    header_label = mat.get('Label', '')
                                                    if header_label:
                                                        header_set.add(header_label)
                                            associated_headers = list(header_set)

                                    # Format the rough opening display
                                    ro_text = f"Rough Opening: {lab}"
                                    if ln and wd:
                                        ro_text += f" - {ln} x {wd}"
                                    elif ln:
                                        ro_text += f" - {ln}"
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
                    fh.write('\n')
                    fh.write("Panel Material Breakdown:\n")
                    lines = []
                    mats = materials_map.get(pname, [])
                    # filter out rough openings from the breakdown
                    mats_filtered = [m for m in (mats or []) if not _is_rough_opening(m)]
                    lines = format_and_sort_materials(mats_filtered)
                    for l in lines:
                        fh.write(f"{l}\n")
                    fh.write('---\n')
        except Exception:
            pass

        # materials.log (Type: ... lines)
        try:
            with open(materials_path, 'w', encoding='utf-8') as fh:
                fh.write(f"=== materials.log cleared at {ts} for {fname} ===\n")
                for pname, pobj in panels_by_name.items():
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
                    for m in materials_map.get(pname, []):
                        try:
                            fh.write(f"Type: {m.get('FamilyMemberName','')} , Label: {m.get('Label','')} , SubAssembly: {m.get('SubAssembly','')} , Desc: {m.get('Desc','')}\n")
                        except Exception:
                            pass
                    fh.write('---\n')
        except Exception:
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
                m_pg = m.get('PanelGuid')
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

# Theme colors and defaults
TOP_BG = '#cfeffd'
LEFT_BG = '#f8f8f8'
BUTTONS_BG = '#e8f8e8'
DETAILS_BG = '#fff7c6'
BREAKDOWN_BG = '#ffdbe6'

HERE = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(HERE, 'gui_zones_state.json')
LOG_FILE = os.path.join(HERE, 'gui_zones_log.json')
LAST_FOLDER_FILE = os.path.join(HERE, 'gui_zones_last_folder.json')


def log_debug(msg, **kwargs):
    """Append a timestamped debug entry to LOG_FILE and print to stdout.
    Keeps callers safe by swallowing any exceptions so logging never breaks GUI.
    """
    try:
        entry = {'ts': _dt.datetime.now(_dt.timezone.utc).isoformat(), 'msg': str(msg)}
        # include optional extra fields
        if kwargs:
            entry.update(kwargs)
        try:
            with open(LOG_FILE, 'a', encoding='utf-8') as fh:
                fh.write(json.dumps(entry) + '\n')
        except Exception:
            # ignore file write errors
            pass
        # Also print to stdout so running from terminal shows messages
        try:
            print(f"[gui_log] {entry['ts']} {entry['msg']}")
        except Exception:
            pass
    except Exception:
        # never raise from logging
        pass


def write_expected_and_materials_logs(ehx_path, panels_by_name, materials_map):
    """Minimal, safe writer for expected.log and materials.log next to the EHX.
    This ensures a global writer exists even if another definition is nested.
    """
    try:
        folder = os.path.dirname(ehx_path) or os.getcwd()
        fname = os.path.basename(ehx_path)
        ts = _dt.datetime.now(_dt.timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        expected_path = os.path.join(folder, 'expected.log')
        materials_path = os.path.join(folder, 'materials.log')
        try:
            with open(expected_path, 'w', encoding='utf-8') as fh:
                fh.write(f"=== expected.log cleared at {ts} for {fname} ===\n")
                # Print basic per-panel header lines
                for pname, pobj in (panels_by_name or {}).items():
                    display_name = pobj.get('DisplayLabel', pname) if isinstance(pobj, dict) else str(pname)
                    fh.write(f"Panel: {display_name}\n")
                    # If materials_map contains rough openings for this panel, list them with computed AFF
                    try:
                        mats = materials_map.get(pname, []) if isinstance(materials_map, dict) else []
                        roughs = [m for m in (mats or []) if _is_rough_opening(m)]
                        if roughs:
                            fh.write("Rough Openings:\n")
                            for m in roughs:
                                try:
                                    aff = None
                                    try:
                                        aff = get_aff_for_rough_opening(pobj or {}, m)
                                    except Exception:
                                        aff = m.get('AFF') if isinstance(m, dict) else None
                                    aff_s = f"{float(aff):.3f}" if isinstance(aff, (int, float)) else (str(aff) if aff is not None else 'None')
                                    lbl = m.get('Label') or m.get('Desc') or ''
                                    fh.write(f"  - {lbl} AFF={aff_s}\n")
                                except Exception:
                                    try:
                                        fh.write(f"  - {str(m)}\n")
                                    except Exception:
                                        pass
                    except Exception:
                        pass
        except Exception as e:
            try:
                log_debug(f"failed to write expected.log to {expected_path} exception={e}")
            except Exception:
                pass
        try:
            with open(materials_path, 'w', encoding='utf-8') as fh:
                fh.write(f"=== materials.log cleared at {ts} for {fname} ===\n")
                # Provide a minimal materials listing per panel if available
                if isinstance(materials_map, dict):
                    for pname, mats in materials_map.items():
                        fh.write(f"Panel: {pname} materials_count={len(mats or [])}\n")
                        # print per-material lines; include AFF for rough openings when available
                        try:
                            for m in (mats or []):
                                try:
                                    if _is_rough_opening(m):
                                        aff = None
                                        try:
                                            aff = get_aff_for_rough_opening(panels_by_name.get(pname, {}), m)
                                        except Exception:
                                            aff = m.get('AFF') if isinstance(m, dict) else None
                                        aff_s = f"{float(aff):.3f}" if isinstance(aff, (int, float)) else (str(aff) if aff is not None else '')
                                        fh.write(f"Type: {m.get('Type')} Label: {m.get('Label')} AFF={aff_s}\n")
                                    else:
                                        fh.write(f"Type: {m.get('Type')} Label: {m.get('Label')}\n")
                                except Exception:
                                    try:
                                        fh.write(str(m) + '\n')
                                    except Exception:
                                        pass
                        except Exception:
                            pass
        except Exception as e:
            try:
                log_debug(f"failed to write materials.log to {materials_path} exception={e}")
            except Exception:
                pass
        try:
            log_debug(f"write_expected_and_materials_logs wrote files in {folder}")
        except Exception:
            pass
    except Exception:
        try:
            log_debug(f"write_expected_and_materials_logs top-level exception")
        except Exception:
            pass


def parse_panels_minimal(path):
    """Very small parser that returns a list of panels with Name and DisplayLabel
    used as a fallback to ensure the GUI can show buttons while the full parser
    is diagnosed. Does not attempt to parse materials deeply.
    """
    out_panels = []
    mats_map = {}
    try:
        tree = ET.parse(path)
        root = tree.getroot()
        # strip namespaces locally
        try:
            for el in list(root.iter()):
                try:
                    if isinstance(el.tag, str) and '}' in el.tag:
                        el.tag = el.tag.split('}', 1)[1]
                except Exception:
                    pass
        except Exception:
            pass
        for panel_el in root.findall('.//Panel'):
            try:
                pg = None
                pl = None
                el = panel_el.find('PanelGuid')
                if el is not None and el.text:
                    pg = el.text.strip()
                el = panel_el.find('Label')
                if el is not None and el.text:
                    pl = el.text.strip()
                if not pg:
                    for tag in ('PanelID','PanelName'):
                        el = panel_el.find(tag)
                        if el is not None and el.text:
                            pg = el.text.strip()
                            break
                if not pg:
                    pg = f"Panel_{len(out_panels)+1}"
                if not pl:
                    pl = pg
                out_panels.append({'Name': pg, 'DisplayLabel': pl})
            except Exception:
                pass
    except Exception as e:
        try:
            log_debug(f"parse_panels_minimal failed {path} exception={e}")
        except Exception:
            pass
    return out_panels, mats_map


def parse_panels_text_fallback(path):
    """Fallback parser: extract PanelGuid and Label directly from file text using regex.
    This helps when XML parsing fails or returns no Panel elements.
    """
    out_panels = []
    try:
        txt = ''
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as fh:
                txt = fh.read()
        except Exception:
            try:
                with open(path, 'rb') as fh:
                    txt = fh.read().decode('utf-8', 'ignore')
            except Exception:
                txt = ''
        if not txt:
            return out_panels, {}
        # find all PanelGuid occurrences
        guids = [m for m in re.finditer(r'<PanelGuid>\s*([^<\s]+)\s*</PanelGuid>', txt, re.IGNORECASE)]
        for g in guids:
            try:
                pg = g.group(1).strip()
                # search for nearest <Label> after guid (limit search window)
                start = g.end()
                window = txt[start:start+1024]
                lm = re.search(r'<Label>\s*([^<]+?)\s*</Label>', window, re.IGNORECASE)
                if lm:
                    pl = lm.group(1).strip()
                else:
                    # fallback: look backwards for a Label within small window
                    back = txt[max(0, g.start()-256):g.start()]
                    bm = re.search(r'<Label>\s*([^<]+?)\s*</Label>', back[::-1], re.IGNORECASE)
                    pl = pl if 'pl' in locals() and pl else (bm.group(1)[::-1].strip() if bm else pg)
                out_panels.append({'Name': pg, 'DisplayLabel': pl})
            except Exception:
                continue
        try:
            log_debug(f"parse_panels_text_fallback extracted count={len(out_panels)} from {path}")
        except Exception:
            pass
    except Exception as e:
        try:
            log_debug(f"parse_panels_text_fallback exception={e} path={path}")
        except Exception:
            pass
    return out_panels, {}

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

# How many bundle placeholders to show across the green zone by default.
# Keep this fixed so per-bundle widths remain stable even when fewer bundles are present.
PLACEHOLDERS_DEFAULT = 5
# Debug: show visible placeholders for empty cells so tray locations are obvious
SHOW_PLACEHOLDERS = True
# Debug: draw computed inner/control bounds inside each bundle for visual verification
# Disabled by default to avoid obscuring interactive widgets; set True to enable overlay
SHOW_DEBUG_BOUNDS = False
# Reserve pixels for per-bundle page control area (Prev/Next). This space is
# subtracted from the inner grid so the 4x4 cells fit symmetrically and aren't
# clipped by the controls.
PAGE_CONTROL_HEIGHT = 36


def make_gui():
    root = tk.Tk()
    root.title('Zones Test GUI')
    root.geometry(f"{DEFAULT_GUI['w']}x{DEFAULT_GUI['h']}")

    # Append a session-start entry to the debug log so we don't lose earlier traces while debugging.
    try:
        init_entry = {'ts': _dt.datetime.now(_dt.timezone.utc).isoformat(), 'msg': 'gui_zones session start - appended (preserve previous)'}
        try:
            with open(LOG_FILE, 'a', encoding='utf-8') as fh:
                fh.write(json.dumps(init_entry) + '\n')
        except Exception:
            # ignore write errors
            pass
    except Exception:
        pass

    # Top bar
    top = tk.Frame(root, bg=TOP_BG)
    top.pack(side='top', fill='x')
    job_val = tk.Label(top, text='(none)', bg=TOP_BG, font=('Arial', 11))
    job_val.pack(side='left', padx=6)
    path_val = tk.Label(top, text='(none)', bg=TOP_BG, font=('Arial', 11), fg='#0033cc')
    path_val.pack(side='left', padx=6)

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

    folder_entry = ttk.Entry(top, width=30)
    folder_entry.pack(side='right', padx=8)
    folder_lbl = tk.Label(top, text='Folder:', bg=TOP_BG)
    folder_lbl.pack(side='right')

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
    # track current page for each bundle key so frames remain static and we can paginate
    bundle_page_map = {}
    # track which page of bundle groups is visible in the green zone
    bundle_group_page = 0
    panel_materials_map = {}
    # track which panel is currently displayed
    selected_panel = {'name': None}

    # Helper: filter materials to those that belong to a given panel using GUID-first logic
    def _filter_materials_by_guid(materials, panel_obj):
        try:
            if not isinstance(materials, (list, tuple)):
                return materials
            out = []
            # Prefer explicit GUIDs available on the panel object
            panel_guid = None
            if isinstance(panel_obj, dict):
                panel_guid = panel_obj.get('Name') or panel_obj.get('PanelGuid') or panel_obj.get('GUID')

            for m in materials:
                try:
                    if not isinstance(m, dict):
                        out.append(m)
                        continue
                    # common material keys that may reference a parent panel
                    mg = m.get('PanelGuid') or m.get('PanelId') or m.get('ParentGuid') or m.get('ParentId') or m.get('Panel')
                    if panel_guid and mg and str(mg) == str(panel_guid):
                        out.append(m)
                        continue
                    # some materials carry a list of panels they belong to
                    panels_field = m.get('Panels') or m.get('PanelGuids')
                    if isinstance(panels_field, (list, tuple)) and panel_guid in panels_field:
                        out.append(m)
                        continue
                    # fallback: if no GUIDs present, accept the material (caller may filter further)
                    out.append(m)
                except Exception:
                    out.append(m)
            return out
        except Exception:
            try:
                return list(materials)
            except Exception:
                return materials

    # Helper: produce a sort key for panel names - prefer numeric trailing part when present
    def _panel_sort_key(panel_name):
        try:
            obj = current_panels.get(panel_name, {}) if isinstance(current_panels, dict) else {}
            display = obj.get('DisplayLabel') or panel_name or ''
            # attempt to use trailing numeric segment (e.g. '07_112' -> 112)
            seg = str(display).split('_')[-1]
            try:
                return (0, int(seg))
            except Exception:
                # fall back to natural sort key
                try:
                    return (1, _nat_key(display))
                except Exception:
                    return (1, str(display))
        except Exception:
            try:
                return (1, _nat_key(str(panel_name)))
            except Exception:
                return (1, str(panel_name))

    # Helper: extract a sensible job path from an EHX file path or parsed XML root
    def extract_jobpath(path_or_root):
        try:
            # If given a string path, try to read a <JobPath> element quickly by scanning file,
            # otherwise return the containing folder.
            if isinstance(path_or_root, str):
                try:
                    with open(path_or_root, 'r', encoding='utf-8') as fh:
                        head = fh.read(40960)
                        import re
                        m = re.search(r'<JobPath>(.*?)</JobPath>', head, re.IGNORECASE | re.DOTALL)
                        if m:
                            return m.group(1).strip()
                except Exception:
                    pass
                return os.path.dirname(path_or_root)

            # If given an ElementTree root or Element, attempt to find JobPath
            root = path_or_root
            try:
                if hasattr(root, 'find'):
                    el = root.find('.//JobPath')
                    if el is not None and getattr(el, 'text', None):
                        return el.text.strip()
            except Exception:
                pass
            return None
        except Exception:
            return None

    # Provide a local materials parser so parse_panels can annotate materials_map
    # This is a simplified, robust extractor borrowed from the more complete
    # fallback parser in `oldd.py` and focused on Boards, Sheets, Bracing, SubAssembly.
    def parse_materials_from_panel(panel_el):
        try:
            def _text_of(el, names):
                if el is None:
                    return None
                for n in names:
                    ch = el.find(n)
                    if ch is not None and ch.text is not None:
                        return ch.text.strip()
                return None

            mats = []
            # Boards
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

            # Sheets
            for node in panel_el.findall('.//Sheet'):
                typ = _text_of(node, ('FamilyMemberName', 'Type', 'Name')) or 'Sheathing'
                fam = _text_of(node, ('FamilyMemberName', 'Family', 'FamilyName', 'Type', 'Name')) or typ
                label = _text_of(node, ('Label', 'LabelText')) or ''
                sub = _text_of(node, ('SubAssembly', 'SubAssemblyName')) or ''
                mat_child = node.find('Material')
                desc = ''
                if mat_child is not None:
                    desc = _text_of(mat_child, ('Description', 'Desc', 'Material', 'Name')) or ''
                if not desc:
                    desc = _text_of(node, ('TypeOfSheathing', 'Description', 'Desc', 'Material', 'Name', 'TypeOfFastener')) or ''
                qty = _text_of(node, ('Quantity', 'QNT', 'Qty')) or '1'
                length = ''
                width = ''
                if mat_child is not None:
                    length = _text_of(mat_child, ('ActualLength', 'Length')) or ''
                    width = _text_of(mat_child, ('ActualWidth', 'Width')) or ''
                if not length:
                    length = _text_of(node, ('ActualLength', 'Length')) or ''
                if not width:
                    width = _text_of(node, ('ActualWidth', 'Width')) or ''
                sheet_guid = _text_of(node, ('SheetGuid', 'SheetID')) or (_text_of(mat_child, ('SheetGuid', 'SheetID')) if mat_child is not None else None)
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

            # SubAssemblies (rough openings)
            for sub_el in panel_el.findall('.//SubAssembly'):
                fam = _text_of(sub_el, ('FamilyMemberName', 'Family', 'FamilyName', 'Type', 'Name')) or ''
                sub_label = _text_of(sub_el, ('Label', 'LabelText')) or ''
                sub_name = _text_of(sub_el, ('SubAssemblyName',)) or ''
                sub_guid = _text_of(sub_el, ('SubAssemblyGuid', 'SubAssemblyID'))
                if fam and str(fam).strip().lower() == 'roughopening':
                    for b in sub_el.findall('.//Board'):
                        btyp = _text_of(b, ('FamilyMemberName', 'Type', 'Name')) or 'Board'
                        blab = _text_of(b, ('Label', 'LabelText')) or ''
                        mat_el = b.find('Material') or b
                        bdesc = _text_of(mat_el, ('Description', 'Desc', 'Material', 'Name')) or ''
                        bal = _text_of(mat_el, ('ActualLength', 'Length')) or ''
                        baw = _text_of(mat_el, ('ActualWidth', 'Width')) or ''
                        b_guid = _text_of(b, ('BoardGuid', 'BoardID'))
                        mats.append({'Type': btyp, 'FamilyMemberName': fam, 'Label': blab, 'SubAssembly': sub_name, 'Desc': bdesc, 'Qty': '', 'ActualLength': bal, 'ActualWidth': baw, 'BoardGuid': b_guid, 'SubAssemblyGuid': sub_guid})

            return mats
        except Exception:
            return []

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
            # apply GUID-first filtering to export materials
            raw_list = panel_materials_map.get(sel_name, [])
            materials_list = _filter_materials_by_guid(raw_list, panel_obj)

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

                # Panel specifications
                candidates = [
                    ('Category', 'Category'),
                    ('Load Bearing', 'LoadBearing'),
                    ('Wall Length', 'WallLength'),
                    ('Height', 'Height'),
                    ('Thickness', 'Thickness'),
                    ('Stud Spacing', 'StudSpacing'),
                ]
                for label, key in candidates:
                    val = panel_obj.get(key, '')
                    if val:
                        if key in ['WallLength', 'Height']:
                            formatted = inches_fmt(val)
                            out.write(f"• {label}: {val} in   ({formatted})\n")
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
                    out.write(f"• Weight: {panel_obj.get('Weight')}\n")
                if panel_obj.get('OnScreenInstruction'):
                    out.write(f"• Production Notes: {panel_obj.get('OnScreenInstruction')}\n")

                # Rough openings
                rough_openings = []
                elevations = panel_obj.get('elevations', [])
                for m in materials_list:
                    if _is_rough_opening(m):
                        lab = m.get('Label') or ''
                        desc = m.get('Desc') or m.get('Description') or ''
                        ln = m.get('ActualLength') or m.get('Length') or ''
                        wd = m.get('ActualWidth') or m.get('Width') or ''

                        # Compute AFF using geometry-aware helper
                        aff_height = get_aff_for_rough_opening(panel_obj, m)

                        # Prefer material-level ReferenceHeader if present
                        associated_headers = []
                        try:
                            if isinstance(m, dict) and m.get('ReferenceHeader'):
                                associated_headers = [str(m.get('ReferenceHeader'))]
                        except Exception:
                            associated_headers = []

                        if not associated_headers:
                            if lab == 'BSMT-HDR':
                                associated_headers = ['G']
                            elif lab == '49x63-L2':
                                associated_headers = ['F']
                            else:
                                header_set = set()
                                for mat in materials_list:
                                    if mat.get('Type', '').lower() == 'header':
                                        header_label = mat.get('Label', '')
                                        if header_label:
                                            header_set.add(header_label)
                                associated_headers = list(header_set)

                        # Format the rough opening display
                        ro_lines = [f"Rough Opening: {lab}"]
                        if ln and wd:
                            ro_lines.append(f"Size: {ln} x {wd}")
                        elif ln:
                            ro_lines.append(f"Size: {ln}")
                        if aff_height is not None:
                            formatted_aff = inches_to_feet_inches_sixteenths(str(aff_height))
                            if formatted_aff:
                                ro_lines.append(f"AFF: {aff_height} ({formatted_aff})")
                            else:
                                ro_lines.append(f"AFF: {aff_height}")
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
                formatter = globals().get('format_and_sort_materials')
                if callable(formatter):
                    breakdown_lines = formatter(breakdown_materials)
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
            # clear GUI state
            current_panels.clear()
            panel_materials_map.clear()
            panels_loaded = False
            selected_panel['name'] = None
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
            # log the action
            try:
                # rotate/clear the debug log to keep it small and start fresh for the next session
                    try:
                        init_entry = {'ts': _dt.datetime.now(_dt.timezone.utc).isoformat(), 'msg': 'gui_zones session cleared via Back/Clear'}
                        try:
                            with open(LOG_FILE, 'w', encoding='utf-8') as fh:
                                fh.write(json.dumps(init_entry) + '\n')
                        except Exception:
                            # fallback to append if write fails
                            try:
                                with open(LOG_FILE, 'a', encoding='utf-8') as fh:
                                    fh.write(json.dumps({'ts': _dt.datetime.now(_dt.timezone.utc).isoformat(), 'action': 'back_clear', 'folder': folder}) + '\n')
                            except Exception:
                                pass
                    except Exception:
                        pass
            except Exception:
                pass
            messagebox.showinfo('Clear', 'GUI cleared and logs removed (if present)')
        except Exception as e:
            messagebox.showerror('Clear Error', str(e))

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

    ttk.Button(top, text='Export', command=export_current_panel).pack(side='right', padx=6)
    ttk.Button(top, text='Back', command=back_clear).pack(side='right', padx=6)
    ttk.Button(top, text='Browse', command=on_browse).pack(side='right', padx=6)

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

    btns_frame = tk.Frame(top_pane, bg=BUTTONS_BG, height=DEFAULT_STATE['green_h'])
    btns_frame.pack_propagate(False)
    btns_frame.pack(fill='both', expand=True, padx=8, pady=8)
    # green zone (buttons) - no visible heading to save space
    btn_grid = tk.Frame(btns_frame, bg=BUTTONS_BG)
    btn_grid.pack(fill='both', expand=True, padx=8, pady=6)

    bottom_inner = tk.PanedWindow(bottom_pane, orient='horizontal')
    bottom_inner.pack(fill='both', expand=True)
    
    # Details frame with scrollbar (yellow zone)
    details_outer = tk.Frame(bottom_inner, bg=DETAILS_BG)
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
    
    details_canvas.pack(side='left', fill='both', expand=True)
    
    # Breakdown frame with scrollbar (pink zone)
    breakdown_outer = tk.Frame(bottom_inner, bg=BREAKDOWN_BG)
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
    
    breakdown_canvas.pack(side='left', fill='both', expand=True)
    
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

    # ...existing code... (auto-load removed to keep file selection manual)

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

    # Helper to produce the short button text for a panel: use the DisplayLabel
    # suffix after the final '_' and then take the last 3 characters (user request)
    def button_text_for(panel_name):
        try:
            obj = current_panels.get(panel_name, {})
            display = obj.get('DisplayLabel') or panel_name or ''
            # take the last segment after '_' if present
            seg = display.split('_')[-1]
            # return last 3 characters (or whole segment if shorter)
            return seg[-3:] if len(seg) > 3 else seg
        except Exception:
            return panel_name

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
                tk.Label(details_scrollable_frame, text=f'Panel: {header_panel_num} (Lot {header_lot_num})', bg=DETAILS_BG, font=('Arial', 11, 'bold')).pack(anchor='w', padx=6, pady=4)
            else:
                tk.Label(details_scrollable_frame, text=f'Panel: {display_name}', bg=DETAILS_BG, font=('Arial', 11, 'bold')).pack(anchor='w', padx=6, pady=4)
        except Exception:
            pass
        # Helper to write labeled lines into details_frame with wrapping
        def add_detail_line(label, value=None, bullet=False, raw=False):
            try:
                if raw:
                    txt = f"• {label}" if bullet else f"{label}"
                else:
                    if bullet:
                        txt = f"• {label}: {value}" if value is not None else f"• {label}:"
                    else:
                        txt = f"{label}: {value}" if value is not None else f"{label}:"
                tk.Label(details_scrollable_frame, text=txt, bg=DETAILS_BG, anchor='w', justify='left', wraplength=DEFAULT_STATE['details_w'], font=('Arial', 10, 'bold')).pack(fill='x', padx=6, pady=2)
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
                
                # Level / Description / Bundle (show these as top-level metadata)
                if lot_num:
                    add_detail_line('Lot', lot_num)
                add_detail_line('Panel', panel_num)
                if 'Level' in panel_obj:
                    add_detail_line('Level', panel_obj.get('Level'))
                if 'Description' in panel_obj:
                    add_detail_line('Description', panel_obj.get('Description'))
                b = panel_obj.get('Bundle') or panel_obj.get('BundleName') or panel_obj.get('BundleGuid') or ''
                if b:
                    add_detail_line('Bundle', b)

                # common field candidates
                candidates = [
                    ('Category', ['Category', 'PanelCategory', 'Type']),
                    ('Load Bearing', ['LoadBearing', 'IsLoadBearing', 'LoadBearingFlag']),
                    ('Wall Length', ['WallLength', 'Length', 'PanelLength']),
                    ('Height', ['Height', 'PanelHeight']),
                    ('Thickness', ['Thickness', 'Depth']),
                    ('Stud Spacing', ['StudSpacing', 'StudsPerFoot']),
                ]
                for label, keys in candidates:
                    val = ''
                    for k in keys:
                        if k in panel_obj:
                            val = panel_obj.get(k)
                            break
                    # Format Wall Length and Height with feet-inches-sixteenths
                    if val and (label == 'Wall Length' or label == 'Height'):
                        try:
                            formatted = inches_to_feet_inches_sixteenths(float(val))
                            if formatted:
                                display_val = f"{val} in   ({formatted})"
                            else:
                                display_val = f"{val} in"
                        except (ValueError, TypeError):
                            display_val = val
                    else:
                        display_val = val
                    add_detail_line(label, display_val, bullet=True)

                # also print Level {LevelNo}: {Description} inside Panel Details if available
                try:
                    level_no = panel_obj.get('LevelNo') or panel_obj.get('Level')
                    desc_txt = panel_obj.get('Description') or ''
                    if level_no and desc_txt:
                        add_detail_line(f"Level {level_no}", desc_txt, bullet=True)
                except Exception:
                    pass

                # Sheathing layers: derive from materials list (first two unique sheathing descriptions)
                try:
                    sheet_descs = []
                    # apply GUID-first filtering so GUI sheathing lines only come from
                    # materials that belong to this panel when GUIDs are present
                    mats_list = materials if isinstance(materials, (list, tuple)) else []
                    mats_list = _filter_materials_by_guid(mats_list, panel_obj)
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
                if 'Weight' in panel_obj:
                    add_detail_line('Weight', panel_obj.get('Weight'), bullet=True)
                if osi:
                    add_detail_line('Production Notes', osi, bullet=True)
                # Rough openings: show them after Production Notes in Panel Details
                try:
                    ro_list = []
                    # mats_list already filtered above
                    mats_list = mats_list
                    elevations = panel_obj.get('elevations', [])
                    log_debug(f"Checking {len(mats_list)} materials for rough openings")
                    log_debug(f"Found {len(elevations)} elevation views")

                    # Debug: show first few materials to see their structure
                    for i, m in enumerate(mats_list[:5]):
                        log_debug(f"Material {i}: Type={m.get('Type')}, Family={m.get('FamilyMemberName')}, Label={m.get('Label')}, Desc={m.get('Desc')}")

                    for m in mats_list:
                        is_ro = _is_rough_opening(m)
                        if is_ro:
                            lab = m.get('Label') or ''
                            desc = m.get('Desc') or m.get('Description') or ''
                            ln = m.get('ActualLength') or m.get('Length') or ''
                            wd = m.get('ActualWidth') or m.get('Width') or ''

                            log_debug(f"Found rough opening - Label: '{lab}', Type: '{m.get('Type')}', Family: '{m.get('FamilyMemberName')}', Desc: '{desc}'")

                            # Prefer material-level AFF first
                            aff_height = None
                            try:
                                if isinstance(m, dict) and m.get('AFF') is not None:
                                    aff_height = float(m.get('AFF'))
                            except Exception:
                                aff_height = None

                            # compute AFF using geometry-aware helper
                            aff_height = get_aff_for_rough_opening(panel_obj, m)

                            # Find associated headers based on rough opening type
                            associated_headers = []
                            if lab == 'BSMT-HDR':
                                # BSMT-HDR uses G headers
                                associated_headers = ['G']
                            elif lab == '49x63-L2':
                                # 49x63-L2 uses F headers
                                associated_headers = ['F']
                            else:
                                # Fallback: find unique header labels
                                header_set = set()
                                for mat in mats_list:
                                    if mat.get('Type', '').lower() == 'header':
                                        header_label = mat.get('Label', '')
                                        if header_label:
                                            header_set.add(header_label)
                                associated_headers = list(header_set)

                            # Format the rough opening display
                            ro_lines = [f"Rough Opening: {lab}"]
                            if ln and wd:
                                ro_lines.append(f"Size: {ln} x {wd}")
                            elif ln:
                                ro_lines.append(f"Size: {ln}")
                            if aff_height is not None:
                                formatted_aff = inches_to_feet_inches_sixteenths(str(aff_height))
                                if formatted_aff:
                                    ro_lines.append(f"AFF: {aff_height} ({formatted_aff})")
                                else:
                                    ro_lines.append(f"AFF: {aff_height}")
                            if associated_headers:
                                ro_lines.append(f"Reference: {', '.join(associated_headers)} - Header")

                            ro_list.append(ro_lines)
                            log_debug(f"Found rough opening: {ro_lines}")
                    log_debug(f"Total rough openings found: {len(ro_list)}")
                    for ro in ro_list:
                        for line in ro:
                            add_detail_line(line, None, bullet=True, raw=True)
                        log_debug(f"Added to GUI: {ro}")
                except Exception as e:
                    log_debug(f"Exception in rough openings display: {e}")
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
            formatter = globals().get('format_and_sort_materials')
            lines = []
            try:
                # remove rough openings from the breakdown source
                mats_list = [m for m in mats_list if not _is_rough_opening(m)]
                if callable(formatter):
                    lines = formatter(mats_list)
                else:
                    # fallback simple formatter
                    for m in mats_list:
                        if not isinstance(m, dict):
                            lines.append(str(m))
                        else:
                            lbl = m.get('Label') or m.get('Name') or ''
                            typ = m.get('Type') or ''
                            desc = m.get('Desc') or m.get('Description') or ''
                            qty = m.get('Qty') or m.get('Quantity') or ''
                            length = m.get('ActualLength') or m.get('Length') or ''
                            width = m.get('ActualWidth') or m.get('Width') or ''
                            size = f"{length} x {width}".strip() if width else (length or '')
                            qty_str = f"({qty})" if qty else ''
                            if size:
                                lines.append(f"{lbl} - {typ} - {desc} - {qty_str} - {size}")
                            else:
                                lines.append(f"{lbl} - {typ} - {desc} - {qty_str}")
            except Exception:
                lines = []

            for l in lines:
                try:
                    tk.Label(breakdown_scrollable_frame, text=l, bg=BREAKDOWN_BG, anchor='center', justify='center', font=('Arial', 10, 'bold')).pack(anchor='center', fill='x', padx=6, pady=1)
                except Exception:
                    pass

            # Center the content after adding all labels
            root.after(100, center_breakdown_content)  # Delay to ensure layout is complete
        except Exception:
            pass
    def on_panel_selected(name):
        try:
            selected_panel['name'] = name
            obj = current_panels.get(name, {})
            mats = panel_materials_map.get(name, [])
            display_panel(name, obj, mats)
        except Exception:
            pass

    def rebuild_bundles(count: int):
        for ch in btn_grid.winfo_children():
            ch.destroy()
        panel_button_widgets.clear()

        # Debug: record entry into rebuild
        try:
            log_debug(f"rebuild_bundles called - panels_loaded={panels_loaded}, current_panels={len(current_panels)}")
        except Exception:
            pass

        # inner layout for panels per bundle: 4 cols x 4 rows
        # Use a fixed number of placeholders so widths remain stable across states
        placeholders = max(1, min(8, PLACEHOLDERS_DEFAULT))
        inner_cols = 4
        rows = 4

        for c in range(placeholders):
            btn_grid.grid_columnconfigure(c, weight=1)
        try:
            # Reserve row 0 for bundle frames (expand) and row 1 for global nav (fixed)
            btn_grid.grid_rowconfigure(0, weight=1)
            btn_grid.grid_rowconfigure(1, weight=0, minsize=PAGE_CONTROL_HEIGHT + 8)
        except Exception:
            pass

        if panels_loaded and current_panels:
            panels_by_name = current_panels
            bundle_panels = {}
            # collect panels by bundle key
            for name, obj in panels_by_name.items():
                bkey = None
                display_label = None
                if isinstance(obj, dict):
                    bkey = obj.get('BundleGuid') or obj.get('BundleId') or obj.get('Bundle') or obj.get('BundleName') or obj.get('BundleLabel')
                    display_label = obj.get('BundleName') or obj.get('Bundle') or obj.get('BundleLabel')
                if not bkey:
                    bkey = 'Bundle'
                bundle_panels.setdefault(str(bkey), {'panels': [], 'label': display_label})['panels'].append(name)

            # Produce a deterministic order for bundle placeholders. Prefer the
            # captured display label if present; otherwise fall back to the key.
            def _bundle_label_for_sort(k):
                info = bundle_panels.get(k, {})
                lbl = info.get('label') or str(k or '')
                return _nat_key(lbl)
            ordered_all = sorted(list(bundle_panels.keys()), key=_bundle_label_for_sort)
            try:
                log_debug(f"bundle_panels keys={list(bundle_panels.keys())} ordered_all={ordered_all}")
            except Exception:
                pass
            total_groups = len(ordered_all)
            per_page_groups = placeholders
            group_pages = (total_groups + per_page_groups - 1) // per_page_groups if total_groups > 0 else 1
            # clamp bundle_group_page
            try:
                bp = int(bundle_group_page)
            except Exception:
                bp = 0
            if bp < 0:
                bp = 0
            if bp >= group_pages:
                bp = group_pages - 1

            start_group = bp * per_page_groups
            end_group = start_group + per_page_groups
            ordered = ordered_all[start_group:end_group]
            try:
                log_debug(f"bundle page {bp}/{group_pages} start={start_group} end={end_group} ordered_slice={ordered}")
            except Exception:
                pass

            for bi in range(placeholders):
                bf_key = ordered[bi] if bi < len(ordered) else None
                entry = bundle_panels.get(bf_key, {'panels': [], 'label': None})
                # Always show numeric placeholders to avoid confusion with bundle keys/labels
                label_text = f'Bundle {bi+1}'
                try:
                    log_debug(f"placeholder idx={bi} bf_key={bf_key} entry_panels_count={len(entry.get('panels', []))} entry_label={entry.get('label')}")
                except Exception:
                    pass
                # Use a plain Frame for bundle trays to avoid platform/theme
                # rendering quirks with LabelFrame that can sometimes obscure
                # child widgets on Windows. Add an explicit header label so
                # bundle titles remain visible.
                bf = tk.Frame(btn_grid, bg=BUTTONS_BG)
                # Header inside the frame (keeps thin and consistent)
                try:
                    hdr = tk.Label(bf, text=label_text, bg=BUTTONS_BG, font=('Arial', 9, 'bold'))
                    hdr.pack(side='top', fill='x')
                except Exception:
                    pass
                bf.grid(row=0, column=bi, sticky='nsew', padx=4, pady=4)
                try:
                    bf.grid_propagate(False)
                    bf.configure(height=max(88, btns_frame.winfo_height() - 16))
                    bf.configure(width=btns_frame.winfo_width() // max(1, placeholders) - 8)
                except Exception:
                    pass
                # Ensure bf uses a 2-row grid: row0 for the 4x4 inner grid (expand),
                # row1 reserved (fixed) for page controls so they never overlap the inner area.
                try:
                    bf.grid_rowconfigure(0, weight=1)
                    bf.grid_rowconfigure(1, weight=0, minsize=PAGE_CONTROL_HEIGHT + 4)
                    bf.grid_columnconfigure(0, weight=1)
                except Exception:
                    pass

                # get panels for this bundle key
                panels_for = list(entry.get('panels', []))
                # Sort panels numerically by trailing panel number (e.g. '07_112' -> 112)
                try:
                    panels_for = sorted(panels_for, key=lambda name: _panel_sort_key(current_panels.get(name, name)))
                except Exception:
                    panels_for.sort()

                # Pagination inside bundle: pages of 16 panels
                total = len(panels_for)
                per_page = inner_cols * rows
                pages = (total + per_page - 1) // per_page if total > 0 else 1
                page_idx = int(bundle_page_map.get(str(bf_key), 0)) if bf_key is not None else 0
                if page_idx < 0:
                    page_idx = 0
                if page_idx >= pages:
                    page_idx = pages - 1
                bundle_page_map[str(bf_key)] = page_idx

                start = page_idx * per_page
                page_panels = panels_for[start:start+per_page]
                try:
                    log_debug(f"bf_key={bf_key} total_panels={total} per_page={per_page} pages={pages} page_idx={page_idx} page_panels={page_panels}")
                except Exception:
                    pass

                # inner grid - compute pixel sizes so we can reserve space for page controls
                inner = tk.Frame(bf, bg=BUTTONS_BG)
                try:
                    # base per-bundle height slice from the green area
                    per_bundle_h = max(88, int(btns_frame.winfo_height() - 16) if btns_frame.winfo_height() else DEFAULT_STATE.get('green_h', 264))
                except Exception:
                    per_bundle_h = DEFAULT_STATE.get('green_h', 264)

                # compute an initial inner height that leaves room for the page control area
                top_padding = 8
                bottom_padding = 4
                inner_h = max(16 * rows, per_bundle_h - PAGE_CONTROL_HEIGHT - top_padding - bottom_padding)

                # derive cell sizes from inner_h and per-bundle width
                try:
                    btns_w = btns_frame.winfo_width() or btn_grid.winfo_reqwidth() or DEFAULT_STATE.get('green_w', 1440)
                    cols_eff = max(1, placeholders)
                    # Aim for a visible bundle tray approx 280px wide and ~248px tall (including control row subtraction)
                    target_bundle_w = 280
                    target_bundle_h = 248
                    per_bundle_w = max(target_bundle_w, int((btns_w - (cols_eff * 12)) / cols_eff))
                    inner_w = int(per_bundle_w * 0.96)
                    # Ensure cell dimensions produce at least the target inner area
                    cell_w = max(20, inner_w // inner_cols)
                    cell_h = max(16, inner_h // rows)
                    # If computed sizes are smaller than target, bump them to meet minimum tray size
                    if (cell_w * inner_cols) < int(target_bundle_w * 0.9):
                        cell_w = max(cell_w, int((target_bundle_w * 0.9) / inner_cols))
                    if (cell_h * rows) < int((target_bundle_h - PAGE_CONTROL_HEIGHT) * 0.9):
                        cell_h = max(cell_h, int(((target_bundle_h - PAGE_CONTROL_HEIGHT) * 0.9) / rows))
                except Exception:
                    cell_w = 40
                    cell_h = 40

                # recompute minimal needed per-bundle height to fit 4 rows + controls
                try:
                    min_needed = (cell_h * rows) + PAGE_CONTROL_HEIGHT + top_padding + bottom_padding
                    # Ensure we provide enough height so inner grid + controls fit and tray is not clipped
                    safe_bf_h = max(per_bundle_h, min_needed + 8, target_bundle_h)
                    try:
                        bf.configure(height=safe_bf_h)
                    except Exception:
                        pass
                except Exception:
                    safe_bf_h = per_bundle_h

                # Defer placement until bf has an accurate measured size so controls
                # and inner grid are placed correctly. Use bf.after to schedule.
                def place_inner_and_controls():
                    try:
                        # Use bf's measured geometry and rely on bf's grid rows so the
                        # inner grid expands and the control row remains a fixed height.
                        measured_bf_h = bf.winfo_height() or safe_bf_h
                        measured_bf_w = bf.winfo_width() or (btns_frame.winfo_width() // max(1, placeholders))
                        # Ensure the control row has at least PAGE_CONTROL_HEIGHT available
                        try:
                            bf.grid_rowconfigure(1, minsize=PAGE_CONTROL_HEIGHT + bottom_padding)
                        except Exception:
                            pass

                        # Place inner into row 0 of bf's grid so it expands to fill available space
                        try:
                            # Reserve bottom padding equal to control row height so inner
                            # buttons never overlap or get clipped by controls.
                            inner.grid(row=0, column=0, sticky='nsew', padx=int(measured_bf_w*0.02), pady=(top_padding, PAGE_CONTROL_HEIGHT + bottom_padding))
                        except Exception:
                            try:
                                inner.place(relx=0.02, rely=0.02, relwidth=0.96, relheight=0.80)
                            except Exception:
                                pass

                        # If page controls were created later they will be grid'ed into row 1
                        # and will respect the minsize set above. Draw overlay now that sizes
                        # are known so we can visualize inner/control bounds.
                        if SHOW_DEBUG_BOUNDS:
                            try:
                                # ensure overlay does not cover interactive widgets
                                try:
                                    overlay.lower()
                                except Exception:
                                    try:
                                        overlay.lift()
                                    except Exception:
                                        pass
                                overlay.delete('all')
                                ix = int(measured_bf_w * 0.02)
                                iy = int(top_padding)
                                iw = int(measured_bf_w * 0.96)
                                ih = int(max(1, measured_bf_h - PAGE_CONTROL_HEIGHT - top_padding - bottom_padding))
                                overlay.create_rectangle(ix, iy, ix+iw, iy+ih, outline='blue')
                                overlay.create_text(ix+8, iy+8, anchor='nw', text=f'Inner {iw}x{ih}', fill='blue', font=('Arial', 8))
                                cx = ix
                                cy = iy + ih
                                cw = iw
                                ch = PAGE_CONTROL_HEIGHT
                                overlay.create_rectangle(cx, cy, cx+cw, cy+ch, outline='red')
                                overlay.create_text(cx+8, cy+4, anchor='nw', text=f'Ctrl {cw}x{ch}', fill='red', font=('Arial', 8))
                            except Exception:
                                pass
                        try:
                            # log measured sizes for diagnostics
                            log_debug(f"measured bf idx={bi} bf_key={bf_key} measured_bf_w={measured_bf_w} measured_bf_h={measured_bf_h} inner_w={iw} inner_h={ih}")
                        except Exception:
                            pass
                    except Exception:
                        try:
                            inner.place(relx=0.02, rely=0.02, relwidth=0.96, relheight=0.80)
                        except Exception:
                            pass

                # schedule placement after bf has been mapped
                bf.after(60, place_inner_and_controls)

                # Optional debug overlay canvas (deferred drawing will update it)
                if SHOW_DEBUG_BOUNDS:
                    try:
                        overlay = tk.Canvas(bf, bg='', highlightthickness=0)
                        overlay.place(relx=0, rely=0, relwidth=1.0, relheight=1.0)
                        # ensure overlay sits behind interactive widgets
                        try:
                            overlay.lower()
                        except Exception:
                            pass
                    except Exception:
                        overlay = None

                # Ensure all grid rows/columns are configured so cells expand evenly
                for r in range(rows):
                    try:
                        inner.grid_rowconfigure(r, weight=1)
                    except Exception:
                        pass
                for c in range(inner_cols):
                    try:
                        inner.grid_columnconfigure(c, weight=1)
                    except Exception:
                        pass

                    # Enforce minimum sizes on the inner grid cells so buttons can't grow
                    try:
                        # raise minimums for better legibility
                        cell_w = max(cell_w, 50)
                        cell_h = max(cell_h, 40)
                        for cc in range(inner_cols):
                            inner.grid_columnconfigure(cc, weight=1, minsize=cell_w)
                        for rr in range(rows):
                            inner.grid_rowconfigure(rr, weight=1, minsize=cell_h)
                    except Exception:
                        pass

                max_buttons_per_row = inner_cols
                for idx, panel_name in enumerate(page_panels):
                    obj = current_panels.get(panel_name, {})
                    display_name = obj.get('DisplayLabel', panel_name)
                    # compute short panel label for buttons: prefer the last 3 digits
                    def _button_text_from_display(name):
                        try:
                            s = str(name or '')
                            # prefer digits: find last continuous digit sequence
                            m = re.findall(r"(\d+)", s)
                            if m:
                                seq = m[-1]
                                return seq[-3:]
                            # fallback: use suffix after last '_' then last 3 chars
                            if '_' in s:
                                suf = s.rsplit('_', 1)[1]
                                return suf[-3:]
                            return s[-3:]
                        except Exception:
                            return str(name)
                    panel_num = _button_text_from_display(display_name)
                    # Create small fixed-size buttons like `oldd.py` so they
                    # reliably fit into the 4x4 tray and remain visible across
                    # themes. Use a small bold tk Font and explicit bg/fg. Fall
                    # back to ttk.Button only if tk.Button fails.
                    try:
                        try:
                            # Slightly larger font to improve legibility
                            small_font = tkfont.Font(size=9, weight='bold')
                        except Exception:
                            small_font = None
                        btn = tk.Button(inner,
                                        text=panel_num,
                                        font=small_font,
                                        relief='raised',
                                        bd=3,
                                        anchor='center',
                                        command=lambda n=panel_name: on_panel_selected(n),
                                        width=6,
                                        height=2,
                                        wraplength=80,
                                        bg='#2e8b57',
                                        fg='#ffffff',
                                        activebackground='#66ff99',
                                        activeforeground='#000000')
                    except Exception:
                        try:
                            btn = ttk.Button(inner, text=panel_num, command=lambda n=panel_name: on_panel_selected(n))
                        except Exception:
                            btn = None
                    try:
                        attach_hover_tooltip(btn, lambda n=panel_name, d=display_name: d)
                    except Exception:
                        pass

                    # Compute row/col for this button. Always fill left-to-right,
                    # top-to-bottom so positions 1..16 map to the 4x4 grid cells
                    # in order (row=0,col=0) .. (row=3,col=3).
                    row = idx // max_buttons_per_row
                    col = idx % max_buttons_per_row
                    # Always place buttons into the fixed 4x4 grid cells so each
                    # button uses the same default size
                    try:
                        btn.grid(row=row, column=col, sticky='nsew', padx=2, pady=2)
                    except Exception:
                        # If grid fails, silently continue; do not pack as that breaks cell layout
                        pass
                    try:
                        # Diagnostic: log the button's text and mapping/visibility state
                        txt = None
                        try:
                            txt = btn.cget('text')
                        except Exception:
                            try:
                                txt = str(btn)
                            except Exception:
                                txt = '<unknown>'
                        mapped = False
                        viewable = False
                        try:
                            mapped = bool(btn.winfo_ismapped())
                            viewable = bool(btn.winfo_viewable())
                        except Exception:
                            pass
                        try:
                            log_debug(f"created_button text={txt} mapped={mapped} viewable={viewable} row={row} col={col} bf_w={bf.winfo_width()} bf_h={bf.winfo_height()} inner_w={inner.winfo_width()} inner_h={inner.winfo_height()}")
                        except Exception:
                            try:
                                log_debug(f"created_button text={txt} mapped={mapped} viewable={viewable} row={row} col={col}")
                            except Exception:
                                pass
                    except Exception:
                        pass
                    panel_button_widgets.append(btn)
                    # Ensure the button is visually prominent across themes
                    try:
                        btn.configure(highlightthickness=1, highlightbackground='#000000')
                        try:
                            btn.lift()
                        except Exception:
                            pass
                    except Exception:
                        pass
                    # row/column weights already configured above for all cells

                # Fill remaining cells with invisible frames so the grid keeps fixed positions
                # but no visible placeholder artifacts are shown.
                try:
                    per_page = inner_cols * rows
                    for empty_idx in range(len(page_panels), per_page):
                        er = empty_idx // inner_cols
                        ec = empty_idx % inner_cols
                        try:
                            # invisible frame matching bundle BG so empty cells look empty
                            ph = tk.Frame(inner, bg=BUTTONS_BG)
                            ph.grid(row=er, column=ec, sticky='nsew', padx=2, pady=2)
                        except Exception:
                            pass
                except Exception:
                    pass

                try:
                    # ensure overlay canvas is sent to back so it cannot obscure buttons
                    try:
                        if SHOW_DEBUG_BOUNDS and overlay is not None:
                            overlay.lower()
                    except Exception:
                        pass
                    # diagnostic: how many children does inner have now?
                    cc = len(inner.winfo_children())
                    log_debug(f"placeholder idx={bi} bf_key={bf_key} inner_children_after_place={cc} expected_buttons={len(page_panels)}")
                    # list child widget types/text where possible
                    try:
                        details = []
                        for ch in inner.winfo_children():
                            try:
                                cls = ch.winfo_class()
                                txt = ''
                                try:
                                    txt = ch.cget('text')
                                except Exception:
                                    try:
                                        # ttk widgets may store text differently
                                        txt = str(ch)
                                    except Exception:
                                        txt = ''
                                details.append(f"{cls}:{txt}")
                            except Exception:
                                continue
                        if details:
                            log_debug(f"placeholder idx={bi} children_detail={'|'.join(details)}")
                    except Exception:
                        pass
                except Exception:
                    pass

                # per-bundle page controls
                if pages > 1:
                    ctrl = tk.Frame(bf, bg=BUTTONS_BG)
                    # place page controls at the bottom using fixed pixel height
                    try:
                        # Grid the controls into the reserved second row so they remain
                        # anchored to the bottom of the bundle frame and never overlap
                        # the inner 4x4 grid. Use sticky 'ew' so it stretches horizontally.
                        ctrl.grid(row=1, column=0, sticky='ew', padx=4, pady=(2, bottom_padding))
                    except Exception:
                        try:
                            ctrl.place(relx=0.02, rely=0.84, relwidth=0.96, relheight=0.14)
                        except Exception:
                            pass
                    def make_nav(bk, pages_count):
                        def go_prev():
                            bundle_page_map[str(bk)] = max(0, bundle_page_map.get(str(bk), 0) - 1)
                            rebuild_bundles(count)
                        def go_next():
                            bundle_page_map[str(bk)] = min(pages_count - 1, bundle_page_map.get(str(bk), 0) + 1)
                            rebuild_bundles(count)
                        return go_prev, go_next
                    prev_cb, next_cb = make_nav(bf_key, pages)
                    try:
                        pbtn = tk.Button(ctrl, text='◀', command=prev_cb)
                        nbtn = tk.Button(ctrl, text='▶', command=next_cb)
                        lbl = tk.Label(ctrl, text=f'Page {page_idx+1}/{pages}', bg=BUTTONS_BG)
                        pbtn.configure(bg='#ffeb99' if page_idx > 0 else BUTTONS_BG)
                        nbtn.configure(bg='#ffeb99' if page_idx < (pages-1) else BUTTONS_BG)
                        pbtn.pack(side='left', padx=6, pady=2)
                        lbl.pack(side='left', expand=True)
                        nbtn.pack(side='right', padx=6, pady=2)
                    except Exception:
                        pass

            # global bundle group navigation if needed
            try:
                if group_pages > 1:
                    nav = tk.Frame(btn_grid, bg=BUTTONS_BG)
                    nav.grid(row=1, column=0, columnspan=placeholders, sticky='ew', padx=4, pady=(2,0))
                    def go_prev_groups():
                        nonlocal bundle_group_page
                        bundle_group_page = max(0, bundle_group_page - 1)
                        rebuild_bundles(count)
                    def go_next_groups():
                        nonlocal bundle_group_page
                        bundle_group_page = min(group_pages - 1, bundle_group_page + 1)
                        rebuild_bundles(count)
                    pbtn = tk.Button(nav, text='◀ Bundles', command=go_prev_groups)
                    lbl = tk.Label(nav, text=f'Bundles: {bundle_group_page+1}/{group_pages}', bg=BUTTONS_BG)
                    nbtn = tk.Button(nav, text='Bundles ▶', command=go_next_groups)
                    pbtn.configure(bg='#ffeb99' if bundle_group_page > 0 else BUTTONS_BG)
                    nbtn.configure(bg='#ffeb99' if bundle_group_page < (group_pages-1) else BUTTONS_BG)
                    pbtn.pack(side='left', padx=6, pady=2)
                    lbl.pack(side='left', expand=True)
                    nbtn.pack(side='right', padx=6, pady=2)
            except Exception:
                pass
            # After constructing this page of bundles, scale button fonts and enforce
            # equal visual widths across all panel buttons so trays look consistent.
            try:
                btns_w = btns_frame.winfo_width() or btn_grid.winfo_reqwidth() or 600
                cols_eff = max(1, min(placeholders, len(ordered)))
                per_bundle_w = max(40, int((btns_w - (cols_eff * 12)) / max(1, cols_eff)))
                # choose font size proportional to per-bundle width (similar to buttons.py)
                fw = max(7, min(12, per_bundle_w // 30))
                btn_font = tkfont.Font(size=fw)
                # measure average character width for this font to convert pixels->chars
                try:
                    char_w = tkfont.Font(font=btn_font).measure('0') or 8
                except Exception:
                    char_w = 8
                # target button pixel width is a fraction of the per-bundle width
                target_btn_px = max(20, int(per_bundle_w * 0.18))
                target_btn_chars = max(2, int(target_btn_px / max(1, char_w)))
                for w in panel_button_widgets:
                    try:
                        w.configure(font=btn_font, width=target_btn_chars)
                    except Exception:
                        pass
            except Exception:
                pass
        else:
            # no panels loaded yet: render empty placeholders
            for bi in range(placeholders):
                bf = tk.LabelFrame(btn_grid, text=f'Bundle {bi+1}', bg=BUTTONS_BG)
                bf.grid(row=0, column=bi, sticky='nsew', padx=4, pady=4)
                try:
                    bf.grid_propagate(False)
                    bf.configure(height=max(44, btns_frame.winfo_height() - 16))
                except Exception:
                    pass
                try:
                    placeholder = tk.Label(bf, text='', bg=BUTTONS_BG)
                    placeholder.pack(expand=True, fill='both')
                except Exception:
                    pass

    rebuild_bundles(5)

    def process_selected_ehx(evt=None):
        nonlocal panels_loaded
        try:
            # Diagnostic: record that the handler was invoked and current selection/folder
            sel_dbg = file_listbox.curselection()
            try:
                sel_txt = file_listbox.get(sel_dbg[0]) if sel_dbg else '<none>'
            except Exception:
                sel_txt = '<error>'
            try:
                fentry = folder_entry.get() or os.getcwd()
            except Exception:
                fentry = os.getcwd()
            try:
                log_debug(f"process_selected_ehx invoked sel={sel_dbg} sel_txt={sel_txt} folder_entry={fentry}")
            except Exception:
                pass
        except Exception:
            pass
        sel = file_listbox.curselection()
        if not sel:
            return
        fname = file_listbox.get(sel[0])
        folder = folder_entry.get() or os.getcwd()
        full = os.path.join(folder, fname)
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
                try:
                    log_debug(f"process_selected_ehx about to call parse_panels for {full}")
                except Exception:
                    pass
                panels, materials_map = parse_panels(full) or ([], {})
                try:
                    if not panels:
                        log_debug(f"parse_panels returned empty, falling back to parse_panels_minimal for {full}")
                        panels, materials_map = parse_panels_minimal(full) or ([], {})
                        log_debug(f"parse_panels_minimal returned count={len(panels)}")
                except Exception:
                    pass
                try:
                    # Diagnostic: log what parse_panels returned
                    ptype = type(panels).__name__
                    pcount = len(panels) if hasattr(panels, '__len__') else 0
                    try:
                        sample = panels[:6] if isinstance(panels, (list, tuple)) else list(panels.keys())[:6]
                    except Exception:
                        sample = None
                    log_debug(f"parse result type={ptype} count={pcount} sample={sample}")
                except Exception:
                    pass
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
        panel_materials_map.clear()
        if isinstance(materials_map, dict):
            for k, v in materials_map.items():
                panel_materials_map[k] = v or []

        try:
            jp = extract_jobpath(full) if callable(extract_jobpath) else ''
            if jp:
                path_val.config(text=jp)
            job_val.config(text=os.path.splitext(fname)[0])
        except Exception:
            pass

        # write expected/materials logs next to the processed file (auto-create/clear)
        try:
            # prefer PV0825 writer if available; otherwise use local helper
            writer = globals().get('write_expected_and_materials_logs')
            if not writer:
                # import local reference
                writer = write_expected_and_materials_logs
            try:
                log_debug(f"calling writer for file={full} writer={'external' if writer is not None else 'none'})")
            except Exception:
                pass
            try:
                writer(full, panels_by_name, panel_materials_map)
                try:
                    log_debug(f"writer completed for {full}")
                except Exception:
                    pass
            except Exception as we:
                try:
                    log_debug(f"writer failed for {full} exception={we}")
                except Exception:
                    pass
                # last-resort: attempt best-effort write using local helpers
                try:
                    import datetime as _dt
                    ts = _dt.datetime.now(_dt.timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
                    folder = os.path.dirname(full)
                    fname = os.path.basename(full)
                    with open(os.path.join(folder, 'expected.log'), 'w', encoding='utf-8') as _fh:
                        _fh.write(f"=== expected.log cleared at {ts} for {fname} ===\n")
                    with open(os.path.join(folder, 'materials.log'), 'w', encoding='utf-8') as _fh:
                        _fh.write(f"=== materials.log cleared at {ts} for {fname} ===\n")
                    try:
                        log_debug(f"fallback writer created minimal logs for {full}")
                    except Exception:
                        pass
                except Exception as fe:
                    try:
                        log_debug(f"fallback writer failed for {full} exception={fe}")
                    except Exception:
                        pass
        except Exception as e:
            try:
                log_debug(f"exception around writer block for {full} exception={e}")
            except Exception:
                pass

        panels_loaded = True
        rebuild_bundles(5)
        # After rebuild, schedule a short task to ensure buttons are visible
        def _ensure_buttons_visible():
            try:
                for w in list(panel_button_widgets):
                    try:
                        if w:
                            try:
                                w.configure(bg='#ffffff', fg='#000000')
                            except Exception:
                                pass
                            try:
                                w.lift()
                            except Exception:
                                pass
                    except Exception:
                        pass
            except Exception:
                pass

        try:
            root.after(180, _ensure_buttons_visible)
        except Exception:
            try:
                _ensure_buttons_visible()
            except Exception:
                pass

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
                fh.write(json.dumps({'ts': _dt.datetime.now(_dt.timezone.utc).isoformat(), 'action': 'lock', 'state': st}) + '\n')
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

    return root

if __name__ == '__main__':
    app = make_gui()
    app.mainloop()
