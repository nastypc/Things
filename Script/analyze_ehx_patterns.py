#!/usr/bin/env python3
"""
Analyze EHX files to identify FamilyMemberName patterns that need exclusion rules
"""
import os
import xml.etree.ElementTree as ET
from collections import defaultdict, Counter
import sys

#!/usr/bin/env python3
"""
Analyze EHX files to identify FamilyMemberName patterns for FamilyMember 32 (LType), 42 (Ladder), and 6 (Loose Members)
"""
import os
import xml.etree.ElementTree as ET
from collections import defaultdict, Counter
import sys

def analyze_ehx_files(ehx_path):
    """Analyze EHX files in the given folder or a single EHX file for SubAssembly patterns and their associated parts"""

    subassembly_occurrences = defaultdict(lambda: defaultdict(lambda: {'count': 0, 'fm': '', 'fm_name': '', 'descriptions': []}))
    subassembly_info = {}  # guid -> (name, family_member)
    subassembly_fm = {}  # name -> family_member
    family_member_patterns = defaultdict(Counter)
    subassembly_patterns = defaultdict(Counter)

    ehx_files = []
    if os.path.isfile(ehx_path) and ehx_path.lower().endswith('.ehx'):
        ehx_files = [ehx_path]
    elif os.path.isdir(ehx_path):
        for root, dirs, files in os.walk(ehx_path):
            for file in files:
                if file.lower().endswith('.ehx'):
                    ehx_files.append(os.path.join(root, file))
    else:
        print(f"Invalid path: {ehx_path}")
        return {}, {}, {}, {}, [], {}

    print(f"Found {len(ehx_files)} EHX file(s) to analyze")

    for ehx_file in ehx_files:
        try:
            tree = ET.parse(ehx_file)
            root = tree.getroot()

            print(f"Processing: {os.path.basename(ehx_file)}")
            
            # Validate XML structure
            if root.tag != 'EHX':
                print(f"Warning: Root element is '{root.tag}', expected 'EHX'")
            
            # First, collect SubAssembly info
            subassembly_count = 0
            for sub_el in root.findall('.//SubAssembly'):
                guid_el = sub_el.find('SubAssemblyGuid')
                name_el = sub_el.find('SubAssemblyName')
                fm_el = sub_el.find('FamilyMember')
                if guid_el is not None and guid_el.text:
                    guid = guid_el.text.strip()
                    name = name_el.text.strip() if name_el is not None and name_el.text else ""
                    fm = fm_el.text.strip() if fm_el is not None and fm_el.text else ""
                    subassembly_info[guid] = (name, fm)
                    if name:
                        subassembly_fm[name] = fm
                        subassembly_count += 1
            
            print(f"  Found {subassembly_count} SubAssemblies")
            
            # Then, collect parts for each SubAssembly
            board_count = 0
            subassembly_board_count = 0
            for board_el in root.findall('.//Board'):
                board_count += 1
                guid_el = board_el.find('SubAssemblyGuid')
                if guid_el is not None and guid_el.text:
                    guid = guid_el.text.strip()
                    if guid in subassembly_info:
                        subassembly_board_count += 1
                        sub_name, fm = subassembly_info[guid]
                        if not sub_name:
                            # If SubAssemblyName is empty, use FamilyMemberName from the board
                            fm_name_el = board_el.find('FamilyMemberName')
                            if fm_name_el is not None and fm_name_el.text:
                                sub_name = fm_name_el.text.strip()

                        subassembly_fm[sub_name] = fm

                        fam_member_name_el = board_el.find('FamilyMemberName')
                        fam_member_name = fam_member_name_el.text.strip() if fam_member_name_el is not None and fam_member_name_el.text else ""
                        fam_member_el = board_el.find('FamilyMember')
                        fam_member = fam_member_el.text.strip() if fam_member_el is not None and fam_member_el.text else ""
                        label_el = board_el.find('Label')
                        label = label_el.text.strip() if label_el is not None and label_el.text else ""
                        material_el = board_el.find('Material')
                        description = ""
                        if material_el is not None:
                            desc_el = material_el.find('Description')
                            description = desc_el.text.strip() if desc_el is not None and desc_el.text else ""

                        if fam_member_name or description:
                            key = label if label else fam_member_name
                            # Track by GUID to show individual SubAssembly occurrences
                            occurrence_key = f"{guid}_{key}"  # Unique key combining GUID and part key
                            subassembly_occurrences[guid][key]['count'] += 1
                            subassembly_occurrences[guid][key]['fm'] = fam_member
                            subassembly_occurrences[guid][key]['fm_name'] = fam_member_name
                            subassembly_occurrences[guid][key]['descriptions'].append(description)

            print(f"  Found {board_count} total Boards, {subassembly_board_count} in SubAssemblies")

            # Collect ALL Board elements for comprehensive pattern analysis
            pattern_count = 0
            beam_pocket_indicators = []
            for board_el in root.findall('.//Board'):
                fam_member = board_el.find('FamilyMember')
                fam_member_name = board_el.find('FamilyMemberName')
                if fam_member is not None and fam_member_name is not None:
                    fam_member_text = fam_member.text.strip() if fam_member.text else ""
                    fam_member_name_text = fam_member_name.text.strip() if fam_member_name.text else ""
                    if fam_member_text and fam_member_name_text:
                        family_member_patterns[fam_member_text][fam_member_name_text] += 1
                        pattern_count += 1

                        # Check for potential beam pocket indicators
                        name_lower = fam_member_name_text.lower()
                        if any(term in name_lower for term in ['beam', 'pocket', 'notch', 'cutout', 'opening', 'hole', 'slot']):
                            beam_pocket_indicators.append({
                                'family_member': fam_member_text,
                                'name': fam_member_name_text,
                                'type': 'Board'
                            })

            # Also collect SubAssembly patterns
            for sub_el in root.findall('.//SubAssembly'):
                sub_name = sub_el.find('SubAssemblyName')
                fam_member = sub_el.find('FamilyMember')
                fam_member_name = sub_el.find('FamilyMemberName')
                if fam_member is not None and fam_member_name is not None:
                    fam_member_text = fam_member.text.strip() if fam_member.text else ""
                    fam_member_name_text = fam_member_name.text.strip() if fam_member_name.text else ""
                    if fam_member_text and fam_member_name_text:
                        family_member_patterns[fam_member_text][fam_member_name_text] += 1
                        sub_name_text = sub_name.text.strip() if sub_name is not None and sub_name.text else fam_member_name_text
                        subassembly_patterns[fam_member_text][sub_name_text] += 1
                        pattern_count += 1

                        # Check SubAssembly names for beam pocket indicators
                        if sub_name_text:
                            name_lower = sub_name_text.lower()
                            if any(term in name_lower for term in ['beam', 'pocket', 'notch', 'cutout', 'opening', 'hole', 'slot']):
                                beam_pocket_indicators.append({
                                    'family_member': fam_member_text,
                                    'name': sub_name_text,
                                    'type': 'SubAssembly'
                                })

            print(f"  Collected {pattern_count} pattern instances from {len(family_member_patterns)} Family Members")
            if beam_pocket_indicators:
                print(f"  Found {len(beam_pocket_indicators)} potential beam pocket indicators")

        except Exception as e:
            print(f"Error parsing {ehx_file}: {e}")
            continue

    # Single-file validation summary
    if len(ehx_files) == 1:
        print(f"\n=== SINGLE-FILE ANALYSIS SUMMARY ===")
        print(f"File: {os.path.basename(ehx_files[0])}")
        print(f"SubAssemblies found: {len(subassembly_fm)}")
        print(f"Family Members identified: {len(family_member_patterns)}")
        total_patterns = sum(len(patterns) for patterns in family_member_patterns.values())
        print(f"Total unique patterns: {total_patterns}")
        total_occurrences = sum(sum(patterns.values()) for patterns in family_member_patterns.values())
        print(f"Total pattern occurrences: {total_occurrences}")
        
        # Check for data consistency
        if subassembly_occurrences:
            parts_count = sum(sum(info['count'] for info in parts.values()) for parts in subassembly_occurrences.values())
            print(f"Parts in SubAssemblies: {parts_count}")
        
    return subassembly_occurrences, subassembly_fm, family_member_patterns, subassembly_patterns, beam_pocket_indicators, subassembly_info

def get_panel_type_category(sub_name, fm_id):
    """Categorize SubAssembly by panel type for sorting purposes"""
    name_lower = sub_name.lower()

    if fm_id == '32':  # LType Family Member
        if 'ltype' in name_lower:
            if '2s' in name_lower:
                return '1_LType_2S'
            elif '3s' in name_lower:
                return '1_LType_3S'
            else:
                return '1_LType_Standard'
        elif 'critical stud' in name_lower:
            return '2_Critical_Stud'
        elif 'end stud' in name_lower:
            return '3_End_Stud'
        elif 'stud' in name_lower:
            return '4_Stud'
        else:
            return '9_Other'

    elif fm_id == '25':  # Openings Family Member
        if name_lower.startswith('dr-'):
            if 'gar' in name_lower:
                return '1_Door_Garage'
            elif 'ent' in name_lower:
                return '1_Door_Entry'
            else:
                return '1_Door_Other'
        elif 'garage' in name_lower:
            return '2_Garage'
        elif 'patio' in name_lower:
            return '3_Patio'
        elif 'hdr' in name_lower:
            return '4_Header'
        elif any(char.isdigit() for char in sub_name) and ('x' in sub_name or 'l' in sub_name):
            return '5_Window'
        else:
            return '9_Other'

    elif fm_id == '42':  # Ladder Family Member
        return '1_Ladder'

    return '9_Other'

def print_analysis(subassembly_occurrences, subassembly_fm, family_member_patterns, subassembly_patterns, beam_pocket_indicators, subassembly_info):
    """Print the analysis results for SubAssembly parts and FamilyMember patterns"""

    print("\n=== SUBASSEMBLY ANALYSIS (FamilyMembers 32, 42, 25) ===")
    print("CONFIRMED SUBASSEMBLY FAMILY MEMBERS:")
    print("- FM32 (LType): Contains SubAssemblies like LType, Critical Stud, End Stud Assembly")
    print("- FM42 (Ladder): Contains SubAssemblies for ladder components")
    print("- FM25 (Openings): Contains SubAssemblies for openings like BSMT-HDR, 49x63-L2")
    print("\nEach of these FamilyMembers contains SubAssemblies with associated material parts.")
    print()

    # Group SubAssemblies by their FamilyMember - now using GUIDs for individual occurrences
    subassembly_by_fm = defaultdict(list)
    for guid, parts in subassembly_occurrences.items():
        if guid in subassembly_info:
            sub_name, fm = subassembly_info[guid]
            if fm in ['32', '42', '25']:
                subassembly_by_fm[fm].append((guid, sub_name))

    for fm_id in ['32', '42', '25']:
        if fm_id in subassembly_by_fm:
            fm_name = {'32': 'LType', '42': 'Ladder', '25': 'Openings'}.get(fm_id, f'FM{fm_id}')
            print(f"FAMILY MEMBER {fm_id} ({fm_name}) SUBASSEMBLIES:")
            print("-" * 45)

            # Sort by panel type category first, then by name
            sorted_subassemblies = sorted(
                subassembly_by_fm[fm_id],
                key=lambda x: (get_panel_type_category(x[1], fm_id), x[1])
            )

            for guid, sub_name in sorted_subassemblies:
                if guid in subassembly_occurrences:
                    panel_category = get_panel_type_category(sub_name, fm_id)
                    category_display = panel_category.split('_', 1)[1].replace('_', ' ') if '_' in panel_category else panel_category
                    print(f"\n• {sub_name} (GUID: {guid[:8]}...) (FM{fm_id}) - {category_display}")
                    print("   Associated Material Parts:")
                    for key, info in sorted(subassembly_occurrences[guid].items()):
                        count = info['count']
                        fm = info['fm']
                        fm_name_part = info['fm_name']
                        descriptions = info['descriptions']
                        if key != fm_name_part:
                            display = f"{key} ({count}) - {fm_name_part}" if fm else f"{key} ({count}) - {fm_name_part}"
                        else:
                            display = f"{fm_name_part} ({count})" if fm else f"{fm_name_part} ({count})"
                        print(f"    ├── {display}")
                        unique_descriptions = list(set(descriptions))
                        for desc in unique_descriptions:
                            print(f"        - {desc}")
            print()

    print("\n=== LOOSE MATERIALS ANALYSIS (All FamilyMembers except 32, 42, 25) ===")

    # Collect all loose materials (excluding SubAssembly FamilyMembers)
    loose_materials = {}  # Will store (fm_id, name) -> count
    loose_subassemblies = {}
    loose_fm_ids = [fm for fm in family_member_patterns.keys() if fm not in ['32', '42', '25']]

    for fm_id in loose_fm_ids:
        if fm_id in family_member_patterns:
            for name, count in family_member_patterns[fm_id].items():
                key = (fm_id, name)  # Store as tuple to preserve FM ID
                if key in loose_materials:
                    loose_materials[key] += count
                else:
                    loose_materials[key] = count
        if fm_id in subassembly_patterns:
            for name, count in subassembly_patterns[fm_id].items():
                if name in loose_subassemblies:
                    loose_subassemblies[name] += count
                else:
                    loose_subassemblies[name] = count

    total_loose_patterns = len(loose_materials)
    total_loose_occurrences = sum(loose_materials.values())
    print(f"Total unique loose material patterns: {total_loose_patterns}")
    print(f"Total occurrences across all EHX files: {total_loose_occurrences}")

    print("\nDETAILED LOOSE MATERIAL PATTERN LIST (Sorted by Occurrence):")
    print("-" * 60)
    print("FM ID: Pattern Name\t\t\t\tOccurrences")
    print("-" * 60)

    # Sort by occurrence count (descending), then by FM ID, then by name
    sorted_loose = sorted(loose_materials.items(), key=lambda x: (-x[1], x[0][0], x[0][1]))

    for (fm_id, name), count in sorted_loose:
        # Format the pattern name with proper spacing
        name_display = name[:35] + "..." if len(name) > 35 else name
        print(f"FM{fm_id}: {name_display}\t\t{count}")

    if loose_subassemblies:
        print("\nTop Loose Material SubAssembly Patterns (by occurrence):")
        for name, count in sorted(loose_subassemblies.items(), key=lambda x: x[1], reverse=True)[:10]:  # Top 10
            print(f"  {name}: {count}")

    # Show breakdown by FamilyMember
    print("\nLoose Material Breakdown by FamilyMember:")
    for fm_id in sorted(loose_fm_ids):
        if fm_id in family_member_patterns and family_member_patterns[fm_id]:
            total_count = sum(family_member_patterns[fm_id].values())
            print(f"  FM{fm_id}: {len(family_member_patterns[fm_id])} patterns, {total_count} total occurrences")

    print("\n=== FAMILY MEMBER 32 (LType) ANALYSIS ===")
    if '32' in family_member_patterns:
        print("FamilyMemberName patterns for FamilyMember 32:")
        for name, count in sorted(family_member_patterns['32'].items(), key=lambda x: x[1], reverse=True):
            print(f"  {name}: {count}")

        print("\nSubAssemblyName patterns for FamilyMember 32:")
        for name, count in sorted(subassembly_patterns['32'].items(), key=lambda x: x[1], reverse=True):
            print(f"  {name}: {count}")

    print("\n=== FAMILY MEMBER 42 (Ladder) ANALYSIS ===")
    if '42' in family_member_patterns:
        print("FamilyMemberName patterns for FamilyMember 42:")
        for name, count in sorted(family_member_patterns['42'].items(), key=lambda x: x[1], reverse=True):
            print(f"  {name}: {count}")

        print("\nSubAssemblyName patterns for FamilyMember 42:")
        for name, count in sorted(subassembly_patterns['42'].items(), key=lambda x: x[1], reverse=True):
            print(f"  {name}: {count}")

    print("\n=== COMBINED SUMMARY ===")

    # Calculate loose materials totals
    loose_fm_ids = [fm for fm in family_member_patterns.keys() if fm not in ['32', '42', '25']]
    loose_patterns_total = sum(len(family_member_patterns.get(fm, {})) for fm in loose_fm_ids)
    loose_occurrences_total = sum(sum(family_member_patterns.get(fm, {}).values()) for fm in loose_fm_ids)

    # Calculate SubAssembly FamilyMember totals
    subassembly_patterns_total = len(family_member_patterns.get('32', {})) + len(family_member_patterns.get('42', {})) + len(family_member_patterns.get('25', {}))
    subassembly_occurrences_total = sum(family_member_patterns.get('32', {}).values()) + sum(family_member_patterns.get('42', {}).values()) + sum(family_member_patterns.get('25', {}).values())

    print(f"Loose Materials: {loose_patterns_total} patterns, {loose_occurrences_total} occurrences")
    print(f"SubAssembly FamilyMembers (32, 42, 25): {subassembly_patterns_total} patterns, {subassembly_occurrences_total} occurrences")
    print(f"Combined Total: {loose_patterns_total + subassembly_patterns_total} patterns, {loose_occurrences_total + subassembly_occurrences_total} occurrences")

    # Show breakdown
    print("\nLoose Materials by FamilyMember:")
    for fm_id in sorted(loose_fm_ids):
        if fm_id in family_member_patterns and family_member_patterns[fm_id]:
            total_count = sum(family_member_patterns[fm_id].values())
            print(f"  - FM{fm_id}: {len(family_member_patterns[fm_id])} patterns, {total_count} occurrences")

    print("\nSubAssembly FamilyMembers:")
    for fm_id in ['32', '42', '25']:
        if fm_id in family_member_patterns and family_member_patterns[fm_id]:
            total_count = sum(family_member_patterns[fm_id].values())
            print(f"  - FM{fm_id}: {len(family_member_patterns[fm_id])} patterns, {total_count} occurrences")

    print("\n=== SUBASSEMBLY FAMILY MEMBERS (32, 42, 25) ANALYSIS ===")
    for fm_id in ['32', '42', '25']:
        if fm_id in family_member_patterns and family_member_patterns[fm_id]:
            print(f"\nFamilyMember {fm_id}:")
            for name, count in sorted(family_member_patterns[fm_id].items(), key=lambda x: x[1], reverse=True)[:15]:  # Top 15
                print(f"  {name}: {count}")

            if fm_id in subassembly_patterns and subassembly_patterns[fm_id]:
                print(f"\nSubAssembly patterns for FamilyMember {fm_id}:")
                for name, count in sorted(subassembly_patterns[fm_id].items(), key=lambda x: x[1], reverse=True)[:10]:  # Top 10
                    print(f"  {name}: {count}")

    print("\n=== ALL FAMILY MEMBER PATTERNS (Sorted by Occurrence) ===")
    all_patterns = []
    for fm_id, patterns in family_member_patterns.items():
        for name, count in patterns.items():
            all_patterns.append((fm_id, name, count))
    all_patterns.sort(key=lambda x: x[2], reverse=True)
    for fm_id, name, count in all_patterns[:50]:  # Top 50
        print(f"  FM{fm_id}: {name} ({count})")

    # NEW: Family Member Relationship Analysis
    print("\n=== FAMILY MEMBER RELATIONSHIP ANALYSIS ===")
    print("SUBASSEMBLY FAMILY MEMBERS (32, 42, 25):")
    
    # Analyze parts within SubAssemblies to see their Family Members
    subassembly_part_fms = defaultdict(Counter)
    for guid, parts in subassembly_occurrences.items():
        if guid in subassembly_info:
            sub_name, sub_fm = subassembly_info[guid]
            if sub_fm in ['32', '42', '25']:
                for key, info in parts.items():
                    part_fm = info['fm']
                    if part_fm:
                        subassembly_part_fms[sub_fm][part_fm] += info['count']
    
    for sub_fm in ['32', '42', '25']:
        if sub_fm in subassembly_part_fms:
            print(f"\n  FM{sub_fm} contains parts from:")
            for part_fm, count in sorted(subassembly_part_fms[sub_fm].items(), key=lambda x: x[1], reverse=True):
                print(f"    FM{part_fm}: {count} parts")
    
    print("\nLOOSE MATERIAL FAMILY MEMBERS (excluding 32, 42, 25):")
    loose_fms = [fm for fm in family_member_patterns.keys() if fm not in ['32', '42', '25']]
    for fm in sorted(loose_fms):
        if family_member_patterns[fm]:
            total_count = sum(family_member_patterns[fm].values())
            print(f"  FM{fm}: {len(family_member_patterns[fm])} patterns, {total_count} total occurrences")

    print("\n=== BEAM POCKET ANALYSIS ===")
    if beam_pocket_indicators:
        print(f"Found {len(beam_pocket_indicators)} potential beam pocket indicators:")
        for indicator in beam_pocket_indicators:
            indicator_type = indicator.get('type', 'Unknown')
            print(f"  FM{indicator['family_member']}: {indicator['name']} ({indicator_type})")
    else:
        print("No beam pocket indicators found in the analyzed files.")

def generate_pattern_list_file(subassembly_occurrences, subassembly_fm, family_member_patterns, subassembly_patterns, beam_pocket_indicators, subassembly_info, output_file):
    """Generate a comprehensive Pattern List.txt file including individual SubAssembly occurrences"""

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("EHX SUBASSEMBLY AND FAMILY MEMBER ANALYSIS\n")
        f.write("=" * 70 + "\n\n")

        f.write("CONFIRMED SUBASSEMBLY FAMILY MEMBERS:\n")
        f.write("- FM32 (LType): Contains SubAssemblies like LType, Critical Stud, End Stud Assembly\n")
        f.write("- FM42 (Ladder): Contains SubAssemblies for ladder components\n")
        f.write("- FM25 (Openings): Contains SubAssemblies for openings like BSMT-HDR, 49x63-L2\n")
        f.write("\nEach of these FamilyMembers contains SubAssemblies with associated material parts.\n\n")

        # Group SubAssemblies by their FamilyMember - now using GUIDs for individual occurrences
        subassembly_by_fm = defaultdict(list)
        for guid, parts in subassembly_occurrences.items():
            if guid in subassembly_info:
                sub_name, fm = subassembly_info[guid]
                if fm in ['32', '42', '25']:
                    subassembly_by_fm[fm].append((guid, sub_name))

        for fm_id in ['32', '42', '25']:
            if fm_id in subassembly_by_fm:
                fm_name = {'32': 'LType', '42': 'Ladder', '25': 'Openings'}.get(fm_id, f'FM{fm_id}')
                f.write(f"FAMILY MEMBER {fm_id} ({fm_name}) SUBASSEMBLIES:\n")
                f.write("-" * 45 + "\n")

                # Sort by panel type category first, then by name
                sorted_subassemblies = sorted(
                    subassembly_by_fm[fm_id],
                    key=lambda x: (get_panel_type_category(x[1], fm_id), x[1])
                )

                for guid, sub_name in sorted_subassemblies:
                    if guid in subassembly_occurrences:
                        panel_category = get_panel_type_category(sub_name, fm_id)
                        category_display = panel_category.split('_', 1)[1].replace('_', ' ') if '_' in panel_category else panel_category
                        f.write(f"\n• {sub_name} (GUID: {guid[:8]}...) (FM{fm_id}) - {category_display}\n")
                        f.write("   Associated Material Parts:\n")
                        for key, info in sorted(subassembly_occurrences[guid].items()):
                            count = info['count']
                            fm = info['fm']
                            fm_name_part = info['fm_name']
                            descriptions = info['descriptions']
                            if key != fm_name_part:
                                display = f"{key} ({count}) - {fm_name_part}" if fm else f"{key} ({count}) - {fm_name_part}"
                            else:
                                display = f"{fm_name_part} ({count})" if fm else f"{fm_name_part} ({count})"
                            f.write(f"    ├── {display}\n")
                            unique_descriptions = list(set(descriptions))
                            for desc in unique_descriptions:
                                f.write(f"        - {desc}\n")
                f.write("\n")

        f.write("\n" + "=" * 70 + "\n")
        f.write("LOOSE MATERIALS ANALYSIS (All FamilyMembers except 32, 42, 25):\n")
        f.write("=" * 70 + "\n\n")

        # Collect all loose materials (excluding SubAssembly FamilyMembers)
        loose_materials = {}  # Will store (fm_id, name) -> count
        loose_subassemblies = {}
        loose_fm_ids = [fm for fm in family_member_patterns.keys() if fm not in ['32', '42', '25']]

        for fm_id in loose_fm_ids:
            if fm_id in family_member_patterns:
                for name, count in family_member_patterns[fm_id].items():
                    key = (fm_id, name)  # Store as tuple to preserve FM ID
                    if key in loose_materials:
                        loose_materials[key] += count
                    else:
                        loose_materials[key] = count
            if fm_id in subassembly_patterns:
                for name, count in subassembly_patterns[fm_id].items():
                    if name in loose_subassemblies:
                        loose_subassemblies[name] += count
                    else:
                        loose_subassemblies[name] = count

        total_loose_patterns = len(loose_materials)
        total_loose_occurrences = sum(loose_materials.values())
        f.write(f"Total unique loose material patterns: {total_loose_patterns}\n")
        f.write(f"Total occurrences across all EHX files: {total_loose_occurrences}\n\n")

        f.write("DETAILED LOOSE MATERIAL PATTERN LIST (Sorted by Occurrence):\n")
        f.write("-" * 60 + "\n")
        f.write("FM ID: Pattern Name\t\t\t\tOccurrences\n")
        f.write("-" * 60 + "\n")

        # Sort by occurrence count (descending), then by FM ID, then by name
        sorted_loose = sorted(loose_materials.items(), key=lambda x: (-x[1], x[0][0], x[0][1]))

        for (fm_id, name), count in sorted_loose:
            # Format the pattern name with proper spacing
            name_display = name[:35] + "..." if len(name) > 35 else name
            f.write(f"FM{fm_id}: {name_display}\t\t{count}\n")

        f.write("\n\nLOOSE MATERIAL SUBASSEMBLY PATTERNS (Sorted by Occurrence):\n")
        f.write("-" * 60 + "\n")
        f.write("SubAssembly Name\t\t\t\tOccurrences\n")
        f.write("-" * 60 + "\n")

        for name, count in sorted(loose_subassemblies.items(), key=lambda x: x[1], reverse=True):
            name_display = name[:35] + "..." if len(name) > 35 else name
            f.write(f"{name_display}\t\t{count}\n")

        # Show breakdown by FamilyMember
        f.write("\n\nLOOSE MATERIAL BREAKDOWN BY FAMILY MEMBER:\n")
        f.write("-" * 50 + "\n")
        for fm_id in sorted(loose_fm_ids):
            if fm_id in family_member_patterns and family_member_patterns[fm_id]:
                total_count = sum(family_member_patterns[fm_id].values())
                f.write(f"FM{fm_id}: {len(family_member_patterns[fm_id])} patterns, {total_count} total occurrences\n")

        # Analyze FamilyMember 32 (LType)
        if '32' in family_member_patterns:
            f.write("\n\n" + "=" * 70 + "\n")
            f.write("FAMILY MEMBER 32 (LType) ANALYSIS:\n")
            f.write("-" * 35 + "\n")
            total_patterns_32 = len(family_member_patterns['32'])
            total_occurrences_32 = sum(family_member_patterns['32'].values())
            f.write(f"Total unique FamilyMemberName patterns: {total_patterns_32}\n")
            f.write(f"Total occurrences across all EHX files: {total_occurrences_32}\n\n")

            f.write("DETAILED PATTERN LIST (FamilyMember 32):\n")
            f.write("-" * 40 + "\n")
            f.write("Pattern Name\t\t\t\tOccurrences\n")
            f.write("-" * 60 + "\n")

            for name, count in sorted(family_member_patterns['32'].items(), key=lambda x: x[1], reverse=True):
                # Format the output with proper tab spacing
                name_display = name[:35] + "..." if len(name) > 35 else name
                f.write(f"{name_display}\t\t{count}\n")

            f.write("\n\nASSOCIATED SUBASSEMBLY PATTERNS (FamilyMember 32):\n")
            f.write("-" * 50 + "\n")
            f.write("SubAssembly Name\t\t\t\tOccurrences\n")
            f.write("-" * 60 + "\n")

            for name, count in sorted(subassembly_patterns['32'].items(), key=lambda x: x[1], reverse=True):
                name_display = name[:35] + "..." if len(name) > 35 else name
                f.write(f"{name_display}\t\t{count}\n")

        # Analyze FamilyMember 42 (Ladder)
        if '42' in family_member_patterns:
            f.write("\n\n" + "=" * 70 + "\n")
            f.write("FAMILY MEMBER 42 (Ladder) ANALYSIS:\n")
            f.write("-" * 36 + "\n")
            total_patterns_42 = len(family_member_patterns['42'])
            total_occurrences_42 = sum(family_member_patterns['42'].values())
            f.write(f"Total unique FamilyMemberName patterns: {total_patterns_42}\n")
            f.write(f"Total occurrences across all EHX files: {total_occurrences_42}\n\n")

            f.write("DETAILED PATTERN LIST (FamilyMember 42):\n")
            f.write("-" * 40 + "\n")
            f.write("Pattern Name\t\t\t\tOccurrences\n")
            f.write("-" * 60 + "\n")

            for name, count in sorted(family_member_patterns['42'].items(), key=lambda x: x[1], reverse=True):
                name_display = name[:35] + "..." if len(name) > 35 else name
                f.write(f"{name_display}\t\t{count}\n")

            f.write("\n\nASSOCIATED SUBASSEMBLY PATTERNS (FamilyMember 42):\n")
            f.write("-" * 50 + "\n")
            f.write("SubAssembly Name\t\t\t\tOccurrences\n")
            f.write("-" * 60 + "\n")

            for name, count in sorted(subassembly_patterns['42'].items(), key=lambda x: x[1], reverse=True):
                name_display = name[:35] + "..." if len(name) > 35 else name
                f.write(f"{name_display}\t\t{count}\n")

        # Combined summary
        f.write("\n\n" + "=" * 70 + "\n")
        f.write("COMBINED SUMMARY (Loose Materials + SubAssembly FamilyMembers):\n")
        f.write("-" * 60 + "\n")

        # Calculate loose materials totals
        loose_fm_ids = [fm for fm in family_member_patterns.keys() if fm not in ['32', '42', '25']]
        loose_patterns_total = sum(len(family_member_patterns.get(fm, {})) for fm in loose_fm_ids)
        loose_occurrences_total = sum(sum(family_member_patterns.get(fm, {}).values()) for fm in loose_fm_ids)

        # Calculate SubAssembly FamilyMember totals
        subassembly_patterns_total = len(family_member_patterns.get('32', {})) + len(family_member_patterns.get('42', {})) + len(family_member_patterns.get('25', {}))
        subassembly_occurrences_total = sum(family_member_patterns.get('32', {}).values()) + sum(family_member_patterns.get('42', {}).values()) + sum(family_member_patterns.get('25', {}).values())

        f.write(f"Loose Materials: {loose_patterns_total} patterns, {loose_occurrences_total} occurrences\n")
        f.write(f"SubAssembly FamilyMembers (32, 42, 25): {subassembly_patterns_total} patterns, {subassembly_occurrences_total} occurrences\n")
        f.write(f"Combined Total: {loose_patterns_total + subassembly_patterns_total} patterns, {loose_occurrences_total + subassembly_occurrences_total} occurrences\n")

        # Show breakdown
        f.write("\nLoose Materials by FamilyMember:\n")
        for fm_id in sorted(loose_fm_ids):
            if fm_id in family_member_patterns and family_member_patterns[fm_id]:
                total_count = sum(family_member_patterns[fm_id].values())
                f.write(f"  - FM{fm_id}: {len(family_member_patterns[fm_id])} patterns, {total_count} occurrences\n")

        f.write("\nSubAssembly FamilyMembers:\n")
        for fm_id in ['32', '42', '25']:
            if fm_id in family_member_patterns and family_member_patterns[fm_id]:
                total_count = sum(family_member_patterns[fm_id].values())
                f.write(f"  - FM{fm_id}: {len(family_member_patterns[fm_id])} patterns, {total_count} occurrences\n")

        f.write("\n\nCOMPLETE COMBINED PATTERN LIST (Grouped by Type):\n")
        f.write("-" * 55 + "\n")

        # List ALL patterns from ALL Family Members (including 32, 42, 25)
        all_fm_ids = sorted(family_member_patterns.keys())
        if any(fm in family_member_patterns for fm in all_fm_ids):
            f.write("\nALL FAMILY MEMBERS (Including 32, 42, 25):\n")
            all_patterns_combined = []
            for fm_id in all_fm_ids:
                if fm_id in family_member_patterns:
                    for name, count in family_member_patterns[fm_id].items():
                        all_patterns_combined.append((fm_id, name, count))
            all_patterns_combined.sort(key=lambda x: x[2], reverse=True)
            for fm_id, name, count in all_patterns_combined:
                f.write(f"- FM{fm_id}: {name} ({count})\n")

        f.write("\n\nALL FAMILY MEMBER PATTERNS (Sorted by Occurrence):\n")
        f.write("-" * 50 + "\n")
        all_patterns = []
        for fm_id, patterns in family_member_patterns.items():
            for name, count in patterns.items():
                all_patterns.append((fm_id, name, count))
        all_patterns.sort(key=lambda x: x[2], reverse=True)
        for fm_id, name, count in all_patterns[:50]:
            f.write(f"FM{fm_id}: {name} ({count})\n")

        # NEW: Family Member Relationship Analysis
        f.write("\n\nFAMILY MEMBER RELATIONSHIP ANALYSIS:\n")
        f.write("-" * 40 + "\n")
        f.write("SUBASSEMBLY FAMILY MEMBERS (32, 42, 25):\n")
        
        # Analyze parts within SubAssemblies to see their Family Members
        subassembly_part_fms = defaultdict(Counter)
        for guid, parts in subassembly_occurrences.items():
            if guid in subassembly_info:
                sub_name, sub_fm = subassembly_info[guid]
                if sub_fm in ['32', '42', '25']:
                    for key, info in parts.items():
                        part_fm = info['fm']
                        if part_fm:
                            subassembly_part_fms[sub_fm][part_fm] += info['count']
        
        for sub_fm in ['32', '42', '25']:
            if sub_fm in subassembly_part_fms:
                f.write(f"\n  FM{sub_fm} contains parts from:\n")
                for part_fm, count in sorted(subassembly_part_fms[sub_fm].items(), key=lambda x: x[1], reverse=True):
                    f.write(f"    FM{part_fm}: {count} parts\n")
        
        f.write("\nLOOSE MATERIAL FAMILY MEMBERS (excluding 32, 42, 25):\n")
        loose_fms = [fm for fm in family_member_patterns.keys() if fm not in ['32', '42', '25']]
        for fm in sorted(loose_fms):
            if family_member_patterns[fm]:
                total_count = sum(family_member_patterns[fm].values())
                f.write(f"  FM{fm}: {len(family_member_patterns[fm])} patterns, {total_count} total occurrences\n")

        f.write("\n\n" + "=" * 70 + "\n")
        f.write("BEAM POCKET ANALYSIS:\n")
        f.write("=" * 70 + "\n\n")
        if beam_pocket_indicators:
            f.write(f"Found {len(beam_pocket_indicators)} potential beam pocket indicators:\n\n")
            for indicator in beam_pocket_indicators:
                indicator_type = indicator.get('type', 'Unknown')
                f.write(f"• FM{indicator['family_member']}: {indicator['name']} ({indicator_type})\n")
        else:
            f.write("No beam pocket indicators found in the analyzed files.\n")

if __name__ == "__main__":
    ehx_path = sys.argv[1] if len(sys.argv) > 1 else r"c:\Users\edward\Downloads\EHX\Script\Test"
    subassembly_occurrences, subassembly_fm, family_member_patterns, subassembly_patterns, beam_pocket_indicators, subassembly_info = analyze_ehx_files(ehx_path)
    print_analysis(subassembly_occurrences, subassembly_fm, family_member_patterns, subassembly_patterns, beam_pocket_indicators, subassembly_info)

    # Generate the Pattern List.txt file
    output_file = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ehx_path, "Pattern_List.txt") if os.path.isdir(ehx_path) else os.path.join(os.path.dirname(ehx_path), "Pattern_List.txt")
    generate_pattern_list_file(subassembly_occurrences, subassembly_fm, family_member_patterns, subassembly_patterns, beam_pocket_indicators, subassembly_info, output_file)
    print(f"\nPattern List.txt generated: {output_file}")

    # Open the output file
    try:
        os.startfile(output_file)
        print(f"Opening {output_file}...")
    except Exception as e:
        print(f"Could not open {output_file}: {e}")
