import oldd, sys
p = r"c:\Users\THOMPSON\Downloads\EHX\Working\Backup\Testing\07-103-104.EHX"
panels, mats_map = oldd.parse_panels(p)
# find the panel with DisplayLabel 07_104
panel_name = None
panel_obj = None
for k, v in panels.items() if isinstance(panels, dict) else [(x.get('Name'), x) for x in panels]:
    pass
# panels may be list; handle both
panel_found = None
if isinstance(panels, dict):
    for k,v in panels.items():
        if (v.get('DisplayLabel') or '') == '07_104' or k == '07_104':
            panel_found = (k,v)
            break
else:
    for p in panels:
        if (p.get('DisplayLabel') or '') == '07_104' or p.get('Name') == '07_104':
            panel_found = (p.get('Name'), p)
            break
if not panel_found:
    print('Panel 07_104 not found; listing panels:')
    if isinstance(panels, dict):
        for k,v in panels.items():
            print('KEY', k, 'DisplayLabel', v.get('DisplayLabel'))
    else:
        for p in panels:
            print('Name', p.get('Name'), 'DisplayLabel', p.get('DisplayLabel'))
    sys.exit(0)

pname, pobj = panel_found
print('Found panel key:', pname)
print('Panel DisplayLabel:', pobj.get('DisplayLabel'))
materials = mats_map.get(pname, [])
print('Materials count:', len(materials))
for m in materials:
    if isinstance(m, dict) and (m.get('Label') == '25x137-L1' or m.get('SubAssembly') == '25x137-L1'):
        print('\nMATERIAL:')
        for k in sorted(m.keys()):
            print(k, ':', m[k])
        try:
            aff = oldd.get_aff_for_rough_opening(pobj, m)
            print('Computed AFF via get_aff_for_rough_opening():', aff)
        except Exception as e:
            print('Error computing AFF:', e)
        break
else:
    print('25x137-L1 material not found; printing first 10 materials:')
    for m in materials[:10]:
        print(m)
