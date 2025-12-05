from enum import Enum
import math
import re
import tkinter as tk
from tkinter import filedialog, messagebox
import os
import json
from typing import Any, Dict, List, Optional, Set, Tuple

FLYOVER_THRESHOLD_MM = 27.0 * 25.4  # 27 inches expressed in millimetres
GLUE_EDGE_OFFSET = 50.8  # Maintain glue lines 2 inches (50.8 mm) away from panel edges

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
                amplitude: float, wavelength: float, tool_index: int, widths: list[int] | None) -> str:
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
        self.length_warnings: List[str] = []
        self.flyover_extension: float = 0.0
        self.last_sheet_mode: str = "trimmed"
        self.last_sheet_target: float = 0.0
        self.last_sheet_gap: float = 0.0
        self.original_x_span: Optional[float] = None

    def parse(self):
        with open(self.file_path, 'r') as f:
            self.lines = f.readlines()
        
        for line in self.lines:
            line = line.strip()
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

        self.resolve_structural_overlaps()
        self.offset_horizontal_members()
        self.resolve_structural_overlaps()

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

                        preserve_horizontal = horizontal.x_size >= 4000
                        if preserve_horizontal:
                            if not hasattr(vertical, '_trimmed_for_horizontal'):
                                desired_bottom = min(top - gap_needed, h_top + gap_needed)
                                if desired_bottom > bottom + tolerance:
                                    vertical.y = desired_bottom
                                    vertical.y_size = top - desired_bottom
                                    setattr(vertical, '_trimmed_for_horizontal', True)
                                    changed = True
                                    continue
                        else:
                            left = horizontal.x
                            right = horizontal.x + horizontal.x_size
                            v_left = vertical.x
                            v_right = vertical.x + vertical.x_size
                            if v_left < right and v_right > left:
                                if v_left >= left:
                                    new_right = max(left, v_left - gap_needed)
                                    if new_right < right - tolerance:
                                        horizontal.x_size = max(0.0, new_right - left)
                                        self._clamp_element(horizontal)
                                        changed = True
                                        continue
                                else:
                                    new_left = min(right, v_right + gap_needed)
                                    if new_left > left + tolerance:
                                        delta = new_left - left
                                        horizontal.x += delta
                                        horizontal.x_size = max(0.0, right - new_left)
                                        self._clamp_element(horizontal)
                                        changed = True
                                        continue

                    required_x = overlap_x + margin
                    required_y = overlap_y + margin
                    axes = [('x', required_x), ('y', required_y)]
                    if required_y < required_x:
                        axes.reverse()

                    resolved = False
                    for axis, shift in axes:
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
                        if self._shift_and_check(elem_b, elem_a, required_x * 0.5, required_y * 0.5, tolerance):
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

    def generate_glue_lines(self, horizontal_nl_groups: Dict[Tuple[str, float, float], Dict[str, Any]], fmt_value, wall_start: float, wall_end: float, wall_bottom: float, wall_top: float) -> List[str]:
        default_tool = self.gl_lines[0].tool_index if self.gl_lines else 16
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

        for key in ordered_keys:
            if key in emitted:
                continue
            orient = key[0]
            originals = key_to_original.get(key, [])
            if orient == 'horizontal' and key in horizontal_nl_groups:
                info = horizontal_nl_groups[key]
                segments = info.get('segments', [])
                if not segments:
                    for gl in originals:
                        new_lines.append(gl.to_string(fmt_value))
                    emitted.add(key)
                    continue
                span_start = info.get('min_nl')
                span_end = info.get('max_nl')
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
                y_value = info.get('y', template.y_start if template else 0.0)
                z_value = info.get('z', template.z_start if template else 0.0)
                tool_index = template.tool_index if template else default_tool
                widths = template.widths if template else None
                gl_start = span_start
                gl_end = span_end
                if span_start <= wall_start + epsilon:
                    gl_start = min(max(wall_start, span_start + self.glue_edge_offset), gl_end)
                if span_end >= wall_end - epsilon:
                    gl_end = max(min(wall_end, span_end - self.glue_edge_offset), gl_start)
                if gl_end < gl_start:
                    gl_end = gl_start
                line = GlueLine._format(fmt_value, gl_start, y_value, z_value, gl_end, y_value, z_value, amplitude, wavelength, tool_index, widths)
                new_lines.append(line)
                emitted.add(key)
            elif orient == 'vertical' and originals:
                for gl in originals:
                    y_start = gl.y_start
                    y_end = gl.y_end
                    if y_start <= wall_bottom + epsilon:
                        y_start = min(max(wall_bottom, y_start + self.glue_edge_offset), y_end)
                    if y_end >= wall_top - epsilon:
                        y_end = max(min(wall_top, y_end - self.glue_edge_offset), y_start)
                    line = gl.format_with(fmt_value, gl.x_start, y_start, gl.z_start, gl.x_end, y_end, gl.z_end, gl.amplitude, gl.wavelength, gl.tool_index)
                    new_lines.append(line)
                emitted.add(key)
            else:
                for gl in originals:
                    new_lines.append(gl.to_string(fmt_value))
                emitted.add(key)

        for key, info in horizontal_nl_groups.items():
            if key in emitted:
                continue
            segments = info.get('segments', [])
            if not segments:
                continue
            span_start = info.get('min_nl')
            span_end = info.get('max_nl')
            if span_start is None or span_end is None:
                merged = self.merge_axis_segments(segments, tolerance)
                if not merged:
                    continue
                span_start = merged[0][0]
                span_end = merged[-1][1]
            gl_start = span_start
            gl_end = span_end
            if span_start <= wall_start + epsilon:
                gl_start = min(max(wall_start, span_start + GLUE_EDGE_OFFSET), gl_end)
            if span_end >= wall_end - epsilon:
                gl_end = max(min(wall_end, span_end - GLUE_EDGE_OFFSET), gl_start)
            if gl_end < gl_start:
                gl_end = gl_start
            y_value = info.get('y', 0.0)
            z_value = info.get('z', 0.0)
            line = GlueLine.default_format(fmt_value, gl_start, y_value, z_value, gl_end, y_value, z_value, 0.0, 0.0, default_tool)
            new_lines.append(line)
            emitted.add(key)

        return new_lines

    def write_adjusted_file(self, output_path: str):
        """Write the adjusted CDT file with updated geometry and formatting."""

        def fmt_value(value: float, width: int) -> str:
            as_int = int(round(value))
            if abs(as_int - value) < 1e-6:
                return f"{as_int:>{max(width, len(str(as_int)))}}"
            text = f"{value:.2f}"
            if width and len(text) > width:
                text = f"{value:.3f}"
            return f"{text:>{max(width, len(text))}}"

        sheathing_index = 0
        sta_index = 0
        top_surface_z = None
        sheathing = self.get_sheathing_elements()
        if sheathing:
            top_surface_z = max(elem.z + elem.z_size for elem in sheathing)
            first_sheet = min(sheathing, key=lambda e: e.x)
            last_sheet = max(sheathing, key=lambda e: e.x + e.x_size)
            wall_start = first_sheet.x
            wall_end = last_sheet.x + last_sheet.x_size
            wall_bottom = min(elem.y for elem in sheathing)
            wall_top = max(elem.y + elem.y_size for elem in sheathing)
        else:
            wall_start = 0.0
            wall_end = self.header.x_size if self.header else 0.0
            wall_bottom = 0.0
            wall_top = self.header.y_size if self.header else 0.0

        seen_nl_keys = set()
        horizontal_nl_groups: Dict[Tuple[str, float, float], Dict[str, Any]] = {}
        horizontal_gl_templates: Dict[Tuple[str, float, float], GlueLine] = {}
        gl_key_by_y: Dict[float, Tuple[str, float, float]] = {}
        for gl in self.gl_lines:
            key = gl.group_key()
            if key[0] == 'horizontal' and key not in horizontal_gl_templates:
                horizontal_gl_templates[key] = gl
                gl_key_by_y[key[1]] = key

        new_gl_lines: Optional[List[str]] = None
        in_gl_section = False
        gl_written = False
        gl_newline = '\n'

        with open(output_path, 'w') as f:
            for line in self.lines:
                newline = '\n' if line.endswith('\n') else ''
                content = line.rstrip('\n')
                stripped = content.strip()

                if not stripped:
                    f.write(content + newline)
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
                        key = (
                            round(min(x_start, x_end), 3),
                            round(min(y_start, y_end), 3),
                            round(max(x_start, x_end), 3),
                            round(max(y_start, y_end), 3),
                            round(nail_distance, 3)
                        )
                        if key in seen_nl_keys:
                            continue
                        seen_nl_keys.add(key)
                        dx = abs(x_end - x_start)
                        dy = abs(y_end - y_start)
                        if dy <= 1e-3:
                            y_mid = round(0.5 * (y_start + y_end), 3)
                            gl_key = gl_key_by_y.get(y_mid)
                            if gl_key:
                                nl_key = gl_key
                                template = horizontal_gl_templates.get(gl_key)
                                z_candidate = template.z_start if template else top_surface_z
                            else:
                                z_candidate = top_surface_z
                                z_round = round(z_candidate if z_candidate is not None else 0.0, 3)
                                nl_key = ('horizontal', y_mid, z_round)
                            seg_start = min(x_start, x_end)
                            seg_end = max(x_start, x_end)
                            info = horizontal_nl_groups.setdefault(
                                nl_key,
                                {
                                    'segments': [],
                                    'min_nl': seg_start,
                                    'max_nl': seg_end
                                }
                            )
                            info['segments'].append((seg_start, seg_end))
                            info['min_nl'] = min(info.get('min_nl', seg_start), seg_start)
                            info['max_nl'] = max(info.get('max_nl', seg_end), seg_end)
                            if 'y' not in info:
                                info['y'] = 0.5 * (y_start + y_end)
                            if 'z' not in info:
                                info['z'] = z_candidate if z_candidate is not None else 0.0
                        rebuilt = ':'.join(parts)
                        f.write(rebuilt + ';' + newline)
                        continue

                if stripped == 'GLUE_LINES;':
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
                        if new_gl_lines is None:
                            new_gl_lines = self.generate_glue_lines(horizontal_nl_groups, fmt_value, wall_start, wall_end, wall_bottom, wall_top)
                        for gl_line in new_gl_lines:
                            f.write(gl_line + gl_newline)
                        gl_written = True
                    in_gl_section = False

                f.write(content + newline)

            if in_gl_section and not gl_written:
                if new_gl_lines is None:
                    new_gl_lines = self.generate_glue_lines(horizontal_nl_groups, fmt_value, wall_start, wall_end, wall_bottom, wall_top)
                for gl_line in new_gl_lines:
                    f.write(gl_line + gl_newline)


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
        for elem_b in elements[i + 1:]:
            if CDTFile.elements_overlap(elem_a, elem_b, tolerance):
                overlaps.append((elem_a, elem_b))
    return overlaps


def contain_within_elm(elements, header: CDTHeader):
    """Clamp structural elements so they remain inside the ELM envelope."""
    if header is None:
        return
    for elem in elements:
        max_x = max(0.0, header.x_size - elem.x_size)
        max_y = max(0.0, header.y_size - elem.y_size)
        if elem.x < 0:
            elem.x = 0
        elif elem.x > max_x:
            elem.x = max_x
        if elem.y < 0:
            elem.y = 0
        elif elem.y > max_y:
            elem.y = max_y


def process_cdt_file(file_path: str, actual_lengths=None) -> str:
    """Adjust a CDT file based on user-supplied lengths and write an adjusted copy."""
    cdt_file = CDTFile(file_path)
    cdt_file.parse()

    boo_elements = cdt_file.get_sheathing_elements()
    original_sum = sum(elem.x_size for elem in boo_elements)
    result = f"Original BOO1 Elements ({len(boo_elements)} panels) - Total x_size: {format_float(original_sum)}mm:\n"
    result += f"{'Panel':<6} {'Orig x_size':<12} {'Orig x':<8}\n"
    result += "-" * 30 + "\n"
    for i, elem in enumerate(boo_elements, 1):
        result += f"{i:<6} {format_float(elem.x_size):<12} {format_float(elem.x):<8}\n"

    actual_lengths = actual_lengths or {}
    cdt_file.adjust_sheathing_positions(actual_lengths)
    adjusted_elements = cdt_file.get_sheathing_elements()
    adjusted_sum = sum(elem.x_size for elem in adjusted_elements)
    flyover = cdt_file.flyover_extension
    if cdt_file.last_sheet_mode == "flyover" and flyover > 0.05:
        overhang_text = f" - Flyover: {format_float(flyover)}mm past ELM"
    elif flyover > 0.5:
        overhang_text = f" - Residual overhang {format_float(flyover)}mm"
    else:
        overhang_text = " - Trimmed to footprint"
    result += f"\nAdjusted BOO1 Elements - Total x_size: {format_float(adjusted_sum)}mm{overhang_text}:\n"
    result += f"{'Panel':<6} {'Adj x_size':<12} {'Adj x':<8}\n"
    result += "-" * 30 + "\n"
    for i, elem in enumerate(adjusted_elements, 1):
        result += f"{i:<6} {format_float(elem.x_size):<12} {format_float(elem.x):<8}\n"
    result += f"Total  {format_float(adjusted_sum)}       -\n"

    overlaps = check_overlaps(adjusted_elements)
    if overlaps:
        result += "\nWarning: Overlaps detected, attempting to contain STA within ELM.\n"
        contain_within_elm(cdt_file.sta_elements, cdt_file.header)
        overlaps = check_overlaps(adjusted_elements)
        if overlaps:
            result += "Warning: Overlaps still detected after containing within ELM:\n"
            for elem1, elem2 in overlaps:
                result += (
                    f"- {elem1.element_type} at ({format_float(elem1.x)}, {format_float(elem1.y)}) size "
                    f"({format_float(elem1.x_size)}, {format_float(elem1.y_size)}) overlaps with "
                    f"{elem2.element_type} at ({format_float(elem2.x)}, {format_float(elem2.y)}) size "
                    f"({format_float(elem2.x_size)}, {format_float(elem2.y_size)})\n"
                )
        else:
            result += "Overlaps resolved by containing STA within ELM.\n"

    base, ext = os.path.splitext(file_path)
    output_file = base + 'x' + ext
    cdt_file.write_adjusted_file(output_file)
    result += f"\nAdjusted CDT file written to {output_file}"
    preserved_span = cdt_file.header.x_size
    summary_lines = [
        f"- ELM footprint preserved at {format_float(preserved_span)}mm"
    ]
    if cdt_file.last_sheet_mode == "flyover":
        summary_lines.append(
            f"- Trailing BOO1 converted to full sheet with flyover of {format_float(cdt_file.flyover_extension)}mm"
        )
    else:
        summary_lines.append(
            f"- Trailing BOO1 trimmed to {format_float(cdt_file.last_sheet_target)}mm (≤27\")"
        )
    summary_lines.append("- Dimensions formatted to two decimal places")
    result += "\nSummary:\n" + "\n".join(summary_lines)

    if cdt_file.length_warnings:
        result += "\nWarnings:\n"
        for warning in cdt_file.length_warnings:
            result += f"- {warning}\n"

    return result

class LengthInputDialog(tk.Toplevel):
    def __init__(self, parent, unique_sizes):
        super().__init__(parent)
        self.title("Enter Actual Lengths")
        self.attributes("-topmost", True)  # Stay on top
        
        # Center the dialog
        parent_x = parent.winfo_x()
        parent_y = parent.winfo_y()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()
        dialog_width = 450
        dialog_height = 120 + len(unique_sizes) * 70  # Adjusted height for better spacing
        x = parent_x + (parent_width - dialog_width) // 2
        y = parent_y + (parent_height - dialog_height) // 2
        self.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")
        
        self.entries = {}
        self.imperial_labels = {}
        row = 0
        for size in sorted(unique_sizes):
            # Frame for each size
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
        
        # Apply button
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
            if text:  # Only process if not blank
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
        
        # Folder path
        tk.Label(root, text="CDT Folder Path:").grid(row=0, column=0, sticky='e')
        self.folder_entry = tk.Entry(root, width=50)
        self.folder_entry.grid(row=0, column=1)
        self.folder_entry.insert(0, self.last_folder)
        tk.Button(root, text="Browse Folder", command=self.browse_folder).grid(row=0, column=2)
        
        # File listbox
        tk.Label(root, text="Select CDT Files:").grid(row=1, column=0, sticky='ne')
        self.file_listbox = tk.Listbox(root, selectmode=tk.MULTIPLE, height=10, width=60)
        self.file_listbox.grid(row=1, column=1, columnspan=2)
        self.file_listbox.bind("<Button-3>", self.open_file)
        
        # Process button
        tk.Button(root, text="Process Selected Files", command=self.process).grid(row=2, column=0, columnspan=3)
        
        # Result text
        self.result_text = tk.Text(root, height=20, width=80)
        self.result_text.grid(row=3, column=0, columnspan=3)
        
        # Load folder if last_folder is set
        if self.last_folder and os.path.exists(self.last_folder):
            self.load_folder(self.last_folder)
    
    def browse_folder(self):
        folder_path = filedialog.askdirectory()
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
    
    def load_folder(self, folder_path):
        self.file_listbox.delete(0, tk.END)
        for file in os.listdir(folder_path):
            if file.lower().endswith('.cdt'):
                self.file_listbox.insert(tk.END, file)
    
    def open_file(self, event):
        try:
            idx = self.file_listbox.nearest(event.y)
            file_name = self.file_listbox.get(idx)
            folder = self.folder_entry.get().strip()
            if folder and file_name:
                file_path = os.path.join(folder, file_name)
                os.startfile(file_path)  # Open original
                # Check for adjusted version and open for comparison
                adjusted_path = file_path.replace('.CDT', '_adjusted.CDT').replace('.cdt', '_adjusted.cdt')
                if os.path.exists(adjusted_path):
                    os.startfile(adjusted_path)  # Open adjusted for split-screen comparison
        except:
            pass
    
    def process(self):
        folder_path = self.folder_entry.get().strip()
        selected_indices = self.file_listbox.curselection()
        if not selected_indices:
            messagebox.showerror("Error", "No files selected.")
            return
        
        # Collect unique BOO1 sizes from selected files, excluding the last BOO1 in each file
        unique_sizes = set()
        for idx in selected_indices:
            file_name = self.file_listbox.get(idx)
            file_path = os.path.join(folder_path, file_name)
            try:
                cdt = CDTFile(file_path)
                cdt.parse()
                boo1_elements = [elem for elem in cdt.get_sheathing_elements() if elem.element_type == 'BOO1']
                for i, elem in enumerate(boo1_elements):
                    if i < len(boo1_elements) - 1:  # Exclude last BOO1
                        unique_sizes.add(elem.x_size)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to parse {file_name}: {str(e)}")
                return
        
        if not unique_sizes:
            messagebox.showerror("Error", "No BOO1 elements found in selected files.")
            return
        
        # Show dialog for inputting actual lengths
        dialog = LengthInputDialog(self.root, unique_sizes)
        if dialog.result is None:
            return  # Cancelled
        
        actual_lengths = dialog.result
        
        # Process each file
        results = []
        for idx in selected_indices:
            file_name = self.file_listbox.get(idx)
            file_path = os.path.join(folder_path, file_name)
            try:
                result = process_cdt_file(file_path, actual_lengths)
                results.append(f"Processed {file_name}:\n{result}\n")
            except Exception as e:
                results.append(f"Error processing {file_name}: {str(e)}\n")
        
        self.result_text.delete(1.0, tk.END)
        self.result_text.insert(tk.END, '\n'.join(results))
        
        # Unselect the processed files
        self.file_listbox.selection_clear(0, tk.END)

# Example usage
if __name__ == "__main__":
    root = tk.Tk()
    app = CDTAdjusterGUI(root)
    root.mainloop()