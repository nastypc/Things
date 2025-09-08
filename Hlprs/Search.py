#!/usr/bin/env python3
"""
EHX Search Widget - Tkinter widget for GUI integration
Can be embedded into existing Tkinter applications

⚠️  IMPORTANT: All search queries use GUID-based filtering for precision
- Level filtering prioritizes Level GUID over level names
- SubAssembly GUID is used for material association
- All searches are based on the GUID system as implemented in oldd.py
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Callable
from collections import defaultdict
import threading
import queue

class EHXSearchWidget(ttk.Frame):
    """Search widget that can be embedded into Tkinter GUIs"""

    def __init__(self, parent, ehx_file_path: str = None, **kwargs):
        """
        Initialize the search widget

        Args:
            parent: Parent Tkinter widget
            ehx_file_path: Path to EHX file (optional, can be set later)
            **kwargs: Additional Frame arguments
        """
        super().__init__(parent, **kwargs)

        self.ehx_file_path = ehx_file_path
        self.search_data = None
        self.search_queue = queue.Queue()
        self.search_thread = None

        self._setup_ui()
        self._setup_bindings()

        if ehx_file_path:
            self.load_ehx_file(ehx_file_path)

    def _setup_ui(self):
        """Setup the user interface"""
        # Main container
        self.configure(padding=5)

        # Search frame
        search_frame = ttk.Frame(self)
        search_frame.pack(fill=tk.X, pady=(0, 5))

        # Search label
        ttk.Label(search_frame, text="🔍 EHX Search:").pack(side=tk.LEFT, padx=(0, 5))

        # Search entry
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(
            search_frame,
            textvariable=self.search_var,
            font=("Segoe UI", 10)
        )
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        # Search button
        self.search_button = ttk.Button(
            search_frame,
            text="Search",
            command=self._perform_search
        )
        self.search_button.pack(side=tk.RIGHT)

        # Results frame
        results_frame = ttk.LabelFrame(self, text="Search Results", padding=5)
        results_frame.pack(fill=tk.BOTH, expand=True)

        # Results text area (terminal-like)
        self.results_text = scrolledtext.ScrolledText(
            results_frame,
            wrap=tk.WORD,
            font=("Consolas", 9),
            bg="#1e1e1e",
            fg="#d4d4d4",
            insertbackground="#d4d4d4"
        )
        self.results_text.pack(fill=tk.BOTH, expand=True)

        # Configure terminal-like colors
        self.results_text.tag_configure("command", foreground="#4ec9b0")  # Green for commands
        self.results_text.tag_configure("result", foreground="#9cdcfe")   # Blue for results
        self.results_text.tag_configure("error", foreground="#f44747")    # Red for errors
        self.results_text.tag_configure("info", foreground="#ce9178")     # Orange for info

        # Status bar
        self.status_var = tk.StringVar(value="Ready - Load an EHX file to begin searching")
        status_bar = ttk.Label(self, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(fill=tk.X, pady=(5, 0))

        # Quick search buttons frame
        quick_frame = ttk.Frame(self)
        quick_frame.pack(fill=tk.X, pady=(5, 0))

        ttk.Button(quick_frame, text="📋 Panels", command=lambda: self._quick_search("panels")).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(quick_frame, text="🏗️ Materials", command=lambda: self._quick_search("materials")).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(quick_frame, text="📦 Bundles", command=lambda: self._quick_search("bundles")).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(quick_frame, text="🧱 Sheathing", command=lambda: self._quick_search("sheathing")).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(quick_frame, text="📊 Counts", command=lambda: self._quick_search("counts")).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(quick_frame, text="🏠 Exterior Walls", command=lambda: self._quick_search("exterior")).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(quick_frame, text="📏 Linear Length", command=lambda: self._quick_search("linear")).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(quick_frame, text="📄 Sheathing Sheets", command=lambda: self._quick_search("sheets")).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(quick_frame, text="🏢 Levels", command=lambda: self._quick_search("levels")).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(quick_frame, text="🔍 GUID Search", command=lambda: self._quick_search("guid")).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(quick_frame, text="🔎 Search All", command=lambda: self._quick_search("search")).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(quick_frame, text="🔧 Debug", command=lambda: self._quick_search("debug")).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(quick_frame, text="🧹 Clear", command=self.clear_results).pack(side=tk.RIGHT)

    def _setup_bindings(self):
        """Setup keyboard and event bindings"""
        # Enter key to search
        self.search_entry.bind("<Return>", lambda e: self._perform_search())

        # Ctrl+L to clear
        self.bind("<Control-l>", lambda e: self.clear_results())
        self.search_entry.bind("<Control-l>", lambda e: self.clear_results())

        # Focus management
        self.search_entry.focus_set()

    def load_ehx_file(self, file_path: str) -> bool:
        """Load and index an EHX file for searching"""
        try:
            self.ehx_file_path = Path(file_path)
            if not self.ehx_file_path.exists():
                self._show_error(f"EHX file not found: {file_path}")
                return False

            self.status_var.set(f"Loading {self.ehx_file_path.name}...")

            # Load in background thread to avoid freezing GUI
            self.search_thread = threading.Thread(
                target=self._load_ehx_background,
                args=(file_path,),
                daemon=True
            )
            self.search_thread.start()

            return True

        except Exception as e:
            self._show_error(f"Error loading EHX file: {e}")
            return False

    def _load_ehx_background(self, file_path: str):
        """Load EHX file in background thread"""
        try:
            # Parse XML
            tree = ET.parse(file_path)
            root = tree.getroot()

            # Build search indexes
            search_data = self._build_search_indexes(root)

            # Update GUI in main thread
            self.after(0, lambda: self._on_ehx_loaded(search_data, file_path))

        except Exception as e:
            self.after(0, lambda: self._show_error(f"Error loading EHX file: {e}"))

    def _build_search_indexes(self, root) -> Dict:
        """Build search indexes from XML data"""
        search_data = {
            'panels': {},
            'materials': defaultdict(list),
            'bundles': {},
            'tree': root
        }

        # Index panels with enhanced data
        for panel in root.findall('.//Panel'):
            label = panel.find('Label')
            if label is not None and label.text:
                # Get level information
                level_guid = panel.find('LevelGuid')
                level_name = panel.find('LevelName')

                # Get panel dimensions for linear calculations
                length_elem = panel.find('ActualLength')
                width_elem = panel.find('ActualWidth')

                search_data['panels'][label.text] = {
                    'guid': panel.find('PanelGuid').text if panel.find('PanelGuid') is not None else '',
                    'bundle_guid': panel.find('BundleGuid').text if panel.find('BundleGuid') is not None else '',
                    'level_guid': level_guid.text if level_guid is not None else '',
                    'level_name': level_name.text if level_name is not None else '',
                    'length': float(length_elem.text) if length_elem is not None and length_elem.text else 0.0,
                    'width': float(width_elem.text) if width_elem is not None and width_elem.text else 0.0,
                    'family_name': panel.find('FamilyMemberName').text if panel.find('FamilyMemberName') is not None else '',
                    'element': panel  # Keep reference to original element
                }

        # Index materials
        for board in root.findall('.//Board'):
            self._index_material(board, 'Board', search_data)

        for sheet in root.findall('.//Sheet'):
            self._index_material(sheet, 'Sheet', search_data)

        for bracing in root.findall('.//Bracing'):
            self._index_material(bracing, 'Bracing', search_data)

        # Index bundles
        bundle_panels = defaultdict(list)
        for panel in root.findall('.//Panel'):
            bundle_guid = panel.find('BundleGuid')
            if bundle_guid is not None and bundle_guid.text:
                bundle_panels[bundle_guid.text].append(panel)

        for bundle_guid, panels in bundle_panels.items():
            bundle_name = panels[0].find('BundleName').text if panels[0].find('BundleName') is not None else f"Bundle {bundle_guid[:8]}"
            search_data['bundles'][bundle_guid] = {
                'name': bundle_name,
                'panel_count': len(panels),
                'panels': [p.find('Label').text for p in panels if p.find('Label') is not None]
            }

        return search_data

    def _index_material(self, element, element_type: str, search_data: Dict):
        """Index a material element"""
        family_name = element.find('FamilyMemberName')
        if family_name is not None:
            material_type = family_name.text
            search_data['materials'][material_type].append({
                'type': element_type,
                'element': element,
                'panel_guid': element.find('PanelGuid').text if element.find('PanelGuid') is not None else '',
                'guid': element.find(f'{element_type}Guid').text if element.find(f'{element_type}Guid') is not None else ''
            })

    def _on_ehx_loaded(self, search_data: Dict, file_path: str):
        """Called when EHX file is loaded"""
        self.search_data = search_data
        self.status_var.set(f"Ready - {len(search_data['panels'])} panels, {sum(len(items) for items in search_data['materials'].values())} materials")

        # Show welcome message
        self._append_result("command", f"EHX> Loaded {Path(file_path).name}")
        self._append_result("info", f"Found {len(search_data['panels'])} panels and {len(search_data['bundles'])} bundles")
        self._append_result("info", "⚠️  ALL SEARCHES USE GUID-BASED FILTERING:")
        self._append_result("info", "Commands: panels, materials, bundles, levels, guid <term>, search <term>, exterior [GUID], linear [GUID], sheets [GUID]")
        self._append_result("info", "Examples: 'search header', 'guid abc-123', 'levels'")
        self._append_result("", "")

    def _perform_search(self):
        """Perform search based on current query"""
        if not self.search_data:
            self._show_error("No EHX file loaded. Please load an EHX file first.")
            return

        query = self.search_var.get().strip()
        if not query:
            return

        # Show command in results
        self._append_result("command", f"EHX> {query}")

        # Process query
        result = self._process_query(query)

        # Show result
        if result:
            self._append_result("result", result)
        else:
            self._append_result("error", "No results found")

        self._append_result("", "")

        # Clear search box for next query
        self.search_var.set("")

    def _process_query(self, query: str) -> str:
        """Process a search query"""
        query = query.lower().strip()

        if not query:
            return ""

        # Panel search
        if query in self.search_data['panels']:
            return self._get_panel_details(query)

        # Material search
        for material_type in self.search_data['materials']:
            if query in material_type.lower():
                count = len(self.search_data['materials'][material_type])
                return f"Found {count} {material_type} pieces"

        # Partial panel search
        panel_matches = [p for p in self.search_data['panels'].keys() if query in p.lower()]
        if panel_matches:
            return f"Panels matching '{query}': {', '.join(panel_matches[:10])}"

        # Commands
        if query == "panels":
            return f"All panels: {', '.join(sorted(self.search_data['panels'].keys()))}"

        if query == "materials":
            material_counts = {mt: len(items) for mt, items in self.search_data['materials'].items()}
            return "\n".join(f"  {mt}: {count}" for mt, count in sorted(material_counts.items()))

        if query == "bundles":
            return "\n".join(f"  {info['name']}: {info['panel_count']} panels" for info in self.search_data['bundles'].values())

        if query.startswith("exterior"):
            level_part = query.replace("exterior", "").strip()
            return self._get_exterior_walls(level_part)

        if query.startswith("linear"):
            level_part = query.replace("linear", "").strip()
            return self._get_linear_length(level_part)

        if query.startswith("levels"):
            return self._get_level_info()

        if query.startswith("guid"):
            guid_part = query.replace("guid", "").strip()
            return self._search_by_guid(guid_part)

        if query.startswith("search"):
            search_part = query.replace("search", "").strip()
            return self._comprehensive_search(search_part)

        if query.startswith("debug"):
            debug_part = query.replace("debug", "").strip()
            return self._debug_analysis(debug_part)

        if query.startswith("sheets"):
            level_part = query.replace("sheets", "").strip()
            return self._get_sheathing_sheets(level_part)

        if query.startswith("sheathing"):
            panel_part = query.replace("sheathing", "").strip()
            if panel_part and panel_part in self.search_data['panels']:
                return self._get_panel_sheathing(panel_part)

        if query.startswith("count"):
            material_part = query.replace("count", "").strip()
            if material_part:
                for material_type in self.search_data['materials']:
                    if material_part in material_type.lower():
                        return f"Total {material_type}: {len(self.search_data['materials'][material_type])}"

        return f"No results found for '{query}'"

    def _get_panel_details(self, panel_label: str) -> str:
        """Get detailed information for a panel"""
        if panel_label not in self.search_data['panels']:
            return f"Panel {panel_label} not found"

        panel_info = self.search_data['panels'][panel_label]

        # Count materials for this panel
        material_counts = defaultdict(int)
        for material_type, items in self.search_data['materials'].items():
            for item in items:
                if item['panel_guid'] == panel_info['guid']:
                    material_counts[material_type] += 1

        result = f"Panel {panel_label}:\n"
        result += f"  GUID: {panel_info['guid'][:8]}...\n"
        result += f"  Bundle: {panel_info['bundle_guid'][:8]}...\n"
        result += "  Materials:\n"

        for material_type, count in sorted(material_counts.items()):
            result += f"    {material_type}: {count}\n"

        return result

    def _get_panel_sheathing(self, panel_label: str) -> str:
        """Get sheathing information for a panel"""
        if panel_label not in self.search_data['panels']:
            return f"Panel {panel_label} not found"

        panel_info = self.search_data['panels'][panel_label]

        # Find sheathing
        sheathing = []
        for item in self.search_data['materials'].get('Sheathing', []):
            if item['panel_guid'] == panel_info['guid']:
                element = item['element']
                material_elem = element.find('Material')
                if material_elem is not None:
                    desc = material_elem.find('Description')
                    label = element.find('Label')
                    if desc is not None and label is not None:
                        sheathing.append(f"  {label.text}: {desc.text}")

        if sheathing:
            return f"Sheathing for {panel_label} ({len(sheathing)} pieces):\n" + "\n".join(sheathing)
        else:
            return f"No sheathing found for {panel_label}"

    def _is_exterior_wall(self, panel_info: Dict) -> bool:
        """Determine if a panel is an exterior wall based on various indicators"""
        family_name = panel_info.get('family_name', '').lower()

        # Common exterior wall indicators
        exterior_indicators = [
            'exterior', 'ext', 'outside', 'outer',
            'wall', 'bearing wall', 'load bearing',
            'shear wall', 'curtain wall'
        ]

        # Check family name for exterior indicators
        for indicator in exterior_indicators:
            if indicator in family_name:
                return True

        # Check for sheathing (exterior walls typically have sheathing)
        if panel_info.get('element') is not None:
            sheathing = panel_info['element'].findall('.//Sheet')
            if sheathing:
                return True

        return False

    def _get_exterior_walls(self, level_filter: str = "") -> str:
        """Get all exterior walls, optionally filtered by level"""
        exterior_walls = []

        for panel_label, panel_info in self.search_data['panels'].items():
            if self._is_exterior_wall(panel_info):
                # Apply level filter if specified - GUID-BASED FILTERING (matches oldd.py system)
                if level_filter:
                    level_guid = panel_info.get('level_guid', '').lower()
                    level_name = panel_info.get('level_name', '').lower()
                    filter_lower = level_filter.lower()

                    # Exact GUID match takes priority
                    if level_guid and filter_lower == level_guid:
                        pass  # Exact GUID match - include
                    elif level_guid and filter_lower in level_guid:
                        pass  # Partial GUID match - include
                    elif level_name and filter_lower in level_name:
                        pass  # Level name match - include
                    else:
                        continue  # No match - skip this panel

                exterior_walls.append({
                    'label': panel_label,
                    'level': panel_info.get('level_name', 'Unknown'),
                    'length': panel_info.get('length', 0),
                    'width': panel_info.get('width', 0),
                    'linear_length': max(panel_info.get('length', 0), panel_info.get('width', 0))  # Use longer dimension
                })

        if not exterior_walls:
            return f"No exterior walls found{' for level: ' + level_filter if level_filter else ''}"

        # Group by level
        by_level = defaultdict(list)
        for wall in exterior_walls:
            by_level[wall['level']].append(wall)

        result = f"Exterior Walls{' for level: ' + level_filter if level_filter else ''}\n"
        total_linear = 0

        for level, walls in sorted(by_level.items()):
            level_linear = sum(w['linear_length'] for w in walls)
            total_linear += level_linear

            result += f"\n{level} ({len(walls)} walls, {level_linear:.1f} ft linear):\n"
            for wall in sorted(walls, key=lambda x: x['label']):
                result += f"  {wall['label']}: {wall['linear_length']:.1f} ft\n"

        result += f"\nTotal Linear Length: {total_linear:.1f} feet"
        return result

    def _get_linear_length(self, level_filter: str = "") -> str:
        """Get total linear length for walls, optionally filtered by level"""
        walls = []

        for panel_label, panel_info in self.search_data['panels'].items():
            # Apply level filter if specified - GUID-BASED FILTERING (matches oldd.py system)
            if level_filter:
                level_guid = panel_info.get('level_guid', '').lower()
                level_name = panel_info.get('level_name', '').lower()
                filter_lower = level_filter.lower()

                # Exact GUID match takes priority
                if level_guid and filter_lower == level_guid:
                    pass  # Exact GUID match - include
                elif level_guid and filter_lower in level_guid:
                    pass  # Partial GUID match - include
                elif level_name and filter_lower in level_name:
                    pass  # Level name match - include
                else:
                    continue  # No match - skip this panel

            walls.append({
                'label': panel_label,
                'level': panel_info.get('level_name', 'Unknown'),
                'length': panel_info.get('length', 0),
                'width': panel_info.get('width', 0),
                'linear_length': max(panel_info.get('length', 0), panel_info.get('width', 0)),
                'is_exterior': self._is_exterior_wall(panel_info)
            })

        if not walls:
            return f"No walls found{' for level: ' + level_filter if level_filter else ''}"

        # Group by level
        by_level = defaultdict(list)
        for wall in walls:
            by_level[wall['level']].append(wall)

        result = f"Wall Linear Length{' for level: ' + level_filter if level_filter else ''}\n"
        total_linear = 0
        total_exterior = 0

        for level, level_walls in sorted(by_level.items()):
            level_linear = sum(w['linear_length'] for w in level_walls)
            level_exterior = sum(w['linear_length'] for w in level_walls if w['is_exterior'])
            total_linear += level_linear
            total_exterior += level_exterior

            result += f"\n{level}:\n"
            result += f"  Total Linear: {level_linear:.1f} ft\n"
            result += f"  Exterior Linear: {level_exterior:.1f} ft\n"
            result += f"  Interior Linear: {level_linear - level_exterior:.1f} ft\n"

        result += f"\nOVERALL TOTALS:\n"
        result += f"  Total Linear Length: {total_linear:.1f} feet\n"
        result += f"  Exterior Linear Length: {total_exterior:.1f} feet\n"
        result += f"  Interior Linear Length: {total_linear - total_exterior:.1f} feet"

        return result

    def _get_sheathing_sheets(self, level_filter: str = "") -> str:
        """Get count of sheets for walls that have sheathing layers, by material type"""
        sheathing_walls = []

        for panel_label, panel_info in self.search_data['panels'].items():
            # Apply level filter if specified - prioritize Level GUID matching
            if level_filter:
                level_guid = panel_info.get('level_guid', '').lower()
                level_name = panel_info.get('level_name', '').lower()
                filter_lower = level_filter.lower()

                # Exact GUID match takes priority
                if level_guid and filter_lower == level_guid:
                    pass  # Exact GUID match - include
                elif level_guid and filter_lower in level_guid:
                    pass  # Partial GUID match - include
                elif level_name and filter_lower in level_name:
                    pass  # Level name match - include
                else:
                    continue  # No match - skip this panel

            # Check if this panel has sheathing
            element = panel_info.get('element')
            if element is not None:
                sheets = element.findall('.//Sheet')
                if sheets:
                    # Count sheets by material type
                    material_counts = defaultdict(int)
                    total_sheets = 0

                    for sheet in sheets:
                        # Get material type from FamilyMemberName or Description
                        family_name = sheet.find('FamilyMemberName')
                        if family_name is not None and family_name.text:
                            material_type = family_name.text.strip()
                        else:
                            # Fallback to Description
                            desc_elem = sheet.find('Material/Description') or sheet.find('Description')
                            material_type = desc_elem.text.strip() if desc_elem is not None and desc_elem.text else 'Unknown'

                        material_counts[material_type] += 1
                        total_sheets += 1

                    if total_sheets > 0:
                        sheathing_walls.append({
                            'label': panel_label,
                            'level': panel_info.get('level_name', 'Unknown'),
                            'total_sheets': total_sheets,
                            'material_breakdown': dict(material_counts),
                            'is_exterior': self._is_exterior_wall(panel_info)
                        })

        if not sheathing_walls:
            return f"No walls with sheathing found{' for level: ' + level_filter if level_filter else ''}"

        # Group by level
        by_level = defaultdict(list)
        for wall in sheathing_walls:
            by_level[wall['level']].append(wall)

        result = f"Sheathing Sheets Count{' for level: ' + level_filter if level_filter else ''}\n"

        # Overall material summary
        overall_materials = defaultdict(int)
        total_sheets_all = 0
        exterior_sheets = 0

        for wall in sheathing_walls:
            for material, count in wall['material_breakdown'].items():
                overall_materials[material] += count
            total_sheets_all += wall['total_sheets']
            if wall['is_exterior']:
                exterior_sheets += wall['total_sheets']

        result += f"\nOVERALL SUMMARY:\n"
        result += f"  Total Walls with Sheathing: {len(sheathing_walls)}\n"
        result += f"  Total Sheets: {total_sheets_all}\n"
        result += f"  Exterior Wall Sheets: {exterior_sheets}\n"
        result += f"  Interior Wall Sheets: {total_sheets_all - exterior_sheets}\n"
        result += f"  Material Breakdown:\n"

        for material, count in sorted(overall_materials.items()):
            result += f"    {material}: {count} sheets\n"

        # Detailed breakdown by level
        for level, walls in sorted(by_level.items()):
            level_sheets = sum(w['total_sheets'] for w in walls)
            level_exterior = sum(w['total_sheets'] for w in walls if w['is_exterior'])

            result += f"\n{level} ({len(walls)} walls, {level_sheets} sheets):\n"

            for wall in sorted(walls, key=lambda x: x['label']):
                ext_indicator = "🏠" if wall['is_exterior'] else "🏢"
                result += f"  {ext_indicator} {wall['label']}: {wall['total_sheets']} sheets\n"

                # Show material breakdown for this wall
                for material, count in sorted(wall['material_breakdown'].items()):
                    result += f"    • {material}: {count}\n"

        return result

    def _search_by_guid(self, guid_query: str) -> str:
        """Comprehensive search by any GUID type with hierarchical reporting"""
        if not guid_query:
            return "Usage: guid <search_term>\nSearches across all GUID types (Level, Bundle, Panel, SubAssembly, Material)"

        guid_query = guid_query.lower()
        results = []

        # Search across all GUID types
        for panel_label, panel_info in self.search_data['panels'].items():
            # Check all GUID fields
            level_guid = panel_info.get('level_guid', '').lower()
            bundle_guid = panel_info.get('bundle_guid', '').lower()
            panel_guid = panel_info.get('guid', '').lower()

            # Check if query matches any GUID
            guid_match = False
            matched_guid_type = ""
            matched_guid = ""

            if guid_query in level_guid:
                guid_match = True
                matched_guid_type = "Level"
                matched_guid = panel_info.get('level_guid', '')
            elif guid_query in bundle_guid:
                guid_match = True
                matched_guid_type = "Bundle"
                matched_guid = panel_info.get('bundle_guid', '')
            elif guid_query in panel_guid:
                guid_match = True
                matched_guid_type = "Panel"
                matched_guid = panel_info.get('guid', '')

            if guid_match:
                # Get associated materials for this panel
                materials = self._get_panel_materials_hierarchical(panel_info)

                results.append({
                    'type': matched_guid_type,
                    'guid': matched_guid,
                    'panel': panel_label,
                    'level': panel_info.get('level_name', 'Unknown'),
                    'materials': materials
                })

        # Also search materials for SubAssembly and Material GUIDs
        for material_type, items in self.search_data['materials'].items():
            for item in items:
                sub_assembly_guid = item.get('SubAssemblyGuid', '').lower()
                material_guid = item.get('guid', '').lower()

                if guid_query in sub_assembly_guid or guid_query in material_guid:
                    # Find the panel this material belongs to
                    panel_info = None
                    for p_label, p_info in self.search_data['panels'].items():
                        if item.get('panel_guid') == p_info.get('guid'):
                            panel_info = p_info
                            break

                    if panel_info:
                        guid_type = "SubAssembly" if guid_query in sub_assembly_guid else f"{item.get('type', 'Material')}"
                        matched_guid = sub_assembly_guid if guid_query in sub_assembly_guid else material_guid

                        results.append({
                            'type': guid_type,
                            'guid': matched_guid,
                            'panel': panel_info.get('guid', ''),
                            'level': panel_info.get('level_name', 'Unknown'),
                            'materials': [{
                                'type': material_type,
                                'label': item.get('Label', ''),
                                'family': item.get('FamilyMemberName', ''),
                                'sub_assembly_guid': sub_assembly_guid
                            }]
                        })

        if not results:
            return f"No GUID matches found for '{guid_query}'"

        # Format results with hierarchical display
        result = f"GUID Search Results for '{guid_query}'\n"
        result += "=" * 60 + "\n"

        for i, item in enumerate(results, 1):
            result += f"\n{i}. {item['type']} GUID: {item['guid']}\n"
            result += f"   Level: {item['level']}\n"
            result += f"   Panel: {item['panel']}\n"

            if item['materials']:
                result += "   Materials:\n"
                for mat in item['materials']:
                    if isinstance(mat, dict):
                        mat_type = mat.get('type', 'Unknown')
                        label = mat.get('label', '')
                        family = mat.get('family', '')
                        sub_guid = mat.get('sub_assembly_guid', '')
                        result += f"     • {mat_type}: {label} ({family})"
                        if sub_guid:
                            result += f" [SubAssembly: {sub_guid[:8]}...]"
                        result += "\n"
                    else:
                        result += f"     • {mat}\n"

        result += "\n" + "=" * 60
        result += f"\nFound {len(results)} GUID match(es)"
        return result

    def _comprehensive_search(self, search_term: str) -> str:
        """Comprehensive search across all fields with GUID-based reporting"""
        if not search_term:
            return "Usage: search <term>\nSearches across panel labels, material types, descriptions, and GUIDs"

        search_term = search_term.lower()
        results = []

        # Search panels
        for panel_label, panel_info in self.search_data['panels'].items():
            if (search_term in panel_label.lower() or
                search_term in panel_info.get('level_name', '').lower() or
                search_term in panel_info.get('family_name', '').lower() or
                search_term in panel_info.get('level_guid', '').lower() or
                search_term in panel_info.get('bundle_guid', '').lower() or
                search_term in panel_info.get('guid', '').lower()):

                materials = self._get_panel_materials_hierarchical(panel_info)
                results.append({
                    'type': 'Panel',
                    'match': panel_label,
                    'guid': panel_info.get('guid', ''),
                    'level': panel_info.get('level_name', 'Unknown'),
                    'materials': materials
                })

        # Search materials
        for material_type, items in self.search_data['materials'].items():
            for item in items:
                if (search_term in material_type.lower() or
                    search_term in item.get('Label', '').lower() or
                    search_term in item.get('FamilyMemberName', '').lower() or
                    search_term in item.get('Desc', '').lower() or
                    search_term in item.get('Type', '').lower() or
                    search_term in item.get('guid', '').lower() or
                    search_term in item.get('SubAssemblyGuid', '').lower()):

                    # Find associated panel
                    associated_panel = "Unknown"
                    level_name = "Unknown"
                    for p_label, p_info in self.search_data['panels'].items():
                        if item.get('panel_guid') == p_info.get('guid'):
                            associated_panel = p_label
                            level_name = p_info.get('level_name', 'Unknown')
                            break

                    results.append({
                        'type': 'Material',
                        'match': f"{material_type}: {item.get('Label', '')}",
                        'guid': item.get('guid', ''),
                        'level': level_name,
                        'panel': associated_panel,
                        'sub_assembly': item.get('SubAssemblyGuid', ''),
                        'details': {
                            'type': material_type,
                            'label': item.get('Label', ''),
                            'family': item.get('FamilyMemberName', ''),
                            'description': item.get('Desc', '')
                        }
                    })

        if not results:
            return f"No matches found for '{search_term}'"

        # Format results with hierarchical context
        result = f"Comprehensive Search Results for '{search_term}'\n"
        result += "=" * 60 + "\n"

        # Group by type
        panels = [r for r in results if r['type'] == 'Panel']
        materials = [r for r in results if r['type'] == 'Material']

        if panels:
            result += f"\nPANELS ({len(panels)} matches):\n"
            for i, panel in enumerate(panels, 1):
                result += f"{i}. {panel['match']}\n"
                result += f"   Level: {panel['level']}\n"
                result += f"   GUID: {panel['guid']}\n"
                if panel['materials']:
                    result += "   Materials:\n"
                    for mat in panel['materials']:
                        if isinstance(mat, dict) and 'headers' in mat:
                            # Rough opening with headers
                            result += f"     • Rough Opening: {mat['label']}\n"
                            if mat['headers']:
                                result += f"       Headers: {', '.join(mat['headers'])}\n"
                        elif isinstance(mat, dict):
                            result += f"     • {mat['type']}: {mat['label']} ({mat['family']})\n"
                result += "\n"

        if materials:
            result += f"\nMATERIALS ({len(materials)} matches):\n"
            for i, material in enumerate(materials, 1):
                result += f"{i}. {material['match']}\n"
                result += f"   Panel: {material['panel']}\n"
                result += f"   Level: {material['level']}\n"
                if material.get('sub_assembly'):
                    result += f"   SubAssembly: {material['sub_assembly'][:8]}...\n"
                if material.get('guid'):
                    result += f"   GUID: {material['guid']}\n"
                if material.get('details'):
                    details = material['details']
                    if details.get('description'):
                        result += f"   Description: {details['description']}\n"
                result += "\n"

        result += "=" * 60
        result += f"\nTotal: {len(results)} matches ({len(panels)} panels, {len(materials)} materials)"
        return result

    def _get_panel_materials_hierarchical(self, panel_info) -> list:
        """Get all materials for a panel with hierarchical context"""
        materials = []
        panel_guid = panel_info.get('guid', '')

        # Group materials by SubAssemblyGuid
        sub_assembly_groups = defaultdict(list)

        for material_type, items in self.search_data['materials'].items():
            for item in items:
                if item.get('panel_guid') == panel_guid:
                    sub_guid = item.get('SubAssemblyGuid', '')
                    if sub_guid:
                        sub_assembly_groups[sub_guid].append(item)
                    else:
                        # Materials without SubAssemblyGuid
                        materials.append({
                            'type': material_type,
                            'label': item.get('Label', ''),
                            'family': item.get('FamilyMemberName', ''),
                            'sub_assembly_guid': ''
                        })

        # Add grouped materials
        for sub_guid, items in sub_assembly_groups.items():
            # Check if this is a rough opening
            has_rough_opening = any(
                item.get('FamilyMemberName', '').lower() == 'roughopening'
                for item in items
            )

            if has_rough_opening:
                # Group rough opening with its headers
                rough_opening = None
                headers = []

                for item in items:
                    family = item.get('FamilyMemberName', '').lower()
                    if family == 'roughopening':
                        rough_opening = item
                    elif 'header' in family or item.get('Type', '').lower() == 'header':
                        headers.append(item)

                if rough_opening:
                    ro_label = rough_opening.get('Label', '')
                    header_labels = [h.get('Label', '') for h in headers]
                    materials.append({
                        'type': 'Rough Opening',
                        'label': ro_label,
                        'family': 'RoughOpening',
                        'headers': header_labels,
                        'sub_assembly_guid': sub_guid
                    })

        return materials

    def _get_level_info(self) -> str:
        """Get information about all levels and their GUIDs"""
        if not self.search_data:
            return "No EHX file loaded"

        # Collect level information
        levels_info = defaultdict(list)

        for panel_label, panel_info in self.search_data['panels'].items():
            level_guid = panel_info.get('level_guid', '')
            level_name = panel_info.get('level_name', 'Unknown')

            if level_guid:
                levels_info[level_guid].append({
                    'name': level_name,
                    'panel': panel_label,
                    'is_exterior': self._is_exterior_wall(panel_info)
                })

        if not levels_info:
            return "No level information found"

        result = "Level Information (GUID-based):\n"
        result += "=" * 50 + "\n"

        for level_guid in sorted(levels_info.keys()):
            panels = levels_info[level_guid]
            level_name = panels[0]['name'] if panels else 'Unknown'
            total_panels = len(panels)
            exterior_panels = sum(1 for p in panels if p['is_exterior'])

            result += f"\nLevel: {level_name}\n"
            result += f"GUID: {level_guid}\n"
            result += f"Total Panels: {total_panels}\n"
            result += f"Exterior Walls: {exterior_panels}\n"
            result += f"Interior Walls: {total_panels - exterior_panels}\n"

            # Show panel list (first 5)
            result += "Panels: "
            panel_names = [p['panel'] for p in panels[:5]]
            result += ", ".join(panel_names)
            if len(panels) > 5:
                result += f" ... (+{len(panels) - 5} more)"
            result += "\n"

        result += "\n" + "=" * 50 + "\n"
        result += "USAGE EXAMPLES (GUID-BASED):\n"
        result += "  exterior [GUID]  - Exterior walls for specific level\n"
        result += "  linear [GUID]    - Linear length for specific level\n"
        result += "  sheets [GUID]    - Sheathing sheets for specific level\n"
        result += "  ⚠️  All filtering uses Level GUID for precision\n"

        return result

    def _quick_search(self, search_type: str):
        """Perform quick search based on button pressed"""
        if not self.search_data:
            self._show_error("No EHX file loaded")
            return

        self._append_result("command", f"EHX> {search_type}")

        if search_type == "panels":
            result = f"All panels ({len(self.search_data['panels'])}): {', '.join(sorted(self.search_data['panels'].keys()))}"
        elif search_type == "materials":
            material_counts = {mt: len(items) for mt, items in self.search_data['materials'].items()}
            result = "Material counts:\n" + "\n".join(f"  {mt}: {count}" for mt, count in sorted(material_counts.items()))
        elif search_type == "bundles":
            result = f"Bundles ({len(self.search_data['bundles'])}):\n" + "\n".join(f"  {info['name']}: {info['panel_count']} panels" for info in self.search_data['bundles'].values())
        elif search_type == "sheathing":
            total_sheathing = len(self.search_data['materials'].get('Sheathing', []))
            result = f"Total sheathing pieces: {total_sheathing}"
        elif search_type == "counts":
            total_panels = len(self.search_data['panels'])
            total_materials = sum(len(items) for items in self.search_data['materials'].values())
            result = f"Summary:\n  Panels: {total_panels}\n  Materials: {total_materials}\n  Bundles: {len(self.search_data['bundles'])}"
        elif search_type == "exterior":
            result = self._get_exterior_walls()
        elif search_type == "linear":
            result = self._get_linear_length()
        elif search_type == "sheets":
            result = self._get_sheathing_sheets()
        elif search_type == "levels":
            result = self._get_level_info()
        elif search_type == "guid":
            result = "GUID Search: Enter 'guid <search_term>' to search across all GUID types\nExamples: 'guid abc-123', 'guid level', 'guid panel'"
        elif search_type == "search":
            result = "Comprehensive Search: Enter 'search <term>' to search across all fields\nExamples: 'search header', 'search osb', 'search level 1'"

        self._append_result("result", result)
        self._append_result("", "")

    def _append_result(self, tag: str, text: str):
        """Append text to results with optional tag"""
        if tag:
            self.results_text.insert(tk.END, text + "\n", tag)
        else:
            self.results_text.insert(tk.END, text + "\n")

        # Auto-scroll to bottom
        self.results_text.see(tk.END)

    def clear_results(self):
        """Clear the results text area"""
        self.results_text.delete(1.0, tk.END)
        self._append_result("info", "Results cleared. Ready for new search.")

    def _show_error(self, message: str):
        """Show error message"""
        self.status_var.set(f"Error: {message}")
        messagebox.showerror("EHX Search Error", message)

    def get_search_data(self) -> Optional[Dict]:
        """Get the current search data (for external access)"""
        return self.search_data

    def set_ehx_file(self, file_path: str):
        """Set a new EHX file to search"""
        self.load_ehx_file(file_path)


# Example usage function
def create_search_demo():
    """Create a demo window showing the search widget"""
    root = tk.Tk()
    root.title("EHX Search Widget Demo")
    root.geometry("800x600")

    # Create search widget
    search_widget = EHXSearchWidget(root)
    search_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Menu bar
    menubar = tk.Menu(root)
    file_menu = tk.Menu(menubar, tearoff=0)
    file_menu.add_command(label="Load EHX File", command=lambda: load_file_demo(search_widget))
    file_menu.add_separator()
    file_menu.add_command(label="Exit", command=root.quit)
    menubar.add_cascade(label="File", menu=file_menu)
    root.config(menu=menubar)

    return root

def load_file_demo(search_widget):
    """Demo function to load an EHX file"""
    from tkinter import filedialog
    file_path = filedialog.askopenfilename(
        title="Select EHX file",
        filetypes=[("EHX files", "*.EHX"), ("All files", "*.*")]
    )
    if file_path:
        search_widget.load_ehx_file(file_path)


if __name__ == "__main__":
    # Demo
    root = create_search_demo()
    root.mainloop()
