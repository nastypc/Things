"""Simple runner to exercise oldd.py parse_panels + writer and verify logs.

Usage: python run_parse_and_write.py
"""
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEST_EHX = HERE / 'Working' / 'Test' / '07_112.EHX'


def resolve_input_path(argv):
    # If user provided a path, use that; otherwise fall back to TEST_EHX
    if len(argv) >= 2:
        p = Path(argv[1])
        if p.exists():
            return p
        # try resolving relative to HERE
        pr = HERE / argv[1]
        if pr.exists():
            return pr
        print(f"Provided EHX not found: {argv[1]}")
        sys.exit(2)
    return TEST_EHX

def main():
    ehx_path = resolve_input_path(sys.argv)
    if not ehx_path.exists():
        print(f"EHX not found: {ehx_path}")
        sys.exit(2)

    # Import the local oldd module
    try:
        import oldd
    except Exception as e:
        print(f"Failed to import oldd.py: {e}")
        sys.exit(3)

    print(f"Parsing: {ehx_path}")
    panels, materials_map = oldd.parse_panels(str(ehx_path))
    print(f"Panels parsed: {len(panels)}")

    # Build panels_by_name mapping (oldd.write expects that shape)
    panels_by_name = {}
    for p in panels:
        if not p:
            continue
        name = p.get('Name') or p.get('PanelGuid') or (p.get('DisplayLabel') or f"Panel_{len(panels_by_name)+1}")
        panels_by_name[name] = p

    # Call writer and verify files
    try:
        # Pass the actual resolved input path so logs are written for that file
        oldd.write_expected_and_materials_logs(str(ehx_path), panels_by_name, materials_map)
    except Exception as e:
        print(f"Writer raised exception: {e}")
        sys.exit(4)

    folder = ehx_path.parent
    exp = folder / 'expected.log'
    mat = folder / 'materials.log'
    print(f"expected.log exists: {exp.exists()}")
    print(f"materials.log exists: {mat.exists()}")

    def print_head(p):
        try:
            with p.open('r', encoding='utf-8') as fh:
                for i, ln in enumerate(fh):
                    if i >= 6:
                        break
                    print(ln.rstrip())
        except Exception as e:
            print(f"Failed to read {p}: {e}")

    if exp.exists():
        print('\n--- expected.log (head) ---')
        print_head(exp)
    if mat.exists():
        print('\n--- materials.log (head) ---')
        print_head(mat)

    print('\nDone.')

if __name__ == "__main__":
    main()
