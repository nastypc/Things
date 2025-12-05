import sys, importlib
sys.path.insert(0, r'c:\Users\edward\Downloads\ET\Sheathing')
try:
    importlib.import_module('src.newcdt')
    print('newcdt imported OK')
except Exception as e:
    import traceback
    traceback.print_exc()
    print('IMPORT_FAILED:', e)
