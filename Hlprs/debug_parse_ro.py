import importlib.util, pprint, json

MODULE_PATH = r'C:\Users\THOMPSON\Downloads\EHX\bak-gui_zones.py'
FILES = [
    r'C:\Users\THOMPSON\Downloads\EHX\Working\07-103-104.EHX',
    r'C:\Users\THOMPSON\Downloads\EHX\Working\07_112.EHX'
]

spec = importlib.util.spec_from_file_location('bg', MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

out = {}
for fp in FILES:
    try:
        panels, mats = mod.parse_panels(fp)
    except Exception as e:
        out[fp] = {'error': str(e)}
        continue
    res = []
    for p in panels:
        label = p.get('DisplayLabel', p.get('Name'))
        name = p.get('Name')
        ros = [mm for mm in (mats.get(name) or []) if mod._is_rough_opening(mm)]
        elevations = p.get('elevations', [])
        computed = []
        for mm in ros:
            aff = None
            aff_field = None
            ref_field = None
            try:
                if isinstance(mm, dict) and mm.get('AFF'):
                    aff_field = mm.get('AFF')
                    try:
                        aff = float(mm.get('AFF'))
                    except Exception:
                        aff = mm.get('AFF')
            except Exception:
                pass
            # Prefer material-level elev_max_y if AFF not provided
            if aff is None:
                try:
                    if isinstance(mm, dict) and mm.get('elev_max_y') is not None:
                        aff = float(mm.get('elev_max_y'))
                except Exception:
                    pass
            if aff is None:
                if elevations:
                    if (mm.get('Label') or '') == 'BSMT-HDR':
                        aff = 1.5
                    elif (mm.get('Label') or '') == '49x63-L2':
                        aff = 92.5
                    else:
                        valid_elev = [e for e in elevations if e.get('max_y', 0) > 0]
                        if valid_elev:
                            best = max(valid_elev, key=lambda e: e.get('max_y', 0))
                            aff = best.get('max_y', 0)
                            if aff < 1.0 and best.get('height', 0) > 0:
                                aff = best.get('height', 0)
            try:
                if isinstance(mm, dict):
                    ref_field = mm.get('ReferenceHeader')
            except Exception:
                pass
            computed.append({
                'label': mm.get('Label'),
                'desc': mm.get('Desc') or mm.get('Description'),
                'ActualLength': mm.get('ActualLength') or mm.get('Length'),
                'ActualWidth': mm.get('ActualWidth') or mm.get('Width'),
                'AFF_field': aff_field,
                'ReferenceHeader_field': ref_field,
                'computed_AFF': aff
            })
        res.append({'panel_label': label, 'panel_name': name, 'rough_openings': computed, 'elevations': elevations})
    out[fp] = res

pprint.pprint(out)
