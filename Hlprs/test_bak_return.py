import importlib, traceback, sys

m = importlib.import_module('bak-gui_zones')
print('module file:', getattr(m, '__file__', 'n/a'))
ret = m.parse_panels(r'C:\\Users\\THOMPSON\\Downloads\\EHX\\Working\\Test\\07_112.EHX')
print('raw return repr:', repr(ret))
print('raw return type:', type(ret))
try:
    print('len:', len(ret))
except Exception as e:
    print('len() failed:', e)
