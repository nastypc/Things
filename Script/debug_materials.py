import Vold

# Parse the EHX file
panels, materials_map = Vold.parse_panels('Test/05-100.ehx')
print('Panel names:', list(materials_map.keys()))

if '05-100' in materials_map:
    materials = materials_map['05-100']
    print(f'Total materials for 05-100: {len(materials)}')
    
    critical_studs = [m for m in materials if isinstance(m, dict) and m.get('Type', '').upper() == 'CRITICALSTUD']
    print(f'CriticalStud materials: {len(critical_studs)}')
    
    for i, cs in enumerate(critical_studs):
        print(f'  {i+1}: Label={cs.get("Label")}, SubAssembly={cs.get("SubAssembly")}, SubAssemblyGuid={cs.get("SubAssemblyGuid")}, FamilyMember={cs.get("FamilyMember")}, FamilyMemberName={cs.get("FamilyMemberName")}')
else:
    print('05-100 not found in materials_map')
    print('Available panels:', list(materials_map.keys()))