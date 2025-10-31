# -*- mode: python ; coding: utf-8 -*-

import os
import sys

# Get the current directory
current_dir = os.path.dirname(os.path.abspath(SPEC))

a = Analysis(
    ['Vold.py'],
    pathex=[current_dir],
    binaries=[],
    datas=[
        # Include JSON state files
        ('gui_zones_state.json', '.'),
        ('gui_zones_last_folder.json', '.'),
        ('gui_zones_log.json', '.'),
        # Include any other data files if needed
    ],
    hiddenimports=[
        'tkinter',
        'tkinter.ttk',
        'tkinter.font',
        'tkinter.messagebox',
        'tkinter.filedialog',
        'xml.etree.ElementTree',
        'collections.defaultdict',
        'datetime',
        'json',
        'os',
        'sys',
        're',
        'math',
        'functools',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Vold',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Set to False for GUI app, True for console output
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add icon if you have one
)
