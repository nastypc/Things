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

        # Index panels
        for panel in root.findall('.//Panel'):
            label = panel.find('Label')
            if label is not None and label.text:
                search_data['panels'][label.text] = {
                    'guid': panel.find('PanelGuid').text if panel.find('PanelGuid') is not None else '',
                    'bundle_guid': panel.find('BundleGuid').text if panel.find('BundleGuid') is not None else '',
                    'level_guid': panel.find('LevelGuid').text if panel.find('LevelGuid') is not None else ''
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
