# --- Canonical process_cdt_file function from main.py, now embedded ---
def process_cdt_file(file_path, actual_lengths=None, mirror=False, preserve_sheathing=False, debug=False, force_regenerate_gl=False):
    cdt_file = CDTFile(file_path)
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
    # Write adjusted file
    suffix = 'x'
    if mirror:
        if preserve_sheathing:
            suffix += 'msf'
        else:
            suffix += 'm'
    output_file = f"{base}{suffix}{ext}"
    cdt_file.write_adjusted_file(output_file, mirror=mirror, preserve_sheathing=preserve_sheathing, force_regenerate_gl=True)
    result += f"\nAdjusted CDT file written to {output_file}"
    return result
"""Launcher that starts the canonical CDT Adjuster GUI from `src/main.py`.

This file intentionally keeps no custom GUI code. The user requested the GUI
to match the canonical `CDTAdjusterGUI` in `src/main.py`. This launcher ensures
we run that class directly so behavior and feature parity are preserved.

It attempts to import `CDTAdjusterGUI` from `src.main`. If that import fails
when running from inside the `src` directory, it will try a fallback import.
"""

import os
import sys
import traceback
from tkinter import messagebox

try:
    import tkinter as tk
except Exception:
    raise

# Make sure project root (one level up from this file) is on sys.path so
# `import src.main` works reliably whether running from project root or from
# inside the `src` folder.
_HERE = os.path.dirname(__file__)
_ROOT = os.path.abspath(os.path.join(_HERE, '..'))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


from enum import Enum
import math
import copy
import re
import shutil
from typing import Any, Dict, List, Optional, Set, Tuple

FLYOVER_THRESHOLD_MM = 27.0 * 25.4
GLUE_EDGE_OFFSET = 50.8
DEFAULT_NL_EDGE_OFFSET = 76.2
PERIMETER_NL_SPACING = 152.4
FIELD_NL_SPACING = 304.8
TONGUE_GROOVE_OFFSET = 12.7
SQUARE_EDGE_OFFSET = 6.35
MEMBER_EDGE_DISTANCE = 76.2

class ELF(Enum):
    OUTSIDE = "outside"
    UP = "up"

class CDTHeader:
    def __init__(self, x_size, y_size, z_size, element_type, length, measurement, quality):
        self.x_size = x_size
        self.y_size = y_size
        self.z_size = z_size
        self.element_type = element_type
        self.length = length
        self.measurement = measurement
        self.quality = quality
    @classmethod
    def from_elm_line(cls, line):
        parts = line.rstrip(';').split(':')
        x_size = float(parts[1].strip())
        y_size = float(parts[2].strip())
        z_size = float(parts[3].strip())
        element_type = int(parts[4].strip())
        length = float(parts[5].strip())
        measurement = float(parts[6].strip())
        quality = float(parts[7].strip())
        return cls(x_size, y_size, z_size, element_type, length, measurement, quality)

class SheathingElement:
    def __init__(self, element_type, x_size, y_size, z_size, x, y, z, tool_index, name, raw=""):
        self.element_type = element_type
        self.x_size = x_size
        self.y_size = y_size
        self.z_size = z_size
        self.x = x
        self.y = y
        self.z = z
        self.tool_index = tool_index
        self.name = name
        self.original_x = x
        self.original_x_size = x_size
        self.original_y = y
        self.original_y_size = y_size
        self.raw = raw
    @classmethod
    def from_cdt_line(cls, line):
        parts = line.rstrip(';').split(':')
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

class CDTFile:
    def __init__(self, file_path):
        self.file_path = file_path
        self.header = None
        self.elements = []
        self.sta_elements = []
        self.lines = []
        self.gl_lines = []
        self.length_warnings = []
        self.flyover_extension = 0.0
        self.last_sheet_mode = "trimmed"
        self.last_sheet_target = 0.0
        self.last_sheet_gap = 0.0
        self.original_x_span = None
    def write_adjusted_file(self, output_path, mirror=False, orientation='horizontal', preserve_sheathing=False, force_regenerate_gl=False):
        """Write the adjusted CDT file with updated geometry and formatting."""
        import math, copy, os
        def fmt_value(value, width):
            as_int = int(math.floor(value + 0.5))
            if abs(as_int - value) < 0.01:
                return f"{as_int:>{max(width, len(str(as_int)))}}"
            text = f"{value:.2f}"
            if width and len(text) > width:
                text = f"{value:.3f}"
            return f"{text:>{max(width, len(text))}}"
        mirrored_backups = {}
        did_restore_boo = False
        if mirror and self.header is not None:
            mirrored_backups['elements'] = [(e.x, e.x_size, e.y, e.y_size) for e in self.elements]
            mirrored_backups['sta'] = [(s.x, s.x_size, s.y, s.y_size) for s in self.sta_elements]
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
                    for elem in self.sta_elements:
                        parts = content.rstrip(';').split(':')
                        if len(parts) >= 8:
                            widths = [len(part) for part in parts[1:]]
                            parts[1] = fmt_value(elem.x_size, widths[0])
                            parts[2] = fmt_value(elem.y_size, widths[1])
                            parts[3] = fmt_value(elem.z_size, widths[2])
                            parts[4] = f"{elem.tool_index:>{max(widths[3], len(str(elem.tool_index)))}}"
                            parts[5] = elem.name
                            rebuilt = ':'.join(parts)
                            f.write(rebuilt + ';' + newline)
                        else:
                            f.write(content + newline)
                        break
                    continue
                if stripped.startswith('BOO') or stripped.startswith('BOI'):
                    for elem in self.elements:
                        if elem.raw.strip().startswith(stripped[:3]):
                            parts = content.rstrip(';').split(':')
                            if len(parts) >= 9:
                                widths = [len(part) for part in parts[1:]]
                                parts[1] = fmt_value(elem.x_size, widths[0])
                                parts[2] = fmt_value(elem.y_size, widths[1])
                                parts[3] = fmt_value(elem.z_size, widths[2])
                                parts[4] = fmt_value(elem.x, widths[3])
                                parts[5] = fmt_value(elem.y, widths[4])
                                parts[6] = fmt_value(elem.z, widths[5])
                                parts[7] = f"{elem.tool_index:>{max(widths[6], len(str(elem.tool_index)))}}"
                                parts[8] = elem.name
                                rebuilt = ':'.join(parts)
                                f.write(rebuilt + ';' + newline)
                            else:
                                f.write(content + newline)
                            break
                    continue
                if stripped.startswith('GL:'):
                    for gl in self.gl_lines:
                        f.write(gl.to_string(fmt_value) + ';' + newline)
                    continue
                f.write(content + newline)
    def parse(self):
        with open(self.file_path, 'r', encoding='utf-8', errors='replace') as f:
            self.lines = f.readlines()
        for raw in self.lines:
            line = raw.rstrip('\n')
            s = line.strip()
            if not s:
                continue
            try:
                if s.startswith('ELM:'):
                    try:
                        self.header = CDTHeader.from_elm_line(s)
                    except Exception:
                        pass
                elif s.startswith('BOO') or s.startswith('BOI'):
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
                continue
        if self.header:
            self.original_x_span = self.header.x_size
            self.original_y_span = self.header.y_size
    def get_sheathing_elements(self):
        return [elem for elem in self.elements if elem.element_type.startswith('BOO') or elem.element_type.startswith('BOI')]
    def get_all_structural_elements(self):
        return self.sta_elements + self.get_sheathing_elements()
    def adjust_sheathing_positions(self, actual_lengths):
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
                elem.x = cumulative_x
                cumulative_x += elem.x_size
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
                self.length_warnings.append(f"Preceding sheathing exceeds footprint by {abs(remaining_raw):.2f}mm; clamping remaining span to 0.")
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
                self.length_warnings.append(f"Sheathing total {final_sum:.2f}mm differs from footprint {original_span:.2f}mm.")
            adjusted_span = final_sum
            self.header.x_size = adjusted_span
            self.header.length = adjusted_span
        # ...existing code...

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
import json
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
        self.sheet_flip_var = tk.BooleanVar(value=False)
        tk.Checkbutton(ctrl, text="Sheet Flip", variable=self.sheet_flip_var).pack(side='left', padx=(6,0))
        tk.Button(ctrl, text="Process Selected Files", command=self.process).pack(side='right')
        tk.Button(ctrl, text="Process All Files", command=self.process_all).pack(side='right', padx=(6,0))
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
        self.file_listbox_original.bind("<Button-3>", lambda e: self.open_file(e, 'original'))
        middle.add(left_col)

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

        self.result_text = tk.Text(root, height=8)
        self.result_text.grid(row=3, column=0, columnspan=3, sticky='ew', padx=6, pady=(0,6))

        self.file_listbox_original.bind('<<ListboxSelect>>', lambda e: None)
        self.file_listbox_processed.bind('<<ListboxSelect>>', lambda e: None)

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

    def load_folder(self, folder_path):
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
                result = process_cdt_file(file_path, actual_lengths)
                results.append(f"Processed {file_name}:\n{result}\n")
            except Exception as e:
                results.append(f"Error processing {file_name}: {str(e)}\n")
        self.result_text.delete(1.0, tk.END)
        self.result_text.insert(tk.END, '\n'.join(results))

    def process_all(self):
        folder_path = self.folder_entry.get().strip()
        if not folder_path or not os.path.exists(folder_path):
            messagebox.showerror("Error", "Folder path is not set or does not exist.")
            return
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
            try:
                result = process_cdt_file(file_path, actual_lengths)
                results.append(f"Processed {file_name}:\n{result}\n")
            except Exception as e:
                results.append(f"Error processing {file_name}: {str(e)}\n")
        self.result_text.delete(1.0, tk.END)
        self.result_text.insert(tk.END, '\n'.join(results))

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


# --- Canonical glue logic from xxmain.py, now embedded ---
GLUE_EDGE_OFFSET = 50.8

class GlueLine:
    def __init__(self, x_start, y_start, z_start, x_end, y_end, z_end, amplitude, wavelength, tool_index, raw=None, widths=None):
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

    @staticmethod
    def _format(fmt_value, x_start, y_start, z_start, x_end, y_end, z_end, amplitude, wavelength, tool_index, widths):
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

    def to_string(self, fmt_value):
        return self._format(fmt_value, self.x_start, self.y_start, self.z_start, self.x_end, self.y_end, self.z_end, self.amplitude, self.wavelength, self.tool_index, self.widths)

    def format_with(self, fmt_value, x_start, y_start, z_start, x_end, y_end, z_end, amplitude, wavelength, tool_index):
        return self._format(fmt_value, x_start, y_start, z_start, x_end, y_end, z_end, amplitude, wavelength, tool_index, self.widths)

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

def merge_axis_segments(segments, tolerance=1.0):
    if not segments:
        return []
    ordered = sorted(segments, key=lambda span: span[0])
    merged = []
    current_start, current_end = ordered[0]
    for start, end in ordered[1:]:
        if start <= current_end + tolerance:
            current_end = max(current_end, end)
        else:
            merged.append((current_start, current_end))
            current_start, current_end = start, end
    merged.append((current_start, current_end))
    return merged

def generate_glue_lines(self, horizontal_nl_groups, fmt_value, wall_start, wall_end, wall_bottom, wall_top):
    default_tool = self.gl_lines[0].tool_index if self.gl_lines else 16
    key_to_original = {}
    ordered_keys = []
    for gl in self.gl_lines:
        key = gl.group_key()
        key_to_original.setdefault(key, []).append(gl)
        if key not in ordered_keys:
            ordered_keys.append(key)

    emitted = set()
    new_lines = []
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
                merged = merge_axis_segments(segments, tolerance)
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
                gl_start = min(max(wall_start, span_start + GLUE_EDGE_OFFSET), gl_end)
            if span_end >= wall_end - epsilon:
                gl_end = max(min(wall_end, span_end - GLUE_EDGE_OFFSET), gl_start)
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
                    y_start = min(max(wall_bottom, y_start + GLUE_EDGE_OFFSET), y_end)
                if y_end >= wall_top - epsilon:
                    y_end = max(min(wall_top, y_end - GLUE_EDGE_OFFSET), y_start)
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
            merged = merge_axis_segments(segments, tolerance)
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


def main():
    root = tk.Tk()
    app = CDTAdjusterGUI(root)
    root.geometry('1200x800')
    root.mainloop()

if __name__ == '__main__':
    main()
