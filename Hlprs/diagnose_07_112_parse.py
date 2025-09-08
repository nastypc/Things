import importlib.util, sys, os
p = os.path.join(os.path.dirname(__file__), '..', 'bak-gui_zones.py')
p = os.path.abspath(p)
print('Loading module from', p)
spec = importlib.util.spec_from_file_location('bgz', p)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
fn = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Working', '07_112.EHX'))
print('Parsing', fn)
try:
    panels, mats = mod.parse_panels(fn)
    print('PANELS count:', len(panels))
    if panels:
        for i,p in enumerate(panels[:30]):
            print(i, 'Name=', p.get('Name'), 'DisplayLabel=', p.get('DisplayLabel'), 'Bundle=', p.get('Bundle') or p.get('BundleName') or p.get('BundleGuid'))
    print('MATERIALS keys sample:', list(mats.keys())[:10])
    # compute bundles mapping as rebuild_bundles does
    panels_by_name = {}
    if isinstance(panels, dict):
        panels_by_name.update(panels)
    else:
        for p in panels or []:
            if not p:
                continue
            name = p.get('Name') or f"Panel_{len(panels_by_name)+1}"
            panels_by_name[name] = p
    bundle_panels = {}
    for name,obj in panels_by_name.items():
        bkey = None
        if isinstance(obj, dict):
            bkey = obj.get('BundleGuid') or obj.get('BundleId') or obj.get('Bundle') or obj.get('BundleName') or obj.get('BundleLabel')
        if not bkey:
            bkey = 'Bundle'
        bundle_panels.setdefault(str(bkey), {'panels': [], 'label': obj.get('BundleName') or obj.get('Bundle') or obj.get('BundleLabel')}).get('panels').append(name)
    print('BUNDLE groups count:', len(bundle_panels))
    for k, v in bundle_panels.items():
        print('KEY:', k, 'label:', v.get('label'), 'count:', len(v.get('panels')))
except Exception as e:
    print('ERROR during parse:', e)
    import traceback; traceback.print_exc()
