import os
import sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.main import CDTFile, GLUE_EDGE, format_float

if __name__ == '__main__':
    x = CDTFile(r'CDT/P1.CDT')
    x.parse()
    print('GLUE_EDGE=', GLUE_EDGE)
    print('Total parsed sta_elements:', len(x.sta_elements))
    for i, s in enumerate(x.sta_elements[:50], 1):
        try:
            xs = float(s.x)
            xsz = float(getattr(s, 'x_size', 0.0))
        except Exception:
            xs = s.x
            xsz = getattr(s, 'x_size', None)
        print(f'{i:2d}: x={xs} x_size={xsz} type={getattr(s, "element_type", None)}')
    # call generate_glue_lines
    # Need horizontal_nl_groups and wall bounds - quick compute by reusing parse internals
    # Build horizontal_nl_groups by scanning NL lines from x.lines
    horiz = {}
    wall_start = 0.0
    wall_end = x.header.x_size if x.header else 0.0
    wall_bottom = 0.0
    wall_top = x.header.z_size if x.header else 0.0
    # build minimal horizontal_nl_groups: assume previous parse stored them in x._cached_horizontal_nl_groups if present
    try:
        horiz = x._cached_horizontal_nl_groups
    except Exception:
        horiz = {}
    # GlueLine expects fmt_value(value, width) so wrap format_float
    def fmt_wrapped(value, width):
        return format_float(value)

    gls = x.generate_glue_lines(horiz, fmt_wrapped, wall_start, wall_end, wall_bottom, wall_top)
    print('Generated GL count:', len(gls))
    for g in gls:
        print(g)
