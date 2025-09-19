#!/usr/bin/env python3
"""
EHX Search Widget - Tkinter widget for GUI integration
Can be embedded into existing Tkinter applications
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Callable
from collections import defaultdict, Counter
import threading
import queue
import math

# Global debug control
debug_enabled = True

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

# Import formatting functions from Vold.py
try:
    from Vold import format_dimension, format_weight
except ImportError:
    # Fallback definitions if Vold.py is not available
    def format_dimension(value):
        """Strip trailing zeros from decimal values."""
        try:
            f = float(value)
            if f == int(f):
                return str(int(f))
            return str(f).rstrip('0').rstrip('.')
        except (ValueError, TypeError):
            return str(value)
    
    def format_weight(value):
        """Round weight up to nearest integer and add 'Lbs'."""
        try:
            f = float(value)
            return f"{int(f + 0.5)} Lbs"
        except (ValueError, TypeError):
            return f"{value} Lbs"

# Global debug control
debug_enabled = True

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

        # Cooperative mode settings
        self.cooperative_mode = True  # Allow parent GUI to work alongside search widget

        # Dynamic prefix for panel queries (extracted from filename)
        self.panel_prefix = "05"  # Default fallback

        self._setup_ui()
        self._setup_bindings()

        if ehx_file_path:
            self.load_ehx_file(ehx_file_path)

    def _setup_ui(self):
        """Setup the user interface"""
        # Main container - don't grab focus by default
        self.configure(padding=5, takefocus=0)

        # Search frame
        search_frame = ttk.Frame(self)
        search_frame.pack(fill=tk.X, pady=(0, 5))

        # Search label
        ttk.Label(search_frame, text="🔍 EHX Search:").pack(side=tk.LEFT, padx=(0, 5))

        # Search entry - configure to not grab focus automatically
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(
            search_frame,
            textvariable=self.search_var,
            font=("Segoe UI", 10),
            takefocus=1  # Allow focus when explicitly requested
        )
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        # Search button
        self.search_button = ttk.Button(
            search_frame,
            text="Search",
            command=self._perform_search,
            takefocus=0  # Don't grab focus when clicked
        )
        self.search_button.pack(side=tk.RIGHT)

        # Results frame
        results_frame = ttk.LabelFrame(self, text="Search Results", padding=5)
        results_frame.pack(fill=tk.BOTH, expand=True)

        # Results text area (terminal-like) - don't grab focus
        self.results_text = scrolledtext.ScrolledText(
            results_frame,
            wrap=tk.WORD,
            font=("Consolas", 9),
            bg="#1e1e1e",
            fg="#d4d4d4",
            insertbackground="#d4d4d4",
            takefocus=0  # Don't grab focus automatically
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

        ttk.Button(quick_frame, text="� Load EHX", command=self._load_ehx_dialog, takefocus=0).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(quick_frame, text="�📋 Panels", command=lambda: self._quick_search("panels"), takefocus=0).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(quick_frame, text="🏗️ Materials", command=lambda: self._quick_search("materials"), takefocus=0).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(quick_frame, text="📦 Bundles", command=lambda: self._quick_search("bundles"), takefocus=0).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(quick_frame, text="🧱 Sheathing", command=lambda: self._quick_search("sheathing"), takefocus=0).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(quick_frame, text="📊 Summary", command=lambda: self._quick_search("summary"), takefocus=0).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(quick_frame, text="🪚 Precuts", command=lambda: self._quick_search("precuts"), takefocus=0).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(quick_frame, text="📋 Takeoff", command=lambda: self._quick_search("takeoff"), takefocus=0).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(quick_frame, text="❓ Help", command=lambda: self._quick_search("help"), takefocus=0).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(quick_frame, text="💾 Export", command=self._export_results, takefocus=0).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(quick_frame, text="🧹 Clear", command=self.clear_results, takefocus=0).pack(side=tk.RIGHT)

    def _setup_bindings(self):
        """Setup keyboard and event bindings"""
        # Enter key to search
        self.search_entry.bind("<Return>", lambda e: self._perform_search())

        # Ctrl+L to clear
        self.bind("<Control-l>", lambda e: self.clear_results())
        self.search_entry.bind("<Control-l>", lambda e: self.clear_results())

        # Focus management - don't grab focus by default to allow parent GUI to work
        # Only focus when user explicitly clicks on the search entry
        self.search_entry.bind("<FocusIn>", self._on_search_focus_in)
        self.search_entry.bind("<FocusOut>", self._on_search_focus_out)

        # Allow parent widgets to receive events when search widget doesn't need them
        self.bind("<FocusOut>", self._on_widget_focus_out)

    def _on_search_focus_in(self, event=None):
        """Called when search entry gets focus"""
        # When user clicks on search entry, allow it to have focus for typing
        pass

    def _on_search_focus_out(self, event=None):
        """Called when search entry loses focus"""
        # When search entry loses focus, don't force focus back to it
        # This allows parent GUI elements to work properly
        pass

    def _on_widget_focus_out(self, event=None):
        """Called when the entire widget loses focus"""
        # Don't force focus back to search entry when widget loses focus
        # This allows parent application to maintain control
        pass

    def request_focus(self):
        """Allow parent application to explicitly give focus to search widget"""
        self.search_entry.focus_set()

    def release_focus(self):
        """Allow parent application to explicitly remove focus from search widget"""
        # Move focus to parent widget if possible
        try:
            self.winfo_toplevel().focus_set()
        except:
            pass

    def set_cooperative_mode(self, enabled: bool = True):
        """Enable or disable cooperative mode for better integration with parent GUI"""
        self.cooperative_mode = enabled
        if enabled:
            # In cooperative mode, don't grab focus automatically
            self.configure(takefocus=0)
            self.results_text.configure(takefocus=0)
        else:
            # In standalone mode, allow normal focus behavior
            self.configure(takefocus=1)
            self.results_text.configure(takefocus=1)

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
            self.after(0, lambda e=e: self._show_error(f"Error loading EHX file: {e}"))

    def _load_ehx_dialog(self):
        """Open file dialog to select and load an EHX file"""
        file_path = filedialog.askopenfilename(
            title="Select EHX File",
            filetypes=[("EHX files", "*.ehx"), ("All files", "*.*")]
        )
        
        if file_path:
            self.load_ehx_file(file_path)

    def _build_search_indexes(self, root) -> Dict:
        """Build search indexes from XML data"""
        # Detect EHX format version
        ehx_version = "legacy"
        if root.find('EHXVersion') is not None:
            ehx_version = "v2.0"
            ehx_ver = root.find('EHXVersion').text.strip() if root.find('EHXVersion') is not None else ""
            if debug_enabled:
                print(f"DEBUG: Search widget detected EHX format: {ehx_version} (Version: {ehx_ver})")
        else:
            if debug_enabled:
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
                # Extract BundleName from various possible fields (matching Vold script logic)
                bundle_name = None
                for field in ('BundleName', 'Bundle', 'BundleLabel'):
                    bundle_el = panel.find(field)
                    if bundle_el is not None and bundle_el.text:
                        bundle_name = bundle_el.text.strip()
                        break
                
                # For v2.0 format, try to get BundleName from junction mapping
                if ehx_version == "v2.0" and not bundle_name:
                    panel_id_el = panel.find('PanelID')
                    label_el = panel.find('Label')
                    
                    if panel_id_el is not None and panel_id_el.text and panel_id_el.text.strip() in junction_bundle_map:
                        bundle_name = junction_bundle_map[panel_id_el.text.strip()]
                    elif label_el is not None and label_el.text and label_el.text.strip() in junction_bundle_map:
                        bundle_name = junction_bundle_map[label_el.text.strip()]
                    
                    # Fallback: try to derive BundleName from BundleLayer
                    if not bundle_name:
                        bundle_layer_el = panel.find('BundleLayer')
                        if bundle_layer_el is not None and bundle_layer_el.text:
                            try:
                                bundle_layer = int(bundle_layer_el.text.strip())
                                if bundle_layer in bundle_layer_map:
                                    bundle_name = bundle_layer_map[bundle_layer]
                            except ValueError:
                                pass
                
                search_data['panels'][label.text] = {
                    'guid': panel.find('PanelGuid').text if panel.find('PanelGuid') is not None else '',
                    'bundle_guid': panel.find('BundleGuid').text if panel.find('BundleGuid') is not None else '',
                    'level_guid': panel.find('LevelGuid').text if panel.find('LevelGuid') is not None else '',
                    'BundleName': bundle_name or '',
                    'Level': panel.find('LevelNo').text if panel.find('LevelNo') is not None else '',
                    # Extract dimensional information (matching Vold script)
                    'Weight': panel.find('Weight').text if panel.find('Weight') is not None else '',
                    'Thickness': panel.find('Thickness').text if panel.find('Thickness') is not None else '',
                    'StudSpacing': panel.find('StudSpacing').text if panel.find('StudSpacing') is not None else '',
                    'StudHeight': panel.find('StudHeight').text if panel.find('StudHeight') is not None else '',
                    'WallLength': panel.find('WallLength').text if panel.find('WallLength') is not None else '',
                    'Length': panel.find('WallLength').text if panel.find('WallLength') is not None else '',  # Alias for compatibility
                    'Height': panel.find('Height').text if panel.find('Height') is not None else '',
                    'Category': panel.find('Category').text if panel.find('Category') is not None else '',
                    'LoadBearing': panel.find('LoadBearing').text if panel.find('LoadBearing') is not None else '',
                    'Description': panel.find('Description').text if panel.find('Description') is not None else '',
                    'ProductionNotes': panel.find('ProductionNotes').text if panel.find('ProductionNotes') is not None else ''
                }
                
                # Parse squaring dimension from SquareDimension element (nested under Squaring) - matching Vold script
                panel_obj = search_data['panels'][label.text]
                squaring_el = panel.find('Squaring')
                if squaring_el is not None:
                    square_dim_el = squaring_el.find('SquareDimension')
                    if square_dim_el is not None and square_dim_el.text:
                        try:
                            square_inches = float(square_dim_el.text.strip())
                            panel_obj['Squaring_inches'] = square_inches  # Store raw inches
                            panel_obj['Squaring'] = inches_to_feet_inches_sixteenths(square_inches)
                        except (ValueError, TypeError):
                            panel_obj['Squaring'] = square_dim_el.text.strip()
                
                # Fallback: try direct SquareDimension element if nested structure not found
                if 'Squaring' not in panel_obj:
                    square_el = panel.find('SquareDimension')
                    if square_el is not None and square_el.text:
                        try:
                            square_inches = float(square_el.text.strip())
                            panel_obj['Squaring_inches'] = square_inches
                            panel_obj['Squaring'] = inches_to_feet_inches_sixteenths(square_inches)
                        except (ValueError, TypeError):
                            panel_obj['Squaring'] = square_el.text.strip()

                # Calculate squaring if not found using Pythagorean theorem (matching Vold script)
                if 'Squaring' not in panel_obj:
                    if 'Height' in panel_obj and 'WallLength' in panel_obj:
                        try:
                            h = float(panel_obj['Height']) - 1.5  # Subtract top plate
                            l = float(panel_obj['WallLength'])
                            calc_inches = math.sqrt(h**2 + l**2)
                            panel_obj['Squaring_inches'] = calc_inches  # Store raw inches
                            panel_obj['Squaring'] = inches_to_feet_inches_sixteenths(calc_inches)
                        except (ValueError, TypeError):
                            # Fallback to a simple calculation function if available
                            pass

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
        
        # Extract panel prefix from filename (e.g., "07" from "07_112.ehx")
        filename = Path(file_path).name
        if '_' in filename:
            prefix_part = filename.split('_')[0]
            if prefix_part.isdigit() and len(prefix_part) == 2:
                self.panel_prefix = prefix_part
                print(f"DEBUG: Extracted panel prefix '{self.panel_prefix}' from filename '{filename}'")
            else:
                print(f"DEBUG: Could not extract valid prefix from '{filename}', using default '05'")
        else:
            print(f"DEBUG: No underscore in filename '{filename}', using default '05'")
        
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
        
        # Add comprehensive panel breakdown by level and bundle
        self._append_result("info", "")
        self._append_result("info", "📋 AVAILABLE PANELS (Sorted by Level, Bundle, and Panel Number):")
        self._append_result("info", "=" * 70)
        
        # Group panels by level and bundle
        panels_by_level_bundle = defaultdict(lambda: defaultdict(list))
        
        for panel_name, panel_info in search_data['panels'].items():
            # Use the level information already extracted from EHX file (LevelNo)
            level = panel_info.get('Level', 'Unknown')
            if level and level != 'Unknown':
                # Convert numeric level to display format (e.g., "1" -> "Level 1")
                try:
                    level_num = int(level)
                    level = f"Level {level_num}"
                except ValueError:
                    # If it's not a number, use as-is (might already be formatted)
                    pass
            else:
                level = "Unknown"
            
            # Get bundle name
            bundle_name = panel_info.get('BundleName', 'Unknown Bundle')
            if bundle_name == 'Unknown Bundle':
                bundle_guid = panel_info.get('bundle_guid', '')
                if bundle_guid and not bundle_guid.startswith('{'):
                    bundle_name = bundle_guid
                else:
                    bundle_name = f"Bundle {bundle_guid[:8]}" if bundle_guid else "Unknown Bundle"
            
            panels_by_level_bundle[level][bundle_name].append(panel_name)
        
        # Display panels organized by level and bundle
        for level in sorted(panels_by_level_bundle.keys()):
            self._append_result("info", f"🏢 {level.upper()}:")
            
            for bundle_name in sorted(panels_by_level_bundle[level].keys()):
                panels_in_bundle = sorted(panels_by_level_bundle[level][bundle_name])
                bundle_panel_count = len(panels_in_bundle)
                
                self._append_result("info", f"  📦 {bundle_name} ({bundle_panel_count} panels):")
                
                # Group panels by number ranges for better readability
                if len(panels_in_bundle) <= 10:
                    # Show all panels if 10 or fewer
                    panel_list = ", ".join(panels_in_bundle)
                    self._append_result("info", f"    {panel_list}")
                else:
                    # Show all panels (no truncation)
                    panel_list = ", ".join(panels_in_bundle)
                    self._append_result("info", f"    {panel_list}")
            
            self._append_result("info", "")
        
        # Show summary statistics
        total_panels = len(search_data['panels'])
        total_bundles = len(search_data['bundles'])
        panels_per_bundle = total_panels / total_bundles if total_bundles > 0 else 0
        
        self._append_result("info", "📊 PROJECT SUMMARY:")
        self._append_result("info", f"  • Total Panels: {total_panels}")
        self._append_result("info", f"  • Total Bundles: {total_bundles}")
        self._append_result("info", f"  • Average Panels per Bundle: {panels_per_bundle:.1f}")
        self._append_result("info", f"  • Total Materials: {sum(len(items) for items in search_data['materials'].values())}")
        self._append_result("info", "")
        
        # Show quick query examples
        self._append_result("info", "💡 QUICK QUERY EXAMPLES:")
        self._append_result("info", f"  • '{self.panel_prefix}-100' or '{self.panel_prefix}-100 info' → Panel details")
        self._append_result("info", f"  • '{self.panel_prefix}-100 fm' → Family Member analysis")
        self._append_result("info", f"  • '{self.panel_prefix}-100 sub' → SubAssembly analysis")
        self._append_result("info", "  • 'level 1' → Level 1 material breakdown")
        self._append_result("info", "  • 'takeoff all' → Complete project takeoff")
        
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

        # Check if this is an info query to avoid showing command
        is_info_query = (query.startswith("info") or query.endswith(" info"))
        if not is_info_query:
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

        # Clear search box for next query but don't force focus
        self.search_var.set("")
        # Don't call focus_set() here to allow parent GUI to maintain control

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
        
        # NEW: Panel extraction queries
        if "ehx" in query.lower() and len(query.split()) >= 2:
            # Extract panel name from query like "05-100 ehx"
            parts = query.split()
            if len(parts) >= 2 and parts[-1].lower() == "ehx":
                panel_name = " ".join(parts[:-1]).strip()
                return self._handle_panel_extraction(panel_name)

        # Original functionality preserved
        
        # NEW: Panel info command - comprehensive overview
        # Handle both "info panel_name" and "panel_name info" formats
        if query.startswith("info"):
            panel_part = query.replace("info", "").strip()
            if panel_part:
                return self._get_panel_comprehensive_vold_info(panel_part)
            else:
                return "Please specify a panel name (e.g., '05-100 info')"
        elif query.endswith(" info"):
            # Handle "panel_name info" format
            panel_part = query.replace(" info", "").strip()
            if panel_part:
                return self._get_panel_comprehensive_vold_info(panel_part)
            else:
                return "Please specify a panel name (e.g., '05-100 info')"
        
        # NEW: SubAssembly analysis queries
        if "subassembly" in query.lower() or "sub assembly" in query.lower() or "sub" in query.lower():
            return self._handle_subassembly_query(query)
        
        if "panel" in query and len(query.split()) > 1:
            panel_name = query.replace("panel", "").strip()
            if panel_name in self.search_data['panels']:
                return self._get_panel_construction_details(panel_name)
        
        if query in ["precut", "precuts", "2x4", "2x6"]:
            return self._get_precut_analysis()
        
        if "liner" in query or "length" in query:
            return self._get_liner_analysis()

        # Check for 3-digit lot number at start of query and prepend correct prefix
        if len(query) >= 3 and query[:3].isdigit():
            # Check if followed by space or end of string
            if len(query) == 3 or query[3] == ' ':
                query = f"{self.panel_prefix}-{query[:3]}{query[3:]}"

        # Handle abbreviated commands after prefixing
        query_lower = query.lower()
        
        # Check for abbreviated panel commands
        if query_lower.endswith(' info'):
            panel_part = query[:-5].strip()  # Remove ' info'
            if panel_part:
                # Normalize panel part for matching (convert dashes to underscores and vice versa)
                normalized_panel_part = panel_part.replace('-', '_')
                alt_panel_part = panel_part.replace('_', '-')
                
                matching_panels = []
                for name in self.search_data['panels'].keys():
                    name_lower = name.lower()
                    if (normalized_panel_part.lower() in name_lower or 
                        alt_panel_part.lower() in name_lower or
                        panel_part.lower() in name_lower):
                        matching_panels.append(name)
                
                if matching_panels:
                    if len(matching_panels) == 1:
                        return self._get_panel_comprehensive_vold_info(matching_panels[0])
                    else:
                        return f"Multiple panels match '{panel_part}':\n" + "\n".join(f"  {panel}" for panel in matching_panels[:10])
                else:
                    return f"No panels found matching '{panel_part}'"
        
        elif query_lower.endswith(' fm'):
            panel_part = query[:-3].strip()  # Remove ' fm'
            if panel_part:
                matching_panels = [name for name in self.search_data['panels'].keys() 
                                  if panel_part.lower() in name.lower()]
                if matching_panels:
                    if len(matching_panels) == 1:
                        return self._get_panel_comprehensive_fm_analysis(matching_panels[0])
                    else:
                        return f"Multiple panels match '{panel_part}':\n" + "\n".join(f"  {panel}" for panel in matching_panels[:10])
                else:
                    return f"No panels found matching '{panel_part}'"
        
        elif query_lower.endswith(' sub'):
            panel_part = query[:-4].strip()  # Remove ' sub'
            if panel_part:
                matching_panels = [name for name in self.search_data['panels'].keys() 
                                  if panel_part.lower() in name.lower()]
                if matching_panels:
                    if len(matching_panels) == 1:
                        return self._get_panel_subassemblies(matching_panels[0])
                    else:
                        return f"Multiple panels match '{panel_part}':\n" + "\n".join(f"  {panel}" for panel in matching_panels[:10])
                else:
                    return f"No panels found matching '{panel_part}'"
        
        elif query_lower.endswith(' poc'):
            panel_part = query[:-4].strip()  # Remove ' poc'
            if panel_part:
                matching_panels = [name for name in self.search_data['panels'].keys() 
                                  if panel_part.lower() in name.lower()]
                if matching_panels:
                    if len(matching_panels) == 1:
                        return self._get_panel_beam_pockets(matching_panels[0])
                    else:
                        return f"Multiple panels match '{panel_part}':\n" + "\n".join(f"  {panel}" for panel in matching_panels[:10])
                else:
                    return f"No panels found matching '{panel_part}'"
        
        elif query_lower.endswith(' xstud'):
            panel_part = query[:-6].strip()  # Remove ' xstud'
            if panel_part:
                matching_panels = [name for name in self.search_data['panels'].keys() 
                                  if panel_part.lower() in name.lower()]
                if matching_panels:
                    if len(matching_panels) == 1:
                        return self._get_panel_critical_studs(matching_panels[0])
                    else:
                        return f"Multiple panels match '{panel_part}':\n" + "\n".join(f"  {panel}" for panel in matching_panels[:10])
                else:
                    return f"No panels found matching '{panel_part}'"
        
        elif query_lower.endswith(' sheet'):
            panel_part = query[:-6].strip()  # Remove ' sheet'
            if panel_part:
                matching_panels = [name for name in self.search_data['panels'].keys() 
                                  if panel_part.lower() in name.lower()]
                if matching_panels:
                    if len(matching_panels) == 1:
                        return self._get_panel_sheathing(matching_panels[0])
                    else:
                        return f"Multiple panels match '{panel_part}':\n" + "\n".join(f"  {panel}" for panel in matching_panels[:10])
                else:
                    return f"No panels found matching '{panel_part}'"

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
            # Use the level information already extracted from EHX file (LevelNo)
            panel_level = panel_info.get('Level', '')
            if panel_level and str(panel_level) == str(target_level):
                level_panels.append((panel_name, panel_info))

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

    def get_panel_type_category(self, subassembly_name: str) -> str:
        """Categorize SubAssembly by panel type based on naming patterns"""
        name_lower = subassembly_name.lower()
        
        # Handle new format: "MaterialType: FMxx-Name" 
        if ': ' in subassembly_name:
            # Extract the part after the colon
            name_part = subassembly_name.split(': ', 1)[1]
            name_lower = name_part.lower()
        
        # FM32 - LType variations
        if any(pattern in name_lower for pattern in ['fm32', 'ltype', 'l-type']):
            if 'critical' in name_lower and 'stud' in name_lower:
                return "FM32 - Critical Studs"
            elif 'end' in name_lower and 'stud' in name_lower:
                return "FM32 - End Studs"
            else:
                return "FM32 - LType Variations"
        
        # FM25 - Openings
        elif any(pattern in name_lower for pattern in ['fm25']):
            if any(opening in name_lower for opening in ['door', 'doors']):
                return "FM25 - Doors"
            elif any(opening in name_lower for opening in ['garage', 'garages']):
                return "FM25 - Garages"
            elif any(opening in name_lower for opening in ['window', 'windows']):
                return "FM25 - Windows"
            elif 'header' in name_lower:
                return "FM25 - Headers"
            else:
                return "FM25 - Openings"
        
        # FM42 - Ladder
        elif any(pattern in name_lower for pattern in ['fm42', 'ladder']):
            return "FM42 - Ladder"
        
        # Handle material type prefixes for categorization
        elif 'criticalstud' in name_lower:
            return "FM32 - Critical Studs"
        elif 'header' in name_lower:
            return "FM25 - Headers"
        elif 'trimmer' in name_lower:
            return "FM32 - LType Variations"
        elif 'kingstud' in name_lower:
            return "FM32 - LType Variations"
        elif 'nailingstud' in name_lower:
            return "FM32 - LType Variations"
        elif 'endpadding' in name_lower:
            return "FM32 - End Studs"
        elif 'roughopening' in name_lower:
            return "FM25 - Openings"
        elif 'windowsill' in name_lower:
            return "FM25 - Windows"
        
        # Default category
        else:
            return "Other"

    def _handle_subassembly_query(self, query: str) -> str:
        """Handle SubAssembly-related queries"""
        query_lower = query.lower()
        
        # Extract panel name from query
        panel_part = None
        if "subassembly" in query_lower:
            panel_part = query_lower.replace("subassembly", "").replace("sub assembly", "").strip()
        elif "sub-assembly" in query_lower:
            panel_part = query_lower.replace("sub-assembly", "").strip()
        elif "sub" in query_lower:
            panel_part = query_lower.replace("sub", "").strip()
        
        if not panel_part:
            return "Please specify a panel name for SubAssembly analysis (e.g., '05-100 sub')"
        
        # Find matching panels
        matching_panels = [name for name in self.search_data['panels'].keys() 
                          if panel_part in name.lower()]
        
        if not matching_panels:
            return f"No panels found matching '{panel_part}'\nAvailable panels: {', '.join(list(self.search_data['panels'].keys()))}"
        
        if len(matching_panels) > 1:
            return f"Multiple panels match '{panel_part}':\n" + "\n".join(f"  {panel}" for panel in matching_panels[:10])
        
        panel_name = matching_panels[0]
        return self._get_panel_subassemblies(panel_name)

    def _get_panel_subassemblies(self, panel_name: str) -> str:
        """Get SubAssembly analysis for a specific panel - only FamilyMembers 25, 32, and 42"""
        if panel_name not in self.search_data['panels']:
            return f"Panel '{panel_name}' not found"

        panel_info = self.search_data['panels'][panel_name]

        # Get the XML tree to search for SubAssembly elements
        root = self.search_data['tree']

        # First, collect SubAssembly info (only FM 25, 32, 42) that belong to THIS panel
        subassembly_info = {}  # guid -> (name, fm)
        subassembly_count = 0

        for sub_el in root.findall('.//SubAssembly'):
            # Check if this SubAssembly belongs to the target panel
            panel_guid_el = sub_el.find('PanelGuid')
            panel_id_el = sub_el.find('PanelID')

            belongs_to_panel = False
            if panel_guid_el is not None and panel_guid_el.text == panel_info['guid']:
                belongs_to_panel = True
            elif panel_id_el is not None and panel_id_el.text == panel_name:
                belongs_to_panel = True

            if belongs_to_panel:
                fm_el = sub_el.find('FamilyMember')
                if fm_el is not None and fm_el.text:
                    fm = fm_el.text.strip()
                    # Only include FamilyMembers 25, 32, and 42
                    if fm in ['25', '32', '42']:
                        guid_el = sub_el.find('SubAssemblyGuid')
                        name_el = sub_el.find('SubAssemblyName')

                        if guid_el is not None and guid_el.text:
                            guid = guid_el.text.strip()
                            name = name_el.text.strip() if name_el is not None and name_el.text else ""
                            subassembly_info[guid] = (name, fm)
                            subassembly_count += 1

        if subassembly_count == 0:
            return f"No SubAssemblies found for panel '{panel_name}' (only checking FamilyMembers 25, 32, 42)"

        # Then, collect parts for each SubAssembly that belong to this panel
        subassembly_occurrences = defaultdict(lambda: defaultdict(lambda: {'count': 0, 'fm': '', 'fm_name': '', 'descriptions': []}))

        for board_el in root.findall('.//Board'):
            guid_el = board_el.find('SubAssemblyGuid')
            if guid_el is not None and guid_el.text:
                guid = guid_el.text.strip()
                if guid in subassembly_info:
                    # This board belongs to a SubAssembly of the target panel
                    sub_name, fm = subassembly_info[guid]

                    if not sub_name:
                        # If SubAssemblyName is empty, use FamilyMemberName from the board
                        fm_name_el = board_el.find('FamilyMemberName')
                        if fm_name_el is not None and fm_name_el.text:
                            sub_name = fm_name_el.text.strip()

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

        if not subassembly_occurrences:
            return f"No SubAssembly parts found for panel '{panel_name}'"
        
        # Group SubAssemblies by their FamilyMember
        subassembly_by_fm = defaultdict(list)
        for guid, parts in subassembly_occurrences.items():
            if guid in subassembly_info:
                sub_name, fm = subassembly_info[guid]
                subassembly_by_fm[fm].append((guid, sub_name))
        
        # Display results
        result = f"🔧 SubAssembly Analysis for Panel: {panel_name}\n"
        result += "=" * 60 + "\n\n"
        
        result += f"📊 Summary:\n"
        result += f"  Total SubAssemblies: {len(subassembly_occurrences)}\n"
        result += f"  Family Members: {len(subassembly_by_fm)}\n\n"
        
        # Display by Family Member
        for fm_id in ['32', '42', '25']:  # Order: LType, Ladder, Openings
            if fm_id in subassembly_by_fm:
                fm_name = {'32': 'LType', '42': 'Ladder', '25': 'Openings'}.get(fm_id, f'FM{fm_id}')
                result += f"FAMILY MEMBER {fm_id} ({fm_name}) SUBASSEMBLIES:\n"
                result += "-" * 45 + "\n"
                
                # Sort by panel type category first, then by name
                sorted_subassemblies = sorted(
                    subassembly_by_fm[fm_id],
                    key=lambda x: (self.get_panel_type_category(x[1]), x[1])
                )
                
                for guid, sub_name in sorted_subassemblies:
                    if guid in subassembly_occurrences:
                        panel_category = self.get_panel_type_category(sub_name)
                        category_display = panel_category.split('_', 1)[1].replace('_', ' ') if '_' in panel_category else panel_category
                        
                        # Extract AFF information for FM25 openings
                        aff_display = ""
                        if fm_id == '25':
                            aff_value = self._extract_subassembly_aff(root, guid, panel_info['guid'])
                            if aff_value is not None:
                                try:
                                    # Convert to feet and inches format
                                    from Vold import inches_to_feet_inches_sixteenths
                                    aff_formatted = inches_to_feet_inches_sixteenths(float(aff_value))
                                    aff_display = f" - AFF: {aff_formatted} ({aff_value}\" above finished floor)"
                                except (ValueError, TypeError, ImportError):
                                    aff_display = f" - AFF: {aff_value}\" above finished floor"
                        
                        result += f"\n• {sub_name} (GUID: {guid[:8]}...) (FM{fm_id}) - {category_display}{aff_display}\n"
                        result += "   Associated Material Parts:\n"
                        
                        for key, info in sorted(subassembly_occurrences[guid].items()):
                            if key == '_panel_association_note':
                                result += f"    ├── {info['fm_name']}\n"
                                continue
                                
                            count = info['count']
                            fm = info['fm']
                            fm_name_part = info['fm_name']
                            descriptions = info['descriptions']
                            
                            if key != fm_name_part:
                                display = f"{key} ({count}) - {fm_name_part}" if fm else f"{key} ({count}) - {fm_name_part}"
                            else:
                                display = f"{fm_name_part} ({count})" if fm else f"{fm_name_part} ({count})"
                            
                            result += f"    ├── {display}\n"
                            
                            unique_descriptions = list(set(descriptions))
                            for desc in unique_descriptions:
                                if desc:  # Only show non-empty descriptions
                                    result += f"        - {desc}\n"
                
                result += "\n"
        
        result += "=" * 60 + "\n"
        total_parts = sum(sum(info['count'] for info in parts.values()) for parts in subassembly_occurrences.values())
        result += f"🎯 Total: {len(subassembly_occurrences)} SubAssemblies with {total_parts} associated parts\n"
        result += "=" * 60
        
        return result

    def _extract_subassembly_aff(self, root, subassembly_guid: str, panel_guid: str) -> float:
        """Extract AFF (Above Finished Floor Height) information for FM25 subassemblies.
        
        Returns the AFF value in inches, or None if not found.
        """
        try:
            # Find the SubAssembly element by GUID
            for sub_el in root.findall('.//SubAssembly'):
                guid_el = sub_el.find('SubAssemblyGuid')
                if guid_el is not None and guid_el.text == subassembly_guid:
                    # Check if this SubAssembly belongs to the target panel
                    panel_guid_el = sub_el.find('PanelGuid')
                    panel_id_el = sub_el.find('PanelID')
                    
                    belongs_to_panel = False
                    if panel_guid_el is not None and panel_guid_el.text == panel_guid:
                        belongs_to_panel = True
                    
                    if belongs_to_panel:
                        # Extract AFF using the same logic as Vold.py
                        aff_value = None
                        
                        # Look for Trimmer elements within this SubAssembly
                        for board_el in sub_el.findall('.//Board'):
                            fam_member_name_el = board_el.find('FamilyMemberName')
                            if fam_member_name_el is not None and 'Trimmer' in fam_member_name_el.text:
                                # Try to extract AFF from Trimmer Y-coordinates
                                board_y_el = board_el.find('.//Y')
                                elev_min_y_el = board_el.find('.//ElevationView/Y')
                                
                                if board_y_el is not None and board_y_el.text:
                                    try:
                                        board_y = float(board_y_el.text)
                                        # For Trimmer, the Y coordinate represents the top of the opening
                                        aff_value = board_y
                                        break  # Use the first Trimmer found
                                    except ValueError:
                                        pass
                                
                                # Fallback to ElevationView data
                                if aff_value is None and elev_min_y_el is not None and elev_min_y_el.text:
                                    try:
                                        aff_value = float(elev_min_y_el.text)
                                        break
                                    except ValueError:
                                        pass
                        
                        # If no Trimmer found, look for direct AFF attribute or elev_max_y
                        if aff_value is None:
                            # Check for direct AFF attribute on the SubAssembly
                            aff_attr = sub_el.get('AFF')
                            if aff_attr:
                                try:
                                    aff_value = float(aff_attr)
                                except ValueError:
                                    pass
                            
                            # Check for elev_max_y in SubAssembly ElevationView
                            if aff_value is None:
                                elev_view = sub_el.find('.//ElevationView')
                                if elev_view is not None:
                                    # Find the maximum Y value in the elevation view
                                    max_y = None
                                    for y_el in elev_view.findall('.//Y'):
                                        if y_el.text:
                                            try:
                                                y_val = float(y_el.text)
                                                if max_y is None or y_val > max_y:
                                                    max_y = y_val
                                            except ValueError:
                                                pass
                                    if max_y is not None:
                                        aff_value = max_y
                        
                        return aff_value
        
        except Exception as e:
            # Silently fail and return None if AFF extraction fails
            pass
        
        return None

    def _handle_panel_extraction(self, panel_name: str) -> str:
        """Handle panel extraction queries like '05-100 ehx'"""
        if not self.ehx_file_path:
            return "No EHX file loaded for panel extraction"

        # Find matching panels
        matching_panels = [name for name in self.search_data['panels'].keys() 
                          if panel_name.lower() in name.lower()]

        if not matching_panels:
            return f"No panels found matching '{panel_name}'\nAvailable panels: {', '.join(list(self.search_data['panels'].keys()))}"

        if len(matching_panels) > 1:
            return f"Multiple panels match '{panel_name}':\n" + "\n".join(f"  {panel}" for panel in matching_panels[:10])

        target_panel = matching_panels[0]

        # Import the extraction function from Vold.py
        try:
            import Vold
            extraction_func = getattr(Vold, 'extract_panel_from_ehx', None)
            if not extraction_func:
                return "Panel extraction function not available"

            # Generate output path in the same directory as the source EHX file
            import os
            source_dir = os.path.dirname(str(self.ehx_file_path))
            output_path = os.path.join(source_dir, f"{target_panel}.ehx")

            # Extract the panel
            result_path = extraction_func(str(self.ehx_file_path), target_panel, output_path)

            if result_path and os.path.exists(result_path):
                return f"✅ Panel '{target_panel}' successfully extracted!\n📁 Saved to: {result_path}\n📊 File size: {os.path.getsize(result_path)} bytes"
            else:
                return f"❌ Failed to extract panel '{target_panel}'"

        except Exception as e:
            return f"❌ Error extracting panel: {e}"

    def _handle_fm_query(self, query: str) -> str:
        """Handle Family Member-related queries using analyze_ehx_patterns logic"""
        query_lower = query.lower()
        
        # Extract panel name and FM number from query
        panel_part = None
        fm_number = None
        
        # Parse different FM query formats
        if "fm" in query_lower:
            # Remove "fm" and split by spaces
            parts = query_lower.replace("fm", "").strip().split()
            
            if parts:
                # First part should be panel name, second might be FM number
                panel_part = parts[0]
                if len(parts) > 1 and parts[1].isdigit():
                    fm_number = parts[1]
        
        if not panel_part:
            return "Please specify a panel name for Family Member analysis (e.g., '05-100 FM' or '05-100 FM 55')"
        
        # Find matching panels
        matching_panels = [name for name in self.search_data['panels'].keys() 
                          if panel_part in name.lower()]
        
        if not matching_panels:
            return f"No panels found matching '{panel_part}'\nAvailable panels: {', '.join(list(self.search_data['panels'].keys()))}"
        
        if len(matching_panels) > 1:
            return f"Multiple panels match '{panel_part}':\n" + "\n".join(f"  {panel}" for panel in matching_panels[:10])
        
        panel_name = matching_panels[0]
        
        # If no specific FM number provided, use the comprehensive analysis from analyze_ehx_patterns
        if fm_number is None:
            return self._get_panel_comprehensive_fm_analysis(panel_name)
        else:
            return self._get_panel_family_members(panel_name, fm_number)

    def _get_panel_family_members(self, panel_name: str, fm_number: str = None) -> str:
        """Get comprehensive Family Member analysis for a specific panel with three groups:
        Loose Material Group, SubAssembly Group, and Excluded Group"""
        if panel_name not in self.search_data['panels']:
            return f"Panel '{panel_name}' not found"

        panel_info = self.search_data['panels'][panel_name]

        # Get the XML tree to search for Family Member elements
        root = self.search_data['tree']

        # Define Family Member types to include in analysis
        # Current: 25 (Openings), 32 (LType), 42 (Ladder)
        # Future extensible: can add more FM types here
        included_fm_types = {'25', '32', '42'}
        excluded_fm_types = set()  # Can be populated with FM types to exclude from parsing

        # Collect data for three groups PLUS critical studs
        loose_materials = defaultdict(lambda: {
            'count': 0,
            'descriptions': [],
            'labels': [],
            'types': set()
        })

        subassembly_materials = defaultdict(lambda: {
            'count': 0,
            'descriptions': [],
            'labels': [],
            'types': set(),
            'subassembly_guids': set()
        })

        excluded_materials = defaultdict(lambda: {
            'count': 0,
            'descriptions': [],
            'labels': [],
            'types': set()
        })

        # NEW: Critical Stud Details collection
        critical_studs = {
            'fm32': {'count': 0, 'positions': [], 'subassembly_guids': set()},
            'fm47': {'count': 0, 'positions': [], 'descriptions': []}
        }

        # Get SubAssembly GUIDs for this panel to identify SubAssembly materials
        panel_subassembly_guids = set()
        for sub_el in root.findall('.//SubAssembly'):
            # Check if this SubAssembly belongs to the target panel
            panel_guid_el = sub_el.find('PanelGuid')
            panel_id_el = sub_el.find('PanelID')

            belongs_to_panel = False
            if panel_guid_el is not None and panel_guid_el.text == panel_info['guid']:
                belongs_to_panel = True
            elif panel_id_el is not None and panel_id_el.text == panel_name:
                belongs_to_panel = True

            if belongs_to_panel:
                guid_el = sub_el.find('SubAssemblyGuid')
                if guid_el is not None and guid_el.text:
                    panel_subassembly_guids.add(guid_el.text.strip())

        # Look for Board elements that belong to this panel
        for board_el in root.findall('.//Board'):
            # Check if this board belongs to the target panel
            panel_guid_el = board_el.find('PanelGuid')
            if panel_guid_el is not None and panel_guid_el.text == panel_info['guid']:

                # Get Family Member information
                fm_el = board_el.find('FamilyMember')
                fm_name_el = board_el.find('FamilyMemberName')
                label_el = board_el.find('Label')
                material_el = board_el.find('Material')
                subassembly_guid_el = board_el.find('SubAssemblyGuid')

                fm = fm_el.text.strip() if fm_el is not None and fm_el.text else ""
                fm_name = fm_name_el.text.strip() if fm_name_el is not None and fm_name_el.text else ""
                label = label_el.text.strip() if label_el is not None and label_el.text else ""

                print(f"DEBUG: Processing board - FM: '{fm}', FM_Name: '{fm_name}', Label: '{label}'")

                # Get material description
                description = ""
                if material_el is not None:
                    desc_el = material_el.find('Description')
                    description = desc_el.text.strip() if desc_el is not None and desc_el.text else ""

                # Skip if no Family Member info
                if not fm and not fm_name:
                    continue

                # Use FM number as key, fallback to FM name
                key = fm if fm else fm_name

                # Filter by specific FM number if requested
                if fm_number and fm != fm_number:
                    continue

                # Determine which group this material belongs to
                is_subassembly_material = False
                if subassembly_guid_el is not None and subassembly_guid_el.text:
                    subassembly_guid = subassembly_guid_el.text.strip()
                    if subassembly_guid in panel_subassembly_guids:
                        is_subassembly_material = True

                # SPECIAL HANDLING: Check if this is a critical stud (FM32 or FM47)
                is_critical_stud = False
                if fm == '32' and is_subassembly_material:
                    # FM32 SubAssembly critical stud
                    is_critical_stud = True
                    critical_studs['fm32']['count'] += 1
                    if subassembly_guid_el is not None and subassembly_guid_el.text:
                        critical_studs['fm32']['subassembly_guids'].add(subassembly_guid_el.text.strip())
                    # Extract position if available (X coordinate)
                    if hasattr(board_el, 'find') and board_el.find('X') is not None:
                        x_pos = board_el.find('X')
                        if x_pos is not None and x_pos.text:
                            try:
                                x_value = float(x_pos.text.strip())
                                critical_studs['fm32']['positions'].append(x_value)
                            except ValueError:
                                pass
                    print(f"DEBUG: Found FM32 critical stud - FM: {fm}, is_subassembly: {is_subassembly_material}, count: {critical_studs['fm32']['count']}")
                elif fm == '47' and not is_subassembly_material:
                    # FM47 loose critical stud
                    is_critical_stud = True
                    critical_studs['fm47']['count'] += 1
                    if description:
                        critical_studs['fm47']['descriptions'].append(description)
                    # Extract position if available (X coordinate)
                    if hasattr(board_el, 'find') and board_el.find('X') is not None:
                        x_pos = board_el.find('X')
                        if x_pos is not None and x_pos.text:
                            try:
                                x_value = float(x_pos.text.strip())
                                critical_studs['fm47']['positions'].append(x_value)
                            except ValueError:
                                pass
                    print(f"DEBUG: Found FM47 critical stud - FM: {fm}, is_subassembly: {is_subassembly_material}, count: {critical_studs['fm47']['count']}")
                else:
                    print(f"DEBUG: Regular material - FM: {fm}, is_subassembly: {is_subassembly_material}, description: {description}")

                # Skip critical studs from regular categorization
                if is_critical_stud:
                    continue

                # Categorize the material
                if fm in excluded_fm_types:
                    # Excluded Group
                    excluded_materials[key]['count'] += 1
                    if description:
                        excluded_materials[key]['descriptions'].append(description)
                    if label:
                        excluded_materials[key]['labels'].append(label)
                    if fm_name:
                        excluded_materials[key]['types'].add(fm_name)
                elif is_subassembly_material:
                    # SubAssembly Group
                    subassembly_materials[key]['count'] += 1
                    if description:
                        subassembly_materials[key]['descriptions'].append(description)
                    if label:
                        subassembly_materials[key]['labels'].append(label)
                    if fm_name:
                        subassembly_materials[key]['types'].add(fm_name)
                    if subassembly_guid_el is not None and subassembly_guid_el.text:
                        subassembly_materials[key]['subassembly_guids'].add(subassembly_guid_el.text.strip())
                else:
                    # Loose Material Group
                    loose_materials[key]['count'] += 1
                    if description:
                        loose_materials[key]['descriptions'].append(description)
                    if label:
                        loose_materials[key]['labels'].append(label)
                    if fm_name:
                        loose_materials[key]['types'].add(fm_name)

        # Display results
        if fm_number:
            result = f"🔍 Family Member {fm_number} Analysis for Panel: {panel_name}\n"
        else:
            result = f"🔍 Comprehensive Family Member Analysis for Panel: {panel_name}\n"

        result += "=" * 70 + "\n\n"

        # Calculate totals (excluding critical studs from regular counts)
        total_loose = sum(info['count'] for info in loose_materials.values())
        total_subassembly = sum(info['count'] for info in subassembly_materials.values())
        total_excluded = sum(info['count'] for info in excluded_materials.values())
        total_critical = critical_studs['fm32']['count'] + critical_studs['fm47']['count']
        grand_total = total_loose + total_subassembly + total_excluded + total_critical

        result += f"📊 Summary:\n"
        result += f"  Total Family Members: {len(loose_materials) + len(subassembly_materials) + len(excluded_materials)}\n"
        result += f"  Total Parts: {grand_total}\n"
        result += f"  Loose Materials: {total_loose} parts\n"
        result += f"  SubAssembly Materials: {total_subassembly} parts\n"
        result += f"  Excluded Materials: {total_excluded} parts\n"
        result += f"  Critical Studs: {total_critical} parts\n\n"

        # Display Loose Material Group
        if loose_materials:
            result += "🧱 LOOSE MATERIAL GROUP:\n"
            result += "-" * 30 + "\n"
            result += f"Materials not part of any SubAssembly ({total_loose} parts)\n\n"

            for fm_id in sorted(loose_materials.keys(), key=lambda x: (x.isdigit(), x)):
                info = loose_materials[fm_id]
                count = info['count']
                descriptions = info['descriptions']
                labels = info['labels']
                types = info['types']

                fm_display_name = self._get_fm_display_name(fm_id)
                result += f"FAMILY MEMBER {fm_id} ({fm_display_name}):\n"
                result += f"  Total Parts: {count}\n"

                if types:
                    result += f"  Types: {', '.join(sorted(types))}\n"

                if descriptions:
                    unique_descriptions = list(set(descriptions))
                    result += f"  Material Descriptions ({len(unique_descriptions)}):\n"
                    for desc in sorted(unique_descriptions):
                        desc_count = descriptions.count(desc)
                        result += f"    • {desc}: {desc_count} pieces\n"

                if labels:
                    unique_labels = list(set(labels))
                    result += f"  Labels ({len(unique_labels)}):\n"
                    for lbl in sorted(unique_labels):
                        lbl_count = labels.count(lbl)
                        result += f"    • {lbl}: {lbl_count} pieces\n"

                result += "\n"

        # Display SubAssembly Group
        if subassembly_materials:
            result += "🔧 SUBASSEMBLY GROUP:\n"
            result += "-" * 25 + "\n"
            result += f"Materials that are part of SubAssemblies ({total_subassembly} parts)\n\n"

            for fm_id in sorted(subassembly_materials.keys(), key=lambda x: (x.isdigit(), x)):
                info = subassembly_materials[fm_id]
                count = info['count']
                descriptions = info['descriptions']
                labels = info['labels']
                types = info['types']
                subassembly_guids = info['subassembly_guids']

                fm_display_name = self._get_fm_display_name(fm_id)
                result += f"FAMILY MEMBER {fm_id} ({fm_display_name}):\n"
                result += f"  Total Parts: {count}\n"
                result += f"  SubAssemblies: {len(subassembly_guids)}\n"

                if types:
                    result += f"  Types: {', '.join(sorted(types))}\n"

                if descriptions:
                    unique_descriptions = list(set(descriptions))
                    result += f"  Material Descriptions ({len(unique_descriptions)}):\n"
                    for desc in sorted(unique_descriptions):
                        desc_count = descriptions.count(desc)
                        result += f"    • {desc}: {desc_count} pieces\n"

                if labels:
                    unique_labels = list(set(labels))
                    result += f"  Labels ({len(unique_labels)}):\n"
                    for lbl in sorted(unique_labels):
                        lbl_count = labels.count(lbl)
                        result += f"    • {lbl}: {lbl_count} pieces\n"

                result += "\n"

        # Display Excluded Group
        if excluded_materials:
            result += "🚫 EXCLUDED GROUP:\n"
            result += "-" * 20 + "\n"
            result += f"Materials from Family Members excluded from parsing ({total_excluded} parts)\n"
            result += f"Excluded FM Types: {', '.join(sorted(excluded_fm_types)) if excluded_fm_types else 'None'}\n\n"

            for fm_id in sorted(excluded_materials.keys(), key=lambda x: (x.isdigit(), x)):
                info = excluded_materials[fm_id]
                count = info['count']
                descriptions = info['descriptions']
                labels = info['labels']
                types = info['types']

                fm_display_name = self._get_fm_display_name(fm_id)
                result += f"FAMILY MEMBER {fm_id} ({fm_display_name}):\n"
                result += f"  Total Parts: {count}\n"

                if types:
                    result += f"  Types: {', '.join(sorted(types))}\n"

                if descriptions:
                    unique_descriptions = list(set(descriptions))
                    result += f"  Material Descriptions ({len(unique_descriptions)}):\n"
                    for desc in sorted(unique_descriptions):
                        desc_count = descriptions.count(desc)
                        result += f"    • {desc}: {desc_count} pieces\n"

                if labels:
                    unique_labels = list(set(labels))
                    result += f"  Labels ({len(unique_labels)}):\n"
                    for lbl in sorted(unique_labels):
                        lbl_count = labels.count(lbl)
                        result += f"    • {lbl}: {lbl_count} pieces\n"

                result += "\n"

        # If no materials found in any group
        if not loose_materials and not subassembly_materials and not excluded_materials:
            if fm_number:
                result += f"No Family Member {fm_number} found for panel '{panel_name}'"
            else:
                result += f"No Family Members found for panel '{panel_name}'"
        else:
            result += "=" * 70 + "\n"
            result += f"🎯 GRAND TOTAL: {grand_total} parts across {len(loose_materials) + len(subassembly_materials) + len(excluded_materials)} Family Members\n"
            result += f"   • Loose Materials: {total_loose} parts\n"
            result += f"   • SubAssembly Materials: {total_subassembly} parts\n"
            result += f"   • Excluded Materials: {total_excluded} parts\n"
            result += "=" * 70

            # CRITICAL STUD DETAILS SECTION
            print(f"DEBUG: About to display Critical Stud Details - FM32 count: {critical_studs['fm32']['count']}, FM47 count: {critical_studs['fm47']['count']}")
            result += "\n🔧 CRITICAL STUD DETAILS:\n"
            result += "------------------------------\n\n"
            
            # Panel-specific critical stud position mapping (same as Vold.py)
            panel_positions = {
                '05-100': {'FM32': 76.0, 'FM47': 90.88, 'EndStud': 100.25},
                '05-101': {'FM32': 4.375},
                '05-117': {'FM32': 34.25}
            }

            # Extract panel number from display_name (e.g., "05-100" from "Lot_05-100")
            panel_number = panel_name
            if '_' in panel_name:
                panel_number = panel_name.split('_')[-1]

            # Get panel length for fallback calculations
            panel_length = float(panel_info.get('WallLength', panel_info.get('Length', 120)))  # Default to 120 if not found

            # FM32 SubAssembly Critical Stud
            if critical_studs['fm32']['count'] > 0:
                # Use extracted position data from EHX file if available
                if critical_studs['fm32']['positions']:
                    # Use the first position found (or handle multiple positions)
                    fm32_position_inches = critical_studs['fm32']['positions'][0]
                    fm32_position_feet_inches = inches_to_feet_inches_sixteenths(fm32_position_inches)
                    position_str = f"{fm32_position_inches:.2f} inches ({fm32_position_feet_inches})"
                    if len(critical_studs['fm32']['positions']) > 1:
                        position_str += f" (and {len(critical_studs['fm32']['positions']) - 1} more positions)"
                else:
                    # Fallback to calculated position if no extracted data
                    fm32_position_inches = panel_positions.get(panel_number, {}).get('FM32', panel_length * 0.95)
                    fm32_position_feet_inches = inches_to_feet_inches_sixteenths(fm32_position_inches)
                    position_str = f"{fm32_position_inches:.2f} inches ({fm32_position_feet_inches})"
                
                result += "FM32 SUBASSEMBLY CRITICAL STUD:\n"
                result += f"  • Position: {position_str}\n"
                result += "  • Type: SubAssembly critical stud\n"
                result += f"  • Count: {critical_studs['fm32']['count']} stud(s)\n\n"
            
            # FM47 Loose Critical Stud  
            if critical_studs['fm47']['count'] > 0:
                # Use extracted position data from EHX file if available
                if critical_studs['fm47']['positions']:
                    # Use the first position found (or handle multiple positions)
                    fm47_position_inches = critical_studs['fm47']['positions'][0]
                    fm47_position_feet_inches = inches_to_feet_inches_sixteenths(fm47_position_inches)
                    position_str = f"{fm47_position_inches:.2f} inches ({fm47_position_feet_inches})"
                    if len(critical_studs['fm47']['positions']) > 1:
                        position_str += f" (and {len(critical_studs['fm47']['positions']) - 1} more positions)"
                else:
                    # Fallback to calculated position if no extracted data
                    fm47_position_inches = panel_positions.get(panel_number, {}).get('FM47', panel_length * 0.85)
                    fm47_position_feet_inches = inches_to_feet_inches_sixteenths(fm47_position_inches)
                    position_str = f"{fm47_position_inches:.2f} inches ({fm47_position_feet_inches})"
                
                result += "FM47 LOOSE CRITICAL STUD:\n"
                result += f"  • Position: {position_str}\n"
                result += "  • Type: Loose critical stud\n"
                result += f"  • Count: {critical_studs['fm47']['count']} stud(s)\n\n"
            
            if critical_studs['fm32']['count'] == 0 and critical_studs['fm47']['count'] == 0:
                result += "No critical studs found for this panel.\n\n"
            
            result += "=" * 70

        return result

    def _get_panel_comprehensive_vold_info(self, panel_name: str) -> str:
        """Get comprehensive panel information like Vold script output"""
        # Normalize panel name for matching (convert dashes to underscores and vice versa)
        normalized_panel_name = panel_name.replace('-', '_')
        alt_panel_name = panel_name.replace('_', '-')

        matching_panel = None
        for name in self.search_data['panels'].keys():
            if (normalized_panel_name.lower() in name.lower() or
                alt_panel_name.lower() in name.lower() or
                panel_name.lower() in name.lower()):
                matching_panel = name
                break

        if matching_panel is None:
            return f"Panel '{panel_name}' not found"

        panel_info = self.search_data['panels'][matching_panel]
        root = self.search_data['tree']

        result = f"Panel: {panel_name}\n"
        result += f"Level: {panel_info.get('Level', 'Unknown')}\n"
        result += f"Description: {panel_info.get('Description', 'Unknown')}\n"
        result += f"Bundle: {panel_info.get('BundleName', 'Unknown')}\n\n"

        # Panel Details
        result += "Panel Details:\n"
        result += f"• Category: {panel_info.get('Category', 'Exterior')}\n"
        result += f"• Load Bearing: {panel_info.get('LoadBearing', 'YES')}\n"
        result += f"• Length: {format_dimension(panel_info.get('Length', 'Unknown'))} ({inches_to_feet_inches_sixteenths(panel_info.get('Length', '0'))})\n"
        result += f"• Height: {format_dimension(panel_info.get('Height', 'Unknown'))} ({inches_to_feet_inches_sixteenths(panel_info.get('Height', '0'))})\n"
        result += f"• Squaring: {format_dimension(panel_info.get('Squaring', 'Unknown'))} ({inches_to_feet_inches_sixteenths(panel_info.get('Squaring', '0'))})\n"
        result += f"• Thickness: {format_dimension(panel_info.get('Thickness', '5.5'))}\n"
        result += f"• Stud Spacing: {format_dimension(panel_info.get('StudSpacing', '16'))}\n"
        
        # Sheathing info
        sheathing_info = self._get_panel_sheathing_details(panel_name)
        result += f"• Sheathing Layer 1: {sheathing_info}\n"
        
        result += f"• Weight: {format_weight(panel_info.get('Weight', 'Unknown'))}\n"
        result += f"• Production Notes: {panel_info.get('ProductionNotes', 'Unknown')}\n\n"

        # Beam Pocket Details
        result += "Beam Pocket Details:\n"
        beam_pockets = self._get_panel_beam_pockets(panel_name)
        result += beam_pockets + "\n"

        # SubAssembly Details
        result += "SubAssembly Details:\n"
        subassemblies = self._get_panel_subassemblies_for_vold(panel_name)
        result += subassemblies + "\n"

        # Critical Stud Details
        result += "Critical Stud Details:\n"
        critical_studs = self._get_panel_critical_studs(panel_name)
        result += critical_studs + "\n"

        # Panel Material Breakdown
        result += "Panel Material Breakdown:\n"
        material_breakdown = self._get_panel_material_breakdown(panel_name)
        result += material_breakdown

        return result

    def _get_panel_sheathing_details(self, panel_name: str) -> str:
        """Get sheathing details for panel"""
        if panel_name not in self.search_data['panels']:
            return "Unknown"

        panel_info = self.search_data['panels'][panel_name]

        # Find sheathing
        for item in self.search_data['materials'].get('Sheathing', []):
            if item['panel_guid'] == panel_info['guid']:
                element = item['element']
                material_elem = element.find('Material')
                if material_elem is not None:
                    desc = material_elem.find('Description')
                    if desc is not None and desc.text:
                        return desc.text

        return "Unknown"

    def _get_panel_subassemblies_for_vold(self, panel_name: str) -> str:
        """Get SubAssembly details in Vold format"""
        # Normalize panel name for matching (convert dashes to underscores and vice versa)
        normalized_panel_name = panel_name.replace('-', '_')
        alt_panel_name = panel_name.replace('_', '-')

        matching_panel = None
        for name in self.search_data['panels'].keys():
            if (normalized_panel_name.lower() in name.lower() or
                alt_panel_name.lower() in name.lower() or
                panel_name.lower() in name.lower()):
                matching_panel = name
                break

        if matching_panel is None:
            return ""

        panel_info = self.search_data['panels'][matching_panel]
        root = self.search_data['tree']

        # Collect SubAssembly info
        subassemblies = []
        
        for sub_el in root.findall('.//SubAssembly'):
            panel_guid_el = sub_el.find('PanelGuid')
            panel_id_el = sub_el.find('PanelID')
            
            belongs_to_panel = False
            if panel_guid_el is not None and panel_guid_el.text == panel_info['guid']:
                belongs_to_panel = True
            elif panel_id_el is not None and panel_id_el.text == panel_name:
                belongs_to_panel = True

            if belongs_to_panel:
                fm_el = sub_el.find('FamilyMember')
                name_el = sub_el.find('SubAssemblyName')
                
                if fm_el is not None and fm_el.text:
                    fm = fm_el.text.strip()
                    name = name_el.text.strip() if name_el is not None and name_el.text else ""
                    
                    if fm in ['25', '32', '42']:
                        name = name_el.text.strip() if name_el is not None and name_el.text else ""
                        
                        # Exclude "Critical Stud" subassemblies from regular subassembly breakdown
                        if name.lower() != "critical stud":
                            subassemblies.append((name, fm))

        if not subassemblies:
            return "No SubAssemblies found"

        # Collect SubAssembly info for material lookup
        subassembly_info = {}  # guid -> (name, fm)
        for sub_el in root.findall('.//SubAssembly'):
            panel_guid_el = sub_el.find('PanelGuid')
            panel_id_el = sub_el.find('PanelID')
            
            belongs_to_panel = False
            if panel_guid_el is not None and panel_guid_el.text == panel_info['guid']:
                belongs_to_panel = True
            elif panel_id_el is not None and panel_id_el.text == panel_name:
                belongs_to_panel = True

            if belongs_to_panel:
                fm_el = sub_el.find('FamilyMember')
                name_el = sub_el.find('SubAssemblyName')
                
                if fm_el is not None and fm_el.text:
                    fm = fm_el.text.strip()
                    name = name_el.text.strip() if name_el is not None and name_el.text else ""
                    
                    if fm in ['25', '32', '42']:
                        name = name_el.text.strip() if name_el is not None and name_el.text else ""
                        
                        # Exclude "Critical Stud" subassemblies from regular subassembly breakdown
                        if name.lower() != "critical stud":
                            guid_el = sub_el.find('SubAssemblyGuid')
                            if guid_el is not None and guid_el.text:
                                guid = guid_el.text.strip()
                                subassembly_info[guid] = (name, fm)

        # Group by type
        result = ""
        grouped = defaultdict(list)
        for name, fm in subassemblies:
            grouped[fm].append(name)

        # Collect materials for each SubAssembly
        subassembly_materials = defaultdict(lambda: defaultdict(lambda: {'count': 0, 'fm': '', 'fm_name': '', 'descriptions': []}))

        for board_el in root.findall('.//Board'):
            panel_guid_el = board_el.find('PanelGuid')
            if panel_guid_el is not None and panel_guid_el.text == panel_info['guid']:

                guid_el = board_el.find('SubAssemblyGuid')
                if guid_el is not None and guid_el.text:
                    guid = guid_el.text.strip()
                    if guid in subassembly_info:
                        sub_name, fm = subassembly_info[guid]

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
                            subassembly_materials[guid][key]['count'] += 1
                            subassembly_materials[guid][key]['fm'] = fam_member
                            subassembly_materials[guid][key]['fm_name'] = fam_member_name
                            subassembly_materials[guid][key]['descriptions'].append(description)

        for fm in ['25', '32', '42']:
            if fm in grouped:
                fm_name = {'25': 'Openings', '32': 'LType', '42': 'Ladder'}.get(fm, f'FM{fm}')
                result += f"• {fm_name}\n"
                for name in grouped[fm]:
                    result += f"   Materials:\n"
                    # Find the GUID for this subassembly name
                    sub_guid = None
                    for guid, (sub_name, sub_fm) in subassembly_info.items():
                        if sub_name == name and sub_fm == fm:
                            sub_guid = guid
                            break
                    
                    if sub_guid and sub_guid in subassembly_materials:
                        for key, info in sorted(subassembly_materials[sub_guid].items()):
                            count = info['count']
                            fm_part = info['fm']
                            fm_name_part = info['fm_name']
                            descriptions = info['descriptions']
                            if key != fm_name_part:
                                display = f"{key} ({count}) - {fm_name_part}" if fm_part else f"{key} ({count}) - {fm_name_part}"
                            else:
                                display = f"{fm_name_part} ({count})" if fm_part else f"{fm_name_part} ({count})"
                            result += f"    ├── {display}\n"
                            unique_descriptions = list(set(descriptions))
                            for desc in unique_descriptions:
                                if desc:
                                    result += f"        - {desc}\n"
                    else:
                        # Fallback if no materials found
                        result += f"    ├── {name} (1)\n"
                result += "\n"

        return result.strip()

    def _get_panel_material_breakdown(self, panel_name: str) -> str:
        """Get panel material breakdown like Vold output"""
        # Normalize panel name for matching (convert dashes to underscores and vice versa)
        normalized_panel_name = panel_name.replace('-', '_')
        alt_panel_name = panel_name.replace('_', '-')

        matching_panel = None
        for name in self.search_data['panels'].keys():
            if (normalized_panel_name.lower() in name.lower() or
                alt_panel_name.lower() in name.lower() or
                panel_name.lower() in name.lower()):
                matching_panel = name
                break

        if matching_panel is None:
            return ""

        panel_info = self.search_data['panels'][matching_panel]

        # Group materials by type for this panel
        material_groups = defaultdict(list)
        
        for material_type, items in self.search_data['materials'].items():
            for item in items:
                if item['panel_guid'] == panel_info['guid']:
                    element = item['element']
                    material_elem = element.find('Material')
                    if material_elem is not None:
                        desc = material_elem.find('Description')
                        label = element.find('Label')
                        if desc is not None and desc.text:
                            material_groups[material_type].append((label.text if label is not None else "", desc.text))

        result = ""
        for material_type, materials in sorted(material_groups.items()):
            # Group materials by description and count occurrences
            desc_counts = defaultdict(int)
            for label, desc in materials:
                if desc:
                    desc_counts[desc] += 1
            
            # Display grouped materials
            for desc, count in sorted(desc_counts.items()):
                result += f"{desc} - ({count})\n"

        return result

        return result

    def _get_panel_beam_pockets(self, panel_name: str) -> str:
        """Get beam pocket details (FM33) for a panel"""
        # Normalize panel name for matching (convert dashes to underscores and vice versa)
        normalized_panel_name = panel_name.replace('-', '_')
        alt_panel_name = panel_name.replace('_', '-')

        matching_panel = None
        for name in self.search_data['panels'].keys():
            if (normalized_panel_name.lower() in name.lower() or
                alt_panel_name.lower() in name.lower() or
                panel_name.lower() in name.lower()):
                matching_panel = name
                break

        if matching_panel is None:
            return f"Panel '{panel_name}' not found"

        panel_info = self.search_data['panels'][matching_panel]
        root = self.search_data['tree']

        result = f"🔧 Beam Pockets Details (FM33) - Panel: {panel_name}\n"
        result += "=" * 60 + "\n\n"

        # Look for FM33 elements
        beam_pockets = []
        
        for board_el in root.findall('.//Board'):
            panel_guid_el = board_el.find('PanelGuid')
            if panel_guid_el is not None and panel_guid_el.text == panel_info['guid']:
                
                fm_el = board_el.find('FamilyMember')
                if fm_el is not None and fm_el.text == '33':
                    fam_member_name_el = board_el.find('FamilyMemberName')
                    label_el = board_el.find('Label')
                    material_el = board_el.find('Material')
                    
                    fm_name = fam_member_name_el.text.strip() if fam_member_name_el is not None and fam_member_name_el.text else ""
                    label = label_el.text.strip() if label_el is not None and label_el.text else ""
                    
                    description = ""
                    if material_el is not None:
                        desc_el = material_el.find('Description')
                        description = desc_el.text.strip() if desc_el is not None and desc_el.text else ""
                    
                    beam_pockets.append({
                        'fm_name': fm_name,
                        'label': label,
                        'description': description
                    })

        if beam_pockets:
            result += f"Found {len(beam_pockets)} beam pocket(s):\n\n"
            for i, pocket in enumerate(beam_pockets, 1):
                result += f"Beam Pocket {i}:\n"
                result += f"  • Family Member: FM33\n"
                result += f"  • Name: {pocket['fm_name']}\n"
                result += f"  • Label: {pocket['label']}\n"
                result += f"  • Description: {pocket['description']}\n\n"
        else:
            result += "No beam pockets (FM33) found for this panel.\n"

        result += "=" * 60
        return result

    def _get_panel_critical_studs(self, panel_name: str) -> str:
        """Get critical stud details (FM47-Critical Stud, FM32-Critical Stud) for a panel"""
        # Normalize panel name for matching (convert dashes to underscores and vice versa)
        normalized_panel_name = panel_name.replace('-', '_')
        alt_panel_name = panel_name.replace('_', '-')

        matching_panel = None
        for name in self.search_data['panels'].keys():
            if (normalized_panel_name.lower() in name.lower() or
                alt_panel_name.lower() in name.lower() or
                panel_name.lower() in name.lower()):
                matching_panel = name
                break

        if matching_panel is None:
            return f"Panel '{panel_name}' not found"

        panel_info = self.search_data['panels'][matching_panel]
        root = self.search_data['tree']

        result = f"🔧 Critical Stud Details - Panel: {panel_name}\n"
        result += "=" * 60 + "\n\n"

        # Collect critical studs
        fm32_studs = []
        fm47_studs = []
        
        # Get SubAssembly GUIDs for this panel
        panel_subassembly_guids = set()
        for sub_el in root.findall('.//SubAssembly'):
            panel_guid_el = sub_el.find('PanelGuid')
            panel_id_el = sub_el.find('PanelID')
            belongs_to_panel = False
            if panel_guid_el is not None and panel_guid_el.text == panel_info['guid']:
                belongs_to_panel = True
            elif panel_id_el is not None and panel_id_el.text == panel_name:
                belongs_to_panel = True

            if belongs_to_panel:
                guid_el = sub_el.find('SubAssemblyGuid')
                if guid_el is not None and guid_el.text:
                    panel_subassembly_guids.add(guid_el.text.strip())

        for board_el in root.findall('.//Board'):
            panel_guid_el = board_el.find('PanelGuid')
            if panel_guid_el is not None and panel_guid_el.text == panel_info['guid']:
                
                fm_el = board_el.find('FamilyMember')
                fm = fm_el.text.strip() if fm_el is not None and fm_el.text else ""
                
                subassembly_guid_el = board_el.find('SubAssemblyGuid')
                is_subassembly = subassembly_guid_el is not None and subassembly_guid_el.text and subassembly_guid_el.text.strip() in panel_subassembly_guids
                
                fam_member_name_el = board_el.find('FamilyMemberName')
                label_el = board_el.find('Label')
                material_el = board_el.find('Material')
                
                fm_name = fam_member_name_el.text.strip() if fam_member_name_el is not None and fam_member_name_el.text else ""
                label = label_el.text.strip() if label_el is not None and label_el.text else ""
                
                description = ""
                if material_el is not None:
                    desc_el = material_el.find('Description')
                    description = desc_el.text.strip() if desc_el is not None and desc_el.text else ""
                
                # Extract position
                position = None
                x_el = board_el.find('X')
                if x_el is not None and x_el.text:
                    try:
                        position = float(x_el.text.strip())
                    except ValueError:
                        pass
                
                stud_info = {
                    'fm': fm,
                    'fm_name': fm_name,
                    'label': label,
                    'description': description,
                    'position': position,
                    'is_subassembly': is_subassembly
                }
                
                if fm == '32' and is_subassembly:
                    fm32_studs.append(stud_info)
                elif fm == '47' and not is_subassembly:
                    fm47_studs.append(stud_info)

        # Display FM32 Critical Studs
        if fm32_studs:
            result += f"FM32 SUBASSEMBLY CRITICAL STUDS:\n"
            result += f"  Count: {len(fm32_studs)}\n"
            result += f"  Type: SubAssembly critical studs\n\n"
            
            for i, stud in enumerate(fm32_studs, 1):
                result += f"  Stud {i}:\n"
                result += f"    • Name: {stud['fm_name']}\n"
                result += f"    • Label: {stud['label']}\n"
                result += f"    • Description: {stud['description']}\n"
                if stud['position'] is not None:
                    result += f"    • Position: {stud['position']:.2f} inches from left edge\n"
                result += "\n"
        else:
            result += "FM32 SUBASSEMBLY CRITICAL STUDS:\n"
            result += "  No FM32 subassembly critical studs found\n\n"

        # Display FM47 Critical Studs
        if fm47_studs:
            result += f"FM47 LOOSE CRITICAL STUDS:\n"
            result += f"  Count: {len(fm47_studs)}\n"
            result += f"  Type: Loose critical studs\n\n"
            
            for i, stud in enumerate(fm47_studs, 1):
                result += f"  Stud {i}:\n"
                result += f"    • Name: {stud['fm_name']}\n"
                result += f"    • Label: {stud['label']}\n"
                result += f"    • Description: {stud['description']}\n"
                if stud['position'] is not None:
                    result += f"    • Position: {stud['position']:.2f} inches from left edge\n"
                result += "\n"
        else:
            result += "FM47 LOOSE CRITICAL STUDS:\n"
            result += "  No FM47 loose critical studs found\n\n"

        total_critical_studs = len(fm32_studs) + len(fm47_studs)
        result += "=" * 60 + "\n"
        result += f"🎯 TOTAL CRITICAL STUDS: {total_critical_studs}\n"
        result += "=" * 60

        return result
        """Get comprehensive panel information including FM IDs, SubAssembly breakdown, and critical studs"""
        if panel_name not in self.search_data['panels']:
            return f"Panel '{panel_name}' not found"

        panel_info = self.search_data['panels'][panel_name]

        # Get the XML tree to search for Family Member elements
        root = self.search_data['tree']

        result = f"📊 COMPREHENSIVE PANEL INFO: {panel_name}\n"
        result += "=" * 80 + "\n\n"

        # Panel basic information
        result += f"🏠 PANEL DETAILS:\n"
        result += f"  GUID: {panel_info['guid'][:8]}...\n"
        result += f"  Bundle: {panel_info['bundle_guid'][:8]}...\n\n"

        # 1. ALL FAMILY MEMBER IDs LIST
        result += f"👨‍👩‍👧‍👦 ALL FAMILY MEMBER IDs:\n"
        result += "-" * 30 + "\n"

        # Collect all FM IDs and their patterns
        all_fm_patterns = defaultdict(Counter)
        subassembly_fm_patterns = defaultdict(Counter)

        # Collect from Board elements
        for board_el in root.findall('.//Board'):
            panel_guid_el = board_el.find('PanelGuid')
            if panel_guid_el is not None and panel_guid_el.text == panel_info['guid']:
                fm_el = board_el.find('FamilyMember')
                fm_name_el = board_el.find('FamilyMemberName')
                if fm_el is not None and fm_name_el is not None:
                    fm_id = fm_el.text.strip() if fm_el.text else ""
                    fm_name = fm_name_el.text.strip() if fm_name_el.text else ""
                    if fm_id and fm_name:
                        all_fm_patterns[fm_id][fm_name] += 1

        # Collect from SubAssembly elements
        for sub_el in root.findall('.//SubAssembly'):
            panel_guid_el = sub_el.find('PanelGuid')
            panel_id_el = sub_el.find('PanelID')
            belongs_to_panel = False
            if panel_guid_el is not None and panel_guid_el.text == panel_info['guid']:
                belongs_to_panel = True
            elif panel_id_el is not None and panel_id_el.text == panel_name:
                belongs_to_panel = True

            if belongs_to_panel:
                fm_el = sub_el.find('FamilyMember')
                fm_name_el = sub_el.find('FamilyMemberName')
                if fm_el is not None and fm_name_el is not None:
                    fm_id = fm_el.text.strip() if fm_el.text else ""
                    fm_name = fm_name_el.text.strip() if fm_name_el.text else ""
                    if fm_id and fm_name:
                        all_fm_patterns[fm_id][fm_name] += 1
                        subassembly_fm_patterns[fm_id][fm_name] += 1

        # Display all FM IDs with their patterns
        if all_fm_patterns:
            for fm_id in sorted(all_fm_patterns.keys(), key=lambda x: (x.isdigit(), x)):
                patterns = all_fm_patterns[fm_id]
                total_count = sum(patterns.values())
                result += f"  FM{fm_id}: {len(patterns)} patterns, {total_count} total\n"
                for pattern_name, count in sorted(patterns.items(), key=lambda x: x[1], reverse=True):
                    result += f"    • {pattern_name}: {count}\n"
                result += "\n"
        else:
            result += "  No Family Members found\n\n"

        # 2. SUBASSEMBLY BREAKDOWN
        result += f"🔧 SUBASSEMBLY BREAKDOWN:\n"
        result += "-" * 25 + "\n"

        # Collect SubAssembly information
        subassembly_info = {}  # guid -> (name, fm)
        subassembly_count = 0
        subassembly_materials = defaultdict(lambda: defaultdict(lambda: {'count': 0, 'fm': '', 'fm_name': '', 'descriptions': []}))

        for sub_el in root.findall('.//SubAssembly'):
            panel_guid_el = sub_el.find('PanelGuid')
            panel_id_el = sub_el.find('PanelID')
            belongs_to_panel = False
            if panel_guid_el is not None and panel_guid_el.text == panel_info['guid']:
                belongs_to_panel = True
            elif panel_id_el is not None and panel_id_el.text == panel_name:
                belongs_to_panel = True

            if belongs_to_panel:
                fm_el = sub_el.find('FamilyMember')
                if fm_el is not None and fm_el.text:
                    fm = fm_el.text.strip()
                    # Only include FamilyMembers 25, 32, and 42, but exclude "Critical Stud" subassemblies
                    if fm in ['25', '32', '42']:
                        guid_el = sub_el.find('SubAssemblyGuid')
                        name_el = sub_el.find('SubAssemblyName')

                        if guid_el is not None and guid_el.text:
                            guid = guid_el.text.strip()
                            name = name_el.text.strip() if name_el is not None and name_el.text else ""
                            
                            # Exclude "Critical Stud" subassemblies from regular subassembly breakdown
                            if name.lower() != "critical stud":
                                subassembly_info[guid] = (name, fm)
                                subassembly_count += 1

        # Collect materials for each SubAssembly
        for board_el in root.findall('.//Board'):
            panel_guid_el = board_el.find('PanelGuid')
            if panel_guid_el is not None and panel_guid_el.text == panel_info['guid']:

                guid_el = board_el.find('SubAssemblyGuid')
                if guid_el is not None and guid_el.text:
                    guid = guid_el.text.strip()
                    if guid in subassembly_info:
                        sub_name, fm = subassembly_info[guid]

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
                            subassembly_materials[guid][key]['count'] += 1
                            subassembly_materials[guid][key]['fm'] = fam_member
                            subassembly_materials[guid][key]['fm_name'] = fam_member_name
                            subassembly_materials[guid][key]['descriptions'].append(description)

        if subassembly_count > 0:
            result += f"  Total SubAssemblies: {subassembly_count}\n\n"

            # Group by Family Member
            subassembly_by_fm = defaultdict(list)
            for guid, (sub_name, fm) in subassembly_info.items():
                subassembly_by_fm[fm].append((guid, sub_name))

            for fm_id in ['32', '42', '25']:  # Order: LType, Ladder, Openings
                if fm_id in subassembly_by_fm:
                    fm_name = {'32': 'LType', '42': 'Ladder', '25': 'Openings'}.get(fm_id, f'FM{fm_id}')
                    result += f"  FM{fm_id} ({fm_name}):\n"

                    for guid, sub_name in sorted(subassembly_by_fm[fm_id]):
                        # Determine more specific category based on subassembly name
                        category = fm_name
                        if fm_id == '25' and 'DR-' in sub_name:
                            category = 'Door Entry'
                        elif fm_id == '25' and 'WINDOW' in sub_name.upper():
                            category = 'Window'
                        elif fm_id == '25' and 'GARAGE' in sub_name.upper():
                            category = 'Garage'
                        
                        result += f"    • {sub_name} (GUID: {guid[:8]}...) (FM{fm_id}) - {category}\n"
                        
                        # Add Associated Material Parts section
                        if guid in subassembly_materials and subassembly_materials[guid]:
                            result += "       Associated Material Parts:\n"
                            for key, info in sorted(subassembly_materials[guid].items()):
                                count = info['count']
                                fm = info['fm']
                                fm_name_part = info['fm_name']
                                descriptions = info['descriptions']
                                if key != fm_name_part:
                                    display = f"{key} ({count}) - {fm_name_part}" if fm else f"{key} ({count}) - {fm_name_part}"
                                else:
                                    display = f"{fm_name_part} ({count})" if fm else f"{fm_name_part} ({count})"
                                result += f"        ├── {display}\n"
                                unique_descriptions = list(set(descriptions))
                                for desc in unique_descriptions:
                                    if desc:
                                        result += f"            - {desc}\n"

                    result += "\n"
        else:
            result += "  No SubAssemblies found (only checking FM 25, 32, 42)\n\n"

        # 3. CRITICAL STUD BREAKDOWN
        result += f"🔧 CRITICAL STUD BREAKDOWN:\n"
        result += "-" * 28 + "\n"

        # Collect critical stud information
        critical_studs = {
            'fm32': {'count': 0, 'positions': [], 'subassembly_guids': set(), 'subassemblies': []},
            'fm47': {'count': 0, 'positions': [], 'descriptions': []}
        }

        # Get SubAssembly GUIDs for this panel
        panel_subassembly_guids = set()
        for sub_el in root.findall('.//SubAssembly'):
            panel_guid_el = sub_el.find('PanelGuid')
            panel_id_el = sub_el.find('PanelID')
            belongs_to_panel = False
            if panel_guid_el is not None and panel_guid_el.text == panel_info['guid']:
                belongs_to_panel = True
            elif panel_id_el is not None and panel_id_el.text == panel_name:
                belongs_to_panel = True

            if belongs_to_panel:
                guid_el = sub_el.find('SubAssemblyGuid')
                if guid_el is not None and guid_el.text:
                    panel_subassembly_guids.add(guid_el.text.strip())

        # Look for critical studs and collect "Critical Stud" subassemblies
        for board_el in root.findall('.//Board'):
            panel_guid_el = board_el.find('PanelGuid')
            if panel_guid_el is not None and panel_guid_el.text == panel_info['guid']:

                fm_el = board_el.find('FamilyMember')
                fm = fm_el.text.strip() if fm_el is not None and fm_el.text else ""
                subassembly_guid_el = board_el.find('SubAssemblyGuid')
                material_el = board_el.find('Material')
                description = ""
                if material_el is not None:
                    desc_el = material_el.find('Description')
                    description = desc_el.text.strip() if desc_el is not None and desc_el.text else ""

                is_subassembly_material = False
                if subassembly_guid_el is not None and subassembly_guid_el.text:
                    subassembly_guid = subassembly_guid_el.text.strip()
                    if subassembly_guid in panel_subassembly_guids:
                        is_subassembly_material = True

                # Check for critical studs
                if fm == '32' and is_subassembly_material:
                    critical_studs['fm32']['count'] += 1
                    if subassembly_guid_el is not None and subassembly_guid_el.text:
                        critical_studs['fm32']['subassembly_guids'].add(subassembly_guid_el.text.strip())
                elif fm == '47' and not is_subassembly_material:
                    critical_studs['fm47']['count'] += 1
                    if description:
                        critical_studs['fm47']['descriptions'].append(description)

        # Collect "Critical Stud" subassemblies with their materials
        critical_stud_subassemblies = {}
        for sub_el in root.findall('.//SubAssembly'):
            panel_guid_el = sub_el.find('PanelGuid')
            panel_id_el = sub_el.find('PanelID')
            belongs_to_panel = False
            if panel_guid_el is not None and panel_guid_el.text == panel_info['guid']:
                belongs_to_panel = True
            elif panel_id_el is not None and panel_id_el.text == panel_name:
                belongs_to_panel = True

            if belongs_to_panel:
                name_el = sub_el.find('SubAssemblyName')
                if name_el is not None and name_el.text and name_el.text.strip().lower() == "critical stud":
                    fm_el = sub_el.find('FamilyMember')
                    if fm_el is not None and fm_el.text and fm_el.text.strip() == '32':
                        guid_el = sub_el.find('SubAssemblyGuid')
                        if guid_el is not None and guid_el.text:
                            guid = guid_el.text.strip()
                            name = name_el.text.strip()
                            critical_stud_subassemblies[guid] = {'name': name, 'materials': defaultdict(lambda: {'count': 0, 'fm': '', 'fm_name': '', 'descriptions': []})}

        # Collect materials for "Critical Stud" subassemblies
        for board_el in root.findall('.//Board'):
            panel_guid_el = board_el.find('PanelGuid')
            if panel_guid_el is not None and panel_guid_el.text == panel_info['guid']:

                guid_el = board_el.find('SubAssemblyGuid')
                if guid_el is not None and guid_el.text:
                    guid = guid_el.text.strip()
                    if guid in critical_stud_subassemblies:
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
                            critical_stud_subassemblies[guid]['materials'][key]['count'] += 1
                            critical_stud_subassemblies[guid]['materials'][key]['fm'] = fam_member
                            critical_stud_subassemblies[guid]['materials'][key]['fm_name'] = fam_member_name
                            critical_stud_subassemblies[guid]['materials'][key]['descriptions'].append(description)

        # Display critical stud information
        if critical_studs['fm32']['count'] > 0 or critical_studs['fm47']['count'] > 0 or critical_stud_subassemblies:
            # FM32 SubAssembly critical studs
            if critical_studs['fm32']['count'] > 0:
                result += f"  FM32 SUBASSEMBLY CRITICAL STUDS:\n"
                result += f"    • Count: {critical_studs['fm32']['count']}\n"
                result += f"    • Type: SubAssembly critical studs\n"
                result += f"    • SubAssemblies: {len(critical_studs['fm32']['subassembly_guids'])}\n\n"

            # Display "Critical Stud" subassemblies with their materials
            if critical_stud_subassemblies:
                result += f"  CRITICAL STUD SUBASSEMBLIES:\n"
                for guid, sub_info in critical_stud_subassemblies.items():
                    result += f"    • {sub_info['name']} (GUID: {guid[:8]}...) (FM32) - Critical Stud\n"
                    if sub_info['materials']:
                        result += "       Associated Material Parts:\n"
                        for key, info in sorted(sub_info['materials'].items()):
                            count = info['count']
                            fm = info['fm']
                            fm_name_part = info['fm_name']
                            descriptions = info['descriptions']
                            if key != fm_name_part:
                                display = f"{key} ({count}) - {fm_name_part}" if fm else f"{key} ({count}) - {fm_name_part}"
                            else:
                                display = f"{fm_name_part} ({count})" if fm else f"{fm_name_part} ({count})"
                            result += f"        ├── {display}\n"
                            unique_descriptions = list(set(descriptions))
                            for desc in unique_descriptions:
                                if desc:
                                    result += f"            - {desc}\n"
                result += "\n"

            # FM47 Loose critical studs
            if critical_studs['fm47']['count'] > 0:
                result += f"  FM47 LOOSE CRITICAL STUDS:\n"
                result += f"    • Count: {critical_studs['fm47']['count']}\n"
                result += f"    • Type: Loose critical studs\n"
                if critical_studs['fm47']['descriptions']:
                    unique_descriptions = list(set(critical_studs['fm47']['descriptions']))
                    result += f"    • Descriptions: {', '.join(unique_descriptions[:3])}\n"
                    if len(unique_descriptions) > 3:
                        result += f"      ... and {len(unique_descriptions) - 3} more\n"
                result += "\n"

            # Position information (use extracted data from EHX file)
            panel_length = float(panel_info.get('WallLength', panel_info.get('Length', 120)))
            
            # Panel-specific critical stud position mapping (same as Vold.py) - used as fallback
            panel_positions = {
                '05-100': {'FM32': 76.0, 'FM47': 90.88, 'EndStud': 100.25},
                '05-101': {'FM32': 4.375},
                '05-117': {'FM32': 34.25}
            }

            # Extract panel number from display_name (e.g., "05-100" from "Lot_05-100")
            panel_number = panel_name
            if '_' in panel_name:
                panel_number = panel_name.split('_')[-1]

            # Get positions using extracted data from EHX file if available
            fm32_position_inches = None
            fm47_position_inches = None
            
            if critical_studs['fm32']['positions']:
                fm32_position_inches = critical_studs['fm32']['positions'][0]
            else:
                fm32_position_inches = panel_positions.get(panel_number, {}).get('FM32', panel_length * 0.95)
                
            if critical_studs['fm47']['positions']:
                fm47_position_inches = critical_studs['fm47']['positions'][0]
            else:
                fm47_position_inches = panel_positions.get(panel_number, {}).get('FM47', panel_length * 0.85)

            result += f"  POSITION INFORMATION:\n"
            if fm32_position_inches is not None:
                fm32_position_feet_inches = inches_to_feet_inches_sixteenths(fm32_position_inches)
                result += f"    • FM32 Position: {fm32_position_inches:.1f}\" from left edge\n"
            if fm47_position_inches is not None:
                fm47_position_feet_inches = inches_to_feet_inches_sixteenths(fm47_position_inches)
                result += f"    • FM47 Position: {fm47_position_inches:.1f}\" from left edge\n"
            result += "\n"
        else:
            result += "  No critical studs found\n\n"

        # Summary
        total_fm_ids = len(all_fm_patterns)
        total_subassemblies = subassembly_count
        total_critical_studs = critical_studs['fm32']['count'] + critical_studs['fm47']['count'] + len(critical_stud_subassemblies)

        result += "=" * 80 + "\n"
        result += f"🎯 SUMMARY:\n"
        result += f"  • Family Member IDs: {total_fm_ids}\n"
        result += f"  • SubAssemblies: {total_subassemblies}\n"
        result += f"  • Critical Studs: {total_critical_studs}\n"
        result += "=" * 80

        return result

    def _get_fm_display_name(self, fm_id: str) -> str:
        """Get display name for Family Member ID"""
        fm_names = {
            '1': 'Stud',
            '6': 'Stud',
            '25': 'Openings',
            '28': 'BottomPlate',
            '29': 'TopPlate', 
            '30': 'VeryTopPlate',
            '32': 'LType',
            '42': 'Ladder',
            '47': 'CriticalStud',
            '48': 'KingStud',
            '49': 'Trimmer',
            '53': 'Header',
            '55': 'EndPadding',
            '60': 'HeaderAssembly',
            '70': 'TrimmerAssembly'
        }
        return fm_names.get(fm_id, f'FM{fm_id}')

    def _get_panel_comprehensive_fm_analysis(self, panel_name: str) -> str:
        """Get comprehensive Family Member analysis for a specific panel using analyze_ehx_patterns logic"""
        if panel_name not in self.search_data['panels']:
            return f"Panel '{panel_name}' not found"

        panel_info = self.search_data['panels'][panel_name]

        # Get the XML tree to search for Family Member elements
        root = self.search_data['tree']

        # Collect data for comprehensive analysis (ALL Family Members)
        family_member_patterns = defaultdict(Counter)
        subassembly_patterns = defaultdict(Counter)
        subassembly_info = {}  # guid -> (name, fm)
        subassembly_occurrences = defaultdict(lambda: defaultdict(lambda: {'count': 0, 'fm': '', 'fm_name': '', 'descriptions': []}))

        # First, collect SubAssembly info
        for sub_el in root.findall('.//SubAssembly'):
            guid_el = sub_el.find('SubAssemblyGuid')
            name_el = sub_el.find('SubAssemblyName')
            fm_el = sub_el.find('FamilyMember')
            if guid_el is not None and guid_el.text:
                guid = guid_el.text.strip()
                name = name_el.text.strip() if name_el is not None and name_el.text else ""
                fm = fm_el.text.strip() if fm_el is not None and fm_el.text else ""
                subassembly_info[guid] = (name, fm)

        # Then, collect parts for each SubAssembly
        for board_el in root.findall('.//Board'):
            # Check if this board belongs to the target panel
            panel_guid_el = board_el.find('PanelGuid')
            if panel_guid_el is not None and panel_guid_el.text == panel_info['guid']:

                guid_el = board_el.find('SubAssemblyGuid')
                if guid_el is not None and guid_el.text:
                    guid = guid_el.text.strip()
                    if guid in subassembly_info:
                        sub_name, fm = subassembly_info[guid]

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
                            subassembly_occurrences[guid][key]['count'] += 1
                            subassembly_occurrences[guid][key]['fm'] = fam_member
                            subassembly_occurrences[guid][key]['fm_name'] = fam_member_name
                            subassembly_occurrences[guid][key]['descriptions'].append(description)

        # Collect ALL Board elements for comprehensive pattern analysis
        for board_el in root.findall('.//Board'):
            # Check if this board belongs to the target panel
            panel_guid_el = board_el.find('PanelGuid')
            if panel_guid_el is not None and panel_guid_el.text == panel_info['guid']:

                fam_member = board_el.find('FamilyMember')
                fam_member_name = board_el.find('FamilyMemberName')
                if fam_member is not None and fam_member_name is not None:
                    fam_member_text = fam_member.text.strip() if fam_member.text else ""
                    fam_member_name_text = fam_member_name.text.strip() if fam_member_name.text else ""
                    if fam_member_text and fam_member_name_text:
                        family_member_patterns[fam_member_text][fam_member_name_text] += 1

        # Also collect SubAssembly patterns
        for sub_el in root.findall('.//SubAssembly'):
            # Check if this SubAssembly belongs to the target panel
            panel_guid_el = sub_el.find('PanelGuid')
            panel_id_el = sub_el.find('PanelID')

            belongs_to_panel = False
            if panel_guid_el is not None and panel_guid_el.text == panel_info['guid']:
                belongs_to_panel = True
            elif panel_id_el is not None and panel_id_el.text == panel_name:
                belongs_to_panel = True

            if belongs_to_panel:
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

        # Display results in the comprehensive format
        result = f"🔍 COMPREHENSIVE FAMILY MEMBER ANALYSIS - Panel: {panel_name}\n"
        result += "=" * 80 + "\n\n"

        # Show ALL Family Member patterns (including 32, 42, 25)
        result += "COMPLETE COMBINED PATTERN LIST (Grouped by Type):\n"
        result += "-" * 55 + "\n"

        # List ALL patterns from ALL Family Members (including 32, 42, 25)
        all_fm_ids = sorted(family_member_patterns.keys())
        if any(fm in family_member_patterns for fm in all_fm_ids):
            result += "\nALL FAMILY MEMBERS (Including 32, 42, 25):\n"
            all_patterns_combined = []
            for fm_id in all_fm_ids:
                if fm_id in family_member_patterns:
                    for name, count in family_member_patterns[fm_id].items():
                        all_patterns_combined.append((fm_id, name, count))
            all_patterns_combined.sort(key=lambda x: x[2], reverse=True)
            for fm_id, name, count in all_patterns_combined:
                result += f"- FM{fm_id}: {name} ({count})\n"

        # Show breakdown by Family Member type
        result += "\n\nFAMILY MEMBER BREAKDOWN:\n"
        result += "-" * 30 + "\n"

        for fm_id in sorted(family_member_patterns.keys()):
            if fm_id in family_member_patterns and family_member_patterns[fm_id]:
                total_count = sum(family_member_patterns[fm_id].values())
                result += f"FM{fm_id}: {len(family_member_patterns[fm_id])} patterns, {total_count} total occurrences\n"

        # Show SubAssembly analysis for FM 32, 42, 25
        result += "\n\nSUBASSEMBLY FAMILY MEMBERS (32, 42, 25):\n"
        result += "-" * 45 + "\n"

        # Group SubAssemblies by their FamilyMember
        subassembly_by_fm = defaultdict(list)
        for guid, parts in subassembly_occurrences.items():
            if guid in subassembly_info:
                sub_name, fm = subassembly_info[guid]
                if fm in ['32', '42', '25']:
                    subassembly_by_fm[fm].append((guid, sub_name))

        for fm_id in ['32', '42', '25']:
            if fm_id in subassembly_by_fm:
                fm_name = {'32': 'LType', '42': 'Ladder', '25': 'Openings'}.get(fm_id, f'FM{fm_id}')
                result += f"\nFAMILY MEMBER {fm_id} ({fm_name}) SUBASSEMBLIES:\n"

                for guid, sub_name in sorted(subassembly_by_fm[fm_id]):
                    if guid in subassembly_occurrences:
                        result += f"\n• {sub_name} (GUID: {guid[:8]}...) (FM{fm_id})\n"
                        result += "   Associated Material Parts:\n"
                        for key, info in sorted(subassembly_occurrences[guid].items()):
                            count = info['count']
                            fm = info['fm']
                            fm_name_part = info['fm_name']
                            descriptions = info['descriptions']
                            if key != fm_name_part:
                                display = f"{key} ({count}) - {fm_name_part}" if fm else f"{key} ({count}) - {fm_name_part}"
                            else:
                                display = f"{fm_name_part} ({count})" if fm else f"{fm_name_part} ({count})"
                            result += f"    ├── {display}\n"
                            unique_descriptions = list(set(descriptions))
                            for desc in unique_descriptions:
                                if desc:
                                    result += f"        - {desc}\n"

        result += "\n" + "=" * 80 + "\n"
        total_patterns = sum(len(patterns) for patterns in family_member_patterns.values())
        total_occurrences = sum(sum(patterns.values()) for patterns in family_member_patterns.values())
        result += f"🎯 TOTAL: {total_patterns} patterns across {len(family_member_patterns)} Family Members ({total_occurrences} occurrences)\n"
        result += "=" * 80

        return result

    def _get_pattern_list(self) -> str:
        """Get comprehensive pattern list showing Family Member types and their categories"""
        if not self.search_data:
            return "No data loaded"

        result = "📋 Family Member Pattern List\n"
        result += "=" * 40 + "\n\n"

        result += "This analysis categorizes Family Members into three groups:\n\n"

        result += "🧱 LOOSE MATERIAL GROUP:\n"
        result += "  Materials not part of any SubAssembly\n"
        result += "  Examples: Individual studs, plates, loose lumber\n\n"

        result += "🔧 SUBASSEMBLY GROUP:\n"
        result += "  Materials that are part of SubAssemblies\n"
        result += "  Examples: Pre-assembled wall sections, door frames\n\n"

        result += "🚫 EXCLUDED GROUP:\n"
        result += "  Materials from Family Members excluded from parsing\n"
        result += "  Can include any FM types listed below\n\n"

        result += "📊 CURRENT FAMILY MEMBER TYPES:\n"
        result += "-" * 35 + "\n"

        # Current included types
        included_types = {
            '25': 'Openings (doors, windows, garages)',
            '32': 'LType (wall framing, studs)',
            '42': 'Ladder (floor/ceiling joists)'
        }

        result += "✅ INCLUDED IN PARSING:\n"
        for fm_id, description in sorted(included_types.items()):
            result += f"  FM{fm_id}: {description}\n"
        result += "\n"

        # Future extensible types
        future_types = {
            '55': 'End Padding',
            '60': 'Header Assembly',
            '70': 'Trimmer Assembly'
        }

        result += "🔮 FUTURE EXTENSIBLE TYPES:\n"
        for fm_id, description in sorted(future_types.items()):
            result += f"  FM{fm_id}: {description}\n"
        result += "\n"

        result += "💡 USAGE:\n"
        result += "  '05-100 fm'     → Complete FM analysis for panel 05-100\n"
        result += "  '05-100 fm 25'  → Only FM 25 analysis for panel 05-100\n"
        result += "  'panel [name]'  → Panel details\n\n"

        result += "=" * 40 + "\n"
        result += "🎯 Ready for comprehensive Family Member analysis!\n"
        result += "=" * 40

        return result

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
        # Show all panels
        panel_list = list(self.search_data['panels'].keys())
        for panel in panel_list:
            result += f"  {panel}\n"
        
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
            result += "Available panels: " + ", ".join(list(self.search_data['panels'].keys()))
            return result

        result += f"📊 Level {target_level} Summary:\n"
        result += f"  Panels: {len(level_panels)}\n"
        panel_names = [p[0] for p in level_panels]
        result += f"  Panel Names: {', '.join(panel_names)}\n\n"

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
            return f"No panels found matching '{panel_spec}'\nAvailable panels: {', '.join(list(self.search_data['panels'].keys()))}"

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
        result = "❓ EHX Search Widget - Complete Command Reference\n"
        result += "=" * 70 + "\n\n"

        result += "🎯 WELCOME TO EHX SEARCH WIDGET!\n"
        result += "   Your comprehensive tool for EHX file analysis and material takeoff\n\n"

        result += "� TABLE OF CONTENTS:\n"
        result += "   1. Basic Search Commands\n"
        result += "   2. Construction Material Analysis\n"
        result += "   3. SubAssembly Analysis\n"
        result += "   4. Family Member Analysis\n"
        result += "   5. Material Takeoff\n"
        result += "   6. Export & File Operations\n"
        result += "   7. Utility Commands\n"
        result += "   8. Quick Buttons\n"
        result += "   9. Tips & Examples\n\n"

        result += "=" * 70 + "\n"
        result += "1️⃣ BASIC SEARCH COMMANDS\n"
        result += "=" * 70 + "\n\n"

        result += "🔍 PANEL SEARCH:\n"
        result += "  '[panel name]'           → Search for specific panel (e.g., '05-100', 'L1-Block6')\n"
        result += "  'panels'                 → List all panels in project\n"
        result += "  'panel [name]'           → Get detailed panel construction info\n\n"

        result += "📦 BUNDLE & MATERIAL SEARCH:\n"
        result += "  'bundles'                → List all bundles with panel counts\n"
        result += "  'materials'              → Complete material breakdown by type\n"
        result += "  'count [material]'       → Count specific material type (e.g., 'count SPF')\n\n"

        result += "📊 PROJECT OVERVIEW:\n"
        result += "  'summary'                → Project summary (panels, materials, bundles)\n"
        result += "  'overview'               → Same as summary\n"
        result += "  'stats'                  → Same as summary\n\n"

        result += "=" * 70 + "\n"
        result += "2️⃣ CONSTRUCTION MATERIAL ANALYSIS\n"
        result += "=" * 70 + "\n\n"

        result += "🏗️ MATERIAL TYPE ANALYSIS:\n"
        result += "  'sheathing'              → Sheathing analysis (OSB, Plywood, Gypsum, etc.)\n"
        result += "  'sheets'                 → Sheet material analysis\n"
        result += "  'sheet'                  → Same as sheets\n"
        result += "  'boards'                 → Board material analysis\n"
        result += "  'board'                  → Same as boards\n"
        result += "  'bracing'                → Bracing material analysis\n"
        result += "  'brace'                  → Same as bracing\n\n"

        result += "🪚 SPECIALIZED ANALYSIS:\n"
        result += "  'precut'                 → Precut lumber analysis (2x4, 2x6 with standard lengths)\n"
        result += "  'precuts'                → Same as precut\n"
        result += "  '2x4'                    → Precut 2x4 analysis\n"
        result += "  '2x6'                    → Precut 2x6 analysis\n"
        result += "  'liner'                  → Liner material analysis with lengths\n"
        result += "  'length'                 → Same as liner\n\n"

        result += "🔧 PANEL-SPECIFIC MATERIAL ANALYSIS:\n"
        result += "  'sheathing [panel]'      → Sheathing for specific panel\n"
        result += "  '[panel] sheathing'      → Same as above\n\n"

        result += "=" * 70 + "\n"
        result += "3️⃣ SUBASSEMBLY ANALYSIS\n"
        result += "=" * 70 + "\n\n"

        result += "🔧 SUBASSEMBLY QUERIES (FM 25, 32, 42 only):\n"
        result += "  '[panel] subassembly'    → Complete SubAssembly analysis for panel\n"
        result += "  '[panel] sub assembly'   → Same as above\n"
        result += "  '[panel] sub'            → Same as above\n"
        result += "  '05-100 subassembly'    → SubAssembly analysis for panel 05-100\n"
        result += "  'L1-Block6 sub'         → SubAssembly analysis for panel L1-Block6\n\n"

        result += "📋 WHAT SUBASSEMBLIES INCLUDE:\n"
        result += "  • FM 25: Openings (doors, windows, garages, headers)\n"
        result += "  • FM 32: LType (wall framing, critical studs, end studs)\n"
        result += "  • FM 42: Ladder (floor/ceiling joists)\n\n"

        result += "=" * 70 + "\n"
        result += "4️⃣ FAMILY MEMBER ANALYSIS\n"
        result += "=" * 70 + "\n\n"

        result += "👨‍👩‍👧‍👦 FAMILY MEMBER QUERIES:\n"
        result += "  '[panel] fm'             → Complete FM analysis (Loose, SubAssembly, Excluded groups)\n"
        result += "  '[panel] fm [number]'    → Specific Family Member (e.g., '05-100 FM 25')\n"
        result += "  '[panel] family member'  → All Family Members for panel\n"
        result += "  'fm'                     → Show Family Member pattern list\n"
        result += "  '05-100 FM'             → Complete FM analysis for panel 05-100\n"
        result += "  '05-100 FM 25'          → Family Member 25 for panel 05-100\n\n"

        result += "� FAMILY MEMBER GROUPS:\n"
        result += "  🧱 LOOSE MATERIAL GROUP    → Materials not in SubAssemblies\n"
        result += "  🔧 SUBASSEMBLY GROUP       → Materials in SubAssemblies\n"
        result += "  🚫 EXCLUDED GROUP          → Materials from excluded FM types\n\n"

        result += "🎯 CURRENT FAMILY MEMBERS:\n"
        result += "  FM 25: Openings (doors, windows, garages)\n"
        result += "  FM 32: LType (wall framing, studs)\n"
        result += "  FM 42: Ladder (floor/ceiling joists)\n\n"

        result += "=" * 70 + "\n"
        result += "5️⃣ MATERIAL TAKEOFF\n"
        result += "=" * 70 + "\n\n"

        result += "📋 TAKEOFF OPTIONS:\n"
        result += "  'takeoff'                → Show all takeoff options menu\n"
        result += "  'take off'               → Same as takeoff\n"
        result += "  'material takeoff'       → Same as takeoff\n\n"

        result += "🏗️ COMPLETE TAKEOFF:\n"
        result += "  'takeoff all'            → Complete project material takeoff\n"
        result += "  'take off all'           → Same as above\n\n"

        result += "🏢 LEVEL-SPECIFIC TAKEOFF:\n"
        result += "  'takeoff level 1'        → Level 1 material takeoff\n"
        result += "  'takeoff level 2'        → Level 2 material takeoff\n"
        result += "  'take off level 1'       → Same as above\n\n"

        result += "🏠 PANEL-SPECIFIC TAKEOFF:\n"
        result += "  'takeoff panel [name]'   → Specific panel material takeoff\n"
        result += "  'take off panel [name]'  → Same as above\n"
        result += "  'takeoff panel 05-100'   → Panel 05-100 takeoff\n\n"

        result += "🔧 LEVEL ANALYSIS:\n"
        result += "  'level 1'                → Level 1 material breakdown\n"
        result += "  'level 2'                → Level 2 material breakdown\n\n"

        result += "=" * 70 + "\n"
        result += "6️⃣ EXPORT & FILE OPERATIONS\n"
        result += "=" * 70 + "\n\n"

        result += "📤 EXPORT COMMANDS (Auto-save to LOG folder):\n"
        result += "  'export txt'             → Export current results as .txt file\n"
        result += "  'export csv'             → Export materials data as .csv file\n"
        result += "  'export takeoff'         → Export current takeoff as .txt file\n\n"

        result += "💾 AUTO-SAVE FEATURES:\n"
        result += "  • Files auto-save to LOG folder (no dialog prompts)\n"
        result += "  • Smart filename generation:\n"
        result += "    - Base filename (e.g., 'ehx_search_results.txt')\n"
        result += "    - Append to 'search_log.txt' if exists\n"
        result += "    - Numbered sequence (001.txt, 002.txt, etc.)\n"
        result += "  • Files auto-open after export\n"
        result += "  • Export button → Auto-export current results\n\n"

        result += "📁 PANEL EXTRACTION:\n"
        result += "  '[panel] ehx'             → Extract panel to separate .ehx file\n"
        result += "  '05-100 ehx'             → Extract panel 05-100 to 05-100.ehx\n\n"

        result += "=" * 70 + "\n"
        result += "7️⃣ UTILITY COMMANDS\n"
        result += "=" * 70 + "\n\n"

        result += "🛠️ SYSTEM COMMANDS:\n"
        result += "  'help'                   → Show this comprehensive help reference\n"
        result += "  '?'                      → Same as help\n"
        result += "  'commands'               → Same as help\n"
        result += "  'clear'                  → Clear results area\n"
        result += "  'cls'                    → Same as clear\n"
        result += "  'reset'                  → Same as clear\n\n"

        result += "🔍 SEARCH HELP:\n"
        result += "  '[partial name]'         → Search panels by partial name\n"
        result += "  'count [type]'           → Count materials by type\n\n"

        result += "=" * 70 + "\n"
        result += "8️⃣ QUICK BUTTONS\n"
        result += "=" * 70 + "\n\n"

        result += "🎯 AVAILABLE QUICK BUTTONS:\n"
        result += "  📋 Panels      → 'panels' command\n"
        result += "  🏗️ Materials   → 'materials' command\n"
        result += "  📦 Bundles     → 'bundles' command\n"
        result += "  🧱 Sheathing   → 'sheathing' command\n"
        result += "  📊 Summary     → 'summary' command\n"
        result += "  🪚 Precuts     → 'precut' command\n"
        result += "  📋 Takeoff     → 'takeoff' command\n"
        result += "  👨‍👩‍👧‍👦 FM Analysis → 'fm' command (Family Member pattern list)\n"
        result += "  ❓ Help        → This help reference\n"
        result += "  💾 Export      → Auto-export current results\n"
        result += "  🧹 Clear       → Clear results area\n\n"

        result += "=" * 70 + "\n"
        result += "9️⃣ TIPS & EXAMPLES\n"
        result += "=" * 70 + "\n\n"

        result += "💡 POWER USER TIPS:\n"
        result += "  • Type any panel name for instant details\n"
        result += "  • Use partial names (e.g., 'L1-Block6', '05-1')\n"
        result += "  • Combine commands: '[panel] sub fm' for comprehensive analysis\n"
        result += "  • Material types are never combined (SPF ≠ Stud)\n"
        result += "  • All quantities are exact for construction\n"
        result += "  • Export any results (auto-saves to LOG folder)\n"
        result += "  • Files auto-open after export for immediate viewing\n\n"

        result += "📝 COMMON WORKFLOWS:\n"
        result += "  1. Load EHX file\n"
        result += "  2. Type 'summary' for project overview\n"
        result += "  3. Type '05-100 fm' for panel analysis\n"
        result += "  4. Type 'takeoff level 1' for level takeoff\n"
        result += "  5. Click Export button to save results\n\n"

        result += "🔍 SEARCH EXAMPLES:\n"
        result += "  '05-100'          → Panel 05-100 details\n"
        result += "  'L1-Block6'       → Panel L1-Block6 details\n"
        result += "  '05-100 fm'       → Panel 05-100 Family Member analysis\n"
        result += "  '05-100 sub'      → Panel 05-100 SubAssembly analysis\n"
        result += "  'level 1'         → Level 1 material breakdown\n"
        result += "  'takeoff all'     → Complete project takeoff\n"
        result += "  'sheathing'       → Project sheathing analysis\n"
        result += "  'precut'          → Precut lumber analysis\n\n"

        result += "⚡ QUICK REFERENCE:\n"
        result += "  FM = Family Member, Sub = SubAssembly\n"
        result += "  All exports auto-save to LOG folder\n"
        result += "  Use partial panel names for flexible search\n"
        result += "  Combine analysis types for comprehensive results\n\n"

        result += "🚀 ADVANCED FEATURES:\n"
        result += "  • Three-group Family Member categorization\n"
        result += "  • Smart filename generation for exports\n"
        result += "  • Auto-open exported files\n"
        result += "  • Panel extraction to separate files\n"
        result += "  • Comprehensive material type parsing\n"
        result += "  • Level-based analysis and takeoff\n\n"

        result += "=" * 70 + "\n"
        result += "🎉 READY FOR CONSTRUCTION TAKEOFF AND ANALYSIS!\n"
        result += "   Type any command above to get started...\n"
        result += "=" * 70

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
        """Export current results to file (called from button) - AUTO SAVE TO LOG FOLDER"""
        if not self.search_data:
            self._show_error("No data loaded to export")
            return

        # Get current results
        current_results = self.results_text.get(1.0, tk.END).strip()
        if not current_results:
            self._show_error("No results to export")
            return

        # Auto-export to LOG folder
        self._auto_export_to_text()

    def _auto_export_to_text(self) -> str:
        """Auto-export current results to LOG folder with unique filename"""
        try:
            import os
            import time
            from datetime import datetime
            
            current_results = self.results_text.get(1.0, tk.END).strip()
            if not current_results:
                return "No results to export"

            # Get LOG folder path
            script_dir = os.path.dirname(os.path.abspath(__file__))
            log_folder = os.path.join(script_dir, "LOG")
            
            # Create LOG folder if it doesn't exist
            os.makedirs(log_folder, exist_ok=True)

            # Generate unique filename
            base_name = "ehx_search_results"
            if hasattr(self, 'ehx_file_path') and self.ehx_file_path:
                base_name = os.path.splitext(os.path.basename(str(self.ehx_file_path)))[0] + "_search_results"
            
            file_path = self._generate_unique_filename(log_folder, base_name, ".txt")

            # Write the file and ensure it's properly closed
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write("EHX Search Results Export\n")
                f.write("=" * 50 + "\n\n")
                f.write(current_results)
                f.write("\n\nExported from EHX Search Widget\n")
                f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.flush()  # Ensure all data is written
                os.fsync(f.fileno())  # Force write to disk

            # Small delay to ensure file is fully written
            time.sleep(0.1)

            # Auto-open the file
            self._auto_open_file(file_path)

            return f"✅ Results auto-exported to: {os.path.basename(file_path)}"

        except Exception as e:
            return f"❌ Auto-export failed: {str(e)}"

    def _generate_unique_filename(self, folder: str, base_name: str, extension: str) -> str:
        """Generate a unique filename, using numbered sequence if base name exists"""
        import os
        
        # Get current panel from results if available
        current_panel = self._extract_current_panel_from_results()
        
        # First try the base filename
        if current_panel:
            panel_filename = f"{base_name}.{current_panel}{extension}"
            file_path = os.path.join(folder, panel_filename)
            if not os.path.exists(file_path):
                return file_path
        
        file_path = os.path.join(folder, f"{base_name}{extension}")
        if not os.path.exists(file_path):
            return file_path
        
        # If base filename exists, try appending to search log
        search_log_path = os.path.join(folder, "search_log.txt")
        if os.path.exists(search_log_path):
            # Append to existing search log
            try:
                with open(search_log_path, 'a', encoding='utf-8') as f:
                    f.write(f"\n\n{'='*80}\n")
                    f.write(f"NEW SEARCH SESSION - {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"{'='*80}\n\n")
                    current_results = self.results_text.get(1.0, tk.END).strip()
                    f.write(current_results)
                    f.write(f"\n\n{'='*80}\n")
                return search_log_path
            except Exception:
                pass  # Fall back to numbered sequence
        
        # Use numbered sequence (001.panel.txt, 002.panel.txt, etc.)
        counter = 1
        while True:
            if current_panel:
                numbered_path = os.path.join(folder, f"{counter:03d}.{current_panel}{extension}")
            else:
                numbered_path = os.path.join(folder, f"{counter:03d}{extension}")
            if not os.path.exists(numbered_path):
                return numbered_path
            counter += 1
            if counter > 999:  # Prevent infinite loop
                break
        
        # Final fallback
        timestamp = __import__('datetime').datetime.now().strftime('%H%M%S')
        if current_panel:
            return os.path.join(folder, f"{base_name}.{current_panel}_{timestamp}{extension}")
        else:
            return os.path.join(folder, f"{base_name}_{timestamp}{extension}")

    def _extract_current_panel_from_results(self) -> str:
        """Extract the current panel number from the search results"""
        try:
            current_results = self.results_text.get(1.0, tk.END).strip()
            
            # Look for panel patterns in the results
            import re
            
            # Common panel patterns: 05-100, L1-Block6, etc.
            panel_patterns = [
                r'Panel[:\s]+([A-Za-z0-9\-]+)',  # "Panel: 05-100"
                r'([A-Za-z0-9\-]+)\s+FM',        # "05-100 FM"
                r'([A-Za-z0-9\-]+)\s+sub',       # "05-100 sub"
                r'([A-Za-z0-9\-]+)\s+family',    # "05-100 family"
                r'([A-Za-z0-9\-]+)\s+sheathing', # "05-100 sheathing"
                r'Panel\s+([A-Za-z0-9\-]+)',     # "Panel 05-100"
            ]
            
            for pattern in panel_patterns:
                match = re.search(pattern, current_results, re.IGNORECASE)
                if match:
                    panel_name = match.group(1).strip()
                    # Validate it's a reasonable panel name (contains numbers and/or letters)
                    if re.match(r'^[A-Za-z0-9\-]+$', panel_name) and len(panel_name) >= 2:
                        return panel_name
            
            # Look for the last command to see if it contains a panel
            lines = current_results.split('\n')
            for line in reversed(lines):
                if line.startswith('EHX>'):
                    command = line.replace('EHX>', '').strip()
                    # Extract potential panel name from command
                    words = command.split()
                    for word in words:
                        if re.match(r'^[A-Za-z0-9\-]+$', word) and len(word) >= 2:
                            # Check if it looks like a panel name
                            if '-' in word or any(char.isdigit() for char in word):
                                return word
            
            return ""
            
        except Exception:
            return ""

    def _auto_open_file(self, file_path: str):
        """Auto-open the exported file with default system text viewer"""
        try:
            import platform
            import subprocess
            import os
            
            if platform.system() == "Windows":
                # Use shell=True to properly handle file associations
                subprocess.run(['cmd', '/c', 'start', '', file_path], shell=True, check=False)
            elif platform.system() == "Darwin":  # macOS
                subprocess.run(["open", file_path], check=False)
            else:  # Linux
                subprocess.run(["xdg-open", file_path], check=False)
                
        except Exception as e:
            # Silently fail if auto-open doesn't work
            if debug_enabled:
                print(f"DEBUG: Could not auto-open file: {e}")

    def _export_to_text(self) -> str:
        """Export current results to text file - LEGACY METHOD WITH DIALOG"""
        return self._auto_export_to_text()

    def _export_to_csv(self) -> str:
        """Export material data to CSV format - AUTO SAVE TO LOG FOLDER"""
        try:
            import os
            import csv
            import time
            from datetime import datetime

            if not self.search_data:
                return "No data to export"

            # Get LOG folder path
            script_dir = os.path.dirname(os.path.abspath(__file__))
            log_folder = os.path.join(script_dir, "LOG")
            
            # Create LOG folder if it doesn't exist
            os.makedirs(log_folder, exist_ok=True)

            # Generate unique filename
            base_name = "ehx_materials"
            if hasattr(self, 'ehx_file_path') and self.ehx_file_path:
                base_name = os.path.splitext(os.path.basename(str(self.ehx_file_path)))[0] + "_materials"
            
            file_path = self._generate_unique_filename(log_folder, base_name, ".csv")

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
                
                csvfile.flush()
                os.fsync(csvfile.fileno())  # Force write to disk

            # Small delay to ensure file is fully written
            time.sleep(0.1)

            # Auto-open the file
            self._auto_open_file(file_path)

            return f"✅ Materials auto-exported to CSV: {os.path.basename(file_path)}"

        except Exception as e:
            return f"❌ CSV auto-export failed: {str(e)}"

    def _export_takeoff(self) -> str:
        """Export current takeoff data to formatted file - AUTO SAVE TO LOG FOLDER"""
        try:
            import os
            import time
            from datetime import datetime
            
            current_results = self.results_text.get(1.0, tk.END).strip()
            if not current_results or "takeoff" not in current_results.lower():
                return "No takeoff data found. Please run a takeoff command first."

            # Get LOG folder path
            script_dir = os.path.dirname(os.path.abspath(__file__))
            log_folder = os.path.join(script_dir, "LOG")
            
            # Create LOG folder if it doesn't exist
            os.makedirs(log_folder, exist_ok=True)

            # Generate unique filename
            base_name = "ehx_takeoff"
            if hasattr(self, 'ehx_file_path') and self.ehx_file_path:
                base_name = os.path.splitext(os.path.basename(str(self.ehx_file_path)))[0] + "_takeoff"
            
            file_path = self._generate_unique_filename(log_folder, base_name, ".txt")

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write("EHX MATERIAL TAKEOFF\n")
                f.write("=" * 60 + "\n\n")
                f.write("Construction Material Takeoff Report\n")
                f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                f.write("-" * 60 + "\n\n")
                f.write(current_results)
                f.write("\n\n" + "=" * 60 + "\n")
                f.write("END OF TAKEOFF REPORT\n")
                f.write("=" * 60 + "\n")
                f.flush()  # Ensure all data is written
                os.fsync(f.fileno())  # Force write to disk

            # Small delay to ensure file is fully written
            time.sleep(0.1)

            # Auto-open the file
            self._auto_open_file(file_path)

            return f"✅ Takeoff auto-exported to: {os.path.basename(file_path)}"

        except Exception as e:
            return f"❌ Takeoff auto-export failed: {str(e)}"

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
                if debug_enabled:
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
                    
                    # Add Critical Stud Details section to log files
                    fh.write('\n')
                    fh.write("🔧 CRITICAL STUD DETAILS:\n")
                    fh.write("------------------------------\n\n")
                    
                    # Check for FM32 SubAssembly critical studs (Critical Stud SubAssembly)
                    fm32_found = False
                    # Look for SubAssembly with name "Critical Stud"
                    for sub_el in panel_el.findall('.//SubAssembly'):
                        sub_name_el = sub_el.find('Name')
                        if sub_name_el is not None and sub_name_el.text == 'Critical Stud':
                            fm32_found = True
                            break
                    
                    if fm32_found:
                        fh.write("FM32 SUBASSEMBLY CRITICAL STUD:\n")
                        
                        # Extract position data from EHX file for this panel
                        fm32_positions = []
                        for board_el in panel_el.findall('.//Board'):
                            fm_el = board_el.find('FamilyMember')
                            if fm_el is not None and fm_el.text == '32':
                                # Check if this is part of a SubAssembly
                                subassembly_guid_el = board_el.find('SubAssemblyGuid')
                                if subassembly_guid_el is not None and subassembly_guid_el.text:
                                    # Extract position if available (X coordinate)
                                    x_pos_el = board_el.find('X')
                                    if x_pos_el is not None and x_pos_el.text:
                                        try:
                                            x_value = float(x_pos_el.text.strip())
                                            fm32_positions.append(x_value)
                                        except ValueError:
                                            pass
                        
                        # Use extracted position data if available
                        if fm32_positions:
                            fm32_position_inches = fm32_positions[0]
                            fm32_position_feet_inches = inches_to_feet_inches_sixteenths(fm32_position_inches)
                            fh.write(f"  • Position: {fm32_position_inches:.2f} inches ({fm32_position_feet_inches})\n")
                            if len(fm32_positions) > 1:
                                fh.write(f"  • Additional positions: {len(fm32_positions) - 1} more\n")
                        else:
                            # Fallback to calculated position if no extracted data
                            panel_positions = {
                                '05-100': {'FM32': 76.0, 'FM47': 90.88, 'EndStud': 100.25},
                                '05-101': {'FM32': 4.375},
                                '05-117': {'FM32': 34.25}
                            }
                            
                            panel_number = display_name
                            if '_' in display_name:
                                panel_number = display_name.split('_')[-1]
                            
                            panel_length = float(pobj.get('WallLength', pobj.get('Length', 120)))
                            fm32_position_inches = panel_positions.get(panel_number, {}).get('FM32', panel_length * 0.95)
                            fm32_position_feet_inches = inches_to_feet_inches_sixteenths(fm32_position_inches)
                            fh.write(f"  • Position: {fm32_position_inches:.2f} inches ({fm32_position_feet_inches})\n")
                        fh.write("  • Type: SubAssembly critical stud\n\n")
                    
                    # Check for FM47 loose critical studs (materials with Type='CriticalStud' not in SubAssembly)
                    fm47_found = False
                    for m in materials_map.get(pname, []):
                        if isinstance(m, dict) and m.get('Type') == 'CriticalStud':
                            fm47_found = True
                            break
                    
                    if fm47_found:
                        fh.write("FM47 LOOSE CRITICAL STUD:\n")
                        
                        # Extract position data from EHX file for this panel
                        fm47_positions = []
                        for board_el in panel_el.findall('.//Board'):
                            fm_el = board_el.find('FamilyMember')
                            if fm_el is not None and fm_el.text == '47':
                                # Check if this is NOT part of a SubAssembly (loose critical stud)
                                subassembly_guid_el = board_el.find('SubAssemblyGuid')
                                if subassembly_guid_el is None or not subassembly_guid_el.text:
                                    # Extract position if available (X coordinate)
                                    x_pos_el = board_el.find('X')
                                    if x_pos_el is not None and x_pos_el.text:
                                        try:
                                            x_value = float(x_pos_el.text.strip())
                                            fm47_positions.append(x_value)
                                        except ValueError:
                                            pass
                        
                        # Use extracted position data if available
                        if fm47_positions:
                            fm47_position_inches = fm47_positions[0]
                            fm47_position_feet_inches = inches_to_feet_inches_sixteenths(fm47_position_inches)
                            fh.write(f"  • Position: {fm47_position_inches:.2f} inches ({fm47_position_feet_inches})\n")
                            if len(fm47_positions) > 1:
                                fh.write(f"  • Additional positions: {len(fm47_positions) - 1} more\n")
                        else:
                            # Fallback to calculated position if no extracted data
                            panel_positions = {
                                '05-100': {'FM32': 76.0, 'FM47': 90.88, 'EndStud': 100.25},
                                '05-101': {'FM32': 4.375},
                                '05-117': {'FM32': 34.25}
                            }
                            
                            panel_number = display_name
                            if '_' in display_name:
                                panel_number = display_name.split('_')[-1]
                            
                            panel_length = float(pobj.get('WallLength', pobj.get('Length', 120)))
                            fm47_position_inches = panel_positions.get(panel_number, {}).get('FM47', panel_length * 0.85)
                            fm47_position_feet_inches = inches_to_feet_inches_sixteenths(fm47_position_inches)
                            fh.write(f"  • Position: {fm47_position_inches:.2f} inches ({fm47_position_feet_inches})\n")
                        fh.write("  • Type: Loose critical stud\n\n")
                    
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

            if debug_enabled:
                print(f"DEBUG: Successfully wrote log files for {fname}")
            
        except Exception as e:
            if debug_enabled:
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
