import os
import sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import Xmain
from src.main import format_float

if __name__ == '__main__':
    x = Xmain.CDTFile(r'CDT/P1.CDT')
    x.parse()
    def fmt_wrapped(value, width):
        return format_float(value)
    # Build horizontal_nl_groups similarly to Xmain.write_adjusted_file expectations
    horiz = {}
    # Xmain.generate_glue_lines expects horizontal_nl_groups built from NL parsing in x.parse();
    # but x.parse() does not store horizontal_nl_groups publicly. We'll call generate_glue_lines with {}
    gls = x.generate_glue_lines({}, fmt_wrapped, 0.0, x.header.x_size if x.header else 0.0, 0.0, x.header.y_size if x.header else 0.0)
    print('Xmain generated', len(gls))
    for g in gls:
        print(g)
