import sys, importlib
sys.path.insert(0, r'c:\Users\edward\Downloads\ET\Sheathing')
# Import newcdt to install the embedded glue monkeypatch
importlib.import_module('src.newcdt')
main = importlib.import_module('src.main')

# Adjust and write an example file using the patched generator
in_file = r'CDT\P1.CDT'
out_file = r'CDT\xP1x_test.CDT'
print('Processing', in_file, '->', out_file)
cdt = main.CDTFile(in_file)
cdt.parse()
cdt.adjust_sheathing_positions({})
cdt.write_adjusted_file(out_file, mirror=False, preserve_sheathing=False, force_regenerate_gl=True)
print('Done; written', out_file)
