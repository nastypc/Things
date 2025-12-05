from enum import Enum
import math
import re
import tkinter as tk
from tkinter import filedialog, messagebox
import os
import json
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

FLYOVER_THRESHOLD_MM = 27.0 * 25.4  # 27 inches expressed in millimetres
GLUE_EDGE_OFFSET = 50.8  # Maintain glue lines 2 inches (50.8 mm) away from panel edges
MAX_STA_NUDGE = 0.75  # Maximum automatic STA shift (mm) when clearing overlaps
SHEET_FLIP_THICKNESS = 18.0  # Default sheet thickness moved during sheet flip operations
PERIMETER_NL_SPACING = 152.4  # 6"
FIELD_NL_SPACING = 304.8  # 12"
TONGUE_GROOVE_EDGE_OFFSET = 12.7  # 1/2"
SQUARE_EDGE_OFFSET = 6.35  # 1/4"
MEMBER_END_FASTENER_OFFSET = 76.2  # 3"
PANEL_EDGE_TOLERANCE = 25.4  # Treat rows within 1" of a panel edge as perimeter
HORIZONTAL_ROW_SNAP_TOLERANCE = 1.0  # mm tolerance to merge near-identical NL rows
SHORT_CASSETTE_MIN_Y = 5 * 12 * 25.4  # 5 ft in mm
SHORT_CASSETTE_FULL_Y = 8 * 12 * 25.4  # 8 ft in mm
GL_DEDUPE_TOLERANCE = 5.0  # mm tolerance when collapsing duplicate glue lines
NL_STA_ALIGNMENT_TOLERANCE = 38.1  # Vertical tolerance when snapping STA coverage to nearby NL rows
GL_STA_ALIGNMENT_TOLERANCE = 38.1  # Vertical tolerance when snapping STA glue to nearby rows

# Load user presets from src/config.json when available. Presets may override
# defaults for sheet-flip behavior (nl edge offset, spacings, member edge distance).
try:
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as cf:
            cfg = json.load(cf)
            PRESETS = cfg.get('presets', {}) if isinstance(cfg, dict) else {}
except Exception:
    PRESETS = {}

# Effective glue inset (configurable via src/config.json -> presets.glue_edge_offset)
GLUE_EDGE = float(PRESETS.get('glue_edge_offset', GLUE_EDGE_OFFSET))
PERIMETER_NL_SPACING = float(PRESETS.get('perimeter_nl_spacing', PERIMETER_NL_SPACING))
FIELD_NL_SPACING = float(PRESETS.get('field_nl_spacing', FIELD_NL_SPACING))
TONGUE_GROOVE_EDGE_OFFSET = float(PRESETS.get('tongue_groove_edge_offset', TONGUE_GROOVE_EDGE_OFFSET))
SQUARE_EDGE_OFFSET = float(PRESETS.get('square_edge_offset', SQUARE_EDGE_OFFSET))
MEMBER_END_FASTENER_OFFSET = float(PRESETS.get('member_end_fastener_offset', MEMBER_END_FASTENER_OFFSET))


class ELF(Enum):
    OUTSIDE = "outside"
    UP = "up"
    # Add other orientations if needed, e.g., INSIDE, DOWN

class CDTHeader:
    def __init__(self, x_size: float, y_size: float, z_size: float, element_type: int, length: float, measurement: float, quality: float):
        self.x_size = x_size
        self.y_size = y_size
        self.z_size = z_size
        self.element_type = element_type
        self.length = length
        self.measurement = measurement
        self.quality = quality

    @classmethod
    def from_elm_line(cls, line: str) -> 'CDTHeader':
        parts = line.rstrip(';').split(':')
        if len(parts) != 8 or parts[0] != 'ELM':
            raise ValueError(f"Invalid ELM line format: {line}")
        x_size = float(parts[1].strip())
        y_size = float(parts[2].strip())
        z_size = float(parts[3].strip())
        element_type = int(parts[4].strip())
        length = float(parts[5].strip())
        measurement = float(parts[6].strip())
        quality = float(parts[7].strip())
        return cls(x_size, y_size, z_size, element_type, length, measurement, quality)

    def __repr__(self):
        return f"CDTHeader(x_size={self.x_size}, y_size={self.y_size}, z_size={self.z_size}, element_type={self.element_type}, length={self.length}, measurement={self.measurement}, quality={self.quality})"

class SheathingElement:
    def __init__(self, element_type: str, x_size: float, y_size: float, z_size: float, x: float, y: float, z: float, tool_index: int, name: str, raw: str = ""):
        self.element_type = element_type  # e.g., 'BOO1', 'BOI1'
        self.x_size = x_size
        self.y_size = y_size
        self.z_size = z_size
        self.x = x
        self.y = y
        self.z = z
        self.tool_index = tool_index
        self.name = name
        self.original_x = x  # Store original x position
        self.original_x_size = x_size  # Store original x_size
        self.original_y = y
        self.original_y_size = y_size
        self.raw = raw

    @classmethod
    def from_cdt_line(cls, line: str) -> 'SheathingElement':
        # Remove trailing semicolon and split by ':'
        parts = line.rstrip(';').split(':')
        if len(parts) < 8:
            raise ValueError(f"Invalid CDT line format: {line}")
        element_type = parts[0].strip()
        x_size = float(parts[1].strip())
        y_size = float(parts[2].strip())
        z_size = float(parts[3].strip())
        x = float(parts[4].strip())
        y = float(parts[5].strip())
        z = float(parts[6].strip())
        tool_index = int(parts[7].strip())
        name = ':'.join(parts[8:]).strip() if len(parts) > 8 else ''
        return cls(element_type, x_size, y_size, z_size, x, y, z, tool_index, name, raw=line)

    def __repr__(self):
        return f"SheathingElement(type={self.element_type}, x_size={self.x_size}, y_size={self.y_size}, z_size={self.z_size}, x={self.x}, y={self.y}, z={self.z}, tool_index={self.tool_index}, name={self.name})"

class GlueLine:
    def __init__(self, x_start: float, y_start: float, z_start: float, x_end: float, y_end: float, z_end: float,
                 amplitude: float, wavelength: float, tool_index: int, raw: Optional[str] = None, widths: Optional[List[int]] = None):
        self.x_start = x_start
        self.y_start = y_start
        self.z_start = z_start
        self.x_end = x_end
        self.y_end = y_end
        self.z_end = z_end
        self.amplitude = amplitude
        self.wavelength = wavelength
        self.tool_index = tool_index
        self.raw = raw
        self.widths = widths

    @classmethod
    def from_line(cls, line: str) -> 'GlueLine':
        raw = line.rstrip('\n')
        stripped = raw.rstrip(';')
        parts = stripped.split(':')
        if len(parts) != 10 or parts[0].strip() != 'GL':
            raise ValueError(f"Invalid GL line format: {line}")
        widths = [len(part) for part in parts[1:]]
        values = [part.strip() for part in parts[1:]]
        x_start = float(values[0])
        y_start = float(values[1])
        z_start = float(values[2])
        x_end = float(values[3])
        y_end = float(values[4])
        z_end = float(values[5])
        amplitude = float(values[6])
        wavelength = float(values[7])
        tool_index = int(round(float(values[8])))
        return cls(x_start, y_start, z_start, x_end, y_end, z_end, amplitude, wavelength, tool_index, raw=raw, widths=widths)

    def orientation(self, tolerance: float = 1e-3) -> str:
        dx = abs(self.x_end - self.x_start)
        dy = abs(self.y_end - self.y_start)
        if dx <= tolerance and dy <= tolerance:
            return 'point'
        if dx <= tolerance:
            return 'vertical'
        if dy <= tolerance:
            return 'horizontal'
        return 'angled'

    def group_key(self, tolerance: float = 1e-3):
        orient = self.orientation(tolerance)
        if orient == 'horizontal':
            y_mid = 0.5 * (self.y_start + self.y_end)
            z_mid = 0.5 * (self.z_start + self.z_end)
            return (orient, round(y_mid, 3), round(z_mid, 3))
        if orient == 'vertical':
            x_mid = 0.5 * (self.x_start + self.x_end)
            z_mid = 0.5 * (self.z_start + self.z_end)
            return (orient, round(x_mid, 3), round(z_mid, 3))
        return (orient, round(self.x_start, 3), round(self.y_start, 3), round(self.z_start, 3))

    def to_string(self, fmt_value) -> str:
        return self.format_with(fmt_value, self.x_start, self.y_start, self.z_start, self.x_end, self.y_end, self.z_end, self.amplitude, self.wavelength, self.tool_index)

    def format_with(self, fmt_value, x_start: float, y_start: float, z_start: float, x_end: float, y_end: float, z_end: float,
                    amplitude: float, wavelength: float, tool_index: int) -> str:
        return self._format(fmt_value, x_start, y_start, z_start, x_end, y_end, z_end, amplitude, wavelength, tool_index, self.widths)

    @staticmethod
    def default_format(fmt_value, x_start: float, y_start: float, z_start: float, x_end: float, y_end: float, z_end: float,
                       amplitude: float, wavelength: float, tool_index: int) -> str:
        return GlueLine._format(fmt_value, x_start, y_start, z_start, x_end, y_end, z_end, amplitude, wavelength, tool_index, None)

    @staticmethod
    def _format(fmt_value, x_start: float, y_start: float, z_start: float, x_end: float, y_end: float, z_end: float,
                amplitude: float, wavelength: float, tool_index: int, widths: Optional[List[int]]) -> str:
        widths = widths or [0] * 9
        values = [x_start, y_start, z_start, x_end, y_end, z_end, amplitude, wavelength, tool_index]
        formatted = []
        for idx, value in enumerate(values):
            width = widths[idx] if idx < len(widths) else 0
            if idx == 8:
                text = str(int(round(value)))
                if width:
                    text = f"{text:>{max(width, len(text))}}"
            else:
                text = fmt_value(value, width)
            formatted.append(text)
        return 'GL:' + ':'.join(formatted) + ';'


class RoutingStart:
    def __init__(self, x: float, y: float, z: float, tool_index: int, raw: Optional[str] = None, widths: Optional[List[int]] = None):
        self.x = x
        self.y = y
        self.z = z
        self.tool_index = tool_index
        self.raw = raw
        self.widths = widths
    @classmethod
    def from_line(cls, line: str) -> 'RoutingStart':
        raw = line.rstrip('\n')
        stripped = raw.rstrip(';')
        parts = stripped.split(':')
        if len(parts) != 5 or parts[0].strip() != 'ROB':
            raise ValueError(f"Invalid ROB line format: {line}")
        widths = [len(part) for part in parts[1:]]
        values = [part.strip() for part in parts[1:]]
        x = float(values[0])
        y = float(values[1])
        z = float(values[2])
        tool_index = int(round(float(values[3])))
        return cls(x, y, z, tool_index, raw=raw, widths=widths)

    def copy(self) -> 'RoutingStart':
        return RoutingStart(self.x, self.y, self.z, self.tool_index, widths=list(self.widths) if self.widths else None)

    def mirror(self, span_x: float):
        self.x = round(span_x - self.x, 6)

    def to_string(self, fmt_value) -> str:
        widths = self.widths or [0, 0, 0, 0]
        tool_width = max(widths[3], len(str(self.tool_index)))
        parts = [
            'ROB',
            fmt_value(self.x, widths[0]),
            fmt_value(self.y, widths[1]),
            fmt_value(self.z, widths[2]),
            f"{self.tool_index:>{tool_width}}"
        ]
        return ':'.join(parts) + ';'


class RoutingLine:
    def __init__(self, x: float, y: float, z: float, radius: float, raw: Optional[str] = None, widths: Optional[List[int]] = None):
        self.x = x
        self.y = y
        self.z = z
        self.radius = radius
        self.raw = raw
        self.widths = widths

    @classmethod
    def from_line(cls, line: str) -> 'RoutingLine':
        raw = line.rstrip('\n')
        stripped = raw.rstrip(';')
        parts = stripped.split(':')
        if len(parts) != 5 or parts[0].strip() != 'RL':
            raise ValueError(f"Invalid RL line format: {line}")
        widths = [len(part) for part in parts[1:]]
        values = [part.strip() for part in parts[1:]]
        x = float(values[0])
        y = float(values[1])
        z = float(values[2])
        radius = float(values[3])
        return cls(x, y, z, radius, raw=raw, widths=widths)

    def copy(self) -> 'RoutingLine':
        return RoutingLine(self.x, self.y, self.z, self.radius, widths=list(self.widths) if self.widths else None)

    def mirror(self, span_x: float):
        self.x = round(span_x - self.x, 6)
        self.radius = -self.radius

    def to_string(self, fmt_value) -> str:
        widths = self.widths or [0, 0, 0, 0]
        parts = [
            'RL',
            fmt_value(self.x, widths[0]),
            fmt_value(self.y, widths[1]),
            fmt_value(self.z, widths[2]),
            fmt_value(self.radius, widths[3])
        ]
        return ':'.join(parts) + ';'


class RoutingBlock:
    def __init__(self, start: RoutingStart):
        self.start = start
        self.points: List[RoutingLine] = []
        self.has_end = False

class Sheathing:
    def __init__(self, elf: ELF):
        self.elf = elf

    def get_z_for_layer(self, layer: str) -> int:
        """
        Returns Z coordinate sign based on layer and ELF.
        Positive for outside layer, negative for inside layer when ELF is OUTSIDE or UP.
        """
        if self.elf in [ELF.OUTSIDE, ELF.UP]:
            return 1 if layer == "outside" else -1
        else:
            # For other ELF, perhaps reverse or something, but not specified
            return -1 if layer == "outside" else 1  # assuming reverse for now

class BOI(Sheathing):
    """Board On Inside"""
    def __init__(self, elf: ELF):
        super().__init__(elf)
        self.layer = "inside"

class BOO(Sheathing):
    """Board On Outside"""
    def __init__(self, elf: ELF):
        super().__init__(elf)
        self.layer = "outside"

class CDTFile:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.header = None
        self.elements = []
        self.sta_elements = []
        self.lines = []  # Keep original lines for modification
        self.gl_lines: List[GlueLine] = []
        self.routing_blocks: List[RoutingBlock] = []
        self.length_warnings: List[str] = []
        self.flyover_extension: float = 0.0
        self.last_sheet_mode: str = "trimmed"
        self.last_sheet_target: float = 0.0
        self.last_sheet_gap: float = 0.0
        self.original_x_span: Optional[float] = None
        self.glue_edge_offset: float = 50.8
        self.sheet_flip: bool = False
        self.allow_negative_overhang: bool = False
        self.full_sheet_reference: float = 0.0
        self.emit_saw_lines: bool = False

    def parse(self):
        with open(self.file_path, 'r') as f:
            self.lines = f.readlines()
        
        current_routing: Optional[RoutingBlock] = None

        for raw_line in self.lines:
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith('ELM:'):
                self.header = CDTHeader.from_elm_line(line)
                if self.original_x_span is None:
                    self.original_x_span = self.header.x_size
            elif line.startswith('STA:') or line.startswith('STB:'):
                elem = SheathingElement.from_cdt_line(line)
                self.sta_elements.append(elem)
            elif line.startswith('BOO1:') or line.startswith('BOI'):
                # Parse sheathing elements
                element = SheathingElement.from_cdt_line(line)
                self.elements.append(element)
            elif line.startswith('GL:'):
                try:
                    self.gl_lines.append(GlueLine.from_line(line))
                except ValueError:
                    pass
            elif line.startswith('ROB:'):
                try:
                    start = RoutingStart.from_line(raw_line)
                    current_routing = RoutingBlock(start)
                    self.routing_blocks.append(current_routing)
                except ValueError:
                    current_routing = None
            elif line.startswith('RL:'):
                if current_routing is not None:
                    try:
                        current_routing.points.append(RoutingLine.from_line(raw_line))
                    except ValueError:
                        pass
            elif line.startswith('ROE'):
                if current_routing is not None:
                    current_routing.has_end = True
                    current_routing = None
            elif line == 'EOF;':
                break  # End of file

    def compute_y_span(self, sheathing_elements):
        """Return (min_y, max_y) across structural elements and sheathing."""
        min_y = float('inf')
        max_y = float('-inf')

        for elem in sheathing_elements:
            min_y = min(min_y, elem.y)
            max_y = max(max_y, elem.y + elem.y_size)

        for elem in self.sta_elements:
            min_y = min(min_y, elem.y)
            max_y = max(max_y, elem.y + elem.y_size)

        if min_y == float('inf') or max_y == float('-inf'):
            return 0.0, 0.0
        return min_y, max_y

    def get_sheathing_elements(self):
        return [elem for elem in self.elements if elem.element_type.startswith('BOO') or elem.element_type.startswith('BOI')]

    def get_all_structural_elements(self):
        return self.sta_elements + self.get_sheathing_elements()

    @staticmethod
    def elements_overlap(elem_a: SheathingElement, elem_b: SheathingElement, tolerance: float = 0.0) -> bool:
        ax1, ax2 = elem_a.x, elem_a.x + elem_a.x_size
        ay1, ay2 = elem_a.y, elem_a.y + elem_a.y_size
        bx1, bx2 = elem_b.x, elem_b.x + elem_b.x_size
        by1, by2 = elem_b.y, elem_b.y + elem_b.y_size

        x_overlap = ax1 < bx2 - tolerance and ax2 > bx1 + tolerance
        y_overlap = ay1 < by2 - tolerance and ay2 > by1 + tolerance
        return x_overlap and y_overlap

    @staticmethod
    def _parse_expected_length(description: str) -> Optional[float]:
        if not description:
            return None
        parts = description.split(':')
        candidates: List[float] = []
        for part in parts:
            token = part.strip()
            if not token:
                continue
            if re.fullmatch(r'-?\d+(?:\.\d+)?', token):
                try:
                    value = float(token)
                except ValueError:
                    continue
                if value > 0:
                    candidates.append(value)
        if candidates:
            return candidates[-1]
        return None

    def adjust_sheathing_positions(self, actual_lengths: dict):
        """
        Adjust x positions of sheathing elements based on actual lengths.
        actual_lengths: dict like {1219.2: 1207.0} for actual length in mm per programmed size
        """
        actual_lengths = actual_lengths or {}
        self.actual_length_lookup = actual_lengths
        self.allow_negative_overhang = False
        cumulative_x = 0.0
        for elem in self.elements:
            if elem.element_type.startswith('BOO') and elem.x_size in actual_lengths:
                actual_length = actual_lengths[elem.x_size]
                elem.x = cumulative_x
                elem.x_size = actual_length
                cumulative_x += actual_length
            else:
                # If no adjustment, keep original but update cumulative
                elem.x = cumulative_x
                cumulative_x += elem.x_size
        
        # Adjust the last BOO1 element's x_size and x position
        boo_elements = [elem for elem in self.elements if elem.element_type.startswith('BOO')]
        if boo_elements and self.header:
            original_span = self.original_x_span if self.original_x_span is not None else self.header.x_size
            original_span = round(original_span, 2)

            full_sheet_original = max(elem.original_x_size for elem in boo_elements)
            full_sheet_target = self.actual_length_lookup.get(full_sheet_original, full_sheet_original)
            full_sheet_target = round(full_sheet_target, 2)
            self.full_sheet_reference = full_sheet_target

            consumed = sum(elem.x_size for elem in boo_elements[:-1])
            remaining_raw = original_span - consumed
            if remaining_raw < -0.5:
                self.length_warnings.append(
                    f"Preceding sheathing exceeds footprint by {abs(remaining_raw):.2f}mm; clamping remaining span to 0."
                )
            remaining_raw = max(0.0, remaining_raw)
            remaining = round(remaining_raw, 2)
            self.last_sheet_gap = remaining

            last_elem = boo_elements[-1]

            if remaining <= FLYOVER_THRESHOLD_MM + 0.5:
                target_last = remaining
                self.last_sheet_mode = "trimmed"
            else:
                target_last = full_sheet_target
                self.last_sheet_mode = "flyover"

            if target_last <= 0:
                target_last = round(max(last_elem.x_size, 0.0), 2)

            last_elem.x_size = round(target_last, 2)
            self.last_sheet_target = last_elem.x_size

            for elem in boo_elements[:-1]:
                elem.x_size = round(elem.x_size, 2)

            cumulative = 0.0
            for elem in boo_elements:
                elem.x = cumulative
                cumulative += elem.x_size

            final_sum = round(cumulative, 2)
            self.flyover_extension = max(0.0, final_sum - original_span)
            if self.last_sheet_mode != "flyover" and abs(final_sum - original_span) > 0.5:
                self.length_warnings.append(
                    f"Sheathing total {final_sum:.2f}mm differs from footprint {original_span:.2f}mm."
                )

            preserved_span = round(original_span, 2)
            self.header.x_size = preserved_span
            self.header.length = preserved_span

        self._apply_origin_flyover(boo_elements)
        self._apply_short_cassette_rule(boo_elements)

        self.resolve_structural_overlaps()
        self.offset_horizontal_members()
        self.resolve_structural_overlaps()
        self._clamp_structural_to_span()
    def _clamp_structural_to_span(self):
        if self.header is None:
            return
        span = max(0.0, self.header.x_size)
        for elem in self.sta_elements:
            elem.x = max(0.0, min(elem.x, span))
            elem_end = min(span, elem.x + elem.x_size)
            elem.x_size = max(0.0, elem_end - elem.x)

        # Update ELM Y span based on all components (round up to nearest mm)
        min_y, max_y = self.compute_y_span(self.get_sheathing_elements())
        span = max_y - min_y
        if span < 0:
            span = 0
        if span > 0:
            precise_span = round(span, 2)
            self.header.y_size = precise_span
            self.header.measurement = precise_span
        self.header.quality = self.header.z_size

    def _clamp_element(self, elem: SheathingElement):
        if self.header is None:
            return
        max_x = max(0.0, self.header.x_size - elem.x_size)
        max_y = max(0.0, self.header.y_size - elem.y_size)
        elem.x = min(max(elem.x, 0.0), max_x)
        elem.y = min(max(elem.y, 0.0), max_y)

    @staticmethod
    def _inset_segment(start: float, end: float, inset: float) -> Tuple[float, float]:
        if inset <= 0:
            return start, end
        reversed_segment = end < start
        if reversed_segment:
            start, end = end, start
        length = end - start
        if length <= inset * 2:
            midpoint = 0.5 * (start + end)
            start = end = midpoint
        else:
            start += inset
            end -= inset
        if reversed_segment:
            return end, start
        return start, end

    @staticmethod
    def _segment_gaps(span_start: float, span_end: float, segments: List[Tuple[float, float]], tolerance: float = 0.5) -> List[Tuple[float, float]]:
        if span_end - span_start <= tolerance:
            return []
        normalized: List[Tuple[float, float]] = []
        for seg_start, seg_end in segments:
            if seg_end < seg_start:
                seg_start, seg_end = seg_end, seg_start
            overlap_start = max(span_start, seg_start)
            overlap_end = min(span_end, seg_end)
            if overlap_end - overlap_start > tolerance:
                normalized.append((overlap_start, overlap_end))
        if normalized:
            merged = CDTFile.merge_axis_segments(normalized, tolerance)
        else:
            merged = []
        gaps: List[Tuple[float, float]] = []
        cursor = span_start
        for cov_start, cov_end in merged:
            if cov_start - cursor > tolerance:
                gaps.append((cursor, cov_start))
            cursor = max(cursor, cov_end)
        if span_end - cursor > tolerance:
            gaps.append((cursor, span_end))
        if not merged:
            return [(span_start, span_end)]
        return gaps

    def _ensure_horizontal_group(self, horizontal_nl_groups: Dict[Tuple[str, float, float], Dict[str, Any]], y_value: float, tolerance: float = 1e-3) -> Tuple[Tuple[str, float, float], Dict[str, Any]]:
        y_round = round(y_value, 3)
        best_key: Optional[Tuple[str, float, float]] = None
        best_delta: Optional[float] = None
        for key, info in horizontal_nl_groups.items():
            orient, y_key, _ = key
            if orient != 'horizontal':
                continue
            delta = abs(y_key - y_round)
            if delta <= tolerance and (best_delta is None or delta < best_delta or (math.isclose(delta, best_delta) and info.get('segments'))):
                best_key = key
                best_delta = delta
        if best_key is not None:
            return best_key, horizontal_nl_groups[best_key]
        z_value = self.glue_plane_z if hasattr(self, 'glue_plane_z') else 0.0
        z_round = round(z_value, 3)
        key = ('horizontal', y_round, z_round)
        info = horizontal_nl_groups.setdefault(key, {'segments': []})
        if 'y' not in info:
            info['y'] = y_round
        if 'z' not in info:
            info['z'] = z_value
        return key, info

    @staticmethod
    def _match_horizontal_group(horizontal_nl_groups: Dict[Tuple[str, float, float], Dict[str, Any]], y_value: float,
                                 tolerance: float) -> Tuple[Optional[Tuple[str, float, float]], Optional[Dict[str, Any]]]:
        y_round = round(y_value, 3)
        best_key: Optional[Tuple[str, float, float]] = None
        best_delta: Optional[float] = None
        for key, info in horizontal_nl_groups.items():
            orient, y_key, _ = key
            if orient != 'horizontal':
                continue
            delta = abs(y_key - y_round)
            if delta <= tolerance and (best_delta is None or delta < best_delta):
                best_key = key
                best_delta = delta
        if best_key is None:
            return None, None
        return best_key, horizontal_nl_groups[best_key]

    @staticmethod
    def _preferred_y_for_span(y_value: float, horizontal_nl_groups: Dict[Tuple[str, float, float], Dict[str, Any]],
                              gl_coverage: Dict[float, List[Tuple[float, float]]], tolerance: float,
                              prefer_gl_sources: bool = False) -> float:
        y_round = round(y_value, 3)
        best_y: Optional[float] = None
        best_score: Optional[Tuple[int, float]] = None

        def consider(candidate: float, source_priority: int):
            nonlocal best_y, best_score
            delta = abs(candidate - y_round)
            if delta > tolerance:
                return
            score = (source_priority, delta)
            if best_score is None or score < best_score:
                best_score = score
                best_y = candidate

        for key in horizontal_nl_groups.keys():
            orient, y_key, _ = key
            if orient != 'horizontal':
                continue
            consider(y_key, 0)
        glue_priority = 0 if prefer_gl_sources else 1
        for y_key in gl_coverage.keys():
            consider(y_key, glue_priority)

        return best_y if best_y is not None else y_round

    @staticmethod
    def _register_gl_span(coverage: Dict[float, List[Tuple[float, float]]], y_value: float, start: float, end: float):
        if end < start:
            start, end = end, start
        y_key = round(y_value, 3)
        coverage.setdefault(y_key, []).append((start, end))

    @staticmethod
    def _segments_cover_interval(segments: List[Tuple[float, float]], start: float, end: float,
                                 tolerance: float = 0.5) -> bool:
        target_start = min(start, end)
        target_end = max(start, end)
        if target_end - target_start <= tolerance:
            return True
        for seg_start, seg_end in segments:
            low = min(seg_start, seg_end)
            high = max(seg_start, seg_end)
            if low - tolerance <= target_start and high + tolerance >= target_end:
                return True
        return False

    def _snapped_panel_spans(self, y_value: float, target_start: float, target_end: float,
                              sheathing_panels_for_y, sheathing_spans_for_y,
                              tolerance: float = 0.5) -> Tuple[List[Tuple[float, float]], Optional[float], Optional[float]]:
        panels = sheathing_panels_for_y(y_value)
        snapped: List[Tuple[float, float]] = []
        panel_min: Optional[float] = None
        panel_max: Optional[float] = None
        overlapped_panel = False
        if panels:
            count = len(panels)
            for idx, panel in enumerate(panels):
                panel_start = panel.x
                panel_end = panel.x + panel.x_size
                if panel_end <= target_start - tolerance or panel_start >= target_end + tolerance:
                    continue
                overlapped_panel = True
                has_left_neighbor = idx > 0
                has_right_neighbor = idx < count - 1
                left_offset = MEMBER_END_FASTENER_OFFSET if has_left_neighbor else SQUARE_EDGE_OFFSET
                right_offset = MEMBER_END_FASTENER_OFFSET if has_right_neighbor else SQUARE_EDGE_OFFSET
                usable_start = max(panel_start + left_offset, target_start)
                usable_end = min(panel_end - right_offset, target_end)
                if usable_end - usable_start <= tolerance:
                    continue
                snapped.append((usable_start, usable_end))
                panel_min = panel_start if panel_min is None else min(panel_min, panel_start)
                panel_max = panel_end if panel_max is None else max(panel_max, panel_end)
        if not snapped and not overlapped_panel:
            spans = sheathing_spans_for_y(y_value)
            for span_start, span_end in spans:
                if span_end <= target_start - tolerance or span_start >= target_end + tolerance:
                    continue
                seg_start = max(span_start, target_start)
                seg_end = min(span_end, target_end)
                if seg_end - seg_start > tolerance:
                    snapped.append((seg_start, seg_end))
                    panel_min = span_start if panel_min is None else min(panel_min, span_start)
                    panel_max = span_end if panel_max is None else max(panel_max, span_end)
        if not snapped and not overlapped_panel and target_end - target_start > tolerance:
            snapped.append((target_start, target_end))
            panel_min = target_start if panel_min is None else min(panel_min, target_start)
            panel_max = target_end if panel_max is None else max(panel_max, target_end)
        return snapped, panel_min, panel_max

    def _is_panel_edge_row(self, y_value: float, panels: List[SheathingElement], tolerance: float = PANEL_EDGE_TOLERANCE) -> bool:
        deck_min = getattr(self, 'deck_min_y', None)
        deck_max = getattr(self, 'deck_max_y', None)
        if deck_min is not None and abs(y_value - deck_min) <= tolerance:
            return True
        if deck_max is not None and abs(y_value - deck_max) <= tolerance:
            return True
        if not panels:
            return False
        has_interior_cover = False
        near_any_edge = False
        for panel in panels:
            top = panel.y + panel.y_size
            if (panel.y + tolerance) < y_value < (top - tolerance):
                has_interior_cover = True
            if abs(y_value - panel.y) <= tolerance or abs(y_value - top) <= tolerance:
                near_any_edge = True
        if has_interior_cover:
            return False
        return near_any_edge

    def _snap_horizontal_y(self, y_value: float, registry: List[float], preferred: Optional[List[float]] = None,
                           tolerance: float = HORIZONTAL_ROW_SNAP_TOLERANCE) -> float:
        candidates: List[float] = []
        if preferred:
            candidates.extend(preferred)
        candidates.extend(registry)
        best = None
        best_delta = None
        for candidate in candidates:
            delta = abs(candidate - y_value)
            if delta <= tolerance:
                if best is None or delta < best_delta:
                    best = candidate
                    best_delta = delta
        if best is None:
            registry.append(y_value)
            return y_value
        if best not in registry:
            registry.append(best)
        return best

    def _sta_span_for_y(self, y_value: float) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
        coverage_tol = 0.5
        sta_member: Optional[SheathingElement] = None
        for sta in self.sta_elements:
            if sta.y - coverage_tol <= y_value <= sta.y + sta.y_size + coverage_tol:
                if sta_member is None or sta.x_size > sta_member.x_size:
                    sta_member = sta
        if sta_member is None:
            return None, None, None, None
        raw_start = sta_member.x
        raw_end = sta_member.x + sta_member.x_size
        sta_start = raw_start + MEMBER_END_FASTENER_OFFSET
        sta_end = raw_end - MEMBER_END_FASTENER_OFFSET
        if sta_end <= sta_start + 1e-3:
            return None, None, raw_start, raw_end
        return sta_start, sta_end, raw_start, raw_end

    def _clamp_horizontal_span(self, x_start: float, x_end: float, y_value: float, wall_start: float,
                               wall_end: float, offset: float, sta_start: Optional[float] = None,
                               sta_end: Optional[float] = None) -> Tuple[float, float]:
        reversed_segment = x_start > x_end
        span_start = min(x_start, x_end)
        span_end = max(x_start, x_end)
        span_start = max(span_start, wall_start)
        span_end = min(span_end, wall_end)
        if sta_start is None or sta_end is None:
            fallback_sta_start, fallback_sta_end, _, _ = self._sta_span_for_y(y_value)
            if sta_start is None:
                sta_start = fallback_sta_start
            if sta_end is None:
                sta_end = fallback_sta_end
        if sta_start is not None:
            span_start = max(span_start, sta_start)
        if sta_end is not None:
            span_end = min(span_end, sta_end)
        span_start, span_end = self._inset_segment(span_start, span_end, offset)
        if span_end < span_start:
            span_end = span_start
        if reversed_segment:
            return span_end, span_start
        return span_start, span_end

    @staticmethod
    def _gl_key(x_start: float, y_start: float, z_start: float, x_end: float, y_end: float, z_end: float,
                amplitude: float, wavelength: float, tool_index: float) -> Tuple:
        def q(value: float) -> float:
            if GL_DEDUPE_TOLERANCE <= 0:
                return round(value, 3)
            return round(value / GL_DEDUPE_TOLERANCE) * GL_DEDUPE_TOLERANCE
        return (
            q(x_start),
            q(y_start),
            q(z_start),
            q(x_end),
            q(y_end),
            q(z_end),
            round(amplitude, 3),
            round(wavelength, 3),
            int(round(tool_index))
        )

    def _append_gl_line(self, dest: List[str], seen_keys: Set[Tuple], fmt_value, x_start: float, y_start: float, z_start: float,
                         x_end: float, y_end: float, z_end: float, amplitude: float, wavelength: float, tool_index: int,
                         widths: Optional[List[int]] = None):
        key = self._gl_key(x_start, y_start, z_start, x_end, y_end, z_end, amplitude, wavelength, tool_index)
        if key in seen_keys:
            return
        seen_keys.add(key)
        if widths is None:
            line = GlueLine.default_format(fmt_value, x_start, y_start, z_start, x_end, y_end, z_end, amplitude, wavelength, tool_index)
        else:
            line = GlueLine._format(fmt_value, x_start, y_start, z_start, x_end, y_end, z_end, amplitude, wavelength, tool_index, widths)
        dest.append(line)

    def _clamp_sheathing_to_span(self, span_x: float):
        """Trim mirrored sheathing so it stays within the available span."""
        trimmed_total = 0.0
        for elem in self.elements:
            if not elem.element_type.startswith(('BOO', 'BOI')):
                continue
            start = elem.x
            end = elem.x + elem.x_size
            clamped_start = min(max(start, 0.0), span_x)
            clamped_end = max(min(end, span_x), 0.0)
            new_size = max(0.0, clamped_end - clamped_start)
            if abs(clamped_start - start) > 1e-3 or abs(new_size - elem.x_size) > 1e-3:
                trimmed_total += max(0.0, (end - start) - new_size)
                elem.x = round(clamped_start, 3)
                elem.x_size = round(new_size, 3)
        if trimmed_total > 0.1:
            message = (
                f"Mirrored sheathing trimmed by {trimmed_total:.2f}mm to stay within {span_x:.2f}mm span."
            )
            if message not in self.length_warnings:
                self.length_warnings.append(message)

    def _apply_origin_flyover(self, sheathing: List[SheathingElement]):
        if not sheathing:
            return
        first = sheathing[0]
        seam_x = first.x + first.x_size
        target = self.full_sheet_reference or first.original_x_size
        extension = max(0.0, target - first.x_size)
        if extension >= FLYOVER_THRESHOLD_MM:
            first.x = seam_x - target
            first.x_size = target
            self.allow_negative_overhang = True
            notice = f"Origin-side flyover enabled: first sheet extends {extension:.2f}mm past origin."
            if notice not in self.length_warnings:
                self.length_warnings.append(notice)

    def _apply_short_cassette_rule(self, sheathing: List[SheathingElement]):
        if not self.header:
            return
        if self.header.y_size >= SHORT_CASSETTE_FULL_Y - 1e-3:
            return
        adjusted_any = False
        for elem in sheathing:
            if elem.y_size < SHORT_CASSETTE_MIN_Y:
                continue
            extension = SHORT_CASSETTE_FULL_Y - elem.y_size
            if extension <= 1e-3:
                continue
            elem.y_size = SHORT_CASSETTE_FULL_Y
            adjusted_any = True
        if adjusted_any:
            msg = (
                f"Short cassette rule applied: BOO1 rows >= {SHORT_CASSETTE_MIN_Y:.0f}mm converted to full {SHORT_CASSETTE_FULL_Y:.0f}mm with north flyover."
            )
            if msg not in self.length_warnings:
                self.length_warnings.append(msg)

    @staticmethod
    def _name_tokens(elem: SheathingElement) -> Set[str]:
        raw = (elem.name or '').lower()
        sanitized = raw.replace('®', '').replace('"', '').replace("'", '').replace(':', ' ')
        parts = sanitized.split()
        if sanitized:
            parts.append(sanitized.strip())
        return set(parts)

    def _is_horizontal_priority(self, elem: SheathingElement) -> bool:
        tokens = self._name_tokens(elem)
        keywords = {'floorjoist', 'joist', 'blocking', 'block', 'beam', 'rimboard'}
        return any(token in tokens for token in keywords)

    def _is_vertical_protected(self, elem: SheathingElement) -> bool:
        tokens = self._name_tokens(elem)
        if {'rimboard', 'cantileverclosure'} & tokens:
            return True
        if self.header is None:
            return False
        near_left = elem.x <= 1.0
        near_right = elem.x + elem.x_size >= self.header.x_size - 1.0
        return near_left or near_right

    def _preferred_shift_dirs(self, mover: SheathingElement, other: SheathingElement, axis: str) -> List[int]:
        mover_center = mover.y + mover.y_size * 0.5 if axis == 'y' else mover.x + mover.x_size * 0.5
        other_center = other.y + other.y_size * 0.5 if axis == 'y' else other.x + other.x_size * 0.5
        primary = 1 if mover_center >= other_center else -1
        return [primary, -primary]

    def _nudge_member(self, mover: SheathingElement, other: SheathingElement, axis: str, magnitude: float, tolerance: float) -> bool:
        max_shift = min(MAX_STA_NUDGE, max(magnitude, 0.0))
        if max_shift <= tolerance:
            return False
        for direction in self._preferred_shift_dirs(mover, other, axis):
            delta = max_shift * direction
            dx = delta if axis == 'x' else 0.0
            dy = delta if axis == 'y' else 0.0
            if self._shift_and_check(mover, other, dx, dy, tolerance):
                return True
        return False

    def _shift_and_check(self, mover: SheathingElement, other: SheathingElement, dx: float, dy: float, tolerance: float) -> bool:
        original_x, original_y = mover.x, mover.y
        mover.x += dx
        mover.y += dy
        self._clamp_element(mover)
        if self.elements_overlap(mover, other, tolerance):
            mover.x = original_x
            mover.y = original_y
            return False
        return True

    def resolve_structural_overlaps(self, tolerance: float = 0.1, margin: float = 1.0, max_iterations: int = 200):
        structural = self.sta_elements
        if not structural:
            return

        for _ in range(max_iterations):
            changed = False
            for i, elem_a in enumerate(structural):
                for elem_b in structural[i + 1:]:
                    overlap_x = min(elem_a.x + elem_a.x_size, elem_b.x + elem_b.x_size) - max(elem_a.x, elem_b.x)
                    overlap_y = min(elem_a.y + elem_a.y_size, elem_b.y + elem_b.y_size) - max(elem_a.y, elem_b.y)
                    if overlap_x <= tolerance or overlap_y <= tolerance:
                        continue

                    a_horizontal = elem_a.x_size > elem_a.y_size
                    b_horizontal = elem_b.x_size > elem_b.y_size

                    if a_horizontal != b_horizontal:
                        horizontal = elem_a if a_horizontal else elem_b
                        vertical = elem_b if a_horizontal else elem_a
                        bottom = vertical.y
                        top = vertical.y + vertical.y_size
                        h_bottom = horizontal.y
                        h_top = horizontal.y + horizontal.y_size
                        gap_needed = margin

                        horizontal_priority = self._is_horizontal_priority(horizontal)
                        if horizontal_priority:
                            if self._nudge_member(horizontal, vertical, 'y', overlap_y, tolerance):
                                changed = True
                                continue
                        if not self._is_vertical_protected(vertical):
                            if self._nudge_member(vertical, horizontal, 'x', overlap_x, tolerance):
                                changed = True
                                continue

                    required_x = min(overlap_x + margin, MAX_STA_NUDGE)
                    required_y = min(overlap_y + margin, MAX_STA_NUDGE)
                    axes = [('x', required_x), ('y', required_y)]
                    if required_y < required_x:
                        axes.reverse()

                    resolved = False
                    for axis, shift in axes:
                        if shift <= tolerance:
                            continue
                        if axis == 'x':
                            if elem_a.x <= elem_b.x:
                                options = [(elem_b, shift), (elem_a, -shift)]
                            else:
                                options = [(elem_a, shift), (elem_b, -shift)]
                            for mover, delta in options:
                                if self._shift_and_check(mover, elem_b if mover is elem_a else elem_a, delta, 0.0, tolerance):
                                    resolved = True
                                    break
                        else:
                            if elem_a.y <= elem_b.y:
                                options = [(elem_b, shift), (elem_a, -shift)]
                            else:
                                options = [(elem_a, shift), (elem_b, -shift)]
                            for mover, delta in options:
                                if self._shift_and_check(mover, elem_b if mover is elem_a else elem_a, 0.0, delta, tolerance):
                                    resolved = True
                                    break
                        if resolved:
                            changed = True
                            break
                    if not resolved:
                        # As a last resort nudge the second element slightly along both axes
                        dx = min(required_x * 0.5, MAX_STA_NUDGE)
                        dy = min(required_y * 0.5, MAX_STA_NUDGE)
                        if self._shift_and_check(elem_b, elem_a, dx, dy, tolerance):
                            changed = True
            if not changed:
                break

    def offset_horizontal_members(self, clearance: float = 0.2):
        if self.header is None:
            return
        structural = self.sta_elements
        if not structural:
            return

        def is_vertical_support(candidate: SheathingElement) -> bool:
            if candidate.y_size <= candidate.x_size:
                return False
            if candidate.y_size <= 200:
                return False
            name_lower = candidate.name.lower()
            disqualifiers = ("floorjoist", "joist", "beam", "blocking", "ledger")
            if any(token in name_lower for token in disqualifiers):
                return False
            return True

        verticals = [elem for elem in structural if is_vertical_support(elem)]
        if not verticals:
            return

        for elem in structural:
            if elem.x_size <= elem.y_size:
                continue  # likely vertical already handled

            relevant_verticals: List[SheathingElement] = []
            for vertical in verticals:
                overlap_y = min(vertical.y + vertical.y_size, elem.y + elem.y_size) - max(vertical.y, elem.y)
                if overlap_y > 0.1:
                    relevant_verticals.append(vertical)
            if not relevant_verticals:
                continue

            center = elem.original_x + elem.x_size * 0.5
            left_verticals = [v for v in relevant_verticals if v.x + v.x_size <= center + 1e-3]
            right_verticals = [v for v in relevant_verticals if v.x >= center - 1e-3]

            left_limit = max((v.x + v.x_size for v in left_verticals), default=0.0)
            right_limit = min((v.x for v in right_verticals), default=self.header.x_size)

            span_without_clearance = max(0.0, right_limit - left_limit)
            if span_without_clearance <= 0:
                continue

            descriptor = elem.name.strip() or elem.element_type

            available_span = max(0.0, span_without_clearance - 2 * clearance)
            trimmed_amount = 0.0
            if elem.x_size > span_without_clearance:
                trimmed_amount = elem.x_size - span_without_clearance
                elem.x_size = span_without_clearance
            elif available_span > 0 and elem.x_size > available_span:
                trimmed_amount = elem.x_size - available_span
                elem.x_size = available_span

            if trimmed_amount > 0.05:
                message = (
                    f"{descriptor} trimmed by {trimmed_amount:.1f}mm to fit available span {span_without_clearance:.1f}mm"
                )
                if message not in self.length_warnings:
                    self.length_warnings.append(message)

            min_allowed = left_limit + clearance
            max_allowed = right_limit - elem.x_size - clearance
            if max_allowed < min_allowed:
                min_allowed = left_limit
                max_allowed = right_limit - elem.x_size
                if max_allowed < min_allowed:
                    balanced = left_limit + 0.5 * max(0.0, span_without_clearance - elem.x_size)
                    elem.x = max(left_limit, min(balanced, right_limit - elem.x_size))
                    self._clamp_element(elem)
                    elem.x_size = round(elem.x_size, 2)
                    continue

            target_x = min(max(elem.x, min_allowed), max_allowed)
            target_x = max(target_x, left_limit)
            target_x = min(target_x, right_limit - elem.x_size)
            elem.x = target_x

            elem.x_size = round(elem.x_size, 2)
            self._clamp_element(elem)

    @staticmethod
    def merge_axis_segments(segments: List[Tuple[float, float]], tolerance: float = 1.0) -> List[Tuple[float, float]]:
        if not segments:
            return []
        ordered = sorted(segments, key=lambda span: span[0])
        merged: List[Tuple[float, float]] = []
        current_start, current_end = ordered[0]
        for start, end in ordered[1:]:
            if start <= current_end + tolerance:
                current_end = max(current_end, end)
            else:
                merged.append((current_start, current_end))
                current_start, current_end = start, end
        merged.append((current_start, current_end))
        return merged

    def generate_glue_lines(self, horizontal_nl_groups: Dict[Tuple[str, float, float], Dict[str, Any]], fmt_value, wall_start: float, wall_end: float, wall_bottom: float, wall_top: float) -> Tuple[List[str], Set[Tuple]]:
        offset = getattr(self, 'glue_edge_offset', GLUE_EDGE)
        glue_plane = getattr(self, 'glue_plane_z', 0.0)
        default_tool = self.gl_lines[0].tool_index if self.gl_lines else 16

        def resolve_span(info: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
            panel_min = info.get('panel_min')
            panel_max = info.get('panel_max')
            if panel_min is not None and panel_max is not None and panel_max > panel_min:
                return panel_min, panel_max
            return info.get('min_nl'), info.get('max_nl')

        key_to_original: Dict[Tuple, List[GlueLine]] = {}
        ordered_keys: List[Tuple] = []
        for gl in self.gl_lines:
            key = gl.group_key()
            key_to_original.setdefault(key, []).append(gl)
            if key not in ordered_keys:
                ordered_keys.append(key)

        emitted: Set[Tuple] = set()
        new_lines: List[str] = []
        tolerance = 1.0
        epsilon = 1e-3

        seen_gl_keys: Set[Tuple] = set()
        horizontal_gl_coverage: Dict[float, List[Tuple[float, float]]] = {}
        matched_nl_keys: Set[Tuple[str, float, float]] = set()

        for key in ordered_keys:
            if key in emitted:
                continue
            orient = key[0]
            originals = key_to_original.get(key, [])
            if orient == 'horizontal':
                info = horizontal_nl_groups.get(key)
                matched_key = key if info is not None else None
                if info is None:
                    matched_key, info = self._match_horizontal_group(horizontal_nl_groups, key[1], GL_STA_ALIGNMENT_TOLERANCE)
                if info is not None:
                    segments = info.get('segments', [])
                    if not segments:
                        for gl in originals:
                            new_lines.append(gl.to_string(fmt_value))
                        emitted.add(key)
                        continue
                    span_start, span_end = resolve_span(info)
                    if span_start is None or span_end is None:
                        merged = self.merge_axis_segments(segments, tolerance)
                        if not merged:
                            span_start = span_end = 0.0
                        else:
                            span_start = merged[0][0]
                            span_end = merged[-1][1]
                    template = originals[0] if originals else None
                    amplitude = template.amplitude if template else 0.0
                    wavelength = template.wavelength if template else 0.0
                    y_value = info.get('y', template.y_start if template else key[1])
                    default_z = template.z_start if template else glue_plane
                    z_value = info.get('z', default_z)
                    tool_index = template.tool_index if template else default_tool
                    widths = template.widths if template else None
                    gl_start = span_start
                    gl_end = span_end
                    sta_span_start = info.get('sta_full_start') if info.get('sta_full_start') is not None else info.get('sta_start')
                    sta_span_end = info.get('sta_full_end') if info.get('sta_full_end') is not None else info.get('sta_end')
                    if sta_span_start is not None and sta_span_end is not None and sta_span_end > sta_span_start:
                        gl_start = sta_span_start
                        gl_end = sta_span_end
                    if gl_start <= wall_start + epsilon:
                        gl_start = max(wall_start, gl_start)
                    if gl_end >= wall_end - epsilon:
                        gl_end = min(wall_end, gl_end)
                    sta_start = sta_span_start
                    sta_end = sta_span_end
                    gl_start, gl_end = self._clamp_horizontal_span(gl_start, gl_end, y_value, wall_start, wall_end, offset, sta_start, sta_end)
                    self._append_gl_line(new_lines, seen_gl_keys, fmt_value, gl_start, y_value, z_value, gl_end, y_value, z_value, amplitude, wavelength, tool_index, widths)
                    self._register_gl_span(horizontal_gl_coverage, y_value, gl_start, gl_end)
                    if matched_key is not None:
                        matched_nl_keys.add(matched_key)
                    emitted.add(key)
                else:
                    for gl in originals:
                        gl_start, gl_end = self._clamp_horizontal_span(gl.x_start, gl.x_end, gl.y_start, wall_start, wall_end, offset)
                        self._append_gl_line(new_lines, seen_gl_keys, fmt_value, gl_start, gl.y_start, gl.z_start, gl_end, gl.y_end, gl.z_end, gl.amplitude, gl.wavelength, gl.tool_index, gl.widths)
                        self._register_gl_span(horizontal_gl_coverage, gl.y_start, gl_start, gl_end)
                    emitted.add(key)
            elif orient == 'vertical' and originals:
                for gl in originals:
                    y_start = gl.y_start
                    y_end = gl.y_end
                    if y_start <= wall_bottom + epsilon:
                        y_start = max(wall_bottom, y_start)
                    if y_end >= wall_top - epsilon:
                        y_end = min(wall_top, y_end)
                    y_start, y_end = self._inset_segment(y_start, y_end, offset)
                    self._append_gl_line(new_lines, seen_gl_keys, fmt_value, gl.x_start, y_start, gl.z_start, gl.x_end, y_end, gl.z_end, gl.amplitude, gl.wavelength, gl.tool_index, gl.widths)
                emitted.add(key)
            else:
                for gl in originals:
                    self._append_gl_line(new_lines, seen_gl_keys, fmt_value, gl.x_start, gl.y_start, gl.z_start, gl.x_end, gl.y_end, gl.z_end, gl.amplitude, gl.wavelength, gl.tool_index, gl.widths)
                emitted.add(key)

        for key, info in horizontal_nl_groups.items():
            if key in matched_nl_keys:
                continue
            segments = info.get('segments', [])
            if not segments:
                continue
            span_start, span_end = resolve_span(info)
            if span_start is None or span_end is None:
                merged = self.merge_axis_segments(segments, tolerance)
                if not merged:
                    continue
                span_start = merged[0][0]
                span_end = merged[-1][1]
            gl_start = span_start
            gl_end = span_end
            if span_start <= wall_start + epsilon:
                gl_start = max(wall_start, span_start)
            if span_end >= wall_end - epsilon:
                gl_end = min(wall_end, span_end)
            sta_start = info.get('sta_start')
            sta_end = info.get('sta_end')
            y_value = info.get('y', 0.0)
            z_value = info.get('z', glue_plane)
            gl_start, gl_end = self._clamp_horizontal_span(gl_start, gl_end, y_value, wall_start, wall_end, offset, sta_start, sta_end)
            self._append_gl_line(new_lines, seen_gl_keys, fmt_value, gl_start, y_value, z_value, gl_end, y_value, z_value, 0.0, 0.0, default_tool)
            self._register_gl_span(horizontal_gl_coverage, y_value, gl_start, gl_end)
            matched_nl_keys.add(key)

        # Fallback: ensure each STA span has horizontal glue coverage
        processed_sta: Set[SheathingElement] = set()
        coverage_tol = 0.5
        for sta in self.sta_elements:
            if sta in processed_sta:
                continue
            processed_sta.add(sta)
            y_start = sta.y + 0.5 * sta.y_size
            sta_start = sta.x + MEMBER_END_FASTENER_OFFSET
            sta_end = sta.x + sta.x_size - MEMBER_END_FASTENER_OFFSET
            if sta_end <= sta_start + 1e-3:
                continue
            target_y = self._preferred_y_for_span(y_start, horizontal_nl_groups, horizontal_gl_coverage, GL_STA_ALIGNMENT_TOLERANCE)
            existing_gl_spans = horizontal_gl_coverage.get(target_y, [])
            gaps = self._segment_gaps(sta_start, sta_end, existing_gl_spans, tolerance=coverage_tol)
            if not gaps:
                continue
            for gap_start, gap_end in gaps:
                gl_start, gl_end = self._clamp_horizontal_span(gap_start, gap_end, y_start, wall_start, wall_end, offset, sta_start, sta_end)
                if gl_end - gl_start <= 1e-3:
                    continue
                glue_z = self.glue_plane_z if hasattr(self, 'glue_plane_z') else 0.0
                self._append_gl_line(new_lines, seen_gl_keys, fmt_value, gl_start, target_y, glue_z, gl_end, target_y, glue_z, 0.0, 0.0, default_tool)
                self._register_gl_span(horizontal_gl_coverage, target_y, gl_start, gl_end)

        return new_lines, seen_gl_keys

    def _fallback_glue_lines(self, fmt_value, wall_start: float, wall_end: float, wall_bottom: float, wall_top: float, seen_keys: Optional[Set[Tuple]] = None) -> Tuple[List[str], Set[Tuple]]:
        fallback: List[str] = []
        seen = seen_keys if seen_keys is not None else set()
        epsilon = 1e-3
        for gl in self.gl_lines:
            x_start = gl.x_start
            x_end = gl.x_end
            y_start = gl.y_start
            y_end = gl.y_end
            if abs(x_end - x_start) <= epsilon:
                if y_start <= wall_bottom + epsilon:
                    y_start = max(wall_bottom, y_start)
                if y_end >= wall_top - epsilon:
                    y_end = min(wall_top, y_end)
                y_start, y_end = self._inset_segment(y_start, y_end, self.glue_edge_offset)
            elif abs(y_end - y_start) <= epsilon:
                if x_start <= wall_start + epsilon:
                    x_start = max(wall_start, x_start)
                if x_end >= wall_end - epsilon:
                    x_end = min(wall_end, x_end)
                x_start, x_end = self._inset_segment(x_start, x_end, self.glue_edge_offset)
            if abs(y_end - y_start) <= epsilon:
                x_start, x_end = self._clamp_horizontal_span(x_start, x_end, y_start, wall_start, wall_end, self.glue_edge_offset)
            self._append_gl_line(
                fallback,
                seen,
                fmt_value,
                x_start,
                y_start,
                gl.z_start,
                x_end,
                y_end,
                gl.z_end,
                gl.amplitude,
                gl.wavelength,
                gl.tool_index,
                gl.widths,
            )
        return fallback, seen

    def _generate_missing_nl_lines(self, fmt_value, horizontal_nl_groups: Dict[Tuple[str, float, float], Dict[str, Any]],
                                   top_surface_z: Optional[float], wall_start: float, wall_end: float,
                                   sheathing_panels_for_y, sheathing_spans_for_y) -> List[str]:
        if top_surface_z is None:
            return []
        coverage_tol = 0.5
        coverage_by_y: Dict[float, List[Tuple[float, float]]] = {}
        for key, info in horizontal_nl_groups.items():
            orient, y_val, _ = key
            if orient != 'horizontal':
                continue
            coverage_by_y.setdefault(y_val, []).extend(info.get('segments', []))
        for y_val, spans in coverage_by_y.items():
            coverage_by_y[y_val] = self.merge_axis_segments(spans, tolerance=coverage_tol) if spans else []
        gl_row_coverage: Dict[float, List[Tuple[float, float]]] = {}
        for gl in self.gl_lines:
            if abs(gl.y_end - gl.y_start) <= 1e-3:
                x_start = min(gl.x_start, gl.x_end)
                x_end = max(gl.x_start, gl.x_end)
                self._register_gl_span(gl_row_coverage, gl.y_start, x_start, x_end)
        additions: List[Tuple[float, float, str]] = []
        for sta in self.sta_elements:
            y_mid = round(sta.y + 0.5 * sta.y_size, 3)
            trimmed_start = max(wall_start, sta.x + MEMBER_END_FASTENER_OFFSET)
            trimmed_end = min(wall_end, sta.x + sta.x_size - MEMBER_END_FASTENER_OFFSET)
            sta_start = trimmed_start
            sta_end = trimmed_end
            sta_face_start = sta.x
            sta_face_end = sta.x + sta.x_size
            if sta_end <= sta_start + 1e-3:
                continue
            target_y = self._preferred_y_for_span(y_mid, horizontal_nl_groups, gl_row_coverage, NL_STA_ALIGNMENT_TOLERANCE)
            coverage_list = coverage_by_y.setdefault(target_y, [])
            gaps = self._segment_gaps(sta_start, sta_end, coverage_list, tolerance=coverage_tol)
            if not gaps:
                continue
            _, group_info = self._ensure_horizontal_group(horizontal_nl_groups, target_y)
            segments = group_info.setdefault('segments', [])
            spacing = group_info.get('spacing', FIELD_NL_SPACING)
            tool_index = int(group_info.get('tool_index', 11))
            group_info.setdefault('spacing', spacing)
            panels_for_row = sheathing_panels_for_y(target_y)
            edge_row = self._is_panel_edge_row(target_y, panels_for_row)
            if edge_row:
                group_info['edge'] = True
                group_info['spacing'] = PERIMETER_NL_SPACING
            else:
                group_info['spacing'] = min(group_info.get('spacing', FIELD_NL_SPACING), FIELD_NL_SPACING)
            group_info.setdefault('tool_index', tool_index)
            group_info.setdefault('y', target_y)
            group_info.setdefault('z', self.glue_plane_z if hasattr(self, 'glue_plane_z') else 0.0)
            for gap_start, gap_end in gaps:
                if gap_end - gap_start <= 1e-3:
                    continue
                snapped_spans, panel_min, panel_max = self._snapped_panel_spans(
                    target_y,
                    gap_start,
                    gap_end,
                    sheathing_panels_for_y,
                    sheathing_spans_for_y,
                    tolerance=coverage_tol
                )
                if panel_min is not None:
                    existing_min = group_info.get('panel_min')
                    group_info['panel_min'] = panel_min if existing_min is None else min(existing_min, panel_min)
                if panel_max is not None:
                    existing_max = group_info.get('panel_max')
                    group_info['panel_max'] = panel_max if existing_max is None else max(existing_max, panel_max)
                for seg_start, seg_end in snapped_spans:
                    segments.append((seg_start, seg_end))
                    coverage_list.append((seg_start, seg_end))
                    group_info['min_nl'] = min(group_info.get('min_nl', seg_start), seg_start)
                    group_info['max_nl'] = max(group_info.get('max_nl', seg_end), seg_end)
                    existing_start = group_info.get('sta_start')
                    existing_end = group_info.get('sta_end')
                    group_info['sta_start'] = max(existing_start, sta_start) if existing_start is not None else sta_start
                    group_info['sta_end'] = min(existing_end, sta_end) if existing_end is not None else sta_end
                    face_start = group_info.get('sta_full_start')
                    face_end = group_info.get('sta_full_end')
                    group_info['sta_full_start'] = min(face_start, sta_face_start) if face_start is not None else sta_face_start
                    group_info['sta_full_end'] = max(face_end, sta_face_end) if face_end is not None else sta_face_end
                    spacing_value = PERIMETER_NL_SPACING if edge_row else group_info.get('spacing', FIELD_NL_SPACING)
                    line = self._format_nl_line(
                        fmt_value,
                        seg_start,
                        target_y,
                        top_surface_z,
                        seg_end,
                        target_y,
                        top_surface_z,
                        spacing_value,
                        tool_index
                    )
                    additions.append((target_y, seg_start, line))
        additions.sort(key=lambda entry: (entry[0], entry[1]))
        return [line for _, _, line in additions]

    def _generate_flyover_stub_lines(self, fmt_value, horizontal_nl_groups: Dict[Tuple[str, float, float], Dict[str, Any]],
                                     top_surface_z: Optional[float]) -> List[str]:
        if top_surface_z is None:
            return []

        additions: List[Tuple[float, float, str]] = []
        tol = PANEL_EDGE_TOLERANCE + 0.1

        def append_stub(info: Dict[str, Any], y_value: float, start: float, end: float,
                         spacing: float, tool_index: int):
            seg_start = min(start, end)
            seg_end = max(start, end)
            if seg_end - seg_start <= 1e-3:
                return
            info.setdefault('segments', []).append((seg_start, seg_end))
            info['min_nl'] = min(info.get('min_nl', seg_start), seg_start)
            info['max_nl'] = max(info.get('max_nl', seg_end), seg_end)
            line = self._format_nl_line(
                fmt_value,
                seg_start,
                y_value,
                top_surface_z,
                seg_end,
                y_value,
                top_surface_z,
                spacing,
                tool_index
            )
            additions.append((y_value, seg_start, line))

        min_stub = PERIMETER_NL_SPACING
        for key, info in horizontal_nl_groups.items():
            orient, y_value, _ = key
            if orient != 'horizontal':
                continue
            if not info.get('edge'):
                continue
            y_row = info.get('y', y_value)
            panel_min = info.get('panel_min')
            panel_max = info.get('panel_max')
            sta_face_start = info.get('sta_full_start')
            sta_face_end = info.get('sta_full_end')
            sta_trim_start = info.get('sta_start')
            sta_trim_end = info.get('sta_end')
            spacing_value = PERIMETER_NL_SPACING
            tool_index = int(round(info.get('tool_index', 11)))
            min_existing = info.get('min_nl')
            max_existing = info.get('max_nl')
            segments = info.get('segments', [])

            if (panel_min is not None and sta_face_start is not None and
                    panel_min < sta_face_start - tol and not info.get('flyover_left_done')):
                stub_end = sta_trim_start if sta_trim_start is not None else sta_face_start + MEMBER_END_FASTENER_OFFSET
                stub_start = max(sta_face_start + SQUARE_EDGE_OFFSET, stub_end - TONGUE_GROOVE_EDGE_OFFSET)
                if stub_end - stub_start < min_stub:
                    max_end = sta_trim_end if sta_trim_end is not None else (stub_start + min_stub)
                    stub_end = min(max_end, stub_start + min_stub)
                if stub_end - stub_start > 1e-3 and not self._segments_cover_interval(segments, stub_start, stub_end):
                    append_stub(info, y_row, stub_start, stub_end, spacing_value, tool_index)
                    info['flyover_left_done'] = True

            if (panel_max is not None and sta_face_end is not None and
                    panel_max > sta_face_end + tol and not info.get('flyover_right_done')):
                stub_start = sta_trim_end if sta_trim_end is not None else sta_face_end - MEMBER_END_FASTENER_OFFSET
                stub_end = min(sta_face_end - SQUARE_EDGE_OFFSET, stub_start + TONGUE_GROOVE_EDGE_OFFSET)
                if stub_end - stub_start < min_stub:
                    min_start = sta_trim_start if sta_trim_start is not None else (stub_end - min_stub)
                    stub_start = max(min_start, stub_end - min_stub)
                if stub_end - stub_start > 1e-3 and not self._segments_cover_interval(segments, stub_start, stub_end):
                    append_stub(info, y_row, stub_start, stub_end, spacing_value, tool_index)
                    info['flyover_right_done'] = True

        additions.sort(key=lambda entry: (entry[0], entry[1]))
        return [line for _, _, line in additions]

    def _original_glue_lines(self, fmt_value, wall_start: float, wall_end: float, offset: float) -> Tuple[List[str], Set[Tuple]]:
        lines: List[str] = []
        seen: Set[Tuple] = set()
        for gl in self.gl_lines:
            x_start = gl.x_start
            x_end = gl.x_end
            if abs(gl.y_end - gl.y_start) <= 1e-3:
                x_start, x_end = self._clamp_horizontal_span(x_start, x_end, gl.y_start, wall_start, wall_end, offset)
            self._append_gl_line(
                lines,
                seen,
                fmt_value,
                x_start,
                gl.y_start,
                gl.z_start,
                x_end,
                gl.y_end,
                gl.z_end,
                gl.amplitude,
                gl.wavelength,
                gl.tool_index,
                gl.widths,
            )
        return lines, seen

    @staticmethod
    def _format_sl(fmt_value, x_start: float, y_start: float, z_start: float, x_end: float, y_end: float, z_end: float,
                   inclination: float = 900.0, tool_index: int = 1) -> str:
        parts = [
            'SL',
            fmt_value(x_start, 0),
            fmt_value(y_start, 0),
            fmt_value(z_start, 0),
            fmt_value(x_end, 0),
            fmt_value(y_end, 0),
            fmt_value(z_end, 0),
            f"{int(round(inclination))}",
            f"{int(round(tool_index))}"
        ]
        return ':'.join(parts) + ';'

    def _format_nl_line(self, fmt_value, x_start: float, y_start: float, z_start: float,
                         x_end: float, y_end: float, z_end: float, spacing: float, tool_index: int) -> str:
        parts = [
            'NL',
            fmt_value(x_start, 0),
            fmt_value(y_start, 0),
            fmt_value(z_start, 0),
            fmt_value(x_end, 0),
            fmt_value(y_end, 0),
            fmt_value(z_end, 0),
            fmt_value(spacing, 0),
            f"{int(round(tool_index))}"
        ]
        return ':'.join(parts) + ';'

    def generate_saw_lines(self, fmt_value, wall_start: float, wall_end: float, wall_bottom: float, wall_top: float,
                           top_surface_z: Optional[float]) -> List[str]:
        if not self.emit_saw_lines:
            return []
        sheathing = self.get_sheathing_elements()
        if not sheathing or top_surface_z is None:
            return []

        bottom_surface_z = min(elem.z for elem in sheathing)
        tolerance = 0.5

        vertical_segments = {'left': [], 'right': []}
        horizontal_segments = {'bottom': [], 'top': []}

        for elem in sheathing:
            y0 = elem.y
            y1 = elem.y + elem.y_size
            x0 = elem.x
            x1 = elem.x + elem.x_size
            if x0 < wall_start - tolerance:
                vertical_segments['left'].append((y0, y1))
            if x1 > wall_end + tolerance:
                vertical_segments['right'].append((y0, y1))
            if y0 < wall_bottom - tolerance:
                horizontal_segments['bottom'].append((x0, x1))
            if y1 > wall_top + tolerance:
                horizontal_segments['top'].append((x0, x1))

        def merged_spans(spans: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
            cleaned = []
            for start, end in spans:
                low = min(start, end)
                high = max(start, end)
                if high - low > tolerance:
                    cleaned.append((low, high))
            if not cleaned:
                return []
            return self.merge_axis_segments(cleaned, tolerance)

        saw_lines: List[str] = []

        for side, spans in vertical_segments.items():
            if not spans:
                continue
            merged = merged_spans(spans)
            if not merged:
                continue
            x_value = wall_start if side == 'left' else wall_end
            for y_start, y_end in merged:
                if y_end - y_start <= tolerance:
                    continue
                saw_lines.append(
                    self._format_sl(fmt_value, x_value, y_start, top_surface_z, x_value, y_end, bottom_surface_z)
                )

        for side, spans in horizontal_segments.items():
            if not spans:
                continue
            merged = merged_spans(spans)
            if not merged:
                continue
            y_value = wall_bottom if side == 'bottom' else wall_top
            for x_start, x_end in merged:
                if x_end - x_start <= tolerance:
                    continue
                saw_lines.append(
                    self._format_sl(fmt_value, x_start, y_value, top_surface_z, x_end, y_value, bottom_surface_z)
                )

        return saw_lines

    def _txt_hash_line(self, content: str) -> str:
        stripped = content.rstrip()
        base = stripped if stripped.endswith(';') else f"{stripped};"
        return f"TXT:# {base}"

    def _transformed_routing_coords(self, block: RoutingBlock, mirror: bool) -> List[Tuple[float, float]]:
        start = block.start.copy()
        points = [pt.copy() for pt in block.points]
        span_x = self.header.x_size if (self.header is not None) else 0.0
        if mirror and self.header is not None:
            start.mirror(span_x)
            mirrored_points = []
            for point in reversed(points):
                mirrored_point = point.copy()
                mirrored_point.mirror(span_x)
                mirrored_points.append(mirrored_point)
            points = mirrored_points
        coords = [(start.x, start.y)]
        coords.extend((pt.x, pt.y) for pt in points)
        return coords

    def generate_routing_saw_lines(
        self,
        fmt_value,
        mirror: bool,
        top_surface_z: Optional[float],
        bottom_surface_z: float
    ) -> List[str]:
        if not (self.emit_saw_lines and self.routing_blocks and top_surface_z is not None):
            return []
        tolerance = 0.5
        outputs: List[str] = []
        seen: Set[Tuple] = set()
        for block in self.routing_blocks:
            coords = self._transformed_routing_coords(block, mirror)
            if len(coords) < 2:
                continue
            xs = [pt[0] for pt in coords]
            ys = [pt[1] for pt in coords]
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)
            for (ax, ay), (bx, by) in zip(coords, coords[1:]):
                dx = bx - ax
                dy = by - ay
                if abs(dx) <= tolerance and abs(dy) <= tolerance:
                    continue
                if abs(dx) <= tolerance:
                    orientation = 'vertical'
                elif abs(dy) <= tolerance:
                    orientation = 'horizontal'
                else:
                    continue
                if orientation == 'vertical':
                    x_value = 0.5 * (ax + bx)
                    y_start = min(ay, by)
                    y_end = max(ay, by)
                    if y_end - y_start <= tolerance:
                        continue
                    if abs(x_value - min_x) <= tolerance or abs(x_value - max_x) <= tolerance:
                        continue
                    key = ('v', round(x_value, 3), round(y_start, 3), round(y_end, 3))
                    if key in seen:
                        continue
                    seen.add(key)
                    outputs.append(self._format_sl(fmt_value, x_value, y_start, top_surface_z, x_value, y_end, bottom_surface_z))
                else:
                    y_value = 0.5 * (ay + by)
                    x_start = min(ax, bx)
                    x_end = max(ax, bx)
                    if x_end - x_start <= tolerance:
                        continue
                    if abs(y_value - min_y) <= tolerance or abs(y_value - max_y) <= tolerance:
                        continue
                    key = ('h', round(y_value, 3), round(x_start, 3), round(x_end, 3))
                    if key in seen:
                        continue
                    seen.add(key)
                    outputs.append(self._format_sl(fmt_value, x_start, y_value, top_surface_z, x_end, y_value, bottom_surface_z))
        return outputs

    def _prepare_routing_blocks(self, fmt_value, mirror: bool, sheet_flip: bool) -> List[List[str]]:
        if not self.routing_blocks:
            return []
        span_x = self.header.x_size if (self.header is not None) else 0.0
        z_shift = -SHEET_FLIP_THICKNESS if sheet_flip else 0.0
        outputs: List[List[str]] = []
        for block in self.routing_blocks:
            start = block.start.copy()
            points = [pt.copy() for pt in block.points]
            if mirror and self.header is not None:
                start.mirror(span_x)
                mirrored_points = []
                for point in reversed(points):
                    mirrored_point = point.copy()
                    mirrored_point.mirror(span_x)
                    mirrored_points.append(mirrored_point)
                points = mirrored_points
            if sheet_flip:
                start.z += z_shift
                for point in points:
                    point.z += z_shift
            block_lines = [start.to_string(fmt_value)]
            for point in points:
                block_lines.append(point.to_string(fmt_value))
            if block.has_end:
                block_lines.append('ROE;')
            outputs.append(block_lines)
        return outputs

    def write_adjusted_file(self, output_path: str, mirror: bool = False):
        """Write the adjusted CDT file with updated geometry and formatting."""

        def fmt_value(value: float, width: int) -> str:
            # Prefer integer-like output when value is effectively integral
            # Use half-up rounding for .5 cases to match manual file formatting
            as_int = int(math.floor(value + 0.5))
            # Only treat value as integer-like when it is very close to an
            # integer. Previously a large 0.51 tolerance caused values like
            # 28.8 to be printed as "29" which produced ELM/STA mismatches
            # in downstream validators. Use a tight tolerance to avoid that.
            if abs(as_int - value) < 0.01:
                return f"{as_int:>{max(width, len(str(as_int)))}}"
            # Otherwise format with two decimals (fallback to 3 if column too small)
            text = f"{value:.2f}"
            if width and len(text) > width:
                text = f"{value:.3f}"
            return f"{text:>{max(width, len(text))}}"

        mirrored_backups = {}
        if mirror and self.header is not None:
            mirrored_backups['elements'] = [(e.x, e.x_size, e.y, e.y_size) for e in self.elements]
            mirrored_backups['sta'] = [(s.x, s.x_size, s.y, s.y_size) for s in self.sta_elements]
            mirrored_backups['gl'] = [(g.x_start, g.x_end, g.y_start, g.y_end) for g in self.gl_lines]
            span_x = self.header.x_size
            # For sheet flip, lock sheathing positions, mirror STA and GL
            if not self.sheet_flip:
                for e in self.elements:
                    e.x = round(span_x - (e.x + e.x_size), 6)
                    e.x_size = e.x_size
                    e.y = e.y
                    e.y_size = e.y_size
            for s in self.sta_elements:
                s.x = round(span_x - (s.x + s.x_size), 6)
                s.x_size = s.x_size
                s.y = s.y
                s.y_size = s.y_size
            for g in self.gl_lines:
                g.x_start = round(span_x - g.x_start, 6)
                g.x_end = round(span_x - g.x_end, 6)
                g.y_start = g.y_start
                g.y_end = g.y_end

        sheet_flip_backups = {}
        if self.sheet_flip:
            thickness = SHEET_FLIP_THICKNESS
            sheet_flip_backups['elements'] = [(e.element_type, e.z) for e in self.elements]
            for elem in self.elements:
                if elem.element_type.startswith('BOO'):
                    elem.element_type = 'BOI' + elem.element_type[3:]
                    elem.z -= thickness
                elif elem.element_type.startswith('BOI'):
                    elem.element_type = 'BOO' + elem.element_type[3:]
                    elem.z += thickness

        sheathing_index = 0
        sta_index = 0
        top_surface_z = None
        glue_plane_z = 0.0
        sheathing = self.get_sheathing_elements()
        if sheathing:
            top_surface_z = max(elem.z + elem.z_size for elem in sheathing)
            glue_plane_z = min(elem.z for elem in sheathing)
            first_sheet = min(sheathing, key=lambda e: e.x)
            last_sheet = max(sheathing, key=lambda e: e.x + e.x_size)
            wall_start = min(s.x for s in self.sta_elements) if self.sta_elements else first_sheet.x
            wall_end = max(s.x + s.x_size for s in self.sta_elements) if self.sta_elements else last_sheet.x + last_sheet.x_size
            wall_bottom = min(s.y for s in self.sta_elements) if self.sta_elements else min(elem.y for elem in sheathing)
            wall_top = max(s.y + s.y_size for s in self.sta_elements) if self.sta_elements else max(elem.y + elem.y_size for elem in sheathing)
        else:
            wall_start = min(s.x for s in self.sta_elements) if self.sta_elements else 0.0
            wall_end = max(s.x + s.x_size for s in self.sta_elements) if self.sta_elements else self.header.x_size if self.header else 0.0
            wall_bottom = min(s.y for s in self.sta_elements) if self.sta_elements else 0.0
            wall_top = max(s.y + s.y_size for s in self.sta_elements) if self.sta_elements else self.header.y_size if self.header else 0.0
            glue_plane_z = self.header.z_size if self.header else 0.0

        self.glue_plane_z = glue_plane_z
        panel_edge_rows: List[float] = []
        self.deck_min_y = None
        self.deck_max_y = None
        if sheathing:
            edges = set()
            for elem in sheathing:
                edges.add(round(elem.y, 3))
                edges.add(round(elem.y + elem.y_size, 3))
            panel_edge_rows = sorted(edges)
            self.deck_min_y = min(elem.y for elem in sheathing)
            self.deck_max_y = max(elem.y + elem.y_size for elem in sheathing)
        horizontal_row_registry: List[float] = []
        saw_line_outputs: List[str] = []
        if self.emit_saw_lines:
            saw_line_outputs = self.generate_saw_lines(fmt_value, wall_start, wall_end, wall_bottom, wall_top, top_surface_z)
            routing_sl = self.generate_routing_saw_lines(fmt_value, mirror, top_surface_z, glue_plane_z)
            if routing_sl:
                saw_line_outputs.extend(routing_sl)
        coverage_cache: Dict[float, List[Tuple[float, float]]] = {}
        panel_cache: Dict[float, List[SheathingElement]] = {}
        sta_cache: Dict[float, Optional[SheathingElement]] = {}
        coverage_tol = 0.5

        def sheathing_spans_for_y(y_value: float) -> List[Tuple[float, float]]:
            key = round(y_value, 3)
            if key in coverage_cache:
                return coverage_cache[key]
            spans: List[Tuple[float, float]] = []
            for elem in sheathing:
                if elem.y - coverage_tol <= y_value <= elem.y + elem.y_size + coverage_tol:
                    spans.append((elem.x, elem.x + elem.x_size))
            merged = self.merge_axis_segments(spans, tolerance=coverage_tol) if spans else []
            coverage_cache[key] = merged
            return merged

        def sheathing_panels_for_y(y_value: float) -> List[SheathingElement]:
            key = round(y_value, 3)
            if key in panel_cache:
                return panel_cache[key]
            panels: List[SheathingElement] = []
            for elem in sheathing:
                if elem.y - coverage_tol <= y_value <= elem.y + elem.y_size + coverage_tol:
                    panels.append(elem)
            panels.sort(key=lambda e: e.x)
            panel_cache[key] = panels
            return panels

        def primary_sta_for_y(y_value: float) -> Optional[SheathingElement]:
            key = round(y_value, 3)
            if key in sta_cache:
                return sta_cache[key]
            candidate: Optional[SheathingElement] = None
            for sta in self.sta_elements:
                if sta.y - coverage_tol <= y_value <= sta.y + sta.y_size + coverage_tol:
                    if candidate is None or sta.x_size > candidate.x_size:
                        candidate = sta
            sta_cache[key] = candidate
            return candidate

        seen_nl_keys = set()
        horizontal_nl_groups: Dict[Tuple[str, float, float], Dict[str, Any]] = {}
        horizontal_gl_templates: Dict[Tuple[str, float, float], GlueLine] = {}
        gl_key_by_y: Dict[float, Tuple[str, float, float]] = {}
        for gl in self.gl_lines:
            key = gl.group_key()
            if key[0] == 'horizontal' and key not in horizontal_gl_templates:
                horizontal_gl_templates[key] = gl
                gl_key_by_y[key[1]] = key

        in_gl_section = False
        gl_written = False
        gl_newline = '\n'
        new_gl_lines = None
        gl_seen_keys: Optional[Set[Tuple]] = None
        nl_supplement_lines: Optional[List[str]] = None
        lock_gl_section = mirror and self.sheet_flip
        glue_offset_value = getattr(self, 'glue_edge_offset', GLUE_EDGE)
        routing_outputs = [] if self.emit_saw_lines else self._prepare_routing_blocks(fmt_value, mirror, self.sheet_flip)
        routing_block_idx = 0
        routing_skip_mode: Optional[str] = None
        saw_lines_written = not self.emit_saw_lines
        saw_lines_newline = '\n'

        with open(output_path, 'w') as f:
            for line in self.lines:
                newline = '\n' if line.endswith('\n') else ''
                content = line.rstrip('\n')
                stripped = content.strip()

                if not stripped:
                    f.write(content + newline)
                    continue

                if routing_skip_mode:
                    if routing_skip_mode == 'txt':
                        f.write(self._txt_hash_line(content) + newline)
                    if stripped == 'ROE;':
                        routing_skip_mode = None
                    continue

                if self.emit_saw_lines and stripped.startswith('SL:'):
                    continue

                if self.emit_saw_lines and stripped.startswith('ROB:'):
                    routing_skip_mode = 'txt'
                    f.write(self._txt_hash_line(content) + newline)
                    continue

                if stripped.startswith('ELM:'):
                    parts = content.rstrip(';').split(':')
                    if len(parts) == 8:
                        widths = [len(part) for part in parts[1:]]
                        parts[1] = fmt_value(self.header.x_size, widths[0])
                        parts[2] = fmt_value(self.header.y_size, widths[1])
                        parts[3] = fmt_value(self.header.z_size, widths[2])
                        parts[4] = f"{self.header.element_type:>{max(widths[3], len(str(self.header.element_type)))}}"
                        parts[5] = fmt_value(self.header.length, widths[4])
                        parts[6] = fmt_value(self.header.measurement, widths[5])
                        parts[7] = fmt_value(self.header.quality, widths[6])
                        rebuilt = ':'.join(parts)
                        f.write(rebuilt + ';' + newline)
                        continue

                if stripped.startswith('STA:') or stripped.startswith('STB:'):
                    if sta_index < len(self.sta_elements):
                        elem = self.sta_elements[sta_index]
                        sta_index += 1
                        parts = content.rstrip(';').split(':')
                        if len(parts) >= 8:
                            widths = [len(part) for part in parts[1:]]
                            parts[1] = fmt_value(elem.x_size, widths[0])
                            parts[2] = fmt_value(elem.y_size, widths[1])
                            parts[3] = fmt_value(elem.z_size, widths[2])
                            parts[4] = fmt_value(elem.x, widths[3])
                            parts[5] = fmt_value(elem.y, widths[4])
                            parts[6] = fmt_value(elem.z, widths[5])
                            parts[7] = f"{elem.tool_index:>{max(widths[6], len(str(elem.tool_index)))}}"
                            rebuilt = ':'.join(parts)
                            f.write(rebuilt + ';' + newline)
                            continue

                if stripped.startswith('BOO') or stripped.startswith('BOI'):
                    if sheathing_index < len(self.elements):
                        elem = self.elements[sheathing_index]
                        sheathing_index += 1
                        parts = content.rstrip(';').split(':')
                        if len(parts) >= 8:
                            widths = [len(part) for part in parts[1:]]
                            parts[1] = fmt_value(elem.x_size, widths[0])
                            parts[2] = fmt_value(elem.y_size, widths[1])
                            parts[3] = fmt_value(elem.z_size, widths[2])
                            parts[4] = fmt_value(elem.x, widths[3])
                            parts[5] = fmt_value(elem.y, widths[4])
                            parts[6] = fmt_value(elem.z, widths[5])
                            parts[7] = f"{elem.tool_index:>{max(widths[6], len(str(elem.tool_index)))}}"
                            name = elem.name
                            if len(parts) > 8:
                                parts[8] = name
                            else:
                                parts.append(name)
                            rebuilt = ':'.join(parts)
                            f.write(rebuilt + ';' + newline)
                            continue

                if stripped.startswith('NL:') and top_surface_z is not None:
                    parts = content.rstrip(';').split(':')
                    if len(parts) == 9:
                        widths = [len(part) for part in parts[1:]]
                        parts[3] = fmt_value(top_surface_z, widths[2])
                        parts[6] = fmt_value(top_surface_z, widths[5])
                        x_start = float(parts[1].strip())
                        y_start = float(parts[2].strip())
                        x_end = float(parts[4].strip())
                        y_end = float(parts[5].strip())
                        nail_distance = float(parts[7].strip())
                        tool_value = int(round(float(parts[8].strip()))) if len(parts) > 8 else 11
                        if mirror:
                            span_x = self.header.x_size if self.header else 0.0
                            x_start = span_x - x_start
                            x_end = span_x - x_end
                        dy = abs(y_end - y_start)
                        segments_to_emit: List[Tuple[float, float, float, float]] = []
                        if dy <= 1e-3:
                            y_mid = round(0.5 * (y_start + y_end), 3)
                            snapped_y = self._snap_horizontal_y(y_mid, horizontal_row_registry, panel_edge_rows)
                            y_mid = snapped_y
                            y_start = snapped_y
                            y_end = snapped_y
                            gl_key = gl_key_by_y.get(y_mid)
                            if gl_key:
                                nl_key = gl_key
                                template = horizontal_gl_templates.get(gl_key)
                                z_candidate = template.z_start if template else glue_plane_z
                            else:
                                z_candidate = glue_plane_z
                                z_round = round(z_candidate if z_candidate is not None else 0.0, 3)
                                nl_key = ('horizontal', y_mid, z_round)
                            x_low = min(x_start, x_end)
                            x_high = max(x_start, x_end)
                            panels = sheathing_panels_for_y(y_mid)
                            edge_row = self._is_panel_edge_row(y_mid, panels)
                            nail_distance_effective = PERIMETER_NL_SPACING if edge_row else min(nail_distance, FIELD_NL_SPACING)
                            sta_start, sta_end, sta_face_start, sta_face_end = self._sta_span_for_y(y_mid)
                            snapped_spans: List[Tuple[float, float]] = []
                            panel_span_start = None
                            panel_span_end = None
                            if panels:
                                panel_count = len(panels)
                                for idx, panel in enumerate(panels):
                                    panel_start = panel.x
                                    panel_end = panel.x + panel.x_size
                                    if sta_start is not None and panel_end <= sta_start + coverage_tol:
                                        continue
                                    if sta_end is not None and panel_start >= sta_end - coverage_tol:
                                        continue
                                    has_left_neighbor = idx > 0
                                    has_right_neighbor = idx < panel_count - 1
                                    left_offset = MEMBER_END_FASTENER_OFFSET if has_left_neighbor else SQUARE_EDGE_OFFSET
                                    right_offset = MEMBER_END_FASTENER_OFFSET if has_right_neighbor else SQUARE_EDGE_OFFSET
                                    usable_start = panel_start + left_offset
                                    usable_end = panel_end - right_offset
                                    if sta_start is not None:
                                        usable_start = max(usable_start, sta_start)
                                    if sta_end is not None:
                                        usable_end = min(usable_end, sta_end)
                                    if usable_end - usable_start <= 1e-3:
                                        continue
                                    snapped_spans.append((usable_start, usable_end))
                                    panel_span_start = panel.x if panel_span_start is None else min(panel_span_start, panel.x)
                                    panel_span_end = (panel.x + panel.x_size) if panel_span_end is None else max(panel_span_end, panel.x + panel.x_size)
                            if not snapped_spans:
                                spans = sheathing_spans_for_y(y_mid)
                                if spans:
                                    for span_start, span_end in spans:
                                        if x_high < span_start - coverage_tol or x_low > span_end + coverage_tol:
                                            continue
                                        snapped_spans.append((span_start, span_end))
                                    panel_span_start = span_start if panel_span_start is None else min(panel_span_start, span_start)
                                    panel_span_end = span_end if panel_span_end is None else max(panel_span_end, span_end)
                            if not snapped_spans:
                                snapped_spans = [(x_low, x_high)]
                            panel_span_start = panel_span_start if panel_span_start is not None else x_low
                            panel_span_end = panel_span_end if panel_span_end is not None else x_high
                            info = horizontal_nl_groups.setdefault(
                                nl_key,
                                {
                                    'segments': [],
                                    'min_nl': snapped_spans[0][0],
                                    'max_nl': snapped_spans[0][1]
                                }
                            )
                            info['edge'] = info.get('edge', False) or edge_row
                            if info.get('edge'):
                                info['spacing'] = min(info.get('spacing', PERIMETER_NL_SPACING), PERIMETER_NL_SPACING)
                            else:
                                info.setdefault('spacing', nail_distance_effective)
                            info.setdefault('tool_index', tool_value)
                            if sta_start is not None and sta_end is not None:
                                existing_start = info.get('sta_start')
                                existing_end = info.get('sta_end')
                                info['sta_start'] = max(existing_start, sta_start) if existing_start is not None else sta_start
                                info['sta_end'] = min(existing_end, sta_end) if existing_end is not None else sta_end
                                if sta_face_start is not None and sta_face_end is not None:
                                    face_start = info.get('sta_full_start')
                                    face_end = info.get('sta_full_end')
                                    info['sta_full_start'] = min(face_start, sta_face_start) if face_start is not None else sta_face_start
                                    info['sta_full_end'] = max(face_end, sta_face_end) if face_end is not None else sta_face_end
                            for span_start, span_end in snapped_spans:
                                seg_start = min(span_start, span_end)
                                seg_end = max(span_start, span_end)
                                if seg_end - seg_start < 1e-3:
                                    continue
                                info['segments'].append((seg_start, seg_end))
                                info['min_nl'] = min(info.get('min_nl', seg_start), seg_start)
                                info['max_nl'] = max(info.get('max_nl', seg_end), seg_end)
                                if 'y' not in info:
                                    info['y'] = 0.5 * (y_start + y_end)
                                if 'z' not in info:
                                    info['z'] = z_candidate if z_candidate is not None else 0.0
                                if x_start <= x_end:
                                    emit_start = seg_start
                                    emit_end = seg_end
                                else:
                                    emit_start = seg_end
                                    emit_end = seg_start
                                segments_to_emit.append((emit_start, y_start, emit_end, y_end))
                                if panel_span_start is not None and panel_span_end is not None and panel_span_end > panel_span_start:
                                    info['panel_min'] = min(info.get('panel_min', panel_span_start), panel_span_start)
                                    info['panel_max'] = max(info.get('panel_max', panel_span_end), panel_span_end)
                        else:
                            segments_to_emit.append((x_start, y_start, x_end, y_end))
                        if not segments_to_emit:
                            continue
                        for seg_x_start, seg_y_start, seg_x_end, seg_y_end in segments_to_emit:
                            key = (
                                round(min(seg_x_start, seg_x_end), 3),
                                round(min(seg_y_start, seg_y_end), 3),
                                round(max(seg_x_start, seg_x_end), 3),
                                round(max(seg_y_start, seg_y_end), 3),
                                round(nail_distance_effective if dy <= 1e-3 else min(nail_distance, FIELD_NL_SPACING), 3)
                            )
                            if key in seen_nl_keys:
                                continue
                            seen_nl_keys.add(key)
                            line_parts = list(parts)
                            line_parts[1] = fmt_value(seg_x_start, widths[0])
                            line_parts[2] = fmt_value(seg_y_start, widths[1])
                            line_parts[4] = fmt_value(seg_x_end, widths[3])
                            line_parts[5] = fmt_value(seg_y_end, widths[4])
                            spacing_value = nail_distance_effective if dy <= 1e-3 else min(nail_distance, FIELD_NL_SPACING)
                            line_parts[7] = fmt_value(spacing_value, widths[6])
                            rebuilt = ':'.join(line_parts)
                            f.write(rebuilt + ';' + newline)
                        continue

                if stripped == 'GLUE_LINES;':
                    if nl_supplement_lines is None:
                        nl_supplement_lines = self._generate_missing_nl_lines(
                            fmt_value,
                            horizontal_nl_groups,
                            top_surface_z,
                            wall_start,
                            wall_end,
                            sheathing_panels_for_y,
                            sheathing_spans_for_y
                        ) or []
                        flyover_lines = self._generate_flyover_stub_lines(
                            fmt_value,
                            horizontal_nl_groups,
                            top_surface_z
                        )
                        if flyover_lines:
                            nl_supplement_lines.extend(flyover_lines)
                    if nl_supplement_lines:
                        nl_newline = newline or '\n'
                        for extra_line in nl_supplement_lines:
                            f.write(extra_line + nl_newline)
                    in_gl_section = True
                    gl_written = False
                    f.write(content + newline)
                    continue

                if in_gl_section and stripped.startswith('GL:'):
                    if newline:
                        gl_newline = newline
                    continue

                if in_gl_section and not stripped.startswith('GL:'):
                    if not gl_written:
                        if lock_gl_section:
                            if new_gl_lines is None:
                                new_gl_lines, gl_seen_keys = self._original_glue_lines(fmt_value, wall_start, wall_end, glue_offset_value)
                        else:
                            if new_gl_lines is None:
                                new_gl_lines, gl_seen_keys = self.generate_glue_lines(horizontal_nl_groups, fmt_value, wall_start, wall_end, wall_bottom, wall_top)
                                if not new_gl_lines:
                                    new_gl_lines, gl_seen_keys = self._fallback_glue_lines(fmt_value, wall_start, wall_end, wall_bottom, wall_top, gl_seen_keys)
                            elif not new_gl_lines:
                                new_gl_lines, gl_seen_keys = self._fallback_glue_lines(fmt_value, wall_start, wall_end, wall_bottom, wall_top, gl_seen_keys)
                        for gl_line in new_gl_lines:
                            f.write(gl_line + gl_newline)
                        gl_written = True
                    in_gl_section = False

                if not self.emit_saw_lines and stripped.startswith('ROB:') and routing_block_idx < len(routing_outputs):
                    block_lines = routing_outputs[routing_block_idx]
                    routing_block_idx += 1
                    for idx, block_line in enumerate(block_lines):
                        f.write(block_line + newline)
                    routing_skip_mode = 'drop'
                    continue

                if self.emit_saw_lines and stripped == 'EOF;':
                    if not saw_lines_written:
                        saw_lines_newline = newline or saw_lines_newline
                        for sl_line in saw_line_outputs:
                            f.write(sl_line + saw_lines_newline)
                        saw_lines_written = True
                    f.write(content + newline)
                    continue

                f.write(content + newline)



        if in_gl_section and not gl_written:
            if lock_gl_section:
                if new_gl_lines is None:
                    new_gl_lines, gl_seen_keys = self._original_glue_lines(fmt_value, wall_start, wall_end, glue_offset_value)
            else:
                if new_gl_lines is None:
                    new_gl_lines, gl_seen_keys = self.generate_glue_lines(horizontal_nl_groups, fmt_value, wall_start, wall_end, wall_bottom, wall_top)
                    if not new_gl_lines:
                        new_gl_lines, gl_seen_keys = self._fallback_glue_lines(fmt_value, wall_start, wall_end, wall_bottom, wall_top, gl_seen_keys)
                elif not new_gl_lines:
                    new_gl_lines, gl_seen_keys = self._fallback_glue_lines(fmt_value, wall_start, wall_end, wall_bottom, wall_top, gl_seen_keys)
            for gl_line in new_gl_lines:
                f.write(gl_line + gl_newline)
            for e, (ox, oxs, oy, oys) in zip(self.elements, mirrored_backups.get('elements', [])):
                e.x, e.x_size, e.y, e.y_size = ox, oxs, oy, oys
            for s, (ox, oxs, oy, oys) in zip(self.sta_elements, mirrored_backups.get('sta', [])):
                s.x, s.x_size, s.y, s.y_size = ox, oxs, oy, oys
            for g, (oxs, oxe, oys, oye) in zip(self.gl_lines, mirrored_backups.get('gl', [])):
                g.x_start, g.x_end, g.y_start, g.y_end = oxs, oxe, oys, oye

        if self.emit_saw_lines and not saw_lines_written:
            newline = saw_lines_newline or '\n'
            with open(output_path, 'a') as f:
                for sl_line in saw_line_outputs:
                    f.write(sl_line + newline)
            saw_lines_written = True

        if self.sheet_flip and sheet_flip_backups:
            for e, (otype, oz) in zip(self.elements, sheet_flip_backups.get('elements', [])):
                e.element_type, e.z = otype, oz


def format_float(value: float) -> str:
    """Return an integer-like string when possible, otherwise keep one decimal place."""
    as_int = int(round(value))
    if abs(as_int - value) < 1e-6:
        return str(as_int)
    return f"{value:.2f}"


def check_overlaps(elements, tolerance: float = 0.5):
    """Return a list of element pairs that overlap within the given tolerance."""
    overlaps = []
    for i, elem_a in enumerate(elements):
        for elem_b in enumerate(elements[i + 1:], start=i + 1):
            if CDTFile.elements_overlap(elem_a, elem_b, tolerance):
                overlaps.append((elem_a, elem_b))
    return overlaps


def process_cdt_file(file_path: str, actual_lengths=None, mirror=False, glue_offset=50.8, sheet_flip=False, emit_saw_lines: bool = False) -> str:
    """Adjust a CDT file based on user-supplied lengths and write an adjusted copy."""
    cdt_file = CDTFile(file_path)
    cdt_file.glue_edge_offset = glue_offset
    cdt_file.sheet_flip = sheet_flip
    cdt_file.emit_saw_lines = emit_saw_lines
    cdt_file.parse()
    base, ext = os.path.splitext(file_path)
    boo_elements = cdt_file.get_sheathing_elements()
    original_sum = sum(elem.x_size for elem in boo_elements)
    result = f"Original BOO1 Elements ({len(boo_elements)} panels) - Total x_size: {original_sum:.2f}mm:\n"
    result += f"{'Panel':<6} {'Orig x_size':<12} {'Orig x':<8}\n"
    result += "-" * 30 + "\n"
    for i, elem in enumerate(boo_elements, 1):
        result += f"{i:<6} {elem.x_size:<12.2f} {elem.x:<8.2f}\n"
    actual_lengths = actual_lengths or {}
    cdt_file.adjust_sheathing_positions(actual_lengths)
    adjusted_elements = cdt_file.get_sheathing_elements()
    adjusted_sum = sum(elem.x_size for elem in adjusted_elements)
    flyover = cdt_file.flyover_extension
    if cdt_file.last_sheet_mode == "flyover" and flyover > 0.05:
        overhang_text = f" - Flyover: {flyover:.2f}mm past ELM"
    elif flyover > 0.5:
        overhang_text = f" - Residual overhang {flyover:.2f}mm"
    else:
        overhang_text = " - Trimmed to footprint"
    result += f"\nAdjusted BOO1 Elements - Total x_size: {adjusted_sum:.2f}mm{overhang_text}:\n"
    result += f"{'Panel':<6} {'Adj x_size':<12} {'Adj x':<8}\n"
    result += "-" * 30 + "\n"
    for i, elem in enumerate(adjusted_elements, 1):
        result += f"{i:<6} {elem.x_size:<12.2f} {elem.x:<8.2f}\n"
    result += f"Total  {adjusted_sum:.2f}       -\n"
    base_suffix = 'xmsf' if mirror and sheet_flip else 'xf' if sheet_flip else 'xm' if mirror else 'x'
    suffix = base_suffix + ('sl' if emit_saw_lines else '')
    output_file = base + suffix + ext
    cdt_file.write_adjusted_file(output_file, mirror=mirror)
    result += f"\nAdjusted CDT file written to {output_file}"
    return result


class LengthInputDialog(tk.Toplevel):
    def __init__(self, parent, unique_sizes):
        super().__init__(parent)
        self.title("Enter Actual Lengths")
        self.attributes("-topmost", True)
        parent_x = parent.winfo_x()
        parent_y = parent.winfo_y()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()
        dialog_width = 450
        dialog_height = 120 + len(unique_sizes) * 70
        x = parent_x + (parent_width - dialog_width) // 2
        y = parent_y + (parent_height - dialog_height) // 2
        self.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")
        self.entries = {}
        self.imperial_labels = {}
        row = 0
        for size in sorted(unique_sizes):
            frame = tk.Frame(self, bd=1, relief='sunken', padx=10, pady=5)
            frame.grid(row=row, column=0, columnspan=2, pady=5, padx=10, sticky='ew')
            tk.Label(frame, text=f"Adjusted Length For Sheet Size {int(size)} (mm):", font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky='w')
            imperial_label = tk.Label(frame, text=f"({self.mm_to_imperial(size)})", fg="blue", font=('Arial', 9))
            imperial_label.grid(row=0, column=1, sticky='w', padx=(10,0))
            self.imperial_labels[size] = imperial_label
            entry = tk.Entry(frame, width=25, font=('Arial', 10))
            entry.grid(row=1, column=0, columnspan=2, pady=(5,0))
            entry.bind('<KeyRelease>', lambda e, s=size: self.update_imperial(s))
            self.entries[size] = entry
            row += 1
        tk.Button(self, text="Apply", command=self.apply, font=('Arial', 10, 'bold'), bg='lightgreen').grid(row=row, column=0, columnspan=2, pady=10)
        self.result = None
        self.wait_window()
    def mm_to_imperial(self, mm):
        inches = mm / 25.4
        feet = int(inches // 12)
        inches_rem = inches % 12
        inches_int = int(inches_rem)
        sixteenths = round((inches_rem - inches_int) * 16)
        if sixteenths == 16:
            inches_int += 1
            sixteenths = 0
        if inches_int == 12:
            feet += 1
            inches_int = 0
        if sixteenths == 0:
            sixteenths_str = ""
        elif sixteenths % 2 == 0:
            eighths = sixteenths // 2
            fractions = ["", "-1/8", "-1/4", "-3/8", "-1/2", "-5/8", "-3/4", "-7/8"]
            sixteenths_str = fractions[eighths]
        else:
            sixteenths_str = f"-{sixteenths}/16"
        return f"{feet}'-{inches_int}{sixteenths_str}\""
    def update_imperial(self, size):
        try:
            text = self.entries[size].get().strip()
            if text:
                val = float(text)
                imperial = self.mm_to_imperial(val)
                self.imperial_labels[size].config(text=f"({imperial})")
            else:
                self.imperial_labels[size].config(text=f"({self.mm_to_imperial(size)})")
        except ValueError:
            self.imperial_labels[size].config(text="(Invalid)")
    def apply(self):
        self.result = {}
        for size, entry in self.entries.items():
            text = entry.get().strip()
            if text:
                try:
                    val = float(text)
                    if val <= 0:
                        raise ValueError
                    self.result[size] = val
                except ValueError:
                    messagebox.showerror("Error", f"Invalid length for size {size}")
                    return
        self.destroy()


class CDTAdjusterGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("CDT Sheathing Adjuster")
        self.config_file = os.path.join(os.path.dirname(__file__), "config.json")

        # Load last folder
        self.last_folder = ""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    self.last_folder = config.get("last_folder", "")
            except:
                pass

        # Top frame: folder selection
        top = tk.Frame(root)
        top.grid(row=0, column=0, columnspan=3, sticky='ew', padx=6, pady=6)
        folder_label = tk.Label(top, text="CDT Folder Path:", cursor="hand2")
        folder_label.pack(side='left')
        folder_label.bind('<Button-1>', lambda e: self.open_folder_location())
        self.folder_entry = tk.Entry(top)
        self.folder_entry.pack(side='left', fill='x', expand=True, padx=(6, 6))
        self.folder_entry.insert(0, self.last_folder)
        tk.Button(top, text="Browse Folder", command=self.browse_folder).pack(side='left')

        # Control frame: mirror options and process
        ctrl = tk.Frame(root)
        ctrl.grid(row=1, column=0, columnspan=3, sticky='ew', padx=6)
        self.mirror_var = tk.BooleanVar(value=False)
        tk.Checkbutton(ctrl, text="Mirror Output", variable=self.mirror_var).pack(side='left')
        self.sheet_flip_var = tk.BooleanVar(value=False)
        tk.Checkbutton(ctrl, text="Sheet Flip", variable=self.sheet_flip_var).pack(side='left', padx=(6,0))
        self.saw_line_var = tk.BooleanVar(value=False)
        tk.Checkbutton(ctrl, text="Saw Lines (SL)", variable=self.saw_line_var).pack(side='left', padx=(6,0))
        self.glue_offset_var = tk.DoubleVar(value=50.8)
        tk.Label(ctrl, text="Glue Offset (mm):").pack(side='left', padx=(6,0))
        self.glue_offset_entry = tk.Entry(ctrl, textvariable=self.glue_offset_var, width=10)
        self.glue_offset_entry.pack(side='left')
        self.glue_offset_imperial_label = tk.Label(ctrl, text=self.mm_to_imperial(50.8), fg="blue", font=('Arial', 9))
        self.glue_offset_imperial_label.pack(side='left', padx=(5,0))
        self.glue_offset_var.trace_add("write", lambda *args: self.update_glue_imperial())
        tk.Button(
            ctrl,
            text="Process Selected Files",
            command=self.process,
            bg="#c8f7c5",
            activebackground="#a8edab"
        ).pack(side='right')
        tk.Button(ctrl, text="About", command=self.show_about).pack(side='right', padx=(6,0))

        middle = tk.PanedWindow(root, orient='horizontal')
        middle.grid(row=2, column=0, columnspan=3, sticky='nsew', padx=6, pady=6)
        left_col = tk.Frame(middle)
        tk.Label(left_col, text="Original CDT Files").pack(anchor='w')
        lb_frame = tk.Frame(left_col)
        lb_frame.pack(fill='both', expand=True)
        self.file_listbox_original = tk.Listbox(lb_frame, selectmode=tk.MULTIPLE)
        self.file_listbox_original.pack(side='left', fill='both', expand=True)
        sb1 = tk.Scrollbar(lb_frame, orient='vertical', command=self.file_listbox_original.yview)
        sb1.pack(side='left', fill='y')
        self.file_listbox_original.config(yscrollcommand=sb1.set)
        self.file_listbox_original.bind("<Button-3>", lambda e, lb=self.file_listbox_original: self.open_file(e, lb))
        middle.add(left_col)

        right_col = tk.Frame(middle)
        tk.Label(right_col, text="Processed CDT Files").pack(anchor='w')
        tk.Button(
            right_col,
            text="Clear Processed Files",
            command=self.clear_processed_files,
            bg="#f8c4c4",
            activebackground="#f2a3a3"
        ).pack(anchor='e', padx=(0,4))
        processed_wrapper = tk.Frame(right_col)
        processed_wrapper.pack(fill='both', expand=True)
        self.processed_categories = [
            ("Processed (x)", ('x',)),
            ("Mirror (xm)", ('xm',)),
            ("Sheet Flip (xf)", ('xf',)),
            ("Mirror + Sheet Flip (xmsf)", ('xmsf',)),
            ("Processed + Saw Line (xsl)", ('xsl',)),
            ("Mirror + Saw Line (xmsl)", ('xmsl',)),
            ("Sheet Flip + Saw Line (xfsl)", ('xfsl',)),
            ("Mirror+Sheet Flip + Saw Line (xmsfsl)", ('xmsfsl',)),
        ]
        self.processed_lists: Dict[str, tk.Listbox] = {}
        self.suffix_to_listbox: Dict[str, tk.Listbox] = {}
        processed_grid = tk.Frame(processed_wrapper)
        processed_grid.pack(fill='both', expand=True)
        columns = 2
        for idx, (label, suffixes) in enumerate(self.processed_categories):
            section = tk.LabelFrame(processed_grid, text=label)
            row = idx // columns
            col = idx % columns
            section.grid(row=row, column=col, sticky='nsew', padx=4, pady=4)
            processed_grid.grid_rowconfigure(row, weight=1)
            processed_grid.grid_columnconfigure(col, weight=1)
            lb = tk.Listbox(section, selectmode=tk.SINGLE, height=6)
            lb.pack(side='left', fill='both', expand=True)
            sb = tk.Scrollbar(section, orient='vertical', command=lb.yview)
            sb.pack(side='right', fill='y')
            lb.config(yscrollcommand=sb.set)
            lb.bind("<Button-3>", lambda e, target=lb: self.open_file(e, target))
            self.processed_lists[label] = lb
            for suffix in suffixes:
                self.suffix_to_listbox[suffix] = lb
        self.processed_suffix_order = sorted(self.suffix_to_listbox.keys(), key=len, reverse=True)
        self.default_processed_list = self.processed_lists.get("Processed (x)")
        middle.add(right_col)

        self.result_text = tk.Text(root, height=15)
        self.result_text.grid(row=3, column=0, columnspan=3, sticky='ew', padx=6, pady=(0,6))

        self.file_listbox_original.bind('<<ListboxSelect>>', lambda e: None)
        for lb in self.processed_lists.values():
            lb.bind('<<ListboxSelect>>', lambda e: None)

        root.grid_rowconfigure(2, weight=1)
        root.grid_columnconfigure(0, weight=1)
        root.grid_columnconfigure(1, weight=1)

        if self.last_folder and os.path.exists(self.last_folder):
            self.load_folder(self.last_folder)

    def browse_folder(self):
        folder_path = tk.filedialog.askdirectory()
        if folder_path:
            self.folder_entry.delete(0, tk.END)
            self.folder_entry.insert(0, folder_path)
            self.last_folder = folder_path
            self.save_config()
            self.load_folder(folder_path)

    def save_config(self):
        config = {"last_folder": self.last_folder}
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f)
        except:
            pass

    def open_folder_location(self):
        folder = self.folder_entry.get().strip()
        if not folder:
            messagebox.showerror("Error", "Folder path is not set.")
            return
        if not os.path.isdir(folder):
            messagebox.showerror("Error", "Folder path does not exist.")
            return
        try:
            os.startfile(folder)
        except OSError as exc:
            messagebox.showerror("Error", f"Failed to open folder: {exc}")

    def clear_processed_files(self):
        folder = self.folder_entry.get().strip()
        if not folder:
            messagebox.showerror("Error", "Folder path is not set.")
            return
        if not os.path.isdir(folder):
            messagebox.showerror("Error", "Folder path does not exist.")
            return
        suffixes = list(self.suffix_to_listbox.keys())
        if not suffixes:
            messagebox.showinfo("Info", "No processed suffixes configured.")
            return
        to_delete = []
        for file in os.listdir(folder):
            if not file.lower().endswith('.cdt'):
                continue
            base = os.path.splitext(file)[0].lower()
            if any(base.endswith(suffix) for suffix in suffixes):
                to_delete.append(file)
        if not to_delete:
            messagebox.showinfo("Info", "No processed files found to delete.")
            return
        confirm = messagebox.askyesno(
            "Confirm Delete",
            f"Delete {len(to_delete)} processed file(s) from:\n{folder}?",
            icon='warning'
        )
        if not confirm:
            return
        errors = []
        for file in to_delete:
            try:
                os.remove(os.path.join(folder, file))
            except OSError as exc:
                errors.append(f"{file}: {exc}")
        if errors:
            messagebox.showerror("Error", "Some files could not be deleted:\n" + '\n'.join(errors))
        else:
            messagebox.showinfo("Success", f"Deleted {len(to_delete)} processed file(s).")
        self.load_folder(folder)

    def load_folder(self, folder_path):
        self.file_listbox_original.delete(0, tk.END)
        for lb in self.processed_lists.values():
            lb.delete(0, tk.END)
        for file in sorted(os.listdir(folder_path)):
            if not file.lower().endswith('.cdt'):
                continue
            base = os.path.splitext(file)[0]
            lower_base = base.lower()
            assigned = False
            for suffix in self.processed_suffix_order:
                if lower_base.endswith(suffix):
                    target_lb = self.suffix_to_listbox.get(suffix)
                    if target_lb is not None:
                        target_lb.insert(tk.END, file)
                        assigned = True
                        break
            if not assigned:
                self.file_listbox_original.insert(tk.END, file)
        self.file_listbox_original.selection_clear(0, tk.END)
        for lb in self.processed_lists.values():
            lb.selection_clear(0, tk.END)

    def mm_to_imperial(self, mm):
        inches = mm / 25.4
        feet = int(inches // 12)
        inches_rem = inches % 12
        inches_int = int(inches_rem)
        sixteenths = round((inches_rem - inches_int) * 16)
        if sixteenths == 16:
            inches_int += 1
            sixteenths = 0
        if inches_int == 12:
            feet += 1
            inches_int = 0
        if sixteenths == 0:
            sixteenths_str = ""
        elif sixteenths % 2 == 0:
            eighths = sixteenths // 2
            fractions = ["", "-1/8", "-1/4", "-3/8", "-1/2", "-5/8", "-3/4", "-7/8"]
            sixteenths_str = fractions[eighths]
        else:
            sixteenths_str = f"-{sixteenths}/16"
        return f"{feet}'-{inches_int}{sixteenths_str}\""

    def update_glue_imperial(self):
        raw = self.glue_offset_entry.get().strip()
        if not raw:
            self.glue_offset_imperial_label.config(text="(Enter value)")
            return
        try:
            val = float(raw)
            imperial = self.mm_to_imperial(val)
            self.glue_offset_imperial_label.config(text=f"({imperial})")
        except ValueError:
            self.glue_offset_imperial_label.config(text="(Invalid)")

    def open_file(self, event, listbox):
        try:
            idx = listbox.nearest(event.y)
            file_name = listbox.get(idx)
            folder = self.folder_entry.get().strip()
            if folder and file_name:
                file_path = os.path.join(folder, file_name)
                os.startfile(file_path)
        except Exception:
            pass


    def process(self):
        folder_path = self.folder_entry.get().strip()
        selected_indices = self.file_listbox_original.curselection()
        if not selected_indices:
            messagebox.showerror("Error", "No files selected.")
            return
        unique_sizes = set()
        for idx in selected_indices:
            file_name = self.file_listbox_original.get(idx)
            file_path = os.path.join(folder_path, file_name)
            try:
                cdt = CDTFile(file_path)
                cdt.parse()
                boo1_elements = [elem for elem in cdt.get_sheathing_elements() if elem.element_type == 'BOO1']
                for i, elem in enumerate(boo1_elements):
                    if i < len(boo1_elements) - 1:
                        unique_sizes.add(elem.x_size)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to parse {file_name}: {str(e)}")
                return
        if not unique_sizes:
            messagebox.showerror("Error", "No BOO1 elements found in selected files.")
            return
        dialog = LengthInputDialog(self.root, unique_sizes)
        if dialog.result is None:
            return
        actual_lengths = dialog.result
        results = []
        for idx in selected_indices:
            file_name = self.file_listbox_original.get(idx)
            file_path = os.path.join(folder_path, file_name)
            try:
                result = process_cdt_file(
                    file_path,
                    actual_lengths,
                    mirror=self.mirror_var.get(),
                    glue_offset=self.glue_offset_var.get(),
                    sheet_flip=self.sheet_flip_var.get(),
                    emit_saw_lines=self.saw_line_var.get()
                )
                results.append(f"Processed {file_name}:\n{result}\n")
            except Exception as e:
                results.append(f"Error processing {file_name}: {str(e)}\n")
        self.result_text.delete(1.0, tk.END)
        self.result_text.insert(tk.END, '\n'.join(results))
        self.load_folder(folder_path)

    def show_about(self):
        about = tk.Toplevel(self.root)
        about.title("What This Script Does")
        about.geometry("700x420")
        about.transient(self.root)
        about.attributes('-topmost', True)
        text = tk.Text(about, wrap='word')
        text.pack(fill='both', expand=True, padx=8, pady=8)
        bullets = [
            "Automates CDT sheathing alignment so exterior boards match actual measured lengths while keeping the structural ELM footprint intact.",
            "Preserves the original ELM span in the file header; trims or converts trailing sheathing panels as needed to match real lengths.",
            "Applies the '27-inch rule' for the trailing BOO1 panel: short residual gaps are trimmed; larger residuals convert the trailing panel to a full-sheet flyover beyond the ELM.",
            "Flyovers are positioned on the outboard (non-origin) edge so the squaring/reference edge at x=0 remains unchanged.",
            "Attempts minimal nudges to structural members to clear overlaps (uses small margins) but preserves long spanning horizontal members when possible.",
            "Regenerates nail lines, glue lines, and metadata with formatted numeric output (integers when exact, otherwise two-decimal formatting) to reflect adjusted geometry.",
            "Rebuilds glue lines as continuous runs with edge offsets so glue applicators avoid panel edges (configurable offset used in generation).",
            "Emits warnings (collected in the processing log) when adjustments exceed tolerances so manual review can target remaining problem spots.",
        ]
        notes = [
            "Additional features in this tool:",
            "- Mirror Output: creates a left/right (horizontal X) mirror of coordinates for the output file.",
            "  * Reflects X positions about ELM.x_size (new_x = ELM.x_size - (x + width)).",
            "  * The tool does NOT flip panel faces (BOO remains BOO); if you need top↔bottom face flips, request a separate 'face flip' feature.",
            "- Sheet Flip: changes BOO (Board On Outside) to BOI (Board On Inside) and adjusts Z coordinates by sheet thickness (typically 18mm) to simulate flipping the sheet orientation.",
            "  * Locks ELM, STA, and GL positions; only adjusts sheathing Z and type.",
            "  * Rebuilds nail lines (NL) based on STA positions for vertical nails and sheet edges for horizontal nails.",
            "- Saw Lines (SL): removes router (RL) blocks and emits SL commands only along flyover edges with inclination 900° and tool index 1 when enabled.",
            "- Glue Offset: Configurable distance (default 50.8mm = 2\") to keep glue lines away from panel edges. Applied to horizontal glue lines when their spans touch the wall edges.",
            "- Processing runs per selected file; re-use the dialog to apply the same length set across multiple selections.",
            "- File naming: generated files use suffixes like 'x' (adjusted), 'xm' (mirrored), 'xf' (sheet flipped), 'xmsf' (mirrored + sheet flipped) appended before the extension; enabling Saw Lines adds a trailing 'sl'.",
            "- The in-memory model is restored after write so subsequent operations start from the original parsed geometry.",
            "- If you want different filename suffixes, per-file length dialogs, or face-flip behavior, I can add those as options.",
        ]
        text.insert('end', "Summary:\n\n")
        for b in bullets:
            text.insert('end', f"• {b}\n\n")
        text.insert('end', "Notes & Current Behavior:\n\n")
        for n in notes:
            text.insert('end', f"{n}\n\n")
        text.config(state='disabled')
        tk.Button(about, text='Close', command=about.destroy).pack(pady=(0,8))


def main():
    root = tk.Tk()
    app = CDTAdjusterGUI(root)
    root.geometry('1200x800')
    root.mainloop()

if __name__ == '__main__':
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        result = process_cdt_file(file_path)
        print(result)
    else:
        main()