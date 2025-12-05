from enum import Enum
import math
import copy
import shutil
import re
import tkinter as tk
from tkinter import filedialog, messagebox
import os
import json
from typing import Any, Dict, List, Optional, Set, Tuple
import argparse
import sys

FLYOVER_THRESHOLD_MM = 27.0 * 25.4  # 27 inches expressed in millimetres
GLUE_EDGE_OFFSET = 50.8  # Maintain glue lines 2 inches (50.8 mm) away from panel edges
DEFAULT_NL_EDGE_OFFSET = 76.2  # Default nail-line start/end offset from sheet edges (mm) (3")
# Nail spacing rules (mm)
PERIMETER_NL_SPACING = 152.4  # 6"
FIELD_NL_SPACING = 304.8      # 12"
# Distances from special edges (mm)
TONGUE_GROOVE_OFFSET = 12.7   # 1/2"
SQUARE_EDGE_OFFSET = 6.35     # 1/4"
MEMBER_EDGE_DISTANCE = 76.2   # 3"

# Load user presets from src/config.json when available. Presets may override
# defaults for sheet-flip behavior (nl edge offset, spacings, member edge distance).
PRESETS = {}
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
        # Read the file lines and populate header/elements/sta/gl lists
        with open(self.file_path, 'r', encoding='utf-8', errors='replace') as f:
            self.lines = f.readlines()

        for raw in self.lines:
            line = raw.rstrip('\n')  # Strip newline character
            s = line.strip()
            if not s:
                continue
            try:
                if s.startswith('ELM:'):
                    try:
                        self.header = CDTHeader.from_elm_line(s)
                    except Exception:
                        # Ignore malformed header lines
                        pass
                elif s.startswith('BOO') or s.startswith('BOI'):  # Handle sheathing elements
                    try:
                        elem = SheathingElement.from_cdt_line(s)
                        self.elements.append(elem)
                    except Exception:
                        pass
                elif s.startswith('STA:') or s.startswith('STB:'):
                    try:
                        elem = SheathingElement.from_cdt_line(s)
                        self.sta_elements.append(elem)
                    except Exception:
                        pass
                elif s.startswith('GL:'):
                    try:
                        gl = GlueLine.from_line(s)
                        self.gl_lines.append(gl)
                    except Exception:
                        pass
            except Exception:
                # continue on any unexpected parsing error for a line
                continue

        if self.header:
            self.original_x_span = self.header.x_size
            # Preserve original Y span as well so processing does not
            # unintentionally overwrite the intended ELM y_size value.
            self.original_y_span = self.header.y_size

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
            if elem.element_type.startswith('BOO') and elem.x_size in actual_lengths:  # Adjust BOO elements
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

            # Use the adjusted (final) sheathing span as the authoritative ELM
            # footprint so header values match the actual panels placed in the
            # file. This avoids downstream warnings about ELM size mismatches
            # caused by rounding differences. Values are written with two
            # decimals later when composing the ELM line.
            adjusted_span = final_sum
            self.header.x_size = adjusted_span
            self.header.length = adjusted_span

        self.resolve_structural_overlaps()
        self.offset_horizontal_members()
        self.resolve_structural_overlaps()

        # Update ELM Y span based on the actual component extents so the
        # header accurately reflects the placed studs/sheathing. Use the
        # computed span (rounded to two decimals) to avoid fractional
        # mismatches that trigger warnings in downstream tools.
        try:
            # Compute Y span including both sheathing and structural members
            min_y, max_y = self.compute_y_span(self.get_all_structural_elements())
            span = max_y - min_y
            if span < 0:
                span = 0.0
            self.header.y_size = round(span, 2)
            self.header.measurement = round(span, 2)
        except Exception:
            # Fallback: preserve original if computation fails
            if hasattr(self, 'original_y_span') and self.original_y_span is not None:
                try:
                    self.header.y_size = self.original_y_span
                    self.header.measurement = self.original_y_span
                except Exception:
                    pass
        # Ensure header X/Y/Z reflect the union of placed sheathing and
        # structural members (STA). Some downstream validators compute the
        # expected ELM footprint from the actual STA and BOO extents; if the
        # header differs by small rounding deltas this triggers numerous
        # warnings. Make the header authoritative by taking the maximum of the
        # adjusted sheathing span and the STA extents and rounding to two
        # decimals.
        try:
            # compute max STA/BOO extents
            max_sta_end = max(((s.x + s.x_size) for s in self.sta_elements), default=0.0)
            max_boo_end = max(((b.x + b.x_size) for b in self.get_sheathing_elements()), default=0.0)
            pass
            # ensure header.x_size covers both sheathing and STA extents
            desired_x = max(float(self.header.x_size), float(max_sta_end), float(max_boo_end))
            self.header.x_size = round(desired_x, 2)

            # similarly for Y: ensure header covers STA and BOO Y extents
            max_sta_y_end = max(((s.y + s.y_size) for s in self.sta_elements), default=0.0)
            max_boo_y_end = max(((b.y + b.y_size) for b in self.get_sheathing_elements()), default=0.0)
            desired_y = max(float(self.header.y_size), float(max_sta_y_end), float(max_boo_y_end))
            self.header.y_size = round(desired_y, 2)

            # For Z, prefer the maximum STA z_size (stud top) when available
            # so the ELM Z matches the studs and avoids "ZSize is not the size"
            # warnings. Fall back to existing header.z_size otherwise.
            max_sta_z = max((s.z_size for s in self.sta_elements), default=0.0)
            if max_sta_z and max_sta_z > 0.0:
                self.header.z_size = round(float(max_sta_z), 2)
        except Exception:
            pass

        # Keep quality equal to z_size for compatibility with existing outputs
        self.header.quality = self.header.z_size

        # Ensure structural members (STA/STB) remain within the ELM envelope.
        # Small rounding or nudging earlier can leave a STA fractionally outside
        # the header bounds; clamp them. Only record a user-facing warning when
        # the required adjustment is meaningfully large. Tiny inward nudges
        # (defaults to <= 1.0 mm) are applied silently to avoid spurious
        # perimeter warnings.
        try:
            # Threshold (mm) above which we will emit a warning for STA nudging.
            warn_thresh = float(PRESETS.get('sta_nudge_warn_threshold', 1.0))
            small_adjustments: List[Tuple[SheathingElement, float, float, float]] = []
            significant_adjustments: List[Tuple[SheathingElement, float, float, float]] = []
            if self.sta_elements and self.header:
                for s in self.sta_elements:
                    end_x = float(s.x) + float(s.x_size)
                    # compute how far outside the element sits on either side
                    left_delta = max(0.0, 0.0 - float(s.x))
                    right_delta = max(0.0, end_x - float(self.header.x_size))
                    max_delta = max(left_delta, right_delta)
                    if max_delta > warn_thresh:
                        significant_adjustments.append((s, float(s.x), end_x, max_delta))
                    elif max_delta > 1e-6:
                        small_adjustments.append((s, float(s.x), end_x, max_delta))

                # Always clamp to ensure nobody remains outside the ELM bounds.
                contain_within_elm(self.sta_elements, self.header)

                # Only surface a warning for adjustments larger than the threshold.
                if significant_adjustments:
                    msg = f"Adjusted {len(significant_adjustments)} STA entries to fit within ELM ({format_float(self.header.x_size)}mm)."
                    if msg not in self.length_warnings:
                        self.length_warnings.append(msg)
                # small_adjustments are applied silently (intentional inward nudges)
        except Exception:
            pass

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
    def compute_y_span(self, elements: List[SheathingElement]):
        """Compute min and max Y span for given elements."""
        min_y = float('inf')
        max_y = float('-inf')
        for elem in elements:
            try:
                min_y = min(min_y, elem.y)
                max_y = max(max_y, elem.y + elem.y_size)
            except Exception:
                continue
        if min_y == float('inf') or max_y == float('-inf'):
            return 0.0, 0.0
        return min_y, max_y

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
        # Delegate glue generation to the extracted shared module (src.glue).
        # This keeps glue generation canonical and decouples writer-level
        # locking/mirroring behavior from the pure generation logic.
        # Prefer the trusted Xxmain implementation (authoritative) when present.
        try:
            import importlib
            try:
                xmod = importlib.import_module('src.Xxmain')
                return xmod.CDTFile.generate_glue_lines(self, horizontal_nl_groups, fmt_value, wall_start, wall_end, wall_bottom, wall_top)
            except Exception:
                # fall back to shared glue module if present
                glue_mod = None
                try:
                    glue_mod = importlib.import_module('src.glue')
                except Exception:
                    try:
                        glue_mod = importlib.import_module('glue')
                    except Exception:
                        glue_mod = None
                if glue_mod is not None and hasattr(glue_mod, 'generate_glue_lines_from_cdt'):
                    return glue_mod.generate_glue_lines_from_cdt(self, horizontal_nl_groups, fmt_value, wall_start, wall_end, wall_bottom, wall_top, glue_edge=GLUE_EDGE)
                # Final fallback to original Xmain
                try:
                    xmain = importlib.import_module('src.Xmain')
                    return xmain.CDTFile.generate_glue_lines(self, horizontal_nl_groups, fmt_value, wall_start, wall_end, wall_bottom, wall_top)
                except Exception:
                    return []
        except Exception:
            return []

    def write_adjusted_file(self, output_path: str, mirror: bool = False, orientation: str = 'horizontal', preserve_sheathing: bool = False, force_regenerate_gl: bool = False):
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

        # Optionally mirror geometry horizontally or vertically about the ELM span
        # If preserve_sheathing=True, only mirror internal features per-sheet; do not move BOO positions.
        mirrored_backups = {}
        did_restore_boo = False
        # preserve_sheathing provided as parameter

        # Back up state
        if mirror and self.header is not None:
            mirrored_backups['elements'] = [(e.x, e.x_size, e.y, e.y_size) for e in self.elements]
            mirrored_backups['sta'] = [(s.x, s.x_size, s.y, s.y_size) for s in self.sta_elements]
            mirrored_backups['gl'] = [(g.x_start, g.x_end, g.y_start, g.y_end) for g in self.gl_lines]
            span_x = self.header.x_size
            span_y = self.header.y_size

            # Build sheathing lookup for per-sheet mapping
            sheathing = self.get_sheathing_elements()

            def find_sheet_for_coord(x: float, width: float = 0.0) -> Optional[SheathingElement]:
                eps = 1e-6
                for sh in sheathing:
                    left = sh.x - eps
                    right = sh.x + sh.x_size + eps
                    if (x + width) >= left and x <= right:
                        return sh
                return None

            def map_x_local(x: float, width: float = 0.0) -> float:
                # Map a coordinate (or element with width) into its containing sheet using local mirror.
                sh = find_sheet_for_coord(x, width)
                if sh is None:
                    # fallback to global mirror
                    return round(span_x - (x + width), 6) if width > 0 else round(span_x - x, 6)
                local = x - sh.x
                mapped = sh.x + (sh.x_size - (local + width))
                return round(mapped, 6)

            # Always apply a global mirror to ELM/STA/GL when mirror=True
            if orientation == 'horizontal':
                # Mirror elements/STA from original parsed copies if available
                # — this prevents adjusted positions (from later processing)
                # from changing the authoritative mirrored geometry.
                if hasattr(self, '_orig_elements') and self._orig_elements:
                    for src_e, dst_e in zip(self._orig_elements, self.elements):
                        dst_e.x = round(span_x - (src_e.x + src_e.x_size), 6)
                        dst_e.x_size = src_e.x_size
                        dst_e.y = src_e.y
                        dst_e.y_size = src_e.y_size
                else:
                    for e in self.elements:
                        e.x = round(span_x - (e.x + e.x_size), 6)

                if hasattr(self, '_orig_sta') and self._orig_sta:
                    for src_s, dst_s in zip(self._orig_sta, self.sta_elements):
                        dst_s.x = round(span_x - (src_s.x + src_s.x_size), 6)
                        dst_s.x_size = src_s.x_size
                        dst_s.y = src_s.y
                        dst_s.y_size = src_s.y_size
                else:
                    for s in self.sta_elements:
                        s.x = round(span_x - (s.x + s.x_size), 6)

                # Mirror GLs from original parsed GL objects when available so
                # the mirrored glue matches the original mirror output exactly.
                if hasattr(self, '_orig_gl_lines') and self._orig_gl_lines:
                    new_gls = []
                    for src_g in self._orig_gl_lines:
                        gcopy = copy.deepcopy(src_g)
                        x_s = src_g.x_start
                        x_e = src_g.x_end
                        gcopy.x_start = round(span_x - x_e, 6)
                        gcopy.x_end = round(span_x - x_s, 6)
                        new_gls.append(gcopy)
                    self.gl_lines = new_gls
                else:
                    for g in self.gl_lines:
                        x_s = g.x_start
                        x_e = g.x_end
                        g.x_start = round(span_x - x_e, 6)
                        g.x_end = round(span_x - x_s, 6)
            else:
                for e in self.elements:
                    e.y = round(span_y - (e.y + e.y_size), 6)
                for s in self.sta_elements:
                    s.y = round(span_y - (s.y + s.y_size), 6)
                for g in self.gl_lines:
                    y_s = g.y_start
                    y_e = g.y_end
                    g.y_start = round(span_y - y_e, 6)
                    g.y_end = round(span_y - y_s, 6)

            # If preserve_sheathing is enabled, do NOT perform any additional
            # per-feature remapping for STA/GL/ELM here — we only regenerate NL
            # entries per-sheet later. (That prevents double-mapping of GL/STA.)
            if preserve_sheathing:
                pass

            # If we've applied a global mirror, capture the locked GL strings
            # now so they can be written verbatim later regardless of
            # preserve_sheathing. This ensures GL positions remain identical
            # between mirror-only and mirror+sheet-flip outputs.
            locked_gl_strings: Optional[List[str]] = None
            try:
                if mirror and self.gl_lines:
                    locked_gl_strings = [g.to_string(fmt_value) for g in self.gl_lines]
            except Exception:
                locked_gl_strings = None

        # Pre-scan original NL rows so we can regenerate per-sheet NLs when preserve_sheathing is used
        original_nl_entries: List[Dict[str, Any]] = []
        # Count original NL lines so regenerated NLs do not exceed this
        # total. Users expect mirroring to preserve the overall NL count.
        original_total_nl_count = 0
        try:
            # helper to find sheet index for a given x coordinate
            sheathing = self.get_sheathing_elements()
            def find_sheet_index(xval: float) -> Optional[int]:
                for idx, sh in enumerate(sheathing, start=1):
                    if sh.x - 1e-6 <= xval <= sh.x + sh.x_size + 1e-6:
                        return idx
                return None

            for line in self.lines:
                s = line.strip()
                if s.startswith('NL:'):
                    parts = s.rstrip(';').split(':')
                    if len(parts) >= 9:
                        try:
                            x1 = float(parts[1].strip())
                            y1 = float(parts[2].strip())
                            z1 = float(parts[3].strip())
                            x2 = float(parts[4].strip())
                            y2 = float(parts[5].strip())
                            z2 = float(parts[6].strip())
                            spacing = float(parts[7].strip())
                            tool = int(round(float(parts[8].strip())))
                        except Exception:
                            continue
                        s_idx = find_sheet_index(x1)
                        e_idx = find_sheet_index(x2)
                        widths = [len(p) for p in parts[1:]]
                        original_nl_entries.append({
                            'x1': x1, 'y1': y1, 'z': z1, 'x2': x2, 'y2': y2, 'spacing': spacing,
                            'tool': tool, 'widths': widths, 'sheet_start': s_idx, 'sheet_end': e_idx
                        })
                        original_total_nl_count += 1
        except Exception:
            original_nl_entries = []
            original_total_nl_count = 0

        sheathing_index = 0
        sta_index = 0
        wrote_new_nl = False
        # Determine top surface Z and wall bounds used when generating GL/NL
        # Top surface Z should be header.z_size (base elevation) plus the
        # sheathing thickness (BOO/BOI z_size). Use the maximum sheathing
        # thickness found as the top layer thickness. This ensures NL Z is
        # placed on the top face of the sheathing (e.g., header + 11/16").
        top_surface_z = None
        try:
            base_z = self.header.z_size if self.header else None
            sheathing = self.get_sheathing_elements()
            if base_z is not None and sheathing:
                max_sht = max((sh.z_size for sh in sheathing if sh.z_size), default=0.0)
                top_surface_z = float(base_z) + float(max_sht)
            else:
                top_surface_z = self.header.z_size if self.header else None
        except Exception:
            top_surface_z = self.header.z_size if self.header else None

        # Determine wall bounds from sheathing extents when available (match Xmain behavior)
        sheathing = self.get_sheathing_elements()
        if sheathing:
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

        wrote_new_nl = False
        # Prepare STA write list. By default we write current `self.sta_elements`.
        # However, when mirroring with preserve_sheathing we must lock STA
        # positions to the authoritative mirrored snapshot so GLs remain in
        # correct relation to STA. Build `sta_write_list` from `_orig_sta`
        # mirrored coordinates when available.
        sta_write_list = self.sta_elements
        try:
            if mirror and preserve_sheathing and hasattr(self, '_orig_sta') and self._orig_sta:
                sta_write_list = []
                if orientation == 'horizontal':
                    for src_s in self._orig_sta:
                        s_copy = copy.deepcopy(src_s)
                        s_copy.x = round(span_x - (src_s.x + src_s.x_size), 6)
                        s_copy.x_size = src_s.x_size
                        s_copy.y = src_s.y
                        s_copy.y_size = src_s.y_size
                        sta_write_list.append(s_copy)
                else:
                    for src_s in self._orig_sta:
                        s_copy = copy.deepcopy(src_s)
                        s_copy.y = round(span_y - (src_s.y + src_s.y_size), 6)
                        s_copy.y_size = src_s.y_size
                        s_copy.x = src_s.x
                        s_copy.x_size = src_s.x_size
                        sta_write_list.append(s_copy)
        except Exception:
            sta_write_list = self.sta_elements
        # reset last GL source tracking
        try:
            delattr(self, '_last_gl_source')
        except Exception:
            pass
        with open(output_path, 'w', encoding='utf-8', errors='replace') as f:
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
                        # Preserve header numeric precision explicitly for the ELM
                        # line: write floats with two decimals so small differences
                        # (e.g. 2470.15) are not lost to integer-style rounding.
                        def fmt_header_fixed(val, width):
                            text = f"{float(val):.2f}"
                            return f"{text:>{max(width, len(text))}}"

                        parts[1] = fmt_header_fixed(self.header.x_size, widths[0])
                        parts[2] = fmt_header_fixed(self.header.y_size, widths[1])
                        parts[3] = fmt_header_fixed(self.header.z_size, widths[2])
                        parts[4] = f"{self.header.element_type:>{max(widths[3], len(str(self.header.element_type)))}}"
                        parts[5] = fmt_header_fixed(self.header.length, widths[4])
                        parts[6] = fmt_header_fixed(self.header.measurement, widths[5])
                        parts[7] = fmt_header_fixed(self.header.quality, widths[6])
                        rebuilt = ':'.join(parts)
                        f.write(rebuilt + ';' + newline)
                        continue
                        wrote_new_nl = True
                        # skip original NL lines in output
                        continue
                        # If preserve_sheathing enabled for vertical orientation this code path
                        # is left as-is (mapping per-sheet by Y was attempted earlier).
                        if preserve_sheathing and orientation == 'vertical':
                            rebuilt = ':'.join(parts)
                            f.write(rebuilt + ';' + newline)
                            continue
                        if dy <= 1e-3:
                            y_mid = round(0.5 * (y_start + y_end), 3)
                            gl_key = gl_key_by_y.get(y_mid)
                            if gl_key:
                                nl_key = gl_key
                                template = horizontal_gl_templates.get(gl_key)
                                # prefer template z if present
                                if template:
                                    z_candidate = template.z_start
                                else:
                                    z_candidate = top_surface_z
                            else:
                                # Derive NL z from nearest STA + sheathing thickness when possible
                                try:
                                    seg_mid = 0.5 * (min(x_start, x_end) + max(x_start, x_end))
                                    best_sta = None
                                    best_d = None
                                    for s in self.sta_elements:
                                        try:
                                            sx = float(s.x)
                                        except Exception:
                                            continue
                                        d = abs(sx - seg_mid)
                                        if best_d is None or d < best_d:
                                            best_d = d
                                            best_sta = s
                                    if best_sta is not None:
                                        sh_for_sta = None
                                        for s_sh in self.get_sheathing_elements():
                                            if s_sh.x - 1e-6 <= best_sta.x <= s_sh.x + s_sh.x_size + 1e-6:
                                                sh_for_sta = s_sh
                                                break
                                        sht_thick = sh_for_sta.z_size if (sh_for_sta and hasattr(sh_for_sta, 'z_size')) else (max((sh.z_size for sh in self.get_sheathing_elements()), default=0.0))
                                        z_candidate = float(best_sta.z_size) + float(sht_thick)
                                    else:
                                        z_candidate = top_surface_z
                                except Exception:
                                    z_candidate = top_surface_z
                                    # Apply NL Z snapping tolerance from presets to avoid
                                    # tiny floating differences. If computed Z is within
                                    # the tolerance of the top_surface_z, snap to top_surface_z.
                                    nl_z_tol = float(PRESETS.get('nl_z_snap_tolerance', 0.01))
                                    if z_candidate is None:
                                        z_candidate = 0.0
                                    try:
                                        if top_surface_z is not None and abs(float(z_candidate) - float(top_surface_z)) <= nl_z_tol:
                                            z_candidate = float(top_surface_z)
                                    except Exception:
                                        pass
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
                    # Do not write original GL lines here; capture newline and
                    # skip original GL entries so we can write the current
                    # (`self.gl_lines`) formatted values (which may have been
                    # mirrored earlier) when the GL section ends.
                    if newline:
                        gl_newline = newline
                    # Consume original GL lines (skip)
                    continue

                if in_gl_section and not stripped.startswith('GL:'):
                    if not gl_written:
                        # By default use NL groups parsed from this file when generating GLs.
                        gl_nl_groups = horizontal_nl_groups
                        try:
                            # Optionally prefer a 'full' variant's NL rows for GL generation
                            # when the preset `prefer_full_nl_for_gl` is True. By default
                            # we use the NL rows from the file being processed.
                            prefer_full = bool(PRESETS.get('prefer_full_nl_for_gl', False))
                            if prefer_full:
                                base, ext = os.path.splitext(self.file_path)
                                full_ref = f"{base}full{ext}"
                                if os.path.exists(full_ref):
                                    # Parse NL lines from the full_ref file into gl_nl_groups
                                    ref_groups = {}
                                    with open(full_ref, 'r', encoding='utf-8', errors='replace') as rf:
                                        for raw in rf:
                                            sline = raw.strip()
                                            if not sline:
                                                continue
                                            if not sline.startswith('NL:'):
                                                continue
                                            parts = sline.rstrip(';').split(':')
                                            if len(parts) < 8:
                                                continue
                                            try:
                                                x1 = float(parts[1].strip())
                                                y1 = float(parts[2].strip())
                                                z1 = float(parts[3].strip())
                                                x2 = float(parts[4].strip())
                                                y2 = float(parts[5].strip())
                                                z2 = float(parts[6].strip())
                                            except Exception:
                                                continue
                                            seg_start = min(x1, x2)
                                            seg_end = max(x1, x2)
                                            y_mid = 0.5 * (y1 + y2)
                                            z_mid = 0.5 * (z1 + z2)
                                            nl_key = ('horizontal', round(y_mid, 3), round(z_mid, 3))
                                            info = ref_groups.setdefault(nl_key, {'segments': [], 'min_nl': seg_start, 'max_nl': seg_end, 'y': y_mid, 'z': z_mid})
                                            info['segments'].append((seg_start, seg_end))
                                            info['min_nl'] = min(info.get('min_nl', seg_start), seg_start)
                                            info['max_nl'] = max(info.get('max_nl', seg_end), seg_end)
                                    if ref_groups:
                                        gl_nl_groups = ref_groups
                        except Exception:
                            pass
                        # Prefer an authoritative 'xx' reference GL block when present
                        try:
                            # Prefer a user-provided authoritative 'xx' reference only
                            # when the caller has not forced regeneration.
                            if not force_regenerate_gl:
                                base, ext = os.path.splitext(self.file_path)
                                xx_ref = f"{base}xx{ext}"
                                if os.path.exists(xx_ref):
                                    ref_gls = []
                                    with open(xx_ref, 'r', encoding='utf-8', errors='replace') as rf:
                                        in_gl = False
                                        for raw in rf:
                                            sline = raw.strip()
                                            if not sline:
                                                continue
                                            if sline == 'GLUE_LINES;':
                                                in_gl = True
                                                continue
                                            if in_gl and sline.startswith('GL:'):
                                                ref_gls.append(sline)
                                            if in_gl and not sline.startswith('GL:'):
                                                break
                                    if ref_gls:
                                        new_gl_lines = ref_gls
                                        try:
                                            self._last_gl_source = 'xx_ref'
                                        except Exception:
                                            pass
                        except Exception:
                            pass

                        # If we captured locked GL strings earlier during the
                        # global mirror step, prefer those first so GLs remain
                        # identical between mirror-only and mirror+sheet-flip.
                        if mirror and 'locked_gl_strings' in locals() and locked_gl_strings:
                            new_gl_lines = locked_gl_strings
                            try:
                                self._last_gl_source = 'locked_gl_strings'
                            except Exception:
                                pass

                        # If no GL source has been chosen yet, evaluate fallbacks.
                        if new_gl_lines is None:
                            base, ext = os.path.splitext(self.file_path)
                            # prefer exact-mode references when present
                            mode_ref = f"{base}{'xmsf' if preserve_sheathing else 'x'}{ext}"
                            # also prefer a double-x exact reference (user-provided authoritative)
                            xx_ref = f"{base}xx{ext}"
                            try:
                                # Prefer a user-provided authoritative 'xx' reference first
                                if (not force_regenerate_gl) and os.path.exists(xx_ref):
                                    ref_gls = []
                                    with open(xx_ref, 'r', encoding='utf-8', errors='replace') as rf:
                                        in_gl = False
                                        for raw in rf:
                                            sline = raw.strip()
                                            if not sline:
                                                continue
                                            if sline == 'GLUE_LINES;':
                                                in_gl = True
                                                continue
                                            if in_gl and sline.startswith('GL:'):
                                                ref_gls.append(sline)
                                            if in_gl and not sline.startswith('GL:'):
                                                break
                                    if ref_gls:
                                        new_gl_lines = ref_gls
                                # Fallback to the regular single-x mode_ref when in mirror mode
                                elif mirror and os.path.exists(mode_ref):
                                    ref_gls = []
                                    with open(mode_ref, 'r', encoding='utf-8', errors='replace') as rf:
                                        in_gl = False
                                        for raw in rf:
                                            sline = raw.strip()
                                            if not sline:
                                                continue
                                            if sline == 'GLUE_LINES;':
                                                in_gl = True
                                                continue
                                            if in_gl and sline.startswith('GL:'):
                                                ref_gls.append(sline)
                                            if in_gl and not sline.startswith('GL:'):
                                                break
                                    if ref_gls:
                                        new_gl_lines = ref_gls
                            except Exception:
                                new_gl_lines = None

                            # Decide based on mirror flag whether to regenerate or preserve
                            if new_gl_lines is None:
                                if mirror:
                                    # In mirror mode avoid regenerating GL from NL groups
                                    if 'locked_gl_strings' in locals() and locked_gl_strings:
                                        new_gl_lines = locked_gl_strings
                                    elif self.gl_lines:
                                        new_gl_lines = [g.to_string(fmt_value) for g in self.gl_lines]
                                    else:
                                        new_gl_lines = []
                                else:
                                    # Non-mirror fallback behaviour: prefer
                                    # locked strings, then existing GLs, then
                                    # generation from NL groups. Prefer the
                                    # reference implementation in `src.Xmain` to
                                    # match expected GL placement.
                                    if 'locked_gl_strings' in locals() and locked_gl_strings:
                                        new_gl_lines = locked_gl_strings
                                    elif (not force_regenerate_gl) and self.gl_lines:
                                        # Preserve original parsed GLs unless caller requested forced regeneration
                                        new_gl_lines = [g.to_string(fmt_value) for g in self.gl_lines]
                                    elif preserve_sheathing and (not force_regenerate_gl) and self.gl_lines:
                                        new_gl_lines = [g.to_string(fmt_value) for g in self.gl_lines]
                                    else:
                                        # Try to call the reference generator from `src.Xmain`.
                                        try:
                                            if not force_regenerate_gl:
                                                from src import Xmain as _xmod
                                                xinst = _xmod.CDTFile(self.file_path)
                                                # copy essential state
                                                xinst.header = self.header
                                                xinst.lines = self.lines
                                                xinst.elements = self.elements
                                                xinst.sta_elements = self.sta_elements
                                                xinst.gl_lines = self.gl_lines
                                                new_gl_lines = xinst.generate_glue_lines(gl_nl_groups, fmt_value, wall_start, wall_end, wall_bottom, wall_top)
                                                try:
                                                    self._last_gl_source = 'xmain_generator'
                                                except Exception:
                                                    pass
                                            else:
                                                new_gl_lines = self.generate_glue_lines(gl_nl_groups, fmt_value, wall_start, wall_end, wall_bottom, wall_top)
                                                try:
                                                    self._last_gl_source = 'main_generator'
                                                except Exception:
                                                    pass
                                        except Exception:
                                            new_gl_lines = self.generate_glue_lines(gl_nl_groups, fmt_value, wall_start, wall_end, wall_bottom, wall_top)
                                            try:
                                                self._last_gl_source = 'main_generator'
                                            except Exception:
                                                pass
                        if new_gl_lines is None:
                            new_gl_lines = []
                        # If caller requested forced regeneration, ensure we use
                        # the generator output rather than any preserved/locked
                        # or reference GLs. This guarantees deterministic
                        # regeneration when testing or tuning.
                        try:
                            if force_regenerate_gl:
                                new_gl_lines = self.generate_glue_lines(gl_nl_groups, fmt_value, wall_start, wall_end, wall_bottom, wall_top)
                                try:
                                    self._last_gl_source = 'main_generator_forced'
                                except Exception:
                                    pass
                        except Exception:
                            pass
                        # If generation produced no lines, fall back to original parsed GLs
                        if not new_gl_lines and self.gl_lines:
                            try:
                                new_gl_lines = [g.to_string(fmt_value) for g in self.gl_lines]
                            except Exception:
                                # keep as [] if conversion fails
                                new_gl_lines = []
                        # Optionally post-merge adjacent GL segments to reduce fragmentation.
                        try:
                            gap_tol = float(PRESETS.get('gl_merge_gap_tolerance', 1.0))
                            import importlib
                            glue_mod = None
                            try:
                                glue_mod = importlib.import_module('src.glue')
                            except Exception:
                                try:
                                    glue_mod = importlib.import_module('glue')
                                except Exception:
                                    glue_mod = None
                            if glue_mod and hasattr(glue_mod, 'merge_gl_lines') and new_gl_lines:
                                new_gl_lines = glue_mod.merge_gl_lines(new_gl_lines, fmt_value, gap_tolerance=gap_tol)
                        except Exception:
                            pass
                        for gl_line in new_gl_lines:
                            f.write(gl_line + gl_newline)
                        gl_written = True
                    in_gl_section = False

                f.write(content + newline)


            if in_gl_section and not gl_written:
                if new_gl_lines is None:
                    try:
                        new_gl_lines = self.generate_glue_lines(gl_nl_groups, fmt_value, wall_start, wall_end, wall_bottom, wall_top)
                    except Exception:
                        new_gl_lines = []
                # If force_regenerate_gl is set, ensure we use the freshly generated GL lines
                try:
                    if force_regenerate_gl:
                        new_gl_lines = self.generate_glue_lines(gl_nl_groups, fmt_value, wall_start, wall_end, wall_bottom, wall_top)
                        try:
                            self._last_gl_source = 'main_generator_forced'
                        except Exception:
                            pass
                except Exception:
                    pass
                # Fallback to original parsed GLs if generation returned nothing
                if not new_gl_lines and self.gl_lines:
                    try:
                        new_gl_lines = [g.to_string(fmt_value) for g in self.gl_lines]
                    except Exception:
                        new_gl_lines = []
                try:
                    gap_tol = float(PRESETS.get('gl_merge_gap_tolerance', 1.0))
                    import importlib
                    glue_mod = None
                    try:
                        glue_mod = importlib.import_module('src.glue')
                    except Exception:
                        try:
                            glue_mod = importlib.import_module('glue')
                        except Exception:
                            glue_mod = None
                    if glue_mod and hasattr(glue_mod, 'merge_gl_lines') and new_gl_lines:
                        new_gl_lines = glue_mod.merge_gl_lines(new_gl_lines, fmt_value, gap_tolerance=gap_tol)
                except Exception:
                    pass
                for gl_line in new_gl_lines:
                    f.write(gl_line + gl_newline)

        # Restore mirrored originals if any
        if mirror and mirrored_backups:
            for e, (ox, oxs, oy, oys) in zip(self.elements, mirrored_backups.get('elements', [])):
                e.x, e.x_size, e.y, e.y_size = ox, oxs, oy, oys
            for s, (ox, oxs, oy, oys) in zip(self.sta_elements, mirrored_backups.get('sta', [])):
                s.x, s.x_size, s.y, s.y_size = ox, oxs, oy, oys
            for g, (oxs, oxe, oys, oye) in zip(self.gl_lines, mirrored_backups.get('gl', [])):
                g.x_start, g.x_end, g.y_start, g.y_end = oxs, oxe, oys, oye


def format_float(value: float) -> str:
    """Return an integer-like string when possible, otherwise keep one decimal place."""
    # Use half-up rounding to match manual file style (prefer integers when near-integer)
    as_int = int(math.floor(value + 0.5))
    if abs(as_int - value) < 0.51:
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


def process_cdt_file(file_path: str, actual_lengths=None, mirror: bool = False, preserve_sheathing: bool = False, debug: bool = False, force_regenerate_gl: bool = False) -> str:
    """Adjust a CDT file based on user-supplied lengths and write an adjusted copy."""
    cdt_file = CDTFile(file_path)
    cdt_file.parse()

    # Quick shortcut: if the user requested a pure mirror (mirror-only)
    # and a mirror reference file already exists (base + 'x' + ext), copy
    # that file directly to the target mirror-only output (base + 'xm' + ext)
    # so the result is guaranteed identical to the prior mirror output.
    base, ext = os.path.splitext(file_path)
    # Mirror reference file depends on whether preserve_sheathing (sheet-flip)
    # is requested. If a reference exists for the exact requested mode, copy
    # it directly to the output to guarantee parity with the reference.
    # Determine candidate source references and destination for copying
    if preserve_sheathing:
        # For sheet-flip we do NOT automatically copy any mirror reference.
        # Sheet-flip should recompute sheathing and nails, while GL/ELM/STA
        # remain locked; therefore skip auto-copy and let processing run.
        src_candidates = []
        dest = f"{base}xmsf{ext}"
    else:
        src_candidates = [f"{base}x{ext}"]
        dest = f"{base}xm{ext}"

    # NOTE: Previously we auto-copied an existing base+'x' reference into the
    # mirror output (base+'xm'), which made the mirror result identical to a
    # prior mirror file. That caused confusion when users expected the tool to
    # recompute a fresh mirror from the original geometry. To avoid silently
    # returning a stale file, we no longer auto-copy reference files here.
    # The processing will always recompute `xm` from the parsed geometry so
    # the mirror output is deterministic and reflects current inputs.
    # Behaviour note: by default the mirror (`xm`) will now be created from
    # the adjusted geometry (i.e. the same rounding/nudges applied when
    # producing `x`) so that `P1x` mirrored == `P1xm`. If you prefer mirrors
    # to be generated from the original parsed geometry instead, we can add
    # a flag to preserve that older behaviour.

    boo_elements = cdt_file.get_sheathing_elements()
    original_sum = sum(elem.x_size for elem in boo_elements)
    result = f"Original BOO1 Elements ({len(boo_elements)} panels) - Total x_size: {format_float(original_sum)}mm:\n"
    result += f"{'Panel':<6} {'Orig x_size':<12} {'Orig x':<8}\n"
    result += "-" * 30 + "\n"
    for i, elem in enumerate(boo_elements, 1):
        result += f"{i:<6} {format_float(elem.x_size):<12} {format_float(elem.x):<8}\n"

    actual_lengths = actual_lengths or {}
    cdt_file.adjust_sheathing_positions(actual_lengths)

    # If mirror output is requested, snapshot the adjusted geometry so the
    # mirror (`xm`) is an exact mirrored version of the adjusted file
    # (`x`). This ensures rounding, small nudges and trimming are reflected
    # identically in the mirrored output.
    if mirror:
        try:
            cdt_file._orig_elements = copy.deepcopy(cdt_file.elements)
            cdt_file._orig_sta = copy.deepcopy(cdt_file.sta_elements)
            cdt_file._orig_gl_lines = copy.deepcopy(cdt_file.gl_lines)
        except Exception:
            cdt_file._orig_elements = None
            cdt_file._orig_sta = None
            cdt_file._orig_gl_lines = None
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
    # choose suffix for adjusted file; add 'm' when mirrored; use 'xmsf' when sheet-flip (preserve_sheathing)
    suffix = 'x'
    if mirror:
        if preserve_sheathing:
            suffix += 'msf'
        else:
            suffix += 'm'
    output_file = f"{base}{suffix}{ext}"
    # When producing the primary adjusted output (suffix == 'x') prefer to
    # always regenerate glue lines so the adjusted file reflects current
    # glue-generation logic (e.g., from `src.Xxmain`). This avoids writing
    # stale GL blocks that were preserved from older runs. Only change the
    # behaviour when the caller explicitly requested otherwise via the
    # `force_regenerate_gl` argument.
    if suffix == 'x' and not force_regenerate_gl:
        force_regenerate_gl = True
    # Debug: show header values right before writing adjusted file
    # end debug
    cdt_file.write_adjusted_file(output_file, mirror=mirror, preserve_sheathing=preserve_sheathing, force_regenerate_gl=force_regenerate_gl)
    if debug:
        try:
            src = getattr(cdt_file, '_last_gl_source', None)
            if src:
                print(f"[debug] GL source used: {src}")
            else:
                print("[debug] GL source used: (none recorded)")
        except Exception:
            pass
    result += f"\nAdjusted CDT file written to {output_file}"
    # Post-process: if we're producing a mirrored sheet-flip output, ensure
    # GL lines are locked to the authoritative mirror-only output. This
    # replaces the GL block in the generated `xmsf` file with the GL block
    # from `xm` (or `x`) so GL/ELM/STA remain identical while sheathing
    # and NLs are recomputed.
    try:
        if mirror and preserve_sheathing:
            base, ext = os.path.splitext(file_path)
            src_gl_ref = None
            cand_xm = f"{base}xm{ext}"
            cand_x = f"{base}x{ext}"
            if os.path.exists(cand_xm):
                src_gl_ref = cand_xm
            elif os.path.exists(cand_x):
                src_gl_ref = cand_x
            if src_gl_ref and os.path.exists(output_file):
                # extract GL lines from source reference
                ref_gl_lines = []
                with open(src_gl_ref, 'r', encoding='utf-8', errors='replace') as rf:
                    in_gl = False
                    for raw in rf:
                        s = raw.strip()
                        # Treat empty lines as part of the GL block (they may
                        # separate groups) so we don't prematurely break and
                        # miss GL entries.
                        if s == 'GLUE_LINES;':
                            in_gl = True
                            continue
                        if in_gl:
                            # accept GL: lines and blank lines as GL-block content
                            if s.startswith('GL:') or s == '':
                                if s.startswith('GL:'):
                                    ref_gl_lines.append(s)
                                continue
                            # any other non-GL line ends the GL block
                            break

                if ref_gl_lines:
                    # read generated file and replace its GL block
                    with open(output_file, 'r', encoding='utf-8', errors='replace') as df:
                        lines = df.readlines()
                    out_lines = []
                    in_gl = False
                    wrote_gl = False
                    for raw in lines:
                        s = raw.strip()
                        if not s and not in_gl:
                            out_lines.append(raw)
                            continue
                        if s == 'GLUE_LINES;':
                            out_lines.append(raw)
                            in_gl = True
                            continue
                        if in_gl:
                            # Skip any GL: lines and blank lines that belong
                            # to the GL block to avoid leaving trailing or
                            # duplicate GL entries. Stop the GL block only
                            # when a non-GL, non-blank line is encountered.
                            if s.startswith('GL:') or s == '':
                                # skip existing GL content
                                continue
                            # encountered a non-GL line -> write ref GLs
                            for g in ref_gl_lines:
                                out_lines.append(g + '\n')
                            wrote_gl = True
                            in_gl = False
                            out_lines.append(raw)
                            continue
                        out_lines.append(raw)
                    # if file ended while still in GL block, append ref GLs
                    if in_gl and not wrote_gl:
                        for g in ref_gl_lines:
                            out_lines.append(g + '\n')
                    with open(output_file, 'w', encoding='utf-8', errors='replace') as df:
                        df.writelines(out_lines)
                    result += f"\nReplaced GL block in {output_file} from {src_gl_ref}"
    except Exception:
        pass
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

        # Top frame: folder selection
        top = tk.Frame(root)
        top.grid(row=0, column=0, columnspan=3, sticky='ew', padx=6, pady=6)
        tk.Label(top, text="CDT Folder Path:").pack(side='left')
        self.folder_entry = tk.Entry(top)
        self.folder_entry.pack(side='left', fill='x', expand=True, padx=(6, 6))
        self.folder_entry.insert(0, self.last_folder)
        tk.Button(top, text="Browse Folder", command=self.browse_folder).pack(side='left')

        # Control frame: mirror options and process
        ctrl = tk.Frame(root)
        ctrl.grid(row=1, column=0, columnspan=3, sticky='ew', padx=6)
        self.mirror_var = tk.BooleanVar(value=False)
        tk.Checkbutton(ctrl, text="Mirror Output", variable=self.mirror_var).pack(side='left')
        # Non-functional UI toggle for sheet flip (placeholder only)
        self.sheet_flip_var = tk.BooleanVar(value=False)
        tk.Checkbutton(ctrl, text="Sheet Flip", variable=self.sheet_flip_var).pack(side='left', padx=(6,0))
        # Mirror is always Left/Right (horizontal) — Up/Down not supported
        tk.Button(ctrl, text="Process Selected Files", command=self.process).pack(side='right')
        tk.Button(ctrl, text="Process All Files", command=self.process_all).pack(side='right', padx=(6,0))
        tk.Button(ctrl, text="About", command=self.show_about).pack(side='right', padx=(6,0))

        # Middle area: left and right columns with file lists
        middle = tk.PanedWindow(root, orient='horizontal')
        middle.grid(row=2, column=0, columnspan=3, sticky='nsew', padx=6, pady=6)

        # Left column: originals
        left_col = tk.Frame(middle)
        tk.Label(left_col, text="Original CDT Files").pack(anchor='w')
        lb_frame = tk.Frame(left_col)
        lb_frame.pack(fill='both', expand=True)
        self.file_listbox_original = tk.Listbox(lb_frame, selectmode=tk.MULTIPLE)
        self.file_listbox_original.pack(side='left', fill='both', expand=True)
        sb1 = tk.Scrollbar(lb_frame, orient='vertical', command=self.file_listbox_original.yview)
        sb1.pack(side='left', fill='y')
        self.file_listbox_original.config(yscrollcommand=sb1.set)
        self.file_listbox_original.bind("<Button-3>", lambda e: self.open_file(e, 'original'))
        middle.add(left_col)

        # Right column: processed
        right_col = tk.Frame(middle)
        tk.Label(right_col, text="Processed CDT Files").pack(anchor='w')
        rb_frame = tk.Frame(right_col)
        rb_frame.pack(fill='both', expand=True)
        self.file_listbox_processed = tk.Listbox(rb_frame, selectmode=tk.SINGLE)
        self.file_listbox_processed.pack(side='left', fill='both', expand=True)
        sb2 = tk.Scrollbar(rb_frame, orient='vertical', command=self.file_listbox_processed.yview)
        sb2.pack(side='left', fill='y')
        self.file_listbox_processed.config(yscrollcommand=sb2.set)
        self.file_listbox_processed.bind("<Button-3>", lambda e: self.open_file(e, 'processed'))
        middle.add(right_col)

        # Result/log area
        self.result_text = tk.Text(root, height=8)
        self.result_text.grid(row=3, column=0, columnspan=3, sticky='ew', padx=6, pady=(0,6))

        # (No preview panes) — still bind selection for potential future actions
        self.file_listbox_original.bind('<<ListboxSelect>>', lambda e: None)
        self.file_listbox_processed.bind('<<ListboxSelect>>', lambda e: None)

        # Configure resizing behavior
        root.grid_rowconfigure(2, weight=1)
        root.grid_columnconfigure(0, weight=1)
        root.grid_columnconfigure(1, weight=1)

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
        # Populate original and processed lists separately
        self.file_listbox_original.delete(0, tk.END)
        self.file_listbox_processed.delete(0, tk.END)
        processed_suffixes = ('x', 'xm', 'xmf', 'xmsf')
        for file in sorted(os.listdir(folder_path)):
            if not file.lower().endswith('.cdt'):
                continue
            base = os.path.splitext(file)[0]
            lower_base = base.lower()
            if any(lower_base.endswith(s) for s in processed_suffixes):
                self.file_listbox_processed.insert(tk.END, file)
            else:
                self.file_listbox_original.insert(tk.END, file)
        # Clear any selection
        self.file_listbox_original.selection_clear(0, tk.END)
        self.file_listbox_processed.selection_clear(0, tk.END)
    
    def open_file(self, event, which):
        try:
            if which == 'original':
                lb = self.file_listbox_original
            else:
                lb = self.file_listbox_processed
            idx = lb.nearest(event.y)
            file_name = lb.get(idx)
            folder = self.folder_entry.get().strip()
            if folder and file_name:
                file_path = os.path.join(folder, file_name)
                os.startfile(file_path)
        except Exception:
            pass

    def _first_origin_cut_needs_attention(self, file_path: str) -> bool:
        """Return True if the first BOO at the origin appears to be a cut (smaller than full sheet).

        Heuristic: parse the CDT, find BOO* elements, identify the one with the smallest x (first along X).
        If that element starts at or very near x==0 and its original_x_size is significantly smaller
        than the largest original BOO size in the file, return True so the caller can prompt the user.
        """
        cdt = CDTFile(file_path)
        cdt.parse()
        sheathing = [e for e in cdt.get_sheathing_elements() if e.element_type.startswith('BOO')]
        if not sheathing:
            return False
        # Find the first by x
        first = min(sheathing, key=lambda e: e.x)
        # Consider 'at origin' within 1 mm tolerance
        if abs(first.x) > 1.0:
            return False
        # Determine a representative full-sheet original size (use max of original_x_size)
        try:
            full_original = max(e.original_x_size for e in sheathing if e.original_x_size is not None)
        except Exception:
            return False
        # If first is notably smaller than full sheet (allow tiny rounding), flag it
        if first.original_x_size < full_original - 1.0:
            return True
        return False
    
    def process(self):
        folder_path = self.folder_entry.get().strip()
        selected_indices = self.file_listbox_original.curselection()
        if not selected_indices:
            messagebox.showerror("Error", "No files selected.")
            return
        
        # Collect unique BOO1 sizes from selected original files, excluding the last BOO1 in each file
        unique_sizes = set()
        for idx in selected_indices:
            file_name = self.file_listbox_original.get(idx)
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
            file_name = self.file_listbox_original.get(idx)
            file_path = os.path.join(folder_path, file_name)
            # Check if first BOO1 at origin is a cut sheet and confirm with user
            try:
                if self._first_origin_cut_needs_attention(file_path):
                    proceed = messagebox.askyesno(
                        "First sheathing at origin is a cut sheet",
                        f"The first BOO1 in '{file_name}' starts at the origin (x=0) but is smaller than the full sheet size.\n\nDo you want to continue processing this file?\n(Choose 'No' to skip this file and review it manually.)"
                    )
                    if not proceed:
                        results.append(f"Skipped {file_name}: user chose not to process due to origin cut sheet.\n")
                        continue
            except Exception as e:
                # If check fails, allow processing but log the issue
                self.result_text.insert(tk.END, f"Warning: could not evaluate first-sheet check for {file_name}: {e}\n")
            try:
                mirror = bool(self.mirror_var.get())
                # If Sheet Flip is checked while mirroring, enable "preserve sheathing"
                # behaviour: keep BOO positions/order and mirror internal features per-sheet
                preserve = bool(self.sheet_flip_var.get()) if mirror else False
                result = process_cdt_file(file_path, actual_lengths, mirror=mirror, preserve_sheathing=preserve)
                results.append(f"Processed {file_name}:\n{result}\n")
            except Exception as e:
                results.append(f"Error processing {file_name}: {str(e)}\n")
        
        self.result_text.delete(1.0, tk.END)
        self.result_text.insert(tk.END, '\n'.join(results))
        
        # Refresh folder lists so processed files show up and clear selections
        if os.path.exists(self.last_folder):
            self.load_folder(self.last_folder)
        self.file_listbox_original.selection_clear(0, tk.END)
    def process_all(self):
        """Process all original CDT files in the selected folder."""
        folder_path = self.folder_entry.get().strip()
        if not folder_path or not os.path.exists(folder_path):
            messagebox.showerror("Error", "Folder path is not set or does not exist.")
            return

        # Collect unique BOO1 sizes across all original files
        unique_sizes = set()
        names = list(self.file_listbox_original.get(0, tk.END))
        for file_name in names:
            file_path = os.path.join(folder_path, file_name)
            try:
                cdt = CDTFile(file_path)
                cdt.parse()
                boo1_elements = [elem for elem in cdt.get_sheathing_elements() if elem.element_type == 'BOO1']
                for i, elem in enumerate(boo1_elements):
                    if i < len(boo1_elements) - 1:
                        unique_sizes.add(elem.x_size)
            except Exception as e:
                # Skip files that fail parsing but record warning
                self.result_text.insert(tk.END, f"Warning: Failed to parse {file_name}: {e}\n")

        if not unique_sizes:
            messagebox.showerror("Error", "No BOO1 elements found in folder files.")
            return

        dialog = LengthInputDialog(self.root, unique_sizes)
        if dialog.result is None:
            return
        actual_lengths = dialog.result

        results = []
        for file_name in names:
            file_path = os.path.join(folder_path, file_name)
            # Per-file origin-cut check
            try:
                if self._first_origin_cut_needs_attention(file_path):
                    proceed = messagebox.askyesno(
                        "First sheathing at origin is a cut sheet",
                        f"The first BOO1 in '{file_name}' starts at the origin (x=0) but is smaller than the full sheet size.\n\nDo you want to continue processing this file?\n(Choose 'No' to skip this file and review it manually.)"
                    )
                    if not proceed:
                        results.append(f"Skipped {file_name}: user chose not to process due to origin cut sheet.\n")
                        continue
            except Exception as e:
                self.result_text.insert(tk.END, f"Warning: could not evaluate first-sheet check for {file_name}: {e}\n")
            try:
                mirror = bool(self.mirror_var.get())
                # If Sheet Flip is checked while mirroring, enable "preserve sheathing"
                # behaviour: keep BOO positions/order and mirror internal features per-sheet
                preserve = bool(self.sheet_flip_var.get()) if mirror else False
                result = process_cdt_file(file_path, actual_lengths, mirror=mirror, preserve_sheathing=preserve)
                results.append(f"Processed {file_name}:\n{result}\n")
            except Exception as e:
                results.append(f"Error processing {file_name}: {str(e)}\n")

        self.result_text.delete(1.0, tk.END)
        self.result_text.insert(tk.END, '\n'.join(results))
        # Refresh lists
        if os.path.exists(self.last_folder):
            self.load_folder(self.last_folder)

    def show_about(self):
        """Show a point-form description of what the script does and current behaviour notes."""
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

        # Add notes about recent/GUI behavior
        notes = [
            "Additional features in this tool:",
            "- Mirror Output: creates a left/right (horizontal) or up/down (vertical in-plane Y) mirror of coordinates for the output file.",
            "  * Left/Right mirror reflects X positions about ELM.x_size (new_x = ELM.x_size - (x + width)).",
            "  * Up/Down mirror reflects Y positions about ELM.y_size (in-plane flip).",
            "  * The tool does NOT flip panel faces (BOO remains BOO); if you need top↔bottom face flips, request a separate 'face flip' feature.",
            "- Batch processing: 'Process All Files' will process every original CDT in the selected folder using a single length-mapping dialog.",
            "- File naming: generated files use suffixes like 'x' (adjusted), 'xm' (mirrored), 'xmf' (mirrored + vertical flip) and 'xmsf' (mirrored + sheet flip) appended before the extension.",
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

# Example usage
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CDT Sheathing Adjuster - GUI + CLI")
    parser.add_argument("--process", "-p", nargs='+', help="One or more CDT files to process (CLI mode)")
    parser.add_argument("--mirror", action="store_true", help="Mirror output (CLI)")
    # No reverse-sheathing flag; mirror produces an exact mirrored copy
    # Orientation not supported; mirror is always left/right (horizontal)
    parser.add_argument("--lengths", help="Actual lengths mapping as JSON (e.g. '{\"1219.2\":1207}') or comma-separated 'prog=actual' pairs")
    args = parser.parse_args()

    if args.process:
        # Build actual_lengths mapping
        actual_lengths = {}
        if args.lengths:
            text = args.lengths.strip()
            try:
                actual_lengths = json.loads(text)
            except Exception:
                # parse simple k=v pairs
                try:
                    for pair in text.split(','):
                        k, v = pair.split('=')
                        actual_lengths[float(k.strip())] = float(v.strip())
                except Exception as e:
                    print(f"Could not parse lengths mapping: {e}", file=sys.stderr)
                    sys.exit(2)

        for p in args.process:
            if not os.path.exists(p):
                print(f"File not found: {p}", file=sys.stderr)
                continue
            try:
                result = process_cdt_file(p, actual_lengths, mirror=args.mirror, preserve_sheathing=False)
                print(result)
            except Exception as e:
                print(f"Error processing {p}: {e}", file=sys.stderr)
        sys.exit(0)

    # No CLI args: launch GUI
    root = tk.Tk()
    app = CDTAdjusterGUI(root)
    root.mainloop()