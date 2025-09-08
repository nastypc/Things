#!/usr/bin/env python3
"""
EHX Query Tool - Database-style access to EHX files
Extract specific information on-demand without full parsing
"""

import xml.etree.ElementTree as ET
from pathlib import Path
import re
from typing import Dict, List, Optional, Tuple

class EHXQueryTool:
    """Query EHX files like a database for specific construction information"""

    def __init__(self, ehx_file_path: str):
        """Initialize with EHX file path"""
        self.file_path = Path(ehx_file_path)
        if not self.file_path.exists():
            raise FileNotFoundError(f"EHX file not found: {ehx_file_path}")

        # Parse XML tree for querying
        self.tree = ET.parse(ehx_file_path)
        self.root = self.tree.getroot()

    def get_panel_info(self, panel_label: str) -> Optional[Dict]:
        """Get basic information about a specific panel"""
        panel = self.root.find(f".//Panel[Label='{panel_label}']")
        if panel is None:
            return None

        return {
            'label': panel.find('Label').text if panel.find('Label') is not None else '',
            'guid': panel.find('PanelGuid').text if panel.find('PanelGuid') is not None else '',
            'level_guid': panel.find('LevelGuid').text if panel.find('LevelGuid') is not None else '',
            'bundle_guid': panel.find('BundleGuid').text if panel.find('BundleGuid') is not None else ''
        }

    def get_panel_sheathing(self, panel_label: str) -> List[Dict]:
        """
        Get sheathing information for a specific panel
        Handles multiple layers and different material types
        Returns: List of sheathing pieces with material, dimensions, quantity
        """
        # Find the panel
        panel_info = self.get_panel_info(panel_label)
        if not panel_info:
            return []

        # Find all sheathing (sheets) associated with this panel
        sheathing_data = []

        # Query for sheets with matching PanelGuid
        sheets = self.root.findall(f".//Sheet[PanelGuid='{panel_info['guid']}']")

        for sheet in sheets:
            # Extract material info from nested Material element
            material_info = self._extract_material_info(sheet)

            sheet_info = {
                'material': material_info['description'],
                'label': sheet.find('Label').text if sheet.find('Label') is not None else '',
                'length': material_info['actual_length'],
                'width': material_info['actual_width'],
                'thickness': material_info['actual_thickness'],
                'quantity': 1,  # Each sheet element represents one piece
                'guid': sheet.find('BoardGuid').text if sheet.find('BoardGuid') is not None else '',
                'layer_type': self._classify_sheathing_layer(material_info['description']),
                'size': material_info['size'],
                'board_feet': material_info['board_feet']
            }
            sheathing_data.append(sheet_info)

        return sheathing_data

    def _extract_material_info(self, sheet_element) -> Dict:
        """Extract material information from nested Material element"""
        material_elem = sheet_element.find('Material')
        if material_elem is None:
            return {
                'description': 'Unknown',
                'actual_length': None,
                'actual_width': None,
                'actual_thickness': None,
                'size': None,
                'board_feet': None
            }

        return {
            'description': material_elem.find('Description').text if material_elem.find('Description') is not None else 'Unknown',
            'actual_length': material_elem.find('ActualLength').text if material_elem.find('ActualLength') is not None else None,
            'actual_width': material_elem.find('ActualWidth').text if material_elem.find('ActualWidth') is not None else None,
            'actual_thickness': material_elem.find('ActualThickness').text if material_elem.find('ActualThickness') is not None else None,
            'size': material_elem.find('Size').text if material_elem.find('Size') is not None else None,
            'board_feet': material_elem.find('BoardFeet').text if material_elem.find('BoardFeet') is not None else None
        }

    def _classify_sheathing_layer(self, description: str) -> str:
        """Classify sheathing by material description"""
        if not description:
            return 'Unknown'

        desc_lower = description.lower()

        # Classify by material description
        if 'osb' in desc_lower or 'oriented' in desc_lower:
            return 'Structural Sheathing (OSB)'
        elif 'plywood' in desc_lower or 'ply' in desc_lower:
            return 'Structural Sheathing (Plywood)'
        elif 'gypsum' in desc_lower or 'drywall' in desc_lower:
            return 'Interior Finish (Gypsum)'
        elif 'cement' in desc_lower or 'fiber' in desc_lower:
            return 'Exterior Sheathing (Fiber Cement)'
        elif 'foam' in desc_lower or 'insulation' in desc_lower:
            return 'Insulation Layer'
        elif 'bp' in desc_lower or 'building paper' in desc_lower:
            return 'Building Paper/Wrap'
        else:
            return f'Sheathing ({description})'

    def get_bundle_sheathing_analysis(self, bundle_guid: str) -> Dict:
        """
        Analyze all sheathing in a bundle
        Useful for understanding exterior vs interior wall patterns
        """
        # Find all panels in this bundle
        panels = self.root.findall(f".//Panel[BundleGuid='{bundle_guid}']")

        bundle_analysis = {
            'bundle_guid': bundle_guid,
            'total_panels': len(panels),
            'panels_with_sheathing': 0,
            'total_sheathing_pieces': 0,
            'layer_breakdown': {},
            'material_breakdown': {},
            'panel_details': []
        }

        for panel in panels:
            panel_label = panel.find('Label').text if panel.find('Label') is not None else 'Unknown'
            panel_guid = panel.find('PanelGuid').text if panel.find('PanelGuid') is not None else ''

            # Get sheathing for this panel
            sheathing = self.get_panel_sheathing(panel_label)

            panel_detail = {
                'panel_label': panel_label,
                'panel_guid': panel_guid,
                'sheathing_count': len(sheathing),
                'layers': []
            }

            if sheathing:
                bundle_analysis['panels_with_sheathing'] += 1
                bundle_analysis['total_sheathing_pieces'] += len(sheathing)

                for piece in sheathing:
                    layer_type = piece['layer_type']
                    material = piece['material']

                    # Track layer types
                    if layer_type not in bundle_analysis['layer_breakdown']:
                        bundle_analysis['layer_breakdown'][layer_type] = 0
                    bundle_analysis['layer_breakdown'][layer_type] += 1

                    # Track materials
                    if material not in bundle_analysis['material_breakdown']:
                        bundle_analysis['material_breakdown'][material] = 0
                    bundle_analysis['material_breakdown'][material] += 1

                    panel_detail['layers'].append({
                        'material': material,
                        'layer_type': layer_type,
                        'dimensions': f"{piece['length']}\" x {piece['width']}\""
                    })

            bundle_analysis['panel_details'].append(panel_detail)

        return bundle_analysis

    def calculate_multi_layer_sheet_requirements(self, panel_label: str) -> Dict:
        """
        Calculate sheet requirements for multiple sheathing layers
        Returns separate calculations for each layer type
        """
        sheathing = self.get_panel_sheathing(panel_label)
        if not sheathing:
            return {'layers': {}, 'total_estimated_sheets': 0}

        layer_calculations = {}
        total_sheets = 0

        # Group by layer type
        layers_by_type = {}
        for piece in sheathing:
            layer_type = piece['layer_type']
            if layer_type not in layers_by_type:
                layers_by_type[layer_type] = []
            layers_by_type[layer_type].append(piece)

        # Calculate for each layer type
        for layer_type, pieces in layers_by_type.items():
            layer_calc = self._calculate_layer_requirements(pieces, layer_type)
            layer_calculations[layer_type] = layer_calc
            total_sheets += layer_calc['estimated_sheets']

        return {
            'layers': layer_calculations,
            'total_estimated_sheets': round(total_sheets, 1),
            'layer_count': len(layer_calculations)
        }

    def _calculate_layer_requirements(self, pieces: List[Dict], layer_type: str) -> Dict:
        """Calculate sheet requirements for a specific layer type"""
        total_area = 0
        details = []

        # Standard sheet sizes by material type
        sheet_sizes = {
            'Structural Sheathing (OSB)': (96, 48),  # 8' x 4'
            'Structural Sheathing (Plywood)': (96, 48),  # 8' x 4'
            'Interior Finish (Gypsum)': (96, 48),  # 8' x 4'
            'Exterior Sheathing (Fiber Cement)': (96, 48),  # 8' x 4'
        }

        sheet_length, sheet_width = sheet_sizes.get(layer_type, (96, 48))  # Default 8' x 4'
        sheet_area_sq_inches = sheet_length * sheet_width

        for piece in pieces:
            try:
                length = float(piece['length']) if piece['length'] else 0
                width = float(piece['width']) if piece['width'] else 0
                area = length * width
                total_area += area

                details.append({
                    'label': piece['label'],
                    'dimensions': f"{length}\" x {width}\"",
                    'area_sq_ft': round(area / 144, 2)
                })
            except (ValueError, TypeError):
                continue

        estimated_sheets = total_area / sheet_area_sq_inches if sheet_area_sq_inches > 0 else 0

        return {
            'piece_count': len(pieces),
            'total_area_sq_ft': round(total_area / 144, 2),
            'estimated_sheets': round(estimated_sheets, 1),
            'standard_sheet_size': f"{sheet_length//12}' x {sheet_width//12}'",
            'details': details
        }

    def get_panel_materials_summary(self, panel_label: str) -> Dict:
        """
        Get complete material summary for a panel
        Returns organized breakdown by material type
        """
        panel_info = self.get_panel_info(panel_label)
        if not panel_info:
            return {}

        summary = {
            'panel_info': panel_info,
            'sheathing': self.get_panel_sheathing(panel_label),
            'framing': self._get_panel_framing(panel_label),
            'headers': self._get_panel_headers(panel_label),
            'bracing': self._get_panel_bracing(panel_label)
        }

        return summary

    def _get_panel_framing(self, panel_label: str) -> List[Dict]:
        """Get framing members for a panel"""
        panel_info = self.get_panel_info(panel_label)
        if not panel_info:
            return []

        framing_data = []
        boards = self.root.findall(f".//Board[PanelGuid='{panel_info['guid']}']")

        for board in boards:
            # Skip headers (they're handled separately)
            family_name = board.find('FamilyMemberName')
            if family_name is not None and 'Header' in family_name.text:
                continue

            board_info = {
                'material': family_name.text if family_name is not None else 'Unknown',
                'label': board.find('Label').text if board.find('Label') else '',
                'length': self._extract_dimension(board, 'Length'),
                'width': self._extract_dimension(board, 'Width'),
                'thickness': self._extract_dimension(board, 'Thickness'),
                'quantity': 1,
                'guid': board.find('BoardGuid').text if board.find('BoardGuid') else ''
            }
            framing_data.append(board_info)

        return framing_data

    def _get_panel_headers(self, panel_label: str) -> List[Dict]:
        """Get header information for a panel"""
        panel_info = self.get_panel_info(panel_label)
        if not panel_info:
            return []

        headers = []
        boards = self.root.findall(f".//Board[PanelGuid='{panel_info['guid']}']")

        for board in boards:
            family_name = board.find('FamilyMemberName')
            if family_name is not None and 'Header' in family_name.text:
                header_info = {
                    'material': family_name.text,
                    'label': board.find('Label').text if board.find('Label') else '',
                    'length': self._extract_dimension(board, 'Length'),
                    'width': self._extract_dimension(board, 'Width'),
                    'thickness': self._extract_dimension(board, 'Thickness'),
                    'quantity': 1,
                    'guid': board.find('BoardGuid').text if board.find('BoardGuid') else ''
                }
                headers.append(header_info)

        return headers

    def _get_panel_bracing(self, panel_label: str) -> List[Dict]:
        """Get bracing information for a panel"""
        panel_info = self.get_panel_info(panel_label)
        if not panel_info:
            return []

        bracing_data = []
        bracings = self.root.findall(f".//Bracing[PanelGuid='{panel_info['guid']}']")

        for bracing in bracings:
            bracing_info = {
                'material': bracing.find('FamilyMemberName').text if bracing.find('FamilyMemberName') else 'Unknown',
                'label': bracing.find('Label').text if bracing.find('Label') else '',
                'length': self._extract_dimension(bracing, 'Length'),
                'width': self._extract_dimension(bracing, 'Width'),
                'thickness': self._extract_dimension(bracing, 'Thickness'),
                'quantity': 1,
                'guid': bracing.find('BracingGuid').text if bracing.find('BracingGuid') else ''
            }
            bracing_data.append(bracing_info)

        return bracing_data

    def _extract_dimension(self, element, dimension_name: str) -> Optional[str]:
        """Extract dimension value from XML element"""
        dim_elem = element.find(f'.//{dimension_name}')
        if dim_elem is not None:
            return dim_elem.text
        return None

    def calculate_sheet_requirements(self, panel_label: str, sheet_length: float = 8.0, sheet_width: float = 4.0) -> Dict:
        """
        Calculate how many full sheets are needed for sheathing
        Assumes standard sheet sizes (8' x 4' by default)
        """
        sheathing = self.get_panel_sheathing(panel_label)
        if not sheathing:
            return {'total_pieces': 0, 'estimated_sheets': 0, 'details': []}

        total_area = 0
        details = []

        for piece in sheathing:
            try:
                length = float(piece['length']) if piece['length'] else 0
                width = float(piece['width']) if piece['width'] else 0
                area = length * width
                total_area += area

                details.append({
                    'label': piece['label'],
                    'dimensions': f"{length}\" x {width}\"",
                    'area_sq_ft': round(area / 144, 2)  # Convert sq inches to sq feet
                })
            except (ValueError, TypeError):
                continue

        sheet_area = sheet_length * sheet_width
        estimated_sheets = total_area / (sheet_area * 144)  # Convert back to sq inches

        return {
            'total_pieces': len(sheathing),
            'total_area_sq_ft': round(total_area / 144, 2),
            'estimated_sheets': round(estimated_sheets, 1),
            'standard_sheet_size': f"{sheet_length}' x {sheet_width}'",
            'details': details
        }


def main():
    """Example usage of the EHX Query Tool"""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python ehx_query_tool.py <ehx_file> [panel_label] [--bundle-analysis]")
        print("Examples:")
        print("  python ehx_query_tool.py 07-103-104.EHX 07_103")
        print("  python ehx_query_tool.py 07-103-104.EHX --bundle-analysis")
        return

    ehx_file = sys.argv[1]

    try:
        # Initialize query tool
        query_tool = EHXQueryTool(ehx_file)

        if len(sys.argv) > 2 and sys.argv[2] == "--bundle-analysis":
            # Bundle-level analysis
            print(f"\n=== Bundle-Level Sheathing Analysis ===")
            bundles = query_tool.root.findall(".//Panel/BundleGuid")
            unique_bundles = set()
            for bundle in bundles:
                if bundle.text:
                    unique_bundles.add(bundle.text)

            for bundle_guid in unique_bundles:
                analysis = query_tool.get_bundle_sheathing_analysis(bundle_guid)
                if analysis['panels_with_sheathing'] > 0:
                    print(f"\nBundle {bundle_guid[:8]}...: {analysis['panels_with_sheathing']}/{analysis['total_panels']} panels have sheathing")
                    print(f"  Total pieces: {analysis['total_sheathing_pieces']}")
                    print("  Layer breakdown:")
                    for layer, count in analysis['layer_breakdown'].items():
                        print(f"    {layer}: {count} pieces")
        else:
            # Panel-specific analysis
            panel_label = sys.argv[2] if len(sys.argv) > 2 else "07_103"

            print(f"\n=== Multi-Layer Sheathing Analysis for Panel {panel_label} ===")

            # Get sheathing with layer classification
            sheathing = query_tool.get_panel_sheathing(panel_label)

            if sheathing:
                print(f"Found {len(sheathing)} sheathing pieces across {len(set(p['layer_type'] for p in sheathing))} layer types:")

                # Group by layer type for display
                layers = {}
                for piece in sheathing:
                    layer = piece['layer_type']
                    if layer not in layers:
                        layers[layer] = []
                    layers[layer].append(piece)

                for layer_type, pieces in layers.items():
                    print(f"\n--- {layer_type} ({len(pieces)} pieces) ---")
                    for i, piece in enumerate(pieces, 1):
                        print(f"  {i}. {piece['material']} - {piece['label']}")
                        print(f"     Dimensions: {piece['length']}\" x {piece['width']}\" x {piece['thickness']}\"")

                # Multi-layer sheet calculations
                print(f"\n=== Sheet Requirements by Layer ===")
                multi_calc = query_tool.calculate_multi_layer_sheet_requirements(panel_label)

                for layer_type, calc in multi_calc['layers'].items():
                    print(f"\n{layer_type}:")
                    print(f"  Pieces: {calc['piece_count']}")
                    print(f"  Total area: {calc['total_area_sq_ft']} sq ft")
                    print(f"  Estimated {calc['standard_sheet_size']} sheets: {calc['estimated_sheets']}")

                print(f"\nTOTAL ESTIMATED SHEETS: {multi_calc['total_estimated_sheets']} sheets")
            else:
                print(f"No sheathing found for panel {panel_label}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
