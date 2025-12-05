"""Independent runner that applies the `main` adjustments but uses
the canonical glue generation from `Xmain`.

Usage:
  python src/xmain_runner.py --input CDT/P1.CDT [--mirror] [--preserve-sheathing] [--force-regenerate-gl] [--out output.cdt]
"""
import argparse
import os
import sys
from typing import Any, Optional, Callable

# Ensure project root is on sys.path so `src` can be imported as a namespace
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

try:
    from src import main as main_mod
    # Use the xxmain implementation as the authoritative glue generator
    from src import Xxmain as xmain_mod
except Exception:
    # Fallback to importlib if direct import fails
    import importlib
    main_mod = importlib.import_module('src.main')
    # prefer Xxmain
    try:
        xmain_mod = importlib.import_module('src.Xxmain')
    except Exception:
        xmain_mod = importlib.import_module('src.Xmain')


def delegate_to_xmain(cdt_file: Any, file_path: str) -> Callable:
    """Return a function that delegates glue generation to Xmain.CDTFile
    using the current state from `cdt_file`."""

    def merge_gl_lines(gl_lines, gap_tolerance: float = 1.0):
        """Merge horizontal GL segments that are colinear and whose gaps are <= gap_tolerance.
        Returns a new list of GL strings."""
        import re
        parsed = []
        horiz = {}
        float_re = re.compile(r"-?\d+\.?\d*")
        for line in gl_lines:
            s = line.strip().rstrip(';')
            if not s.startswith('GL:'):
                continue
            parts = s.split(':')[1:9]
            try:
                x1 = float(parts[0])
                y1 = float(parts[1])
                z1 = float(parts[2])
                x2 = float(parts[3])
                y2 = float(parts[4])
                z2 = float(parts[5])
            except Exception:
                continue
            orient = 'horizontal' if abs(y1 - y2) < 1e-3 else 'other'
            key = (round(0.5 * (y1 + y2), 3), round(0.5 * (z1 + z2), 3))
            if orient == 'horizontal':
                seg = (min(x1, x2), max(x1, x2))
                horiz.setdefault(key, []).append(seg)
            else:
                parsed.append(line)

        # merge segments per (y,z)
        merged_lines = []
        for key, segs in horiz.items():
            segs_sorted = sorted(segs, key=lambda s: s[0])
            cur_s, cur_e = segs_sorted[0]
            for s_start, s_end in segs_sorted[1:]:
                if s_start <= cur_e + gap_tolerance:
                    cur_e = max(cur_e, s_end)
                else:
                    y_mid, z_mid = key
                    merged_lines.append((cur_s, cur_e, y_mid, z_mid))
                    cur_s, cur_e = s_start, s_end
            y_mid, z_mid = key
            merged_lines.append((cur_s, cur_e, y_mid, z_mid))

        # Build formatted GL strings: use a simple numeric format matching existing output
        out_lines = []
        for s in parsed:
            out_lines.append(s)
        for seg in merged_lines:
            x_s, x_e, y_m, z_m = seg
            # format numbers similar to existing files
            def fmt(v):
                if abs(round(v) - v) < 0.01:
                    return f"{int(round(v))}"
                return f"{v:.2f}"
            line = f"GL:{fmt(x_s)}:{fmt(y_m)}:{fmt(z_m)}:{fmt(x_e)}:{fmt(y_m)}:{fmt(z_m)}:0:0:16;"
            out_lines.append(line)
        return out_lines

    def _gen(horizontal_nl_groups, fmt_value, wall_start, wall_end, wall_bottom, wall_top):
        xinst = xmain_mod.CDTFile(file_path)
        # copy relevant state
        xinst.header = cdt_file.header
        xinst.lines = cdt_file.lines
        xinst.elements = cdt_file.elements
        xinst.sta_elements = cdt_file.sta_elements
        xinst.gl_lines = cdt_file.gl_lines
        raw_lines = xinst.generate_glue_lines(horizontal_nl_groups, fmt_value, wall_start, wall_end, wall_bottom, wall_top)
        # apply post-merge pass to reduce fragmentation at STA intersections
        gap_tol = 1.0
        try:
            if hasattr(main_mod, 'PRESETS'):
                gap_tol = float(main_mod.PRESETS.get('gl_merge_gap_tolerance', gap_tol))
        except Exception:
            pass
        merged = merge_gl_lines(raw_lines, gap_tolerance=gap_tol)
        return merged

    return _gen


def process(file_path: str, mirror: bool = False, preserve_sheathing: bool = False, force_regenerate_gl: bool = False, debug: bool = False, out: Optional[str] = None):
    cdt = main_mod.CDTFile(file_path)
    cdt.parse()

    # Apply sheathing adjustments (uses main's logic for nudging/rounding)
    cdt.adjust_sheathing_positions({})

    # Monkeypatch generate_glue_lines to call Xmain's canonical generator
    cdt.generate_glue_lines = delegate_to_xmain(cdt, file_path)

    base, ext = os.path.splitext(file_path)
    if out:
        output = out
    else:
        suffix = 'x'
        if mirror:
            suffix += 'm' if not preserve_sheathing else 'msf'
        output = f"{base}{suffix}{ext}"

    cdt.write_adjusted_file(output, mirror=mirror, preserve_sheathing=preserve_sheathing, force_regenerate_gl=force_regenerate_gl)

    if debug:
        src = getattr(cdt, '_last_gl_source', None)
        print(f"[debug] GL source used: {src}")

    print(f"Processed {file_path} -> {output}")
    return output


def main():
    p = argparse.ArgumentParser(description='Run Xmain-based sheathing adjuster (runner).')
    p.add_argument('--input', '-i', required=True, help='Input CDT file')
    p.add_argument('--mirror', action='store_true', help='Produce mirror output')
    p.add_argument('--preserve-sheathing', action='store_true', help='Preserve sheathing when mirroring (sheet-flip)')
    p.add_argument('--force-regenerate-gl', action='store_true', help='Force GL regeneration')
    p.add_argument('--debug', action='store_true', help='Verbose debug output')
    p.add_argument('--out', help='Output path (optional)')
    args = p.parse_args()

    process(args.input, mirror=args.mirror, preserve_sheathing=args.preserve_sheathing, force_regenerate_gl=args.force_regenerate_gl, debug=args.debug, out=args.out)


if __name__ == '__main__':
    main()
