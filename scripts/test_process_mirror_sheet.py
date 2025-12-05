import os
from importlib.machinery import SourceFileLoader
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
mod = SourceFileLoader('main_module', os.path.join(root, 'src', 'main.py')).load_module()
cdt_dir = os.path.join(root, 'CDT')
path = os.path.join(cdt_dir, 'P1.CDT')
print('Calling process_cdt_file with mirror=True preserve_sheathing=True')
res = mod.process_cdt_file(path, actual_lengths=None, mirror=True, preserve_sheathing=True)
print('Result:', res)
