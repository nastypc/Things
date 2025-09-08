"""
render_panel_gui.py

Provides a simple Tkinter popup that displays the rendered panel image created by
`scripts/render_panel.py` and allows loading a reference image (PNG) or PDF.
- If the reference is a PNG, it can be overlaid semi-transparently for visual comparison.
- If the reference is a PDF and PyMuPDF is available, the first page is rendered and overlaid.
- If PyMuPDF is not available for PDFs, the script will open the PDF with the system viewer.

Usage examples:
    python render_panel_gui.py --ehx "Working/07_112.EHX" --panel "07_112"
    python render_panel_gui.py --ehx "Working/07_112.EHX" --panel "07_112" --no-gui  # just render PNG and exit

This is intentionally a separate script; it will call into `scripts/render_panel.py` to
produce the PNG then present a popup for visual comparison.
"""
from __future__ import annotations
import importlib.util
import os
import sys
from pathlib import Path
import tempfile
import tkinter as tk
from tkinter import filedialog, messagebox

# PIL for image handling
try:
    from PIL import Image, ImageTk, ImageOps
except Exception:
    print('Pillow is required. Installing may help: python -m pip install Pillow')
    raise

# Try to import PyMuPDF for PDF->image rendering (optional)
HAS_PYMUPDF = False
try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except Exception:
    HAS_PYMUPDF = False

HERE = Path(__file__).resolve().parent
RENDERER = Path(HERE) / 'render_panel.py'

# load render_panel module
spec = importlib.util.spec_from_file_location('rp', str(RENDERER))
rp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rp)

DEFAULT_EHX = str(Path(__file__).resolve().parents[1] / 'Working' / '07_112.EHX')
DEFAULT_PANEL = '07_112'


def render_to_png(ehx_path: str, panel_ident: str, out_path: str | None = None) -> str:
    """Call the renderer to produce PNG and return the PNG path."""
    out = out_path or (Path(HERE) / f"render_{panel_ident.replace(' ', '_')}.png")
    try:
        # rp.render_panel will save a PNG if successful
        rp.render_panel(ehx_path, panel_ident, str(out))
        return str(out)
    except Exception as e:
        raise


def render_pdf_first_page_to_pil(pdf_path: str, zoom: float = 2.0):
    """Render the first page of a PDF to a PIL image using PyMuPDF when available.
    Returns None if not available.
    """
    if not HAS_PYMUPDF:
        return None
    try:
        doc = fitz.open(pdf_path)
        page = doc.load_page(0)
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
        return img
    except Exception:
        return None


class PanelCompareApp:
    def __init__(self, master, ehx_path: str, panel_ident: str, png_path: str):
        self.master = master
        self.ehx_path = ehx_path
        self.panel_ident = panel_ident
        self.png_path = png_path
        self.base_img = Image.open(png_path).convert('RGBA')
        self.ref_img = None
        self.overlay_on = tk.BooleanVar(value=False)
        self.opacity = tk.DoubleVar(value=0.5)

        self.build_ui()
        self.show_base()

    def build_ui(self):
        self.master.title(f'Panel Preview - {self.panel_ident}')
        # main frame
        frm = tk.Frame(self.master)
        frm.pack(fill='both', expand=True)

        # canvas
        self.canvas = tk.Canvas(frm, bg='#ffffff')
        self.canvas.pack(side='left', fill='both', expand=True)

        ctrl = tk.Frame(frm)
        ctrl.pack(side='right', fill='y')

        tk.Button(ctrl, text='Load reference (PNG/PDF)', command=self.load_reference).pack(padx=6, pady=6)
        tk.Checkbutton(ctrl, text='Overlay reference', variable=self.overlay_on, command=self.update_overlay).pack(padx=6, pady=6)
        tk.Label(ctrl, text='Overlay opacity').pack(padx=6, pady=(12,0))
        scale = tk.Scale(ctrl, from_=0, to=100, orient='horizontal', variable=tk.IntVar(value=int(self.opacity.get()*100)), command=self._scale_cb)
        # link scale to opacity var
        scale.set(int(self.opacity.get()*100))
        scale.pack(padx=6, pady=6)
        tk.Button(ctrl, text='Open reference externally', command=self.open_reference_externally).pack(padx=6, pady=6)
        tk.Button(ctrl, text='Close', command=self.master.destroy).pack(side='bottom', padx=6, pady=12)

        # keep refs
        self._scale_widget = scale

    def _scale_cb(self, val):
        try:
            v = float(val)/100.0
            self.opacity.set(v)
            self.update_overlay()
        except Exception:
            pass

    def show_base(self):
        # Fit image to canvas size; for simplicity set canvas to image size
        w, h = self.base_img.size
        self.canvas.config(width=w, height=h)
        self.tk_base = ImageTk.PhotoImage(self.base_img)
        self.canvas.create_image(0, 0, image=self.tk_base, anchor='nw', tags='base')
        self.canvas.config(scrollregion=(0,0,w,h))

    def load_reference(self):
        p = filedialog.askopenfilename(title='Select reference (PNG or PDF)', filetypes=[('Images and PDFs','*.png;*.jpg;*.jpeg;*.pdf'), ('PNG','*.png'), ('PDF','*.pdf')])
        if not p:
            return
        ext = Path(p).suffix.lower()
        if ext in ('.png', '.jpg', '.jpeg'):
            try:
                img = Image.open(p).convert('RGBA')
                self.ref_img = img
                self.overlay_on.set(True)
                self.update_overlay()
            except Exception as e:
                messagebox.showerror('Load error', f'Could not load image: {e}')
        elif ext == '.pdf':
            # try to render with PyMuPDF
            img = render_pdf_first_page_to_pil(p, zoom=2.0)
            if img is not None:
                self.ref_img = img.convert('RGBA')
                self.overlay_on.set(True)
                self.update_overlay()
            else:
                # fallback: open externally
                if messagebox.askyesno('PDF', 'PyMuPDF not available or PDF rendering failed. Open PDF in external viewer?'):
                    try:
                        os.startfile(p)
                    except Exception:
                        messagebox.showinfo('Open PDF', f'Please open the file manually: {p}')
        else:
            messagebox.showinfo('Unsupported', 'Unsupported file type')

    def update_overlay(self):
        # remove any existing overlay
        self.canvas.delete('overlay')
        if not self.overlay_on.get() or self.ref_img is None:
            return
        # resize reference to base image size
        try:
            base_w, base_h = self.base_img.size
            ref = ImageOps.contain(self.ref_img, (base_w, base_h)).convert('RGBA')
            # apply opacity
            alpha = int(max(0, min(255, round(self.opacity.get() * 255))))
            overlay = ref.copy()
            # set alpha channel
            overlay.putalpha(alpha)
            self.tk_overlay = ImageTk.PhotoImage(overlay)
            self.canvas.create_image(0, 0, image=self.tk_overlay, anchor='nw', tags='overlay')
        except Exception as e:
            messagebox.showerror('Overlay error', f'Could not overlay reference: {e}')

    def open_reference_externally(self):
        p = filedialog.askopenfilename(title='Select reference to open', filetypes=[('PDF','*.pdf'),('Any','*.*')])
        if not p:
            return
        try:
            os.startfile(p)
        except Exception:
            messagebox.showinfo('Open reference', f'Please open manually: {p}')


def main(argv=None):
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--ehx', default=DEFAULT_EHX, help='EHX path')
    p.add_argument('--panel', default=DEFAULT_PANEL, help='Panel DisplayLabel or Name')
    p.add_argument('--out', default='', help='Optional PNG output path')
    p.add_argument('--no-gui', action='store_true', help='Render PNG but do not open GUI (for automated runs)')
    args = p.parse_args(argv or sys.argv[1:])

    ehx_path = args.ehx
    if not os.path.isabs(ehx_path):
        ehx_path = str(Path(__file__).resolve().parents[1] / args.ehx)
    out = args.out if args.out else None

    try:
        png = render_to_png(ehx_path, args.panel, out)
    except Exception as e:
        print('Rendering failed:', e)
        sys.exit(1)

    if args.no_gui:
        print('Rendered PNG to:', png)
        return

    # Launch GUI
    root = tk.Tk()
    app = PanelCompareApp(root, ehx_path, args.panel, png)
    root.mainloop()


if __name__ == '__main__':
    main()
