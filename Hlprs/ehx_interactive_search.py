#!/usr/bin/env python3
"""
EHX Interactive Search Tool
Search and explore EHX files interactively through a command-line interface
"""

import xml.etree.ElementTree as ET
from pathlib import Path
import re
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import os

class EHXInteractiveSearch:
    """Interactive search interface for EHX files"""

    def __init__(self, ehx_file_path: str):
        """Initialize with EHX file path"""
        self.file_path = Path(ehx_file_path)
        if not self.file_path.exists():
            raise FileNotFoundError(f"EHX file not found: {ehx_file_path}")

        print(f"Loading EHX file: {ehx_file_path}")
        self.tree = ET.parse(ehx_file_path)
        self.root = self.tree.getroot()

        # Build search indexes for faster queries
        self._build_indexes()
        print("Ready for interactive search!")

    def _build_indexes(self):
        """Build indexes for fast searching"""
        self.panel_index = {}  # panel_label -> panel_info
        self.material_index = defaultdict(list)  # material_type -> list of items
        self.bundle_index = {}  # bundle_guid -> bundle_info

        # Index panels
        for panel in self.root.findall('.//Panel'):
            label = panel.find('Label')
            if label is not None and label.text:
                self.panel_index[label.text] = {
                    'guid': panel.find('PanelGuid').text if panel.find('PanelGuid') is not None else '',
                    'bundle_guid': panel.find('BundleGuid').text if panel.find('BundleGuid') is not None else '',
                    'level_guid': panel.find('LevelGuid').text if panel.find('LevelGuid') is not None else ''
                }

        # Index materials by type
        for board in self.root.findall('.//Board'):
            self._index_material(board, 'Board')

        for sheet in self.root.findall('.//Sheet'):
            self._index_material(sheet, 'Sheet')

        for bracing in self.root.findall('.//Bracing'):
            self._index_material(bracing, 'Bracing')

        # Index bundles
        bundle_panels = defaultdict(list)
        for panel in self.root.findall('.//Panel'):
            bundle_guid = panel.find('BundleGuid')
            if bundle_guid is not None and bundle_guid.text:
                bundle_panels[bundle_guid.text].append(panel)

        for bundle_guid, panels in bundle_panels.items():
            bundle_name = panels[0].find('BundleName').text if panels[0].find('BundleName') is not None else f"Bundle {bundle_guid[:8]}"
            self.bundle_index[bundle_guid] = {
                'name': bundle_name,
                'panel_count': len(panels),
                'panels': [p.find('Label').text for p in panels if p.find('Label') is not None]
            }

    def _index_material(self, element, element_type: str):
        """Index a material element"""
        family_name = element.find('FamilyMemberName')
        if family_name is not None:
            material_type = family_name.text
            self.material_index[material_type].append({
                'type': element_type,
                'element': element,
                'panel_guid': element.find('PanelGuid').text if element.find('PanelGuid') is not None else '',
                'guid': element.find(f'{element_type}Guid').text if element.find(f'{element_type}Guid') is not None else ''
            })

    def search(self, query: str) -> str:
        """Process a search query and return results"""
        query = query.strip().lower()

        if not query:
            return self._show_help()

        # Parse query for commands
        if query.startswith('help'):
            return self._show_help()

        elif query.startswith('panels') or query == 'p':
            return self._search_panels(query.replace('panels', '').replace('p', '').strip())

        elif query.startswith('materials') or query == 'm':
            return self._search_materials(query.replace('materials', '').replace('m', '').strip())

        elif query.startswith('bundles') or query == 'b':
            return self._search_bundles(query.replace('bundles', '').replace('b', '').strip())

        elif query.startswith('sheathing') or query == 's':
            return self._search_sheathing(query.replace('sheathing', '').replace('s', '').strip())

        elif query.startswith('detail') or query == 'd':
            return self._show_detail(query.replace('detail', '').replace('d', '').strip())

        elif query.startswith('count') or query == 'c':
            return self._count_items(query.replace('count', '').replace('c', '').strip())

        else:
            # Try to interpret as panel search first, then material search
            result = self._search_panels(query)
            if "No panels found" in result:
                result = self._search_materials(query)
            if "No materials found" in result:
                result = f"No results found for '{query}'. Try 'help' for available commands."
            return result

    def _show_help(self) -> str:
        """Show available commands"""
        return """
=== EHX Interactive Search Help ===

SEARCH COMMANDS:
  [panel_name]          - Search for specific panel (e.g., "07_103")
  panels [term]         - Search panels by name or partial match
  materials [type]      - Search materials by type (e.g., "header", "sheathing")
  bundles [name]        - Search bundles by name
  sheathing [panel]     - Show sheathing details for panel
  detail [item]         - Show detailed information for item
  count [type]          - Count items by type

SHORTCUTS:
  p [term]             - Same as 'panels'
  m [type]             - Same as 'materials'
  b [name]             - Same as 'bundles'
  s [panel]            - Same as 'sheathing'
  d [item]             - Same as 'detail'
  c [type]             - Same as 'count'

EXAMPLES:
  07_103               - Show panel 07_103 details
  panels 07            - Show all panels starting with 07
  materials header     - Show all headers
  sheathing 07_103     - Show sheathing for panel 07_103
  bundles tall         - Show bundles with "tall" in name
  count sheathing      - Count all sheathing pieces
  detail 07_103        - Show complete details for panel 07_103

Type 'quit' or 'exit' to end session.
        """

    def _search_panels(self, query: str) -> str:
        """Search for panels"""
        if not query:
            # Show all panels
            results = []
            for label, info in sorted(self.panel_index.items()):
                results.append(f"  {label}")
            return f"=== All Panels ({len(results)}) ===\n" + "\n".join(results)

        # Search by partial match
        results = []
        for label, info in self.panel_index.items():
            if query in label.lower():
                results.append(f"  {label} (Bundle: {info['bundle_guid'][:8]}...)")

        if results:
            return f"=== Panels matching '{query}' ({len(results)}) ===\n" + "\n".join(results)
        else:
            return f"No panels found matching '{query}'"

    def _search_materials(self, query: str) -> str:
        """Search for materials"""
        if not query:
            # Show material types
            types = sorted(self.material_index.keys())
            return f"=== Material Types ({len(types)}) ===\n" + "\n".join(f"  {t} ({len(self.material_index[t])})" for t in types)

        # Search by material type
        results = []
        for material_type, items in self.material_index.items():
            if query in material_type.lower():
                results.append(f"  {material_type}: {len(items)} pieces")

        if results:
            return f"=== Materials matching '{query}' ===\n" + "\n".join(results)
        else:
            return f"No materials found matching '{query}'"

    def _search_bundles(self, query: str) -> str:
        """Search for bundles"""
        if not query:
            # Show all bundles
            results = []
            for guid, info in self.bundle_index.items():
                results.append(f"  {info['name']} ({info['panel_count']} panels)")
            return f"=== All Bundles ({len(results)}) ===\n" + "\n".join(results)

        # Search by name
        results = []
        for guid, info in self.bundle_index.items():
            if query in info['name'].lower():
                results.append(f"  {info['name']} ({info['panel_count']} panels): {', '.join(info['panels'][:3])}{'...' if len(info['panels']) > 3 else ''}")

        if results:
            return f"=== Bundles matching '{query}' ({len(results)}) ===\n" + "\n".join(results)
        else:
            return f"No bundles found matching '{query}'"

    def _search_sheathing(self, query: str) -> str:
        """Search sheathing for specific panel"""
        if not query:
            return "Please specify a panel name (e.g., 'sheathing 07_103')"

        panel_info = self.panel_index.get(query.upper())
        if not panel_info:
            return f"Panel '{query}' not found"

        # Find sheathing for this panel
        sheathing = []
        for item in self.material_index.get('Sheathing', []):
            if item['panel_guid'] == panel_info['guid']:
                element = item['element']
                material_elem = element.find('Material')
                if material_elem is not None:
                    desc = material_elem.find('Description')
                    label = element.find('Label')
                    if desc is not None and label is not None:
                        sheathing.append(f"  {label.text}: {desc.text}")

        if sheathing:
            return f"=== Sheathing for Panel {query} ({len(sheathing)} pieces) ===\n" + "\n".join(sheathing)
        else:
            return f"No sheathing found for panel {query}"

    def _show_detail(self, query: str) -> str:
        """Show detailed information for an item"""
        if not query:
            return "Please specify what to show details for (e.g., 'detail 07_103')"

        # Try panel first
        if query.upper() in self.panel_index:
            panel_info = self.panel_index[query.upper()]
            bundle_info = self.bundle_index.get(panel_info['bundle_guid'], {})

            # Count materials for this panel
            material_counts = defaultdict(int)
            for material_type, items in self.material_index.items():
                for item in items:
                    if item['panel_guid'] == panel_info['guid']:
                        material_counts[material_type] += 1

            result = f"""
=== Detailed Information for Panel {query} ===

Panel GUID: {panel_info['guid']}
Bundle: {bundle_info.get('name', 'Unknown')} ({panel_info['bundle_guid'][:8]}...)
Level GUID: {panel_info['level_guid'][:8]}...

Materials Breakdown:
"""
            for material_type, count in sorted(material_counts.items()):
                result += f"  {material_type}: {count} pieces\n"

            # Show sheathing details if any
            sheathing_details = self._search_sheathing(query)
            if "No sheathing found" not in sheathing_details:
                result += f"\n{sheathing_details}"

            return result

        return f"Item '{query}' not found. Try searching for panels, materials, or bundles first."

    def _count_items(self, query: str) -> str:
        """Count items by type"""
        if not query:
            # Show overall counts
            total_panels = len(self.panel_index)
            total_materials = sum(len(items) for items in self.material_index.values())
            total_bundles = len(self.bundle_index)

            return f"""
=== Overall Counts ===
Total Panels: {total_panels}
Total Material Pieces: {total_materials}
Total Bundles: {total_bundles}
Material Types: {len(self.material_index)}
"""

        # Count specific material type (case-insensitive search)
        query_lower = query.lower()
        for material_type in self.material_index:
            if query_lower in material_type.lower():
                count = len(self.material_index[material_type])
                return f"Total {material_type} pieces: {count}"

        return f"Material type '{query}' not found. Available types: {', '.join(sorted(self.material_index.keys()))}"


def interactive_search(ehx_file_path: str):
    """Run interactive search session"""
    try:
        search_tool = EHXInteractiveSearch(ehx_file_path)

        print("\n" + "="*50)
        print("EHX Interactive Search Tool")
        print("="*50)
        print("Type 'help' for commands, 'quit' to exit")
        print()

        while True:
            try:
                query = input("EHX> ").strip()
                if query.lower() in ['quit', 'exit', 'q']:
                    print("Goodbye!")
                    break

                result = search_tool.search(query)
                print(result)
                print()

            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
            except EOFError:
                print("\nGoodbye!")
                break

    except Exception as e:
        print(f"Error: {e}")


def main():
    """Main entry point"""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python ehx_interactive_search.py <ehx_file>")
        print("Example: python ehx_interactive_search.py 07-103-104.EHX")
        return

    ehx_file = sys.argv[1]

    if len(sys.argv) > 2 and sys.argv[2] == "--batch":
        # Batch mode for testing
        search_tool = EHXInteractiveSearch(ehx_file)
        test_queries = [
            "help",
            "panels",
            "07_103",
            "materials sheathing",
            "sheathing 07_103",
            "bundles",
            "count sheathing",
            "detail 07_103"
        ]

        print("Running batch test queries...")
        for query in test_queries:
            print(f"\n--- Query: {query} ---")
            result = search_tool.search(query)
            print(result)
    else:
        # Interactive mode
        interactive_search(ehx_file)


if __name__ == "__main__":
    main()
