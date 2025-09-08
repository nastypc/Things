import importlib, traceback, sys

try:
    m = importlib.import_module('bak-gui_zones')
    print('module file:', getattr(m, '__file__', 'n/a'))
    print('has parse_panels:', hasattr(m, 'parse_panels'))
    try:
        panels, mats = m.parse_panels(r'C:\\Users\\THOMPSON\\Downloads\\EHX\\Working\\Test\\07_112.EHX')
        print('panels count:', len(panels) if hasattr(panels, '__len__') else 'n/a')
        print('sample panels keys (first 3):')
        from pprint import pprint
        try:
            pprint(panels[:3])
        except Exception:
            pprint(list(panels)[:3])
        print('materials map keys sample:', list(mats.keys())[:5])
    except Exception:
        traceback.print_exc()
except Exception:
    traceback.print_exc()
    sys.exit(1)
