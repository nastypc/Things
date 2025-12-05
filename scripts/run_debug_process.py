import sys
import traceback
import os
# Ensure workspace root is on sys.path
root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, root)
from src.main import process_cdt_file

p = r'CDT\\P1.CDT'
try:
    res = process_cdt_file(p, actual_lengths=None, mirror=False, preserve_sheathing=False)
    print('Result:\n', res)
except Exception as e:
    print('Exception during processing:')
    traceback.print_exc()
