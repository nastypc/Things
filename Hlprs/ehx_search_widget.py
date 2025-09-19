#!/usr/bin/env python3
"""
EHX Search Widget - Tkinter widget for GUI integration
Can be embedded into existing Tkinter applications
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Callable
from collections import defaultdict
import threading
import queue
import math
import importlib.util

# Import formatting functions from Vold.py
try:
    import sys
    vold_path = Path(__file__).parent.parent / "Script" / "Vold.py"
    if vold_path.exists():
        spec = importlib.util.spec_from_file_location("Vold", vold_path)
        vold_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(vold_module)
        format_dimension = vold_module.format_dimension
        format_weight = vold_module.format_weight
        inches_to_feet_inches_sixteenths = vold_module.inches_to_feet_inches_sixteenths
    else:
        raise ImportError("Vold.py not found")
except ImportError:
    # Fallback definitions if Vold.py is not available
    def format_dimension(value):
        """Strip trailing zeros from decimal numbers."""
        try:
            num = float(str(value))
            if num == int(num):
                return str(int(num))
            else:
                return str(num).rstrip('0').rstrip('.')
        except (ValueError, TypeError):
            return str(value)

    def format_weight(value):
        """Format weight by rounding up to nearest integer."""
        if not value:
            return value
        try:
            num = float(str(value))
            return str(math.ceil(num))
        except (ValueError, TypeError):
            return str(value)

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
        return ''

# Global sorting functions for consistent ordering throughout the application
def sort_bundle_keys(bundle_keys):
    """Sort bundle keys by bundle number (B1, B2, etc.) with smart fallback."""
    def smart_sort_key(bundle_name):
        import re
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

def sort_panel_names(panel_names):
    """Sort panel names numerically (05-100, 05-101, etc.) and simple numeric formats (100, 101, etc.)."""
    def panel_sort_key(panel_name):
        import re
        # First try to match "XX-YYY" format (like "05-100")
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

def sort_panels_by_bundle_and_name(panels_dict):
    """Sort panels by bundle, then by panel name for consistent ordering."""
    def panel_sort_key(item):
        pname, pobj = item
        bundle_name = pobj.get('BundleName') or pobj.get('Bundle') or ''
        display_name = pobj.get('DisplayLabel', pname)
        return (bundle_name, display_name)
    
    return sorted(panels_dict.items(), key=panel_sort_key)

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
        ttk.Button(quick_frame, text="📊 Summary", command=lambda: self._quick_search("summary")).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(quick_frame, text="🪚 Precuts", command=lambda: self._quick_search("precuts")).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(quick_frame, text="📋 Takeoff", command=lambda: self._quick_search("takeoff")).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(quick_frame, text="❓ Help", command=lambda: self._quick_search("help")).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(quick_frame, text="💾 Export", command=self._export_results).pack(side=tk.LEFT, padx=(0, 2))
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
        # Detect EHX format version
        ehx_version = "legacy"
        if root.find('EHXVersion') is not None:
            ehx_version = "v2.0"
            ehx_ver = root.find('EHXVersion').text.strip() if root.find('EHXVersion') is not None else ""
            print(f"DEBUG: Search widget detected EHX format: {ehx_version} (Version: {ehx_ver})")
        else:
            print(f"DEBUG: Search widget detected EHX format: {ehx_version}")

        search_data = {
            'panels': {},
            'materials': defaultdict(list),
            'bundles': {},
            'tree': root,
            'ehx_version': ehx_version
        }

        # Index panels
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

        # Index materials
        for board in root.findall('.//Board'):
            self._index_material(board, 'Board', search_data)

        for sheet in root.findall('.//Sheet'):
            self._index_material(sheet, 'Sheet', search_data)

        for bracing in root.findall('.//Bracing'):
            self._index_material(bracing, 'Bracing', search_data)

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

        # Index bundles
        bundle_panels = defaultdict(list)
        for panel in root.findall('.//Panel'):
            bundle_guid = panel.find('BundleGuid')
            bundle_key = None
            
            if bundle_guid is not None and bundle_guid.text:
                # v2.0 format with BundleGuid
                bundle_key = bundle_guid.text
            else:
                # Legacy format fallback - use BundleName or Bundle
                bundle_name_el = panel.find('BundleName') or panel.find('Bundle')
                if bundle_name_el is not None and bundle_name_el.text:
                    bundle_key = bundle_name_el.text.strip()
            
            if bundle_key:
                bundle_panels[bundle_key].append(panel)

        for bundle_key, panels in bundle_panels.items():
            # Try to get BundleName from the first panel
            bundle_name = None
            first_panel = panels[0]
            
            # First try direct BundleName under Panel (legacy format)
            bundle_name_el = first_panel.find('BundleName')
            if bundle_name_el is not None and bundle_name_el.text:
                bundle_name = bundle_name_el.text.strip()
            
            # For v2.0 format, try to get BundleName from Junction mapping
            if ehx_version == "v2.0" and not bundle_name:
                # Try to match by PanelID/Label using the junction mapping
                panel_id_el = first_panel.find('PanelID')
                label_el = first_panel.find('Label')
                
                if panel_id_el is not None and panel_id_el.text and panel_id_el.text.strip() in junction_bundle_map:
                    bundle_name = junction_bundle_map[panel_id_el.text.strip()]
                elif label_el is not None and label_el.text and label_el.text.strip() in junction_bundle_map:
                    bundle_name = junction_bundle_map[label_el.text.strip()]
                
                # Fallback: try to derive BundleName from BundleLayer
                if not bundle_name:
                    bundle_layer_el = first_panel.find('BundleLayer')
                    if bundle_layer_el is not None and bundle_layer_el.text:
                        try:
                            bundle_layer = int(bundle_layer_el.text.strip())
                            if bundle_layer in bundle_layer_map:
                                bundle_name = bundle_layer_map[bundle_layer]
                        except ValueError:
                            pass
            
            # For legacy format, if we used BundleName as key, use it as the display name
            if not bundle_name:
                if bundle_key and not bundle_key.startswith('{'):  # Not a GUID
                    bundle_name = bundle_key
                else:
                    # Fallback to truncated GUID
                    bundle_name = f"Bundle {bundle_key[:8]}" if bundle_key else "Unknown Bundle"
                
            search_data['bundles'][bundle_key] = {
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
        ehx_version = search_data.get('ehx_version', 'legacy')
        version_info = f" (EHX {ehx_version})" if ehx_version != 'legacy' else ""
        self.status_var.set(f"Ready{version_info} - {len(search_data['panels'])} panels, {sum(len(items) for items in search_data['materials'].values())} materials")

        # Check for unassigned panels
        panels_dict = search_data.get('panels', {})
        unassigned_panels = detect_unassigned_panels(panels_dict)
        
        # Show welcome message
        self._append_result("command", f"EHX> Loaded {Path(file_path).name}")
        self._append_result("info", f"Found {len(search_data['panels'])} panels and {len(search_data['bundles'])} bundles")
        self._append_result("info", f"EHX Format: {ehx_version}{version_info}")
        
        # Show diagnostic info for v2.0 files
        if ehx_version == "v2.0" and unassigned_panels:
            try:
                tree = ET.parse(file_path)
                root = tree.getroot()
                diag_report = diagnose_v2_bundle_assignment(root, ehx_version, panels_dict)
                if diag_report:
                    self._append_result("warning", f"V2.0 Diagnostic: {diag_report['junctions_found']} junctions, {diag_report['bundles_found']} bundles")
                    self._append_result("warning", f"Bundle assignments: {diag_report['panels_assigned']} assigned, {diag_report['panels_unassigned']} unassigned")
            except Exception as e:
                self._append_result("error", f"Diagnostic error: {e}")
        
        # Show unassigned panels warning if any found
        if unassigned_panels:
            self._append_result("warning", f"⚠️  WARNING: {len(unassigned_panels)} panel(s) not assigned to any bundle!")
            for panel in unassigned_panels[:5]:  # Show first 5 in the widget
                self._append_result("warning", f"   • {panel['display_name']} (Level: {panel['level']})")
            if len(unassigned_panels) > 5:
                self._append_result("warning", f"   ... and {len(unassigned_panels) - 5} more (see logs for details)")
        
        self._append_result("info", "Type your search query or use quick buttons above")
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
        """Process a search query with intelligent construction helpers"""
        query = query.lower().strip()

        if not query:
            return ""

        # Intelligent Construction Helpers
        if query == "sheathing":
            return self._get_construction_summary("sheathing")
        
        if query in ["sheets", "sheet"]:
            return self._get_construction_summary("sheets")
        
        if query in ["boards", "board"]:
            return self._get_construction_summary("boards")
        
        if query in ["bracing", "brace"]:
            return self._get_construction_summary("bracing")
        
        if query in ["help", "commands", "?", "h"]:
            return self._get_help_reference()
        
        if query in ["summary", "overview", "stats"]:
            total_panels = len(self.search_data['panels'])
            total_materials = sum(len(items) for items in self.search_data['materials'].values())
            return f"📊 Project Summary:\n  Panels: {total_panels}\n  Materials: {total_materials}\n  Bundles: {len(self.search_data['bundles'])}\n\n💡 Try typing: 'sheathing', 'level 1', 'precut', 'liner' for detailed analysis"
        
        if query in ["clear", "cls", "reset"]:
            self.clear_results()
            return ""
        
        if query.startswith("export"):
            return self._handle_export_command(query)
        
        if "level" in query:
            return self._get_level_breakdown(query)
        
        if query in ["takeoff", "take off", "material takeoff"]:
            return self._get_takeoff_options()
        
        if query.startswith("takeoff level") or query.startswith("take off level"):
            level_part = query.replace("takeoff level", "").replace("take off level", "").strip()
            return self._get_level_takeoff(level_part)
        
        if query.startswith("takeoff panel") or query.startswith("take off panel"):
            panel_part = query.replace("takeoff panel", "").replace("take off panel", "").strip()
            return self._get_panel_takeoff(panel_part)
        
        if query.startswith("takeoff all") or query.startswith("take off all"):
            return self._get_complete_takeoff()
        
        if "panel" in query and len(query.split()) > 1:
            panel_name = query.replace("panel", "").strip()
            if panel_name in self.search_data['panels']:
                return self._get_panel_construction_details(panel_name)
        
        if query in ["precut", "precuts", "2x4", "2x6"]:
            return self._get_precut_analysis()
        
        if "liner" in query or "length" in query:
            return self._get_liner_analysis()

        # Original functionality preserved
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

        if query == "bundles":
            return "\n".join(f"  {info['name']}: {info['panel_count']} panels" for info in self.search_data['bundles'].values())

        if query == "materials":
            return self._get_full_material_breakdown()

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

        return f"No results found for '{query}'. Try: sheathing, sheets, materials, level, precut, liner"

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

    def _quick_search(self, search_type: str):
        """Perform quick search based on button pressed"""
        if not self.search_data:
            self._show_error("No EHX file loaded")
            return

        self._append_result("command", f"EHX> {search_type}")

        if search_type == "panels":
            result = f"All panels ({len(self.search_data['panels'])}): {', '.join(sorted(self.search_data['panels'].keys()))}"
        elif search_type == "materials":
            result = self._get_full_material_breakdown()
        elif search_type == "bundles":
            result = f"Bundles ({len(self.search_data['bundles'])}):\n" + "\n".join(f"  {info['name']}: {info['panel_count']} panels" for info in self.search_data['bundles'].values())
        elif search_type == "sheathing":
            result = self._get_construction_summary("sheathing")
        elif search_type == "summary":
            total_panels = len(self.search_data['panels'])
            total_materials = sum(len(items) for items in self.search_data['materials'].values())
            result = f"📊 Project Summary:\n  Panels: {total_panels}\n  Materials: {total_materials}\n  Bundles: {len(self.search_data['bundles'])}\n\n💡 Try typing: 'sheathing', 'level 1', 'precut', 'liner' for detailed analysis"
        elif search_type == "precuts":
            result = self._get_precut_analysis()
        elif search_type == "takeoff":
            result = self._get_takeoff_options()
        elif search_type == "help":
            result = self._get_help_reference()

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

    def _get_construction_summary(self, material_type: str) -> str:
        """Get intelligent construction summary for a material type, sorted by material"""
        if not self.search_data:
            return "No data loaded"

        material_key = material_type.title()
        if material_key not in self.search_data['materials']:
            return f"No {material_type} found in this project"

        items = self.search_data['materials'][material_key]
        total_count = len(items)

        # Get unique material descriptions and group by material type
        material_groups = defaultdict(list)
        for item in items:
            element = item['element']
            material_elem = element.find('Material')
            if material_elem is not None:
                desc = material_elem.find('Description')
                if desc is not None and desc.text:
                    # Parse the material subtype from description
                    parsed_info = self._parse_material_description(desc.text, material_key)
                    material_groups[parsed_info['subtype']].append(desc.text)

        result = f"🏗️ {material_key} Summary:\n"
        result += f"  Total Pieces: {total_count}\n"
        result += f"  Material Subtypes: {len(material_groups)}\n\n"
        
        # Display by material subtype
        for subtype in sorted(material_groups.keys()):
            subtype_count = len(material_groups[subtype])
            subtype_percentage = (subtype_count / total_count * 100) if total_count > 0 else 0
            result += f"📋 {subtype} ({subtype_count} pieces, {subtype_percentage:.1f}%):\n"
            
            # Show unique descriptions within this subtype
            unique_descriptions = set(material_groups[subtype])
            for desc in sorted(unique_descriptions):
                count = material_groups[subtype].count(desc)
                result += f"  • {desc}: {count} pieces\n"
            result += "\n"

        # Add helpful suggestions
        result += "💡 Try also: 'materials' for full breakdown, 'level 1' for per-level analysis"
        return result

    def _parse_material_description(self, description: str, material_type: str) -> dict:
        """Parse material description to extract subtype"""
        desc_lower = description.lower()
        
        subtype = "Unknown"
        
        if material_type == "Sheathing":
            if "osb" in desc_lower:
                subtype = "OSB"
            elif "plywood" in desc_lower or "ply" in desc_lower:
                subtype = "Plywood"
            elif "waferboard" in desc_lower:
                subtype = "Waferboard"
            elif "gypsum" in desc_lower:
                subtype = "Gypsum"
            elif "cement" in desc_lower:
                subtype = "Cement Board"
        elif material_type == "Sheet":
            if "osb" in desc_lower:
                subtype = "OSB"
            elif "plywood" in desc_lower or "ply" in desc_lower:
                subtype = "Plywood"
            elif "particle" in desc_lower:
                subtype = "Particle Board"
            elif "wafer" in desc_lower:
                subtype = "Waferboard"
        elif material_type == "Board":
            if "spf" in desc_lower:
                subtype = "SPF"
            elif "stud" in desc_lower:
                subtype = "Stud"
            elif "douglas" in desc_lower or "df" in desc_lower:
                subtype = "Douglas Fir"
            elif "hemlock" in desc_lower:
                subtype = "Hemlock"
            elif "cedar" in desc_lower:
                subtype = "Cedar"
            elif "pine" in desc_lower:
                subtype = "Pine"
        
        return {
            'subtype': subtype,
            'original_description': description
        }

    def _get_full_material_breakdown(self) -> str:
        """Get comprehensive material breakdown with construction insights"""
        if not self.search_data:
            return "No data loaded"

        result = "📊 Complete Material Breakdown:\n\n"

        # Overall totals
        total_materials = sum(len(items) for items in self.search_data['materials'].values())
        result += f"🎯 Project Totals:\n"
        result += f"  Panels: {len(self.search_data['panels'])}\n"
        result += f"  Total Materials: {total_materials}\n"
        result += f"  Bundles: {len(self.search_data['bundles'])}\n\n"

        # Material breakdown
        result += "🔨 Material Details:\n"
        for material_type, items in sorted(self.search_data['materials'].items()):
            count = len(items)
            percentage = (count / total_materials * 100) if total_materials > 0 else 0
            result += f"  {material_type}: {count} pieces ({percentage:.1f}%)\n"

        # Construction insights
        result += "\n🏗️ Construction Insights:\n"
        
        # Check for common construction patterns
        if 'Sheathing' in self.search_data['materials']:
            sheathing_count = len(self.search_data['materials']['Sheathing'])
            result += f"  • Exterior sheathing coverage: {sheathing_count} pieces\n"
        
        if 'Sheet' in self.search_data['materials']:
            sheet_count = len(self.search_data['materials']['Sheet'])
            result += f"  • Structural sheets: {sheet_count} pieces\n"

        # Bundle efficiency
        avg_panels_per_bundle = len(self.search_data['panels']) / len(self.search_data['bundles']) if self.search_data['bundles'] else 0
        result += f"  • Average panels per bundle: {avg_panels_per_bundle:.1f}\n"

        return result

    def _get_level_breakdown(self, query: str) -> str:
        """Get per-level material breakdown"""
        if not self.search_data:
            return "No data loaded"

        # Extract level number from query (e.g., "level 1", "level 2")
        level_part = query.replace("level", "").strip()
        if not level_part:
            return "Please specify a level number (e.g., 'level 1')"

        try:
            target_level = int(level_part)
        except ValueError:
            return f"Invalid level number: {level_part}"

        result = f"📐 Level {target_level} Analysis:\n\n"

        # Find panels in this level
        level_panels = []
        for panel_name, panel_info in self.search_data['panels'].items():
            # Try to extract level from panel name or info
            level_found = False
            if f"L{target_level}" in panel_name or f"Level{target_level}" in panel_name:
                level_panels.append((panel_name, panel_info))
                level_found = True

        if not level_panels:
            result += f"No panels found for Level {target_level}\n"
            result += "Available panels: " + ", ".join(list(self.search_data['panels'].keys())[:5]) + "..."
            return result

        result += f"Found {len(level_panels)} panels in Level {target_level}:\n"
        
        # Count materials for this level
        level_materials = defaultdict(int)
        for panel_name, panel_info in level_panels:
            for material_type, items in self.search_data['materials'].items():
                for item in items:
                    if item['panel_guid'] == panel_info['guid']:
                        level_materials[material_type] += 1

        result += "\nMaterials for Level {target_level}:\n"
        for material_type, count in sorted(level_materials.items()):
            result += f"  {material_type}: {count} pieces\n"

        return result

    def _get_panel_construction_details(self, panel_name: str) -> str:
        """Get detailed construction information for a specific panel"""
        if panel_name not in self.search_data['panels']:
            return f"Panel '{panel_name}' not found"

        panel_info = self.search_data['panels'][panel_name]
        
        result = f"🔍 Panel: {panel_name}\n"
        result += f"  GUID: {panel_info['guid'][:8]}...\n"
        result += f"  Bundle: {panel_info['bundle_guid'][:8]}...\n\n"

        # Get all materials for this panel
        panel_materials = defaultdict(list)
        for material_type, items in self.search_data['materials'].items():
            for item in items:
                if item['panel_guid'] == panel_info['guid']:
                    element = item['element']
                    material_elem = element.find('Material')
                    if material_elem is not None:
                        desc = material_elem.find('Description')
                        if desc is not None and desc.text:
                            panel_materials[material_type].append(desc.text)

        result += "Construction Materials:\n"
        for material_type, descriptions in sorted(panel_materials.items()):
            result += f"  {material_type} ({len(descriptions)} pieces):\n"
            for desc in sorted(set(descriptions)):  # Remove duplicates
                count = descriptions.count(desc)
                result += f"    • {desc}: {count}\n"

        return result

    def _get_precut_analysis(self) -> str:
        """Analyze precut lumber (2x4, 2x6) with standard lengths, sorted by material type"""
        if not self.search_data:
            return "No data loaded"

        result = "🪚 Precut Lumber Analysis:\n\n"

        # Standard precut lengths
        standard_lengths = ["7'-8 5/8\"", "8'-8 5/8\"", "9'-8 5/8\"", "7 ft 8-5/8 in", "8 ft 8-5/8 in", "9 ft 8-5/8 in"]
        
        # Look for boards that might be precuts
        precut_candidates = []
        if 'Board' in self.search_data['materials']:
            for item in self.search_data['materials']['Board']:
                element = item['element']
                material_elem = element.find('Material')
                if material_elem is not None:
                    desc = material_elem.find('Description')
                    length_elem = material_elem.find('ActualLength')
                    
                    if desc is not None and desc.text and length_elem is not None and length_elem.text:
                        desc_text = desc.text.lower()
                        length_text = length_elem.text
                        
                        # Check if it's 2x4 or 2x6
                        if ('2x4' in desc_text or '2x6' in desc_text) and any(std_len in length_text for std_len in standard_lengths):
                            # Parse material type, dimensions, and length
                            parsed_info = self._parse_precut_description(desc.text, length_text)
                            if parsed_info:
                                precut_candidates.append({
                                    'material_type': parsed_info['material_type'],
                                    'dimensions': parsed_info['dimensions'],
                                    'length': parsed_info['length'],
                                    'full_description': desc.text,
                                    'panel_guid': item['panel_guid']
                                })

        if precut_candidates:
            result += f"Found {len(precut_candidates)} potential precut pieces:\n\n"
            
            # Group by material type, then dimensions, then length
            precut_groups = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
            for precut in precut_candidates:
                precut_groups[precut['material_type']][precut['dimensions']][precut['length']] += 1
            
            # Sort and display by material type
            for material_type in sorted(precut_groups.keys()):
                result += f"📋 {material_type}:\n"
                material_total = 0
                
                for dimensions in sorted(precut_groups[material_type].keys()):
                    result += f"  {dimensions}:\n"
                    
                    for length in sorted(precut_groups[material_type][dimensions].keys()):
                        count = precut_groups[material_type][dimensions][length]
                        result += f"    • {length}: {count} pieces\n"
                        material_total += count
                
                result += f"  Total {material_type}: {material_total} pieces\n\n"
            
            # Overall summary
            total_precuts = len(precut_candidates)
            unique_materials = len(precut_groups)
            result += f"📊 Summary: {total_precuts} precuts across {unique_materials} material types\n"
            
        else:
            result += "No standard precut lengths found.\n"
            result += "Standard lengths checked: 7'-8 5/8\", 8'-8 5/8\", 9'-8 5/8\"\n"
            result += "Material types checked: 2x4, 2x6"

        return result

    def _parse_precut_description(self, description: str, length: str) -> dict:
        """Parse precut description to extract material type, dimensions, and length"""
        desc_lower = description.lower()
        
        # Extract material type
        material_type = "Unknown"
        if "spf" in desc_lower:
            material_type = "SPF"
        elif "stud" in desc_lower:
            material_type = "Stud"
        elif "douglas" in desc_lower or "df" in desc_lower:
            material_type = "Douglas Fir"
        elif "hemlock" in desc_lower:
            material_type = "Hemlock"
        elif "cedar" in desc_lower:
            material_type = "Cedar"
        elif "pine" in desc_lower:
            material_type = "Pine"
        elif "fir" in desc_lower:
            material_type = "Fir"
        elif "spruce" in desc_lower:
            material_type = "Spruce"
        
        # Extract dimensions (2x4, 2x6, etc.)
        dimensions = "Unknown"
        if "2x4" in desc_lower:
            dimensions = "2x4"
        elif "2x6" in desc_lower:
            dimensions = "2x6"
        elif "2x8" in desc_lower:
            dimensions = "2x8"
        elif "2x10" in desc_lower:
            dimensions = "2x10"
        elif "2x12" in desc_lower:
            dimensions = "2x12"
        
        # Clean up length
        clean_length = length.strip()
        
        return {
            'material_type': material_type,
            'dimensions': dimensions,
            'length': clean_length,
            'original_description': description
        }

    def _get_liner_analysis(self) -> str:
        """Analyze liner materials and calculate total lengths, sorted by material type"""
        if not self.search_data:
            return "No data loaded"

        result = "📏 Liner Analysis:\n\n"

        # Look for liner-related materials
        liner_candidates = []
        total_length = 0
        
        for material_type, items in self.search_data['materials'].items():
            for item in items:
                element = item['element']
                material_elem = element.find('Material')
                if material_elem is not None:
                    desc = material_elem.find('Description')
                    length_elem = material_elem.find('ActualLength')
                    
                    if desc is not None and desc.text:
                        desc_text = desc.text.lower()
                        if 'liner' in desc_text or 'plywood' in desc_text or 'osb' in desc_text or 'sheathing' in desc_text or 'board' in desc_text:
                            length = 0
                            if length_elem is not None and length_elem.text:
                                try:
                                    # Try to extract numeric length
                                    length_text = length_elem.text.replace("'", "").replace("\"", "").replace("ft", "").replace("in", "").strip()
                                    if length_text:
                                        length = float(length_text.split()[0]) if length_text.split() else 0
                                except (ValueError, IndexError):
                                    pass
                            
                            # Parse material type from description
                            parsed_info = self._parse_liner_description(desc.text, length_elem.text if length_elem is not None else "")
                            liner_candidates.append({
                                'material_type': parsed_info['material_type'],
                                'description': desc.text,
                                'length': length,
                                'panel_guid': item['panel_guid']
                            })
                            total_length += length

        if liner_candidates:
            result += f"Found {len(liner_candidates)} liner pieces:\n"
            result += f"Total calculated length: {total_length:.1f} linear feet\n\n"
            
            # Group by material type, then by description
            liner_groups = defaultdict(lambda: defaultdict(lambda: {'count': 0, 'total_length': 0}))
            for liner in liner_candidates:
                liner_groups[liner['material_type']][liner['description']]['count'] += 1
                liner_groups[liner['material_type']][liner['description']]['total_length'] += liner['length']
            
            # Display by material type
            for material_type in sorted(liner_groups.keys()):
                result += f"📋 {material_type}:\n"
                material_total_count = 0
                material_total_length = 0
                
                for liner_desc, data in sorted(liner_groups[material_type].items()):
                    count = data['count']
                    length = data['total_length']
                    result += f"  • {liner_desc}: {count} pieces, {length:.1f} ft total\n"
                    material_total_count += count
                    material_total_length += length
                
                result += f"  Total {material_type}: {material_total_count} pieces, {material_total_length:.1f} ft\n\n"
            
            # Overall summary
            unique_materials = len(liner_groups)
            result += f"📊 Summary: {len(liner_candidates)} liner pieces across {unique_materials} material types\n"
            
        else:
            result += "No liner materials found.\n"
            result += "Searched for: liner, plywood, osb materials"

        return result

    def _parse_liner_description(self, description: str, length: str) -> dict:
        """Parse liner description to extract material type"""
        desc_lower = description.lower()
        
        # Extract material type
        material_type = "Unknown"
        if "osb" in desc_lower:
            material_type = "OSB"
        elif "plywood" in desc_lower or "ply" in desc_lower:
            material_type = "Plywood"
        elif "gypsum" in desc_lower:
            material_type = "Gypsum"
        elif "cement" in desc_lower:
            material_type = "Cement Board"
        elif "waferboard" in desc_lower:
            material_type = "Waferboard"
        elif "particle" in desc_lower:
            material_type = "Particle Board"
        
        return {
            'material_type': material_type,
            'original_description': description
        }

    def _get_takeoff_options(self) -> str:
        """Show takeoff options menu"""
        if not self.search_data:
            return "No data loaded"

        result = "📋 Material Takeoff Options:\n\n"
        result += "Choose your takeoff scope:\n\n"
        result += "🔸 Type these commands:\n"
        result += "  'takeoff all'     → Complete project takeoff\n"
        result += "  'takeoff level 1' → Level 1 takeoff\n"
        result += "  'takeoff level 2' → Level 2 takeoff\n"
        result += "  'takeoff panel [name]' → Specific panel takeoff\n\n"
        result += "📊 Available Levels:\n"
        
        # Find available levels
        levels_found = set()
        for panel_name, panel_info in self.search_data['panels'].items():
            # Use the LevelNo from panel data
            level = panel_info.get('Level')
            if level:
                levels_found.add(str(level))
        
        if levels_found:
            for level in sorted(levels_found):
                result += f"  Level {level}\n"
        else:
            result += "  (Levels will be detected from panel names)\n"
        
        result += "\n📋 Available Panels:\n"
        # Show first few panels as examples
        panel_list = list(self.search_data['panels'].keys())[:10]
        for panel in panel_list:
            result += f"  {panel}\n"
        if len(self.search_data['panels']) > 10:
            result += f"  ... and {len(self.search_data['panels']) - 10} more\n"
        
        result += "\n💡 Example: 'takeoff level 1' or 'takeoff panel L1-Block6-Lot1-Unit3054-Brampton-004529'"
        return result

    def _get_level_takeoff(self, level_spec: str) -> str:
        """Get complete material takeoff for a specific level"""
        if not self.search_data:
            return "No data loaded"

        if not level_spec:
            return "Please specify a level number (e.g., 'takeoff level 1')"

        try:
            target_level = int(level_spec)
        except ValueError:
            return f"Invalid level number: {level_spec}"

        result = f"📋 Complete Material Takeoff - Level {target_level}\n"
        result += "=" * 50 + "\n\n"

        # Find panels in this level
        level_panels = []
        for panel_name, panel_info in self.search_data['panels'].items():
            # Use the LevelNo from panel data
            level = panel_info.get('Level')
            if level and str(level) == str(target_level):
                level_panels.append((panel_name, panel_info))

        if not level_panels:
            result += f"No panels found for Level {target_level}\n"
            result += "Available panels: " + ", ".join(list(self.search_data['panels'].keys())[:5]) + "..."
            return result

        result += f"📊 Level {target_level} Summary:\n"
        result += f"  Panels: {len(level_panels)}\n"
        panel_names = [p[0] for p in level_panels[:5]]
        result += f"  Panel Names: {', '.join(panel_names)}{'...' if len(level_panels) > 5 else ''}\n\n"

        # Count materials for this level
        level_materials = defaultdict(lambda: defaultdict(lambda: {'count': 0, 'descriptions': set()}))
        total_level_materials = 0

        for panel_name, panel_info in level_panels:
            for material_type, items in self.search_data['materials'].items():
                for item in items:
                    if item['panel_guid'] == panel_info['guid']:
                        element = item['element']
                        material_elem = element.find('Material')
                        if material_elem is not None:
                            desc = material_elem.find('Description')
                            if desc is not None and desc.text:
                                # Parse material subtype
                                parsed_info = self._parse_material_description(desc.text, material_type)
                                subtype = parsed_info['subtype']
                                level_materials[material_type][subtype]['count'] += 1
                                level_materials[material_type][subtype]['descriptions'].add(desc.text)
                                total_level_materials += 1

        # Display takeoff by material type
        result += "🏗️ MATERIAL TAKEOFF:\n"
        result += "-" * 30 + "\n\n"

        grand_total = 0
        for material_type in sorted(level_materials.keys()):
            result += f"📦 {material_type.upper()}:\n"
            material_total = 0
            
            for subtype in sorted(level_materials[material_type].keys()):
                subtype_data = level_materials[material_type][subtype]
                count = subtype_data['count']
                descriptions = subtype_data['descriptions']
                material_total += count
                grand_total += count
                
                result += f"  {subtype}: {count} pieces\n"
                # Show material descriptions
                for desc in sorted(descriptions):
                    desc_count = sum(1 for item in self.search_data['materials'][material_type] 
                                   if (item['panel_guid'] in [p[1]['guid'] for p in level_panels] and
                                       item['element'].find('Material/Description') is not None and
                                       item['element'].find('Material/Description').text == desc))
                    result += f"    • {desc}: {desc_count}\n"
            
            result += f"  Total {material_type}: {material_total} pieces\n\n"

        result += "=" * 50 + "\n"
        result += f"🎯 LEVEL {target_level} GRAND TOTAL: {grand_total} materials across {len(level_panels)} panels\n"
        result += "=" * 50

        return result

    def _get_panel_takeoff(self, panel_spec: str) -> str:
        """Get complete material takeoff for a specific panel"""
        if not self.search_data:
            return "No data loaded"

        if not panel_spec:
            return "Please specify a panel name (e.g., 'takeoff panel L1-Block6-Lot1-Unit3054-Brampton-004529')"

        # Find panel (partial matching)
        matching_panels = [name for name in self.search_data['panels'].keys() if panel_spec.lower() in name.lower()]
        
        if not matching_panels:
            return f"No panels found matching '{panel_spec}'\nAvailable panels: {', '.join(list(self.search_data['panels'].keys())[:5])}..."

        if len(matching_panels) > 1:
            return f"Multiple panels match '{panel_spec}':\n" + "\n".join(f"  {panel}" for panel in matching_panels[:10])

        panel_name = matching_panels[0]
        panel_info = self.search_data['panels'][panel_name]

        result = f"📋 Complete Material Takeoff - Panel: {panel_name}\n"
        result += "=" * 60 + "\n\n"

        result += f"📊 Panel Information:\n"
        result += f"  GUID: {panel_info['guid'][:8]}...\n"
        result += f"  Bundle: {panel_info['bundle_guid'][:8]}...\n\n"

        # Get all materials for this panel
        panel_materials = defaultdict(lambda: defaultdict(lambda: {'count': 0, 'descriptions': defaultdict(int)}))
        total_panel_materials = 0

        for material_type, items in self.search_data['materials'].items():
            for item in items:
                if item['panel_guid'] == panel_info['guid']:
                    element = item['element']
                    material_elem = element.find('Material')
                    if material_elem is not None:
                        desc = material_elem.find('Description')
                        if desc is not None and desc.text:
                            # Parse material subtype
                            parsed_info = self._parse_material_description(desc.text, material_type)
                            subtype = parsed_info['subtype']
                            panel_materials[material_type][subtype]['count'] += 1
                            panel_materials[material_type][subtype]['descriptions'][desc.text] += 1
                            total_panel_materials += 1

        # Display takeoff by material type
        result += "🏗️ MATERIAL TAKEOFF:\n"
        result += "-" * 30 + "\n\n"

        grand_total = 0
        for material_type in sorted(panel_materials.keys()):
            result += f"📦 {material_type.upper()}:\n"
            material_total = 0
            
            for subtype in sorted(panel_materials[material_type].keys()):
                subtype_data = panel_materials[material_type][subtype]
                count = subtype_data['count']
                material_total += count
                grand_total += count
                
                result += f"  {subtype}: {count} pieces\n"
                # Show material descriptions with counts
                for desc, desc_count in sorted(subtype_data['descriptions'].items()):
                    result += f"    • {desc}: {desc_count}\n"
            
            result += f"  Total {material_type}: {material_total} pieces\n\n"

        result += "=" * 60 + "\n"
        result += f"🎯 PANEL TOTAL: {grand_total} materials\n"
        result += "=" * 60

        return result

    def _get_complete_takeoff(self) -> str:
        """Get complete material takeoff for entire project"""
        if not self.search_data:
            return "No data loaded"

        result = "📋 Complete Project Material Takeoff\n"
        result += "=" * 50 + "\n\n"

        result += f"📊 Project Summary:\n"
        result += f"  Total Panels: {len(self.search_data['panels'])}\n"
        result += f"  Total Bundles: {len(self.search_data['bundles'])}\n"
        total_materials = sum(len(items) for items in self.search_data['materials'].values())
        result += f"  Total Materials: {total_materials}\n\n"

        # Complete material breakdown
        result += "🏗️ COMPLETE MATERIAL TAKEOFF:\n"
        result += "-" * 35 + "\n\n"

        grand_total = 0
        for material_type in sorted(self.search_data['materials'].keys()):
            items = self.search_data['materials'][material_type]
            material_total = len(items)
            grand_total += material_total
            
            result += f"📦 {material_type.upper()}: {material_total} pieces\n"
            
            # Group by subtype
            subtypes = defaultdict(lambda: {'count': 0, 'descriptions': defaultdict(int)})
            
            for item in items:
                element = item['element']
                material_elem = element.find('Material')
                if material_elem is not None:
                    desc = material_elem.find('Description')
                    if desc is not None and desc.text:
                        # Parse material subtype
                        parsed_info = self._parse_material_description(desc.text, material_type)
                        subtype = parsed_info['subtype']
                        subtypes[subtype]['count'] += 1
                        subtypes[subtype]['descriptions'][desc.text] += 1
            
            # Display subtypes
            for subtype in sorted(subtypes.keys()):
                subtype_data = subtypes[subtype]
                result += f"  {subtype}: {subtype_data['count']} pieces\n"
                
                # Show top descriptions (limit to avoid too much output)
                sorted_descs = sorted(subtype_data['descriptions'].items(), key=lambda x: x[1], reverse=True)
                for desc, count in sorted_descs[:5]:  # Show top 5
                    result += f"    • {desc}: {count}\n"
                if len(sorted_descs) > 5:
                    result += f"    • ... and {len(sorted_descs) - 5} more\n"
            
            result += "\n"

        result += "=" * 50 + "\n"
        result += f"🎯 PROJECT GRAND TOTAL: {grand_total} materials\n"
        result += "=" * 50 + "\n\n"
        result += "💡 For level-specific takeoff: 'takeoff level 1'\n"
        result += "💡 For panel-specific takeoff: 'takeoff panel [name]'"

        return result

    def _get_help_reference(self) -> str:
        """Get comprehensive help reference for all available commands"""
        result = "❓ EHX Search Command Reference\n"
        result += "=" * 50 + "\n\n"

        result += "🔍 BASIC SEARCH COMMANDS:\n"
        result += "  'panels'           → List all panels\n"
        result += "  'materials'        → Full material breakdown\n"
        result += "  'bundles'          → List all bundles\n"
        result += "  '[panel name]'     → Search specific panel\n"
        result += "  'count [material]' → Count specific material\n\n"

        result += "🏗️ CONSTRUCTION QUERIES:\n"
        result += "  'sheathing'        → Sheathing analysis\n"
        result += "  'sheets'           → Sheet material analysis\n"
        result += "  'boards'           → Board material analysis\n"
        result += "  'bracing'          → Bracing material analysis\n"
        result += "  'precut'           → Precut lumber analysis\n"
        result += "  'liner'            → Liner material analysis\n\n"

        result += "📋 MATERIAL TAKEOFF:\n"
        result += "  'takeoff'          → Show takeoff options\n"
        result += "  'takeoff all'      → Complete project takeoff\n"
        result += "  'takeoff level 1'  → Level 1 takeoff\n"
        result += "  'takeoff level 2'  → Level 2 takeoff\n"
        result += "  'takeoff panel [name]' → Panel takeoff\n\n"

        result += "🔧 LEVEL & PANEL ANALYSIS:\n"
        result += "  'level 1'          → Level 1 material breakdown\n"
        result += "  'level 2'          → Level 2 material breakdown\n"
        result += "  'panel [name]'     → Panel material details\n\n"

        result += "📤 EXPORT COMMANDS:\n"
        result += "  'export txt'       → Export to text file\n"
        result += "  'export csv'       → Export to CSV file\n"
        result += "  'export takeoff'   → Export current takeoff\n\n"

        result += "🛠️ UTILITY COMMANDS:\n"
        result += "  'help' or '?'      → Show this help\n"
        result += "  'commands'         → Show this help\n"
        result += "  'summary'          → Project overview\n"
        result += "  'clear'            → Clear results\n\n"

        result += "🎯 QUICK BUTTONS:\n"
        result += "  📋 Panels    → List all panels\n"
        result += "  🏗️ Materials → Material breakdown\n"
        result += "  📦 Bundles   → Bundle information\n"
        result += "  🧱 Sheathing → Sheathing analysis\n"
        result += "  📊 Summary   → Project summary\n"
        result += "  🪚 Precuts   → Precut analysis\n"
        result += "  📋 Takeoff   → Takeoff options\n"
        result += "  ❓ Help      → This help reference\n"
        result += "  💾 Export    → Export results\n"
        result += "  🧹 Clear     → Clear results\n\n"

        result += "💡 TIPS:\n"
        result += "  • Type any panel name for instant details\n"
        result += "  • Use partial names (e.g., 'L1-Block6')\n"
        result += "  • Material types are never combined (SPF ≠ Stud)\n"
        result += "  • All quantities are exact for construction\n"
        result += "  • Export any results for external use\n\n"

        result += "=" * 50 + "\n"
        result += "🚀 Ready for construction takeoff and analysis!\n"
        result += "=" * 50

        return result

    def _handle_export_command(self, query: str) -> str:
        """Handle export commands"""
        export_type = query.replace("export", "").strip().lower()

        if not export_type:
            return "Please specify export type: 'export txt', 'export csv', or 'export takeoff'"

        if export_type == "txt":
            return self._export_to_text()
        elif export_type == "csv":
            return self._export_to_csv()
        elif export_type == "takeoff":
            return self._export_takeoff()
        else:
            return f"Unknown export type: {export_type}. Use 'export txt', 'export csv', or 'export takeoff'"

    def _export_results(self):
        """Export current results to file (called from button)"""
        if not self.search_data:
            self._show_error("No data loaded to export")
            return

        # Get current results
        current_results = self.results_text.get(1.0, tk.END).strip()
        if not current_results:
            self._show_error("No results to export")
            return

        # Ask user for export type
        from tkinter import simpledialog
        export_type = simpledialog.askstring(
            "Export Results",
            "Choose export format:\n\n• 'txt' for text file\n• 'csv' for spreadsheet\n• 'takeoff' for construction takeoff",
            parent=self.winfo_toplevel()
        )

        if not export_type:
            return

        export_type = export_type.lower().strip()

        if export_type == "txt":
            self._export_to_text()
        elif export_type == "csv":
            self._export_to_csv()
        elif export_type == "takeoff":
            self._export_takeoff()
        else:
            self._show_error(f"Unknown export type: {export_type}")

    def _export_to_text(self) -> str:
        """Export current results to text file"""
        try:
            from tkinter import filedialog
            current_results = self.results_text.get(1.0, tk.END).strip()

            if not current_results:
                return "No results to export"

            # Suggest filename based on current search
            default_name = "ehx_search_results.txt"
            if hasattr(self, 'ehx_file_path') and self.ehx_file_path:
                import os
                base_name = os.path.splitext(os.path.basename(str(self.ehx_file_path)))[0]
                default_name = f"{base_name}_search_results.txt"

            file_path = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                initialfile=default_name,
                title="Export Search Results to Text File"
            )

            if file_path:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write("EHX Search Results Export\n")
                    f.write("=" * 50 + "\n\n")
                    f.write(current_results)
                    f.write("\n\nExported from EHX Search Widget\n")
                    f.write(f"Date: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

                return f"✅ Results exported to: {file_path}"
            else:
                return "Export cancelled"

        except Exception as e:
            return f"❌ Export failed: {str(e)}"

    def _export_to_csv(self) -> str:
        """Export material data to CSV format"""
        try:
            from tkinter import filedialog
            import csv

            if not self.search_data:
                return "No data to export"

            # Suggest filename
            default_name = "ehx_materials.csv"
            if hasattr(self, 'ehx_file_path') and self.ehx_file_path:
                import os
                base_name = os.path.splitext(os.path.basename(str(self.ehx_file_path)))[0]
                default_name = f"{base_name}_materials.csv"

            file_path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialfile=default_name,
                title="Export Materials to CSV"
            )

            if file_path:
                with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)

                    # Write header
                    writer.writerow(['Material Type', 'Subtype', 'Description', 'Quantity', 'Panel GUID'])

                    # Write material data
                    for material_type, items in self.search_data['materials'].items():
                        for item in items:
                            element = item['element']
                            material_elem = element.find('Material')
                            if material_elem is not None:
                                desc = material_elem.find('Description')
                                if desc is not None and desc.text:
                                    parsed_info = self._parse_material_description(desc.text, material_type)
                                    writer.writerow([
                                        material_type,
                                        parsed_info['subtype'],
                                        desc.text,
                                        1,  # Each row represents one piece
                                        item['panel_guid']
                                    ])

                return f"✅ Materials exported to CSV: {file_path}"
            else:
                return "Export cancelled"

        except Exception as e:
            return f"❌ CSV export failed: {str(e)}"

    def _export_takeoff(self) -> str:
        """Export current takeoff data to formatted file"""
        try:
            from tkinter import filedialog
            current_results = self.results_text.get(1.0, tk.END).strip()

            if not current_results or "takeoff" not in current_results.lower():
                return "No takeoff data found. Please run a takeoff command first."

            # Suggest filename
            default_name = "ehx_takeoff.txt"
            if hasattr(self, 'ehx_file_path') and self.ehx_file_path:
                import os
                base_name = os.path.splitext(os.path.basename(str(self.ehx_file_path)))[0]
                default_name = f"{base_name}_takeoff.txt"

            file_path = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                initialfile=default_name,
                title="Export Takeoff to File"
            )

            if file_path:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write("EHX MATERIAL TAKEOFF\n")
                    f.write("=" * 60 + "\n\n")
                    f.write("Construction Material Takeoff Report\n")
                    f.write(f"Generated: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                    f.write("-" * 60 + "\n\n")
                    f.write(current_results)
                    f.write("\n\n" + "=" * 60 + "\n")
                    f.write("END OF TAKEOFF REPORT\n")
                    f.write("=" * 60 + "\n")

                return f"✅ Takeoff exported to: {file_path}"
            else:
                return "Export cancelled"

        except Exception as e:
            return f"❌ Takeoff export failed: {str(e)}"

    def _write_log_files(self, file_path: str, root):
        """Write expected.log and materials.log files for the EHX file"""
        try:
            import os
            from datetime import datetime
            
            folder = os.path.dirname(file_path)
            fname = os.path.basename(file_path)
            ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Detect EHX format version
            ehx_version = "legacy"
            if root.find('EHXVersion') is not None:
                ehx_version = "v2.0"

            # For v2.0 format, build mapping from PanelID/Label to BundleName from Junction elements
            junction_bundle_map = {}  # maps PanelID/Label -> BundleName
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

            # Build panels data from XML
            panels_by_name = {}
            materials_map = {}
            
            for panel_el in root.findall('.//Panel'):
                panel_guid = None
                panel_label = None
                
                for t in ('PanelGuid', 'PanelID'):
                    el = panel_el.find(t)
                    if el is not None and el.text:
                        panel_guid = el.text.strip()
                        break
                
                label_el = panel_el.find('Label')
                if label_el is not None and label_el.text:
                    panel_label = label_el.text.strip()
                
                if not panel_guid:
                    panel_guid = f"Panel_{len(panels_by_name)+1}"
                if not panel_label:
                    panel_label = panel_guid
                
                panel_obj = {'Name': panel_guid, 'DisplayLabel': panel_label}
                
                for fld in ['Level', 'Description', 'Bundle', 'BundleName', 'Height', 'Thickness', 
                           'StudSpacing', 'WallLength', 'LoadBearing', 'Category', 'Weight']:
                    el = panel_el.find(fld)
                    if el is not None and el.text:
                        panel_obj[fld] = el.text.strip()
                
                # Special handling for v2.0 format: extract BundleName from Junction mapping
                if ehx_version == "v2.0" and not panel_obj.get('BundleName'):
                    # Try to match by PanelID/Label using the junction mapping
                    panel_id = panel_obj.get('Name')  # This is the panel_guid/panel_id
                    panel_label = panel_obj.get('DisplayLabel')  # This is the display label
                    
                    bundle_name = None
                    if panel_id and panel_id in junction_bundle_map:
                        bundle_name = junction_bundle_map[panel_id]
                    elif panel_label and panel_label in junction_bundle_map:
                        bundle_name = junction_bundle_map[panel_label]
                    
                    if bundle_name:
                        panel_obj['BundleName'] = bundle_name
                
                panels_by_name[panel_guid] = panel_obj
                
                # Parse materials for this panel
                mats = []
                for node in panel_el.findall('.//Board'):
                    typ = node.find('FamilyMemberName')
                    typ = typ.text if typ is not None else 'Board'
                    label = node.find('Label')
                    label = label.text if label is not None else ''
                    desc = node.find('Material/Description')
                    desc = desc.text if desc is not None else ''
                    qty = node.find('Quantity')
                    qty = qty.text if qty is not None else '1'
                    mats.append({'Type': typ, 'Label': label, 'Desc': desc, 'Qty': qty})
                
                materials_map[panel_guid] = mats

            # Sort panels by bundle, then by panel name for consistent log output
            sorted_panels = sort_panels_by_bundle_and_name(panels_by_name)

            # Detect unassigned panels
            unassigned_panels = detect_unassigned_panels(panels_by_name)
            
            # For v2.0 files, get diagnostic information
            ehx_version = "legacy"
            diag_report = None
            try:
                # Try to detect version from the file path or content
                import os
                fname_lower = os.path.basename(folder).lower()
                if 'mpo' in fname_lower or 'v2' in fname_lower:
                    ehx_version = "v2.0"
                    # Get diagnostic info for v2.0 files
                    diag_report = diagnose_v2_bundle_assignment(root, ehx_version, panels_by_name)
            except Exception as e:
                print(f"Search widget diagnostic setup error: {e}")

            # Write expected.log
            expected_path = os.path.join(folder, 'expected.log')
            with open(expected_path, 'w', encoding='utf-8') as fh:
                fh.write(f"=== expected.log cleared at {ts} for {fname} ===\n")
                
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
                
                for pname, pobj in sorted_panels:
                    display_name = pobj.get('DisplayLabel', pname)
                    fh.write(f"Panel: {display_name}\n")
                    if 'Level' in pobj:
                        fh.write(f"Level: {pobj.get('Level')}\n")
                    if 'Description' in pobj:
                        fh.write(f"Description: {pobj.get('Description')}\n")
                    b = pobj.get('Bundle') or pobj.get('BundleName') or ''
                    if b:
                        fh.write(f"Bundle: {b}\n")
                    fh.write("Panel Details:\n")
                    for key in ['Category', 'LoadBearing', 'WallLength', 'Height', 'Thickness', 'StudSpacing']:
                        if key in pobj:
                            fh.write(f"• {key}: {pobj.get(key)}\n")
                    if 'Weight' in pobj:
                        fh.write(f"• Weight: {pobj.get('Weight')}\n")
                    fh.write('\n')
                    fh.write("Panel Material Breakdown:\n")
                    for m in materials_map.get(pname, []):
                        if isinstance(m, dict):
                            lbl = m.get('Label') or ''
                            typ = m.get('Type') or ''
                            desc = m.get('Desc') or ''
                            qty = m.get('Qty') or ''
                            if lbl or typ or desc:
                                fh.write(f"{lbl} - {typ} - {desc} - ({qty})\n")
                    fh.write('---\n')

            # Write materials.log
            materials_path = os.path.join(folder, 'materials.log')
            with open(materials_path, 'w', encoding='utf-8') as fh:
                fh.write(f"=== materials.log cleared at {ts} for {fname} ===\n")
                for pname, pobj in sorted_panels:
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
                        if isinstance(m, dict):
                            fh.write(f"Type: {m.get('Type','')} , Label: {m.get('Label','')} , Desc: {m.get('Desc','')}\n")
                    fh.write('---\n')

            print(f"DEBUG: Successfully wrote log files for {fname}")
            
        except Exception as e:
            print(f"DEBUG: Failed to write log files from search widget: {e}")


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
