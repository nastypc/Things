import importlib.util

spec = importlib.util.spec_from_file_location('bg', r'c:\Users\THOMPSON\Downloads\EHX\bak-gui_zones.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

ehx = r'c:\Users\THOMPSON\Downloads\EHX\Working\dummy_6_bundles.EHX'
panels, mats = mod.parse_panels(ehx)
print('Panels found:', len(panels))
for p in panels:
    print('-', (p.get('DisplayLabel') or p.get('Name') or ''), p.get('Name'), p.get('Bundle') or p.get('BundleName'))

# Print bundle summary
bundle_counts = {}
for p in panels:
    b = p.get('Bundle') or p.get('BundleName') or 'Bundle'
    bundle_counts[b] = bundle_counts.get(b, 0) + 1
print('\nBundle summary:')
for b, cnt in bundle_counts.items():
    print(f' - {b}: {cnt} panels')
