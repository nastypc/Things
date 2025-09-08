#!/usr/bin/env python3
"""
EHX Format Compatibility Test
Tests both legacy and v2.0 EHX file formats
"""

import os
import xml.etree.ElementTree as ET
from pathlib import Path

def test_ehx_format_compatibility():
    """Test parsing of both EHX file formats"""

    # Test files (update these paths to your actual files)
    test_files = [
        r"c:\Users\THOMPSON\Downloads\EHX\Working\07_112.EHX",  # Legacy format
        r"c:\Users\THOMPSON\Downloads\EHX\Working\Test\Test 2\MPO-L1-005008.EHX"  # v2.0 format
    ]

    for file_path in test_files:
        if os.path.exists(file_path):
            print(f"\n{'='*60}")
            print(f"Testing: {Path(file_path).name}")
            print(f"{'='*60}")

            try:
                tree = ET.parse(file_path)
                root = tree.getroot()

                # Detect format
                ehx_version = "legacy"
                job_info = {}

                if root.find('EHXVersion') is not None:
                    ehx_version = "v2.0"
                    job_info['EHXVersion'] = root.find('EHXVersion').text.strip() if root.find('EHXVersion') is not None else ""
                    job_info['InterfaceVersion'] = root.find('InterfaceVersion').text.strip() if root.find('InterfaceVersion') is not None else ""
                    job_info['PluginVersion'] = root.find('PluginVersion').text.strip() if root.find('PluginVersion') is not None else ""
                    job_info['Date'] = root.find('Date').text.strip() if root.find('Date') is not None else ""

                print(f"✅ Format Detected: {ehx_version}")

                if ehx_version == "v2.0":
                    print(f"   EHX Version: {job_info.get('EHXVersion', 'Unknown')}")
                    print(f"   Interface Version: {job_info.get('InterfaceVersion', 'Unknown')}")
                    print(f"   Plugin Version: {job_info.get('PluginVersion', 'Unknown')}")
                    print(f"   Export Date: {job_info.get('Date', 'Unknown')}")

                # Find Job element (works for both formats)
                job_el = root.find('.//Job')
                if job_el is None:
                    job_el = root  # Fallback for older format

                # Extract job metadata
                job_id = ""
                for tag in ['JobID']:
                    el = job_el.find(tag)
                    if el is not None and el.text:
                        job_id = el.text.strip()
                        break

                print(f"✅ Job ID: {job_id}")

                # Count panels
                panels = root.findall('.//Panel')
                print(f"✅ Panels Found: {len(panels)}")

                # Count materials
                boards = root.findall('.//Board')
                sheets = root.findall('.//Sheet')
                bracing = root.findall('.//Bracing')
                total_materials = len(boards) + len(sheets) + len(bracing)

                print(f"✅ Materials Found: {total_materials}")
                print(f"   - Boards: {len(boards)}")
                print(f"   - Sheets: {len(sheets)}")
                print(f"   - Bracing: {len(bracing)}")

                # Test JobPath extraction
                jobpath_el = root.find('.//JobPath')
                if jobpath_el is None:
                    job_el = root.find('.//Job')
                    if job_el is not None:
                        jobpath_el = job_el.find('JobPath')

                jobpath = jobpath_el.text.strip() if jobpath_el is not None and jobpath_el.text else "Not found"
                print(f"✅ Job Path: {jobpath}")

                print(f"🎉 SUCCESS: {ehx_version} format parsed successfully!")

            except Exception as e:
                print(f"❌ ERROR: Failed to parse {Path(file_path).name}")
                print(f"   Error: {e}")

        else:
            print(f"⚠️  File not found: {file_path}")

if __name__ == "__main__":
    print("EHX Format Compatibility Test")
    print("Testing both legacy and v2.0 EHX file formats...")
    test_ehx_format_compatibility()
