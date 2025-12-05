"""Shared glue generation utilities extracted from Xmain/main.

Provide a single function `generate_glue_lines_from_cdt` that accepts a
CDTFile-like object and returns formatted GL lines. This keeps glue
generation pure and allows writer code to decide about locking/mirroring.
"""
from typing import Any, Dict, List, Tuple
import importlib

try:
    GlueLine = importlib.import_module('src.Xmain').GlueLine
except Exception:
    # Fallback if package path differs
    from Xmain import GlueLine  # type: ignore


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


def generate_glue_lines_from_cdt(cdt, horizontal_nl_groups: Dict[Tuple[str, float, float], Dict[str, Any]], fmt_value, wall_start: float, wall_end: float, wall_bottom: float, wall_top: float, glue_edge: float = 50.8) -> List[str]:
    """Generate GL lines for a CDTFile-like object.

    This is largely the logic taken from Xmain's `generate_glue_lines` but
    implemented as a standalone function so `src/main.py` and other callers
    can share the canonical behaviour.
    """
    # Attempt to get defaults from existing GLs when present
    default_tool = cdt.gl_lines[0].tool_index if getattr(cdt, 'gl_lines', None) else 16
    default_y = cdt.gl_lines[0].y_start if getattr(cdt, 'gl_lines', None) else (0.5 * (wall_bottom + wall_top))
    default_z = cdt.gl_lines[0].z_start if getattr(cdt, 'gl_lines', None) else wall_top

    # Ensure default_y is not pinned to the absolute wall edges; apply glue_edge
    # inset when there's room. This prevents GL y-coordinates being 0 when the
    # wall bottom is zero and the original GL rows used 0 as a placeholder.
    try:
        epsilon = 1e-3
        available_h = float(wall_top) - float(wall_bottom)
        if available_h > 2.0 * float(glue_edge) + epsilon:
            min_y = float(wall_bottom) + float(glue_edge)
            max_y = float(wall_top) - float(glue_edge)
            if default_y <= float(wall_bottom) + epsilon:
                default_y = min_y
            elif default_y >= float(wall_top) - epsilon:
                default_y = max_y
            else:
                # clamp into safe zone
                default_y = max(min(default_y, max_y), min_y)
        else:
            # little vertical room — fall back to midline
            default_y = 0.5 * (float(wall_bottom) + float(wall_top))
    except Exception:
        pass

    # If STA elements exist, prefer row-by-sta emission (anchors to STA spans)
    sta_candidates = []
    if getattr(cdt, 'sta_elements', None):
        # Filter STA elements to the subset that behave as vertical supports
        # (joists/posts). This avoids treating large horizontal members
        # (beams, ledgers) as supports which would split glue runs.
        def is_vertical_support(candidate) -> bool:
            try:
                if candidate.y_size <= candidate.x_size:
                    return False
                if getattr(candidate, 'y_size', 0) <= 200:
                    return False
                name_lower = (getattr(candidate, 'name', '') or '').lower()
                disqualifiers = ("floorjoist", "joist", "beam", "blocking", "ledger")
                if any(token in name_lower for token in disqualifiers):
                    return False
                return True
            except Exception:
                return False

        sta_candidates = [s for s in cdt.sta_elements if is_vertical_support(s)]

    # Build unique STA spans (dedupe exact duplicates)
    unique = {}
    for sta in sta_candidates:
        try:
            s_x = float(sta.x)
            s_w = float(getattr(sta, 'x_size', 0.0))
        except Exception:
            continue
        key = (round(s_x, 3), round(s_x + s_w, 3))
        if key not in unique:
            unique[key] = (s_x, s_x + s_w)
    raw_spans = [unique[k] for k in sorted(unique.keys(), key=lambda kk: kk[0])]

    CLUSTER_TOLERANCE = float(getattr(cdt, 'PRESETS', {}).get('sta_cluster_tolerance', 50.0)) if hasattr(cdt, 'PRESETS') else 50.0
    sta_spans = []
    if raw_spans:
        cur_start, cur_end = raw_spans[0]
        for s, e in raw_spans[1:]:
            if s <= cur_end + CLUSTER_TOLERANCE:
                cur_end = max(cur_end, e)
            else:
                sta_spans.append((cur_start, cur_end))
                cur_start, cur_end = s, e
        sta_spans.append((cur_start, cur_end))
    else:
        sta_spans = []

    out_lines: List[str] = []
    if sta_spans:
        if horizontal_nl_groups:
            rows = []
            for key, info in horizontal_nl_groups.items():
                orient = key[0]
                if orient != 'horizontal':
                    continue
                y = info.get('y', key[1])
                z = info.get('z', key[2])
                rows.append((y, z))
            rows.sort(key=lambda r: r[0])

            for (y_value, z_value) in rows:
                for span_start, span_end in sta_spans:
                    # apply inset from both ends of the STA span
                    gl_start = max(wall_start, span_start + glue_edge)
                    gl_end = min(wall_end, span_end - glue_edge)
                    # If inset would invert the span, fall back to full span
                    if gl_end <= gl_start:
                        gl_start = max(wall_start, span_start)
                        gl_end = min(wall_end, span_end)
                    gl_start = max(gl_start, wall_start)
                    gl_end = min(gl_end, wall_end)
                    if gl_end < gl_start:
                        continue
                    tool_index = default_tool
                    out_lines.append(GlueLine(gl_start, y_value, z_value, gl_end, y_value, z_value, 0.0, 0.0, tool_index).to_string(fmt_value))
            try:
                setattr(cdt, '_last_gl_source', 'glue_module_per_sta_by_row')
            except Exception:
                pass
            return out_lines

        # fallback: no NL rows, one GL per STA span
        for span_start, span_end in sta_spans:
            gl_start = max(wall_start, span_start + glue_edge)
            gl_end = min(wall_end, span_end - glue_edge)
            if gl_end <= gl_start:
                gl_start = max(wall_start, span_start)
                gl_end = min(wall_end, span_end)
            gl_start = max(gl_start, wall_start)
            gl_end = min(gl_end, wall_end)
            if gl_end < gl_start:
                continue
            tool_index = default_tool
            out_lines.append(GlueLine(gl_start, default_y, default_z, gl_end, default_y, default_z, 0.0, 0.0, tool_index).to_string(fmt_value))
        try:
            setattr(cdt, '_last_gl_source', 'glue_module_per_sta')
        except Exception:
            pass
        return out_lines

    # If no STA elements, fall back to a behavior similar to Xmain
    # Build key->original mapping
    key_to_original = {}
    ordered_keys = []
    for gl in getattr(cdt, 'gl_lines', []):
        key = gl.group_key()
        key_to_original.setdefault(key, []).append(gl)
        if key not in ordered_keys:
            ordered_keys.append(key)

    tolerance = 1.0
    epsilon = 1e-3

    gl_objs = []

    for key in ordered_keys:
        orient = key[0]
        originals = key_to_original.get(key, [])
        if orient == 'horizontal' and key in horizontal_nl_groups:
            info = horizontal_nl_groups[key]
            segments = info.get('segments', [])
            template = originals[0] if originals else None
            amplitude = template.amplitude if template else 0.0
            wavelength = template.wavelength if template else 0.0
            y_value = info.get('y', template.y_start if template else 0.0)
            z_value = info.get('z', template.z_start if template else 0.0)
            tool_index = template.tool_index if template else default_tool
            widths = template.widths if template else None

            if segments:
                merged = merge_axis_segments(segments, tolerance)
                spans = merged
            else:
                spans = [(min(g.x_start, g.x_end), max(g.x_start, g.x_end)) for g in originals]

            for span_start, span_end in spans:
                gl_start = span_start
                gl_end = span_end
                if span_start <= wall_start + epsilon:
                    gl_start = min(max(wall_start, span_start + glue_edge), gl_end)
                if span_end >= wall_end - epsilon:
                    gl_end = max(min(wall_end, span_end - glue_edge), gl_start)
                if gl_end < gl_start:
                    gl_end = gl_start
                gl_objs.append(GlueLine(gl_start, y_value, z_value, gl_end, y_value, z_value, amplitude, wavelength, tool_index, widths=widths))

        elif orient == 'vertical' and originals:
            for gl in originals:
                y_start = gl.y_start
                y_end = gl.y_end
                if y_start <= wall_bottom + epsilon:
                    y_start = min(max(wall_bottom, y_start + glue_edge), y_end)
                if y_end >= wall_top - epsilon:
                    y_end = max(min(wall_top, y_end - glue_edge), y_start)
                gl_objs.append(GlueLine(gl.x_start, y_start, gl.z_start, gl.x_end, y_end, gl.z_end, gl.amplitude, gl.wavelength, gl.tool_index, widths=gl.widths))

        else:
            for gl in originals:
                gl_objs.append(gl)

    # Include NL-derived groups not matched earlier
    for key, info in horizontal_nl_groups.items():
        if key in key_to_original:
            continue
        segments = info.get('segments', [])
        if not segments:
            continue
        merged = merge_axis_segments(segments, tolerance)
        if not merged:
            continue
        y_value = info.get('y', 0.0)
        z_value = info.get('z', 0.0)
        for span_start, span_end in merged:
            gl_start = span_start
            gl_end = span_end
            if span_start <= wall_start + epsilon:
                gl_start = min(max(wall_start, span_start + glue_edge), gl_end)
            if span_end >= wall_end - epsilon:
                gl_end = max(min(wall_end, span_end - glue_edge), gl_start)
            if gl_end < gl_start:
                gl_end = gl_start
            gl_objs.append(GlueLine(gl_start, y_value, z_value, gl_end, y_value, z_value, 0.0, 0.0, default_tool))

    horiz_map = {}
    final_objs = []
    for g in gl_objs:
        if abs(g.y_start - g.y_end) <= 1e-3 and abs(g.z_start - g.z_end) <= 1e-3:
            yk = round(0.5 * (g.y_start + g.y_end), 3)
            zk = round(0.5 * (g.z_start + g.z_end), 3)
            horiz_map.setdefault((yk, zk), []).append((min(g.x_start, g.x_end), max(g.x_start, g.x_end), g))
        else:
            final_objs.append(g)

    for (yk, zk), spans in horiz_map.items():
        segments = [(s, e) for s, e, _ in spans]
        merged = merge_axis_segments(segments, tolerance)
        for mstart, mend in merged:
            rep = None
            for s, e, obj in spans:
                if not (e < mstart - 1e-6 or s > mend + 1e-6):
                    rep = obj
                    break
            if rep is None:
                rep = spans[0][2]
            amplitude = rep.amplitude
            wavelength = rep.wavelength
            tool_index = rep.tool_index
            final_objs.append(GlueLine(mstart, rep.y_start, rep.z_start, mend, rep.y_start, rep.z_start, amplitude, wavelength, tool_index, widths=rep.widths))

    out_lines = [obj.to_string(fmt_value) for obj in final_objs]
    try:
        setattr(cdt, '_last_gl_source', 'glue_module_fallback')
    except Exception:
        pass
    return out_lines


def merge_gl_lines(gl_lines: List[str], fmt_value, gap_tolerance: float = 1.0) -> List[str]:
    """Merge adjacent horizontal GL segments that share the same (y,z)
    grouping when the gap between segments is <= gap_tolerance (mm).

    Accepts a list of formatted GL strings and returns a new list of
    formatted GL strings after merging. Non-horizontal GLs are preserved.
    """
    parsed = []
    for s in gl_lines:
        try:
            gl = GlueLine.from_line(s)
            parsed.append(gl)
        except Exception:
            # preserve lines we can't parse
            parsed.append(s)

    horiz_map = {}
    others = []
    for item in parsed:
        if isinstance(item, GlueLine):
            orient = item.orientation()
            if orient == 'horizontal':
                yk = round(0.5 * (item.y_start + item.y_end), 3)
                zk = round(0.5 * (item.z_start + item.z_end), 3)
                horiz_map.setdefault((yk, zk), []).append((min(item.x_start, item.x_end), max(item.x_start, item.x_end), item))
            else:
                others.append(item)
        else:
            others.append(item)

    merged_lines = []
    for (yk, zk), spans in horiz_map.items():
        spans_sorted = sorted(spans, key=lambda t: t[0])
        cur_s, cur_e, cur_obj = spans_sorted[0]
        reps = [cur_obj]
        for s, e, obj in spans_sorted[1:]:
            if s <= cur_e + gap_tolerance:
                # merge
                cur_e = max(cur_e, e)
                reps.append(obj)
            else:
                # finalize current
                rep = reps[0]
                new_obj = GlueLine(cur_s, rep.y_start, rep.z_start, cur_e, rep.y_start, rep.z_start, rep.amplitude, rep.wavelength, rep.tool_index, widths=rep.widths)
                merged_lines.append(new_obj.to_string(fmt_value))
                cur_s, cur_e, cur_obj = s, e, obj
                reps = [obj]
        # finalize last
        rep = reps[0]
        new_obj = GlueLine(cur_s, rep.y_start, rep.z_start, cur_e, rep.y_start, rep.z_start, rep.amplitude, rep.wavelength, rep.tool_index, widths=rep.widths)
        merged_lines.append(new_obj.to_string(fmt_value))

    # append non-horizontal or unparsable lines as-is (preserve original order where possible)
    # To preserve deterministic ordering, place merged horizontals first sorted by x start
    try:
        others_strs = []
        for o in others:
            if isinstance(o, GlueLine):
                others_strs.append(o.to_string(fmt_value))
            else:
                others_strs.append(str(o))
    except Exception:
        others_strs = [str(o) for o in others]

    # Combine: horizontals then others (matches prior behaviour where horizontals are primary)
    return merged_lines + others_strs
