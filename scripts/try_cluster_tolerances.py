import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from src.main import CDTFile, PRESETS, GLUE_EDGE, format_float

def try_tol(tol):
    PRESETS['sta_cluster_tolerance'] = tol
    x = CDTFile(r'CDT/P1.CDT')
    x.parse()
    # build horizontal_nl_groups similarly to write_adjusted_file by invoking internal logic
    # There's no easy public builder, but we can call write_adjusted_file into a temp and read back GLs
    # Instead, call generate_glue_lines with an empty horizontal_nl_groups to test per-sta fallback
    def fmt_wrapped(value, width):
        return format_float(value)
    wall_start = 0.0
    wall_end = x.header.x_size if x.header else 0.0
    wall_bottom = 0.0
    wall_top = x.header.y_size if x.header else 0.0
    # Pass empty horizontal_nl_groups => generator will fallback to single GL per STA span
    gls = x.generate_glue_lines({}, fmt_wrapped, wall_start, wall_end, wall_bottom, wall_top)
    print(f"tol={tol} -> {len(gls)} gls")

if __name__ == '__main__':
    for t in [0, 10, 50, 100, 300, 1000]:
        try_tol(t)
