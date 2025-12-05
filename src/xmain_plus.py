"""Enhanced Xmain GUI wrapper that uses the xmain_runner processing logic.

This keeps the original `src/Xmain.py` intact but provides a GUI that
calls `src/xmain_runner.process(...)` so all the main.py adjustments and
Xmain glue logic are used together.

Run with:
  python src/xmain_plus.py
"""
import os
import tkinter as tk
from tkinter import filedialog, messagebox

import sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
try:
    from src import Xmain as xmain_mod
    from src import xmain_runner
except Exception:
    import importlib
    xmain_mod = importlib.import_module('src.Xmain')
    xmain_runner = importlib.import_module('src.xmain_runner')


class XmainPlusGUI(xmain_mod.CDTAdjusterGUI):
    def __init__(self, root):
        super().__init__(root)
        # Add additional options to the GUI
        row = 0
        # Place checkboxes below folder entry
        opt_frame = tk.Frame(self.root)
        opt_frame.grid(row=0, column=3, rowspan=2, sticky='n')

        self.var_mirror = tk.BooleanVar(value=False)
        self.var_preserve = tk.BooleanVar(value=False)
        self.var_force_gl = tk.BooleanVar(value=False)

        tk.Checkbutton(opt_frame, text='Mirror', variable=self.var_mirror).pack(anchor='w')
        tk.Checkbutton(opt_frame, text='Preserve Sheathing (sheet-flip)', variable=self.var_preserve).pack(anchor='w')
        tk.Checkbutton(opt_frame, text='Force Regenerate GL', variable=self.var_force_gl).pack(anchor='w')

    def process(self):
        folder_path = self.folder_entry.get().strip()
        selected_indices = self.file_listbox.curselection()
        if not selected_indices:
            messagebox.showerror('Error', 'No files selected.')
            return

        # Collect unique BOO1 sizes from selected files, excluding the last BOO1 in each file
        unique_sizes = set()
        for idx in selected_indices:
            file_name = self.file_listbox.get(idx)
            file_path = os.path.join(folder_path, file_name)
            try:
                cdt = xmain_mod.CDTFile(file_path)
                cdt.parse()
                boo1_elements = [elem for elem in cdt.get_sheathing_elements() if elem.element_type == 'BOO1']
                for i, elem in enumerate(boo1_elements):
                    if i < len(boo1_elements) - 1:
                        unique_sizes.add(elem.x_size)
            except Exception as e:
                messagebox.showerror('Error', f'Failed to parse {file_name}: {str(e)}')
                return

        if not unique_sizes:
            messagebox.showerror('Error', 'No BOO1 elements found in selected files.')
            return

        # Show dialog for inputting actual lengths (reuse Xmain's dialog)
        dialog = xmain_mod.LengthInputDialog(self.root, unique_sizes)
        if dialog.result is None:
            return

        actual_lengths = dialog.result

        # Process each file using xmain_runner.process
        results = []
        for idx in selected_indices:
            file_name = self.file_listbox.get(idx)
            file_path = os.path.join(folder_path, file_name)
            try:
                out = xmain_runner.process(file_path, mirror=self.var_mirror.get(), preserve_sheathing=self.var_preserve.get(), force_regenerate_gl=self.var_force_gl.get(), debug=False)
                results.append(f'Processed {file_name} -> {out}')
            except Exception as e:
                results.append(f'Error processing {file_name}: {str(e)}')

        self.result_text.delete(1.0, tk.END)
        self.result_text.insert(tk.END, '\n'.join(results))


if __name__ == '__main__':
    root = tk.Tk()
    app = XmainPlusGUI(root)
    root.mainloop()
