import os
import sys
from importlib.machinery import SourceFileLoader

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, root)
mod = SourceFileLoader('main_module', os.path.join(root, 'src', 'main.py')).load_module()

cdt_dir = os.path.join(root, 'CDT')
path = os.path.join(cdt_dir, 'P1.CDT')
print('Processing (create base x then mirror+sheet-flip):', path)
# First ensure a base 'x' adjusted file exists (recompute from original)
out_x = mod.process_cdt_file(path, actual_lengths=None, mirror=False, preserve_sheathing=False)
print(out_x)
# Now produce the mirror+sheet-flip output using the recomputed base
out = mod.process_cdt_file(path, actual_lengths=None, mirror=True, preserve_sheathing=True)
print(out)
