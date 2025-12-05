import os
import sys

# Ensure workspace root is on sys.path so `src` can be imported when run from scripts/
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.main import process_cdt_file


if __name__ == '__main__':
    result = process_cdt_file(r'CDT/P1.CDT', debug=True, force_regenerate_gl=True)
    print(result)
