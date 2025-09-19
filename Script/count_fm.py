#!/usr/bin/env python3
"""
Simple script to count FM25 and FM32 materials in an EHX file
"""

import xml.etree.ElementTree as ET
import sys
import os

def count_fm_materials(ehx_file_path):
    """Count FM25 and FM32 materials in an EHX file"""
    try:
        tree = ET.parse(ehx_file_path)
        root = tree.getroot()

        fm_counts = {
            'FM25': 0,
            'FM32': 0
        }

        # Count materials by FamilyMember ID in Board elements
        for board in root.findall('.//Board'):
            fm_el = board.find('FamilyMember')
            fm_name_el = board.find('FamilyMemberName')
            label_el = board.find('Label')
            
            fm_id = fm_el.text.strip() if fm_el is not None and fm_el.text else ""
            fm_name = fm_name_el.text.strip() if fm_name_el is not None and fm_name_el.text else ""
            label = label_el.text.strip() if label_el is not None and label_el.text else ""
            
            if fm_id == '25':
                fm_counts['FM25'] += 1
                print(f"FM25 by ID (Board): {label} - {fm_name}")
            elif fm_id == '32':
                fm_counts['FM32'] += 1
                print(f"FM32 by ID (Board): {label} - {fm_name}")

        # Count SubAssembly elements by FamilyMember ID
        for sub_el in root.findall('.//SubAssembly'):
            fm_el = sub_el.find('FamilyMember')
            fm_name_el = sub_el.find('SubAssemblyName')
            label_el = sub_el.find('Label')
            
            fm_id = fm_el.text.strip() if fm_el is not None and fm_el.text else ""
            fm_name = fm_name_el.text.strip() if fm_name_el is not None and fm_name_el.text else ""
            label = label_el.text.strip() if label_el is not None and label_el.text else ""
            
            if fm_id == '25':
                fm_counts['FM25'] += 1
                print(f"FM25 by ID (SubAssembly): {label} - {fm_name}")
            elif fm_id == '32':
                fm_counts['FM32'] += 1
                print(f"FM32 by ID (SubAssembly): {label} - {fm_name}")

        # Also count by FamilyMemberName for verification
        fm_name_counts = {
            'FM25': 0,
            'FM32': 0
        }

        for board in root.findall('.//Board'):
            fm_name_el = board.find('FamilyMemberName')
            label_el = board.find('Label')
            
            if fm_name_el is not None and fm_name_el.text:
                fm_name = fm_name_el.text.strip().lower()
                label = label_el.text.strip() if label_el is not None and label_el.text else ""
                
                if 'fm25' in fm_name or fm_name in ['roughopening', 'opening']:
                    fm_name_counts['FM25'] += 1
                    print(f"FM25 by name (Board): {label} - {fm_name}")
                elif 'fm32' in fm_name or 'ltype' in fm_name or 'critical' in fm_name:
                    fm_name_counts['FM32'] += 1
                    print(f"FM32 by name (Board): {label} - {fm_name}")

        # Count SubAssembly names
        for sub_el in root.findall('.//SubAssembly'):
            fm_name_el = sub_el.find('SubAssemblyName')
            label_el = sub_el.find('Label')
            
            if fm_name_el is not None and fm_name_el.text:
                fm_name = fm_name_el.text.strip().lower()
                label = label_el.text.strip() if label_el is not None and label_el.text else ""
                
                if 'fm25' in fm_name or fm_name in ['roughopening', 'opening']:
                    fm_name_counts['FM25'] += 1
                    print(f"FM25 by name (SubAssembly): {label} - {fm_name}")
                elif 'fm32' in fm_name or 'ltype' in fm_name or 'critical' in fm_name:
                    fm_name_counts['FM32'] += 1
                    print(f"FM32 by name (SubAssembly): {label} - {fm_name}")

        print(f"\nEHX File: {os.path.basename(ehx_file_path)}")
        print(f"FM25 materials (by ID): {fm_counts['FM25']}")
        print(f"FM32 materials (by ID): {fm_counts['FM32']}")
        print(f"FM25 materials (by name): {fm_name_counts['FM25']}")
        print(f"FM32 materials (by name): {fm_name_counts['FM32']}")

        return fm_counts

    except Exception as e:
        print(f"Error processing {ehx_file_path}: {e}")
        return None

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python count_fm.py <ehx_file>")
        sys.exit(1)

    ehx_file = sys.argv[1]
    if not os.path.exists(ehx_file):
        print(f"File not found: {ehx_file}")
        sys.exit(1)

    count_fm_materials(ehx_file)