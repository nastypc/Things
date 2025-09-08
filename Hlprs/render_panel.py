"""
render_panel.py

Quick renderer for a single panel using the parser in `bak-gui_zones.py`.
Draws stick materials (studs, plates, headers, bracing) only. Excludes sheets/boards/fasteners.
Saves a PNG to the `scripts/` folder named `render_<panel_displaylabel>.png`.

Usage (defaults target Working/07_112.EHX and panel DisplayLabel "07_112"):
    python render_panel.py --ehx "Working/07_112.EHX" --panel "07_112"

The script imports the local `bak-gui_zones.py` (same folder as parent) and calls
`parse_panels()` to obtain panel and material information.
"""
from __future__ import annotations
import argparse
import importlib.util
import os
import sys
from pathlib import Path
from typing import List, Dict, Any

# matplotlib is optional; we will attempt to import it and fail with user-friendly message
try:
    import matplotlib
    matplotlib.use('Agg')  # headless
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches
except Exception as e:
    print('matplotlib is required but not available. Run: python -m pip install matplotlib')
    raise

HERE = Path(__file__).resolve().parent.parent
MODULE_PATH = Path(HERE) / 'bak-gui_zones.py'

# Load parser module from file
spec = importlib.util.spec_from_file_location('bg', str(MODULE_PATH))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

# Defaults
DEFAULT_EHX = str(Path(HERE) / 'Working' / '07_112.EHX')
DEFAULT_PANEL = '07_112'

# Heuristics for selecting stick materials
INCLUDE_KEYWORDS = ['stud', 'plate', 'header', 'bracing', 'sill', 'cripple', 'jack', 'king', 'platecap', 'nailer']
EXCLUDE_KEYWORDS = ['sheet', 'sheath', 'board', 'fastener', 'boardguid', 'sheathing']

COLOR_MAP = {
    'header': '#d9534f',   # red
    'stud': '#7f8c8d',     # gray
    'plate': '#8b5a2b',    # brown
    'bracing': '#2ca02c',  # green
    'default': '#4b77be'   # blue
}


def is_stick_material(m: Dict[str, Any]) -> bool:
    if not isinstance(m, dict):
        return False
    t = str(m.get('Type') or m.get('FamilyMemberName') or '').lower()
    lbl = str(m.get('Label') or '').lower()
    desc = str(m.get('Desc') or m.get('Description') or '').lower()
    # exclude obvious non-sticks
    for ex in EXCLUDE_KEYWORDS:
        if ex in t or ex in lbl or ex in desc:
            return False
    # include if any include keyword appears
    for kw in INCLUDE_KEYWORDS:
        if kw in t or kw in lbl or kw in desc:
            return True
    # Also include obvious 'Bracing' type
    if 'bracing' in t:
        return True
    return False


def pick_color_for_material(m: Dict[str, Any]) -> str:
    t = str(m.get('Type') or m.get('FamilyMemberName') or '').lower()
    lbl = str(m.get('Label') or '').lower()
    for k in ('header', 'stud', 'plate', 'bracing'):
        if k in t or k in lbl:
            return COLOR_MAP.get(k, COLOR_MAP['default'])
    return COLOR_MAP['default']


def find_panel_and_materials(ehx_path: str, panel_ident: str):
    panels, mats_map = mod.parse_panels(ehx_path)
    # panels is list of panel_obj dicts
    target_panel = None
    target_name = None
    for p in panels:
        if not isinstance(p, dict):
            continue
        disp = p.get('DisplayLabel') or p.get('Name')
        if disp == panel_ident or p.get('Name') == panel_ident:
            target_panel = p
            target_name = p.get('Name')
            break
    # fallback: try exact name match in the keys of mats_map
    if not target_panel:
        for k in mats_map.keys():
            if k == panel_ident:
                target_name = k
                # panels list may not have object; create minimal obj
                target_panel = {'Name': k, 'DisplayLabel': panel_ident}
                break
    if not target_panel:
        # fallback to first panel
        if panels:
            target_panel = panels[0]
            target_name = target_panel.get('Name')
    materials = mats_map.get(target_name, []) if target_name else []
    return target_panel, materials


def compute_canvas_bounds(materials: List[Dict[str, Any]], panel_obj: Dict[str, Any]):
    xs = []
    ys = []
    for m in materials:
        try:
            bx0 = float(m.get('bottom_x_min')) if m.get('bottom_x_min') is not None else None
            bx1 = float(m.get('bottom_x_max')) if m.get('bottom_x_max') is not None else None
            if bx0 is not None and bx1 is not None:
                xs.extend([bx0, bx1])
            # use material elev_max_y if present
            if m.get('elev_max_y') is not None:
                ys.append(float(m.get('elev_max_y')))
        except Exception:
            pass
    # also include panel height and elevations
    try:
        if panel_obj and isinstance(panel_obj, dict):
            h = panel_obj.get('Height') or panel_obj.get('PanelHeight')
            if h:
                ys.append(float(h))
            for e in (panel_obj.get('elevations') or []):
                ys.append(float(e.get('max_y') or 0))
                for p in (e.get('points') or []):
                    xs.append(float(p.get('x', 0)))
                    ys.append(float(p.get('y', 0)))
    except Exception:
        pass
    if not xs:
        xs = [0.0, 96.0]  # default 8ft width
    if not ys:
        ys = [0.0, 96.0]
    xmin = min(xs) - 6.0
    xmax = max(xs) + 6.0
    ymin = 0.0
    ymax = max(ys) + 6.0
    return xmin, xmax, ymin, ymax


def render_panel(ehx_path: str, panel_ident: str, out_path: str = None):
    panel_obj, materials = find_panel_and_materials(ehx_path, panel_ident)
    display_label = (panel_obj.get('DisplayLabel') if panel_obj else panel_ident) or panel_ident
    out_name = out_path or (Path(__file__).parent / f"render_{display_label.replace(' ', '_')}.png")

    # filter materials for sticks
    sticks = [m for m in materials if is_stick_material(m)]

    # If GUID filtering was used earlier, many materials may still belong to the panel
    # but parsed materials may include board entries; we filtered them above.

    xmin, xmax, ymin, ymax = compute_canvas_bounds(sticks, panel_obj or {})
    width_in = (xmax - xmin)
    height_in = (ymax - ymin)

    # create figure sized proportionally; DPI 100
    dpi = 100
    fig_w = max(6.0, width_in / 12.0)  # scale: 12 inches -> 1 inch on figure
    fig_h = max(4.0, height_in / 12.0)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=dpi)

    # Background: draw panel outline using elevation polygons if present
    # We will draw a light gray full-height rectangle as background
    ax.add_patch(patches.Rectangle((xmin, ymin), width_in, height_in, facecolor='#f2f2f2', edgecolor='none', zorder=0))

    # Draw each stick material as a rectangle from bottom (y=0) up to elev_max_y (or panel height)
    for m in sticks:
        try:
            bx0 = float(m.get('bottom_x_min')) if m.get('bottom_x_min') is not None else None
            bx1 = float(m.get('bottom_x_max')) if m.get('bottom_x_max') is not None else None
            if bx0 is None or bx1 is None:
                # skip items without horizontal placement
                continue
            top = None
            if m.get('elev_max_y') is not None:
                top = float(m.get('elev_max_y'))
            else:
                # try panel height
                try:
                    top = float(panel_obj.get('Height')) if panel_obj and panel_obj.get('Height') else None
                except Exception:
                    top = None
            if top is None:
                # fallback to best elevation from panel_obj
                elevs = panel_obj.get('elevations') or []
                if elevs:
                    top = max((e.get('max_y') or 0) for e in elevs)
            if top is None:
                top = height_in
            h = float(top) - ymin
            if h <= 0:
                h = max(1.0, height_in)
            x = float(bx0)
            w = float(bx1) - float(bx0)
            color = pick_color_for_material(m)
            rect = patches.Rectangle((x, ymin), w, h, facecolor=color, edgecolor='#333333', linewidth=0.5, alpha=0.9, zorder=2)
            ax.add_patch(rect)
            # add small label if space
            lbl = m.get('Label') or m.get('FamilyMemberName') or ''
            if lbl:
                cx = x + w/2
                cy = ymin + min(12.0, h*0.1)
                ax.text(cx, cy, lbl, ha='center', va='bottom', fontsize=6, zorder=3)
        except Exception as e:
            # skip problematic material
            continue

    # annotate axes and save
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_xlabel('X (in)')
    ax.set_ylabel('Y / Elevation (in)')
    ax.set_title(f'Panel: {display_label}')
    ax.set_aspect('equal', adjustable='box')

    # invert Y axis if desired (so 0 is bottom) — matplotlib has origin at lower-left by default; keep as-is

    # tidy up
    plt.tight_layout()
    out_name = str(out_name)
    plt.savefig(out_name, dpi=dpi)
    print(f"Saved rendered panel to: {out_name}")


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--ehx', default=DEFAULT_EHX, help='Path to EHX file (relative to project root or absolute)')
    p.add_argument('--panel', default=DEFAULT_PANEL, help='Panel DisplayLabel or internal Name to render')
    p.add_argument('--out', default='', help='Optional output PNG path')
    args = p.parse_args()
    ehx_path = args.ehx
    if not os.path.isabs(ehx_path):
        ehx_path = str(Path(HERE) / args.ehx)
    out = args.out if args.out else None
    try:
        render_panel(ehx_path, args.panel, out)
    except Exception as e:
        print('Error rendering panel:', e)
        raise
